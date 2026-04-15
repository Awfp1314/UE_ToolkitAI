#pragma once

#include "CoreMinimal.h"
#include "BlueprintExtractorTypes.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BlueprintExtractorLibrary.generated.h"

class UBlueprint;
class UStateTree;
class UDataAsset;
class UDataTable;
class UBehaviorTree;
class UBlackboardData;
class UUserDefinedStruct;
class UUserDefinedEnum;
class UCurveBase;
class UCurveTable;
class UMaterial;
class UMaterialInstance;
class UMaterialFunctionInterface;
class UAnimSequence;
class UAnimMontage;
class UBlendSpace;

UCLASS()
class BLUEPRINTEXTRACTOR_API UBlueprintExtractorLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractBlueprintToJson(UBlueprint* Blueprint, const FString& OutputPath, EBlueprintExtractionScope Scope, const TArray<FName>& GraphFilter);

	static bool ExtractBlueprintToJson(UBlueprint* Blueprint, const FString& OutputPath, EBlueprintExtractionScope Scope)
	{ return ExtractBlueprintToJson(Blueprint, OutputPath, Scope, TArray<FName>()); }

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractBlueprintToJsonString(UBlueprint* Blueprint, FString& OutJsonString, EBlueprintExtractionScope Scope, const TArray<FName>& GraphFilter, bool bIncludeClassDefaults = false);

	static bool ExtractBlueprintToJsonString(UBlueprint* Blueprint, FString& OutJsonString, EBlueprintExtractionScope Scope)
	{ return ExtractBlueprintToJsonString(Blueprint, OutJsonString, Scope, TArray<FName>()); }

	static TSharedPtr<FJsonObject> ExtractBlueprintToJsonObject(UBlueprint* Blueprint, EBlueprintExtractionScope Scope, const TArray<FName>& GraphFilter = {}, bool bIncludeClassDefaults = false);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractStateTreeToJson(UStateTree* StateTree, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractStateTreeToJsonObject(UStateTree* StateTree);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractDataAssetToJson(UDataAsset* DataAsset, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractDataAssetToJsonObject(UDataAsset* DataAsset);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractDataTableToJson(UDataTable* DataTable, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractDataTableToJsonObject(UDataTable* DataTable);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractBehaviorTreeToJson(UBehaviorTree* BehaviorTree, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractBehaviorTreeToJsonObject(UBehaviorTree* BehaviorTree);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractBlackboardToJson(UBlackboardData* BlackboardData, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractBlackboardToJsonObject(UBlackboardData* BlackboardData);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractUserDefinedStructToJson(UUserDefinedStruct* UserDefinedStruct, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractUserDefinedStructToJsonObject(UUserDefinedStruct* UserDefinedStruct);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractUserDefinedEnumToJson(UUserDefinedEnum* UserDefinedEnum, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractUserDefinedEnumToJsonObject(UUserDefinedEnum* UserDefinedEnum);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractCurveToJson(UCurveBase* Curve, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractCurveToJsonObject(UCurveBase* Curve);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractCurveTableToJson(UCurveTable* CurveTable, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractCurveTableToJsonObject(UCurveTable* CurveTable);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractMaterialInstanceToJson(UMaterialInstance* MaterialInstance, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractMaterialInstanceToJsonObject(UMaterialInstance* MaterialInstance);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractMaterialToJson(UMaterial* Material, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractMaterialToJsonObject(UMaterial* Material, bool bVerbose = false);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractMaterialFunctionToJson(UMaterialFunctionInterface* MaterialFunction, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractMaterialFunctionToJsonObject(UMaterialFunctionInterface* MaterialFunction, bool bVerbose = false);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractAnimSequenceToJson(UAnimSequence* AnimSequence, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractAnimSequenceToJsonObject(UAnimSequence* AnimSequence);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractAnimMontageToJson(UAnimMontage* AnimMontage, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractAnimMontageToJsonObject(UAnimMontage* AnimMontage);

	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor", meta=(DevelopmentOnly))
	static bool ExtractBlendSpaceToJson(UBlendSpace* BlendSpace, const FString& OutputPath);

	static TSharedPtr<FJsonObject> ExtractBlendSpaceToJsonObject(UBlendSpace* BlendSpace);

	/** Extract assets with cascade: follows references to other extractable assets (Blueprints, StateTrees).
	 *  GraphFilter limits which graphs are extracted from Blueprints. Empty = all graphs. */
	static TSharedPtr<FJsonObject> ExtractWithCascade(const TArray<UObject*>& InitialAssets, const FString& OutputDir, EBlueprintExtractionScope Scope, int32 MaxDepth, const TArray<FName>& GraphFilter = {});

private:
	static TArray<FSoftObjectPath> CollectBlueprintReferences(const UBlueprint* Blueprint);
	static TArray<FSoftObjectPath> CollectStateTreeReferences(const UStateTree* StateTree);
	static TArray<FSoftObjectPath> CollectBehaviorTreeReferences(const UBehaviorTree* BehaviorTree);
	static TArray<FSoftObjectPath> CollectMaterialReferences(const UMaterial* Material);
	static TArray<FSoftObjectPath> CollectMaterialFunctionReferences(const UMaterialFunctionInterface* MaterialFunction);
	static TArray<FSoftObjectPath> CollectMaterialInstanceReferences(const UMaterialInstance* MaterialInstance);
	static TArray<FSoftObjectPath> CollectAnimMontageReferences(const UAnimMontage* AnimMontage);
	static TArray<FSoftObjectPath> CollectBlendSpaceReferences(const UBlendSpace* BlendSpace);
};
