#include "Authoring/StateTreeAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Blueprint/StateTreeConditionBlueprintBase.h"
#include "Blueprint/StateTreeConsiderationBlueprintBase.h"
#include "Blueprint/StateTreeEvaluatorBlueprintBase.h"
#include "Blueprint/StateTreeTaskBlueprintBase.h"
#include "Logging/TokenizedMessage.h"
#include "Misc/PackageName.h"
#include "StateTree.h"
#include "StateTreeCompilerLog.h"
#include "StateTreeEditingSubsystem.h"
#include "StateTreeEditorData.h"
#include "StateTreeEditorModule.h"
#include "StateTreeEditorPropertyBindings.h"
#include "StateTreeSchema.h"
#include "StateTreeState.h"
#include "StateTreeTaskBase.h"
#include "StateTreeTypes.h"
#include "StructUtils/InstancedStruct.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace StateTreeAuthoringInternal
{

struct FStateSelector
{
	FGuid StateId;
	FString StatePath;
	FString StateName;
};

struct FEditorNodeSelector
{
	FGuid EditorNodeId;
};

struct FTransitionSelector
{
	FGuid TransitionId;
};

struct FStateIndex
{
	TMap<FGuid, UStateTreeState*> ById;
	TMultiMap<FString, UStateTreeState*> ByExactPath;
	TMultiMap<FString, UStateTreeState*> ByNormalizedPath;
	TMultiMap<FString, UStateTreeState*> ByName;
};

struct FStateSelectorFieldSet
{
	const TCHAR* PrimaryIdField = nullptr;
	const TCHAR* SecondaryIdField = nullptr;
	const TCHAR* TertiaryIdField = nullptr;
	const TCHAR* PrimaryPathField = nullptr;
	const TCHAR* SecondaryPathField = nullptr;
	const TCHAR* TertiaryPathField = nullptr;
	const TCHAR* PrimaryNameField = nullptr;
	const TCHAR* SecondaryNameField = nullptr;
	const TCHAR* TertiaryNameField = nullptr;
};

struct FDeferredStateLink
{
	FStateTreeStateLink* Link = nullptr;
	FStateSelector Selector;
	FString Path;
};

struct FEditorNodeHandle
{
	FStateTreeEditorNode* Node = nullptr;
	UObject* Owner = nullptr;
	FString Path;
};

struct FTransitionHandle
{
	FStateTreeTransition* Transition = nullptr;
	UStateTreeState* OwnerState = nullptr;
	FString Path;
};

struct FTreeMutationScratch
{
	TArray<FDeferredStateLink> DeferredLinks;
};

// Forward declaration — used before definition
static bool ApplyBindingsFromJson(UStateTreeEditorData* EditorData,
                                  const TArray<TSharedPtr<FJsonValue>>& BindingValues,
                                  TArray<FString>& OutErrors,
                                  const FString& Path);

static TSharedPtr<FJsonObject> NormalizePayload(const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* NestedPayload = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("stateTree"), NestedPayload)
		&& NestedPayload
		&& NestedPayload->IsValid())
	{
		return *NestedPayload;
	}

	return PayloadJson;
}

template <typename EnumType>
static bool TryParseEnumByName(const UEnum* EnumObject,
                               const FString& Value,
                               EnumType& OutValue)
{
	if (!EnumObject || Value.IsEmpty())
	{
		return false;
	}

	for (int32 Index = 0; Index < EnumObject->NumEnums(); ++Index)
	{
		if (EnumObject->HasMetaData(TEXT("Hidden"), Index))
		{
			continue;
		}

		if (EnumObject->GetNameStringByIndex(Index).Equals(Value, ESearchCase::IgnoreCase))
		{
			OutValue = static_cast<EnumType>(EnumObject->GetValueByIndex(Index));
			return true;
		}
	}

	const int64 ExactValue = EnumObject->GetValueByNameString(Value);
	if (ExactValue != INDEX_NONE)
	{
		OutValue = static_cast<EnumType>(ExactValue);
		return true;
	}

	return false;
}

static bool ParseGuidString(const FString& GuidString, FGuid& OutGuid)
{
	if (GuidString.IsEmpty())
	{
		return false;
	}

	// FGuid::Parse handles multiple formats including bare-hex
	// (XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX) and hyphenated
	// ({XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}).
	// The FGuid(string) constructor only accepts the braced-hyphenated form,
	// so use FGuid::Parse first to support bare-hex GUIDs from extract_asset.
	if (FGuid::Parse(GuidString, OutGuid))
	{
		return OutGuid.IsValid();
	}

	// Fallback: try the raw constructor for any other accepted format
	OutGuid = FGuid(GuidString);
	return OutGuid.IsValid();
}

static FString NormalizeStatePathForLookup(FString StatePath)
{
	StatePath.TrimStartAndEndInline();
	StatePath.ReplaceInline(TEXT("\\"), TEXT("/"));
	StatePath.ReplaceInline(TEXT("."), TEXT("/"));
	while (StatePath.Contains(TEXT("//")))
	{
		StatePath.ReplaceInline(TEXT("//"), TEXT("/"));
	}
	return StatePath;
}

static bool TryGetAnyNonEmptyStringField(const TSharedPtr<FJsonObject>& Payload,
                                         FString& OutValue,
                                         const TCHAR*& OutMatchedField,
                                         const TCHAR* PrimaryField,
                                         const TCHAR* SecondaryField = nullptr,
                                         const TCHAR* TertiaryField = nullptr)
{
	OutValue.Reset();
	OutMatchedField = nullptr;
	if (!Payload.IsValid())
	{
		return false;
	}

	const auto TryField = [&](const TCHAR* FieldName) -> bool
	{
		FString Candidate;
		if (FieldName && Payload->TryGetStringField(FieldName, Candidate) && !Candidate.IsEmpty())
		{
			OutValue = Candidate;
			OutMatchedField = FieldName;
			return true;
		}

		return false;
	};

	return TryField(PrimaryField)
		|| TryField(SecondaryField)
		|| TryField(TertiaryField);
}

static bool ParseStateSelectorWithFields(const TSharedPtr<FJsonObject>& Payload,
                                         const FStateSelectorFieldSet& FieldSet,
                                         FStateSelector& OutSelector,
                                         FString& OutError,
                                         const FString& MissingSelectorError)
{
	OutSelector = FStateSelector();
	if (!Payload.IsValid())
	{
		OutError = TEXT("State selector payload must be an object.");
		return false;
	}

	FString GuidString;
	const TCHAR* MatchedField = nullptr;
	if (TryGetAnyNonEmptyStringField(
			Payload,
			GuidString,
			MatchedField,
			FieldSet.PrimaryIdField,
			FieldSet.SecondaryIdField,
			FieldSet.TertiaryIdField))
	{
		if (!ParseGuidString(GuidString, OutSelector.StateId))
		{
			const FString FieldLabel = MatchedField ? FString(MatchedField) : FString(TEXT("stateId"));
			OutError = FString::Printf(TEXT("Invalid %s '%s'."), *FieldLabel, *GuidString);
			return false;
		}

		return true;
	}

	if (TryGetAnyNonEmptyStringField(
			Payload,
			OutSelector.StatePath,
			MatchedField,
			FieldSet.PrimaryPathField,
			FieldSet.SecondaryPathField,
			FieldSet.TertiaryPathField))
	{
		return true;
	}

	if (TryGetAnyNonEmptyStringField(
			Payload,
			OutSelector.StateName,
			MatchedField,
			FieldSet.PrimaryNameField,
			FieldSet.SecondaryNameField,
			FieldSet.TertiaryNameField))
	{
		return true;
	}

	OutError = MissingSelectorError;
	return false;
}

static bool ParseStateSelector(const TSharedPtr<FJsonObject>& Payload,
                               FStateSelector& OutSelector,
                               FString& OutError)
{
	const FStateSelectorFieldSet FieldSet {
		TEXT("stateId"),
		TEXT("id"),
		nullptr,
		TEXT("statePath"),
		TEXT("path"),
		nullptr,
		TEXT("stateName"),
		TEXT("name"),
		nullptr,
	};
	return ParseStateSelectorWithFields(
		Payload,
		FieldSet,
		OutSelector,
		OutError,
		TEXT("State selector requires stateId, statePath, or stateName."));
}

static bool ParseLinkedStateSelector(const TSharedPtr<FJsonObject>& Payload,
                                     FStateSelector& OutSelector,
                                     FString& OutError)
{
	const FStateSelectorFieldSet FieldSet {
		TEXT("linkedStateId"),
		TEXT("stateId"),
		TEXT("id"),
		TEXT("linkedStatePath"),
		TEXT("statePath"),
		TEXT("path"),
		TEXT("linkedStateName"),
		TEXT("stateName"),
		TEXT("name"),
	};
	return ParseStateSelectorWithFields(
		Payload,
		FieldSet,
		OutSelector,
		OutError,
		TEXT("linkedSubtree requires linkedStateId, linkedStatePath, linkedStateName, or their stateId/statePath/stateName aliases."));
}

static bool ParseEditorNodeSelector(const TSharedPtr<FJsonObject>& Payload,
                                    FEditorNodeSelector& OutSelector,
                                    FString& OutError)
{
	if (!Payload.IsValid())
	{
		OutError = TEXT("Editor node selector payload must be an object.");
		return false;
	}

	FString GuidString;
	if (!(Payload->TryGetStringField(TEXT("editorNodeId"), GuidString)
		  || Payload->TryGetStringField(TEXT("id"), GuidString))
		|| !ParseGuidString(GuidString, OutSelector.EditorNodeId))
	{
		OutError = TEXT("Editor node selector requires a valid editorNodeId.");
		return false;
	}

	return true;
}

static bool ParseTransitionSelector(const TSharedPtr<FJsonObject>& Payload,
                                    FTransitionSelector& OutSelector,
                                    FString& OutError)
{
	if (!Payload.IsValid())
	{
		OutError = TEXT("Transition selector payload must be an object.");
		return false;
	}

	FString GuidString;
	if (!(Payload->TryGetStringField(TEXT("transitionId"), GuidString)
		  || Payload->TryGetStringField(TEXT("id"), GuidString))
		|| !ParseGuidString(GuidString, OutSelector.TransitionId))
	{
		OutError = TEXT("Transition selector requires a valid transitionId.");
		return false;
	}

	return true;
}

static FString GetSchemaPathFromPayload(const TSharedPtr<FJsonObject>& Payload)
{
	if (!Payload.IsValid())
	{
		return FString();
	}

	FString SchemaPath;
	if ((Payload->TryGetStringField(TEXT("schema"), SchemaPath)
		 || Payload->TryGetStringField(TEXT("schemaClass"), SchemaPath)
		 || Payload->TryGetStringField(TEXT("schemaClassPath"), SchemaPath))
		&& !SchemaPath.IsEmpty())
	{
		return SchemaPath;
	}

	return FString();
}

static UClass* ResolveSchemaClass(const TSharedPtr<FJsonObject>& Payload,
                                  TArray<FString>& OutErrors,
                                  const bool bRequired)
{
	const FString SchemaPath = GetSchemaPathFromPayload(Payload);
	if (SchemaPath.IsEmpty())
	{
		if (bRequired)
		{
			OutErrors.Add(TEXT("StateTree schema is required."));
		}
		return nullptr;
	}

	UClass* SchemaClass = FAuthoringHelpers::ResolveClass(
		SchemaPath,
		UStateTreeSchema::StaticClass());
	if (!SchemaClass)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to resolve StateTree schema '%s'."),
			*SchemaPath));
		return nullptr;
	}

	if (SchemaClass->HasAnyClassFlags(CLASS_Abstract))
	{
		OutErrors.Add(FString::Printf(
			TEXT("StateTree schema '%s' is abstract."),
			*SchemaClass->GetPathName()));
		return nullptr;
	}

	return SchemaClass;
}

