#include "Debugger/StateTreeDebuggerBridge.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#if WITH_STATETREE_TRACE_DEBUGGER
#include "Debugger/StateTreeDebugger.h"
#include "Debugger/StateTreeDebuggerTypes.h"
#include "Debugger/StateTreeTraceTypes.h"
#include "StateTree.h"
#include "StateTreeModule.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogBPEStateTreeDebugger, Log, All);

// ============================================================
// Helpers
// ============================================================

static TSharedPtr<FJsonObject> MakeBridgeResult(bool bSuccess, const FString& Message = TEXT(""))
{
	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), bSuccess);
	Result->SetStringField(TEXT("operation"), TEXT("statetree_debugger"));
	if (!Message.IsEmpty())
	{
		Result->SetStringField(bSuccess ? TEXT("message") : TEXT("error"), Message);
	}
	return Result;
}

// ============================================================
// Public API
// ============================================================

TSharedPtr<FJsonObject> FStateTreeDebuggerBridge::Start(const FString& AssetPath)
{
#if WITH_STATETREE_TRACE_DEBUGGER
	if (Debugger.IsValid() && Debugger->IsAnalysisSessionActive())
	{
		return MakeBridgeResult(false, TEXT("Debugger session is already active. Call stop first."));
	}

	Debugger = MakeShared<FStateTreeDebugger>();

	// Optionally filter to a specific StateTree asset
	if (!AssetPath.IsEmpty())
	{
		UStateTree* Asset = LoadObject<UStateTree>(nullptr, *AssetPath);
		if (!Asset)
		{
			// Try content path
			const FString FullPath = AssetPath.EndsWith(TEXT(".") + FPackageName::GetAssetPackageExtension())
				? AssetPath
				: AssetPath + TEXT(".") + FPaths::GetBaseFilename(AssetPath);
			Asset = LoadObject<UStateTree>(nullptr, *FullPath);
		}
		if (Asset)
		{
			CachedFilterAsset = TStrongObjectPtr<UStateTree>(Asset);
			Debugger->SetAsset(Asset);
		}
		else
		{
			UE_LOG(LogBPEStateTreeDebugger, Warning,
				TEXT("StateTree asset not found at '%s' — recording ALL instances."), *AssetPath);
		}
	}

	const bool bStarted = Debugger->RequestAnalysisOfEditorSession();
	if (!bStarted)
	{
		Debugger.Reset();
		return MakeBridgeResult(false,
			TEXT("Failed to start trace analysis. Ensure PIE is running or a live trace session is available."));
	}

	TSharedPtr<FJsonObject> Result = MakeBridgeResult(true, TEXT("StateTree debugger started."));
	Result->SetBoolField(TEXT("recording"), true);
	Result->SetStringField(TEXT("assetFilter"), AssetPath.IsEmpty() ? TEXT("(all)") : AssetPath);
	return Result;

#else
	return MakeBridgeResult(false, TEXT("WITH_STATETREE_TRACE_DEBUGGER is not enabled in this build."));
#endif
}

TSharedPtr<FJsonObject> FStateTreeDebuggerBridge::Stop()
{
#if WITH_STATETREE_TRACE_DEBUGGER
	if (!Debugger.IsValid())
	{
		return MakeBridgeResult(false, TEXT("No active debugger session."));
	}

	if (Debugger->IsAnalysisSessionActive())
	{
		Debugger->StopSessionAnalysis();
	}

	IStateTreeModule& Module = IStateTreeModule::Get();
	if (Module.IsTracing())
	{
		Module.StopTraces();
	}

	Debugger.Reset();
	CachedFilterAsset.Reset();
	return MakeBridgeResult(true, TEXT("StateTree debugger stopped."));

#else
	return MakeBridgeResult(false, TEXT("WITH_STATETREE_TRACE_DEBUGGER is not enabled in this build."));
#endif
}

