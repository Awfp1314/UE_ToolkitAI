// Copyright HUTAO. All Rights Reserved.

#include "BlueprintToAI.h"

#define LOCTEXT_NAMESPACE "FBlueprintToAIModule"

void FBlueprintToAIModule::StartupModule()
{
	UE_LOG(LogTemp, Log, TEXT("BlueprintToAI: Module started"));
}

void FBlueprintToAIModule::ShutdownModule()
{
	UE_LOG(LogTemp, Log, TEXT("BlueprintToAI: Module shutdown"));
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FBlueprintToAIModule, BlueprintToAI)
