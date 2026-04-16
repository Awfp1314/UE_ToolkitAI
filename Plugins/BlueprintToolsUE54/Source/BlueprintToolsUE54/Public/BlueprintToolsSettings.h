#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "BlueprintToolsTypes.h"
#include "BlueprintToolsSettings.generated.h"

UCLASS(Config=EditorPerProjectUserSettings, DefaultConfig, meta=(DisplayName="Blueprint Tools UE5.4"))
class BLUEPRINTTOOLSUE54_API UBlueprintToolsSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	UBlueprintToolsSettings();

	UPROPERTY(Config, EditAnywhere, Category="Extraction")
	EBlueprintExtractionScope DefaultScope = EBlueprintExtractionScope::Full;

	UPROPERTY(Config, EditAnywhere, Category="Output")
	bool bPrettyPrintJson = true;

	UPROPERTY(Config, EditAnywhere, Category="Advanced")
	bool bAutoCompileAfterModify = true;

	static const UBlueprintToolsSettings* Get();

	virtual FName GetCategoryName() const override { return TEXT("Plugins"); }
	virtual FText GetSectionText() const override;
};