TSharedPtr<FJsonObject> FStateTreeDebuggerBridge::Read(const FString& PayloadJson)
{
#if WITH_STATETREE_TRACE_DEBUGGER
	if (!Debugger.IsValid() || !Debugger->IsAnalysisSessionActive())
	{
		return MakeBridgeResult(false, TEXT("No active debugger session. Call start first."));
	}

	// Parse optional payload
	FString FilterInstanceIdStr;
	int32 MaxEvents = 500;
	double ScrubTime = -1.0;

	if (!PayloadJson.IsEmpty())
	{
		TSharedPtr<FJsonObject> Payload;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (FJsonSerializer::Deserialize(Reader, Payload) && Payload.IsValid())
		{
			Payload->TryGetStringField(TEXT("instanceId"), FilterInstanceIdStr);
			Payload->TryGetNumberField(TEXT("maxEvents"), MaxEvents);
			double TempScrub = -1.0;
			if (Payload->TryGetNumberField(TEXT("scrubTime"), TempScrub))
			{
				ScrubTime = TempScrub;
			}
		}
	}

	// Set scrub time if requested
	if (ScrubTime >= 0.0)
	{
		Debugger->SetScrubTime(ScrubTime);
	}

	// Force sync to latest data
	Debugger->SyncToCurrentSessionDuration();

	// Get all instances
	TArray<UE::StateTreeDebugger::FInstanceDescriptor> Instances;
	Debugger->GetSessionInstances(Instances);

	TSharedPtr<FJsonObject> Result = MakeBridgeResult(true);
	Result->SetNumberField(TEXT("recordingDuration"), Debugger->GetRecordingDuration());
	Result->SetNumberField(TEXT("analysisDuration"), Debugger->GetAnalysisDuration());
	Result->SetNumberField(TEXT("scrubTime"), Debugger->GetScrubTime());
	Result->SetBoolField(TEXT("paused"), Debugger->IsAnalysisSessionPaused());

	// Serialize instances
	TArray<TSharedPtr<FJsonValue>> InstancesArray;
	for (const UE::StateTreeDebugger::FInstanceDescriptor& Inst : Instances)
	{
		if (!Inst.IsValid())
		{
			continue;
		}

		TSharedPtr<FJsonObject> InstObj = MakeShared<FJsonObject>();
		InstObj->SetStringField(TEXT("id"), FString::Printf(TEXT("%u_%u"), Inst.Id.Id, Inst.Id.SerialNumber));
		InstObj->SetStringField(TEXT("name"), Inst.Name);
		InstObj->SetStringField(TEXT("displayName"), Debugger->GetInstanceName(Inst.Id).ToString());
		InstObj->SetStringField(TEXT("description"), Debugger->GetInstanceDescription(Inst.Id).ToString());
		InstObj->SetBoolField(TEXT("isActive"), Debugger->IsActiveInstance(Debugger->GetScrubTime(), Inst.Id));

		if (Inst.StateTree.IsValid())
		{
			InstObj->SetStringField(TEXT("stateTreeAsset"), Inst.StateTree->GetPathName());
		}

		if (Inst.Lifetime.HasLowerBound())
		{
			InstObj->SetNumberField(TEXT("lifetimeStart"), Inst.Lifetime.GetLowerBoundValue());
		}
		if (Inst.Lifetime.HasUpperBound())
		{
			InstObj->SetNumberField(TEXT("lifetimeEnd"), Inst.Lifetime.GetUpperBoundValue());
		}

		// If filtering to a specific instance, also include its events
		const FString InstIdStr = FString::Printf(TEXT("%u_%u"), Inst.Id.Id, Inst.Id.SerialNumber);
		if (!FilterInstanceIdStr.IsEmpty() && FilterInstanceIdStr == InstIdStr)
		{
			TSharedPtr<FJsonObject> EventsObj = SerializeInstanceEvents(Inst.Id, MaxEvents);
			if (EventsObj.IsValid())
			{
				InstObj->SetObjectField(TEXT("events"), EventsObj);
			}
		}

		InstancesArray.Add(MakeShared<FJsonValueObject>(InstObj));
	}

	Result->SetArrayField(TEXT("instances"), InstancesArray);
	Result->SetNumberField(TEXT("instanceCount"), static_cast<double>(InstancesArray.Num()));

	return Result;

#else
	return MakeBridgeResult(false, TEXT("WITH_STATETREE_TRACE_DEBUGGER is not enabled in this build."));
#endif
}

bool FStateTreeDebuggerBridge::IsActive() const
{
#if WITH_STATETREE_TRACE_DEBUGGER
	return Debugger.IsValid() && Debugger->IsAnalysisSessionActive();
#else
	return false;
#endif
}

void FStateTreeDebuggerBridge::Shutdown()
{
#if WITH_STATETREE_TRACE_DEBUGGER
	if (Debugger.IsValid())
	{
		if (Debugger->IsAnalysisSessionActive())
		{
			Debugger->StopSessionAnalysis();
		}
		Debugger.Reset();
	}
	CachedFilterAsset.Reset();
#endif
}

// ============================================================
// Serialization (private, under WITH_STATETREE_TRACE_DEBUGGER)
// ============================================================

