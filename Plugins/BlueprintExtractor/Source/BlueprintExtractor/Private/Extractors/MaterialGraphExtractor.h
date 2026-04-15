#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UMaterial;
class UMaterialFunctionInterface;

struct FMaterialGraphExtractor
{
	static TSharedPtr<FJsonObject> ExtractMaterial(const UMaterial* Material, bool bVerbose = false);
	static TSharedPtr<FJsonObject> ExtractMaterialFunction(const UMaterialFunctionInterface* MaterialFunction, bool bVerbose = false);
};
