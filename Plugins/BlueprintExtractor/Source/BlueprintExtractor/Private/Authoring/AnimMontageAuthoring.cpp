#include "Authoring/AnimMontageAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "CoreGlobals.h"
#include "Animation/AnimCompositeBase.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "Animation/AnimNotifies/AnimNotifyState.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimTypes.h"
#include "Animation/Skeleton.h"
#include "Engine/SkeletalMesh.h"
#include "Factories/AnimMontageFactory.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace AnimMontageAuthoringInternal
{

static TSharedPtr<FJsonObject> NormalizePayload(const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* MontageObject = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("animMontage"), MontageObject)
		&& MontageObject
		&& MontageObject->IsValid())
	{
		return *MontageObject;
	}

	return PayloadJson;
}

static TArray<TSharedPtr<FJsonValue>> GetArrayField(const TSharedPtr<FJsonObject>& Payload,
                                                    const TCHAR* FieldName)
{
	const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
	if (Payload.IsValid()
		&& Payload->TryGetArrayField(FieldName, Array)
		&& Array)
	{
		return *Array;
	}

	return {};
}

static bool AppendValidationSummary(FAssetMutationContext& Context,
                                    const TArray<FString>& Errors,
                                    const FString& Summary)
{
	const bool bSuccess = Errors.Num() == 0;
	Context.SetValidationSummary(bSuccess, Summary, Errors);
	for (const FString& Error : Errors)
	{
		Context.AddError(TEXT("validation_error"), Error, Context.AssetPath);
	}
	return bSuccess;
}

static bool TryGetNumberField(const TSharedPtr<FJsonObject>& Object,
                              const TCHAR* FieldName,
                              double& OutValue)
{
	return Object.IsValid() && Object->TryGetNumberField(FieldName, OutValue);
}

static bool TryGetBoolFieldEither(const TSharedPtr<FJsonObject>& Object,
                                  const TCHAR* FieldNameA,
                                  const TCHAR* FieldNameB,
                                  bool& OutValue)
{
	return (Object.IsValid() && Object->TryGetBoolField(FieldNameA, OutValue))
		|| (Object.IsValid() && Object->TryGetBoolField(FieldNameB, OutValue));
}

static bool IsValidMontageTime(const UAnimMontage* AnimMontage, const float Time)
{
	if (!AnimMontage)
	{
		return false;
	}

	const float Length = AnimMontage->GetPlayLength();
	return Time >= 0.0f && Time <= Length + UE_KINDA_SMALL_NUMBER;
}

static float GetRequestedSequenceLength(const TSharedPtr<FJsonObject>& Payload)
{
	double RequestedLength = 0.0;
	if (TryGetNumberField(Payload, TEXT("sequenceLength"), RequestedLength) && RequestedLength > 0.0)
	{
		return static_cast<float>(RequestedLength);
	}

	return 0.0f;
}

static void RefreshMontageCompositeLength(UAnimMontage* AnimMontage,
                                         const TSharedPtr<FJsonObject>& Payload)
{
	if (!AnimMontage)
	{
		return;
	}

	float CompositeLength = AnimMontage->CalculateSequenceLength();
	if (const float RequestedLength = GetRequestedSequenceLength(Payload); RequestedLength > 0.0f)
	{
		CompositeLength = FMath::Max(CompositeLength, RequestedLength);
	}

	if (CompositeLength > 0.0f)
	{
		AnimMontage->SetCompositeLength(CompositeLength);
	}
}

static UAnimSequence* ResolveSourceAnimation(const TSharedPtr<FJsonObject>& Payload,
                                             TArray<FString>& OutErrors)
{
	if (!Payload.IsValid())
	{
		return nullptr;
	}

	FString SourceAnimationPath;
	if (!(Payload->TryGetStringField(TEXT("sourceAnimation"), SourceAnimationPath)
		|| Payload->TryGetStringField(TEXT("sourceAnimSequence"), SourceAnimationPath))
		|| SourceAnimationPath.IsEmpty())
	{
		return nullptr;
	}

	UAnimSequence* SourceAnimation = LoadObject<UAnimSequence>(nullptr, *SourceAnimationPath);
	if (!SourceAnimation)
	{
		OutErrors.Add(FString::Printf(TEXT("Failed to load source animation '%s'."), *SourceAnimationPath));
	}

	return SourceAnimation;
}

static USkeleton* ResolveSkeleton(const TSharedPtr<FJsonObject>& Payload,
                                  UAnimSequence* SourceAnimation,
                                  TArray<FString>& OutErrors)
{
	if (SourceAnimation)
	{
		return SourceAnimation->GetSkeleton();
	}

	if (!Payload.IsValid())
	{
		OutErrors.Add(TEXT("AnimMontage payload is missing."));
		return nullptr;
	}

	FString SkeletonPath;
	if (!(Payload->TryGetStringField(TEXT("skeleton"), SkeletonPath)
		|| Payload->TryGetStringField(TEXT("skeletonPath"), SkeletonPath))
		|| SkeletonPath.IsEmpty())
	{
		OutErrors.Add(TEXT("AnimMontage creation requires a skeleton or sourceAnimation."));
		return nullptr;
	}

	USkeleton* Skeleton = LoadObject<USkeleton>(nullptr, *SkeletonPath);
	if (!Skeleton)
	{
		OutErrors.Add(FString::Printf(TEXT("Failed to load skeleton '%s'."), *SkeletonPath));
	}

	return Skeleton;
}

static USkeletalMesh* ResolvePreviewMesh(const TSharedPtr<FJsonObject>& Payload,
                                         TArray<FString>& OutErrors)
{
	if (!Payload.IsValid())
	{
		return nullptr;
	}

	FString PreviewMeshPath;
	if (!(Payload->TryGetStringField(TEXT("previewMesh"), PreviewMeshPath)
		|| Payload->TryGetStringField(TEXT("previewSkeletalMesh"), PreviewMeshPath))
		|| PreviewMeshPath.IsEmpty())
	{
		return nullptr;
	}

	USkeletalMesh* PreviewMesh = LoadObject<USkeletalMesh>(nullptr, *PreviewMeshPath);
	if (!PreviewMesh)
	{
		OutErrors.Add(FString::Printf(TEXT("Failed to load preview mesh '%s'."), *PreviewMeshPath));
	}

	return PreviewMesh;
}