#if WITH_STATETREE_TRACE_DEBUGGER

FString FStateTreeDebuggerBridge::StateHandleToName(const UStateTree* StateTreeAsset, FStateTreeStateHandle Handle)
{
	if (!StateTreeAsset || !Handle.IsValid())
	{
		return TEXT("(invalid)");
	}

	const FCompactStateTreeState* State = StateTreeAsset->GetStateFromHandle(Handle);
	if (!State)
	{
		return FString::Printf(TEXT("Handle_%d"), Handle.Index);
	}

	return State->Name.ToString();
}

TSharedPtr<FJsonObject> FStateTreeDebuggerBridge::SerializeInstanceEvents(FStateTreeInstanceDebugId InstanceId, int32 MaxEvents) const
{
	if (!Debugger.IsValid())
	{
		return nullptr;
	}

	const UE::StateTreeDebugger::FInstanceEventCollection& Collection = Debugger->GetEventCollection(InstanceId);
	if (!Collection.IsValid())
	{
		return nullptr;
	}

	const UStateTree* Asset = Debugger->GetAsset();

	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetNumberField(TEXT("totalEvents"), static_cast<double>(Collection.Events.Num()));

	// Serialize events (last MaxEvents)
	const int32 StartIdx = FMath::Max(0, Collection.Events.Num() - MaxEvents);
	TArray<TSharedPtr<FJsonValue>> EventsArray;

	for (int32 i = StartIdx; i < Collection.Events.Num(); ++i)
	{
		TSharedPtr<FJsonObject> EventObj = SerializeEvent(Collection.Events[i], Asset);
		if (EventObj.IsValid())
		{
			EventsArray.Add(MakeShared<FJsonValueObject>(EventObj));
		}
	}

	Result->SetArrayField(TEXT("events"), EventsArray);
	Result->SetNumberField(TEXT("returnedEvents"), static_cast<double>(EventsArray.Num()));
	Result->SetNumberField(TEXT("skippedEvents"), static_cast<double>(StartIdx));

	// Active states changes
	TArray<TSharedPtr<FJsonValue>> ActiveChanges;
	for (const auto& ChangePair : Collection.ActiveStatesChanges)
	{
		if (ChangePair.EventIndex < Collection.Events.Num())
		{
			const FStateTreeTraceEventVariantType& ChangeEvent = Collection.Events[ChangePair.EventIndex];
			if (const FStateTreeTraceActiveStatesEvent* ActiveEvent = ChangeEvent.TryGet<FStateTreeTraceActiveStatesEvent>())
			{
				TSharedPtr<FJsonObject> ChangeObj = MakeShared<FJsonObject>();
				ChangeObj->SetNumberField(TEXT("eventIdx"), static_cast<double>(ChangePair.EventIndex));
				ChangeObj->SetNumberField(TEXT("worldTime"), ActiveEvent->RecordingWorldTime);

				TArray<TSharedPtr<FJsonValue>> StatesArray;
				for (const auto& AssetStates : ActiveEvent->ActiveStates.PerAssetStates)
				{
					const UStateTree* EventAsset = AssetStates.WeakStateTree.Get();
					for (const FStateTreeStateHandle& Handle : AssetStates.ActiveStates)
					{
						StatesArray.Add(MakeShared<FJsonValueString>(StateHandleToName(EventAsset, Handle)));
					}
				}
				ChangeObj->SetArrayField(TEXT("activeStates"), StatesArray);
				ActiveChanges.Add(MakeShared<FJsonValueObject>(ChangeObj));
			}
		}
	}
	Result->SetArrayField(TEXT("activeStatesChanges"), ActiveChanges);

	return Result;
}

