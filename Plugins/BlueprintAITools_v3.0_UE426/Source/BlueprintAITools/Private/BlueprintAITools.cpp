// Copyright Epic Games, Inc. All Rights Reserved.

#include "BlueprintAITools.h"

// UE5 重命名了 Ticker：FTicker → FTSTicker
#if ENGINE_MAJOR_VERSION >= 5
#include "Containers/Ticker.h"
#else
#include "Containers/Ticker.h"
#endif

#if WITH_EDITOR
#include "IPythonScriptPlugin.h"
#endif

#define LOCTEXT_NAMESPACE "FBlueprintAIToolsModule"

void FBlueprintAIToolsModule::StartupModule()
{
	// 在编辑器模式下自动启动 RPC 服务器
#if WITH_EDITOR
	// 延迟启动，确保 Python 插件已加载
	auto TickerDelegate = FTickerDelegate::CreateLambda([](float DeltaTime) -> bool
	{
		// 获取 Python 脚本插件
		IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
		if (PythonPlugin)
		{
			// 执行 Python 脚本启动 RPC 服务器
			FString PythonScript = TEXT(
				"try:\n"
				"    import ue_rpc_server\n"
				"    ue_rpc_server.start_rpc_server()\n"
				"    import unreal\n"
				"    unreal.log('[BlueprintAITools] RPC 服务器已自动启动')\n"
				"except Exception as e:\n"
				"    import unreal\n"
				"    unreal.log_error('[BlueprintAITools] 自动启动 RPC 服务器失败: {}'.format(e))\n"
			);
			
			PythonPlugin->ExecPythonCommand(*PythonScript);
			
			UE_LOG(LogTemp, Log, TEXT("[BlueprintAITools] 插件已加载，RPC 服务器已自动启动"));
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("[BlueprintAITools] Python 插件未找到，无法自动启动 RPC 服务器"));
		}
		
		// 返回 false 表示只执行一次
		return false;
	});

	// UE5 用 FTSTicker，UE4 用 FTicker
#if ENGINE_MAJOR_VERSION >= 5
	FTSTicker::GetCoreTicker().AddTicker(TickerDelegate, 2.0f);
#else
	FTicker::GetCoreTicker().AddTicker(TickerDelegate, 2.0f);
#endif

#endif // WITH_EDITOR
}

void FBlueprintAIToolsModule::ShutdownModule()
{
	// This function may be called during shutdown to clean up your module.  For modules that support dynamic reloading,
	// we call this function before unloading the module.
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FBlueprintAIToolsModule, BlueprintAITools)