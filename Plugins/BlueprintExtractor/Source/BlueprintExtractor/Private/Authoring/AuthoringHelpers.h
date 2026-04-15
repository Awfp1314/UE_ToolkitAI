#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "EdGraph/EdGraphPin.h"

class FProperty;
class UBlueprint;
class UClass;
class UObject;
class UScriptStruct;
class UEnum;
enum class EBlueprintCompileOptions;
struct FAssetMutationContext;

struct FAuthoringHelpers
{
	static UObject* ResolveObject(const FString& ObjectPath, UClass* RequiredClass = nullptr);
	static UClass* ResolveClass(const FString& ClassPath, UClass* RequiredBaseClass = nullptr);
	static UScriptStruct* ResolveScriptStruct(const FString& StructPath);
	static UEnum* ResolveEnum(const FString& EnumPath);

	static bool ParsePinType(const TSharedPtr<FJsonObject>& PinTypeObject,
	                         FEdGraphPinType& OutPinType,
	                         FString& OutError);

	static bool ApplyStructProperties(const UScriptStruct* ScriptStruct,
	                                  void* StructMemory,
	                                  const TSharedPtr<FJsonObject>& Properties,
	                                  TArray<FString>& OutErrors,
	                                  bool bValidationOnly);

	static bool JsonValueToPropertyExportText(const FProperty* Property,
	                                          const TSharedPtr<FJsonValue>& JsonValue,
	                                          FString& OutText,
	                                          TArray<FString>& OutErrors,
	                                          UObject* OwnerObject = nullptr);

	static bool CompileBlueprint(UBlueprint* Blueprint,
	                             FAssetMutationContext& Context,
	                             const FString& AssetKind,
	                             EBlueprintCompileOptions AdditionalCompileOptions = static_cast<EBlueprintCompileOptions>(0));
};