static UStateTreeEditorData* EnsureEditorData(UStateTree* StateTree,
                                              UClass* SchemaClass,
                                              TArray<FString>& OutErrors)
{
	if (!StateTree)
	{
		OutErrors.Add(TEXT("StateTree is null."));
		return nullptr;
	}

	if (!SchemaClass)
	{
		OutErrors.Add(TEXT("StateTree schema class is null."));
		return nullptr;
	}

	UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData);
	TNonNullSubclassOf<UStateTreeEditorData> DesiredEditorDataClass =
		FStateTreeEditorModule::GetModule().GetEditorDataClass(SchemaClass);

	if (!EditorData)
	{
		EditorData = NewObject<UStateTreeEditorData>(
			StateTree,
			DesiredEditorDataClass.Get(),
			FName(),
			RF_Transactional);
		StateTree->EditorData = EditorData;
	}
	else if (!EditorData->IsA(DesiredEditorDataClass.Get()))
	{
		EditorData = Cast<UStateTreeEditorData>(StaticDuplicateObject(
			EditorData,
			StateTree,
			NAME_None,
			RF_Transactional,
			DesiredEditorDataClass.Get()));
		StateTree->EditorData = EditorData;
	}

	if (!EditorData)
	{
		OutErrors.Add(TEXT("Failed to create StateTree editor data."));
		return nullptr;
	}

	if (!EditorData->Schema || EditorData->Schema->GetClass() != SchemaClass)
	{
		EditorData->Schema = NewObject<UStateTreeSchema>(
			EditorData,
			SchemaClass,
			NAME_None,
			RF_Transactional);
	}

	EditorData->EditorBindings.SetBindingsOwner(EditorData);
	return EditorData;
}

static UStateTreeEditorData* GetExistingEditorData(UStateTree* StateTree,
                                                   TArray<FString>& OutErrors)
{
	if (!StateTree)
	{
		OutErrors.Add(TEXT("StateTree is null."));
		return nullptr;
	}

	if (UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData))
	{
		EditorData->EditorBindings.SetBindingsOwner(EditorData);
		return EditorData;
	}

	if (const UStateTreeSchema* ExistingSchema = StateTree->GetSchema())
	{
		return EnsureEditorData(StateTree, ExistingSchema->GetClass(), OutErrors);
	}

	OutErrors.Add(TEXT("StateTree has no editor data or compiled schema."));
	return nullptr;
}

static bool AppendValidationSummary(FAssetMutationContext& Context,
                                    const bool bSuccess,
                                    const FString& Summary,
                                    const TArray<FString>& Errors,
                                    const TArray<FString>& Warnings)
{
	Context.SetValidationSummary(bSuccess, Summary, Errors);
	for (const FString& Error : Errors)
	{
		Context.AddError(TEXT("validation_error"), Error, Context.AssetPath);
	}
	for (const FString& Warning : Warnings)
	{
		Context.AddWarning(TEXT("validation_warning"), Warning, Context.AssetPath);
	}
	return bSuccess;
}

static TSharedPtr<FJsonObject> BuildCompileSummary(const FStateTreeCompilerLog& Log,
                                                   const bool bCompileResult,
                                                   TArray<FString>& OutErrors,
                                                   TArray<FString>& OutWarnings)
{
	TArray<TSharedPtr<FJsonValue>> ErrorValues;
	TArray<TSharedPtr<FJsonValue>> WarningValues;
	TArray<TSharedPtr<FJsonValue>> MessageValues;

	for (const TSharedRef<FTokenizedMessage>& Message : Log.ToTokenizedMessages())
	{
		const FString MessageText = Message->ToText().ToString();
		const EMessageSeverity::Type Severity = Message->GetSeverity();

		TSharedPtr<FJsonObject> MessageObject = MakeShared<FJsonObject>();
		FString SeverityString = TEXT("info");
		if (Severity == EMessageSeverity::Error)
		{
			SeverityString = TEXT("error");
			OutErrors.Add(MessageText);
			ErrorValues.Add(MakeShared<FJsonValueString>(MessageText));
		}
		else if (Severity == EMessageSeverity::Warning || Severity == EMessageSeverity::PerformanceWarning)
		{
			SeverityString = TEXT("warning");
			OutWarnings.Add(MessageText);
			WarningValues.Add(MakeShared<FJsonValueString>(MessageText));
		}

		MessageObject->SetStringField(TEXT("severity"), SeverityString);
		MessageObject->SetStringField(TEXT("message"), MessageText);
		MessageValues.Add(MakeShared<FJsonValueObject>(MessageObject));
	}

	const bool bSuccess = bCompileResult && OutErrors.Num() == 0;
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), bSuccess);
	Result->SetStringField(TEXT("status"), bSuccess ? TEXT("Succeeded") : TEXT("Failed"));
	Result->SetArrayField(TEXT("errors"), ErrorValues);
	Result->SetArrayField(TEXT("warnings"), WarningValues);
	Result->SetArrayField(TEXT("messages"), MessageValues);
	Result->SetNumberField(TEXT("errorCount"), OutErrors.Num());
	Result->SetNumberField(TEXT("warningCount"), OutWarnings.Num());
	return Result;
}

/** Pre-compile safety: walk all editor nodes and verify their FInstancedStruct
 *  pointers are valid. After Live Coding, UScriptStruct pointers inside
 *  FInstancedStruct can go stale — CompileStateTree would crash accessing them. */
static bool PreValidateEditorNodes(const UStateTree* StateTree, TArray<FString>& OutErrors)
{
	const UStateTreeEditorData* EditorData = StateTree ? Cast<UStateTreeEditorData>(StateTree->EditorData) : nullptr;
	if (!EditorData) return true; // nothing to validate

	auto CheckNodeArray = [&](const TArray<FStateTreeEditorNode>& Nodes, const FString& Context)
	{
		for (int32 i = 0; i < Nodes.Num(); ++i)
		{
			const FStateTreeEditorNode& EditorNode = Nodes[i];
			if (EditorNode.Node.IsValid() && !EditorNode.Node.GetScriptStruct())
			{
				OutErrors.Add(FString::Printf(
					TEXT("%s[%d] has a valid FInstancedStruct with a null UScriptStruct pointer (stale after Live Coding?)."),
					*Context, i));
			}
			if (EditorNode.Instance.IsValid() && !EditorNode.Instance.GetScriptStruct())
			{
				OutErrors.Add(FString::Printf(
					TEXT("%s[%d].Instance has a valid FInstancedStruct with a null UScriptStruct pointer."),
					*Context, i));
			}
		}
	};

	CheckNodeArray(EditorData->Evaluators, TEXT("Evaluators"));
	CheckNodeArray(EditorData->GlobalTasks, TEXT("GlobalTasks"));

	TArray<const UStateTreeState*> Stack;
	for (const UStateTreeState* RootState : EditorData->SubTrees)
	{
		if (RootState) Stack.Push(RootState);
	}
	while (Stack.Num() > 0)
	{
		const UStateTreeState* State = Stack.Pop();
		const FString StatePath = State->Name.ToString();

		CheckNodeArray(State->Tasks, FString::Printf(TEXT("State '%s' Tasks"), *StatePath));
		CheckNodeArray(State->EnterConditions, FString::Printf(TEXT("State '%s' EnterConditions"), *StatePath));

		for (const FStateTreeTransition& Transition : State->Transitions)
		{
			CheckNodeArray(Transition.Conditions, FString::Printf(TEXT("State '%s' Transition Conditions"), *StatePath));
		}

		for (const UStateTreeState* ChildState : State->Children)
		{
			if (ChildState) Stack.Push(ChildState);
		}
	}

	return OutErrors.Num() == 0;
}

static bool ValidateAndCompile(UStateTree* StateTree,
                               FAssetMutationContext& Context,
                               const FString& SuccessSummary,
                               const FString& FailureSummary)
{
	if (!StateTree || !StateTree->EditorData)
	{
		Context.AddError(TEXT("editor_data_missing"), TEXT("StateTree has no editor data."));
		return false;
	}

	// Pre-validate: catch stale struct pointers before the engine compiler accesses them.
	{
		TArray<FString> PreValidationErrors;
		if (!PreValidateEditorNodes(StateTree, PreValidationErrors))
		{
			for (const FString& Error : PreValidationErrors)
			{
				Context.AddError(TEXT("stale_struct_pointer"), Error);
			}
			Context.SetValidationSummary(false,
				TEXT("StateTree has nodes with stale struct pointers (likely after Live Coding). "
				     "Restart the editor and retry."),
				PreValidationErrors);
			return false;
		}
	}

	FStateTreeCompilerLog CompilerLog;
	const bool bCompileResult = UStateTreeEditingSubsystem::CompileStateTree(StateTree, CompilerLog);

	TArray<FString> Errors;
	TArray<FString> Warnings;
	Context.SetCompileSummary(BuildCompileSummary(CompilerLog, bCompileResult, Errors, Warnings));

	return AppendValidationSummary(
		Context,
		bCompileResult && Errors.Num() == 0,
		(bCompileResult && Errors.Num() == 0) ? SuccessSummary : FailureSummary,
		Errors,
		Warnings);
}

static UStateTree* CreateTransientStateTree(const TSharedPtr<FJsonObject>& Payload,
                                            TArray<FString>& OutErrors)
{
	UClass* SchemaClass = ResolveSchemaClass(Payload, OutErrors, true);
	if (!SchemaClass)
	{
		return nullptr;
	}

	UStateTree* PreviewTree = NewObject<UStateTree>(
		GetTransientPackage(),
		MakeUniqueObjectName(GetTransientPackage(), UStateTree::StaticClass(), TEXT("StateTreePreview")),
		RF_Transient);
	if (!PreviewTree)
	{
		OutErrors.Add(TEXT("Failed to create transient StateTree preview."));
		return nullptr;
	}

	if (!EnsureEditorData(PreviewTree, SchemaClass, OutErrors))
	{
		return nullptr;
	}

	return PreviewTree;
}

static bool ParseGameplayTagString(const FString& TagString,
                                   FGameplayTag& OutTag)
{
	if (TagString.IsEmpty())
	{
		OutTag = FGameplayTag();
		return true;
	}

	OutTag = FGameplayTag::RequestGameplayTag(FName(*TagString), false);
	return OutTag.IsValid();
}

static bool ApplyStructPropertyObject(const UScriptStruct* ScriptStruct,
                                      void* StructMemory,
                                      const TSharedPtr<FJsonObject>& PropertiesObject,
                                      TArray<FString>& OutErrors,
                                      const FString& Path,
                                      const bool bValidationOnly)
{
	if (!PropertiesObject.IsValid())
	{
		return true;
	}

	TArray<FString> PropertyErrors;
	const bool bSuccess = FAuthoringHelpers::ApplyStructProperties(
		ScriptStruct,
		StructMemory,
		PropertiesObject,
		PropertyErrors,
		bValidationOnly);
	for (const FString& Error : PropertyErrors)
	{
		OutErrors.Add(FString::Printf(TEXT("%s: %s"), *Path, *Error));
	}

	return bSuccess;
}

static bool ApplyObjectProperties(UObject* Object,
                                  const TSharedPtr<FJsonObject>& PropertiesObject,
                                  TArray<FString>& OutErrors,
                                  const FString& Path,
                                  const bool bValidationOnly)
{
	if (!Object || !PropertiesObject.IsValid())
	{
		return true;
	}

	TArray<FString> PropertyErrors;
	const bool bSuccess = FPropertySerializer::ApplyPropertiesFromJson(
		Object,
		PropertiesObject,
		PropertyErrors,
		bValidationOnly,
		true);
	for (const FString& Error : PropertyErrors)
	{
		OutErrors.Add(FString::Printf(TEXT("%s: %s"), *Path, *Error));
	}

	return bSuccess;
}

static bool ApplyEventDesc(const TSharedPtr<FJsonValue>& EventValue,
                           FStateTreeEventDesc& OutEvent,
                           bool& bOutHasEvent,
                           TArray<FString>& OutErrors,
                           const FString& Path)
{
	OutEvent = FStateTreeEventDesc();
	bOutHasEvent = false;

	if (!EventValue.IsValid() || EventValue->Type == EJson::Null)
	{
		return true;
	}

	const TSharedPtr<FJsonObject> EventObject = EventValue->AsObject();
	if (!EventObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s must be an object or null."), *Path));
		return false;
	}

	FString TagString;
	if (EventObject->TryGetStringField(TEXT("tag"), TagString)
		&& !ParseGameplayTagString(TagString, OutEvent.Tag))
	{
		OutErrors.Add(FString::Printf(
			TEXT("%s.tag '%s' is not a registered gameplay tag."),
			*Path,
			*TagString));
	}

	FString PayloadStructPath;
	if (EventObject->TryGetStringField(TEXT("payloadStruct"), PayloadStructPath)
		&& !PayloadStructPath.IsEmpty())
	{
		OutEvent.PayloadStruct = FAuthoringHelpers::ResolveScriptStruct(PayloadStructPath);
		if (!OutEvent.PayloadStruct)
		{
			OutErrors.Add(FString::Printf(
				TEXT("%s.payloadStruct '%s' could not be resolved."),
				*Path,
				*PayloadStructPath));
		}
	}

	bool bConsumeOnSelect = false;
	if (EventObject->TryGetBoolField(TEXT("consumeOnSelect"), bConsumeOnSelect))
	{
		OutEvent.bConsumeEventOnSelect = bConsumeOnSelect;
	}

	bOutHasEvent = OutEvent.IsValid();
	return OutErrors.Num() == 0;
}