static FString GetNotifyGuidString(const FAnimNotifyEvent& NotifyEvent)
{
#if WITH_EDITORONLY_DATA
	return NotifyEvent.Guid.IsValid()
		? NotifyEvent.Guid.ToString(EGuidFormats::DigitsWithHyphens)
		: FString();
#else
	return FString();
#endif
}

static FString BuildNotifyId(const FAnimNotifyEvent& NotifyEvent, const int32 NotifyIndex)
{
	const FString NotifyGuid = GetNotifyGuidString(NotifyEvent);
	if (!NotifyGuid.IsEmpty())
	{
		return NotifyGuid;
	}

	return FString::Printf(TEXT("index:%d"), NotifyIndex);
}

static int32 EnsureTrackIndex(UAnimMontage* AnimMontage,
                              const TSharedPtr<FJsonObject>& SourceObject)
{
	if (!AnimMontage)
	{
		return INDEX_NONE;
	}

#if WITH_EDITORONLY_DATA
	if (AnimMontage->AnimNotifyTracks.Num() == 0)
	{
		AnimMontage->AnimNotifyTracks.Add(FAnimNotifyTrack(TEXT("1"), FLinearColor::White));
	}

	FString TrackName;
	if (SourceObject.IsValid()
		&& SourceObject->TryGetStringField(TEXT("trackName"), TrackName)
		&& !TrackName.IsEmpty())
	{
		const FName DesiredTrackName(*TrackName);
		for (int32 Index = 0; Index < AnimMontage->AnimNotifyTracks.Num(); ++Index)
		{
			if (AnimMontage->AnimNotifyTracks[Index].TrackName == DesiredTrackName)
			{
				return Index;
			}
		}

		return AnimMontage->AnimNotifyTracks.Add(FAnimNotifyTrack(DesiredTrackName, FLinearColor::White));
	}

	double TrackIndexValue = 0.0;
	if (SourceObject.IsValid() && SourceObject->TryGetNumberField(TEXT("trackIndex"), TrackIndexValue))
	{
		const int32 DesiredIndex = FMath::Max(0, static_cast<int32>(TrackIndexValue));
		while (AnimMontage->AnimNotifyTracks.Num() <= DesiredIndex)
		{
			AnimMontage->AnimNotifyTracks.Add(FAnimNotifyTrack(
				*FString::FromInt(AnimMontage->AnimNotifyTracks.Num() + 1),
				FLinearColor::White));
		}
		return DesiredIndex;
	}

	return 0;
#else
	return 0;
#endif
}

static bool ParseNotifyEventType(const FString& NotifyTypeString,
                                 bool& bOutIsNotifyState,
                                 TArray<FString>& OutErrors,
                                 const FString& NotifyPath)
{
	if (NotifyTypeString.IsEmpty()
		|| NotifyTypeString.Equals(TEXT("Notify"), ESearchCase::IgnoreCase))
	{
		bOutIsNotifyState = false;
		return true;
	}

	if (NotifyTypeString.Equals(TEXT("NotifyState"), ESearchCase::IgnoreCase))
	{
		bOutIsNotifyState = true;
		return true;
	}

	if (NotifyTypeString.Equals(TEXT("Named"), ESearchCase::IgnoreCase))
	{
		bOutIsNotifyState = false;
		return true;
	}

	OutErrors.Add(FString::Printf(TEXT("%s.notifyType: unsupported notifyType '%s'."),
		*NotifyPath,
		*NotifyTypeString));
	return false;
}

static void ApplyOptionalNotifySettings(FAnimNotifyEvent& NotifyEvent,
                                        const TSharedPtr<FJsonObject>& NotifyObject,
                                        TArray<FString>& OutErrors,
                                        const FString& NotifyPath)
{
	double NumberValue = 0.0;
	if (TryGetNumberField(NotifyObject, TEXT("notifyTriggerChance"), NumberValue))
	{
		NotifyEvent.NotifyTriggerChance = static_cast<float>(NumberValue);
	}

	FString EnumText;
	if (NotifyObject.IsValid() && NotifyObject->TryGetStringField(TEXT("notifyFilterType"), EnumText) && !EnumText.IsEmpty())
	{
		const UEnum* FilterEnum = StaticEnum<ENotifyFilterType::Type>();
		const int64 EnumValue = FilterEnum ? FilterEnum->GetValueByNameString(EnumText) : INDEX_NONE;
		if (EnumValue == INDEX_NONE)
		{
			OutErrors.Add(FString::Printf(TEXT("%s.notifyFilterType: invalid value '%s'."),
				*NotifyPath,
				*EnumText));
		}
		else
		{
			NotifyEvent.NotifyFilterType = static_cast<ENotifyFilterType::Type>(EnumValue);
		}
	}

	if (TryGetNumberField(NotifyObject, TEXT("notifyFilterLOD"), NumberValue))
	{
		NotifyEvent.NotifyFilterLOD = static_cast<int32>(NumberValue);
	}

	if (NotifyObject.IsValid() && NotifyObject->TryGetStringField(TEXT("montageTickType"), EnumText) && !EnumText.IsEmpty())
	{
		const UEnum* TickTypeEnum = StaticEnum<EMontageNotifyTickType::Type>();
		const int64 EnumValue = TickTypeEnum ? TickTypeEnum->GetValueByNameString(EnumText) : INDEX_NONE;
		if (EnumValue == INDEX_NONE)
		{
			OutErrors.Add(FString::Printf(TEXT("%s.montageTickType: invalid value '%s'."),
				*NotifyPath,
				*EnumText));
		}
		else
		{
			NotifyEvent.MontageTickType = static_cast<EMontageNotifyTickType::Type>(EnumValue);
		}
	}

	bool bBoolValue = false;
	if (TryGetBoolFieldEither(NotifyObject, TEXT("canBeFilteredViaRequest"), TEXT("bCanBeFilteredViaRequest"), bBoolValue))
	{
		NotifyEvent.bCanBeFilteredViaRequest = bBoolValue;
	}
	if (TryGetBoolFieldEither(NotifyObject, TEXT("triggerOnDedicatedServer"), TEXT("bTriggerOnDedicatedServer"), bBoolValue))
	{
		NotifyEvent.bTriggerOnDedicatedServer = bBoolValue;
	}
	if (TryGetBoolFieldEither(NotifyObject, TEXT("triggerOnFollower"), TEXT("bTriggerOnFollower"), bBoolValue))
	{
		NotifyEvent.bTriggerOnFollower = bBoolValue;
	}
	if (TryGetBoolFieldEither(NotifyObject, TEXT("convertedFromBranchingPoint"), TEXT("bConvertedFromBranchingPoint"), bBoolValue))
	{
		NotifyEvent.bConvertedFromBranchingPoint = bBoolValue;
	}
}

