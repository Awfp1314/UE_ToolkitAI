#include "BlueprintExtractorModule.h"
#include "ContentBrowserExtension.h"
#include "Diagnostics/BlueprintExtractorLogAccess.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"
#include "Misc/App.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "RemoteControlSettings.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

DEFINE_LOG_CATEGORY(LogBlueprintExtractor);

#define LOCTEXT_NAMESPACE "FBlueprintExtractorModule"

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

void FBlueprintExtractorModule::StartupModule()
{
	FContentBrowserExtension::RegisterMenuExtension(ContentBrowserExtenderDelegateHandle);
	EditorInstanceId = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower);
	RegistryFilePath = FPaths::Combine(GetEditorRegistryDirectory(), FString::Printf(TEXT("%s.json"), *EditorInstanceId));
	RefreshEditorRegistry();
	BlueprintExtractorLogAccess::Startup();
	RegistryTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateRaw(this, &FBlueprintExtractorModule::HandleRegistryHeartbeat),
		2.0f);
	UE_LOG(LogBlueprintExtractor, Log, TEXT("BlueprintExtractor module started"));
}

void FBlueprintExtractorModule::ShutdownModule()
{
	if (RegistryTickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(RegistryTickerHandle);
		RegistryTickerHandle.Reset();
	}
	BlueprintExtractorLogAccess::Shutdown();
	RemoveEditorRegistryFile();
	FContentBrowserExtension::UnregisterMenuExtension(ContentBrowserExtenderDelegateHandle);
}

FString FBlueprintExtractorModule::GetEngineRoot() const
{
	const FString EngineDir = FPaths::ConvertRelativePathToFull(FPaths::EngineDir());
	return FPaths::ConvertRelativePathToFull(FPaths::GetPath(FPaths::GetPath(EngineDir)));
}

FString FBlueprintExtractorModule::GetEngineVersion() const
{
	return FEngineVersion::Current().ToString();
}

FString FBlueprintExtractorModule::GetEditorTarget() const
{
	return FString::Printf(TEXT("%sEditor"), FApp::GetProjectName());
}

int32 FBlueprintExtractorModule::GetEditorProcessId() const
{
	return static_cast<int32>(FPlatformProcess::GetCurrentProcessId());
}

FString FBlueprintExtractorModule::GetRemoteControlHost() const
{
	return TEXT("127.0.0.1");
}

int32 FBlueprintExtractorModule::GetRemoteControlHttpPort() const
{
	return static_cast<int32>(GetDefault<URemoteControlSettings>()->RemoteControlHttpServerPort);
}

FString FBlueprintExtractorModule::GetEditorRegistryDirectory() const
{
	const FString OverrideDir = FPlatformMisc::GetEnvironmentVariable(TEXT("BLUEPRINT_EXTRACTOR_EDITOR_REGISTRY_DIR"));
	if (!OverrideDir.IsEmpty())
	{
		return FPaths::ConvertRelativePathToFull(OverrideDir);
	}

	return FPaths::Combine(
		FPaths::ConvertRelativePathToFull(FPlatformProcess::UserTempDir()),
		TEXT("BlueprintExtractor"),
		TEXT("EditorRegistry"));
}

void FBlueprintExtractorModule::RefreshEditorRegistry()
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
	Snapshot->SetStringField(TEXT("engineRoot"), GetEngineRoot());
	Snapshot->SetStringField(TEXT("engineVersion"), GetEngineVersion());
	Snapshot->SetStringField(TEXT("editorTarget"), GetEditorTarget());
	Snapshot->SetNumberField(TEXT("processId"), GetEditorProcessId());
	Snapshot->SetStringField(TEXT("remoteControlHost"), GetRemoteControlHost());
	Snapshot->SetNumberField(TEXT("remoteControlPort"), GetRemoteControlHttpPort());
	Snapshot->SetStringField(TEXT("lastSeenAt"), LastRegistryHeartbeat);

	if (!FFileHelper::SaveStringToFile(SerializeRegistryJsonObject(Snapshot), *RegistryFilePath))
	{
		UE_LOG(LogBlueprintExtractor, Warning, TEXT("Failed to write BlueprintExtractor editor registry file: %s"), *RegistryFilePath);
	}
}

bool FBlueprintExtractorModule::HandleRegistryHeartbeat(float DeltaTime)
{
	RefreshEditorRegistry();
	return true;
}

void FBlueprintExtractorModule::RemoveEditorRegistryFile()
{
	if (!RegistryFilePath.IsEmpty())
	{
		IFileManager::Get().Delete(*RegistryFilePath, false, true);
	}
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FBlueprintExtractorModule, BlueprintExtractor)