static UClass* ResolveInstanceObjectClass(const TSharedPtr<FJsonObject>& NodeObject,
                                          UClass* RequiredBaseClass,
                                          TArray<FString>& OutErrors,
                                          const FString& Path)
{
	if (!NodeObject.IsValid())
	{
		return nullptr;
	}

	FString ClassPath;
	if (!(NodeObject->TryGetStringField(TEXT("instanceObjectClass"), ClassPath) && !ClassPath.IsEmpty()))
	{
		FString ObjectPath;
		if (NodeObject->TryGetStringField(TEXT("instanceObjectPath"), ObjectPath) && !ObjectPath.IsEmpty())
		{
			UObject* ExistingObject = FAuthoringHelpers::ResolveObject(ObjectPath);
			if (!ExistingObject)
			{
				OutErrors.Add(FString::Printf(
					TEXT("%s.instanceObjectPath '%s' could not be resolved."),
					*Path, *ObjectPath));
				return nullptr;
			}
			UClass* ExistingClass = ExistingObject->GetClass();
			if (!RequiredBaseClass || ExistingClass->IsChildOf(RequiredBaseClass))
			{
				return ExistingClass;
			}
			OutErrors.Add(FString::Printf(
				TEXT("%s.instanceObjectPath '%s' resolved to class '%s' which is not a subclass of '%s'."),
				*Path, *ObjectPath, *ExistingClass->GetPathName(),
				*RequiredBaseClass->GetPathName()));
			return nullptr;
		}
		return nullptr;
	}

	UClass* ResolvedClass = FAuthoringHelpers::ResolveClass(ClassPath, RequiredBaseClass);
	if (!ResolvedClass)
	{
		OutErrors.Add(FString::Printf(
			TEXT("%s.instanceObjectClass '%s' could not be resolved."),
			*Path,
			*ClassPath));
	}
	return ResolvedClass;
}

static void InitializeNodeInstance(FStateTreeEditorNode& EditorNode,
                                   UObject* Owner)
{
	EditorNode.Instance.Reset();
	EditorNode.InstanceObject = nullptr;

	if (const FStateTreeNodeBase* NodeBase = EditorNode.Node.GetPtr<FStateTreeNodeBase>())
	{
		if (const UScriptStruct* InstanceStruct = Cast<UScriptStruct>(NodeBase->GetInstanceDataType()))
		{
			EditorNode.Instance.InitializeAs(InstanceStruct);
		}
		else if (const UClass* InstanceClass = Cast<UClass>(NodeBase->GetInstanceDataType()))
		{
			EditorNode.InstanceObject = NewObject<UObject>(Owner, InstanceClass, NAME_None, RF_Transactional);
		}
	}
}

static bool ConfigureBlueprintWrapperClass(FStateTreeEditorNode& EditorNode,
                                           const TSharedPtr<FJsonObject>& NodeObject,
                                           TArray<FString>& OutErrors,
                                           const FString& Path)
{
	const UScriptStruct* NodeStruct = EditorNode.Node.GetScriptStruct();
	if (!NodeStruct || !NodeObject.IsValid())
	{
		return true;
	}

	if (NodeStruct->IsChildOf(FStateTreeBlueprintTaskWrapper::StaticStruct()))
	{
		if (FStateTreeBlueprintTaskWrapper* Wrapper = EditorNode.Node.GetMutablePtr<FStateTreeBlueprintTaskWrapper>())
		{
			Wrapper->TaskClass = ResolveInstanceObjectClass(NodeObject, UStateTreeTaskBlueprintBase::StaticClass(), OutErrors, Path);
			if (!Wrapper->TaskClass)
			{
				OutErrors.AddUnique(FString::Printf(
					TEXT("%s: Blueprint task wrapper requires 'instanceObjectClass' specifying a UStateTreeTaskBlueprintBase subclass."),
					*Path));
			}
			return Wrapper->TaskClass != nullptr;
		}
	}

	if (NodeStruct->IsChildOf(FStateTreeBlueprintEvaluatorWrapper::StaticStruct()))
	{
		if (FStateTreeBlueprintEvaluatorWrapper* Wrapper = EditorNode.Node.GetMutablePtr<FStateTreeBlueprintEvaluatorWrapper>())
		{
			Wrapper->EvaluatorClass = ResolveInstanceObjectClass(NodeObject, UStateTreeEvaluatorBlueprintBase::StaticClass(), OutErrors, Path);
			if (!Wrapper->EvaluatorClass)
			{
				OutErrors.AddUnique(FString::Printf(
					TEXT("%s: Blueprint evaluator wrapper requires 'instanceObjectClass' specifying a UStateTreeEvaluatorBlueprintBase subclass."),
					*Path));
			}
			return Wrapper->EvaluatorClass != nullptr;
		}
	}

	if (NodeStruct->IsChildOf(FStateTreeBlueprintConditionWrapper::StaticStruct()))
	{
		if (FStateTreeBlueprintConditionWrapper* Wrapper = EditorNode.Node.GetMutablePtr<FStateTreeBlueprintConditionWrapper>())
		{
			Wrapper->ConditionClass = ResolveInstanceObjectClass(NodeObject, UStateTreeConditionBlueprintBase::StaticClass(), OutErrors, Path);
			if (!Wrapper->ConditionClass)
			{
				OutErrors.AddUnique(FString::Printf(
					TEXT("%s: Blueprint condition wrapper requires 'instanceObjectClass' specifying a UStateTreeConditionBlueprintBase subclass."),
					*Path));
			}
			return Wrapper->ConditionClass != nullptr;
		}
	}

	if (NodeStruct->IsChildOf(FStateTreeBlueprintConsiderationWrapper::StaticStruct()))
	{
		if (FStateTreeBlueprintConsiderationWrapper* Wrapper = EditorNode.Node.GetMutablePtr<FStateTreeBlueprintConsiderationWrapper>())
		{
			Wrapper->ConsiderationClass = ResolveInstanceObjectClass(NodeObject, UStateTreeConsiderationBlueprintBase::StaticClass(), OutErrors, Path);
			if (!Wrapper->ConsiderationClass)
			{
				OutErrors.AddUnique(FString::Printf(
					TEXT("%s: Blueprint consideration wrapper requires 'instanceObjectClass' specifying a UStateTreeConsiderationBlueprintBase subclass."),
					*Path));
			}
			return Wrapper->ConsiderationClass != nullptr;
		}
	}

	return true;
}

static bool BuildEditorNode(FStateTreeEditorNode& OutEditorNode,
                            UObject* Owner,
                            const TSharedPtr<FJsonObject>& NodeObject,
                            TArray<FString>& OutErrors,
                            const FString& Path,
                            const bool bValidationOnly,
                            const FGuid* PreservedId = nullptr)
{
	if (!NodeObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s must be an object."), *Path));
		return false;
	}

	FString NodeStructPath;
	if (!NodeObject->TryGetStringField(TEXT("nodeStructType"), NodeStructPath) || NodeStructPath.IsEmpty())
	{
		OutErrors.Add(FString::Printf(TEXT("%s.nodeStructType is required."), *Path));
		return false;
	}

	UScriptStruct* NodeStruct = FAuthoringHelpers::ResolveScriptStruct(NodeStructPath);
	if (!NodeStruct)
	{
		OutErrors.Add(FString::Printf(
			TEXT("%s.nodeStructType '%s' could not be resolved."),
			*Path,
			*NodeStructPath));
		return false;
	}

	OutEditorNode.Reset();
	OutEditorNode.Node.InitializeAs(NodeStruct);

	if (!ConfigureBlueprintWrapperClass(OutEditorNode, NodeObject, OutErrors, Path))
	{
		return false;
	}

	InitializeNodeInstance(OutEditorNode, Owner);

	if (PreservedId && PreservedId->IsValid())
	{
		OutEditorNode.ID = *PreservedId;
	}
	else
	{
		FString GuidString;
		if ((NodeObject->TryGetStringField(TEXT("editorNodeId"), GuidString)
			 || NodeObject->TryGetStringField(TEXT("id"), GuidString))
			&& ParseGuidString(GuidString, OutEditorNode.ID))
		{
		}
		else
		{
			OutEditorNode.ID = FGuid::NewGuid();
		}
	}

	FString OperandString;
	if (NodeObject->TryGetStringField(TEXT("expressionOperand"), OperandString)
		&& !OperandString.IsEmpty()
		&& !TryParseEnumByName(StaticEnum<EStateTreeExpressionOperand>(), OperandString, OutEditorNode.ExpressionOperand))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.expressionOperand '%s' is invalid."), *Path, *OperandString));
	}

	int32 ExpressionIndent = 0;
	if (NodeObject->TryGetNumberField(TEXT("expressionIndent"), ExpressionIndent))
	{
		OutEditorNode.ExpressionIndent = static_cast<uint8>(FMath::Clamp(ExpressionIndent, 0, UE::StateTree::MaxExpressionIndent));
	}

	if (const TSharedPtr<FJsonObject>* NodeProperties = nullptr;
		NodeObject->TryGetObjectField(TEXT("nodeProperties"), NodeProperties) && NodeProperties && NodeProperties->IsValid())
	{
		ApplyStructPropertyObject(
			NodeStruct,
			OutEditorNode.Node.GetMutableMemory(),
			*NodeProperties,
			OutErrors,
			Path + TEXT(".nodeProperties"),
			bValidationOnly);
	}

	if (const TSharedPtr<FJsonObject>* InstanceProperties = nullptr;
		NodeObject->TryGetObjectField(TEXT("instanceProperties"), InstanceProperties) && InstanceProperties && InstanceProperties->IsValid())
	{
		if (OutEditorNode.Instance.IsValid())
		{
			ApplyStructPropertyObject(
				OutEditorNode.Instance.GetScriptStruct(),
				OutEditorNode.Instance.GetMutableMemory(),
				*InstanceProperties,
				OutErrors,
				Path + TEXT(".instanceProperties"),
				bValidationOnly);
		}
		else if (OutEditorNode.InstanceObject)
		{
			ApplyObjectProperties(
				OutEditorNode.InstanceObject,
				*InstanceProperties,
				OutErrors,
				Path + TEXT(".instanceProperties"),
				bValidationOnly);
		}
	}

	FString DisplayName;
	if (NodeObject->TryGetStringField(TEXT("name"), DisplayName) && !DisplayName.IsEmpty())
	{
		if (FStateTreeNodeBase* NodeBase = OutEditorNode.Node.GetMutablePtr<FStateTreeNodeBase>())
		{
			NodeBase->Name = FName(*DisplayName);
		}
	}

	return OutErrors.Num() == 0;
}

static bool BuildEditorNodeArray(const TArray<TSharedPtr<FJsonValue>>& NodeValues,
                                 UObject* Owner,
                                 TArray<FStateTreeEditorNode>& OutNodes,
                                 TArray<FString>& OutErrors,
                                 const FString& Path,
                                 const bool bValidationOnly)
{
	OutNodes.Reset();
	for (int32 Index = 0; Index < NodeValues.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> NodeObject = NodeValues[Index].IsValid() ? NodeValues[Index]->AsObject() : nullptr;
		FStateTreeEditorNode& NewNode = OutNodes.AddDefaulted_GetRef();
		if (!BuildEditorNode(NewNode, Owner, NodeObject, OutErrors, FString::Printf(TEXT("%s[%d]"), *Path, Index), bValidationOnly))
		{
			OutNodes.Pop();
		}
	}
	return OutErrors.Num() == 0;
}

static bool BuildStateIndexRecursive(UStateTreeState* State,
                                     FStateIndex& OutIndex,
                                     TArray<FString>& OutErrors)
{
	if (!State)
	{
		return true;
	}

	if (State->ID.IsValid())
	{
		if (OutIndex.ById.Contains(State->ID))
		{
			OutErrors.Add(FString::Printf(TEXT("Duplicate StateTree state id '%s'."), *State->ID.ToString()));
		}
		else
		{
			OutIndex.ById.Add(State->ID, State);
		}
	}

	const auto AddUniquePathEntry = [](TMultiMap<FString, UStateTreeState*>& IndexMap,
	                                   const FString& PathKey,
	                                   UStateTreeState* InState)
	{
		if (!InState || PathKey.IsEmpty())
		{
			return;
		}

		TArray<UStateTreeState*> ExistingStates;
		IndexMap.MultiFind(PathKey, ExistingStates);
		if (!ExistingStates.Contains(InState))
		{
			IndexMap.Add(PathKey, InState);
		}
	};

	const FString ExactPath = State->GetPath();
	AddUniquePathEntry(OutIndex.ByExactPath, ExactPath, State);
	AddUniquePathEntry(OutIndex.ByNormalizedPath, NormalizeStatePathForLookup(ExactPath), State);
	OutIndex.ByName.Add(State->Name.ToString(), State);

	for (UStateTreeState* Child : State->Children)
	{
		BuildStateIndexRecursive(Child, OutIndex, OutErrors);
	}

	return OutErrors.Num() == 0;
}