static bool BuildNotifyEvent(UAnimMontage* AnimMontage,
                             const TSharedPtr<FJsonObject>& NotifyObject,
                             const int32 NotifyIndex,
                             FAnimNotifyEvent& OutEvent,
                             TArray<FString>& OutErrors)
{
	const FString NotifyPath = FString::Printf(TEXT("notifies[%d]"), NotifyIndex);
	if (!NotifyObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s: expected notify object."), *NotifyPath));
		return false;
	}

	double TriggerTime = 0.0;
	if (!(TryGetNumberField(NotifyObject, TEXT("triggerTime"), TriggerTime)
		|| TryGetNumberField(NotifyObject, TEXT("startTime"), TriggerTime)
		|| TryGetNumberField(NotifyObject, TEXT("time"), TriggerTime)))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.triggerTime: missing trigger time."), *NotifyPath));
		return false;
	}

	if (!IsValidMontageTime(AnimMontage, static_cast<float>(TriggerTime)))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.triggerTime: time %g is outside AnimMontage range."),
			*NotifyPath,
			TriggerTime));
		return false;
	}

	FString NotifyName;
	NotifyObject->TryGetStringField(TEXT("notifyName"), NotifyName);

	FString NotifyClassPath;
	NotifyObject->TryGetStringField(TEXT("notifyClassPath"), NotifyClassPath);

	FString NotifyTypeString;
	NotifyObject->TryGetStringField(TEXT("notifyType"), NotifyTypeString);

	bool bIsNotifyState = false;
	if (!ParseNotifyEventType(NotifyTypeString, bIsNotifyState, OutErrors, NotifyPath))
	{
		return false;
	}

	OutEvent = FAnimNotifyEvent();
	OutEvent.NotifyName = NAME_None;
	OutEvent.Link(AnimMontage, static_cast<float>(TriggerTime));
	OutEvent.TriggerTimeOffset = GetTriggerTimeOffsetForType(
		AnimMontage->CalculateOffsetForNotify(static_cast<float>(TriggerTime)));
	OutEvent.TrackIndex = EnsureTrackIndex(AnimMontage, NotifyObject);

	if (!NotifyClassPath.IsEmpty())
	{
		UClass* NotifyClass = FAuthoringHelpers::ResolveClass(
			NotifyClassPath,
			bIsNotifyState ? UAnimNotifyState::StaticClass() : UAnimNotify::StaticClass());
		if (!NotifyClass)
		{
			OutErrors.Add(FString::Printf(TEXT("%s.notifyClassPath: failed to resolve class '%s'."),
				*NotifyPath,
				*NotifyClassPath));
			return false;
		}

		if (bIsNotifyState)
		{
			OutEvent.NotifyStateClass = NewObject<UAnimNotifyState>(
				AnimMontage,
				NotifyClass,
				NAME_None,
				RF_Transactional);
			OutEvent.Notify = nullptr;
		}
		else
		{
			OutEvent.Notify = NewObject<UAnimNotify>(
				AnimMontage,
				NotifyClass,
				NAME_None,
				RF_Transactional);
			OutEvent.NotifyStateClass = nullptr;
		}
	}
	else
	{
		OutEvent.Notify = nullptr;
		OutEvent.NotifyStateClass = nullptr;
	}

	double Duration = 0.0;
	if (!TryGetNumberField(NotifyObject, TEXT("duration"), Duration))
	{
		double EndTriggerTime = 0.0;
		if (TryGetNumberField(NotifyObject, TEXT("endTriggerTime"), EndTriggerTime))
		{
			Duration = EndTriggerTime - TriggerTime;
		}
	}

	if (OutEvent.NotifyStateClass)
	{
		if (Duration < 0.0)
		{
			OutErrors.Add(FString::Printf(TEXT("%s.duration: duration must be non-negative."), *NotifyPath));
			return false;
		}

		if (!IsValidMontageTime(AnimMontage, static_cast<float>(TriggerTime + Duration)))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.endTriggerTime: state notify exceeds AnimMontage range."),
				*NotifyPath));
			return false;
		}

		OutEvent.SetDuration(static_cast<float>(Duration));
		OutEvent.EndLink.Link(AnimMontage, OutEvent.EndLink.GetTime());
	}
	else
	{
		OutEvent.SetDuration(0.0f);
	}

	if (OutEvent.Notify || OutEvent.NotifyStateClass)
	{
		UObject* NotifyInstance = OutEvent.Notify
			? static_cast<UObject*>(OutEvent.Notify)
			: static_cast<UObject*>(OutEvent.NotifyStateClass);
		if (!NotifyName.IsEmpty())
		{
			OutEvent.NotifyName = FName(*NotifyName);
		}
		else if (OutEvent.Notify)
		{
			OutEvent.NotifyName = FName(*OutEvent.Notify->GetNotifyName());
		}
		else
		{
			OutEvent.NotifyName = FName(*OutEvent.NotifyStateClass->GetNotifyName());
		}

		const TSharedPtr<FJsonObject>* PropertiesObject = nullptr;
		if (NotifyObject->TryGetObjectField(TEXT("properties"), PropertiesObject)
			&& PropertiesObject
			&& PropertiesObject->IsValid())
		{
			FPropertySerializer::ApplyPropertiesFromJson(
				NotifyInstance,
				*PropertiesObject,
				OutErrors,
				false,
				true);
		}
	}
	else if (NotifyName.IsEmpty())
	{
		OutErrors.Add(FString::Printf(TEXT("%s: named notifies require notifyName when no notifyClassPath is supplied."),
			*NotifyPath));
		return false;
	}
	else
	{
		OutEvent.NotifyName = FName(*NotifyName);
	}

