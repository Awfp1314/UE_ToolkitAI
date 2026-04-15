#include "Extractors/CurveExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "Curves/CurveBase.h"
#include "Curves/CurveFloat.h"
#include "Curves/CurveLinearColor.h"
#include "Curves/CurveVector.h"
#include "Curves/RichCurve.h"
#include "Curves/SimpleCurve.h"

namespace CurveExtractorInternal
{

static FString InterpModeToString(const ERichCurveInterpMode InterpMode)
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

static FString ExtrapolationToString(const ERichCurveExtrapolation Extrapolation)
{
	switch (Extrapolation)
	{
	case RCCE_Cycle:
		return TEXT("Cycle");
	case RCCE_CycleWithOffset:
		return TEXT("CycleWithOffset");
	case RCCE_Oscillate:
		return TEXT("Oscillate");
	case RCCE_Linear:
		return TEXT("Linear");
	case RCCE_Constant:
		return TEXT("Constant");
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
	KeyObject->SetStringField(TEXT("interpMode"), InterpModeToString(Key.InterpMode));
	return KeyObject;
}

static TSharedPtr<FJsonObject> SerializeSimpleCurveKey(const FSimpleCurveKey& Key, const ERichCurveInterpMode InterpMode)
{
	TSharedPtr<FJsonObject> KeyObject = MakeShared<FJsonObject>();
	KeyObject->SetNumberField(TEXT("time"), Key.Time);
	KeyObject->SetNumberField(TEXT("value"), Key.Value);
	KeyObject->SetStringField(TEXT("interpMode"), InterpModeToString(InterpMode));
	return KeyObject;
}

static void SetCurveMetadata(const FRealCurve& Curve, const TSharedPtr<FJsonObject>& CurveObject)
{
	if (!CurveObject.IsValid())
	{
		return;
	}

	CurveObject->SetNumberField(TEXT("defaultValue"), Curve.GetDefaultValue());
	CurveObject->SetStringField(TEXT("preInfinityExtrap"), ExtrapolationToString(Curve.PreInfinityExtrap));
	CurveObject->SetStringField(TEXT("postInfinityExtrap"), ExtrapolationToString(Curve.PostInfinityExtrap));
}

} // namespace CurveExtractorInternal

TSharedPtr<FJsonObject> FCurveExtractor::Extract(const UCurveBase* Curve)
{
	if (!Curve)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> CurveObject = MakeShared<FJsonObject>();
	CurveObject->SetStringField(TEXT("assetPath"), Curve->GetPathName());
	CurveObject->SetStringField(TEXT("assetName"), Curve->GetName());

	TSharedPtr<FJsonObject> Channels = MakeShared<FJsonObject>();
	if (const UCurveFloat* FloatCurve = Cast<UCurveFloat>(Curve))
	{
		CurveObject->SetStringField(TEXT("curveType"), TEXT("Float"));
		Channels->SetObjectField(TEXT("default"), SerializeRichCurve(FloatCurve->FloatCurve));
	}
	else if (const UCurveVector* VectorCurve = Cast<UCurveVector>(Curve))
	{
		CurveObject->SetStringField(TEXT("curveType"), TEXT("Vector"));
		Channels->SetObjectField(TEXT("x"), SerializeRichCurve(VectorCurve->FloatCurves[0]));
		Channels->SetObjectField(TEXT("y"), SerializeRichCurve(VectorCurve->FloatCurves[1]));
		Channels->SetObjectField(TEXT("z"), SerializeRichCurve(VectorCurve->FloatCurves[2]));
	}
	else if (const UCurveLinearColor* LinearColorCurve = Cast<UCurveLinearColor>(Curve))
	{
		CurveObject->SetStringField(TEXT("curveType"), TEXT("LinearColor"));
		Channels->SetObjectField(TEXT("r"), SerializeRichCurve(LinearColorCurve->FloatCurves[0]));
		Channels->SetObjectField(TEXT("g"), SerializeRichCurve(LinearColorCurve->FloatCurves[1]));
		Channels->SetObjectField(TEXT("b"), SerializeRichCurve(LinearColorCurve->FloatCurves[2]));
		Channels->SetObjectField(TEXT("a"), SerializeRichCurve(LinearColorCurve->FloatCurves[3]));
	}
	else
	{
		return nullptr;
	}

	CurveObject->SetObjectField(TEXT("channels"), Channels);
	Root->SetObjectField(TEXT("curve"), CurveObject);
	return Root;
}

TSharedPtr<FJsonObject> FCurveExtractor::SerializeRichCurve(const FRichCurve& Curve)
{
	TSharedPtr<FJsonObject> CurveObject = MakeShared<FJsonObject>();
	CurveExtractorInternal::SetCurveMetadata(Curve, CurveObject);

	TArray<TSharedPtr<FJsonValue>> Keys;
	for (const FRichCurveKey& Key : Curve.GetConstRefOfKeys())
	{
		Keys.Add(MakeShared<FJsonValueObject>(CurveExtractorInternal::SerializeRichCurveKey(Key)));
	}
	CurveObject->SetArrayField(TEXT("keys"), Keys);

	return CurveObject;
}

TSharedPtr<FJsonObject> FCurveExtractor::SerializeSimpleCurve(const FSimpleCurve& Curve)
{
	TSharedPtr<FJsonObject> CurveObject = MakeShared<FJsonObject>();
	CurveExtractorInternal::SetCurveMetadata(Curve, CurveObject);

	TArray<TSharedPtr<FJsonValue>> Keys;
	for (const FSimpleCurveKey& Key : Curve.GetConstRefOfKeys())
	{
		Keys.Add(MakeShared<FJsonValueObject>(CurveExtractorInternal::SerializeSimpleCurveKey(Key, Curve.GetKeyInterpMode())));
	}
	CurveObject->SetArrayField(TEXT("keys"), Keys);

	return CurveObject;
}
