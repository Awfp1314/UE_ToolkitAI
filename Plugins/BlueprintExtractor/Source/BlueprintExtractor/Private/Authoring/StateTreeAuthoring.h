#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UStateTree;

struct FStateTreeAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UStateTree* StateTree,
	                                      const FString& Operation,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
