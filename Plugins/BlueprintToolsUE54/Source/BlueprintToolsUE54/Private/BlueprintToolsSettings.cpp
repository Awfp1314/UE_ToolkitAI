#include "BlueprintToolsSettings.h"

#define LOCTEXT_NAMESPACE "BlueprintToolsSettings"

UBlueprintToolsSettings::UBlueprintToolsSettings()
{
}

const UBlueprintToolsSettings* UBlueprintToolsSettings::Get()
{
	return GetDefault<UBlueprintToolsSettings>();
}

FText UBlueprintToolsSettings::GetSectionText() const
{
	return LOCTEXT("SettingsSection", "Blueprint Tools UE5.4");
}

#undef LOCTEXT_NAMESPACE
