#include "Extractors/StateTreeExtractor.h"
#include "BlueprintExtractorModule.h"
#include "BlueprintExtractorVersion.h"
#include "BlueprintJsonSchema.h"
#include "StateTree.h"
#include "StateTreeEditorData.h"
#include "StateTreeEditorPropertyBindings.h"
#include "StateTreePropertyBindings.h"
#include "StateTreeState.h"
#include "StateTreeTypes.h"
#include "StructUtils/InstancedStruct.h"

TSharedPtr<FJsonObject> FStateTreeExtractor::Extract(const UStateTree* StateTree)
{
	if (!ensureMsgf(StateTree, TEXT("StateTreeExtractor: null StateTree")))
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> STObj = MakeShared<FJsonObject>();
	STObj->SetStringField(TEXT("assetPath"), StateTree->GetPathName());
	STObj->SetStringField(TEXT("assetName"), StateTree->GetName());

	// Schema
	if (const UStateTreeSchema* Schema = StateTree->GetSchema())
	{
		STObj->SetStringField(TEXT("schema"), Schema->GetClass()->GetPathName());
		STObj->SetStringField(TEXT("schemaName"), Schema->GetClass()->GetName());
	}

#if WITH_EDITORONLY_DATA
	const UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData);
	if (!EditorData)
	{
		UE_LOG(LogBlueprintExtractor, Warning, TEXT("StateTree '%s' has no editor data"), *StateTree->GetName());
		Root->SetObjectField(TEXT("stateTree"), STObj);
		return Root;
	}

	// Evaluators
	TArray<TSharedPtr<FJsonValue>> Evaluators;
	for (const FStateTreeEditorNode& Evaluator : EditorData->Evaluators)
	{
		TSharedPtr<FJsonObject> EvalObj = ExtractEditorNode(Evaluator);
		if (EvalObj)
		{
			Evaluators.Add(MakeShared<FJsonValueObject>(EvalObj));
		}
	}
	STObj->SetArrayField(TEXT("evaluators"), Evaluators);

	// Global Tasks
	TArray<TSharedPtr<FJsonValue>> GlobalTasks;
	for (const FStateTreeEditorNode& Task : EditorData->GlobalTasks)
	{
		TSharedPtr<FJsonObject> TaskObj = ExtractEditorNode(Task);
		if (TaskObj)
		{
			GlobalTasks.Add(MakeShared<FJsonValueObject>(TaskObj));
		}
	}
	STObj->SetArrayField(TEXT("globalTasks"), GlobalTasks);

	// States (SubTrees are the root-level states)
	TArray<TSharedPtr<FJsonValue>> States;
	for (const UStateTreeState* State : EditorData->SubTrees)
	{
		if (State)
		{
			TSharedPtr<FJsonObject> StateObj = ExtractState(State);
			if (StateObj)
			{
				States.Add(MakeShared<FJsonValueObject>(StateObj));
			}
		}
	}
	STObj->SetArrayField(TEXT("states"), States);

	// Property bindings
	TSharedPtr<FJsonObject> BindingsObj = ExtractBindings(EditorData);
	if (BindingsObj)
	{
		STObj->SetObjectField(TEXT("bindings"), BindingsObj);
	}

#endif // WITH_EDITORONLY_DATA

	Root->SetObjectField(TEXT("stateTree"), STObj);
	return Root;
}