#if WITH_EDITORONLY_DATA
	FString NotifyGuidString;
	if (!NotifyObject->TryGetStringField(TEXT("notifyGuid"), NotifyGuidString))
	{
		NotifyObject->TryGetStringField(TEXT("notifyId"), NotifyGuidString);
	}

	if (!NotifyGuidString.IsEmpty() && !FGuid::Parse(NotifyGuidString, OutEvent.Guid))
	{
		OutEvent.Guid = FGuid::NewGuid();
	}
	else if (!OutEvent.Guid.IsValid())
	{
		OutEvent.Guid = FGuid::NewGuid();
	}
#endif

	ApplyOptionalNotifySettings(OutEvent, NotifyObject, OutErrors, NotifyPath);
	return OutErrors.Num() == 0;
}

struct FNotifySelector
{
	FString NotifyId;
	FString NotifyGuid;
	int32 NotifyIndex = INDEX_NONE;
};

static bool BuildNotifySelector(const TSharedPtr<FJsonObject>& Payload,
                                FNotifySelector& OutSelector,
                                FString& OutError)
{
	if (!Payload.IsValid())
	{
		OutError = TEXT("Notify selector payload must be an object.");
		return false;
	}

	const TSharedPtr<FJsonObject>* SelectorObject = nullptr;
	const TSharedPtr<FJsonObject> Selector = (Payload->TryGetObjectField(TEXT("selector"), SelectorObject)
		&& SelectorObject
		&& SelectorObject->IsValid())
		? *SelectorObject
		: Payload;

	double NotifyIndexValue = 0.0;
	Selector->TryGetStringField(TEXT("notifyId"), OutSelector.NotifyId);
	Selector->TryGetStringField(TEXT("notifyGuid"), OutSelector.NotifyGuid);
	if (Selector->TryGetNumberField(TEXT("notifyIndex"), NotifyIndexValue)
		|| Selector->TryGetNumberField(TEXT("index"), NotifyIndexValue))
	{
		OutSelector.NotifyIndex = static_cast<int32>(NotifyIndexValue);
	}

	if (!OutSelector.NotifyId.IsEmpty()
		|| !OutSelector.NotifyGuid.IsEmpty()
		|| OutSelector.NotifyIndex != INDEX_NONE)
	{
		return true;
	}

	OutError = TEXT("Notify selector requires notifyId, notifyGuid, or notifyIndex.");
	return false;
}

static FAnimNotifyEvent* FindNotifyBySelector(UAnimMontage* AnimMontage,
                                              const FNotifySelector& Selector,
                                              int32& OutNotifyIndex)
{
	if (!AnimMontage)
	{
		return nullptr;
	}

	if (Selector.NotifyIndex != INDEX_NONE && AnimMontage->Notifies.IsValidIndex(Selector.NotifyIndex))
	{
		OutNotifyIndex = Selector.NotifyIndex;
		return &AnimMontage->Notifies[Selector.NotifyIndex];
	}

	for (int32 Index = 0; Index < AnimMontage->Notifies.Num(); ++Index)
	{
		FAnimNotifyEvent& NotifyEvent = AnimMontage->Notifies[Index];
		if (!Selector.NotifyId.IsEmpty() && BuildNotifyId(NotifyEvent, Index) == Selector.NotifyId)
		{
			OutNotifyIndex = Index;
			return &NotifyEvent;
		}

#if WITH_EDITORONLY_DATA
		if (!Selector.NotifyGuid.IsEmpty()
			&& NotifyEvent.Guid.IsValid()
			&& NotifyEvent.Guid.ToString(EGuidFormats::DigitsWithHyphens) == Selector.NotifyGuid)
		{
			OutNotifyIndex = Index;
			return &NotifyEvent;
		}
#endif
	}

	return nullptr;
}

