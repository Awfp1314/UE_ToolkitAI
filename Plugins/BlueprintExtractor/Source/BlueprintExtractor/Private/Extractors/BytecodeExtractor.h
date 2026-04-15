#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBlueprint;

struct FBytecodeExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UBlueprint* Blueprint);
};
