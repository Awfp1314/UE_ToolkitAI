#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UUserDefinedStruct;

struct FUserDefinedStructAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UUserDefinedStruct* UserDefinedStruct,
	                                      const FString& Operation,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
