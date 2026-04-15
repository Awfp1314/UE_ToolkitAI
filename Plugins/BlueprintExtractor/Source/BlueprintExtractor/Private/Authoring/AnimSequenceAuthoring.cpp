#include "Authoring/AnimSequenceAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"
#include "AnimationBlueprintLibrary.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "CoreGlobals.h"
#include "Animation/AnimCurveTypes.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "Animation/AnimNotifies/AnimNotifyState.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimTypes.h"
#include "Animation/Skeleton.h"
#include "Engine/SkeletalMesh.h"
#include "Factories/AnimSequenceFactory.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectGlobals.h"

namespace AnimSequenceAuthoringInternal
{

static TSharedPtr<FJsonObject> NormalizePayload(const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* SequenceObject = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("animSequence"), SequenceObject)
		&& SequenceObject
		&& SequenceObject->IsValid())
	{
		return *SequenceObject;
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

static bool IsValidSequenceTime(const UAnimSequence* AnimSequence, const float Time)
{
	if (!AnimSequence)
	{
		return false;
	}

	const float Length = AnimSequence->GetPlayLength();
	return Time >= 0.0f && Time <= Length + UE_KINDA_SMALL_NUMBER;
}

static USkeleton* ResolveSkeleton(const TSharedPtr<FJsonObject>& Payload, TArray<FString>& OutErrors)
{
	if (!Payload.IsValid())
	{
		OutErrors.Add(TEXT("AnimSequence payload is missing."));
		return nullptr;
	}

	FString SkeletonPath;
	if (!(Payload->TryGetStringField(TEXT("skeleton"), SkeletonPath)
		|| Payload->TryGetStringField(TEXT("skeletonPath"), SkeletonPath))
		|| SkeletonPath.IsEmpty())
	{
		OutErrors.Add(TEXT("AnimSequence creation requires a skeleton path."));
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

static int32 EnsureTrackIndex(UAnimSequence* AnimSequence,
                              const TSharedPtr<FJsonObject>& SourceObject)
{
	if (!AnimSequence)
	{
		return INDEX_NONE;
	}

#if WITH_EDITORONLY_DATA
	if (AnimSequence->AnimNotifyTracks.Num() == 0)
	{
		AnimSequence->AnimNotifyTracks.Add(FAnimNotifyTrack(TEXT("1"), FLinearColor::White));
	}

	FString TrackName;
	if (SourceObject.IsValid()
		&& SourceObject->TryGetStringField(TEXT("trackName"), TrackName)
		&& !TrackName.IsEmpty())
	{
		const FName DesiredTrackName(*TrackName);
		for (int32 Index = 0; Index < AnimSequence->AnimNotifyTracks.Num(); ++Index)
		{
			if (AnimSequence->AnimNotifyTracks[Index].TrackName == DesiredTrackName)
			{
				return Index;
			}
		}

		return AnimSequence->AnimNotifyTracks.Add(FAnimNotifyTrack(DesiredTrackName, FLinearColor::White));
	}

	double TrackIndexValue = 0.0;
	if (SourceObject.IsValid() && SourceObject->TryGetNumberField(TEXT("trackIndex"), TrackIndexValue))
	{
		const int32 DesiredIndex = FMath::Max(0, static_cast<int32>(TrackIndexValue));
		while (AnimSequence->AnimNotifyTracks.Num() <= DesiredIndex)
		{
			AnimSequence->AnimNotifyTracks.Add(FAnimNotifyTrack(
				*FString::FromInt(AnimSequence->AnimNotifyTracks.Num() + 1),
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
}

static bool BuildNotifyEvent(UAnimSequence* AnimSequence,
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

	if (!IsValidSequenceTime(AnimSequence, static_cast<float>(TriggerTime)))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.triggerTime: time %g is outside AnimSequence range."),
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
	OutEvent.Link(AnimSequence, static_cast<float>(TriggerTime));
	OutEvent.TriggerTimeOffset = GetTriggerTimeOffsetForType(
		AnimSequence->CalculateOffsetForNotify(static_cast<float>(TriggerTime)));
	OutEvent.TrackIndex = EnsureTrackIndex(AnimSequence, NotifyObject);

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
				AnimSequence,
				NotifyClass,
				NAME_None,
				RF_Transactional);
			OutEvent.Notify = nullptr;
		}
		else
		{
			OutEvent.Notify = NewObject<UAnimNotify>(
				AnimSequence,
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

		if (!IsValidSequenceTime(AnimSequence, static_cast<float>(TriggerTime + Duration)))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.endTriggerTime: state notify exceeds AnimSequence range."),
				*NotifyPath));
			return false;
		}

		OutEvent.SetDuration(static_cast<float>(Duration));
		OutEvent.EndLink.Link(AnimSequence, OutEvent.EndLink.GetTime());
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

static FAnimNotifyEvent* FindNotifyBySelector(UAnimSequence* AnimSequence,
                                              const FNotifySelector& Selector,
                                              int32& OutNotifyIndex)
{
	if (!AnimSequence)
	{
		return nullptr;
	}

	if (Selector.NotifyIndex != INDEX_NONE && AnimSequence->Notifies.IsValidIndex(Selector.NotifyIndex))
	{
		OutNotifyIndex = Selector.NotifyIndex;
		return &AnimSequence->Notifies[Selector.NotifyIndex];
	}

	for (int32 Index = 0; Index < AnimSequence->Notifies.Num(); ++Index)
	{
		FAnimNotifyEvent& NotifyEvent = AnimSequence->Notifies[Index];
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

static bool PatchNotify(UAnimSequence* AnimSequence,
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
	FAnimNotifyEvent* NotifyEvent = FindNotifyBySelector(AnimSequence, Selector, NotifyIndex);
	if (!NotifyEvent)
	{
		OutErrors.Add(TEXT("Failed to find AnimSequence notify for patch selector."));
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
						AnimSequence,
						NotifyClass,
						NAME_None,
						RF_Transactional);
					NotifyEvent->Notify = nullptr;
				}
				else
				{
					NotifyEvent->Notify = NewObject<UAnimNotify>(
						AnimSequence,
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
		if (!IsValidSequenceTime(AnimSequence, static_cast<float>(TriggerTime)))
		{
			OutErrors.Add(FString::Printf(TEXT("notify.triggerTime: time %g is outside AnimSequence range."),
				TriggerTime));
			return false;
		}

		NotifyEvent->Link(AnimSequence, static_cast<float>(TriggerTime));
		NotifyEvent->TriggerTimeOffset = GetTriggerTimeOffsetForType(
			AnimSequence->CalculateOffsetForNotify(static_cast<float>(TriggerTime)));
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
			|| !IsValidSequenceTime(AnimSequence, NotifyEvent->GetTriggerTime() + static_cast<float>(Duration)))
		{
			OutErrors.Add(TEXT("notify.duration: state notify duration is invalid for this AnimSequence."));
			return false;
		}

		NotifyEvent->SetDuration(static_cast<float>(Duration));
		NotifyEvent->EndLink.Link(AnimSequence, NotifyEvent->EndLink.GetTime());
	}

	if (PatchObject->HasField(TEXT("trackName")) || PatchObject->HasField(TEXT("trackIndex")))
	{
		NotifyEvent->TrackIndex = EnsureTrackIndex(AnimSequence, PatchObject);
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

static bool ReplaceNotifies(UAnimSequence* AnimSequence,
                            const TArray<TSharedPtr<FJsonValue>>& Notifies,
                            TArray<FString>& OutErrors)
{
	TArray<FAnimNotifyEvent> NewNotifies;
	NewNotifies.Reserve(Notifies.Num());

	for (int32 Index = 0; Index < Notifies.Num(); ++Index)
	{
		FAnimNotifyEvent& NotifyEvent = NewNotifies.AddDefaulted_GetRef();
		const TSharedPtr<FJsonObject> NotifyObject = Notifies[Index].IsValid() ? Notifies[Index]->AsObject() : nullptr;
		if (!BuildNotifyEvent(AnimSequence, NotifyObject, Index, NotifyEvent, OutErrors))
		{
			return false;
		}
	}

	AnimSequence->Notifies = MoveTemp(NewNotifies);
	return true;
}

static bool ReplaceSyncMarkers(UAnimSequence* AnimSequence,
                               const TArray<TSharedPtr<FJsonValue>>& SyncMarkers,
                               TArray<FString>& OutErrors)
{
	TArray<FAnimSyncMarker> NewMarkers;
	NewMarkers.Reserve(SyncMarkers.Num());

	for (int32 Index = 0; Index < SyncMarkers.Num(); ++Index)
	{
		const FString MarkerPath = FString::Printf(TEXT("syncMarkers[%d]"), Index);
		const TSharedPtr<FJsonObject> MarkerObject = SyncMarkers[Index].IsValid() ? SyncMarkers[Index]->AsObject() : nullptr;
		if (!MarkerObject.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s: expected sync marker object."), *MarkerPath));
			return false;
		}

		FString MarkerName;
		if (!(MarkerObject->TryGetStringField(TEXT("markerName"), MarkerName)
			|| MarkerObject->TryGetStringField(TEXT("name"), MarkerName))
			|| MarkerName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.markerName: missing marker name."), *MarkerPath));
			return false;
		}

		double Time = 0.0;
		if (!(TryGetNumberField(MarkerObject, TEXT("time"), Time)
			|| TryGetNumberField(MarkerObject, TEXT("triggerTime"), Time)))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.time: missing marker time."), *MarkerPath));
			return false;
		}

		if (!IsValidSequenceTime(AnimSequence, static_cast<float>(Time)))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.time: marker time %g is outside AnimSequence range."),
				*MarkerPath,
				Time));
			return false;
		}

		FAnimSyncMarker& Marker = NewMarkers.AddDefaulted_GetRef();
		Marker.MarkerName = FName(*MarkerName);
		Marker.Time = static_cast<float>(Time);
		Marker.TrackIndex = EnsureTrackIndex(AnimSequence, MarkerObject);

#if WITH_EDITORONLY_DATA
		FString MarkerGuid;
		if ((MarkerObject->TryGetStringField(TEXT("markerGuid"), MarkerGuid)
		     || MarkerObject->TryGetStringField(TEXT("guid"), MarkerGuid))
		    && !MarkerGuid.IsEmpty())
		{
			FGuid ParsedGuid;
			if (FGuid::Parse(MarkerGuid, ParsedGuid))
			{
				Marker.Guid = ParsedGuid;
			}
		}
		if (!Marker.Guid.IsValid())
		{
			Marker.Guid = FGuid::NewGuid();
		}
#endif
	}

	NewMarkers.Sort();
	AnimSequence->AuthoredSyncMarkers = MoveTemp(NewMarkers);
	return true;
}

static bool ReplaceCurves(UAnimSequence* AnimSequence,
                          const TArray<TSharedPtr<FJsonValue>>& Curves,
                          TArray<FString>& OutErrors)
{
	UAnimationBlueprintLibrary::RemoveAllCurveData(AnimSequence);

	for (int32 CurveIndex = 0; CurveIndex < Curves.Num(); ++CurveIndex)
	{
		const FString CurvePath = FString::Printf(TEXT("curves[%d]"), CurveIndex);
		const TSharedPtr<FJsonObject> CurveObject = Curves[CurveIndex].IsValid() ? Curves[CurveIndex]->AsObject() : nullptr;
		if (!CurveObject.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s: expected curve object."), *CurvePath));
			return false;
		}

		FString CurveName;
		if (!(CurveObject->TryGetStringField(TEXT("curveName"), CurveName)
			|| CurveObject->TryGetStringField(TEXT("name"), CurveName))
			|| CurveName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.curveName: missing curve name."), *CurvePath));
			return false;
		}

		double CurveFlagsValue = static_cast<double>(AACF_DefaultCurve);
		CurveObject->TryGetNumberField(TEXT("curveTypeFlags"), CurveFlagsValue);
		const bool bMetaDataCurve = (static_cast<int32>(CurveFlagsValue) & AACF_Metadata) != 0;
		UAnimationBlueprintLibrary::AddCurve(
			AnimSequence,
			FName(*CurveName),
			ERawCurveTrackTypes::RCT_Float,
			bMetaDataCurve);

		const TArray<TSharedPtr<FJsonValue>>* Keys = nullptr;
		if (!CurveObject->TryGetArrayField(TEXT("keys"), Keys) || !Keys || Keys->Num() == 0)
		{
			continue;
		}

		TArray<float> Times;
		TArray<float> Values;
		Times.Reserve(Keys->Num());
		Values.Reserve(Keys->Num());

		for (int32 KeyIndex = 0; KeyIndex < Keys->Num(); ++KeyIndex)
		{
			const TSharedPtr<FJsonObject> KeyObject = (*Keys)[KeyIndex].IsValid() ? (*Keys)[KeyIndex]->AsObject() : nullptr;
			if (!KeyObject.IsValid())
			{
				OutErrors.Add(FString::Printf(TEXT("%s.keys[%d]: expected key object."), *CurvePath, KeyIndex));
				return false;
			}

			double Time = 0.0;
			double Value = 0.0;
			if (!KeyObject->TryGetNumberField(TEXT("time"), Time)
				|| !KeyObject->TryGetNumberField(TEXT("value"), Value))
			{
				OutErrors.Add(FString::Printf(TEXT("%s.keys[%d]: keys require numeric time and value."),
					*CurvePath,
					KeyIndex));
				return false;
			}

			if (!IsValidSequenceTime(AnimSequence, static_cast<float>(Time)))
			{
				OutErrors.Add(FString::Printf(TEXT("%s.keys[%d].time: key time %g is outside AnimSequence range."),
					*CurvePath,
					KeyIndex,
					Time));
				return false;
			}

			Times.Add(static_cast<float>(Time));
			Values.Add(static_cast<float>(Value));
		}

		UAnimationBlueprintLibrary::AddFloatCurveKeys(AnimSequence, FName(*CurveName), Times, Values);
	}

	return true;
}

static bool FinalizeAnimSequence(UAnimSequence* AnimSequence)
{
	if (!AnimSequence)
	{
		return false;
	}

#if WITH_EDITORONLY_DATA
	if (AnimSequence->AnimNotifyTracks.Num() == 0)
	{
		AnimSequence->AnimNotifyTracks.Add(FAnimNotifyTrack(TEXT("1"), FLinearColor::White));
	}
#endif

	AnimSequence->RefreshSyncMarkerDataFromAuthored();
	AnimSequence->RefreshCacheData();
	return true;
}

static bool ApplyCreatePayload(UAnimSequence* AnimSequence,
                               const TSharedPtr<FJsonObject>& Payload,
                               TArray<FString>& OutErrors)
{
	if (!AnimSequence)
	{
		OutErrors.Add(TEXT("AnimSequence is null."));
		return false;
	}

	double RateScale = 0.0;
	if (TryGetNumberField(Payload, TEXT("rateScale"), RateScale))
	{
		AnimSequence->RateScale = static_cast<float>(RateScale);
	}

	const TArray<TSharedPtr<FJsonValue>> Notifies = GetArrayField(Payload, TEXT("notifies"));
	if (Notifies.Num() > 0 && !ReplaceNotifies(AnimSequence, Notifies, OutErrors))
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>> SyncMarkers = GetArrayField(Payload, TEXT("syncMarkers"));
	if (SyncMarkers.Num() > 0 && !ReplaceSyncMarkers(AnimSequence, SyncMarkers, OutErrors))
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>> Curves = GetArrayField(Payload, TEXT("curves"));
	if (Curves.Num() > 0 && !ReplaceCurves(AnimSequence, Curves, OutErrors))
	{
		return false;
	}

	return FinalizeAnimSequence(AnimSequence);
}

static bool ApplyModifyOperation(UAnimSequence* AnimSequence,
                                 const FString& Operation,
                                 const TSharedPtr<FJsonObject>& Payload,
                                 TArray<FString>& OutErrors)
{
	if (!AnimSequence)
	{
		OutErrors.Add(TEXT("AnimSequence is null."));
		return false;
	}

	if (Operation.Equals(TEXT("replace_notifies"), ESearchCase::IgnoreCase))
	{
		if (!ReplaceNotifies(AnimSequence, GetArrayField(Payload, TEXT("notifies")), OutErrors))
		{
			return false;
		}
		return FinalizeAnimSequence(AnimSequence);
	}

	if (Operation.Equals(TEXT("patch_notify"), ESearchCase::IgnoreCase))
	{
		if (!PatchNotify(AnimSequence, Payload, OutErrors))
		{
			return false;
		}
		return FinalizeAnimSequence(AnimSequence);
	}

	if (Operation.Equals(TEXT("replace_sync_markers"), ESearchCase::IgnoreCase))
	{
		if (!ReplaceSyncMarkers(AnimSequence, GetArrayField(Payload, TEXT("syncMarkers")), OutErrors))
		{
			return false;
		}
		return FinalizeAnimSequence(AnimSequence);
	}

	if (Operation.Equals(TEXT("replace_curve_metadata"), ESearchCase::IgnoreCase))
	{
		if (!ReplaceCurves(AnimSequence, GetArrayField(Payload, TEXT("curves")), OutErrors))
		{
			return false;
		}
		return FinalizeAnimSequence(AnimSequence);
	}

	OutErrors.Add(FString::Printf(TEXT("Unsupported AnimSequence operation '%s'."), *Operation));
	return false;
}

static UAnimSequence* CreateSequenceAsset(UObject* Outer,
                                          const FName AssetName,
                                          USkeleton* Skeleton,
                                          USkeletalMesh* PreviewMesh)
{
	if (!Outer || !Skeleton)
	{
		return nullptr;
	}

	UAnimSequenceFactory* Factory = NewObject<UAnimSequenceFactory>();
	if (!Factory)
	{
		return nullptr;
	}

	Factory->TargetSkeleton = Skeleton;
	Factory->PreviewSkeletalMesh = PreviewMesh;

	return Cast<UAnimSequence>(Factory->FactoryCreateNew(
		UAnimSequence::StaticClass(),
		Outer,
		AssetName,
		Outer == GetTransientPackage() ? RF_Transient : RF_Public | RF_Standalone,
		nullptr,
		GWarn));
}

static void ClearTransientImportData(UAnimSequence* AnimSequence)
{
	if (!AnimSequence || AnimSequence->GetOutermost() != GetTransientPackage())
	{
		return;
	}

	if (FObjectPropertyBase* ImportDataProperty = FindFProperty<FObjectPropertyBase>(AnimSequence->GetClass(), TEXT("AssetImportData")))
	{
		if (UObject* ImportData = ImportDataProperty->GetObjectPropertyValue_InContainer(AnimSequence))
		{
			ImportData->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors);
		}

		ImportDataProperty->SetObjectPropertyValue_InContainer(AnimSequence, nullptr);
	}
}

} // namespace AnimSequenceAuthoringInternal

TSharedPtr<FJsonObject> FAnimSequenceAuthoring::Create(const FString& AssetPath,
                                                       const TSharedPtr<FJsonObject>& PayloadJson,
                                                       const bool bValidateOnly)
{
	using namespace AnimSequenceAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_anim_sequence"), AssetPath, TEXT("AnimSequence"), bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	USkeleton* Skeleton = ResolveSkeleton(Payload, ValidationErrors);
	USkeletalMesh* PreviewMesh = ResolvePreviewMesh(Payload, ValidationErrors);

	UAnimSequence* PreviewSequence = nullptr;
	if (Skeleton)
	{
		PreviewSequence = CreateSequenceAsset(
			GetTransientPackage(),
			MakeUniqueObjectName(GetTransientPackage(), UAnimSequence::StaticClass(), TEXT("PreviewAnimSequence")),
			Skeleton,
			PreviewMesh);
		if (!PreviewSequence)
		{
			ValidationErrors.Add(TEXT("Failed to create transient AnimSequence preview asset."));
		}
	}

	if (PreviewSequence)
	{
		ApplyCreatePayload(PreviewSequence, Payload, ValidationErrors);
	}

	if (!AppendValidationSummary(Context, ValidationErrors, TEXT("AnimSequence payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create AnimSequence")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	UAnimSequence* AnimSequence = CreateSequenceAsset(
		Package,
		FPackageName::GetShortFName(AssetPath),
		Skeleton,
		PreviewMesh);
	if (!AnimSequence)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create AnimSequence asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	AnimSequence->Modify();

	TArray<FString> ApplyErrors;
	if (!ApplyCreatePayload(AnimSequence, Payload, ApplyErrors))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, AssetPath);
		}
		UObject* AssetPtr = AnimSequence;
		CleanupFailedCreateAsset(AssetPtr);
		return Context.BuildResult(false);
	}

	AnimSequence->PostEditChange();
	FAssetRegistryModule::AssetCreated(AnimSequence);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(AnimSequence);
	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FAnimSequenceAuthoring::Modify(UAnimSequence* AnimSequence,
                                                       const FString& Operation,
                                                       const TSharedPtr<FJsonObject>& PayloadJson,
                                                       const bool bValidateOnly)
{
	using namespace AnimSequenceAuthoringInternal;

	const FString AssetPath = AnimSequence ? AnimSequence->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_anim_sequence"), AssetPath, TEXT("AnimSequence"), bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (!AnimSequence)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("AnimSequence is null."));
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	const bool bSkipPreviewValidation = Operation.Equals(TEXT("replace_notifies"), ESearchCase::IgnoreCase)
		&& GetArrayField(Payload, TEXT("notifies")).Num() == 0;
	if (bSkipPreviewValidation)
	{
		Context.SetValidationSummary(true, TEXT("AnimSequence payload validated."));
	}
	else
	{
		UAnimSequence* PreviewSequence = Cast<UAnimSequence>(StaticDuplicateObject(AnimSequence, GetTransientPackage()));
		if (!PreviewSequence)
		{
			ValidationErrors.Add(TEXT("Failed to duplicate AnimSequence for validation preview."));
		}
		else
		{
			ClearTransientImportData(PreviewSequence);
			ApplyModifyOperation(PreviewSequence, Operation, Payload, ValidationErrors);
		}

		if (!AppendValidationSummary(Context, ValidationErrors, TEXT("AnimSequence payload validated.")))
		{
			return Context.BuildResult(false);
		}
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify AnimSequence")));
	AnimSequence->Modify();

	TArray<FString> ApplyErrors;
	if (!ApplyModifyOperation(AnimSequence, Operation, Payload, ApplyErrors))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, AssetPath);
		}
		return Context.BuildResult(false);
	}

	AnimSequence->PostEditChange();
	AnimSequence->MarkPackageDirty();
	Context.TrackDirtyObject(AnimSequence);
	return Context.BuildResult(true);
}
