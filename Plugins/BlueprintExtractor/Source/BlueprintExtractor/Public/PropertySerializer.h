#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

class FProperty;
class UClass;
class UObject;

struct FPropertySerializer
{
	static TSharedPtr<FJsonValue> SerializePropertyValue(const FProperty* Property, const void* ValuePtr);
	static TSharedPtr<FJsonObject> SerializePropertyOverrides(const UObject* Object);
	static TSharedPtr<FJsonObject> SerializePropertyOverridesAgainstBaseline(const UObject* Object, const UObject* BaselineObject);
	static TArray<TSharedPtr<FJsonValue>> SerializeUserProperties(
		const void* Container,
		const UClass* ContainerClass,
		const TArray<const UClass*>& SkipClasses);
	static bool ApplyJsonValueToProperty(const FProperty* Property,
	                                     void* ValuePtr,
	                                     UObject* OwnerObject,
	                                     const TSharedPtr<FJsonValue>& JsonValue,
	                                     TArray<FString>& OutErrors,
	                                     bool bValidationOnly = false);
	static bool ApplyPropertiesFromJson(UObject* Target,
	                                    const TSharedPtr<FJsonObject>& PropertiesJson,
	                                    TArray<FString>& OutErrors,
	                                    bool bValidationOnly = false,
	                                    bool bRequireEditableProperty = true);
};