static FStateIndex BuildStateIndex(UStateTreeEditorData* EditorData,
                                   TArray<FString>& OutErrors)
{
	FStateIndex Result;
	if (!EditorData)
	{
		return Result;
	}

	for (UStateTreeState* RootState : EditorData->SubTrees)
	{
		BuildStateIndexRecursive(RootState, Result, OutErrors);
	}

	return Result;
}

static UStateTreeState* ResolveIndexedState(const FStateIndex& Index,
                                            const FStateSelector& Selector,
                                            TArray<FString>& OutErrors,
                                            const FString& ContextPath,
                                            const FStateIndex* SourceIndex = nullptr)
{
	if (Selector.StateId.IsValid())
	{
		if (UStateTreeState* const* FoundState = Index.ById.Find(Selector.StateId))
		{
			return *FoundState;
		}

		if (SourceIndex)
		{
			if (UStateTreeState* const* SourceState = SourceIndex->ById.Find(Selector.StateId))
			{
				const FString CanonicalSourcePath = NormalizeStatePathForLookup((*SourceState)->GetPath());
				if (!CanonicalSourcePath.IsEmpty())
				{
					TArray<UStateTreeState*> RemappedMatches;
					Index.ByNormalizedPath.MultiFind(CanonicalSourcePath, RemappedMatches);
					if (RemappedMatches.Num() == 1)
					{
						return RemappedMatches[0];
					}
				}
			}
		}

		OutErrors.Add(FString::Printf(TEXT("%s: stateId '%s' was not found."), *ContextPath, *Selector.StateId.ToString()));
		return nullptr;
	}

	if (!Selector.StatePath.IsEmpty())
	{
		TArray<UStateTreeState*> Matches;
		Index.ByExactPath.MultiFind(Selector.StatePath, Matches);
		if (Matches.Num() == 0)
		{
			Index.ByNormalizedPath.MultiFind(NormalizeStatePathForLookup(Selector.StatePath), Matches);
		}
		if (Matches.Num() == 1)
		{
			return Matches[0];
		}
		if (Matches.Num() > 1)
		{
			OutErrors.Add(FString::Printf(TEXT("%s: statePath '%s' is ambiguous."), *ContextPath, *Selector.StatePath));
			return nullptr;
		}

		OutErrors.Add(FString::Printf(TEXT("%s: statePath '%s' was not found."), *ContextPath, *Selector.StatePath));
		return nullptr;
	}

	if (!Selector.StateName.IsEmpty())
	{
		TArray<UStateTreeState*> Matches;
		Index.ByName.MultiFind(Selector.StateName, Matches);
		if (Matches.Num() == 1)
		{
			return Matches[0];
		}
		if (Matches.Num() > 1)
		{
			OutErrors.Add(FString::Printf(TEXT("%s: stateName '%s' is ambiguous."), *ContextPath, *Selector.StateName));
			return nullptr;
		}
		OutErrors.Add(FString::Printf(TEXT("%s: stateName '%s' was not found."), *ContextPath, *Selector.StateName));
	}

	return nullptr;
}

static void CollectEditorNodesForState(UStateTreeState* State,
                                       TMap<FGuid, FEditorNodeHandle>& OutNodes)
{
	if (!State)
	{
		return;
	}

	const FString StatePath = State->GetPath();

	auto AddNodes = [&](TArray<FStateTreeEditorNode>& Nodes, const FString& CollectionPath)
	{
		for (int32 Index = 0; Index < Nodes.Num(); ++Index)
		{
			FStateTreeEditorNode& Node = Nodes[Index];
			if (Node.ID.IsValid())
			{
				OutNodes.Add(Node.ID, {&Node, State, FString::Printf(TEXT("%s.%s[%d]"), *StatePath, *CollectionPath, Index)});
			}
		}
	};

	AddNodes(State->EnterConditions, TEXT("enterConditions"));
	AddNodes(State->Tasks, TEXT("tasks"));
	AddNodes(State->Considerations, TEXT("considerations"));

	if (State->SingleTask.ID.IsValid())
	{
		OutNodes.Add(State->SingleTask.ID, {&State->SingleTask, State, StatePath + TEXT(".singleTask")});
	}

	for (int32 TransitionIndex = 0; TransitionIndex < State->Transitions.Num(); ++TransitionIndex)
	{
		FStateTreeTransition& Transition = State->Transitions[TransitionIndex];
		for (int32 ConditionIndex = 0; ConditionIndex < Transition.Conditions.Num(); ++ConditionIndex)
		{
			FStateTreeEditorNode& Node = Transition.Conditions[ConditionIndex];
			if (Node.ID.IsValid())
			{
				OutNodes.Add(Node.ID, {&Node, State, FString::Printf(TEXT("%s.transitions[%d].conditions[%d]"), *StatePath, TransitionIndex, ConditionIndex)});
			}
		}
	}

	for (UStateTreeState* Child : State->Children)
	{
		CollectEditorNodesForState(Child, OutNodes);
	}
}

static TMap<FGuid, FEditorNodeHandle> BuildEditorNodeIndex(UStateTreeEditorData* EditorData)
{
	TMap<FGuid, FEditorNodeHandle> Nodes;
	if (!EditorData)
	{
		return Nodes;
	}

	for (int32 Index = 0; Index < EditorData->Evaluators.Num(); ++Index)
	{
		FStateTreeEditorNode& Node = EditorData->Evaluators[Index];
		if (Node.ID.IsValid())
		{
			Nodes.Add(Node.ID, {&Node, EditorData, FString::Printf(TEXT("evaluators[%d]"), Index)});
		}
	}

	for (int32 Index = 0; Index < EditorData->GlobalTasks.Num(); ++Index)
	{
		FStateTreeEditorNode& Node = EditorData->GlobalTasks[Index];
		if (Node.ID.IsValid())
		{
			Nodes.Add(Node.ID, {&Node, EditorData, FString::Printf(TEXT("globalTasks[%d]"), Index)});
		}
	}

	for (UStateTreeState* RootState : EditorData->SubTrees)
	{
		CollectEditorNodesForState(RootState, Nodes);
	}

	return Nodes;
}

static void CollectTransitions(UStateTreeState* State,
                               TMap<FGuid, FTransitionHandle>& OutTransitions)
{
	if (!State)
	{
		return;
	}

	const FString StatePath = State->GetPath();
	for (int32 Index = 0; Index < State->Transitions.Num(); ++Index)
	{
		FStateTreeTransition& Transition = State->Transitions[Index];
		if (Transition.ID.IsValid())
		{
			OutTransitions.Add(Transition.ID, {&Transition, State, FString::Printf(TEXT("%s.transitions[%d]"), *StatePath, Index)});
		}
	}

	for (UStateTreeState* Child : State->Children)
	{
		CollectTransitions(Child, OutTransitions);
	}
}

static TMap<FGuid, FTransitionHandle> BuildTransitionIndex(UStateTreeEditorData* EditorData)
{
	TMap<FGuid, FTransitionHandle> Transitions;
	if (!EditorData)
	{
		return Transitions;
	}

	for (UStateTreeState* RootState : EditorData->SubTrees)
	{
		CollectTransitions(RootState, Transitions);
	}

	return Transitions;
}

static bool QueueLinkedStateSelector(const TSharedPtr<FJsonObject>& StateObject,
                                     FStateTreeStateLink& OutLink,
                                     TArray<FDeferredStateLink>& DeferredLinks,
                                     TArray<FString>& OutErrors,
                                     const FString& Path)
{
	const TSharedPtr<FJsonObject>* LinkObject = nullptr;
	if (!StateObject.IsValid()
		|| !StateObject->TryGetObjectField(TEXT("linkedSubtree"), LinkObject)
		|| !LinkObject
		|| !LinkObject->IsValid())
	{
		return true;
	}

	FStateSelector Selector;
	FString SelectorError;
	if (!ParseLinkedStateSelector(*LinkObject, Selector, SelectorError))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.linkedSubtree: %s"), *Path, *SelectorError));
		return false;
	}

	OutLink = FStateTreeStateLink(EStateTreeTransitionType::GotoState);
	DeferredLinks.Add({&OutLink, Selector, Path + TEXT(".linkedSubtree")});
	return true;
}

static bool TryGetTransitionTargetLinkType(const TSharedPtr<FJsonObject>& TransitionObject,
                                           EStateTreeTransitionType& OutLinkType,
                                           bool& bOutHasTargetState,
                                           TArray<FString>& OutErrors,
                                           const FString& Path)
{
	bOutHasTargetState = false;
	OutLinkType = EStateTreeTransitionType::GotoState;

	const TSharedPtr<FJsonObject>* TargetObject = nullptr;
	if (!TransitionObject.IsValid()
		|| !TransitionObject->TryGetObjectField(TEXT("targetState"), TargetObject)
		|| !TargetObject
		|| !TargetObject->IsValid())
	{
		return true;
	}

	bOutHasTargetState = true;

	FString LinkTypeString;
	if ((*TargetObject)->TryGetStringField(TEXT("linkType"), LinkTypeString)
		&& !LinkTypeString.IsEmpty()
		&& !TryParseEnumByName(StaticEnum<EStateTreeTransitionType>(), LinkTypeString, OutLinkType))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.targetState.linkType '%s' is invalid."), *Path, *LinkTypeString));
		return false;
	}

	return true;
}

static bool ValidateLinkedAssetTransitionTarget(UStateTreeState* OwnerState,
                                                const TSharedPtr<FJsonObject>& TransitionObject,
                                                TArray<FString>& OutErrors,
                                                const FString& Path)
{
	if (!OwnerState || OwnerState->Type != EStateTreeStateType::LinkedAsset)
	{
		return true;
	}

	EStateTreeTransitionType LinkType = EStateTreeTransitionType::GotoState;
	bool bHasTargetState = false;
	if (!TryGetTransitionTargetLinkType(TransitionObject, LinkType, bHasTargetState, OutErrors, Path))
	{
		return false;
	}

	if (!bHasTargetState || LinkType != EStateTreeTransitionType::GotoState)
	{
		return true;
	}

	OutErrors.Add(FString::Printf(
		TEXT("%s.targetState: LinkedAsset state '%s' does not support GotoState targetState selectors to peer states in the current tree. Unreal compiles these links as 'None'; use enterConditions on the destination states or a supported transition topology instead."),
		*Path,
		*OwnerState->GetPath()));
	return false;
}

static bool ApplyTransitionTarget(const TSharedPtr<FJsonObject>& TransitionObject,
                                  FStateTreeTransition& Transition,
                                  TArray<FDeferredStateLink>& DeferredLinks,
                                  TArray<FString>& OutErrors,
                                  const FString& Path)
{
	const TSharedPtr<FJsonObject>* TargetObject = nullptr;
	EStateTreeTransitionType LinkType = EStateTreeTransitionType::GotoState;
	bool bHasTargetState = false;
	if (!TryGetTransitionTargetLinkType(TransitionObject, LinkType, bHasTargetState, OutErrors, Path))
	{
		return false;
	}

	if (!bHasTargetState
		|| !TransitionObject.IsValid()
		|| !TransitionObject->TryGetObjectField(TEXT("targetState"), TargetObject)
		|| !TargetObject
		|| !TargetObject->IsValid())
	{
		return true;
	}

	Transition.State = FStateTreeStateLink(LinkType);
	if (LinkType != EStateTreeTransitionType::GotoState)
	{
		return OutErrors.Num() == 0;
	}

	FStateSelector Selector;
	FString SelectorError;
	if (!ParseStateSelector(*TargetObject, Selector, SelectorError))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.targetState: %s"), *Path, *SelectorError));
		return false;
	}

	DeferredLinks.Add({&Transition.State, Selector, Path + TEXT(".targetState")});
	return true;
}

static bool BuildStateRecursive(UObject* Owner,
                                UStateTreeState*& OutState,
                                const TSharedPtr<FJsonObject>& StateObject,
                                FTreeMutationScratch& Scratch,
                                TArray<FString>& OutErrors,
                                const FString& Path,
                                const bool bValidationOnly);

