#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UCurveBase;
struct FRichCurve;
struct FSimpleCurve;

struct FCurveExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UCurveBase* Curve);
	static TSharedPtr<FJsonObject> SerializeRichCurve(const FRichCurve& Curve);
	static TSharedPtr<FJsonObject> SerializeSimpleCurve(const FSimpleCurve& Curve);
};
