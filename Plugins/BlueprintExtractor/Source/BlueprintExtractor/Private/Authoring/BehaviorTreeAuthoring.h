#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBehaviorTree;

struct FBehaviorTreeAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UBehaviorTree* BehaviorTree,
	                                      const FString& Operation,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
