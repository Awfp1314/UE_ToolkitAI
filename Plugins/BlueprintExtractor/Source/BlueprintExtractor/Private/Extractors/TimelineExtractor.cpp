#include "Extractors/TimelineExtractor.h"
#include "BlueprintJsonSchema.h"
#include "BlueprintExtractorModule.h"
#include "Engine/Blueprint.h"
#include "Engine/TimelineTemplate.h"
#include "Curves/CurveFloat.h"
#include "Curves/CurveVector.h"
#include "Curves/CurveLinearColor.h"

static TSharedPtr<FJsonObject> SerializeCurveKey(const FRichCurveKey& Key)
{
	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();
	Obj->SetNumberField(TEXT("time"), Key.Time);
	Obj->SetNumberField(TEXT("value"), Key.Value);
	Obj->SetNumberField(TEXT("arriveTangent"), Key.ArriveTangent);
	Obj->SetNumberField(TEXT("leaveTangent"), Key.LeaveTangent);

	FString InterpMode;
	switch (Key.InterpMode)
	{
	case RCIM_Linear: InterpMode = TEXT("Linear"); break;
	case RCIM_Constant: InterpMode = TEXT("Constant"); break;
	case RCIM_Cubic: InterpMode = TEXT("Cubic"); break;
	default: InterpMode = TEXT("None"); break;
	}
	Obj->SetStringField(TEXT("interpMode"), InterpMode);

	return Obj;
}

static TArray<TSharedPtr<FJsonValue>> SerializeFloatCurveKeys(const FRichCurve& Curve)
{
	TArray<TSharedPtr<FJsonValue>> Keys;
	for (const FRichCurveKey& Key : Curve.GetConstRefOfKeys())
	{
		Keys.Add(MakeShared<FJsonValueObject>(SerializeCurveKey(Key)));
	}
	return Keys;
}

TArray<TSharedPtr<FJsonValue>> FTimelineExtractor::Extract(const UBlueprint* Blueprint)
{
	TArray<TSharedPtr<FJsonValue>> Result;

	if (!ensureMsgf(Blueprint, TEXT("TimelineExtractor: null Blueprint")))
	{
		return Result;
	}

	for (const UTimelineTemplate* Timeline : Blueprint->Timelines)
	{
		if (!Timeline)
		{
			continue;
		}

		TSharedPtr<FJsonObject> TlObj = MakeShared<FJsonObject>();
		TlObj->SetStringField(TEXT("name"), Timeline->GetVariableName().ToString());
		TlObj->SetNumberField(TEXT("timelineLength"), Timeline->TimelineLength);
		TlObj->SetBoolField(TEXT("autoPlay"), Timeline->bAutoPlay);
		TlObj->SetBoolField(TEXT("loop"), Timeline->bLoop);
		TlObj->SetBoolField(TEXT("replicated"), Timeline->bReplicated);
		TlObj->SetBoolField(TEXT("ignoreTimeDilation"), Timeline->bIgnoreTimeDilation);

		TArray<TSharedPtr<FJsonValue>> AllTracks;

		// Float tracks
		for (const FTTFloatTrack& Track : Timeline->FloatTracks)
		{
			TSharedPtr<FJsonObject> TrackObj = MakeShared<FJsonObject>();
			TrackObj->SetStringField(TEXT("trackName"), Track.GetTrackName().ToString());
			TrackObj->SetStringField(TEXT("trackType"), TEXT("Float"));

			if (Track.CurveFloat)
			{
				TrackObj->SetArrayField(TEXT("keys"), SerializeFloatCurveKeys(Track.CurveFloat->FloatCurve));
			}

			AllTracks.Add(MakeShared<FJsonValueObject>(TrackObj));
		}

		// Vector tracks
		for (const FTTVectorTrack& Track : Timeline->VectorTracks)
		{
			TSharedPtr<FJsonObject> TrackObj = MakeShared<FJsonObject>();
			TrackObj->SetStringField(TEXT("trackName"), Track.GetTrackName().ToString());
			TrackObj->SetStringField(TEXT("trackType"), TEXT("Vector"));

			if (Track.CurveVector)
			{
				TSharedPtr<FJsonObject> CurvesObj = MakeShared<FJsonObject>();
				CurvesObj->SetArrayField(TEXT("x"), SerializeFloatCurveKeys(Track.CurveVector->FloatCurves[0]));
				CurvesObj->SetArrayField(TEXT("y"), SerializeFloatCurveKeys(Track.CurveVector->FloatCurves[1]));
				CurvesObj->SetArrayField(TEXT("z"), SerializeFloatCurveKeys(Track.CurveVector->FloatCurves[2]));
				TrackObj->SetObjectField(TEXT("curves"), CurvesObj);
			}

			AllTracks.Add(MakeShared<FJsonValueObject>(TrackObj));
		}

		// Event tracks
		for (const FTTEventTrack& Track : Timeline->EventTracks)
		{
			TSharedPtr<FJsonObject> TrackObj = MakeShared<FJsonObject>();
			TrackObj->SetStringField(TEXT("trackName"), Track.GetTrackName().ToString());
			TrackObj->SetStringField(TEXT("trackType"), TEXT("Event"));

			if (Track.CurveKeys)
			{
				TArray<TSharedPtr<FJsonValue>> Keys;
				for (const FRichCurveKey& Key : Track.CurveKeys->FloatCurve.GetConstRefOfKeys())
				{
					TSharedPtr<FJsonObject> KeyObj = MakeShared<FJsonObject>();
					KeyObj->SetNumberField(TEXT("time"), Key.Time);
					Keys.Add(MakeShared<FJsonValueObject>(KeyObj));
				}
				TrackObj->SetArrayField(TEXT("keys"), Keys);
			}

			AllTracks.Add(MakeShared<FJsonValueObject>(TrackObj));
		}

		// Linear color tracks
		for (const FTTLinearColorTrack& Track : Timeline->LinearColorTracks)
		{
			TSharedPtr<FJsonObject> TrackObj = MakeShared<FJsonObject>();
			TrackObj->SetStringField(TEXT("trackName"), Track.GetTrackName().ToString());
			TrackObj->SetStringField(TEXT("trackType"), TEXT("LinearColor"));

			if (Track.CurveLinearColor)
			{
				TSharedPtr<FJsonObject> CurvesObj = MakeShared<FJsonObject>();
				CurvesObj->SetArrayField(TEXT("r"), SerializeFloatCurveKeys(Track.CurveLinearColor->FloatCurves[0]));
				CurvesObj->SetArrayField(TEXT("g"), SerializeFloatCurveKeys(Track.CurveLinearColor->FloatCurves[1]));
				CurvesObj->SetArrayField(TEXT("b"), SerializeFloatCurveKeys(Track.CurveLinearColor->FloatCurves[2]));
				CurvesObj->SetArrayField(TEXT("a"), SerializeFloatCurveKeys(Track.CurveLinearColor->FloatCurves[3]));
				TrackObj->SetObjectField(TEXT("curves"), CurvesObj);
			}

			AllTracks.Add(MakeShared<FJsonValueObject>(TrackObj));
		}

		TlObj->SetArrayField(TEXT("tracks"), AllTracks);
		Result.Add(MakeShared<FJsonValueObject>(TlObj));
	}

	return Result;
}