TSharedPtr<FJsonObject> FStateTreeExtractor::ExtractState(const UStateTreeState* State)
{
	if (!State)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	Obj->SetStringField(TEXT("name"), State->Name.ToString());
	Obj->SetStringField(TEXT("id"), State->ID.ToString());
	Obj->SetStringField(TEXT("statePath"), State->GetPath());
	Obj->SetBoolField(TEXT("enabled"), State->bEnabled);

	if (!State->Description.IsEmpty())
	{
		Obj->SetStringField(TEXT("description"), State->Description);
	}

	if (State->Tag.IsValid())
	{
		Obj->SetStringField(TEXT("tag"), State->Tag.ToString());
	}

	// State type
	if (const UEnum* TypeEnum = StaticEnum<EStateTreeStateType>())
	{
		Obj->SetStringField(TEXT("type"), TypeEnum->GetNameStringByValue(static_cast<int64>(State->Type)));
	}

	// Selection behavior
	if (const UEnum* SelectionEnum = StaticEnum<EStateTreeStateSelectionBehavior>())
	{
		Obj->SetStringField(TEXT("selectionBehavior"), SelectionEnum->GetNameStringByValue(static_cast<int64>(State->SelectionBehavior)));
	}

	// Linked subtree
	if (State->Type == EStateTreeStateType::Linked)
	{
		TSharedPtr<FJsonObject> LinkObj = MakeShared<FJsonObject>();
		LinkObj->SetStringField(TEXT("linkedStateId"), State->LinkedSubtree.ID.ToString());
		LinkObj->SetStringField(TEXT("linkedStateName"), State->LinkedSubtree.Name.ToString());
		Obj->SetObjectField(TEXT("linkedSubtree"), LinkObj);
	}

	// Linked asset
	if (State->Type == EStateTreeStateType::LinkedAsset && State->LinkedAsset)
	{
		Obj->SetStringField(TEXT("linkedAsset"), FBlueprintJsonSchema::GetObjectPathString(State->LinkedAsset));
	}

	// Tasks
	TArray<TSharedPtr<FJsonValue>> Tasks;
	for (const FStateTreeEditorNode& Task : State->Tasks)
	{
		TSharedPtr<FJsonObject> TaskObj = ExtractEditorNode(Task);
		if (TaskObj)
		{
			Tasks.Add(MakeShared<FJsonValueObject>(TaskObj));
		}
	}
	Obj->SetArrayField(TEXT("tasks"), Tasks);

	// Single task (used when schema calls for single task per state)
	if (State->SingleTask.Node.IsValid())
	{
		Obj->SetObjectField(TEXT("singleTask"), ExtractEditorNode(State->SingleTask));
	}

	// Enter conditions
	TArray<TSharedPtr<FJsonValue>> EnterConditions;
	for (const FStateTreeEditorNode& Condition : State->EnterConditions)
	{
		TSharedPtr<FJsonObject> CondObj = ExtractEditorNode(Condition);
		if (CondObj)
		{
			EnterConditions.Add(MakeShared<FJsonValueObject>(CondObj));
		}
	}
	if (EnterConditions.Num() > 0)
	{
		Obj->SetArrayField(TEXT("enterConditions"), EnterConditions);
	}

	// Considerations (utility-based selection)
	TArray<TSharedPtr<FJsonValue>> Considerations;
	for (const FStateTreeEditorNode& Consideration : State->Considerations)
	{
		TSharedPtr<FJsonObject> ConsObj = ExtractEditorNode(Consideration);
		if (ConsObj)
		{
			Considerations.Add(MakeShared<FJsonValueObject>(ConsObj));
		}
	}
	if (Considerations.Num() > 0)
	{
		Obj->SetArrayField(TEXT("considerations"), Considerations);
	}

	// Required event to enter
	if (State->bHasRequiredEventToEnter && State->RequiredEventToEnter.IsValid())
	{
		TSharedPtr<FJsonObject> EventObj = MakeShared<FJsonObject>();
		EventObj->SetStringField(TEXT("tag"), State->RequiredEventToEnter.Tag.ToString());
		if (State->RequiredEventToEnter.PayloadStruct)
		{
			EventObj->SetStringField(TEXT("payloadStruct"), State->RequiredEventToEnter.PayloadStruct->GetPathName());
		}
		EventObj->SetBoolField(TEXT("consumeOnSelect"), State->RequiredEventToEnter.bConsumeEventOnSelect);
		Obj->SetObjectField(TEXT("requiredEventToEnter"), EventObj);
	}

	// Transitions
	TArray<TSharedPtr<FJsonValue>> Transitions;
	for (const FStateTreeTransition& Transition : State->Transitions)
	{
		TSharedPtr<FJsonObject> TransObj = ExtractTransition(Transition);
		if (TransObj)
		{
			Transitions.Add(MakeShared<FJsonValueObject>(TransObj));
		}
	}
	if (Transitions.Num() > 0)
	{
		Obj->SetArrayField(TEXT("transitions"), Transitions);
	}

	// Children
	TArray<TSharedPtr<FJsonValue>> Children;
	for (const UStateTreeState* Child : State->Children)
	{
		if (Child)
		{
			TSharedPtr<FJsonObject> ChildObj = ExtractState(Child);
			if (ChildObj)
			{
				Children.Add(MakeShared<FJsonValueObject>(ChildObj));
			}
		}
	}
	if (Children.Num() > 0)
	{
		Obj->SetArrayField(TEXT("children"), Children);
	}

	return Obj;
}

