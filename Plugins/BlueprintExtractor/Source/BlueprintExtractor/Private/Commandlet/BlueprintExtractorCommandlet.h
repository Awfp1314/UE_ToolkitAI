#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"
#include "BlueprintExtractorCommandlet.generated.h"

class UBlueprintExtractorSubsystem;

/**
 * Commandlet that exposes UBlueprintExtractorSubsystem methods via stdin/stdout JSON-RPC.
 * Launched by the MCP CommandletAdapter: UnrealEditor-Cmd <project> -run=BlueprintExtractor -stdin
 *
 * Protocol:
 *   stdin  → {"jsonrpc":"2.0","id":N,"method":"MethodName","params":{...}}\n
 *   stdout ← {"jsonrpc":"2.0","id":N,"result":{...}}\n   or   {"jsonrpc":"2.0","id":N,"error":"..."}\n
 *
 * Method dispatch uses UE Reflection — any UFUNCTION on UBlueprintExtractorSubsystem is callable.
 */
UCLASS()
class UBlueprintExtractorCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UBlueprintExtractorCommandlet();
	virtual int32 Main(const FString& Params) override;

private:
	static void WriteStdout(const FString& Line);
	static FString ProcessRequest(UBlueprintExtractorSubsystem* Subsystem, const FString& RequestJson);
	static FString InvokeViaReflection(UBlueprintExtractorSubsystem* Subsystem, const FString& MethodName, const TSharedPtr<FJsonObject>& Params);
	static FString MakeJsonRpcResult(int64 Id, const FString& ResultJson);
	static FString MakeJsonRpcError(int64 Id, const FString& Message);
};