static bool PatchNotify(UAnimMontage* AnimMontage,
                        const TSharedPtr<FJsonObject>& Payload,
                        TArray<FString>& OutErrors)
{
	FNotifySelector Selector;
	FString SelectorError;
	if (!BuildNotifySelector(Payload, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	int32 NotifyIndex = INDEX_NONE;
	FAnimNotifyEvent* NotifyEvent = FindNotifyBySelector(AnimMontage, Selector, NotifyIndex);
	if (!NotifyEvent)
	{
		OutErrors.Add(TEXT("Failed to find AnimMontage notify for patch selector."));
		return false;
	}

	const TSharedPtr<FJsonObject>* NotifyPatchObject = nullptr;
	const TSharedPtr<FJsonObject> PatchObject = (Payload.IsValid()
		&& Payload->TryGetObjectField(TEXT("notify"), NotifyPatchObject)
		&& NotifyPatchObject
		&& NotifyPatchObject->IsValid())
		? *NotifyPatchObject
		: Payload;

	if (!PatchObject.IsValid())
	{
		OutErrors.Add(TEXT("patch_notify requires a notify payload."));
		return false;
	}

	FString NotifyClassPath;
	PatchObject->TryGetStringField(TEXT("notifyClassPath"), NotifyClassPath);

	FString NotifyTypeString;
	PatchObject->TryGetStringField(TEXT("notifyType"), NotifyTypeString);

	if (!NotifyClassPath.IsEmpty() || !NotifyTypeString.IsEmpty())
	{
		bool bIsNotifyState = NotifyEvent->NotifyStateClass != nullptr;
		if (!NotifyTypeString.IsEmpty()
			&& !ParseNotifyEventType(NotifyTypeString, bIsNotifyState, OutErrors, TEXT("notify")))
		{
			return false;
		}

		if (NotifyClassPath.IsEmpty())
		{
			NotifyEvent->Notify = nullptr;
			NotifyEvent->NotifyStateClass = nullptr;
			NotifyEvent->SetDuration(0.0f);
		}
		else
		{
			UClass* NotifyClass = FAuthoringHelpers::ResolveClass(
				NotifyClassPath,
				bIsNotifyState ? UAnimNotifyState::StaticClass() : UAnimNotify::StaticClass());
			if (!NotifyClass)
			{
				OutErrors.Add(FString::Printf(TEXT("notify.notifyClassPath: failed to resolve class '%s'."),
					*NotifyClassPath));
				return false;
			}

			const bool bNeedsReplacement = bIsNotifyState
				? (!NotifyEvent->NotifyStateClass || NotifyEvent->NotifyStateClass->GetClass() != NotifyClass)
				: (!NotifyEvent->Notify || NotifyEvent->Notify->GetClass() != NotifyClass);

			if (bNeedsReplacement)
			{
				if (bIsNotifyState)
				{
					NotifyEvent->NotifyStateClass = NewObject<UAnimNotifyState>(
						AnimMontage,
						NotifyClass,
						NAME_None,
						RF_Transactional);
					NotifyEvent->Notify = nullptr;
				}
				else
				{
					NotifyEvent->Notify = NewObject<UAnimNotify>(
						AnimMontage,
						NotifyClass,
						NAME_None,
						RF_Transactional);
					NotifyEvent->NotifyStateClass = nullptr;
					NotifyEvent->SetDuration(0.0f);
				}
			}
		}
	}

	double TriggerTime = 0.0;
	if (TryGetNumberField(PatchObject, TEXT("triggerTime"), TriggerTime)
		|| TryGetNumberField(PatchObject, TEXT("startTime"), TriggerTime)
		|| TryGetNumberField(PatchObject, TEXT("time"), TriggerTime))
	{
		if (!IsValidMontageTime(AnimMontage, static_cast<float>(TriggerTime)))
		{
			OutErrors.Add(FString::Printf(TEXT("notify.triggerTime: time %g is outside AnimMontage range."),
				TriggerTime));
			return false;
		}

		NotifyEvent->Link(AnimMontage, static_cast<float>(TriggerTime));
		NotifyEvent->TriggerTimeOffset = GetTriggerTimeOffsetForType(
			AnimMontage->CalculateOffsetForNotify(static_cast<float>(TriggerTime)));
	}

	double Duration = 0.0;
	bool bHasDuration = TryGetNumberField(PatchObject, TEXT("duration"), Duration);
	if (!bHasDuration)
	{
		double EndTriggerTime = 0.0;
		if (TryGetNumberField(PatchObject, TEXT("endTriggerTime"), EndTriggerTime))
		{
			bHasDuration = true;
			Duration = EndTriggerTime - NotifyEvent->GetTriggerTime();
		}
	}

	if (bHasDuration)
	{
		if (!NotifyEvent->NotifyStateClass)
		{
			OutErrors.Add(TEXT("notify.duration: duration may only be set on state notifies."));
			return false;
		}

		if (Duration < 0.0
			|| !IsValidMontageTime(AnimMontage, NotifyEvent->GetTriggerTime() + static_cast<float>(Duration)))
		{
			OutErrors.Add(TEXT("notify.duration: state notify duration is invalid for this AnimMontage."));
			return false;
		}

		NotifyEvent->SetDuration(static_cast<float>(Duration));
		NotifyEvent->EndLink.Link(AnimMontage, NotifyEvent->EndLink.GetTime());
	}

	if (PatchObject->HasField(TEXT("trackName")) || PatchObject->HasField(TEXT("trackIndex")))
	{
		NotifyEvent->TrackIndex = EnsureTrackIndex(AnimMontage, PatchObject);
	}

	FString NotifyName;
	if (PatchObject->TryGetStringField(TEXT("notifyName"), NotifyName))
	{
		NotifyEvent->NotifyName = NotifyName.IsEmpty() ? NAME_None : FName(*NotifyName);
	}
	else if (NotifyEvent->Notify)
	{
		NotifyEvent->NotifyName = FName(*NotifyEvent->Notify->GetNotifyName());
	}
	else if (NotifyEvent->NotifyStateClass)
	{
		NotifyEvent->NotifyName = FName(*NotifyEvent->NotifyStateClass->GetNotifyName());
	}

	const TSharedPtr<FJsonObject>* PropertiesObject = nullptr;
	if (PatchObject->TryGetObjectField(TEXT("properties"), PropertiesObject)
		&& PropertiesObject
		&& PropertiesObject->IsValid())
	{
		UObject* NotifyInstance = NotifyEvent->Notify
			? static_cast<UObject*>(NotifyEvent->Notify)
			: static_cast<UObject*>(NotifyEvent->NotifyStateClass);
		if (!NotifyInstance)
		{
			OutErrors.Add(TEXT("notify.properties: named notifies do not support object property patches."));
			return false;
		}

		FPropertySerializer::ApplyPropertiesFromJson(
			NotifyInstance,
			*PropertiesObject,
			OutErrors,
			false,
			true);
	}

#if WITH_EDITORONLY_DATA
	FString NotifyGuidString;
	if (PatchObject->TryGetStringField(TEXT("notifyGuid"), NotifyGuidString)
		|| PatchObject->TryGetStringField(TEXT("notifyId"), NotifyGuidString))
	{
		FGuid ParsedGuid;
		if (FGuid::Parse(NotifyGuidString, ParsedGuid))
		{
			NotifyEvent->Guid = ParsedGuid;
		}
	}
#endif

	ApplyOptionalNotifySettings(*NotifyEvent, PatchObject, OutErrors, TEXT("notify"));
	return OutErrors.Num() == 0;
}

static bool ReplaceNotifies(UAnimMontage* AnimMontage,
                            const TArray<TSharedPtr<FJsonValue>>& Notifies,
                            TArray<FString>& OutErrors)
{
	TArray<FAnimNotifyEvent> NewNotifies;
	NewNotifies.Reserve(Notifies.Num());

	for (int32 Index = 0; Index < Notifies.Num(); ++Index)
	{
		FAnimNotifyEvent& NotifyEvent = NewNotifies.AddDefaulted_GetRef();
		const TSharedPtr<FJsonObject> NotifyObject = Notifies[Index].IsValid() ? Notifies[Index]->AsObject() : nullptr;
		if (!BuildNotifyEvent(AnimMontage, NotifyObject, Index, NotifyEvent, OutErrors))
		{
			return false;
		}
	}

	AnimMontage->Notifies = MoveTemp(NewNotifies);
	return true;
}

static bool ReplaceSlots(UAnimMontage* AnimMontage,
                         const TArray<TSharedPtr<FJsonValue>>& Slots,
                         TArray<FString>& OutErrors)
{
	TArray<FSlotAnimationTrack> NewTracks;
	NewTracks.Reserve(Slots.Num());

	for (int32 SlotIndex = 0; SlotIndex < Slots.Num(); ++SlotIndex)
	{
		const FString SlotPath = FString::Printf(TEXT("slots[%d]"), SlotIndex);
		const TSharedPtr<FJsonObject> SlotObject = Slots[SlotIndex].IsValid() ? Slots[SlotIndex]->AsObject() : nullptr;
		if (!SlotObject.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s: expected slot object."), *SlotPath));
			return false;
		}

		FString SlotName;
		if (!(SlotObject->TryGetStringField(TEXT("slotName"), SlotName)
			|| SlotObject->TryGetStringField(TEXT("name"), SlotName))
			|| SlotName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.slotName: missing slot name."), *SlotPath));
			return false;
		}

		FSlotAnimationTrack& NewTrack = NewTracks.AddDefaulted_GetRef();
		NewTrack.SlotName = FName(*SlotName);

		const TArray<TSharedPtr<FJsonValue>>* Segments = nullptr;
		if (!SlotObject->TryGetArrayField(TEXT("segments"), Segments) || !Segments)
		{
			continue;
		}

		for (int32 SegmentIndex = 0; SegmentIndex < Segments->Num(); ++SegmentIndex)
		{
			const FString SegmentPath = FString::Printf(TEXT("%s.segments[%d]"), *SlotPath, SegmentIndex);
			const TSharedPtr<FJsonObject> SegmentObject = (*Segments)[SegmentIndex].IsValid() ? (*Segments)[SegmentIndex]->AsObject() : nullptr;
			if (!SegmentObject.IsValid())
			{
				OutErrors.Add(FString::Printf(TEXT("%s: expected segment object."), *SegmentPath));
				return false;
			}

			FString AnimationPath;
			if (!(SegmentObject->TryGetStringField(TEXT("animSequence"), AnimationPath)
				|| SegmentObject->TryGetStringField(TEXT("animation"), AnimationPath))
				|| AnimationPath.IsEmpty())
			{
				OutErrors.Add(FString::Printf(TEXT("%s.animSequence: missing animation reference."), *SegmentPath));
				return false;
			}

			UAnimSequenceBase* Animation = Cast<UAnimSequenceBase>(
				FAuthoringHelpers::ResolveObject(AnimationPath, UAnimSequenceBase::StaticClass()));
			if (!Animation)
			{
				OutErrors.Add(FString::Printf(TEXT("%s.animSequence: failed to load animation '%s'."),
					*SegmentPath,
					*AnimationPath));
				return false;
			}

			if (AnimMontage->GetSkeleton() && Animation->GetSkeleton() != AnimMontage->GetSkeleton())
			{
				OutErrors.Add(FString::Printf(TEXT("%s.animSequence: animation skeleton does not match montage skeleton."),
					*SegmentPath));
				return false;
			}

			FAnimSegment& Segment = NewTrack.AnimTrack.AnimSegments.AddDefaulted_GetRef();
			Segment.SetAnimReference(Animation, true);
			Segment.StartPos = NewTrack.AnimTrack.GetLength();

			double NumberValue = 0.0;
			if (TryGetNumberField(SegmentObject, TEXT("startTime"), NumberValue))
			{
				Segment.StartPos = static_cast<float>(NumberValue);
			}
			if (TryGetNumberField(SegmentObject, TEXT("animStartTime"), NumberValue))
			{
				Segment.AnimStartTime = static_cast<float>(NumberValue);
			}
			if (TryGetNumberField(SegmentObject, TEXT("animEndTime"), NumberValue))
			{
				Segment.AnimEndTime = static_cast<float>(NumberValue);
			}
			if (TryGetNumberField(SegmentObject, TEXT("animPlayRate"), NumberValue))
			{
				Segment.AnimPlayRate = static_cast<float>(NumberValue);
			}
			if (TryGetNumberField(SegmentObject, TEXT("loopingCount"), NumberValue))
			{
				Segment.LoopingCount = FMath::Max(1, static_cast<int32>(NumberValue));
			}
		}
	}

	AnimMontage->SlotAnimTracks = MoveTemp(NewTracks);
	return true;
}

static bool ReplaceSections(UAnimMontage* AnimMontage,
                            const TArray<TSharedPtr<FJsonValue>>& Sections,
                            TArray<FString>& OutErrors)
{
	TArray<FCompositeSection> NewSections;
	TSet<FName> SeenNames;

	for (int32 SectionIndex = 0; SectionIndex < Sections.Num(); ++SectionIndex)
	{
		const FString SectionPath = FString::Printf(TEXT("sections[%d]"), SectionIndex);
		const TSharedPtr<FJsonObject> SectionObject = Sections[SectionIndex].IsValid() ? Sections[SectionIndex]->AsObject() : nullptr;
		if (!SectionObject.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s: expected section object."), *SectionPath));
			return false;
		}

		FString SectionName;
		if (!(SectionObject->TryGetStringField(TEXT("sectionName"), SectionName)
			|| SectionObject->TryGetStringField(TEXT("name"), SectionName))
			|| SectionName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.sectionName: missing section name."), *SectionPath));
			return false;
		}

		const FName SectionFName(*SectionName);
		if (SeenNames.Contains(SectionFName))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.sectionName: duplicate section '%s'."), *SectionPath, *SectionName));
			return false;
		}
		SeenNames.Add(SectionFName);

		double StartTime = 0.0;
		if (!(TryGetNumberField(SectionObject, TEXT("startTime"), StartTime)
			|| TryGetNumberField(SectionObject, TEXT("time"), StartTime)))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.startTime: missing section start time."), *SectionPath));
			return false;
		}

		if (!IsValidMontageTime(AnimMontage, static_cast<float>(StartTime)))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.startTime: time %g is outside AnimMontage range."),
				*SectionPath,
				StartTime));
			return false;
		}

		FCompositeSection& Section = NewSections.AddDefaulted_GetRef();
		Section.SectionName = SectionFName;
		Section.Link(AnimMontage, static_cast<float>(StartTime));

		FString NextSectionName;
		if (SectionObject->TryGetStringField(TEXT("nextSectionName"), NextSectionName) && !NextSectionName.IsEmpty())
		{
			Section.NextSectionName = FName(*NextSectionName);
		}
	}

	NewSections.Sort([](const FCompositeSection& Left, const FCompositeSection& Right)
	{
		return Left.GetTime() < Right.GetTime();
	});

	AnimMontage->CompositeSections = MoveTemp(NewSections);
	return true;
}

