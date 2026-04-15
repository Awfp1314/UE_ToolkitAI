#include "BlueprintExtractorSettings.h"
#include "Misc/Paths.h"

#define LOCTEXT_NAMESPACE "BlueprintExtractorSettings"

UBlueprintExtractorSettings::UBlueprintExtractorSettings()
{
	OutputDirectory.Path = TEXT("BlueprintExtractor");
}

const UBlueprintExtractorSettings* UBlueprintExtractorSettings::Get()
{
	return GetDefault<UBlueprintExtractorSettings>();
}

FString UBlueprintExtractorSettings::GetResolvedOutputDirectoryPath() const
{
	return ResolveOutputDirectoryPath(OutputDirectory.Path);
}

FString UBlueprintExtractorSettings::ResolveOutputDirectoryPath(const FString& ConfiguredPath)
{
	if (ConfiguredPath.IsEmpty())
	{
		return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("BlueprintExtractor"));
	}

	if (FPaths::IsRelative(ConfiguredPath))
	{
		return FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir() / ConfiguredPath);
	}

	return FPaths::ConvertRelativePathToFull(ConfiguredPath);
}

FText UBlueprintExtractorSettings::GetSectionText() const
{
	return LOCTEXT("SectionText", "Blueprint Extractor");
}

#undef LOCTEXT_NAMESPACE