TSharedPtr<FJsonObject> FStateTreeExtractor::ExtractEditorNode(const FStateTreeEditorNode& EditorNode)
{
	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	Obj->SetStringField(TEXT("id"), EditorNode.ID.ToString());

	// Expression operand (And/Or for conditions)
	if (const UEnum* OperandEnum = StaticEnum<EStateTreeExpressionOperand>())
	{
		Obj->SetStringField(TEXT("expressionOperand"), OperandEnum->GetNameStringByValue(static_cast<int64>(EditorNode.ExpressionOperand)));
	}
	Obj->SetNumberField(TEXT("expressionIndent"), EditorNode.ExpressionIndent);

	// Node struct (the task/condition/evaluator definition)
	if (EditorNode.Node.IsValid())
	{
		const UScriptStruct* NodeStruct = EditorNode.Node.GetScriptStruct();
		if (NodeStruct)
		{
			Obj->SetStringField(TEXT("nodeStructType"), NodeStruct->GetPathName());
			Obj->SetStringField(TEXT("nodeStructName"), NodeStruct->GetName());

			const uint8* NodeMemory = EditorNode.Node.GetMemory();
			if (NodeMemory)
			{
				TSharedPtr<FJsonObject> NodeProps = ExtractStructProperties(NodeStruct, NodeMemory);
				if (NodeProps && NodeProps->Values.Num() > 0)
				{
					Obj->SetObjectField(TEXT("nodeProperties"), NodeProps);
				}
			}
		}
	}

	// Instance data struct
	if (EditorNode.Instance.IsValid())
	{
		const UScriptStruct* InstanceStruct = EditorNode.Instance.GetScriptStruct();
		if (InstanceStruct)
		{
			Obj->SetStringField(TEXT("instanceStructType"), InstanceStruct->GetPathName());
			Obj->SetStringField(TEXT("instanceStructName"), InstanceStruct->GetName());

			const uint8* InstanceMemory = EditorNode.Instance.GetMemory();
			if (InstanceMemory)
			{
				TSharedPtr<FJsonObject> InstanceProps = ExtractStructProperties(InstanceStruct, InstanceMemory);
				if (InstanceProps && InstanceProps->Values.Num() > 0)
				{
					Obj->SetObjectField(TEXT("instanceProperties"), InstanceProps);
				}
			}
		}
	}

	// Instance object (for Blueprint-based tasks/conditions)
	if (EditorNode.InstanceObject)
	{
		Obj->SetStringField(TEXT("instanceObjectPath"), FBlueprintJsonSchema::GetObjectPathString(EditorNode.InstanceObject));
		Obj->SetStringField(TEXT("instanceObjectClass"), EditorNode.InstanceObject->GetClass()->GetPathName());
	}

	// Node name
	FName NodeName = EditorNode.GetName();
	if (!NodeName.IsNone())
	{
		Obj->SetStringField(TEXT("name"), NodeName.ToString());
	}

	return Obj;
}

TSharedPtr<FJsonObject> FStateTreeExtractor::ExtractTransition(const FStateTreeTransition& Transition)
{
	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	Obj->SetStringField(TEXT("id"), Transition.ID.ToString());
	Obj->SetBoolField(TEXT("enabled"), Transition.bTransitionEnabled);

	// Trigger
	if (const UEnum* TriggerEnum = StaticEnum<EStateTreeTransitionTrigger>())
	{
		Obj->SetStringField(TEXT("trigger"), TriggerEnum->GetNameStringByValue(static_cast<int64>(Transition.Trigger)));
	}

	// Priority
	if (const UEnum* PriorityEnum = StaticEnum<EStateTreeTransitionPriority>())
	{
		Obj->SetStringField(TEXT("priority"), PriorityEnum->GetNameStringByValue(static_cast<int64>(Transition.Priority)));
	}

	// Target state
	TSharedPtr<FJsonObject> TargetObj = MakeShared<FJsonObject>();
	TargetObj->SetStringField(TEXT("stateId"), Transition.State.ID.ToString());
	TargetObj->SetStringField(TEXT("stateName"), Transition.State.Name.ToString());
	if (const UEnum* LinkEnum = StaticEnum<EStateTreeTransitionType>())
	{
		TargetObj->SetStringField(TEXT("linkType"), LinkEnum->GetNameStringByValue(static_cast<int64>(Transition.State.LinkType)));
	}
	Obj->SetObjectField(TEXT("targetState"), TargetObj);

	// Required event
	if (Transition.RequiredEvent.IsValid())
	{
		TSharedPtr<FJsonObject> EventObj = MakeShared<FJsonObject>();
		EventObj->SetStringField(TEXT("tag"), Transition.RequiredEvent.Tag.ToString());
		if (Transition.RequiredEvent.PayloadStruct)
		{
			EventObj->SetStringField(TEXT("payloadStruct"), Transition.RequiredEvent.PayloadStruct->GetPathName());
		}
		EventObj->SetBoolField(TEXT("consumeOnSelect"), Transition.RequiredEvent.bConsumeEventOnSelect);
		Obj->SetObjectField(TEXT("requiredEvent"), EventObj);
	}

	// Delay
	if (Transition.bDelayTransition)
	{
		Obj->SetNumberField(TEXT("delayDuration"), Transition.DelayDuration);
		Obj->SetNumberField(TEXT("delayRandomVariance"), Transition.DelayRandomVariance);
	}

	// Conditions
	TArray<TSharedPtr<FJsonValue>> Conditions;
	for (const FStateTreeEditorNode& Condition : Transition.Conditions)
	{
		TSharedPtr<FJsonObject> CondObj = ExtractEditorNode(Condition);
		if (CondObj)
		{
			Conditions.Add(MakeShared<FJsonValueObject>(CondObj));
		}
	}
	if (Conditions.Num() > 0)
	{
		Obj->SetArrayField(TEXT("conditions"), Conditions);
	}

	return Obj;
}