static bool BuildTransitionArray(UStateTreeState* OwnerState,
                                 const TArray<TSharedPtr<FJsonValue>>& TransitionValues,
                                 TArray<FStateTreeTransition>& OutTransitions,
                                 FTreeMutationScratch& Scratch,
                                 TArray<FString>& OutErrors,
                                 const FString& Path,
                                 const bool bValidationOnly)
{
	OutTransitions.Reset();

	for (int32 Index = 0; Index < TransitionValues.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> TransitionObject = TransitionValues[Index].IsValid() ? TransitionValues[Index]->AsObject() : nullptr;
		if (!TransitionObject.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s[%d] must be an object."), *Path, Index));
			continue;
		}

		FStateTreeTransition& Transition = OutTransitions.AddDefaulted_GetRef();

		FString GuidString;
		if ((TransitionObject->TryGetStringField(TEXT("transitionId"), GuidString)
			 || TransitionObject->TryGetStringField(TEXT("id"), GuidString))
			&& ParseGuidString(GuidString, Transition.ID))
		{
		}
		else
		{
			Transition.ID = FGuid::NewGuid();
		}

		bool bEnabled = false;
		if (TransitionObject->TryGetBoolField(TEXT("enabled"), bEnabled))
		{
			Transition.bTransitionEnabled = bEnabled;
		}

		FString TriggerString;
		if (TransitionObject->TryGetStringField(TEXT("trigger"), TriggerString)
			&& !TriggerString.IsEmpty()
			&& !TryParseEnumByName(StaticEnum<EStateTreeTransitionTrigger>(), TriggerString, Transition.Trigger))
		{
			OutErrors.Add(FString::Printf(TEXT("%s[%d].trigger '%s' is invalid."), *Path, Index, *TriggerString));
		}

		FString PriorityString;
		if (TransitionObject->TryGetStringField(TEXT("priority"), PriorityString)
			&& !PriorityString.IsEmpty()
			&& !TryParseEnumByName(StaticEnum<EStateTreeTransitionPriority>(), PriorityString, Transition.Priority))
		{
			OutErrors.Add(FString::Printf(TEXT("%s[%d].priority '%s' is invalid."), *Path, Index, *PriorityString));
		}

		double DelayDuration = 0.0;
		double DelayVariance = 0.0;
		const bool bHasDelayDuration = TransitionObject->TryGetNumberField(TEXT("delayDuration"), DelayDuration);
		const bool bHasDelayVariance = TransitionObject->TryGetNumberField(TEXT("delayRandomVariance"), DelayVariance);
		if (bHasDelayDuration)
		{
			Transition.DelayDuration = static_cast<float>(DelayDuration);
		}
		if (bHasDelayVariance)
		{
			Transition.DelayRandomVariance = static_cast<float>(DelayVariance);
		}
		Transition.bDelayTransition = bHasDelayDuration || bHasDelayVariance;

		if (const TSharedPtr<FJsonValue>* RequiredEventValue = TransitionObject->Values.Find(TEXT("requiredEvent"));
			RequiredEventValue)
		{
			bool bHasRequiredEvent = false;
			ApplyEventDesc(
				*RequiredEventValue,
				Transition.RequiredEvent,
				bHasRequiredEvent,
				OutErrors,
				FString::Printf(TEXT("%s[%d].requiredEvent"), *Path, Index));
		}

		if (const TArray<TSharedPtr<FJsonValue>>* Conditions = nullptr;
			TransitionObject->TryGetArrayField(TEXT("conditions"), Conditions) && Conditions)
		{
			BuildEditorNodeArray(
				*Conditions,
				OwnerState,
				Transition.Conditions,
				OutErrors,
				FString::Printf(TEXT("%s[%d].conditions"), *Path, Index),
				bValidationOnly);
		}

		const FString TransitionPath = FString::Printf(TEXT("%s[%d]"), *Path, Index);
		if (!ValidateLinkedAssetTransitionTarget(OwnerState, TransitionObject, OutErrors, TransitionPath))
		{
			continue;
		}

		ApplyTransitionTarget(
			TransitionObject,
			Transition,
			Scratch.DeferredLinks,
			OutErrors,
			TransitionPath);
	}

	return OutErrors.Num() == 0;
}

static bool ApplyStatePayload(UStateTreeState* State,
                              const TSharedPtr<FJsonObject>& StateObject,
                              FTreeMutationScratch& Scratch,
                              TArray<FString>& OutErrors,
                              const FString& Path,
                              const bool bValidationOnly,
                              const bool bIsPatch)
{
	if (!State || !StateObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s must be an object."), *Path));
		return false;
	}

	FString Name;
	if (StateObject->TryGetStringField(TEXT("newName"), Name) && !Name.IsEmpty())
	{
		State->Name = FName(*Name);
	}
	else if (StateObject->TryGetStringField(TEXT("name"), Name) && !Name.IsEmpty())
	{
		State->Name = FName(*Name);
	}

	if (!bIsPatch)
	{
		FString GuidString;
		if ((StateObject->TryGetStringField(TEXT("stateId"), GuidString) || StateObject->TryGetStringField(TEXT("id"), GuidString))
			&& !GuidString.IsEmpty()
			&& !ParseGuidString(GuidString, State->ID))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.id '%s' is invalid."), *Path, *GuidString));
		}
	}

	bool bEnabled = false;
	if (StateObject->TryGetBoolField(TEXT("enabled"), bEnabled))
	{
		State->bEnabled = bEnabled;
	}

	if (StateObject->HasField(TEXT("description")))
	{
		StateObject->TryGetStringField(TEXT("description"), State->Description);
	}

	if (StateObject->HasField(TEXT("tag")))
	{
		FString TagString;
		StateObject->TryGetStringField(TEXT("tag"), TagString);
		if (!ParseGameplayTagString(TagString, State->Tag))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.tag '%s' is not a registered gameplay tag."), *Path, *TagString));
		}
	}

	FString TypeString;
	if (StateObject->TryGetStringField(TEXT("type"), TypeString)
		&& !TypeString.IsEmpty()
		&& !TryParseEnumByName(StaticEnum<EStateTreeStateType>(), TypeString, State->Type))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.type '%s' is invalid."), *Path, *TypeString));
	}

	FString SelectionBehaviorString;
	if (StateObject->TryGetStringField(TEXT("selectionBehavior"), SelectionBehaviorString)
		&& !SelectionBehaviorString.IsEmpty()
		&& !TryParseEnumByName(StaticEnum<EStateTreeStateSelectionBehavior>(), SelectionBehaviorString, State->SelectionBehavior))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.selectionBehavior '%s' is invalid."), *Path, *SelectionBehaviorString));
	}

	if (StateObject->HasField(TEXT("linkedAsset")))
	{
		FString LinkedAssetPath;
		StateObject->TryGetStringField(TEXT("linkedAsset"), LinkedAssetPath);
		State->LinkedAsset = LinkedAssetPath.IsEmpty() ? nullptr : LoadObject<UStateTree>(nullptr, *LinkedAssetPath);
		if (!LinkedAssetPath.IsEmpty() && !State->LinkedAsset)
		{
			OutErrors.Add(FString::Printf(TEXT("%s.linkedAsset '%s' could not be resolved."), *Path, *LinkedAssetPath));
		}
	}

	if (const TSharedPtr<FJsonValue>* RequiredEventValue = StateObject->Values.Find(TEXT("requiredEventToEnter"));
		RequiredEventValue)
	{
		bool bHasRequiredEvent = false;
		ApplyEventDesc(*RequiredEventValue, State->RequiredEventToEnter, bHasRequiredEvent, OutErrors, Path + TEXT(".requiredEventToEnter"));
		State->bHasRequiredEventToEnter = bHasRequiredEvent;
	}

	if (State->Type == EStateTreeStateType::Linked)
	{
		QueueLinkedStateSelector(StateObject, State->LinkedSubtree, Scratch.DeferredLinks, OutErrors, Path);
	}
	else if (StateObject->HasField(TEXT("linkedSubtree")))
	{
		State->LinkedSubtree = FStateTreeStateLink();
	}

	if (const TArray<TSharedPtr<FJsonValue>>* EnterConditions = nullptr;
		StateObject->TryGetArrayField(TEXT("enterConditions"), EnterConditions) && EnterConditions)
	{
		BuildEditorNodeArray(*EnterConditions, State, State->EnterConditions, OutErrors, Path + TEXT(".enterConditions"), bValidationOnly);
	}

	if (const TArray<TSharedPtr<FJsonValue>>* Tasks = nullptr;
		StateObject->TryGetArrayField(TEXT("tasks"), Tasks) && Tasks)
	{
		BuildEditorNodeArray(*Tasks, State, State->Tasks, OutErrors, Path + TEXT(".tasks"), bValidationOnly);
	}

	// addTasks — append to existing tasks instead of replacing
	if (const TArray<TSharedPtr<FJsonValue>>* AddTasks = nullptr;
		StateObject->TryGetArrayField(TEXT("addTasks"), AddTasks) && AddTasks)
	{
		for (int32 Index = 0; Index < AddTasks->Num(); ++Index)
		{
			const TSharedPtr<FJsonObject> NodeObject = (*AddTasks)[Index].IsValid() ? (*AddTasks)[Index]->AsObject() : nullptr;
			FStateTreeEditorNode& NewNode = State->Tasks.AddDefaulted_GetRef();
			if (!BuildEditorNode(NewNode, State, NodeObject, OutErrors, FString::Printf(TEXT("%s.addTasks[%d]"), *Path, Index), bValidationOnly))
			{
				State->Tasks.Pop();
			}
		}
	}

	if (const TArray<TSharedPtr<FJsonValue>>* Considerations = nullptr;
		StateObject->TryGetArrayField(TEXT("considerations"), Considerations) && Considerations)
	{
		BuildEditorNodeArray(*Considerations, State, State->Considerations, OutErrors, Path + TEXT(".considerations"), bValidationOnly);
	}

	if (StateObject->HasField(TEXT("singleTask")))
	{
		const TSharedPtr<FJsonValue>* SingleTaskValue = StateObject->Values.Find(TEXT("singleTask"));
		if (SingleTaskValue && (*SingleTaskValue).IsValid() && (*SingleTaskValue)->Type != EJson::Null)
		{
			BuildEditorNode(State->SingleTask, State, (*SingleTaskValue)->AsObject(), OutErrors, Path + TEXT(".singleTask"), bValidationOnly);
		}
		else
		{
			State->SingleTask.Reset();
		}
	}

	if (const TArray<TSharedPtr<FJsonValue>>* Transitions = nullptr;
		StateObject->TryGetArrayField(TEXT("transitions"), Transitions) && Transitions)
	{
		BuildTransitionArray(State, *Transitions, State->Transitions, Scratch, OutErrors, Path + TEXT(".transitions"), bValidationOnly);
	}

	if (StateObject->HasField(TEXT("children")))
	{
		State->Children.Reset();
		const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
		if (StateObject->TryGetArrayField(TEXT("children"), Children) && Children)
		{
			for (int32 ChildIndex = 0; ChildIndex < Children->Num(); ++ChildIndex)
			{
				const TSharedPtr<FJsonObject> ChildObject = (*Children)[ChildIndex].IsValid() ? (*Children)[ChildIndex]->AsObject() : nullptr;
				UStateTreeState* ChildState = nullptr;
				if (BuildStateRecursive(State, ChildState, ChildObject, Scratch, OutErrors, FString::Printf(TEXT("%s.children[%d]"), *Path, ChildIndex), bValidationOnly))
				{
					ChildState->Parent = State;
					State->Children.Add(ChildState);
				}
			}
		}
	}

	// addChildren — append to existing children instead of replacing
	if (const TArray<TSharedPtr<FJsonValue>>* AddChildren = nullptr;
		StateObject->TryGetArrayField(TEXT("addChildren"), AddChildren) && AddChildren)
	{
		for (int32 ChildIndex = 0; ChildIndex < AddChildren->Num(); ++ChildIndex)
		{
			const TSharedPtr<FJsonObject> ChildObject = (*AddChildren)[ChildIndex].IsValid() ? (*AddChildren)[ChildIndex]->AsObject() : nullptr;
			UStateTreeState* ChildState = nullptr;
			if (BuildStateRecursive(State, ChildState, ChildObject, Scratch, OutErrors, FString::Printf(TEXT("%s.addChildren[%d]"), *Path, ChildIndex), bValidationOnly))
			{
				ChildState->Parent = State;
				State->Children.Add(ChildState);
			}
		}
	}

	return OutErrors.Num() == 0;
}

