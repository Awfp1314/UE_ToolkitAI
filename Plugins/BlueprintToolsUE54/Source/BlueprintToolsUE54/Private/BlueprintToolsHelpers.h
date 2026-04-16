#pragma once

#include "CoreMinimal.h"
#include "EdGraph/EdGraphPin.h"

class UBlueprint;
class FJsonObject;
class FJsonValue;

/**
 * Helper functions for Blueprint authoring operations
 */
class FBlueprintToolsHelpers
{
public:
	/** Resolve an object by path (class, struct, enum, asset) */
	static UObject* ResolveObject(const FString& ObjectPath, UClass* RequiredClass = nullptr);

	/** Resolve a class by path */
	static UClass* ResolveClass(const FString& ClassPath, UClass* RequiredBaseClass = nullptr);

	/** Resolve a script struct by path */
	static UScriptStruct* ResolveScriptStruct(const FString& StructPath);

	/** Resolve an enum by path */
	static UEnum* ResolveEnum(const FString& EnumPath);

	/** Parse pin type from JSON object */
	static bool ParsePinType(const TSharedPtr<FJsonObject>& PinTypeObject,
	                        FEdGraphPinType& OutPinType,
	                        FString& OutError);

	/** Find variable index by name in Blueprint */
	static int32 FindVariableIndex(const UBlueprint* Blueprint, FName VariableName);

	/** Compile Blueprint and collect errors/warnings */
	static bool CompileBlueprint(UBlueprint* Blueprint,
	                            TArray<TSharedPtr<FJsonValue>>& OutErrors,
	                            TArray<TSharedPtr<FJsonValue>>& OutWarnings);

	/** Create error JSON object */
	static TSharedPtr<FJsonObject> CreateErrorResponse(const FString& ErrorMessage);

	/** Create success JSON object */
	static TSharedPtr<FJsonObject> CreateSuccessResponse();

	/** Serialize JSON object to string */
	static FString SerializeJsonObject(const TSharedPtr<FJsonObject>& JsonObject);

private:
	/** Normalize asset object path */
	static FString NormalizeAssetObjectPath(const FString& ObjectPath);

	/** Check if asset exists in registry */
	static bool DoesAssetExist(const FString& AssetPath);

	/** Parse container type string */
	static bool ParseContainerType(const FString& ContainerTypeString, EPinContainerType& OutContainerType);

	/** Parse terminal type for map value types */
	static bool ParseTerminalType(const TSharedPtr<FJsonObject>& ValueTypeObject,
	                             FEdGraphTerminalType& OutTerminalType,
	                             FString& OutError);
};
