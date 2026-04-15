#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBlackboardData;

struct FBlackboardAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UBlackboardData* BlackboardData,
	                                      const FString& Operation,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
