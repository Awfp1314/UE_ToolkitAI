#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UMaterial;
class UMaterialFunctionInterface;
class UObject;

struct FMaterialGraphAuthoring
{
	static TSharedPtr<FJsonObject> CreateMaterial(const FString& AssetPath,
	                                              const FString& InitialTexturePath,
	                                              const TSharedPtr<FJsonObject>& SettingsJson,
	                                              bool bValidateOnly);

	static TSharedPtr<FJsonObject> CreateMaterialFunction(const FString& AssetPath,
	                                                      const FString& AssetKind,
	                                                      const TSharedPtr<FJsonObject>& SettingsJson,
	                                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> ModifyMaterial(UMaterial* Material,
	                                              const TSharedPtr<FJsonObject>& PayloadJson,
	                                              bool bValidateOnly);

	static TSharedPtr<FJsonObject> ModifyMaterialFunction(UMaterialFunctionInterface* MaterialFunction,
	                                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> CompileMaterialAsset(UObject* Asset);
};