TSharedPtr<FJsonObject> FStateTreeExtractor::ExtractStructProperties(const UScriptStruct* ScriptStruct, const uint8* Memory)
{
	TSharedPtr<FJsonObject> Props = MakeShared<FJsonObject>();

	if (!ScriptStruct || !Memory)
	{
		return Props;
	}

	for (TFieldIterator<FProperty> PropIt(ScriptStruct); PropIt; ++PropIt)
	{
		FProperty* Property = *PropIt;

		// Skip deprecated and transient properties
		if (Property->HasAnyPropertyFlags(CPF_Deprecated | CPF_Transient))
		{
			continue;
		}

		FString ValueStr;
		Property->ExportText_InContainer(0, ValueStr, Memory, nullptr, nullptr, PPF_None);

		if (!ValueStr.IsEmpty())
		{
			Props->SetStringField(Property->GetName(), ValueStr);
		}
	}

	return Props;
}

TSharedPtr<FJsonObject> FStateTreeExtractor::ExtractPropertyPath(const FPropertyBindingPath& Path)
{
	TSharedPtr<FJsonObject> PathObj = MakeShared<FJsonObject>();

#if WITH_EDITORONLY_DATA
	if (Path.GetStructID().IsValid())
	{
		PathObj->SetStringField(TEXT("structId"), Path.GetStructID().ToString());
	}
#endif

	TConstArrayView<FPropertyBindingPathSegment> Segments = Path.GetSegments();
	if (Segments.Num() > 0)
	{
		TArray<TSharedPtr<FJsonValue>> SegmentArray;
		for (const FPropertyBindingPathSegment& Segment : Segments)
		{
			TSharedPtr<FJsonObject> SegObj = MakeShared<FJsonObject>();
			SegObj->SetStringField(TEXT("name"), Segment.GetName().ToString());

			if (Segment.GetArrayIndex() != INDEX_NONE)
			{
				SegObj->SetNumberField(TEXT("arrayIndex"), Segment.GetArrayIndex());
			}

			if (Segment.GetInstanceStruct())
			{
				SegObj->SetStringField(TEXT("instanceStruct"), Segment.GetInstanceStruct()->GetPathName());
			}

			SegmentArray.Add(MakeShared<FJsonValueObject>(SegObj));
		}
		PathObj->SetArrayField(TEXT("segments"), SegmentArray);
	}

	return PathObj;
}

TSharedPtr<FJsonObject> FStateTreeExtractor::ExtractBindings(const UStateTreeEditorData* EditorData)
{
	if (!EditorData)
	{
		return nullptr;
	}

	const FStateTreeEditorPropertyBindings& Bindings = *EditorData->GetPropertyEditorBindings();
	TConstArrayView<FStateTreePropertyPathBinding> PropertyBindings = Bindings.GetBindings();

	if (PropertyBindings.Num() == 0)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> BindingsObj = MakeShared<FJsonObject>();

	TArray<TSharedPtr<FJsonValue>> BindingArray;
	for (const FStateTreePropertyPathBinding& Binding : PropertyBindings)
	{
		TSharedPtr<FJsonObject> BindingObj = MakeShared<FJsonObject>();

		BindingObj->SetObjectField(TEXT("sourcePath"), ExtractPropertyPath(Binding.GetSourcePath()));
		BindingObj->SetObjectField(TEXT("targetPath"), ExtractPropertyPath(Binding.GetTargetPath()));

		BindingArray.Add(MakeShared<FJsonValueObject>(BindingObj));
	}

	BindingsObj->SetArrayField(TEXT("propertyBindings"), BindingArray);
	BindingsObj->SetNumberField(TEXT("count"), PropertyBindings.Num());

	return BindingsObj;
}
