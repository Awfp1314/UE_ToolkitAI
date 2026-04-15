#include "Extractors/AnimAssetExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "PropertySerializer.h"
#include "Animation/AnimCompositeBase.h"
#include "Animation/AnimCurveTypes.h"
#include "Animation/AnimEnums.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "Animation/AnimNotifies/AnimNotifyState.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/BlendSpace.h"
#include "Animation/BlendSpace1D.h"
#include "Animation/Skeleton.h"
#include "Misc/EngineVersionComparison.h"

namespace AnimAssetExtractorInternal
{

static FString AdditiveAnimationTypeToString(const EAdditiveAnimationType AdditiveAnimationType)
{
	if (const UEnum* Enum = StaticEnum<EAdditiveAnimationType>())
	{
		return Enum->GetNameStringByValue(AdditiveAnimationType);
	}

	return TEXT("None");
}

static FString AdditiveBasePoseTypeToString(const EAdditiveBasePoseType AdditiveBasePoseType)
{
	if (const UEnum* Enum = StaticEnum<EAdditiveBasePoseType>())
	{
		return Enum->GetNameStringByValue(AdditiveBasePoseType);
	}

	return TEXT("None");
}

static FString NotifyEventTypeToString(const EAnimNotifyEventType::Type NotifyEventType)
{
	switch (NotifyEventType)
	{
	case EAnimNotifyEventType::Begin:
		return TEXT("Begin");
	case EAnimNotifyEventType::End:
		return TEXT("End");
	default:
		return TEXT("Queued");
	}
}

static FString MontageTickTypeToString(const EMontageNotifyTickType::Type TickType)
{
	switch (TickType)
	{
	case EMontageNotifyTickType::BranchingPoint:
		return TEXT("BranchingPoint");
	default:
		return TEXT("Queued");
	}
}

static FString NotifyFilterTypeToString(const ENotifyFilterType::Type FilterType)
{
	switch (FilterType)
	{
	case ENotifyFilterType::NoFiltering:
		return TEXT("NoFiltering");
	case ENotifyFilterType::LOD:
		return TEXT("LOD");
	default:
		return TEXT("NoFiltering");
	}
}

static FString CurveInterpModeToString(const ERichCurveInterpMode InterpMode)
{
	switch (InterpMode)
	{
	case RCIM_Linear:
		return TEXT("Linear");
	case RCIM_Constant:
		return TEXT("Constant");
	case RCIM_Cubic:
		return TEXT("Cubic");
	default:
		return TEXT("None");
	}
}

static TSharedPtr<FJsonObject> SerializeRichCurveKey(const FRichCurveKey& Key)
{
	TSharedPtr<FJsonObject> KeyObject = MakeShared<FJsonObject>();
	KeyObject->SetNumberField(TEXT("time"), Key.Time);
	KeyObject->SetNumberField(TEXT("value"), Key.Value);
	KeyObject->SetNumberField(TEXT("arriveTangent"), Key.ArriveTangent);
	KeyObject->SetNumberField(TEXT("leaveTangent"), Key.LeaveTangent);
	KeyObject->SetStringField(TEXT("interpMode"), CurveInterpModeToString(Key.InterpMode));
	return KeyObject;
}

static TSharedPtr<FJsonObject> SerializeSamplingRate(const FFrameRate& SamplingRate)
{
	TSharedPtr<FJsonObject> SamplingRateObject = MakeShared<FJsonObject>();
	SamplingRateObject->SetNumberField(TEXT("numerator"), SamplingRate.Numerator);
	SamplingRateObject->SetNumberField(TEXT("denominator"), SamplingRate.Denominator);
	SamplingRateObject->SetNumberField(TEXT("asDecimal"), SamplingRate.AsDecimal());
	return SamplingRateObject;
}

static void SetAnimationAssetFields(const UAnimationAsset* AnimationAsset, const TSharedPtr<FJsonObject>& AssetObject)
{
	if (!AnimationAsset || !AssetObject.IsValid())
	{
		return;
	}

	AssetObject->SetStringField(TEXT("assetPath"), AnimationAsset->GetPathName());
	AssetObject->SetStringField(TEXT("assetName"), AnimationAsset->GetName());

	if (const USkeleton* Skeleton = AnimationAsset->GetSkeleton())
	{
		AssetObject->SetStringField(TEXT("skeleton"), Skeleton->GetPathName());
	}
}

static TSharedPtr<FJsonObject> SerializeVector(const FVector& VectorValue)
{
	TSharedPtr<FJsonObject> VectorObject = MakeShared<FJsonObject>();
	VectorObject->SetNumberField(TEXT("x"), VectorValue.X);
	VectorObject->SetNumberField(TEXT("y"), VectorValue.Y);
	VectorObject->SetNumberField(TEXT("z"), VectorValue.Z);
	return VectorObject;
}

static TSharedPtr<FJsonObject> SerializeBlendParameter(const FBlendParameter& BlendParameter)
{
	TSharedPtr<FJsonObject> ParameterObject = MakeShared<FJsonObject>();
	ParameterObject->SetStringField(TEXT("name"), BlendParameter.DisplayName);
	ParameterObject->SetNumberField(TEXT("min"), BlendParameter.Min);
	ParameterObject->SetNumberField(TEXT("max"), BlendParameter.Max);
	ParameterObject->SetNumberField(TEXT("gridDivisions"), BlendParameter.GridNum);
	ParameterObject->SetBoolField(TEXT("snapToGrid"), BlendParameter.bSnapToGrid);
	ParameterObject->SetBoolField(TEXT("wrapInput"), BlendParameter.bWrapInput);
	return ParameterObject;
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

static FString GetTrackName(const UAnimSequenceBase* AnimBase, const int32 TrackIndex)
{
#if WITH_EDITORONLY_DATA
	if (AnimBase && AnimBase->AnimNotifyTracks.IsValidIndex(TrackIndex))
	{
		return AnimBase->AnimNotifyTracks[TrackIndex].TrackName.ToString();
	}
#endif
	return FString();
}

static FString GetMarkerGuidString(const FAnimSyncMarker& SyncMarker)
{
#if WITH_EDITORONLY_DATA
	return SyncMarker.Guid.IsValid()
		? SyncMarker.Guid.ToString(EGuidFormats::DigitsWithHyphens)
		: FString();
#else
	return FString();
#endif
}

} // namespace AnimAssetExtractorInternal

TSharedPtr<FJsonObject> FAnimAssetExtractor::ExtractAnimSequence(const UAnimSequence* AnimSequence)
{
	if (!AnimSequence)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> SequenceObject = MakeShared<FJsonObject>();
	AnimAssetExtractorInternal::SetAnimationAssetFields(AnimSequence, SequenceObject);
	SequenceObject->SetNumberField(TEXT("sequenceLength"), AnimSequence->GetPlayLength());
	SequenceObject->SetNumberField(TEXT("rateScale"), AnimSequence->RateScale);
	SequenceObject->SetNumberField(TEXT("numFrames"), AnimSequence->GetNumberOfSampledKeys());
	SequenceObject->SetObjectField(TEXT("samplingFrameRate"), AnimAssetExtractorInternal::SerializeSamplingRate(AnimSequence->GetSamplingFrameRate()));
	SequenceObject->SetBoolField(TEXT("isAdditive"), AnimSequence->IsValidAdditive());
	SequenceObject->SetStringField(TEXT("additiveAnimType"), AnimAssetExtractorInternal::AdditiveAnimationTypeToString(AnimSequence->GetAdditiveAnimType()));
	SequenceObject->SetStringField(TEXT("refPoseType"), AnimAssetExtractorInternal::AdditiveBasePoseTypeToString(AnimSequence->RefPoseType));
	SequenceObject->SetArrayField(TEXT("notifies"), ExtractNotifies(AnimSequence));
	SequenceObject->SetArrayField(TEXT("curves"), ExtractCurves(AnimSequence));

	TArray<TSharedPtr<FJsonValue>> SyncMarkers;
	for (int32 MarkerIndex = 0; MarkerIndex < AnimSequence->AuthoredSyncMarkers.Num(); ++MarkerIndex)
	{
		const FAnimSyncMarker& SyncMarker = AnimSequence->AuthoredSyncMarkers[MarkerIndex];
		TSharedPtr<FJsonObject> MarkerObject = MakeShared<FJsonObject>();
		MarkerObject->SetStringField(TEXT("markerName"), SyncMarker.MarkerName.ToString());
		MarkerObject->SetNumberField(TEXT("time"), SyncMarker.Time);
		MarkerObject->SetNumberField(TEXT("markerIndex"), MarkerIndex);
		MarkerObject->SetNumberField(TEXT("trackIndex"), SyncMarker.TrackIndex);
		MarkerObject->SetStringField(TEXT("trackName"), AnimAssetExtractorInternal::GetTrackName(AnimSequence, SyncMarker.TrackIndex));
		const FString MarkerGuid = AnimAssetExtractorInternal::GetMarkerGuidString(SyncMarker);
		if (!MarkerGuid.IsEmpty())
		{
			MarkerObject->SetStringField(TEXT("markerGuid"), MarkerGuid);
		}
		SyncMarkers.Add(MakeShared<FJsonValueObject>(MarkerObject));
	}
	SequenceObject->SetArrayField(TEXT("syncMarkers"), SyncMarkers);

	Root->SetObjectField(TEXT("animSequence"), SequenceObject);
	return Root;
}

TSharedPtr<FJsonObject> FAnimAssetExtractor::ExtractAnimMontage(const UAnimMontage* AnimMontage)
{
	if (!AnimMontage)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> MontageObject = MakeShared<FJsonObject>();
	AnimAssetExtractorInternal::SetAnimationAssetFields(AnimMontage, MontageObject);
	MontageObject->SetNumberField(TEXT("sequenceLength"), AnimMontage->GetPlayLength());
	MontageObject->SetNumberField(TEXT("rateScale"), AnimMontage->RateScale);
	MontageObject->SetArrayField(TEXT("notifies"), ExtractNotifies(AnimMontage));

	TArray<TSharedPtr<FJsonValue>> Slots;
	for (const FSlotAnimationTrack& SlotTrack : AnimMontage->SlotAnimTracks)
	{
		TSharedPtr<FJsonObject> SlotObject = MakeShared<FJsonObject>();
		SlotObject->SetStringField(TEXT("slotName"), SlotTrack.SlotName.ToString());

		TArray<TSharedPtr<FJsonValue>> Segments;
		for (const FAnimSegment& Segment : SlotTrack.AnimTrack.AnimSegments)
		{
			TSharedPtr<FJsonObject> SegmentObject = MakeShared<FJsonObject>();
			const UAnimSequenceBase* AnimReference = Segment.GetAnimReference().Get();
			if (AnimReference)
			{
				SegmentObject->SetStringField(TEXT("animSequence"), AnimReference->GetPathName());
			}
			SegmentObject->SetNumberField(TEXT("startTime"), Segment.StartPos);
			SegmentObject->SetNumberField(TEXT("endTime"), Segment.StartPos + Segment.GetLength());
			SegmentObject->SetNumberField(TEXT("animStartTime"), Segment.AnimStartTime);
			SegmentObject->SetNumberField(TEXT("animEndTime"), Segment.AnimEndTime);
			SegmentObject->SetNumberField(TEXT("animPlayRate"), Segment.AnimPlayRate);
			SegmentObject->SetNumberField(TEXT("loopingCount"), Segment.LoopingCount);
			SegmentObject->SetNumberField(TEXT("segmentLength"), Segment.GetLength());
			Segments.Add(MakeShared<FJsonValueObject>(SegmentObject));
		}

		SlotObject->SetArrayField(TEXT("segments"), Segments);
		Slots.Add(MakeShared<FJsonValueObject>(SlotObject));
	}
	MontageObject->SetArrayField(TEXT("slots"), Slots);

	TArray<TSharedPtr<FJsonValue>> Sections;
	for (int32 SectionIndex = 0; SectionIndex < AnimMontage->GetNumSections(); ++SectionIndex)
	{
		float StartTime = 0.0f;
		float EndTime = 0.0f;
		AnimMontage->GetSectionStartAndEndTime(SectionIndex, StartTime, EndTime);

		const FCompositeSection& Section = AnimMontage->CompositeSections[SectionIndex];

		TSharedPtr<FJsonObject> SectionObject = MakeShared<FJsonObject>();
		SectionObject->SetStringField(TEXT("sectionName"), Section.SectionName.ToString());
		SectionObject->SetNumberField(TEXT("startTime"), StartTime);
		SectionObject->SetNumberField(TEXT("endTime"), EndTime);
		SectionObject->SetStringField(TEXT("nextSectionName"), Section.NextSectionName.IsNone() ? TEXT("") : Section.NextSectionName.ToString());
		Sections.Add(MakeShared<FJsonValueObject>(SectionObject));
	}
	MontageObject->SetArrayField(TEXT("sections"), Sections);

	TArray<TSharedPtr<FJsonValue>> BranchingPoints;
	for (const FAnimNotifyEvent& NotifyEvent : AnimMontage->Notifies)
	{
		if (!NotifyEvent.IsBranchingPoint())
		{
			continue;
		}

		TSharedPtr<FJsonObject> BranchingPointObject = MakeShared<FJsonObject>();
		const FString NotifyName = !NotifyEvent.NotifyName.IsNone()
			? NotifyEvent.NotifyName.ToString()
			: NotifyEvent.GetNotifyEventName().ToString();
		BranchingPointObject->SetStringField(TEXT("notifyName"), NotifyName);
		BranchingPointObject->SetNumberField(TEXT("triggerTime"), NotifyEvent.GetTriggerTime());
		BranchingPointObject->SetNumberField(TEXT("endTriggerTime"), NotifyEvent.GetEndTriggerTime());
		BranchingPointObject->SetNumberField(TEXT("duration"), NotifyEvent.GetDuration());
		BranchingPointObject->SetStringField(TEXT("montageTickType"), NotifyEvent.MontageTickType == EMontageNotifyTickType::BranchingPoint ? TEXT("BranchingPoint") : TEXT("Queued"));
		BranchingPointObject->SetBoolField(TEXT("convertedFromBranchingPoint"), NotifyEvent.bConvertedFromBranchingPoint);
		BranchingPointObject->SetNumberField(TEXT("trackIndex"), NotifyEvent.TrackIndex);

		BranchingPoints.Add(MakeShared<FJsonValueObject>(BranchingPointObject));
	}
	MontageObject->SetArrayField(TEXT("branchingPoints"), BranchingPoints);

	Root->SetObjectField(TEXT("animMontage"), MontageObject);
	return Root;
}

TSharedPtr<FJsonObject> FAnimAssetExtractor::ExtractBlendSpace(const UBlendSpace* BlendSpace)
{
	if (!BlendSpace)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> BlendSpaceObject = MakeShared<FJsonObject>();
	AnimAssetExtractorInternal::SetAnimationAssetFields(BlendSpace, BlendSpaceObject);
	BlendSpaceObject->SetBoolField(TEXT("is1D"), BlendSpace->IsA<UBlendSpace1D>());
	BlendSpaceObject->SetObjectField(TEXT("axisX"), AnimAssetExtractorInternal::SerializeBlendParameter(BlendSpace->GetBlendParameter(0)));
	if (!BlendSpace->IsA<UBlendSpace1D>())
	{
		BlendSpaceObject->SetObjectField(TEXT("axisY"), AnimAssetExtractorInternal::SerializeBlendParameter(BlendSpace->GetBlendParameter(1)));
	}

	TArray<TSharedPtr<FJsonValue>> Samples;
	for (int32 SampleIndex = 0; SampleIndex < BlendSpace->GetNumberOfBlendSamples(); ++SampleIndex)
	{
		const FBlendSample& Sample = BlendSpace->GetBlendSample(SampleIndex);

		TSharedPtr<FJsonObject> SampleObject = MakeShared<FJsonObject>();
		SampleObject->SetNumberField(TEXT("sampleIndex"), SampleIndex);
		if (Sample.Animation)
		{
			SampleObject->SetStringField(TEXT("animation"), Sample.Animation->GetPathName());
		}
		SampleObject->SetObjectField(TEXT("sampleValue"), AnimAssetExtractorInternal::SerializeVector(Sample.SampleValue));
		SampleObject->SetNumberField(TEXT("rateScale"), Sample.RateScale);
#if UE_VERSION_NEWER_THAN_OR_EQUAL(5, 7, 0)
		SampleObject->SetBoolField(TEXT("useSingleFrameForBlending"), Sample.bUseSingleFrameForBlending);
		if (Sample.bUseSingleFrameForBlending)
		{
			SampleObject->SetNumberField(TEXT("frameIndexToSample"), Sample.FrameIndexToSample);
		}
#endif
		Samples.Add(MakeShared<FJsonValueObject>(SampleObject));
	}

	BlendSpaceObject->SetNumberField(TEXT("sampleCount"), Samples.Num());
	BlendSpaceObject->SetArrayField(TEXT("samples"), Samples);

	Root->SetObjectField(TEXT("blendSpace"), BlendSpaceObject);
	return Root;
}

TArray<TSharedPtr<FJsonValue>> FAnimAssetExtractor::ExtractNotifies(const UAnimSequenceBase* AnimBase)
{
	TArray<TSharedPtr<FJsonValue>> Notifies;
	if (!AnimBase)
	{
		return Notifies;
	}

	for (int32 NotifyIndex = 0; NotifyIndex < AnimBase->Notifies.Num(); ++NotifyIndex)
	{
		const FAnimNotifyEvent& NotifyEvent = AnimBase->Notifies[NotifyIndex];
		TSharedPtr<FJsonObject> NotifyObject = MakeShared<FJsonObject>();

		FString NotifyName = NotifyEvent.NotifyName.ToString();
		if (NotifyName.IsEmpty() && NotifyEvent.Notify)
		{
			NotifyName = NotifyEvent.Notify->GetNotifyName();
		}
		if (NotifyName.IsEmpty() && NotifyEvent.NotifyStateClass)
		{
			NotifyName = NotifyEvent.NotifyStateClass->GetNotifyName();
		}
		NotifyObject->SetStringField(TEXT("notifyName"), NotifyName);
		NotifyObject->SetStringField(TEXT("notifyId"), AnimAssetExtractorInternal::BuildNotifyId(NotifyEvent, NotifyIndex));
		NotifyObject->SetNumberField(TEXT("notifyIndex"), NotifyIndex);
		NotifyObject->SetNumberField(TEXT("trackIndex"), NotifyEvent.TrackIndex);
		NotifyObject->SetStringField(TEXT("trackName"), AnimAssetExtractorInternal::GetTrackName(AnimBase, NotifyEvent.TrackIndex));
		const FString NotifyGuid = AnimAssetExtractorInternal::GetNotifyGuidString(NotifyEvent);
		if (!NotifyGuid.IsEmpty())
		{
			NotifyObject->SetStringField(TEXT("notifyGuid"), NotifyGuid);
		}

		UObject* NotifyInstance = nullptr;
		if (NotifyEvent.Notify)
		{
			NotifyInstance = NotifyEvent.Notify;
			NotifyObject->SetStringField(TEXT("notifyClass"), NotifyEvent.Notify->GetClass()->GetName());
			NotifyObject->SetStringField(TEXT("notifyClassPath"), NotifyEvent.Notify->GetClass()->GetPathName());
			NotifyObject->SetStringField(TEXT("notifyType"), TEXT("Notify"));
		}
		else if (NotifyEvent.NotifyStateClass)
		{
			NotifyInstance = NotifyEvent.NotifyStateClass;
			NotifyObject->SetStringField(TEXT("notifyClass"), NotifyEvent.NotifyStateClass->GetClass()->GetName());
			NotifyObject->SetStringField(TEXT("notifyClassPath"), NotifyEvent.NotifyStateClass->GetClass()->GetPathName());
			NotifyObject->SetStringField(TEXT("notifyType"), TEXT("NotifyState"));
		}

		NotifyObject->SetNumberField(TEXT("triggerTime"), NotifyEvent.GetTriggerTime());
		NotifyObject->SetNumberField(TEXT("endTriggerTime"), NotifyEvent.GetEndTriggerTime());
		NotifyObject->SetNumberField(TEXT("duration"), NotifyEvent.GetDuration());
		NotifyObject->SetNumberField(TEXT("notifyTriggerChance"), NotifyEvent.NotifyTriggerChance);
		NotifyObject->SetStringField(TEXT("notifyFilterType"), AnimAssetExtractorInternal::NotifyFilterTypeToString(NotifyEvent.NotifyFilterType));
		NotifyObject->SetNumberField(TEXT("notifyFilterLOD"), NotifyEvent.NotifyFilterLOD);
		NotifyObject->SetBoolField(TEXT("canBeFilteredViaRequest"), NotifyEvent.bCanBeFilteredViaRequest);
		NotifyObject->SetBoolField(TEXT("triggerOnDedicatedServer"), NotifyEvent.bTriggerOnDedicatedServer);
		NotifyObject->SetBoolField(TEXT("triggerOnFollower"), NotifyEvent.bTriggerOnFollower);
		NotifyObject->SetStringField(TEXT("montageTickType"), AnimAssetExtractorInternal::MontageTickTypeToString(NotifyEvent.MontageTickType));
		NotifyObject->SetBoolField(TEXT("convertedFromBranchingPoint"), NotifyEvent.bConvertedFromBranchingPoint);

		if (NotifyInstance)
		{
			const TSharedPtr<FJsonObject> Properties = FPropertySerializer::SerializePropertyOverrides(NotifyInstance);
			if (Properties.IsValid() && Properties->Values.Num() > 0)
			{
				NotifyObject->SetObjectField(TEXT("properties"), Properties);
			}
		}

		Notifies.Add(MakeShared<FJsonValueObject>(NotifyObject));
	}

	return Notifies;
}

TArray<TSharedPtr<FJsonValue>> FAnimAssetExtractor::ExtractCurves(const UAnimSequenceBase* AnimBase)
{
	TArray<TSharedPtr<FJsonValue>> Curves;
	if (!AnimBase)
	{
		return Curves;
	}

	for (const FFloatCurve& Curve : AnimBase->GetCurveData().FloatCurves)
	{
		TSharedPtr<FJsonObject> CurveObject = MakeShared<FJsonObject>();
		CurveObject->SetStringField(TEXT("curveName"), Curve.GetName().ToString());
		CurveObject->SetNumberField(TEXT("curveTypeFlags"), Curve.GetCurveTypeFlags());

		TArray<TSharedPtr<FJsonValue>> Keys;
		for (const FRichCurveKey& Key : Curve.FloatCurve.GetConstRefOfKeys())
		{
			Keys.Add(MakeShared<FJsonValueObject>(AnimAssetExtractorInternal::SerializeRichCurveKey(Key)));
		}
		CurveObject->SetArrayField(TEXT("keys"), Keys);
		Curves.Add(MakeShared<FJsonValueObject>(CurveObject));
	}

	return Curves;
}
