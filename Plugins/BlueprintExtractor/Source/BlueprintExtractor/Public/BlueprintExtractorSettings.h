#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "BlueprintExtractorTypes.h"
#include "BlueprintExtractorSettings.generated.h"

UCLASS(Config=EditorPerProjectUserSettings, DefaultConfig, meta=(DisplayName="Blueprint Extractor"))
class BLUEPRINTEXTRACTOR_API UBlueprintExtractorSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	UBlueprintExtractorSettings();

	FString GetResolvedOutputDirectoryPath() const;
	static FString ResolveOutputDirectoryPath(const FString& ConfiguredPath);

	UPROPERTY(Config, EditAnywhere, Category="Output", meta=(RelativeToGameContentDir))
	FDirectoryPath OutputDirectory;

	UPROPERTY(Config, EditAnywhere, Category="Output")
	EBlueprintExtractionScope DefaultScope = EBlueprintExtractionScope::Full;

	UPROPERTY(Config, EditAnywhere, Category="Output")
	bool bPrettyPrint = true;

	UPROPERTY(Config, EditAnywhere, Category="Advanced")
	bool bIncludeBytecode = false;

	UPROPERTY(Config, EditAnywhere, Category="Cascade", meta=(DisplayName="Enable Cascade Extraction"))
	bool bEnableCascadeExtraction = false;

	UPROPERTY(Config, EditAnywhere, Category="Cascade", meta=(ClampMin=1, ClampMax=10, EditCondition="bEnableCascadeExtraction", DisplayName="Max Cascade Depth"))
	int32 MaxCascadeDepth = 3;

	static const UBlueprintExtractorSettings* Get();

	virtual FName GetCategoryName() const override { return TEXT("Plugins"); }
	virtual FText GetSectionText() const override;
};
