#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBlueprint;

struct FBlueprintAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const FString& ParentClassPath,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UBlueprint* Blueprint,
	                                      const FString& Operation,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> ModifyGraphs(UBlueprint* Blueprint,
	                                            const FString& Operation,
	                                            const TSharedPtr<FJsonObject>& PayloadJson,
	                                            bool bValidateOnly);
};
