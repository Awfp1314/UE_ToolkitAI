#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/StrongObjectPtr.h"

#if WITH_STATETREE_TRACE_DEBUGGER
#include "Debugger/StateTreeDebugger.h"
#endif

class UStateTree;

/**
 * Bridge between BlueprintExtractor subsystem and UE StateTree Debugger.
 * Wraps FStateTreeDebugger lifecycle, trace recording, and JSON serialization of events.
 * All public methods return TSharedPtr<FJsonObject> suitable for Remote Control responses.
 *
 * Requires WITH_STATETREE_TRACE_DEBUGGER (Desktop + Editor builds only).
 */
class FStateTreeDebuggerBridge
{
public:
	/** Start recording StateTree traces. Optionally filter to a specific StateTree asset. */
	TSharedPtr<FJsonObject> Start(const FString& AssetPath);

	/** Stop recording and discard the debugger session. */
	TSharedPtr<FJsonObject> Stop();

	/** Read current debugger state: instances, events, active states.
	 *  PayloadJson can contain:
	 *    instanceId (string) — filter to one instance
	 *    maxEvents (int)     — limit event count per instance (default 500)
	 *    scrubTime (double)  — set scrub position before reading
	 */
	TSharedPtr<FJsonObject> Read(const FString& PayloadJson);

	/** Returns true if a debugger session is currently active. */
	bool IsActive() const;

	/** Cleanup — call from subsystem destructor. */
	void Shutdown();

private:
#if WITH_STATETREE_TRACE_DEBUGGER
	TSharedPtr<FStateTreeDebugger> Debugger;

	/** Strong reference to the filtered StateTree asset to prevent GC.
	 *  FStateTreeDebugger::SetAsset stores a TWeakObjectPtr — without this strong ref
	 *  the asset can be collected between Start() and Read(), causing a check() crash
	 *  in FStateTreeDebugger::AddEvents. */
	TStrongObjectPtr<UStateTree> CachedFilterAsset;

	TSharedPtr<FJsonObject> SerializeInstances() const;
	TSharedPtr<FJsonObject> SerializeInstanceEvents(FStateTreeInstanceDebugId InstanceId, int32 MaxEvents) const;
	static TSharedPtr<FJsonObject> SerializeEvent(const FStateTreeTraceEventVariantType& Event, const UStateTree* StateTreeAsset);
	static FString StateHandleToName(const UStateTree* StateTreeAsset, FStateTreeStateHandle Handle);
#endif
};
