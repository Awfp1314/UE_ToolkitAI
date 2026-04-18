#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "BlueprintAnalyzerSubsystem.generated.h"

/**
 * Editor subsystem for blueprint analysis
 * Provides read-only access to blueprint structure for AI assistant
 */
UCLASS()
class BLUEPRINTANALYZER_API UBlueprintAnalyzerSubsystem : public UEditorSubsystem
{
	GENERATED_BODY()

public:
	/**
	 * Extracts a Blueprint asset to a JSON string
	 * Returns blueprint structure including graphs, variables, and functions
	 * @param AssetPath - Full asset path (e.g. "/Game/Blueprints/MyBlueprint")
	 * @return JSON string with blueprint data or error object
	 */
	UFUNCTION(BlueprintCallable, Category="Blueprint Analyzer")
	FString ExtractBlueprint(const FString& AssetPath);

	/**
	 * Extracts a Widget Blueprint (UMG) to a JSON string
	 * Returns widget hierarchy and properties
	 * @param AssetPath - Full asset path to widget blueprint
	 * @return JSON string with widget data or error object
	 */
	UFUNCTION(BlueprintCallable, Category="Blueprint Analyzer")
	FString ExtractWidgetBlueprint(const FString& AssetPath);

	/**
	 * Gets current editor context information
	 * Returns project info, open assets, and editor state
	 * @return JSON string with editor context
	 */
	UFUNCTION(BlueprintCallable, Category="Blueprint Analyzer")
	FString GetEditorContext();

private:
	// Helper: Load asset from path
	UObject* LoadAssetFromPath(const FString& AssetPath);
	
	// Helper: Create error JSON
	FString CreateErrorJson(const FString& ErrorMessage);
	
	// Helper: Extract blueprint graph data
	TSharedPtr<FJsonObject> ExtractGraphData(class UEdGraph* Graph);
	
	// Helper: Extract blueprint variables
	TArray<TSharedPtr<FJsonValue>> ExtractVariables(class UBlueprint* Blueprint);
	
	// Helper: Extract blueprint functions
	TArray<TSharedPtr<FJsonValue>> ExtractFunctions(class UBlueprint* Blueprint);
	
	// Helper: Extract widget tree
	TSharedPtr<FJsonObject> ExtractWidgetTree(class UWidgetBlueprint* WidgetBP);
};
