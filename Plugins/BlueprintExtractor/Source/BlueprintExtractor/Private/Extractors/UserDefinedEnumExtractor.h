#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UUserDefinedEnum;

struct FUserDefinedEnumExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UUserDefinedEnum* UserDefinedEnum);
};
