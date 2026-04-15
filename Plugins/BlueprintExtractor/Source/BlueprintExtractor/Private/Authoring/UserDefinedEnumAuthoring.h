#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UUserDefinedEnum;

struct FUserDefinedEnumAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UUserDefinedEnum* UserDefinedEnum,
	                                      const FString& Operation,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
