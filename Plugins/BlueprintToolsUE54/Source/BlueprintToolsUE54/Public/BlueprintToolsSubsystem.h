#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "BlueprintToolsTypes.h"
#include "BlueprintToolsSubsystem.generated.h"

/**
 * Editor subsystem for Blueprint extraction and authoring via Remote Control API
 * Focused on core Blueprint operations for UE 5.4
 */
UCLASS()
class BLUEPRINTTOOLSUE54_API UBlueprintToolsSubsystem : public UEditorSubsystem
{
	GENERATED_BODY()

private:
	static EBlueprintExtractionScope ParseScope(const FString& ScopeString);
	
	// Variable operation helpers
	FString AddVariable(UBlueprint* Blueprint, const TSharedPtr<FJsonObject>& PayloadObject);
	FString RemoveVariable(UBlueprint* Blueprint, const TSharedPtr<FJsonObject>& PayloadObject);
	FString ModifyVariable(UBlueprint* Blueprint, const TSharedPtr<FJsonObject>& PayloadObject);

public:
	/** Extracts a Blueprint asset to a JSON string. Returns an error JSON object on failure.
	 *  Scope: ClassLevel, Variables, Components, FunctionsShallow, Full (default)
	 *  GraphFilter: comma-separated list of graph names to extract (empty = all graphs)
	 *  bIncludeClassDefaults: include CDO property values that differ from parent class */
	UFUNCTION(BlueprintCallable, Category="Blueprint Tools")
	FString ExtractBlueprint(
		const FString& AssetPath,
		const FString& Scope = TEXT("Full"),
		const FString& GraphFilter = TEXT(""),
		const bool bIncludeClassDefaults = false);

	/** Creates a new Blueprint asset with optional member payloads.
	 *  ParentClassPath: full path to parent class (e.g., "/Script/Engine.Actor")
	 *  PayloadJson: optional JSON with variables, functions, components to create
	 *  bValidateOnly: if true, only validates without creating */
	UFUNCTION(BlueprintCallable, Category="Blueprint Tools")
	FString CreateBlueprint(
		const FString& AssetPath,
		const FString& ParentClassPath,
		const FString& PayloadJson = TEXT(""),
		const bool bValidateOnly = false);

	/** Modifies member authoring surfaces on an existing Blueprint asset.
	 *  Operation: add_variable, remove_variable, modify_variable, add_function, remove_function, etc.
	 *  PayloadJson: operation-specific JSON payload
	 *  bValidateOnly: if true, only validates without modifying */
	UFUNCTION(BlueprintCallable, Category="Blueprint Tools")
	FString ModifyBlueprintMembers(
		const FString& AssetPath,
		const FString& Operation,
		const FString& PayloadJson = TEXT(""),
		const bool bValidateOnly = false);

	/** Compiles a Blueprint asset. Returns JSON array of errors/warnings. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Tools")
	FString CompileBlueprint(const FString& AssetPath);

	/** Saves one or more dirty asset packages explicitly.
	 *  AssetPathsJson: JSON array of asset paths to save */
	UFUNCTION(BlueprintCallable, Category="Blueprint Tools")
	FString SaveAssets(const FString& AssetPathsJson);

	/** Searches assets by name query and optional class filter.
	 *  Query: search string
	 *  ClassFilter: filter by class name (default: "Blueprint")
	 *  MaxResults: maximum number of results to return */
	UFUNCTION(BlueprintCallable, Category="Blueprint Tools")
	FString SearchAssets(
		const FString& Query,
		const FString& ClassFilter = TEXT("Blueprint"),
		const int32 MaxResults = 50);

	/** Lists assets under a package path.
	 *  PackagePath: path to search (e.g., "/Game/Blueprints")
	 *  bRecursive: search subdirectories
	 *  ClassFilter: filter by class name (empty = all) */
	UFUNCTION(BlueprintCallable, Category="Blueprint Tools")
	FString ListAssets(
		const FString& PackagePath,
		const bool bRecursive = true,
		const FString& ClassFilter = TEXT(""));

	/** Returns current project/editor context for MCP host integration. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Tools")
	FString GetEditorContext();
};
