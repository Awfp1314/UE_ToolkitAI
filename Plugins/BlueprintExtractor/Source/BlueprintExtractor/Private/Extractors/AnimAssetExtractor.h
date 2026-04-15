#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

class UAnimSequence;
class UAnimSequenceBase;
class UAnimMontage;
class UBlendSpace;

struct FAnimAssetExtractor
{
	static TSharedPtr<FJsonObject> ExtractAnimSequence(const UAnimSequence* AnimSequence);
	static TSharedPtr<FJsonObject> ExtractAnimMontage(const UAnimMontage* AnimMontage);
	static TSharedPtr<FJsonObject> ExtractBlendSpace(const UBlendSpace* BlendSpace);

private:
	static TArray<TSharedPtr<FJsonValue>> ExtractNotifies(const UAnimSequenceBase* AnimBase);
	static TArray<TSharedPtr<FJsonValue>> ExtractCurves(const UAnimSequenceBase* AnimBase);
};
