#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"

class BLUEPRINTEXTRACTOR_API FBlueprintJsonSchema
{
public:
	static TSharedPtr<FJsonObject> SerializePinType(const FEdGraphPinType& PinType);
	static TArray<TSharedPtr<FJsonValue>> SerializePropertyFlags(uint64 Flags);
	static TArray<TSharedPtr<FJsonValue>> SerializeFunctionFlags(uint32 Flags);
	static TArray<TSharedPtr<FJsonValue>> SerializeClassFlags(uint32 Flags);
	static FString GetObjectPathString(const UObject* Object);
	static FString BlueprintTypeToString(EBlueprintType Type);
	static TSharedPtr<FJsonObject> SerializeObjectReference(const UClass* Class);
};