static bool BuildStateRecursive(UObject* Owner,
                                UStateTreeState*& OutState,
                                const TSharedPtr<FJsonObject>& StateObject,
                                FTreeMutationScratch& Scratch,
                                TArray<FString>& OutErrors,
                                const FString& Path,
                                const bool bValidationOnly)
{
	if (!StateObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s must be an object."), *Path));
		OutState = nullptr;
		return false;
	}

	OutState = NewObject<UStateTreeState>(Owner, NAME_None, RF_Transactional);
	if (!OutState)
	{
		OutErrors.Add(FString::Printf(TEXT("%s could not create a UStateTreeState."), *Path));
		return false;
	}

	return ApplyStatePayload(OutState, StateObject, Scratch, OutErrors, Path, bValidationOnly, false);
}

static bool ResolveDeferredLinks(UStateTreeEditorData* EditorData,
                                 FTreeMutationScratch& Scratch,
                                 TArray<FString>& OutErrors,
                                 const FStateIndex* SourceIndex = nullptr)
{
	TArray<FString> IndexErrors;
	const FStateIndex StateIndex = BuildStateIndex(EditorData, IndexErrors);
	OutErrors.Append(IndexErrors);

	for (FDeferredStateLink& DeferredLink : Scratch.DeferredLinks)
	{
		if (!DeferredLink.Link)
		{
			continue;
		}

		UStateTreeState* TargetState = ResolveIndexedState(StateIndex, DeferredLink.Selector, OutErrors, DeferredLink.Path, SourceIndex);
		if (!TargetState)
		{
			continue;
		}

		DeferredLink.Link->LinkType = EStateTreeTransitionType::GotoState;
		DeferredLink.Link->ID = TargetState->ID;
		DeferredLink.Link->Name = TargetState->Name;
	}

	return OutErrors.Num() == 0;
}

static bool ApplySchemaFromPayload(UStateTree* StateTree,
                                   const TSharedPtr<FJsonObject>& Payload,
                                   TArray<FString>& OutErrors,
                                   const bool bRequired)
{
	UClass* SchemaClass = ResolveSchemaClass(Payload, OutErrors, bRequired);
	if (!SchemaClass)
	{
		return !bRequired;
	}

	return EnsureEditorData(StateTree, SchemaClass, OutErrors) != nullptr;
}

static bool ReplaceTree(UStateTree* StateTree,
                        const TSharedPtr<FJsonObject>& Payload,
                        TArray<FString>& OutErrors,
                        const bool bValidationOnly)
{
	if (!ApplySchemaFromPayload(StateTree, Payload, OutErrors, false))
	{
		return false;
	}

	UStateTreeEditorData* EditorData = GetExistingEditorData(StateTree, OutErrors);
	if (!EditorData)
	{
		return false;
	}

	EditorData->Evaluators.Reset();
	EditorData->GlobalTasks.Reset();
	EditorData->SubTrees.Reset();

	if (const TArray<TSharedPtr<FJsonValue>>* Evaluators = nullptr;
		Payload.IsValid() && Payload->TryGetArrayField(TEXT("evaluators"), Evaluators) && Evaluators)
	{
		BuildEditorNodeArray(*Evaluators, EditorData, EditorData->Evaluators, OutErrors, TEXT("evaluators"), bValidationOnly);
	}

	if (const TArray<TSharedPtr<FJsonValue>>* GlobalTasks = nullptr;
		Payload.IsValid() && Payload->TryGetArrayField(TEXT("globalTasks"), GlobalTasks) && GlobalTasks)
	{
		BuildEditorNodeArray(*GlobalTasks, EditorData, EditorData->GlobalTasks, OutErrors, TEXT("globalTasks"), bValidationOnly);
	}

	FTreeMutationScratch Scratch;
	if (const TArray<TSharedPtr<FJsonValue>>* States = nullptr;
		Payload.IsValid() && Payload->TryGetArrayField(TEXT("states"), States) && States)
	{
		for (int32 Index = 0; Index < States->Num(); ++Index)
		{
			const TSharedPtr<FJsonObject> StateObject = (*States)[Index].IsValid() ? (*States)[Index]->AsObject() : nullptr;
			UStateTreeState* RootState = nullptr;
			if (BuildStateRecursive(EditorData, RootState, StateObject, Scratch, OutErrors, FString::Printf(TEXT("states[%d]"), Index), bValidationOnly))
			{
				RootState->Parent = nullptr;
				EditorData->SubTrees.Add(RootState);
			}
		}
	}

	if (EditorData->SubTrees.Num() == 0)
	{
		EditorData->AddRootState();
	}

	ResolveDeferredLinks(EditorData, Scratch, OutErrors);

	// Apply bindings if provided
	if (const TSharedPtr<FJsonObject>* BindingsObj = nullptr;
		Payload.IsValid() && Payload->TryGetObjectField(TEXT("bindings"), BindingsObj)
		&& BindingsObj && BindingsObj->IsValid())
	{
		const TArray<TSharedPtr<FJsonValue>>* BindingValues = nullptr;
		if ((*BindingsObj)->TryGetArrayField(TEXT("propertyBindings"), BindingValues) && BindingValues)
		{
			ApplyBindingsFromJson(EditorData, *BindingValues, OutErrors, TEXT("bindings.propertyBindings"));
		}
	}

	return OutErrors.Num() == 0;
}

