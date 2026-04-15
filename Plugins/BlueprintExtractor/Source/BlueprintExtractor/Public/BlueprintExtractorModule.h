#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Modules/ModuleManager.h"

DECLARE_LOG_CATEGORY_EXTERN(LogBlueprintExtractor, Log, All);

class FBlueprintExtractorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

	const FString& GetEditorInstanceId() const { return EditorInstanceId; }
	FString GetEngineRoot() const;
	FString GetEngineVersion() const;
	FString GetEditorTarget() const;
	int32 GetEditorProcessId() const;
	FString GetRemoteControlHost() const;
	int32 GetRemoteControlHttpPort() const;
	FString GetLastRegistryHeartbeat() const { return LastRegistryHeartbeat; }
	FString GetRegistryFilePath() const { return RegistryFilePath; }

private:
	FString GetEditorRegistryDirectory() const;
	void RefreshEditorRegistry();
	bool HandleRegistryHeartbeat(float DeltaTime);
	void RemoveEditorRegistryFile();

	FString EditorInstanceId;
	FString RegistryFilePath;
	FString LastRegistryHeartbeat;
	FDelegateHandle ContentBrowserExtenderDelegateHandle;
	FTSTicker::FDelegateHandle RegistryTickerHandle;
};