static bool FinalizeAnimMontage(UAnimMontage* AnimMontage,
                                const TSharedPtr<FJsonObject>& Payload,
                                TArray<FString>& OutErrors)
{
	if (!AnimMontage)
	{
		OutErrors.Add(TEXT("AnimMontage is null."));
		return false;
	}

#if WITH_EDITORONLY_DATA
	if (AnimMontage->AnimNotifyTracks.Num() == 0)
	{
		AnimMontage->AnimNotifyTracks.Add(FAnimNotifyTrack(TEXT("1"), FLinearColor::White));
	}
#endif

	AnimMontage->CompositeSections.Sort([](const FCompositeSection& Left, const FCompositeSection& Right)
	{
		return Left.GetTime() < Right.GetTime();
	});
	UAnimMontageFactory::EnsureStartingSection(AnimMontage);
	RefreshMontageCompositeLength(AnimMontage, Payload);

	for (const FCompositeSection& Section : AnimMontage->CompositeSections)
	{
		if (!Section.NextSectionName.IsNone()
			&& AnimMontage->GetSectionIndex(Section.NextSectionName) == INDEX_NONE)
		{
			OutErrors.Add(FString::Printf(TEXT("Section '%s' references missing nextSectionName '%s'."),
				*Section.SectionName.ToString(),
				*Section.NextSectionName.ToString()));
		}
	}

	for (int32 NotifyIndex = 0; NotifyIndex < AnimMontage->Notifies.Num(); ++NotifyIndex)
	{
		const FAnimNotifyEvent& NotifyEvent = AnimMontage->Notifies[NotifyIndex];
		if (!IsValidMontageTime(AnimMontage, NotifyEvent.GetTriggerTime()))
		{
			OutErrors.Add(FString::Printf(TEXT("Notify %d trigger time is outside AnimMontage range."), NotifyIndex));
		}
		if (NotifyEvent.NotifyStateClass && !IsValidMontageTime(AnimMontage, NotifyEvent.GetEndTriggerTime()))
		{
			OutErrors.Add(FString::Printf(TEXT("Notify %d end time is outside AnimMontage range."), NotifyIndex));
		}
	}

	if (OutErrors.Num() > 0)
	{
		return false;
	}

	AnimMontage->UpdateLinkableElements();
	AnimMontage->RefreshCacheData();
	return true;
}

