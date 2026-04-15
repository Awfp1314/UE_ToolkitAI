// Copyright HUTAO. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "BlueprintToAISubsystem.generated.h"

/**
 * Editor Subsystem for Blueprint AI operations
 * Provides functions to extract, create, and modify Blueprints via Remote Control API
 */
UCLASS()
class BLUEPRINTTOAI_API UBlueprintToAISubsystem : public UEditorSubsystem
{
	GENERATED_BODY()

public:
	// USubsystem implementation
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/**
	 * Extract Blueprint structure to JSON
	 * @param AssetPath - Content path to the Blueprint asset (e.g., "/Game/Blueprints/BP_MyActor")
	 * @param Scope - Extraction scope: "Minimal", "Compact", or "Full"
	 * @return JSON string containing Blueprint structure
	 */
	UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
	FString ExtractBlueprint(const FString& AssetPath, const FString& Scope);

	/**
	 * Create a new Blueprint asset
	 * @param AssetPath - Content path for the new Blueprint (e.g., "/Game/Blueprints/BP_NewActor")
	 * @param ParentClass - Parent class path (e.g., "/Script/Engine.Actor")
	 * @param GraphDSL - Optional DSL string to define initial graph (e.g., "Event BeginPlay -> Print(\"Hello\")")
	 * @param PayloadJson - Optional JSON payload for variables, components, etc.
	 * @return JSON string with operation result
	 */
	UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
	FString CreateBlueprint(const FString& AssetPath, const FString& ParentClass, 
	                       const FString& GraphDSL, const FString& PayloadJson);

	/**
	 * Modify an existing Blueprint
	 * @param AssetPath - Content path to the Blueprint asset
	 * @param Operation - Operation type: "add_variable", "add_component", "modify_graph", "reparent"
	 * @param PayloadJson - JSON payload with operation-specific data
	 * @return JSON string with operation result
	 */
	UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
	FString ModifyBlueprint(const FString& AssetPath, const FString& Operation, 
	                       const FString& PayloadJson);

	/**
	 * Save Blueprint assets to disk
	 * @param AssetPaths - Array of content paths to save
	 * @return JSON string with operation result
	 */
	UFUNCTION(BlueprintCallable, Category = "BlueprintToAI")
	FString SaveBlueprints(const TArray<FString>& AssetPaths);

private:
	// Helper: Load Blueprint from asset path
	class UBlueprint* LoadBlueprintAsset(const FString& AssetPath, FString& OutError);
	
	// Helper: Create success response JSON
	FString CreateSuccessResponse(const FString& Operation, const TSharedPtr<FJsonObject>& Data = nullptr);
	
	// Helper: Create error response JSON
	FString CreateErrorResponse(const FString& Operation, const FString& ErrorMessage);
};
