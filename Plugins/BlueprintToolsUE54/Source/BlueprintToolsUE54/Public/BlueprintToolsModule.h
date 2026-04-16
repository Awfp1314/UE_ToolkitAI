#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Modules/ModuleManager.h"

DECLARE_LOG_CATEGORY_EXTERN(LogBlueprintTools, Log, All);

class FBlueprintToolsModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

	const FString& GetEditorInstanceId() const { return EditorInstanceId; }
	FString GetRemoteControlHost() const;
	int32 GetRemoteControlHttpPort() const;

private:
	FString GetEditorRegistryDirectory() const;
	void RefreshEditorRegistry();
	bool HandleRegistryHeartbeat(float DeltaTime);
	void RemoveEditorRegistryFile();

	FString EditorInstanceId;
	FString RegistryFilePath;
	FString LastRegistryHeartbeat;
	FTSTicker::FDelegateHandle RegistryTickerHandle;
};
