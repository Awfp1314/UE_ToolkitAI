#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UWidgetBlueprint;

struct FFontAuthoring
{
	static TSharedPtr<FJsonObject> ImportFonts(const TSharedPtr<FJsonObject>& PayloadJson,
	                                           bool bValidateOnly);
};
