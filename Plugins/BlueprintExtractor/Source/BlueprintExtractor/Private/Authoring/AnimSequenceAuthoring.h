#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UAnimSequence;

struct FAnimSequenceAuthoring
{
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UAnimSequence* AnimSequence,
	                                      const FString& Operation,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