static bool PatchState(UStateTree* StateTree,
                       const TSharedPtr<FJsonObject>& Payload,
                       TArray<FString>& OutErrors,
                       const bool bValidationOnly,
                       const FStateIndex* CurrentIndex = nullptr,
                       const FStateIndex* SourceIndex = nullptr)
{
	UStateTreeEditorData* EditorData = GetExistingEditorData(StateTree, OutErrors);
	if (!EditorData)
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* StateObject = nullptr;
	TSharedPtr<FJsonObject> EffectivePayload = Payload;
	if (Payload.IsValid() && Payload->TryGetObjectField(TEXT("state"), StateObject) && StateObject && StateObject->IsValid())
	{
		EffectivePayload = *StateObject;
	}

	FStateSelector Selector;
	FString SelectorError;
	TSharedPtr<FJsonObject> SelectorSource = Payload;
	if (Payload->HasField(TEXT("selector")))
	{
		SelectorSource = Payload->GetObjectField(TEXT("selector"));
	}
	if (!ParseStateSelector(SelectorSource, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	TArray<FString> IndexErrors;
	FStateIndex BuiltIndex;
	const FStateIndex* EffectiveIndex = CurrentIndex;
	if (!EffectiveIndex)
	{
		BuiltIndex = BuildStateIndex(EditorData, IndexErrors);
		EffectiveIndex = &BuiltIndex;
	}
	OutErrors.Append(IndexErrors);
	UStateTreeState* TargetState = ResolveIndexedState(*EffectiveIndex, Selector, OutErrors, TEXT("patch_state"), SourceIndex);
	if (!TargetState)
	{
		return false;
	}

	FTreeMutationScratch Scratch;
	ApplyStatePayload(TargetState, EffectivePayload, Scratch, OutErrors, TargetState->GetPath(), bValidationOnly, true);
	ResolveDeferredLinks(EditorData, Scratch, OutErrors, SourceIndex);

	// Apply bindings if provided (from the original Payload, not EffectivePayload).
	// This allows callers to create tasks (with pre-assigned ids) and wire their
	// bindings in a single patch_state call.
	// Supports both nested format (bindings.propertyBindings) and flat format
	// (propertyBindings at the Payload root), matching the set_bindings/add_binding
	// conventions.
	if (Payload.IsValid())
	{
		const TArray<TSharedPtr<FJsonValue>>* BindingValues = nullptr;
		bool bFoundBindings = false;

		// Try nested: payload.bindings.propertyBindings
		if (const TSharedPtr<FJsonObject>* BindingsObj = nullptr;
			Payload->TryGetObjectField(TEXT("bindings"), BindingsObj)
			&& BindingsObj && BindingsObj->IsValid())
		{
			if ((*BindingsObj)->TryGetArrayField(TEXT("propertyBindings"), BindingValues) && BindingValues)
			{
				bFoundBindings = true;
				ApplyBindingsFromJson(EditorData, *BindingValues, OutErrors, TEXT("bindings.propertyBindings"));
			}
		}

		// Fallback: flat payload.propertyBindings (same format as set_bindings/add_binding)
		if (!bFoundBindings
			&& Payload->TryGetArrayField(TEXT("propertyBindings"), BindingValues)
			&& BindingValues)
		{
			ApplyBindingsFromJson(EditorData, *BindingValues, OutErrors, TEXT("propertyBindings"));
		}
	}

	return OutErrors.Num() == 0;
}

static bool PatchEditorNode(UStateTree* StateTree,
                            const TSharedPtr<FJsonObject>& Payload,
                            TArray<FString>& OutErrors,
                            const bool bValidationOnly)
{
	UStateTreeEditorData* EditorData = GetExistingEditorData(StateTree, OutErrors);
	if (!EditorData)
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* NodeObject = nullptr;
	TSharedPtr<FJsonObject> EffectivePayload = Payload;
	if (Payload.IsValid() && Payload->TryGetObjectField(TEXT("editorNode"), NodeObject) && NodeObject && NodeObject->IsValid())
	{
		EffectivePayload = *NodeObject;
	}

	FEditorNodeSelector Selector;
	FString SelectorError;
	TSharedPtr<FJsonObject> SelectorSource = Payload;
	if (Payload.IsValid() && Payload->HasField(TEXT("selector")))
	{
		SelectorSource = Payload->GetObjectField(TEXT("selector"));
	}
	if (!ParseEditorNodeSelector(SelectorSource, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	TMap<FGuid, FEditorNodeHandle> NodeIndex = BuildEditorNodeIndex(EditorData);
	FEditorNodeHandle* ExistingHandle = NodeIndex.Find(Selector.EditorNodeId);
	if (!ExistingHandle || !ExistingHandle->Node || !ExistingHandle->Owner)
	{
		OutErrors.Add(FString::Printf(TEXT("Editor node '%s' was not found."), *Selector.EditorNodeId.ToString()));
		return false;
	}

	const UScriptStruct* CurrentStruct = ExistingHandle->Node->Node.GetScriptStruct();
	const FString CurrentInstanceClassPath = ExistingHandle->Node->InstanceObject ? ExistingHandle->Node->InstanceObject->GetClass()->GetPathName() : FString();
	FString RequestedStructPath;
	const bool bHasRequestedStruct = EffectivePayload->TryGetStringField(TEXT("nodeStructType"), RequestedStructPath) && !RequestedStructPath.IsEmpty();
	FString RequestedInstanceClassPath;
	const bool bHasRequestedInstanceClass = EffectivePayload->TryGetStringField(TEXT("instanceObjectClass"), RequestedInstanceClassPath) && !RequestedInstanceClassPath.IsEmpty();

	const bool bRequiresRebuild =
		!CurrentStruct
		|| (bHasRequestedStruct && CurrentStruct->GetPathName() != RequestedStructPath)
		|| (bHasRequestedInstanceClass && CurrentInstanceClassPath != RequestedInstanceClassPath);

	if (bRequiresRebuild)
	{
		FStateTreeEditorNode ReplacementNode;
		if (!BuildEditorNode(ReplacementNode, ExistingHandle->Owner, EffectivePayload, OutErrors, ExistingHandle->Path, bValidationOnly, &ExistingHandle->Node->ID))
		{
			return false;
		}
		*ExistingHandle->Node = MoveTemp(ReplacementNode);
		return OutErrors.Num() == 0;
	}

	FString OperandString;
	if (EffectivePayload->TryGetStringField(TEXT("expressionOperand"), OperandString)
		&& !OperandString.IsEmpty()
		&& !TryParseEnumByName(StaticEnum<EStateTreeExpressionOperand>(), OperandString, ExistingHandle->Node->ExpressionOperand))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.expressionOperand '%s' is invalid."), *ExistingHandle->Path, *OperandString));
	}

	int32 ExpressionIndent = 0;
	if (EffectivePayload->TryGetNumberField(TEXT("expressionIndent"), ExpressionIndent))
	{
		ExistingHandle->Node->ExpressionIndent = static_cast<uint8>(FMath::Clamp(ExpressionIndent, 0, UE::StateTree::MaxExpressionIndent));
	}

	if (const TSharedPtr<FJsonObject>* NodeProperties = nullptr;
		EffectivePayload->TryGetObjectField(TEXT("nodeProperties"), NodeProperties) && NodeProperties && NodeProperties->IsValid())
	{
		ApplyStructPropertyObject(
			ExistingHandle->Node->Node.GetScriptStruct(),
			ExistingHandle->Node->Node.GetMutableMemory(),
			*NodeProperties,
			OutErrors,
			ExistingHandle->Path + TEXT(".nodeProperties"),
			bValidationOnly);
	}

	if (const TSharedPtr<FJsonObject>* InstanceProperties = nullptr;
		EffectivePayload->TryGetObjectField(TEXT("instanceProperties"), InstanceProperties) && InstanceProperties && InstanceProperties->IsValid())
	{
		if (ExistingHandle->Node->Instance.IsValid())
		{
			ApplyStructPropertyObject(
				ExistingHandle->Node->Instance.GetScriptStruct(),
				ExistingHandle->Node->Instance.GetMutableMemory(),
				*InstanceProperties,
				OutErrors,
				ExistingHandle->Path + TEXT(".instanceProperties"),
				bValidationOnly);
		}
		else if (ExistingHandle->Node->InstanceObject)
		{
			ApplyObjectProperties(
				ExistingHandle->Node->InstanceObject,
				*InstanceProperties,
				OutErrors,
				ExistingHandle->Path + TEXT(".instanceProperties"),
				bValidationOnly);
		}
	}

	FString DisplayName;
	if (EffectivePayload->TryGetStringField(TEXT("name"), DisplayName) && !DisplayName.IsEmpty())
	{
		if (FStateTreeNodeBase* NodeBase = ExistingHandle->Node->Node.GetMutablePtr<FStateTreeNodeBase>())
		{
			NodeBase->Name = FName(*DisplayName);
		}
	}

	return OutErrors.Num() == 0;
}

static bool PatchTransition(UStateTree* StateTree,
                            const TSharedPtr<FJsonObject>& Payload,
                            TArray<FString>& OutErrors,
                            const bool bValidationOnly,
                            const FStateIndex* SourceIndex = nullptr)
{
	UStateTreeEditorData* EditorData = GetExistingEditorData(StateTree, OutErrors);
	if (!EditorData)
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* TransitionObject = nullptr;
	TSharedPtr<FJsonObject> EffectivePayload = Payload;
	if (Payload.IsValid() && Payload->TryGetObjectField(TEXT("transition"), TransitionObject) && TransitionObject && TransitionObject->IsValid())
	{
		EffectivePayload = *TransitionObject;
	}

	FTransitionSelector Selector;
	FString SelectorError;
	TSharedPtr<FJsonObject> SelectorSource = Payload;
	if (Payload.IsValid() && Payload->HasField(TEXT("selector")))
	{
		SelectorSource = Payload->GetObjectField(TEXT("selector"));
	}
	if (!ParseTransitionSelector(SelectorSource, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	TMap<FGuid, FTransitionHandle> TransitionIndex = BuildTransitionIndex(EditorData);
	FTransitionHandle* ExistingHandle = TransitionIndex.Find(Selector.TransitionId);
	if (!ExistingHandle || !ExistingHandle->Transition || !ExistingHandle->OwnerState)
	{
		OutErrors.Add(FString::Printf(TEXT("Transition '%s' was not found."), *Selector.TransitionId.ToString()));
		return false;
	}

	bool bEnabled = false;
	if (EffectivePayload->TryGetBoolField(TEXT("enabled"), bEnabled))
	{
		ExistingHandle->Transition->bTransitionEnabled = bEnabled;
	}

	FString TriggerString;
	if (EffectivePayload->TryGetStringField(TEXT("trigger"), TriggerString)
		&& !TriggerString.IsEmpty()
		&& !TryParseEnumByName(StaticEnum<EStateTreeTransitionTrigger>(), TriggerString, ExistingHandle->Transition->Trigger))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.trigger '%s' is invalid."), *ExistingHandle->Path, *TriggerString));
	}

	FString PriorityString;
	if (EffectivePayload->TryGetStringField(TEXT("priority"), PriorityString)
		&& !PriorityString.IsEmpty()
		&& !TryParseEnumByName(StaticEnum<EStateTreeTransitionPriority>(), PriorityString, ExistingHandle->Transition->Priority))
	{
		OutErrors.Add(FString::Printf(TEXT("%s.priority '%s' is invalid."), *ExistingHandle->Path, *PriorityString));
	}

	if (const TSharedPtr<FJsonValue>* RequiredEventValue = EffectivePayload->Values.Find(TEXT("requiredEvent"));
		RequiredEventValue)
	{
		bool bHasRequiredEvent = false;
		ApplyEventDesc(*RequiredEventValue, ExistingHandle->Transition->RequiredEvent, bHasRequiredEvent, OutErrors, ExistingHandle->Path + TEXT(".requiredEvent"));
	}

	double DelayDuration = 0.0;
	double DelayVariance = 0.0;
	const bool bHasDelayDuration = EffectivePayload->TryGetNumberField(TEXT("delayDuration"), DelayDuration);
	const bool bHasDelayVariance = EffectivePayload->TryGetNumberField(TEXT("delayRandomVariance"), DelayVariance);
	if (bHasDelayDuration)
	{
		ExistingHandle->Transition->DelayDuration = static_cast<float>(DelayDuration);
	}
	if (bHasDelayVariance)
	{
		ExistingHandle->Transition->DelayRandomVariance = static_cast<float>(DelayVariance);
	}
	if (bHasDelayDuration || bHasDelayVariance)
	{
		ExistingHandle->Transition->bDelayTransition = bHasDelayDuration || bHasDelayVariance;
	}

	if (const TArray<TSharedPtr<FJsonValue>>* Conditions = nullptr;
		EffectivePayload->TryGetArrayField(TEXT("conditions"), Conditions) && Conditions)
	{
		BuildEditorNodeArray(*Conditions, ExistingHandle->OwnerState, ExistingHandle->Transition->Conditions, OutErrors, ExistingHandle->Path + TEXT(".conditions"), bValidationOnly);
	}

	if (EffectivePayload->HasField(TEXT("targetState")))
	{
		if (!ValidateLinkedAssetTransitionTarget(ExistingHandle->OwnerState, EffectivePayload, OutErrors, ExistingHandle->Path))
		{
			return false;
		}

		FTreeMutationScratch Scratch;
		ApplyTransitionTarget(EffectivePayload, *ExistingHandle->Transition, Scratch.DeferredLinks, OutErrors, ExistingHandle->Path);
		ResolveDeferredLinks(EditorData, Scratch, OutErrors, SourceIndex);
	}

	return OutErrors.Num() == 0;
}

static bool SetSchema(UStateTree* StateTree,
                      const TSharedPtr<FJsonObject>& Payload,
                      TArray<FString>& OutErrors)
{
	UClass* SchemaClass = ResolveSchemaClass(Payload, OutErrors, true);
	return SchemaClass && EnsureEditorData(StateTree, SchemaClass, OutErrors) != nullptr;
}

static bool ParsePropertyPathFromJson(const TSharedPtr<FJsonObject>& PathObject,
                                      FPropertyBindingPath& OutPath,
                                      TArray<FString>& OutErrors,
                                      const FString& Path)
{
	if (!PathObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s must be an object."), *Path));
		return false;
	}

#if WITH_EDITORONLY_DATA
	FString StructIdString;
	if (PathObject->TryGetStringField(TEXT("structId"), StructIdString) && !StructIdString.IsEmpty())
	{
		FGuid StructId;
		if (ParseGuidString(StructIdString, StructId))
		{
			OutPath.SetStructID(StructId);
		}
		else
		{
			OutErrors.Add(FString::Printf(TEXT("%s.structId '%s' is not a valid GUID."), *Path, *StructIdString));
			return false;
		}
	}
#endif

	const TArray<TSharedPtr<FJsonValue>>* Segments = nullptr;
	if (PathObject->TryGetArrayField(TEXT("segments"), Segments) && Segments)
	{
		for (int32 Index = 0; Index < Segments->Num(); ++Index)
		{
			const TSharedPtr<FJsonObject> SegObj = (*Segments)[Index].IsValid() ? (*Segments)[Index]->AsObject() : nullptr;
			if (!SegObj.IsValid())
			{
				OutErrors.Add(FString::Printf(TEXT("%s.segments[%d] must be an object."), *Path, Index));
				continue;
			}

			FString SegName;
			if (!SegObj->TryGetStringField(TEXT("name"), SegName) || SegName.IsEmpty())
			{
				OutErrors.Add(FString::Printf(TEXT("%s.segments[%d].name is required."), *Path, Index));
				continue;
			}

			int32 ArrayIndex = INDEX_NONE;
			double ArrayIndexDouble = 0;
			if (SegObj->TryGetNumberField(TEXT("arrayIndex"), ArrayIndexDouble))
			{
				ArrayIndex = static_cast<int32>(ArrayIndexDouble);
			}

			const UStruct* InstanceStruct = nullptr;
			FString InstanceStructPath;
			if (SegObj->TryGetStringField(TEXT("instanceStruct"), InstanceStructPath) && !InstanceStructPath.IsEmpty())
			{
				InstanceStruct = FAuthoringHelpers::ResolveScriptStruct(InstanceStructPath);
				if (!InstanceStruct)
				{
					InstanceStruct = FAuthoringHelpers::ResolveClass(InstanceStructPath, nullptr);
				}
				if (!InstanceStruct)
				{
					OutErrors.Add(FString::Printf(TEXT("%s.segments[%d].instanceStruct '%s' could not be resolved."),
						*Path, Index, *InstanceStructPath));
				}
			}

			OutPath.AddPathSegment(FName(*SegName), ArrayIndex, InstanceStruct);
		}
	}

	return OutErrors.Num() == 0;
}

static bool ApplyBindingsFromJson(UStateTreeEditorData* EditorData,
                                  const TArray<TSharedPtr<FJsonValue>>& BindingValues,
                                  TArray<FString>& OutErrors,
                                  const FString& Path)
{
	if (!EditorData)
	{
		OutErrors.Add(TEXT("EditorData is null."));
		return false;
	}

	FStateTreeEditorPropertyBindings* Bindings = EditorData->GetPropertyEditorBindings();
	if (!Bindings)
	{
		OutErrors.Add(TEXT("Could not get property editor bindings."));
		return false;
	}

	for (int32 Index = 0; Index < BindingValues.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> BindingObj = BindingValues[Index].IsValid() ? BindingValues[Index]->AsObject() : nullptr;
		if (!BindingObj.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s[%d] must be an object."), *Path, Index));
			continue;
		}

		const TSharedPtr<FJsonObject>* SourcePathObj = nullptr;
		const TSharedPtr<FJsonObject>* TargetPathObj = nullptr;
		if (!BindingObj->TryGetObjectField(TEXT("sourcePath"), SourcePathObj) || !SourcePathObj || !SourcePathObj->IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s[%d].sourcePath is required."), *Path, Index));
			continue;
		}
		if (!BindingObj->TryGetObjectField(TEXT("targetPath"), TargetPathObj) || !TargetPathObj || !TargetPathObj->IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s[%d].targetPath is required."), *Path, Index));
			continue;
		}

		FPropertyBindingPath SourcePath;
		FPropertyBindingPath TargetPath;

		TArray<FString> PathErrors;
		ParsePropertyPathFromJson(*SourcePathObj, SourcePath, PathErrors, FString::Printf(TEXT("%s[%d].sourcePath"), *Path, Index));
		ParsePropertyPathFromJson(*TargetPathObj, TargetPath, PathErrors, FString::Printf(TEXT("%s[%d].targetPath"), *Path, Index));
		OutErrors.Append(PathErrors);

		if (PathErrors.Num() == 0)
		{
			Bindings->AddBinding(SourcePath, TargetPath);
		}
	}

	return OutErrors.Num() == 0;
}

static bool SetBindings(UStateTree* StateTree,
                        const TSharedPtr<FJsonObject>& Payload,
                        TArray<FString>& OutErrors,
                        const bool bValidationOnly)
{
	UStateTreeEditorData* EditorData = GetExistingEditorData(StateTree, OutErrors);
	if (!EditorData)
	{
		return false;
	}

	FStateTreeEditorPropertyBindings* Bindings = EditorData->GetPropertyEditorBindings();
	if (!Bindings)
	{
		OutErrors.Add(TEXT("Could not get property editor bindings."));
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* BindingValues = nullptr;
	if (!Payload.IsValid()
		|| !Payload->TryGetArrayField(TEXT("propertyBindings"), BindingValues)
		|| !BindingValues)
	{
		OutErrors.Add(TEXT("set_bindings requires a 'propertyBindings' array."));
		return false;
	}

	if (!bValidationOnly)
	{
		// Clear existing bindings by removing all
		Bindings->RemoveBindings([](FPropertyBindingBinding&) { return true; });
	}

	return ApplyBindingsFromJson(EditorData, *BindingValues, OutErrors, TEXT("propertyBindings"));
}

static bool AddBinding(UStateTree* StateTree,
                       const TSharedPtr<FJsonObject>& Payload,
                       TArray<FString>& OutErrors,
                       const bool bValidationOnly)
{
	UStateTreeEditorData* EditorData = GetExistingEditorData(StateTree, OutErrors);
	if (!EditorData)
	{
		return false;
	}

	if (!Payload.IsValid())
	{
		OutErrors.Add(TEXT("add_binding requires a payload."));
		return false;
	}

	// Support both single binding and array of bindings
	const TArray<TSharedPtr<FJsonValue>>* BindingValues = nullptr;
	if (Payload->TryGetArrayField(TEXT("propertyBindings"), BindingValues) && BindingValues)
	{
		return ApplyBindingsFromJson(EditorData, *BindingValues, OutErrors, TEXT("propertyBindings"));
	}

	// Single binding specified at the top level
	const TSharedPtr<FJsonObject>* SourcePathObj = nullptr;
	const TSharedPtr<FJsonObject>* TargetPathObj = nullptr;
	if (Payload->TryGetObjectField(TEXT("sourcePath"), SourcePathObj)
		&& Payload->TryGetObjectField(TEXT("targetPath"), TargetPathObj)
		&& SourcePathObj && SourcePathObj->IsValid()
		&& TargetPathObj && TargetPathObj->IsValid())
	{
		TArray<TSharedPtr<FJsonValue>> SingleArray;
		SingleArray.Add(MakeShared<FJsonValueObject>(Payload));
		return ApplyBindingsFromJson(EditorData, SingleArray, OutErrors, TEXT("binding"));
	}

	OutErrors.Add(TEXT("add_binding requires either 'propertyBindings' array or 'sourcePath'/'targetPath' objects."));
	return false;
}

static bool RemoveBinding(UStateTree* StateTree,
                          const TSharedPtr<FJsonObject>& Payload,
                          TArray<FString>& OutErrors,
                          const bool bValidationOnly)
{
	UStateTreeEditorData* EditorData = GetExistingEditorData(StateTree, OutErrors);
	if (!EditorData)
	{
		return false;
	}

	FStateTreeEditorPropertyBindings* Bindings = EditorData->GetPropertyEditorBindings();
	if (!Bindings)
	{
		OutErrors.Add(TEXT("Could not get property editor bindings."));
		return false;
	}

	if (!Payload.IsValid())
	{
		OutErrors.Add(TEXT("remove_binding requires a payload."));
		return false;
	}

	const TSharedPtr<FJsonObject>* TargetPathObj = nullptr;
	if (!Payload->TryGetObjectField(TEXT("targetPath"), TargetPathObj) || !TargetPathObj || !TargetPathObj->IsValid())
	{
		OutErrors.Add(TEXT("remove_binding requires a 'targetPath' object."));
		return false;
	}

	FPropertyBindingPath TargetPath;
	ParsePropertyPathFromJson(*TargetPathObj, TargetPath, OutErrors, TEXT("targetPath"));
	if (OutErrors.Num() > 0)
	{
		return false;
	}

	if (!bValidationOnly)
	{
		Bindings->RemoveBindings(TargetPath);
	}

	return true;
}

static bool ApplyOperation(UStateTree* StateTree,
                           const FString& Operation,
                           const TSharedPtr<FJsonObject>& Payload,
                           TArray<FString>& OutErrors,
                           const bool bValidationOnly,
                           const FStateIndex* CurrentIndex = nullptr,
                           const FStateIndex* SourceIndex = nullptr)
{
	if (Operation == TEXT("replace_tree"))
	{
		return ReplaceTree(StateTree, Payload, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("patch_state"))
	{
		return PatchState(StateTree, Payload, OutErrors, bValidationOnly, CurrentIndex, SourceIndex);
	}
	if (Operation == TEXT("patch_editor_node"))
	{
		return PatchEditorNode(StateTree, Payload, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("patch_transition"))
	{
		return PatchTransition(StateTree, Payload, OutErrors, bValidationOnly, SourceIndex);
	}
	if (Operation == TEXT("set_schema"))
	{
		return SetSchema(StateTree, Payload, OutErrors);
	}
	if (Operation == TEXT("set_bindings"))
	{
		return SetBindings(StateTree, Payload, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("add_binding"))
	{
		return AddBinding(StateTree, Payload, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("remove_binding"))
	{
		return RemoveBinding(StateTree, Payload, OutErrors, bValidationOnly);
	}

	OutErrors.Add(FString::Printf(TEXT("Unsupported StateTree operation '%s'."), *Operation));
	return false;
}

} // namespace StateTreeAuthoringInternal

TSharedPtr<FJsonObject> FStateTreeAuthoring::Create(const FString& AssetPath,
                                                    const TSharedPtr<FJsonObject>& PayloadJson,
                                                    const bool bValidateOnly)
{
	using namespace StateTreeAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_state_tree"), AssetPath, TEXT("StateTree"), bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
			FString::Printf(TEXT("[Step 1/4: Pre-check] Asset already exists at '%s'. "
				"Use modify_state_tree to update an existing StateTree, or choose a different path."),
				*AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	TArray<FString> PreviewErrors;
	UStateTree* PreviewTree = CreateTransientStateTree(Payload, PreviewErrors);
	for (const FString& Error : PreviewErrors)
	{
		Context.AddError(TEXT("validation_error"),
			FString::Printf(TEXT("[Step 2/4: Preview Validation] %s"), *Error),
			AssetPath);
	}
	if (!PreviewTree)
	{
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	ApplyOperation(PreviewTree, TEXT("replace_tree"), Payload, ValidationErrors, true);
	if (ValidationErrors.Num() > 0)
	{
		Context.SetValidationSummary(false, TEXT("[Step 2/4: Preview Validation] StateTree payload failed validation."), ValidationErrors);
		for (const FString& Error : ValidationErrors)
		{
			Context.AddError(TEXT("validation_error"),
				FString::Printf(TEXT("[Step 2/4: Preview Validation] %s"), *Error),
				AssetPath);
		}
		return Context.BuildResult(false);
	}

	if (!ValidateAndCompile(PreviewTree, Context, TEXT("StateTree payload validated."), TEXT("[Step 2/4: Preview Validation] StateTree payload failed compile validation.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create StateTree")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
			FString::Printf(TEXT("[Step 3/4: Asset Creation] Failed to create package for '%s'. "
				"Verify the path is valid and the parent directory exists."),
				*AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UStateTree* StateTree = NewObject<UStateTree>(Package, AssetName, RF_Public | RF_Standalone | RF_Transactional);
	if (!StateTree)
	{
		Context.AddError(TEXT("asset_create_failed"),
			FString::Printf(TEXT("[Step 3/4: Asset Creation] Failed to create StateTree object '%s' in package '%s'. "
				"The object name may conflict with an existing object."),
				*AssetName.ToString(), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	StateTree->Modify();
	if (!ApplySchemaFromPayload(StateTree, Payload, ValidationErrors, true))
	{
		for (const FString& Error : ValidationErrors)
		{
			Context.AddError(TEXT("apply_error"),
				FString::Printf(TEXT("[Step 3/4: Asset Creation — Schema Application] %s"), *Error),
				AssetPath);
		}
		return Context.BuildResult(false);
	}

	if (UStateTreeEditorData* EditorData = GetExistingEditorData(StateTree, ValidationErrors))
	{
		EditorData->Modify();
	}

	ValidationErrors.Reset();
	ApplyOperation(StateTree, TEXT("replace_tree"), Payload, ValidationErrors, false);
	if (ValidationErrors.Num() > 0)
	{
		for (const FString& Error : ValidationErrors)
		{
			Context.AddError(TEXT("apply_error"),
				FString::Printf(TEXT("[Step 3/4: Asset Creation — Tree Population] %s"), *Error),
				AssetPath);
		}
		return Context.BuildResult(false);
	}

	if (!ValidateAndCompile(StateTree, Context, TEXT("StateTree compiled successfully."), TEXT("[Step 4/4: Final Compile] StateTree compile failed after asset creation.")))
	{
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(StateTree);
	StateTree->MarkPackageDirty();
	Context.TrackDirtyObject(StateTree);
	if (StateTree->EditorData)
	{
		Context.TrackChangedObject(StateTree->EditorData);
	}

	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FStateTreeAuthoring::Modify(UStateTree* StateTree,
                                                    const FString& Operation,
                                                    const TSharedPtr<FJsonObject>& PayloadJson,
                                                    const bool bValidateOnly)
{
	using namespace StateTreeAuthoringInternal;

	const FString AssetPath = StateTree ? StateTree->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_state_tree"), AssetPath, TEXT("StateTree"), bValidateOnly);

	if (!StateTree)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("StateTree is null."));
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);
	const bool bNeedsStateSelectorRemap = Operation == TEXT("patch_state") || Operation == TEXT("patch_transition");

	FStateIndex SourceStateIndex;
	const FStateIndex* SourceStateIndexPtr = nullptr;
	if (bNeedsStateSelectorRemap)
	{
		TArray<FString> SourceIndexErrors;
		if (UStateTreeEditorData* SourceEditorData = GetExistingEditorData(StateTree, SourceIndexErrors))
		{
			SourceStateIndex = BuildStateIndex(SourceEditorData, SourceIndexErrors);
		}
		for (const FString& Error : SourceIndexErrors)
		{
			Context.AddError(TEXT("source_state_index_error"), Error, AssetPath);
		}
		if (SourceIndexErrors.Num() > 0)
		{
			return Context.BuildResult(false);
		}
		SourceStateIndexPtr = &SourceStateIndex;
	}

	UStateTree* WorkingTree = DuplicateObject<UStateTree>(StateTree, GetTransientPackage());
	if (!WorkingTree)
	{
		Context.AddError(TEXT("preview_duplicate_failed"), TEXT("Failed to duplicate StateTree for validation."));
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	FStateIndex PreviewStateIndex;
	const FStateIndex* PreviewStateIndexPtr = nullptr;
	if (bNeedsStateSelectorRemap)
	{
		TArray<FString> PreviewIndexErrors;
		if (UStateTreeEditorData* PreviewEditorData = GetExistingEditorData(WorkingTree, PreviewIndexErrors))
		{
			PreviewStateIndex = BuildStateIndex(PreviewEditorData, PreviewIndexErrors);
		}
		ValidationErrors.Append(PreviewIndexErrors);
		if (ValidationErrors.Num() > 0)
		{
			Context.SetValidationSummary(false, TEXT("StateTree payload failed validation."), ValidationErrors);
			for (const FString& Error : ValidationErrors)
			{
				Context.AddError(TEXT("validation_error"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
		PreviewStateIndexPtr = &PreviewStateIndex;
	}

	ApplyOperation(WorkingTree, Operation, Payload, ValidationErrors, true, PreviewStateIndexPtr, SourceStateIndexPtr);
	if (ValidationErrors.Num() > 0)
	{
		Context.SetValidationSummary(false, TEXT("StateTree payload failed validation."), ValidationErrors);
		for (const FString& Error : ValidationErrors)
		{
			Context.AddError(TEXT("validation_error"), Error, AssetPath);
		}
		return Context.BuildResult(false);
	}

	if (!ValidateAndCompile(WorkingTree, Context, TEXT("StateTree payload validated."), TEXT("StateTree payload failed validation.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify StateTree")));
	StateTree->Modify();
	if (UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData))
	{
		EditorData->Modify();
	}

	ValidationErrors.Reset();
	FStateIndex CurrentStateIndex;
	const FStateIndex* CurrentStateIndexPtr = nullptr;
	if (bNeedsStateSelectorRemap)
	{
		TArray<FString> CurrentIndexErrors;
		if (UStateTreeEditorData* CurrentEditorData = GetExistingEditorData(StateTree, CurrentIndexErrors))
		{
			CurrentStateIndex = BuildStateIndex(CurrentEditorData, CurrentIndexErrors);
		}
		ValidationErrors.Append(CurrentIndexErrors);
		if (ValidationErrors.Num() > 0)
		{
			for (const FString& Error : ValidationErrors)
			{
				Context.AddError(TEXT("apply_error"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
		CurrentStateIndexPtr = &CurrentStateIndex;
	}

	ApplyOperation(StateTree, Operation, Payload, ValidationErrors, false, CurrentStateIndexPtr, SourceStateIndexPtr);
	if (ValidationErrors.Num() > 0)
	{
		for (const FString& Error : ValidationErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, AssetPath);
		}
		return Context.BuildResult(false);
	}

	if (!ValidateAndCompile(StateTree, Context, TEXT("StateTree compiled successfully."), TEXT("StateTree compile failed.")))
	{
		return Context.BuildResult(false);
	}

	StateTree->MarkPackageDirty();
	Context.TrackDirtyObject(StateTree);
	if (StateTree->EditorData)
	{
		Context.TrackChangedObject(StateTree->EditorData);
	}

	return Context.BuildResult(true);
}