TSharedPtr<FJsonObject> FStateTreeDebuggerBridge::SerializeEvent(
	const FStateTreeTraceEventVariantType& Event,
	const UStateTree* StateTreeAsset)
{
	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	// Visitor pattern for TVariant
	if (const FStateTreeTracePhaseEvent* Phase = Event.TryGet<FStateTreeTracePhaseEvent>())
	{
		Obj->SetStringField(TEXT("type"), TEXT("phase"));
		Obj->SetNumberField(TEXT("worldTime"), Phase->RecordingWorldTime);
		Obj->SetStringField(TEXT("eventType"), StaticEnum<EStateTreeTraceEventType>()->GetNameStringByValue(static_cast<int64>(Phase->EventType)));
		Obj->SetStringField(TEXT("phase"), StaticEnum<EStateTreeUpdatePhase>()->GetNameStringByValue(static_cast<int64>(Phase->Phase)));
		Obj->SetStringField(TEXT("state"), StateHandleToName(StateTreeAsset, Phase->StateHandle));
	}
	else if (const FStateTreeTraceStateEvent* State = Event.TryGet<FStateTreeTraceStateEvent>())
	{
		Obj->SetStringField(TEXT("type"), TEXT("state"));
		Obj->SetNumberField(TEXT("worldTime"), State->RecordingWorldTime);
		Obj->SetStringField(TEXT("eventType"), StaticEnum<EStateTreeTraceEventType>()->GetNameStringByValue(static_cast<int64>(State->EventType)));
		Obj->SetStringField(TEXT("state"), StateHandleToName(StateTreeAsset, State->GetStateHandle()));
	}
	else if (const FStateTreeTraceTaskEvent* Task = Event.TryGet<FStateTreeTraceTaskEvent>())
	{
		Obj->SetStringField(TEXT("type"), TEXT("task"));
		Obj->SetNumberField(TEXT("worldTime"), Task->RecordingWorldTime);
		Obj->SetStringField(TEXT("eventType"), StaticEnum<EStateTreeTraceEventType>()->GetNameStringByValue(static_cast<int64>(Task->EventType)));
		Obj->SetStringField(TEXT("typePath"), Task->TypePath);
		Obj->SetStringField(TEXT("status"), StaticEnum<EStateTreeRunStatus>()->GetNameStringByValue(static_cast<int64>(Task->Status)));
		if (!Task->InstanceDataAsText.IsEmpty())
		{
			Obj->SetStringField(TEXT("instanceData"), Task->InstanceDataAsText);
		}
	}
	else if (const FStateTreeTraceTransitionEvent* Transition = Event.TryGet<FStateTreeTraceTransitionEvent>())
	{
		Obj->SetStringField(TEXT("type"), TEXT("transition"));
		Obj->SetNumberField(TEXT("worldTime"), Transition->RecordingWorldTime);
		Obj->SetStringField(TEXT("eventType"), StaticEnum<EStateTreeTraceEventType>()->GetNameStringByValue(static_cast<int64>(Transition->EventType)));
	}
	else if (const FStateTreeTraceConditionEvent* Condition = Event.TryGet<FStateTreeTraceConditionEvent>())
	{
		Obj->SetStringField(TEXT("type"), TEXT("condition"));
		Obj->SetNumberField(TEXT("worldTime"), Condition->RecordingWorldTime);
		Obj->SetStringField(TEXT("eventType"), StaticEnum<EStateTreeTraceEventType>()->GetNameStringByValue(static_cast<int64>(Condition->EventType)));
		Obj->SetStringField(TEXT("typePath"), Condition->TypePath);
		if (!Condition->InstanceDataAsText.IsEmpty())
		{
			Obj->SetStringField(TEXT("instanceData"), Condition->InstanceDataAsText);
		}
	}
	else if (const FStateTreeTraceActiveStatesEvent* ActiveStates = Event.TryGet<FStateTreeTraceActiveStatesEvent>())
	{
		Obj->SetStringField(TEXT("type"), TEXT("activeStates"));
		Obj->SetNumberField(TEXT("worldTime"), ActiveStates->RecordingWorldTime);

		TArray<TSharedPtr<FJsonValue>> StatesArray;
		for (const auto& AssetStates : ActiveStates->ActiveStates.PerAssetStates)
		{
			const UStateTree* EventAsset = AssetStates.WeakStateTree.Get();
			for (const FStateTreeStateHandle& Handle : AssetStates.ActiveStates)
			{
				StatesArray.Add(MakeShared<FJsonValueString>(StateHandleToName(EventAsset, Handle)));
			}
		}
		Obj->SetArrayField(TEXT("activeStates"), StatesArray);
	}
	else if (const FStateTreeTraceLogEvent* Log = Event.TryGet<FStateTreeTraceLogEvent>())
	{
		Obj->SetStringField(TEXT("type"), TEXT("log"));
		Obj->SetNumberField(TEXT("worldTime"), Log->RecordingWorldTime);
		Obj->SetStringField(TEXT("message"), Log->Message);
	}
	else
	{
		// Other event types (EvaluatorEvent, PropertyEvent, InstanceFrameEvent)
		Obj->SetStringField(TEXT("type"), TEXT("other"));
	}

	return Obj;
}

#endif // WITH_STATETREE_TRACE_DEBUGGER
