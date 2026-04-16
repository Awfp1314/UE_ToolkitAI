#include "BlueprintToolsModule.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "RemoteControlSettings.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

DEFINE_LOG_CATEGORY(LogBlueprintTools);

#define LOCTEXT_NAMESPACE "FBlueprintToolsModule"

namespace
{
	static FString SerializeRegistryJsonObject(const TSharedPtr<FJsonObject>& JsonObject)
	{
		FString OutString;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
		FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
		return OutString;
	}
}

void FBlueprintToolsModule::StartupModule()
{
	EditorInstanceId = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower);
	RegistryFilePath = FPaths::Combine(GetEditorRegistryDirectory(), FString::Printf(TEXT("%s.json"), *EditorInstanceId));
	RefreshEditorRegistry();
	
	RegistryTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateRaw(this, &FBlueprintToolsModule::HandleRegistryHeartbeat),
		2.0f);
	
	UE_LOG(LogBlueprintTools, Log, TEXT("BlueprintTools UE5.4 module started"));
}

void FBlueprintToolsModule::ShutdownModule()
{
	if (RegistryTickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(RegistryTickerHandle);
		RegistryTickerHandle.Reset();
	}
	
	RemoveEditorRegistryFile();
	UE_LOG(LogBlueprintTools, Log, TEXT("BlueprintTools UE5.4 module shutdown"));
}

FString FBlueprintToolsModule::GetRemoteControlHost() const
{
	return TEXT("127.0.0.1");
}

int32 FBlueprintToolsModule::GetRemoteControlHttpPort() const
{
	return static_cast<int32>(GetDefault<URemoteControlSettings>()->RemoteControlHttpServerPort);
}

FString FBlueprintToolsModule::GetEditorRegistryDirectory() const
{
	const FString OverrideDir = FPlatformMisc::GetEnvironmentVariable(TEXT("BLUEPRINT_TOOLS_EDITOR_REGISTRY_DIR"));
	if (!OverrideDir.IsEmpty())
	{
		return FPaths::ConvertRelativePathToFull(OverrideDir);
	}

	return FPaths::Combine(
		FPaths::ConvertRelativePathToFull(FPlatformProcess::UserTempDir()),
		TEXT("BlueprintTools"),
		TEXT("EditorRegistry"));
}

void FBlueprintToolsModule::RefreshEditorRegistry()
{
	if (EditorInstanceId.IsEmpty())
	{
		return;
	}

	const FString RegistryDir = GetEditorRegistryDirectory();
	IFileManager::Get().MakeDirectory(*RegistryDir, true);

	const TSharedPtr<FJsonObject> Snapshot = MakeShared<FJsonObject>();
	LastRegistryHeartbeat = FDateTime::UtcNow().ToIso8601();
	Snapshot->SetStringField(TEXT("instanceId"), EditorInstanceId);
	Snapshot->SetStringField(TEXT("projectName"), FApp::GetProjectName());
	Snapshot->SetStringField(TEXT("projectFilePath"), FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath()));
	Snapshot->SetStringField(TEXT("projectDir"), FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()));
	Snapshot->SetStringField(TEXT("engineVersion"), FEngineVersion::Current().ToString());
	Snapshot->SetNumberField(TEXT("processId"), static_cast<int32>(FPlatformProcess::GetCurrentProcessId()));
	Snapshot->SetStringField(TEXT("remoteControlHost"), GetRemoteControlHost());
	Snapshot->SetNumberField(TEXT("remoteControlPort"), GetRemoteControlHttpPort());
	Snapshot->SetStringField(TEXT("lastSeenAt"), LastRegistryHeartbeat);
	Snapshot->SetStringField(TEXT("pluginVersion"), TEXT("UE5.4"));

	if (!FFileHelper::SaveStringToFile(SerializeRegistryJsonObject(Snapshot), *RegistryFilePath))
	{
		UE_LOG(LogBlueprintTools, Warning, TEXT("Failed to write BlueprintTools editor registry file: %s"), *RegistryFilePath);
	}
}

bool FBlueprintToolsModule::HandleRegistryHeartbeat(float DeltaTime)
{
	RefreshEditorRegistry();
	return true;
}

void FBlueprintToolsModule::RemoveEditorRegistryFile()
{
	if (!RegistryFilePath.IsEmpty())
	{
		IFileManager::Get().Delete(*RegistryFilePath, false, true);
	}
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FBlueprintToolsModule, BlueprintToolsUE54)
