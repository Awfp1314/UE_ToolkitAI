#include "BlueprintAnalyzerModule.h"

#define LOCTEXT_NAMESPACE "FBlueprintAnalyzerModule"

void FBlueprintAnalyzerModule::StartupModule()
{
	// This code will execute after your module is loaded into memory
	UE_LOG(LogTemp, Log, TEXT("BlueprintAnalyzer module started"));
}

void FBlueprintAnalyzerModule::ShutdownModule()
{
	// This function may be called during shutdown to clean up your module
	UE_LOG(LogTemp, Log, TEXT("BlueprintAnalyzer module shutdown"));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FBlueprintAnalyzerModule, BlueprintAnalyzer)