static bool ApplyCreatePayload(UAnimMontage* AnimMontage,
                               const TSharedPtr<FJsonObject>& Payload,
                               TArray<FString>& OutErrors)
{
	if (!AnimMontage)
	{
		OutErrors.Add(TEXT("AnimMontage is null."));
		return false;
	}

	double RateScale = 0.0;
	if (TryGetNumberField(Payload, TEXT("rateScale"), RateScale))
	{
		AnimMontage->RateScale = static_cast<float>(RateScale);
	}

	const TArray<TSharedPtr<FJsonValue>> Slots = GetArrayField(Payload, TEXT("slots"));
	if (Slots.Num() > 0 && !ReplaceSlots(AnimMontage, Slots, OutErrors))
	{
		return false;
	}

	RefreshMontageCompositeLength(AnimMontage, Payload);

	const TArray<TSharedPtr<FJsonValue>> Sections = GetArrayField(Payload, TEXT("sections"));
	if (Sections.Num() > 0 && !ReplaceSections(AnimMontage, Sections, OutErrors))
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>> Notifies = GetArrayField(Payload, TEXT("notifies"));
	if (Notifies.Num() > 0 && !ReplaceNotifies(AnimMontage, Notifies, OutErrors))
	{
		return false;
	}

	return FinalizeAnimMontage(AnimMontage, Payload, OutErrors);
}

static bool ApplyModifyOperation(UAnimMontage* AnimMontage,
                                 const FString& Operation,
                                 const TSharedPtr<FJsonObject>& Payload,
                                 TArray<FString>& OutErrors)
{
	if (Operation.Equals(TEXT("replace_notifies"), ESearchCase::IgnoreCase))
	{
		if (!ReplaceNotifies(AnimMontage, GetArrayField(Payload, TEXT("notifies")), OutErrors))
		{
			return false;
		}
		return FinalizeAnimMontage(AnimMontage, Payload, OutErrors);
	}

	if (Operation.Equals(TEXT("patch_notify"), ESearchCase::IgnoreCase))
	{
		if (!PatchNotify(AnimMontage, Payload, OutErrors))
		{
			return false;
		}
		return FinalizeAnimMontage(AnimMontage, Payload, OutErrors);
	}

	if (Operation.Equals(TEXT("replace_sections"), ESearchCase::IgnoreCase))
	{
		if (!ReplaceSections(AnimMontage, GetArrayField(Payload, TEXT("sections")), OutErrors))
		{
			return false;
		}
		return FinalizeAnimMontage(AnimMontage, Payload, OutErrors);
	}

	if (Operation.Equals(TEXT("replace_slots"), ESearchCase::IgnoreCase))
	{
		if (!ReplaceSlots(AnimMontage, GetArrayField(Payload, TEXT("slots")), OutErrors))
		{
			return false;
		}
		return FinalizeAnimMontage(AnimMontage, Payload, OutErrors);
	}

	OutErrors.Add(FString::Printf(TEXT("Unsupported AnimMontage operation '%s'."), *Operation));
	return false;
}

static UAnimMontage* CreateMontageAsset(UObject* Outer,
                                        const FName AssetName,
                                        USkeleton* Skeleton,
                                        UAnimSequence* SourceAnimation,
                                        USkeletalMesh* PreviewMesh)
{
	if (!Outer || (!Skeleton && !SourceAnimation))
	{
		return nullptr;
	}

	UAnimMontageFactory* Factory = NewObject<UAnimMontageFactory>();
	if (!Factory)
	{
		return nullptr;
	}

	Factory->TargetSkeleton = Skeleton;
	Factory->SourceAnimation = SourceAnimation;
	Factory->PreviewSkeletalMesh = PreviewMesh;

	return Cast<UAnimMontage>(Factory->FactoryCreateNew(
		UAnimMontage::StaticClass(),
		Outer,
		AssetName,
		Outer == GetTransientPackage() ? RF_Transient : RF_Public | RF_Standalone,
		nullptr,
		GWarn));
}

static void CleanupTransientMontage(UAnimMontage*& AnimMontage)
{
	if (!AnimMontage)
	{
		return;
	}

	AnimMontage->ClearFlags(RF_Public | RF_Standalone);
	AnimMontage->MarkAsGarbage();
	AnimMontage = nullptr;
}

static void CleanupFailedCreatedMontage(UAnimMontage*& AnimMontage)
{
	UObject* AssetPtr = AnimMontage;
	CleanupFailedCreateAsset(AssetPtr);
	AnimMontage = nullptr;
}

} // namespace AnimMontageAuthoringInternal

TSharedPtr<FJsonObject> FAnimMontageAuthoring::Create(const FString& AssetPath,
                                                      const TSharedPtr<FJsonObject>& PayloadJson,
                                                      const bool bValidateOnly)
{
	using namespace AnimMontageAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_anim_montage"), AssetPath, TEXT("AnimMontage"), bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	UAnimSequence* SourceAnimation = ResolveSourceAnimation(Payload, ValidationErrors);
	USkeleton* Skeleton = ResolveSkeleton(Payload, SourceAnimation, ValidationErrors);
	USkeletalMesh* PreviewMesh = ResolvePreviewMesh(Payload, ValidationErrors);

	UAnimMontage* PreviewMontage = nullptr;
	if (Skeleton || SourceAnimation)
	{
		PreviewMontage = CreateMontageAsset(
			GetTransientPackage(),
			MakeUniqueObjectName(GetTransientPackage(), UAnimMontage::StaticClass(), TEXT("PreviewAnimMontage")),
			Skeleton,
			SourceAnimation,
			PreviewMesh);
		if (!PreviewMontage)
		{
			ValidationErrors.Add(TEXT("Failed to create transient AnimMontage preview asset."));
		}
	}

	if (PreviewMontage)
	{
		ApplyCreatePayload(PreviewMontage, Payload, ValidationErrors);
		CleanupTransientMontage(PreviewMontage);
	}

	if (!AppendValidationSummary(Context, ValidationErrors, TEXT("AnimMontage payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create AnimMontage")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	UAnimMontage* AnimMontage = CreateMontageAsset(
		Package,
		FPackageName::GetShortFName(AssetPath),
		Skeleton,
		SourceAnimation,
		PreviewMesh);
	if (!AnimMontage)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create AnimMontage asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	AnimMontage->Modify();

	TArray<FString> ApplyErrors;
	if (!ApplyCreatePayload(AnimMontage, Payload, ApplyErrors))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, AssetPath);
		}
		CleanupFailedCreatedMontage(AnimMontage);
		return Context.BuildResult(false);
	}

	AnimMontage->PostEditChange();
	FAssetRegistryModule::AssetCreated(AnimMontage);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(AnimMontage);
	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FAnimMontageAuthoring::Modify(UAnimMontage* AnimMontage,
                                                      const FString& Operation,
                                                      const TSharedPtr<FJsonObject>& PayloadJson,
                                                      const bool bValidateOnly)
{
	using namespace AnimMontageAuthoringInternal;

	const FString AssetPath = AnimMontage ? AnimMontage->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_anim_montage"), AssetPath, TEXT("AnimMontage"), bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (!AnimMontage)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("AnimMontage is null."));
		return Context.BuildResult(false);
	}

	UAnimMontage* PreviewMontage = Cast<UAnimMontage>(StaticDuplicateObject(AnimMontage, GetTransientPackage()));
	TArray<FString> ValidationErrors;
	if (!PreviewMontage)
	{
		ValidationErrors.Add(TEXT("Failed to duplicate AnimMontage for validation preview."));
	}
	else
	{
		ApplyModifyOperation(PreviewMontage, Operation, Payload, ValidationErrors);
		CleanupTransientMontage(PreviewMontage);
	}

	if (!AppendValidationSummary(Context, ValidationErrors, TEXT("AnimMontage payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify AnimMontage")));
	AnimMontage->Modify();

	TArray<FString> ApplyErrors;
	if (!ApplyModifyOperation(AnimMontage, Operation, Payload, ApplyErrors))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, AssetPath);
		}
		return Context.BuildResult(false);
	}

	AnimMontage->PostEditChange();
	AnimMontage->MarkPackageDirty();
	Context.TrackDirtyObject(AnimMontage);
	return Context.BuildResult(true);
}
