#include "Authoring/BlueprintAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"
#include "PropertySerializer.h"

#include "AnimGraphNode_Base.h"
#include "AnimationGraphSchema.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimInstance.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "BaseWidgetBlueprint.h"
#include "Components/ActorComponent.h"
#include "Components/Widget.h"
#include "EdGraphSchema_K2_Actions.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/LevelScriptActor.h"
#include "Engine/MemberReference.h"
#include "Engine/SCS_Node.h"
#include "Engine/InheritableComponentHandler.h"
#include "Engine/SimpleConstructionScript.h"
#include "GameFramework/Actor.h"
#include "K2Node_CallFunction.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_VariableGet.h"
#include "KismetCompilerModule.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "PackageTools.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace BlueprintAuthoringInternal
{

enum class EBlueprintMutationFlags : uint8
{
	None = 0,
	Defaults = 1 << 0,
	Structural = 1 << 1,
	Compile = 1 << 2
};
ENUM_CLASS_FLAGS(EBlueprintMutationFlags);

static TSharedPtr<FJsonObject> NormalizePayload(
	const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* BlueprintObject = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("blueprint"), BlueprintObject)
		&& BlueprintObject
		&& BlueprintObject->IsValid())
	{
		return *BlueprintObject;
	}

	return PayloadJson;
}

static TArray<TSharedPtr<FJsonValue>> GetVariablesArray(
	const TSharedPtr<FJsonObject>& Payload)
{
	const TArray<TSharedPtr<FJsonValue>>* Variables = nullptr;
	if (Payload.IsValid()
		&& Payload->TryGetArrayField(TEXT("variables"), Variables)
		&& Variables)
	{
		return *Variables;
	}

	return {};
}

static TArray<TSharedPtr<FJsonValue>> GetFunctionArray(
	const TSharedPtr<FJsonObject>& Payload)
{
	const TArray<TSharedPtr<FJsonValue>>* Functions = nullptr;
	if (Payload.IsValid()
		&& Payload->TryGetArrayField(TEXT("functionGraphs"), Functions)
		&& Functions)
	{
		return *Functions;
	}

	if (Payload.IsValid()
		&& Payload->TryGetArrayField(TEXT("functionStubs"), Functions)
		&& Functions)
	{
		return *Functions;
	}

	if (Payload.IsValid()
		&& Payload->TryGetArrayField(TEXT("functions"), Functions)
		&& Functions)
	{
		return *Functions;
	}

	return {};
}

static TSharedPtr<FJsonObject> GetClassDefaultsObject(
	const TSharedPtr<FJsonObject>& Payload)
{
	if (!Payload.IsValid())
	{
		return nullptr;
	}

	const TSharedPtr<FJsonObject>* DefaultsObject = nullptr;
	if (Payload->TryGetObjectField(TEXT("classDefaults"), DefaultsObject)
		&& DefaultsObject
		&& DefaultsObject->IsValid())
	{
		return *DefaultsObject;
	}

	if (Payload->TryGetObjectField(TEXT("class_defaults"), DefaultsObject)
		&& DefaultsObject
		&& DefaultsObject->IsValid())
	{
		return *DefaultsObject;
	}

	if (Payload->TryGetObjectField(TEXT("properties"), DefaultsObject)
		&& DefaultsObject
		&& DefaultsObject->IsValid())
	{
		return *DefaultsObject;
	}

	return nullptr;
}

static TArray<TSharedPtr<FJsonValue>> GetRootComponentsArray(
	const TSharedPtr<FJsonObject>& Payload)
{
	if (!Payload.IsValid())
	{
		return {};
	}

	const TArray<TSharedPtr<FJsonValue>>* RootComponents = nullptr;
	if (Payload->TryGetArrayField(TEXT("rootComponents"), RootComponents)
		&& RootComponents)
	{
		return *RootComponents;
	}

	const TSharedPtr<FJsonObject>* ComponentsObject = nullptr;
	if (Payload->TryGetObjectField(TEXT("components"), ComponentsObject)
		&& ComponentsObject
		&& ComponentsObject->IsValid()
		&& (*ComponentsObject)->TryGetArrayField(TEXT("rootComponents"), RootComponents)
		&& RootComponents)
	{
		return *RootComponents;
	}

	return {};
}

static bool ParseVariableName(const TSharedPtr<FJsonObject>& VariableObject,
                              FString& OutVariableName)
{
	return VariableObject.IsValid()
		&& ((VariableObject->TryGetStringField(TEXT("name"), OutVariableName)
		     || VariableObject->TryGetStringField(
			     TEXT("variableName"),
			     OutVariableName))
		    && !OutVariableName.IsEmpty());
}

static bool ParseComponentName(const TSharedPtr<FJsonObject>& ComponentObject,
                               FString& OutComponentName)
{
	return ComponentObject.IsValid()
		&& ((ComponentObject->TryGetStringField(TEXT("componentName"), OutComponentName)
		     || ComponentObject->TryGetStringField(TEXT("name"), OutComponentName))
		    && !OutComponentName.IsEmpty());
}

static bool ParseFunctionName(const TSharedPtr<FJsonObject>& FunctionObject,
                              FString& OutFunctionName)
{
	return FunctionObject.IsValid()
		&& ((FunctionObject->TryGetStringField(TEXT("functionName"), OutFunctionName)
		     || FunctionObject->TryGetStringField(TEXT("graphName"), OutFunctionName)
		     || FunctionObject->TryGetStringField(TEXT("name"), OutFunctionName))
		    && !OutFunctionName.IsEmpty());
}

static bool ParseParentClassPath(const TSharedPtr<FJsonObject>& Payload,
                                 FString& OutParentClassPath)
{
	return Payload.IsValid()
		&& ((Payload->TryGetStringField(TEXT("parentClassPath"), OutParentClassPath)
		     || Payload->TryGetStringField(TEXT("parent_class_path"), OutParentClassPath))
		    && !OutParentClassPath.IsEmpty());
}

static bool IsClassChildOfAny(const UClass* CandidateClass,
                              const TSet<const UClass*>& ClassSet)
{
	if (!CandidateClass)
	{
		return false;
	}

	for (const UClass* Class : ClassSet)
	{
		if (Class && CandidateClass->IsChildOf(Class))
		{
			return true;
		}
	}

	return false;
}

static bool IsClassAllowedByReparentRules(const UClass* CandidateClass,
                                          const TSet<const UClass*>& AllowedChildrenOfClasses,
                                          const TSet<const UClass*>& DisallowedChildrenOfClasses)
{
	if (!CandidateClass)
	{
		return false;
	}

	const bool bMatchesAllowedClasses = AllowedChildrenOfClasses.Num() == 0
		|| IsClassChildOfAny(CandidateClass, AllowedChildrenOfClasses);
	return bMatchesAllowedClasses
		&& !IsClassChildOfAny(CandidateClass, DisallowedChildrenOfClasses);
}

static int32 FindVariableIndex(const UBlueprint* Blueprint, const FName VariableName)
{
	return Blueprint
		? FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, VariableName)
		: INDEX_NONE;
}

static UEdGraph* FindFunctionGraph(UBlueprint* Blueprint, const FName GraphName)
{
	if (!Blueprint)
	{
		return nullptr;
	}

	for (UEdGraph* Graph : Blueprint->FunctionGraphs)
	{
		if (Graph && Graph->GetFName() == GraphName)
		{
			return Graph;
		}
	}

	return nullptr;
}

static UK2Node_FunctionEntry* FindFunctionEntryNode(UEdGraph* Graph)
{
	if (!Graph)
	{
		return nullptr;
	}

	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (UK2Node_FunctionEntry* EntryNode = Cast<UK2Node_FunctionEntry>(Node))
		{
			return EntryNode;
		}
	}

	return nullptr;
}

static bool ParsePropertyFlags(const TSharedPtr<FJsonObject>& VariableObject,
                               uint64& OutFlags,
                               TArray<FString>& OutErrors)
{
	const TArray<TSharedPtr<FJsonValue>>* FlagsArray = nullptr;
	if (!VariableObject.IsValid()
		|| !VariableObject->TryGetArrayField(TEXT("propertyFlags"), FlagsArray)
		|| !FlagsArray)
	{
		return false;
	}

	OutFlags = 0;
	for (int32 Index = 0; Index < FlagsArray->Num(); ++Index)
	{
		FString FlagName;
		if (!(*FlagsArray)[Index].IsValid()
			|| !(*FlagsArray)[Index]->TryGetString(FlagName)
			|| FlagName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(
				TEXT("propertyFlags[%d] must be a non-empty string."),
				Index));
			continue;
		}

#define CHECK_BLUEPRINT_FLAG(Flag) \
		if (FlagName == TEXT(#Flag))   \
		{                              \
			OutFlags |= Flag;          \
			continue;                  \
		}
		CHECK_BLUEPRINT_FLAG(CPF_Edit);
		CHECK_BLUEPRINT_FLAG(CPF_BlueprintVisible);
		CHECK_BLUEPRINT_FLAG(CPF_BlueprintReadOnly);
		CHECK_BLUEPRINT_FLAG(CPF_Net);
		CHECK_BLUEPRINT_FLAG(CPF_SaveGame);
		CHECK_BLUEPRINT_FLAG(CPF_EditConst);
		CHECK_BLUEPRINT_FLAG(CPF_DisableEditOnInstance);
		CHECK_BLUEPRINT_FLAG(CPF_DisableEditOnTemplate);
		CHECK_BLUEPRINT_FLAG(CPF_Transient);
		CHECK_BLUEPRINT_FLAG(CPF_Config);
		CHECK_BLUEPRINT_FLAG(CPF_RepNotify);
		CHECK_BLUEPRINT_FLAG(CPF_Interp);
		CHECK_BLUEPRINT_FLAG(CPF_ExposeOnSpawn);
		CHECK_BLUEPRINT_FLAG(CPF_BlueprintAssignable);
		CHECK_BLUEPRINT_FLAG(CPF_BlueprintCallable);
#undef CHECK_BLUEPRINT_FLAG

		OutErrors.Add(FString::Printf(
			TEXT("Unsupported Blueprint variable property flag '%s'."),
			*FlagName));
	}

	return OutErrors.Num() == 0;
}

static int32 ParseFunctionFlags(const TSharedPtr<FJsonObject>& FunctionObject,
                                TArray<FString>& OutErrors)
{
	int32 Flags = FUNC_BlueprintCallable | FUNC_Public;
	if (!FunctionObject.IsValid())
	{
		return Flags;
	}

	const TArray<TSharedPtr<FJsonValue>>* FunctionFlags = nullptr;
	if (FunctionObject->TryGetArrayField(TEXT("functionFlags"), FunctionFlags)
		&& FunctionFlags)
	{
		Flags &= ~(FUNC_Public | FUNC_Protected | FUNC_Private);
		for (int32 Index = 0; Index < FunctionFlags->Num(); ++Index)
		{
			FString FlagName;
			if (!(*FunctionFlags)[Index].IsValid()
				|| !(*FunctionFlags)[Index]->TryGetString(FlagName)
				|| FlagName.IsEmpty())
			{
				OutErrors.Add(FString::Printf(
					TEXT("functionFlags[%d] must be a non-empty string."),
					Index));
				continue;
			}

#define CHECK_FUNCTION_FLAG(Flag) \
			if (FlagName == TEXT(#Flag)) \
			{                           \
				Flags |= Flag;          \
				continue;               \
			}
			CHECK_FUNCTION_FLAG(FUNC_BlueprintCallable);
			CHECK_FUNCTION_FLAG(FUNC_BlueprintPure);
			CHECK_FUNCTION_FLAG(FUNC_Static);
			CHECK_FUNCTION_FLAG(FUNC_Const);
			CHECK_FUNCTION_FLAG(FUNC_Public);
			CHECK_FUNCTION_FLAG(FUNC_Protected);
			CHECK_FUNCTION_FLAG(FUNC_Private);
#undef CHECK_FUNCTION_FLAG

			OutErrors.Add(FString::Printf(
				TEXT("Unsupported Blueprint function flag '%s'."),
				*FlagName));
		}
	}

	FString AccessSpecifier;
	if (FunctionObject->TryGetStringField(TEXT("accessSpecifier"), AccessSpecifier)
		&& !AccessSpecifier.IsEmpty())
	{
		Flags &= ~(FUNC_Public | FUNC_Protected | FUNC_Private);
		if (AccessSpecifier.Equals(TEXT("Public"), ESearchCase::IgnoreCase))
		{
			Flags |= FUNC_Public;
		}
		else if (
			AccessSpecifier.Equals(TEXT("Protected"), ESearchCase::IgnoreCase))
		{
			Flags |= FUNC_Protected;
		}
		else if (
			AccessSpecifier.Equals(TEXT("Private"), ESearchCase::IgnoreCase))
		{
			Flags |= FUNC_Private;
		}
		else
		{
			OutErrors.Add(FString::Printf(
				TEXT("Unsupported accessSpecifier '%s'."),
				*AccessSpecifier));
		}
	}

	bool bFlagValue = false;
	if (FunctionObject->TryGetBoolField(TEXT("isPure"), bFlagValue) && bFlagValue)
	{
		Flags |= FUNC_BlueprintPure;
	}
	if (FunctionObject->TryGetBoolField(TEXT("isConst"), bFlagValue) && bFlagValue)
	{
		Flags |= FUNC_Const;
	}
	if (FunctionObject->TryGetBoolField(TEXT("isStatic"), bFlagValue)
		&& bFlagValue)
	{
		Flags |= FUNC_Static;
	}

	return Flags;
}

static bool ApplyVariableMetadata(
	FBPVariableDescription& VariableDescription,
	const TSharedPtr<FJsonObject>& VariableObject,
	const bool bReplaceMetadata,
	TArray<FString>& OutErrors)
{
	if (!VariableObject.IsValid())
	{
		return true;
	}

	const TSharedPtr<FJsonObject>* MetadataObject = nullptr;
	if (bReplaceMetadata)
	{
		VariableDescription.MetaDataArray.Reset();
	}

	if (VariableObject->TryGetObjectField(TEXT("metadata"), MetadataObject)
		&& MetadataObject
		&& MetadataObject->IsValid())
	{
		if (bReplaceMetadata)
		{
			VariableDescription.MetaDataArray.Reset();
		}

		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair
		     : (*MetadataObject)->Values)
		{
			FString MetadataValue;
			if (!Pair.Value.IsValid()
				|| !Pair.Value->TryGetString(MetadataValue))
			{
				OutErrors.Add(FString::Printf(
					TEXT("Variable metadata '%s' must be a string."),
					*Pair.Key));
				continue;
			}

			VariableDescription.SetMetaData(FName(*Pair.Key), MetadataValue);
		}
	}

	return OutErrors.Num() == 0;
}

static bool ApplyVariableDefinition(UBlueprint* Blueprint,
                                    const TSharedPtr<FJsonObject>& VariableObject,
                                    const bool bAllowCreate,
                                    const bool bReplaceMetadata,
                                    TArray<FString>& OutErrors)
{
	if (!Blueprint || !VariableObject.IsValid())
	{
		OutErrors.Add(TEXT("Variable payload must be an object."));
		return false;
	}

	FString VariableNameString;
	if (!ParseVariableName(VariableObject, VariableNameString))
	{
		OutErrors.Add(TEXT("Variable payload requires name or variableName."));
		return false;
	}

	FName VariableName(*VariableNameString);
	int32 VariableIndex = FindVariableIndex(Blueprint, VariableName);
	if (VariableIndex == INDEX_NONE)
	{
		if (!bAllowCreate)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Blueprint variable '%s' was not found."),
				*VariableNameString));
			return false;
		}

		const TSharedPtr<FJsonObject>* PinTypeObject = nullptr;
		if (!(VariableObject->TryGetObjectField(TEXT("type"), PinTypeObject)
			  || VariableObject->TryGetObjectField(TEXT("pinType"), PinTypeObject))
			|| !PinTypeObject
			|| !PinTypeObject->IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("Variable '%s' requires a type object."),
				*VariableNameString));
			return false;
		}

		FEdGraphPinType ParsedPinType;
		FString ParseError;
		if (!FAuthoringHelpers::ParsePinType(
			    *PinTypeObject,
			    ParsedPinType,
			    ParseError))
		{
			OutErrors.Add(ParseError);
			return false;
		}

		FString DefaultValue;
		VariableObject->TryGetStringField(TEXT("defaultValue"), DefaultValue);
		if (!FBlueprintEditorUtils::AddMemberVariable(
			    Blueprint,
			    VariableName,
			    ParsedPinType,
			    DefaultValue))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to add Blueprint variable '%s'."),
				*VariableNameString));
			return false;
		}

		VariableIndex = FindVariableIndex(Blueprint, VariableName);
	}

	if (VariableIndex == INDEX_NONE || !Blueprint->NewVariables.IsValidIndex(VariableIndex))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to resolve Blueprint variable '%s' after mutation."),
			*VariableNameString));
		return false;
	}

	FString NewVariableName;
	if (VariableObject->TryGetStringField(TEXT("newName"), NewVariableName)
		&& !NewVariableName.IsEmpty()
		&& NewVariableName != VariableNameString)
	{
		FBlueprintEditorUtils::RenameMemberVariable(
			Blueprint,
			VariableName,
			FName(*NewVariableName));
		VariableName = FName(*NewVariableName);
		VariableIndex = FindVariableIndex(Blueprint, VariableName);
		if (VariableIndex == INDEX_NONE
			|| !Blueprint->NewVariables.IsValidIndex(VariableIndex))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to rename Blueprint variable '%s' to '%s'."),
				*VariableNameString,
				*NewVariableName));
			return false;
		}
	}

	const TSharedPtr<FJsonObject>* PinTypeObject = nullptr;
	if ((VariableObject->TryGetObjectField(TEXT("type"), PinTypeObject)
		 || VariableObject->TryGetObjectField(TEXT("pinType"), PinTypeObject))
		&& PinTypeObject
		&& PinTypeObject->IsValid())
	{
		FEdGraphPinType ParsedPinType;
		FString ParseError;
		if (!FAuthoringHelpers::ParsePinType(
			    *PinTypeObject,
			    ParsedPinType,
			    ParseError))
		{
			OutErrors.Add(ParseError);
			return false;
		}

		if (Blueprint->NewVariables[VariableIndex].VarType != ParsedPinType)
		{
			FBlueprintEditorUtils::ChangeMemberVariableType(
				Blueprint,
				VariableName,
				ParsedPinType);
			VariableIndex = FindVariableIndex(Blueprint, VariableName);
			if (!Blueprint->NewVariables.IsValidIndex(VariableIndex))
			{
				OutErrors.Add(FString::Printf(
					TEXT("Failed to change type for Blueprint variable '%s'."),
					*VariableName.ToString()));
				return false;
			}
		}
	}

	FBPVariableDescription& VariableDescription =
		Blueprint->NewVariables[VariableIndex];

	FString FriendlyName;
	if (VariableObject->TryGetStringField(TEXT("friendlyName"), FriendlyName))
	{
		VariableDescription.FriendlyName = FriendlyName;
	}

	FString Category;
	if (VariableObject->TryGetStringField(TEXT("category"), Category))
	{
		VariableDescription.Category = FText::FromString(Category);
	}

	FString DefaultValue;
	if (VariableObject->TryGetStringField(TEXT("defaultValue"), DefaultValue))
	{
		VariableDescription.DefaultValue = DefaultValue;
	}

	FString RepNotifyFunc;
	if (VariableObject->TryGetStringField(TEXT("repNotifyFunc"), RepNotifyFunc))
	{
		VariableDescription.RepNotifyFunc =
			RepNotifyFunc.IsEmpty() ? NAME_None : FName(*RepNotifyFunc);
	}

	uint64 PropertyFlags = 0;
	TArray<FString> PropertyFlagErrors;
	if (ParsePropertyFlags(VariableObject, PropertyFlags, PropertyFlagErrors))
	{
		VariableDescription.PropertyFlags = PropertyFlags;
	}
	for (const FString& Error : PropertyFlagErrors)
	{
		OutErrors.Add(Error);
	}

	ApplyVariableMetadata(
		VariableDescription,
		VariableObject,
		bReplaceMetadata,
		OutErrors);

	return OutErrors.Num() == 0;
}

static bool ReplaceVariables(UBlueprint* Blueprint,
                             const TArray<TSharedPtr<FJsonValue>>& Variables,
                             TArray<FString>& OutErrors)
{
	if (!Blueprint)
	{
		OutErrors.Add(TEXT("Blueprint is null."));
		return false;
	}

	TArray<FName> ExistingVariables;
	ExistingVariables.Reserve(Blueprint->NewVariables.Num());
	for (const FBPVariableDescription& Description : Blueprint->NewVariables)
	{
		ExistingVariables.Add(Description.VarName);
	}

	if (ExistingVariables.Num() > 0)
	{
		FBlueprintEditorUtils::BulkRemoveMemberVariables(Blueprint, ExistingVariables);
	}

	bool bSuccess = true;
	for (int32 Index = 0; Index < Variables.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> VariableObject =
			Variables[Index].IsValid() ? Variables[Index]->AsObject() : nullptr;
		if (!VariableObject.IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("variables[%d] must be an object."),
				Index));
			bSuccess = false;
			continue;
		}

		bSuccess &= ApplyVariableDefinition(
			Blueprint,
			VariableObject,
			true,
			true,
			OutErrors);
	}

	return bSuccess && OutErrors.Num() == 0;
}

static bool AddVariables(UBlueprint* Blueprint,
                         const TArray<TSharedPtr<FJsonValue>>& Variables,
                         TArray<FString>& OutErrors)
{
	if (!Blueprint)
	{
		OutErrors.Add(TEXT("Blueprint is null."));
		return false;
	}

	if (Variables.Num() == 0)
	{
		OutErrors.Add(TEXT("add_variables requires at least one variable."));
		return false;
	}

	bool bSuccess = true;
	for (int32 Index = 0; Index < Variables.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> VariableObject =
			Variables[Index].IsValid() ? Variables[Index]->AsObject() : nullptr;
		if (!VariableObject.IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("variables[%d] must be an object."),
				Index));
			bSuccess = false;
			continue;
		}

		bSuccess &= ApplyVariableDefinition(
			Blueprint,
			VariableObject,
			true,
			false,
			OutErrors);
	}

	return bSuccess && OutErrors.Num() == 0;
}

static bool PatchVariable(UBlueprint* Blueprint,
                          const TSharedPtr<FJsonObject>& Payload,
                          TArray<FString>& OutErrors)
{
	if (!Payload.IsValid())
	{
		OutErrors.Add(TEXT("patch_variable requires a payload object."));
		return false;
	}

	const TSharedPtr<FJsonObject>* VariableObject = nullptr;
	if (Payload->TryGetObjectField(TEXT("variable"), VariableObject)
		&& VariableObject
		&& VariableObject->IsValid())
	{
		return ApplyVariableDefinition(
			Blueprint,
			*VariableObject,
			false,
			false,
			OutErrors);
	}

	return ApplyVariableDefinition(Blueprint, Payload, false, false, OutErrors);
}

static void ClearComponents(UBlueprint* Blueprint)
{
	if (!Blueprint || !Blueprint->SimpleConstructionScript)
	{
		return;
	}

	USimpleConstructionScript* SCS = Blueprint->SimpleConstructionScript;
	TArray<USCS_Node*> RootNodes;
	for (USCS_Node* RootNode : SCS->GetRootNodes())
	{
		RootNodes.Add(RootNode);
	}

	for (int32 Index = RootNodes.Num() - 1; Index >= 0; --Index)
	{
		if (RootNodes[Index])
		{
			SCS->RemoveNode(RootNodes[Index], false);
		}
	}

	SCS->ValidateSceneRootNodes();
}

static bool ApplyNodeMetadata(USCS_Node* Node,
                              const TSharedPtr<FJsonObject>& ComponentObject,
                              TArray<FString>& OutErrors)
{
	if (!Node || !ComponentObject.IsValid())
	{
		return true;
	}

	const TSharedPtr<FJsonObject>* MetadataObject = nullptr;
	if (ComponentObject->TryGetObjectField(TEXT("metadata"), MetadataObject)
		&& MetadataObject
		&& MetadataObject->IsValid())
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair
		     : (*MetadataObject)->Values)
		{
			FString MetadataValue;
			if (!Pair.Value.IsValid()
				|| !Pair.Value->TryGetString(MetadataValue))
			{
				OutErrors.Add(FString::Printf(
					TEXT("Component metadata '%s' must be a string."),
					*Pair.Key));
				continue;
			}

			Node->SetMetaData(FName(*Pair.Key), MetadataValue);
		}
	}

	return OutErrors.Num() == 0;
}

static bool ApplyComponentTemplateProperties(
	USCS_Node* Node,
	const TSharedPtr<FJsonObject>& ComponentObject,
	TArray<FString>& OutErrors)
{
	if (!Node || !Node->ComponentTemplate || !ComponentObject.IsValid())
	{
		return true;
	}

	const TSharedPtr<FJsonObject>* OverridesObject = nullptr;
	if (!(ComponentObject->TryGetObjectField(TEXT("propertyOverrides"), OverridesObject)
		  || ComponentObject->TryGetObjectField(TEXT("properties"), OverridesObject))
		|| !OverridesObject
		|| !OverridesObject->IsValid())
	{
		return true;
	}

	return FPropertySerializer::ApplyPropertiesFromJson(
		Node->ComponentTemplate,
		*OverridesObject,
		OutErrors,
		false,
		true);
}

static bool BuildComponentTree(UBlueprint* Blueprint,
                               USCS_Node* ParentNode,
                               const TSharedPtr<FJsonObject>& ComponentObject,
                               TSet<FName>& UsedNames,
                               TArray<FString>& OutErrors)
{
	if (!Blueprint || !Blueprint->SimpleConstructionScript)
	{
		OutErrors.Add(TEXT("Blueprint does not support SimpleConstructionScript components."));
		return false;
	}

	if (!ComponentObject.IsValid())
	{
		OutErrors.Add(TEXT("Component definition must be an object."));
		return false;
	}

	FString ComponentName;
	if (!ParseComponentName(ComponentObject, ComponentName))
	{
		OutErrors.Add(TEXT("Component definition requires componentName or name."));
		return false;
	}

	const FName ComponentFName(*ComponentName);
	if (UsedNames.Contains(ComponentFName))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Duplicate component name '%s'."),
			*ComponentName));
		return false;
	}

	FString ComponentClassPath;
	if (!ComponentObject->TryGetStringField(TEXT("componentClass"), ComponentClassPath)
		|| ComponentClassPath.IsEmpty())
	{
		OutErrors.Add(FString::Printf(
			TEXT("Component '%s' requires componentClass."),
			*ComponentName));
		return false;
	}

	UClass* ComponentClass = FAuthoringHelpers::ResolveClass(
		ComponentClassPath,
		UActorComponent::StaticClass());
	if (!ComponentClass || ComponentClass->HasAnyClassFlags(CLASS_Abstract))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Component class '%s' is not a concrete UActorComponent class."),
			*ComponentClassPath));
		return false;
	}

	USimpleConstructionScript* SCS = Blueprint->SimpleConstructionScript;
	USCS_Node* Node = SCS->CreateNode(ComponentClass, ComponentFName);
	if (!Node)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to create component node '%s'."),
			*ComponentName));
		return false;
	}

	UsedNames.Add(ComponentFName);

	FString AttachToName;
	if (ComponentObject->TryGetStringField(TEXT("attachToName"), AttachToName))
	{
		Node->AttachToName = AttachToName.IsEmpty() ? NAME_None : FName(*AttachToName);
	}

	ApplyNodeMetadata(Node, ComponentObject, OutErrors);
	ApplyComponentTemplateProperties(Node, ComponentObject, OutErrors);

	if (ParentNode)
	{
		ParentNode->AddChildNode(Node);
	}
	else
	{
		SCS->AddNode(Node);
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (ComponentObject->TryGetArrayField(TEXT("children"), Children) && Children)
	{
		for (int32 Index = 0; Index < Children->Num(); ++Index)
		{
			const TSharedPtr<FJsonObject> ChildObject =
				(*Children)[Index].IsValid() ? (*Children)[Index]->AsObject() : nullptr;
			if (!BuildComponentTree(
				    Blueprint,
				    Node,
				    ChildObject,
				    UsedNames,
				    OutErrors))
			{
				return false;
			}
		}
	}

	return OutErrors.Num() == 0;
}

static bool ReplaceComponents(UBlueprint* Blueprint,
                              const TArray<TSharedPtr<FJsonValue>>& RootComponents,
                              TArray<FString>& OutErrors)
{
	if (!Blueprint || !Blueprint->SimpleConstructionScript)
	{
		OutErrors.Add(TEXT("Blueprint does not support component authoring."));
		return false;
	}

	ClearComponents(Blueprint);

	TSet<FName> UsedNames;
	bool bSuccess = true;
	for (int32 Index = 0; Index < RootComponents.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> ComponentObject =
			RootComponents[Index].IsValid() ? RootComponents[Index]->AsObject() : nullptr;
		if (!ComponentObject.IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("rootComponents[%d] must be an object."),
				Index));
			bSuccess = false;
			continue;
		}

		bSuccess &= BuildComponentTree(
			Blueprint,
			nullptr,
			ComponentObject,
			UsedNames,
			OutErrors);
	}

	Blueprint->SimpleConstructionScript->ValidateSceneRootNodes();
	return bSuccess && OutErrors.Num() == 0;
}

static bool ReparentComponentNode(UBlueprint* Blueprint,
                                  USCS_Node* Node,
                                  USCS_Node* NewParent,
                                  TArray<FString>& OutErrors)
{
	if (!Blueprint || !Blueprint->SimpleConstructionScript || !Node)
	{
		OutErrors.Add(TEXT("Invalid component reparent request."));
		return false;
	}

	if (Node == NewParent || (NewParent && NewParent->IsChildOf(Node)))
	{
		OutErrors.Add(TEXT("Component reparent would create a cycle."));
		return false;
	}

	USimpleConstructionScript* SCS = Blueprint->SimpleConstructionScript;
	USCS_Node* OldParent = SCS->FindParentNode(Node);

	if (OldParent == NewParent)
	{
		return true;
	}

	if (OldParent)
	{
		OldParent->RemoveChildNode(Node, false);
	}
	else
	{
		SCS->RemoveNode(Node, false);
	}

	if (NewParent)
	{
		NewParent->AddChildNode(Node);
	}
	else
	{
		SCS->AddNode(Node);
	}

	SCS->ValidateSceneRootNodes();
	return true;
}

static bool PatchComponent(UBlueprint* Blueprint,
                           const TSharedPtr<FJsonObject>& Payload,
                           TArray<FString>& OutErrors)
{
	if (!Blueprint || !Blueprint->SimpleConstructionScript)
	{
		OutErrors.Add(TEXT("Blueprint does not support component authoring."));
		return false;
	}

	const TSharedPtr<FJsonObject>* ComponentObject = nullptr;
	TSharedPtr<FJsonObject> EffectivePayload = Payload;
	if (Payload.IsValid()
		&& Payload->TryGetObjectField(TEXT("component"), ComponentObject)
		&& ComponentObject
		&& ComponentObject->IsValid())
	{
		EffectivePayload = *ComponentObject;
	}

	FString ComponentName;
	if (!ParseComponentName(EffectivePayload, ComponentName))
	{
		OutErrors.Add(TEXT("patch_component requires componentName or name."));
		return false;
	}

	USCS_Node* Node = Blueprint->SimpleConstructionScript->FindSCSNode(FName(*ComponentName));
	if (!Node)
	{
		// Search parent class chain for the component
		USCS_Node* ParentNode = nullptr;
		FString ParentClassName;
		UClass* ParentClass = Blueprint->ParentClass;
		while (ParentClass && !ParentNode)
		{
			if (UBlueprintGeneratedClass* BPGC = Cast<UBlueprintGeneratedClass>(ParentClass))
			{
				if (BPGC->SimpleConstructionScript)
				{
					ParentNode = BPGC->SimpleConstructionScript->FindSCSNode(FName(*ComponentName));
					if (ParentNode)
					{
						ParentClassName = BPGC->ClassGeneratedBy
							? BPGC->ClassGeneratedBy->GetName()
							: BPGC->GetName();
					}
				}
			}
			ParentClass = ParentClass->GetSuperClass();
		}

		if (!ParentNode)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Blueprint component '%s' was not found in '%s' or any parent class."),
				*ComponentName, *Blueprint->GetName()));
			return false;
		}

		// Use UInheritableComponentHandler to override inherited component properties
		UInheritableComponentHandler* ICH = Blueprint->GetInheritableComponentHandler(/*bCreateIfNecessary=*/true);
		if (!ICH)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to create InheritableComponentHandler for '%s'. "
				     "Component '%s' is inherited from '%s' but cannot be overridden."),
				*Blueprint->GetName(), *ComponentName, *ParentClassName));
			return false;
		}

		FComponentKey CompKey(ParentNode);

		// Get existing override template or create a new one
		UActorComponent* OverrideTemplate = ICH->GetOverridenComponentTemplate(CompKey);
		if (!OverrideTemplate)
		{
			OverrideTemplate = ICH->CreateOverridenComponentTemplate(CompKey);
			if (!OverrideTemplate)
			{
				OutErrors.Add(FString::Printf(
					TEXT("Failed to create override template for inherited component '%s' from '%s'."),
					*ComponentName, *ParentClassName));
				return false;
			}
		}

		// Apply properties to the override template
		const TSharedPtr<FJsonObject>* PropertiesObject = nullptr;
		if ((EffectivePayload->TryGetObjectField(TEXT("properties"), PropertiesObject)
			|| EffectivePayload->TryGetObjectField(TEXT("propertyOverrides"), PropertiesObject))
			&& PropertiesObject && (*PropertiesObject)->Values.Num() > 0)
		{
			if (!FPropertySerializer::ApplyPropertiesFromJson(
					OverrideTemplate, *PropertiesObject, OutErrors, false, true))
			{
				return false;
			}
		}

		// Warn about operations not supported on inherited components
		TArray<FString> UnsupportedKeys;
		if (EffectivePayload->HasField(TEXT("newName")))
			UnsupportedKeys.Add(TEXT("newName"));
		if (EffectivePayload->HasField(TEXT("parentComponentName")))
			UnsupportedKeys.Add(TEXT("parentComponentName"));
		if (EffectivePayload->HasField(TEXT("attachToName")))
			UnsupportedKeys.Add(TEXT("attachToName"));

		if (UnsupportedKeys.Num() > 0)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Warning: '%s' is inherited from '%s'. Only property overrides are supported. "
				     "The following operations were ignored: %s"),
				*ComponentName, *ParentClassName,
				*FString::Join(UnsupportedKeys, TEXT(", "))));
		}

		return true;
	}

	FString NewName;
	if (EffectivePayload->TryGetStringField(TEXT("newName"), NewName)
		&& !NewName.IsEmpty()
		&& NewName != ComponentName)
	{
		Node->SetVariableName(FName(*NewName));
	}

	FString AttachToName;
	if (EffectivePayload->TryGetStringField(TEXT("attachToName"), AttachToName))
	{
		Node->AttachToName = AttachToName.IsEmpty() ? NAME_None : FName(*AttachToName);
	}

	FString ParentComponentName;
	if (EffectivePayload->TryGetStringField(TEXT("parentComponentName"), ParentComponentName))
	{
		USCS_Node* NewParentNode = nullptr;
		if (!ParentComponentName.IsEmpty())
		{
			NewParentNode =
				Blueprint->SimpleConstructionScript->FindSCSNode(FName(*ParentComponentName));
			if (!NewParentNode)
			{
				OutErrors.Add(FString::Printf(
					TEXT("Component parent '%s' was not found."),
					*ParentComponentName));
				return false;
			}
		}

		ReparentComponentNode(Blueprint, Node, NewParentNode, OutErrors);
	}

	ApplyNodeMetadata(Node, EffectivePayload, OutErrors);
	ApplyComponentTemplateProperties(Node, EffectivePayload, OutErrors);
	return OutErrors.Num() == 0;
}

static bool AddComponent(UBlueprint* Blueprint,
                         const TSharedPtr<FJsonObject>& Payload,
                         TArray<FString>& OutErrors)
{
	if (!Blueprint || !Blueprint->SimpleConstructionScript)
	{
		OutErrors.Add(TEXT("Blueprint does not support component authoring (no SimpleConstructionScript)."));
		return false;
	}

	USCS_Node* ParentNode = nullptr;
	FString ParentComponentName;
	if (Payload->TryGetStringField(TEXT("parentComponentName"), ParentComponentName)
		&& !ParentComponentName.IsEmpty())
	{
		ParentNode =
			Blueprint->SimpleConstructionScript->FindSCSNode(FName(*ParentComponentName));
		if (!ParentNode)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Parent component '%s' was not found."),
				*ParentComponentName));
			return false;
		}
	}

	// Collect existing component names to avoid duplicates
	TSet<FName> UsedNames;
	for (USCS_Node* Node : Blueprint->SimpleConstructionScript->GetAllNodes())
	{
		if (Node)
		{
			UsedNames.Add(Node->GetVariableName());
		}
	}

	// Use the component definition from payload — either nested under "component" or the payload itself
	const TSharedPtr<FJsonObject>* ComponentObject = nullptr;
	TSharedPtr<FJsonObject> EffectivePayload = Payload;
	if (Payload->TryGetObjectField(TEXT("component"), ComponentObject)
		&& ComponentObject && (*ComponentObject).IsValid())
	{
		EffectivePayload = *ComponentObject;
	}

	return BuildComponentTree(Blueprint, ParentNode, EffectivePayload, UsedNames, OutErrors);
}

static bool ApplyFunctionStub(UEdGraph* Graph,
                              const TSharedPtr<FJsonObject>& FunctionObject,
                              TArray<FString>& OutErrors)
{
	if (!Graph || !FunctionObject.IsValid())
	{
		OutErrors.Add(TEXT("Function stub payload must be an object."));
		return false;
	}

	FString Category;
	if (FunctionObject->TryGetStringField(TEXT("category"), Category))
	{
		FBlueprintEditorUtils::SetBlueprintFunctionOrMacroCategory(
			Graph,
			FText::FromString(Category),
			true);
	}

	UK2Node_FunctionEntry* EntryNode = FindFunctionEntryNode(Graph);
	if (!EntryNode)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Function graph '%s' is missing a function entry node."),
			*Graph->GetName()));
		return false;
	}

	EntryNode->SetExtraFlags(ParseFunctionFlags(FunctionObject, OutErrors));
	return OutErrors.Num() == 0;
}

static bool ReplaceFunctionStubs(UBlueprint* Blueprint,
                                 const TArray<TSharedPtr<FJsonValue>>& Functions,
                                 TArray<FString>& OutErrors)
{
	if (!Blueprint)
	{
		OutErrors.Add(TEXT("Blueprint is null."));
		return false;
	}

	TArray<UEdGraph*> ExistingGraphs;
	for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
	{
		if (FunctionGraph)
		{
			ExistingGraphs.Add(FunctionGraph);
		}
	}

	if (ExistingGraphs.Num() > 0)
	{
		FBlueprintEditorUtils::RemoveGraphs(Blueprint, ExistingGraphs);
	}

	bool bSuccess = true;
	for (int32 Index = 0; Index < Functions.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> FunctionObject =
			Functions[Index].IsValid() ? Functions[Index]->AsObject() : nullptr;
		if (!FunctionObject.IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("functionStubs[%d] must be an object."),
				Index));
			bSuccess = false;
			continue;
		}

		FString FunctionName;
		if (!ParseFunctionName(FunctionObject, FunctionName))
		{
			OutErrors.Add(FString::Printf(
				TEXT("functionStubs[%d] requires functionName, graphName, or name."),
				Index));
			bSuccess = false;
			continue;
		}

		if (FindFunctionGraph(Blueprint, FName(*FunctionName)))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Duplicate function graph '%s'."),
				*FunctionName));
			bSuccess = false;
			continue;
		}

		UEdGraph* NewGraph = FBlueprintEditorUtils::CreateNewGraph(
			Blueprint,
			FName(*FunctionName),
			UEdGraph::StaticClass(),
			UEdGraphSchema_K2::StaticClass());
		if (!NewGraph)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to create function graph '%s'."),
				*FunctionName));
			bSuccess = false;
			continue;
		}

		FBlueprintEditorUtils::AddFunctionGraph<UClass>(Blueprint, NewGraph, true, nullptr);
		bSuccess &= ApplyFunctionStub(NewGraph, FunctionObject, OutErrors);
	}

	return bSuccess && OutErrors.Num() == 0;
}

static bool UpsertFunctionStubs(UBlueprint* Blueprint,
                                const TArray<TSharedPtr<FJsonValue>>& Functions,
                                TArray<FString>& OutErrors)
{
	if (!Blueprint)
	{
		OutErrors.Add(TEXT("Blueprint is null."));
		return false;
	}

	bool bSuccess = true;
	for (int32 Index = 0; Index < Functions.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> FunctionObject =
			Functions[Index].IsValid() ? Functions[Index]->AsObject() : nullptr;
		if (!FunctionObject.IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("functionGraphs[%d] must be an object."),
				Index));
			bSuccess = false;
			continue;
		}

		FString FunctionName;
		if (!ParseFunctionName(FunctionObject, FunctionName))
		{
			OutErrors.Add(FString::Printf(
				TEXT("functionGraphs[%d] requires functionName, graphName, or name."),
				Index));
			bSuccess = false;
			continue;
		}

		bool bReplaceExisting = false;
		FunctionObject->TryGetBoolField(TEXT("replaceExisting"), bReplaceExisting);
		UEdGraph* TargetGraph = FindFunctionGraph(Blueprint, FName(*FunctionName));
		if (TargetGraph && bReplaceExisting)
		{
			TArray<UEdGraph*> GraphsToRemove = { TargetGraph };
			FBlueprintEditorUtils::RemoveGraphs(Blueprint, GraphsToRemove);
			TargetGraph = nullptr;
		}

		if (!TargetGraph)
		{
			TargetGraph = FBlueprintEditorUtils::CreateNewGraph(
				Blueprint,
				FName(*FunctionName),
				UEdGraph::StaticClass(),
				UEdGraphSchema_K2::StaticClass());
			if (!TargetGraph)
			{
				OutErrors.Add(FString::Printf(
					TEXT("Failed to create function graph '%s'."),
					*FunctionName));
				bSuccess = false;
				continue;
			}

			FBlueprintEditorUtils::AddFunctionGraph<UClass>(Blueprint, TargetGraph, true, nullptr);
		}

		bSuccess &= ApplyFunctionStub(TargetGraph, FunctionObject, OutErrors);
	}

	return bSuccess && OutErrors.Num() == 0;
}

static bool ReloadBlueprintPackage(UBlueprint* Blueprint, FString& OutError)
{
	if (!Blueprint)
	{
		OutError = TEXT("Blueprint is null.");
		return false;
	}

	UPackage* Package = Blueprint->GetOutermost();
	if (!Package)
	{
		OutError = TEXT("Blueprint package is null.");
		return false;
	}

	const TArray<UPackage*> PackagesToReload = { Package };
	FText ReloadError;
	const bool bReloaded = UPackageTools::ReloadPackages(
		PackagesToReload,
		ReloadError,
		EReloadPackagesInteractionMode::AssumePositive);
	if (!bReloaded)
	{
		OutError = ReloadError.ToString();
		return false;
	}

	return true;
}

static UEdGraphPin* FindPinByName(UEdGraphNode* Node, const FString& PinName)
{
	if (!Node)
	{
		return nullptr;
	}

	for (UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin && Pin->PinName == FName(*PinName))
		{
			return Pin;
		}
	}

	return nullptr;
}

static bool AppendFunctionCallToSequence(UBlueprint* Blueprint,
                                         const TSharedPtr<FJsonObject>& Payload,
                                         TArray<FString>& OutErrors)
{
	if (!Blueprint || !Payload.IsValid())
	{
		OutErrors.Add(TEXT("append_function_call_to_sequence requires a Blueprint and payload."));
		return false;
	}

	FString GraphName;
	if (!Payload->TryGetStringField(TEXT("graphName"), GraphName) || GraphName.IsEmpty())
	{
		OutErrors.Add(TEXT("append_function_call_to_sequence requires graphName."));
		return false;
	}

	UEdGraph* Graph = FindFunctionGraph(Blueprint, FName(*GraphName));
	if (!Graph)
	{
		OutErrors.Add(FString::Printf(TEXT("Blueprint graph '%s' was not found."), *GraphName));
		return false;
	}

	FString FunctionName;
	if (!Payload->TryGetStringField(TEXT("functionName"), FunctionName) || FunctionName.IsEmpty())
	{
		OutErrors.Add(TEXT("append_function_call_to_sequence requires functionName."));
		return false;
	}

	UK2Node_ExecutionSequence* SequenceNode = nullptr;
	FString SequenceNodeTitle;
	Payload->TryGetStringField(TEXT("sequenceNodeTitle"), SequenceNodeTitle);
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		UK2Node_ExecutionSequence* Candidate = Cast<UK2Node_ExecutionSequence>(Node);
		if (!Candidate)
		{
			continue;
		}

		if (SequenceNodeTitle.IsEmpty() || Candidate->GetNodeTitle(ENodeTitleType::ListView).ToString().Contains(SequenceNodeTitle))
		{
			SequenceNode = Candidate;
			break;
		}
	}

	if (!SequenceNode)
	{
		OutErrors.Add(FString::Printf(TEXT("No execution sequence node was found in graph '%s'."), *GraphName));
		return false;
	}

	double PosX = 0.0;
	double PosY = 0.0;
	Payload->TryGetNumberField(TEXT("posX"), PosX);
	Payload->TryGetNumberField(TEXT("posY"), PosY);
	const FVector2D NodePosition(PosX, PosY);

	UK2Node_CallFunction* CallFunctionNode = FEdGraphSchemaAction_K2NewNode::SpawnNode<UK2Node_CallFunction>(
		Graph,
		NodePosition,
		EK2NewNodeFlags::None,
		[&FunctionName, Blueprint, Payload](UK2Node_CallFunction* NewNode)
		{
			FString OwnerClassPath;
			if (Payload->TryGetStringField(TEXT("ownerClass"), OwnerClassPath) && !OwnerClassPath.IsEmpty())
			{
				if (UClass* OwnerClass = FAuthoringHelpers::ResolveClass(OwnerClassPath, UObject::StaticClass()))
				{
					if (UFunction* Function = OwnerClass->FindFunctionByName(FName(*FunctionName)))
					{
						NewNode->SetFromFunction(Function);
						return;
					}
				}
			}

			if (Blueprint && Blueprint->SkeletonGeneratedClass)
			{
				if (UFunction* Function = Blueprint->SkeletonGeneratedClass->FindFunctionByName(FName(*FunctionName)))
				{
					NewNode->SetFromFunction(Function);
					return;
				}
			}

			NewNode->FunctionReference.SetSelfMember(FName(*FunctionName));
		});

	if (!CallFunctionNode)
	{
		OutErrors.Add(FString::Printf(TEXT("Failed to create call node for '%s'."), *FunctionName));
		return false;
	}

	int32 ThenPinCount = 0;
	for (UEdGraphPin* Pin : SequenceNode->Pins)
	{
		if (Pin && Pin->Direction == EGPD_Output && Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_Exec)
		{
			++ThenPinCount;
		}
	}

	if (ThenPinCount <= 0)
	{
		OutErrors.Add(TEXT("Execution sequence node did not expose any exec output pins."));
		return false;
	}

	const int32 AppendIndex = ThenPinCount - 1;
	SequenceNode->AddInputPin();
	UEdGraphPin* ThenPin = SequenceNode->GetThenPinGivenIndex(AppendIndex + 1);
	UEdGraphPin* ExecutePin = FindPinByName(CallFunctionNode, TEXT("execute"));
	if (!ThenPin || !ExecutePin)
	{
		OutErrors.Add(TEXT("Failed to resolve exec pins while appending a function call."));
		return false;
	}

	const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
	if (!Schema->TryCreateConnection(ThenPin, ExecutePin))
	{
		OutErrors.Add(TEXT("Failed to wire the appended function call into the sequence node."));
		return false;
	}

	return true;
}

static bool ApplyClassDefaults(UBlueprint* Blueprint,
                               const TSharedPtr<FJsonObject>& DefaultsObject,
                               TArray<FString>& OutErrors,
                               const bool bValidationOnly)
{
	if (!Blueprint || !DefaultsObject.IsValid())
	{
		return true;
	}

	UObject* DefaultTarget = nullptr;
	if (Blueprint->GeneratedClass)
	{
		DefaultTarget = Blueprint->GeneratedClass->GetDefaultObject();
	}

	if (!DefaultTarget)
	{
		OutErrors.Add(TEXT("Blueprint GeneratedClass is not available for class-default edits."));
		return false;
	}

	TArray<FString> ValidationErrors;
	const bool bValidationSuccess = FPropertySerializer::ApplyPropertiesFromJson(
		DefaultTarget,
		DefaultsObject,
		ValidationErrors,
		true,
		true);
	OutErrors.Append(ValidationErrors);
	if (!bValidationSuccess)
	{
		return false;
	}

	if (bValidationOnly)
	{
		return true;
	}

	return FPropertySerializer::ApplyPropertiesFromJson(
		DefaultTarget,
		DefaultsObject,
		OutErrors,
		false,
		true);
}

static bool ValidateBlueprintReparentTarget(UBlueprint* Blueprint,
                                            UClass* NewParentClass,
                                            TArray<FString>& OutErrors)
{
	if (!Blueprint)
	{
		OutErrors.Add(TEXT("Blueprint is null."));
		return false;
	}

	if (!NewParentClass)
	{
		OutErrors.Add(TEXT("reparent requires a valid parent class."));
		return false;
	}

	if (!FKismetEditorUtilities::CanCreateBlueprintOfClass(NewParentClass))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Class '%s' cannot be used as a Blueprint parent."),
			*NewParentClass->GetPathName()));
		return false;
	}

	const bool bIsActor = Blueprint->ParentClass
		&& Blueprint->ParentClass->IsChildOf(AActor::StaticClass());
	const bool bIsAnimBlueprint = Blueprint->IsA(UAnimBlueprint::StaticClass());
	const bool bIsLevelScriptActor = Blueprint->ParentClass
		&& Blueprint->ParentClass->IsChildOf(ALevelScriptActor::StaticClass());
	const bool bIsComponentBlueprint = Blueprint->ParentClass
		&& Blueprint->ParentClass->IsChildOf(UActorComponent::StaticClass());
	const bool bIsEditorOnlyBlueprint = FBlueprintEditorUtils::IsEditorUtilityBlueprint(Blueprint);
	const bool bIsWidgetBlueprint = Blueprint->IsA(UBaseWidgetBlueprint::StaticClass());

	if (bIsLevelScriptActor)
	{
		if (!NewParentClass->IsChildOf(ALevelScriptActor::StaticClass()))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' is not compatible with LevelScript Blueprints."),
				*NewParentClass->GetPathName()));
			return false;
		}

		if (!NewParentClass->HasAnyClassFlags(CLASS_Native))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' is not a native LevelScriptActor parent."),
				*NewParentClass->GetPathName()));
			return false;
		}
	}
	else if (bIsActor)
	{
		if (!NewParentClass->IsChildOf(AActor::StaticClass())
			|| NewParentClass->IsChildOf(ALevelScriptActor::StaticClass()))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' is not compatible with Actor-based Blueprints."),
				*NewParentClass->GetPathName()));
			return false;
		}
	}
	else if (bIsAnimBlueprint)
	{
		if (!NewParentClass->IsChildOf(UAnimInstance::StaticClass()))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' is not compatible with Anim Blueprints."),
				*NewParentClass->GetPathName()));
			return false;
		}
	}
	else if (bIsComponentBlueprint)
	{
		if (!NewParentClass->IsChildOf(UActorComponent::StaticClass()))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' is not compatible with Component Blueprints."),
				*NewParentClass->GetPathName()));
			return false;
		}
	}
	else if (bIsEditorOnlyBlueprint && !bIsWidgetBlueprint)
	{
		if (NewParentClass->IsChildOf(UWidget::StaticClass()))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' is not compatible with non-widget editor utility Blueprints."),
				*NewParentClass->GetPathName()));
			return false;
		}
	}
	else if (NewParentClass->IsChildOf(AActor::StaticClass()))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Class '%s' is not compatible with non-Actor Blueprints."),
			*NewParentClass->GetPathName()));
		return false;
	}

	TSet<const UClass*> AllowedChildrenOfClasses;
	TSet<const UClass*> DisallowedChildrenOfClasses;
	Blueprint->GetReparentingRules(AllowedChildrenOfClasses, DisallowedChildrenOfClasses);
	if (!IsClassAllowedByReparentRules(
		    NewParentClass,
		    AllowedChildrenOfClasses,
		    DisallowedChildrenOfClasses))
	{
		const bool bAllowedMismatch = AllowedChildrenOfClasses.Num() > 0
			&& !IsClassChildOfAny(NewParentClass, AllowedChildrenOfClasses);
		if (bAllowedMismatch)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' is outside this Blueprint's allowed reparenting hierarchy."),
				*NewParentClass->GetPathName()));
		}
		else
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' is disallowed by this Blueprint's reparenting rules."),
				*NewParentClass->GetPathName()));
		}
		return false;
	}

	if (const UClass* SelfClass = Blueprint->GeneratedClass
			? Blueprint->GeneratedClass
			: Blueprint->SkeletonGeneratedClass)
	{
		if (NewParentClass == SelfClass || NewParentClass->IsChildOf(SelfClass))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' cannot parent this Blueprint because it is the Blueprint's generated class or one of its children."),
				*NewParentClass->GetPathName()));
			return false;
		}
	}

	const IKismetCompilerInterface& KismetCompilerModule =
		FModuleManager::LoadModuleChecked<IKismetCompilerInterface>(KISMET_COMPILER_MODULENAME);

	if (Blueprint->ParentClass)
	{
		TSet<const UClass*> MismatchedSubclasses;
		KismetCompilerModule.GetSubclassesWithDifferingBlueprintTypes(
			Blueprint->ParentClass,
			MismatchedSubclasses);
		if (IsClassChildOfAny(NewParentClass, MismatchedSubclasses))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' uses a different Blueprint type and cannot parent '%s'."),
				*NewParentClass->GetPathName(),
				*Blueprint->GetPathName()));
			return false;
		}

		UClass* CurrentBlueprintClassType = nullptr;
		UClass* CurrentGeneratedClassType = nullptr;
		KismetCompilerModule.GetBlueprintTypesForClass(
			Blueprint->ParentClass,
			CurrentBlueprintClassType,
			CurrentGeneratedClassType);

		UClass* TargetBlueprintClassType = nullptr;
		UClass* TargetGeneratedClassType = nullptr;
		KismetCompilerModule.GetBlueprintTypesForClass(
			NewParentClass,
			TargetBlueprintClassType,
			TargetGeneratedClassType);

		if ((CurrentBlueprintClassType && TargetBlueprintClassType
		     && CurrentBlueprintClassType != TargetBlueprintClassType)
		    || (CurrentGeneratedClassType && TargetGeneratedClassType
		        && CurrentGeneratedClassType != TargetGeneratedClassType))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Class '%s' uses Blueprint type '%s', which does not match the current Blueprint type '%s'."),
				*NewParentClass->GetPathName(),
				TargetBlueprintClassType ? *TargetBlueprintClassType->GetName() : TEXT("Unknown"),
				CurrentBlueprintClassType ? *CurrentBlueprintClassType->GetName() : TEXT("Unknown")));
			return false;
		}
	}

	return true;
}

static bool ReparentBlueprint(UBlueprint* Blueprint,
                              const TSharedPtr<FJsonObject>& Payload,
                              TArray<FString>& OutErrors,
                              const bool bValidationOnly,
                              bool& bOutRequiresMutation)
{
	bOutRequiresMutation = false;

	if (!Blueprint)
	{
		OutErrors.Add(TEXT("Blueprint is null."));
		return false;
	}

	FString ParentClassPath;
	if (!ParseParentClassPath(Payload, ParentClassPath))
	{
		OutErrors.Add(TEXT("reparent requires payload.parentClassPath or payload.parent_class_path."));
		return false;
	}

	UClass* NewParentClass = FAuthoringHelpers::ResolveClass(
		ParentClassPath,
		UObject::StaticClass());
	if (!NewParentClass)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Parent class not found: %s"),
			*ParentClassPath));
		return false;
	}

	if (NewParentClass == Blueprint->ParentClass)
	{
		return true;
	}

	if (!ValidateBlueprintReparentTarget(Blueprint, NewParentClass, OutErrors))
	{
		return false;
	}

	const bool bCanMutateBlueprint = !bValidationOnly
		|| Blueprint->GetOutermost() == GetTransientPackage();
	if (!bCanMutateBlueprint)
	{
		return true;
	}

	Blueprint->ParentClass = NewParentClass;
	if (Blueprint->SimpleConstructionScript != nullptr)
	{
		Blueprint->SimpleConstructionScript->ValidateSceneRootNodes();
	}

	FBlueprintEditorUtils::RefreshAllNodes(Blueprint);
	bOutRequiresMutation = true;
	return true;
}

static EBlueprintCompileOptions GetCompileOptionsForOperation(const FString& Operation)
{
	EBlueprintCompileOptions CompileOptions = EBlueprintCompileOptions::None;
	if (Operation == TEXT("reparent"))
	{
		CompileOptions |= EBlueprintCompileOptions::UseDeltaSerializationDuringReinstancing;
		CompileOptions |= EBlueprintCompileOptions::SkipNewVariableDefaultsDetection;
		if (GEditor && GEditor->PlayWorld != nullptr)
		{
			CompileOptions |= EBlueprintCompileOptions::IncludeCDOInReferenceReplacement;
		}
	}

	return CompileOptions;
}

static bool ApplyOperation(UBlueprint* Blueprint,
                           const FString& Operation,
                           const TSharedPtr<FJsonObject>& Payload,
                           TArray<FString>& OutErrors,
                           EBlueprintMutationFlags& OutMutationFlags,
                           const bool bValidationOnly = false)
{
	if (!Blueprint)
	{
		OutErrors.Add(TEXT("Blueprint is null."));
		return false;
	}

	if (Operation == TEXT("replace_variables"))
	{
		OutMutationFlags |=
			EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return ReplaceVariables(Blueprint, GetVariablesArray(Payload), OutErrors);
	}

	if (Operation == TEXT("add_variables"))
	{
		OutMutationFlags |=
			EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return AddVariables(Blueprint, GetVariablesArray(Payload), OutErrors);
	}

	if (Operation == TEXT("patch_variable"))
	{
		OutMutationFlags |=
			EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return PatchVariable(Blueprint, Payload, OutErrors);
	}

	if (Operation == TEXT("replace_components"))
	{
		OutMutationFlags |=
			EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return ReplaceComponents(Blueprint, GetRootComponentsArray(Payload), OutErrors);
	}

	if (Operation == TEXT("patch_component"))
	{
		OutMutationFlags |=
			EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return PatchComponent(Blueprint, Payload, OutErrors);
	}

	if (Operation == TEXT("add_component"))
	{
		OutMutationFlags |=
			EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return AddComponent(Blueprint, Payload, OutErrors);
	}

	if (Operation == TEXT("replace_function_stubs"))
	{
		OutMutationFlags |=
			EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return ReplaceFunctionStubs(Blueprint, GetFunctionArray(Payload), OutErrors);
	}

	if (Operation == TEXT("reparent"))
	{
		bool bRequiresMutation = false;
		const bool bSuccess = ReparentBlueprint(
			Blueprint,
			Payload,
			OutErrors,
			bValidationOnly,
			bRequiresMutation);
		if (bSuccess && bRequiresMutation)
		{
			OutMutationFlags |=
				EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		}
		return bSuccess;
	}

	if (Operation == TEXT("patch_class_defaults"))
	{
		OutMutationFlags |= EBlueprintMutationFlags::Defaults;
		return ApplyClassDefaults(
			Blueprint,
			GetClassDefaultsObject(Payload),
			OutErrors,
			bValidationOnly);
	}

	if (Operation == TEXT("compile"))
	{
		OutMutationFlags |= EBlueprintMutationFlags::Compile;
		return true;
	}

	OutErrors.Add(FString::Printf(
		TEXT("Unsupported Blueprint operation '%s'."),
		*Operation));
	return false;
}

// ─── AnimGraph Authoring ────────────────────────────────────────────────────

static UEdGraph* FindAnimGraph(const UBlueprint* Blueprint, const FString& GraphName)
{
	const FName TargetName = GraphName.IsEmpty() ? FName(TEXT("AnimGraph")) : FName(*GraphName);

	// Main AnimGraph lives in UbergraphPages
	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (Graph && Graph->GetFName() == TargetName)
		{
			return Graph;
		}
	}

	// Anim layer graphs live in FunctionGraphs
	for (UEdGraph* Graph : Blueprint->FunctionGraphs)
	{
		if (Graph && Graph->GetFName() == TargetName)
		{
			return Graph;
		}
	}

	return nullptr;
}

static UClass* ResolveAnimGraphNodeClass(const FString& ClassName, TArray<FString>& OutErrors)
{
	// Try short name first: "AnimGraphNode_ModifyBone" → "/Script/AnimGraph.AnimGraphNode_ModifyBone"
	FString FullPath = ClassName;
	if (!ClassName.Contains(TEXT(".")))
	{
		FullPath = FString::Printf(TEXT("/Script/AnimGraph.%s"), *ClassName);
	}

	UClass* NodeClass = FindObject<UClass>(nullptr, *FullPath);
	if (!NodeClass)
	{
		// Fallback: try to load it
		NodeClass = StaticLoadClass(UAnimGraphNode_Base::StaticClass(), nullptr, *FullPath);
	}

	if (!NodeClass)
	{
		// Try other common modules: AnimGraphRuntime, Engine
		for (const TCHAR* Module : { TEXT("AnimGraphRuntime"), TEXT("Engine") })
		{
			FString AltPath = FString::Printf(TEXT("/Script/%s.%s"), Module, *ClassName);
			NodeClass = FindObject<UClass>(nullptr, *AltPath);
			if (NodeClass) break;
			NodeClass = StaticLoadClass(UAnimGraphNode_Base::StaticClass(), nullptr, *AltPath);
			if (NodeClass) break;
		}
	}

	if (!NodeClass)
	{
		OutErrors.Add(FString::Printf(
			TEXT("AnimGraph node class '%s' not found. Use full path (e.g. /Script/AnimGraph.AnimGraphNode_ModifyBone) or short name."),
			*ClassName));
		return nullptr;
	}

	if (!NodeClass->IsChildOf(UAnimGraphNode_Base::StaticClass()))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Class '%s' is not an AnimGraph node (must derive from UAnimGraphNode_Base)."),
			*ClassName));
		return nullptr;
	}

	return NodeClass;
}

static UEdGraphNode* FindNodeById(
	const UEdGraph* Graph,
	const FString& NodeRef,
	const TMap<FString, UEdGraphNode*>& CreatedNodes,
	TArray<FString>& OutErrors)
{
	// Check created nodes first (by user-assigned ID)
	if (UEdGraphNode* const* Found = CreatedNodes.Find(NodeRef))
	{
		return *Found;
	}

	// Try GUID
	FGuid ParsedGuid;
	if (FGuid::Parse(NodeRef, ParsedGuid))
	{
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (Node && Node->NodeGuid == ParsedGuid)
			{
				return Node;
			}
		}
	}

	// Try by node title / class name suffix
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (!Node) continue;
		// Match by class short name (e.g. "AnimGraphNode_Root")
		if (Node->GetClass()->GetName() == NodeRef)
		{
			return Node;
		}
		// Match by comment/title
		if (Node->NodeComment == NodeRef)
		{
			return Node;
		}
	}

	OutErrors.Add(FString::Printf(
		TEXT("AnimGraph node '%s' not found. Use a node ID from this call, a node GUID, or a class name like 'AnimGraphNode_Root'."),
		*NodeRef));
	return nullptr;
}

static UEdGraphPin* FindPinOnAnimNode(UEdGraphNode* Node, const FString& PinName, TArray<FString>& OutErrors)
{
	if (!Node)
	{
		return nullptr;
	}

	for (UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin && Pin->PinName.ToString() == PinName)
		{
			return Pin;
		}
	}

	// Build available pin list for the error message
	TArray<FString> AvailablePins;
	for (const UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin)
		{
			AvailablePins.Add(FString::Printf(TEXT("%s (%s)"),
				*Pin->PinName.ToString(),
				Pin->Direction == EGPD_Input ? TEXT("in") : TEXT("out")));
		}
	}

	OutErrors.Add(FString::Printf(
		TEXT("Pin '%s' not found on node '%s'. Available pins: [%s]"),
		*PinName,
		*Node->GetClass()->GetName(),
		*FString::Join(AvailablePins, TEXT(", "))));
	return nullptr;
}

static bool AddAnimGraphNodes(UBlueprint* Blueprint,
                              const TSharedPtr<FJsonObject>& Payload,
                              TArray<FString>& OutErrors)
{
	if (!Blueprint || !Payload.IsValid())
	{
		OutErrors.Add(TEXT("add_animgraph_nodes requires a valid Blueprint and payload."));
		return false;
	}

	FString GraphName;
	Payload->TryGetStringField(TEXT("graphName"), GraphName);
	UEdGraph* AnimGraph = FindAnimGraph(Blueprint, GraphName);
	if (!AnimGraph)
	{
		OutErrors.Add(FString::Printf(
			TEXT("AnimGraph '%s' not found. This operation requires an AnimBlueprint."),
			GraphName.IsEmpty() ? TEXT("AnimGraph") : *GraphName));
		return false;
	}

	// Phase 1: Create all nodes
	TMap<FString, UEdGraphNode*> CreatedNodes;
	const TArray<TSharedPtr<FJsonValue>>* NodesArray = nullptr;
	if (!Payload->TryGetArrayField(TEXT("nodes"), NodesArray) || !NodesArray)
	{
		OutErrors.Add(TEXT("add_animgraph_nodes requires a 'nodes' array."));
		return false;
	}

	for (int32 Index = 0; Index < NodesArray->Num(); ++Index)
	{
		const FString NodePath = FString::Printf(TEXT("nodes[%d]"), Index);
		const TSharedPtr<FJsonObject> NodeDef = (*NodesArray)[Index].IsValid()
			? (*NodesArray)[Index]->AsObject()
			: nullptr;
		if (!NodeDef.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s: expected an object."), *NodePath));
			continue;
		}

		FString NodeId;
		if (!NodeDef->TryGetStringField(TEXT("id"), NodeId) || NodeId.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.id: required string identifier."), *NodePath));
			continue;
		}

		if (CreatedNodes.Contains(NodeId))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.id: duplicate node ID '%s'."), *NodePath, *NodeId));
			continue;
		}

		FString ClassName;
		if (!(NodeDef->TryGetStringField(TEXT("class"), ClassName)
			  || NodeDef->TryGetStringField(TEXT("nodeClass"), ClassName))
			|| ClassName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.class: required AnimGraph node class name."), *NodePath));
			continue;
		}

		// Try AnimGraphNode_Base first, then K2Node_VariableGet as fallback
		UEdGraphNode* NewNode = nullptr;

		TArray<FString> AnimResolveErrors;
		UClass* NodeClass = ResolveAnimGraphNodeClass(ClassName, AnimResolveErrors);
		if (NodeClass)
		{
			// Standard AnimGraph node
			UAnimGraphNode_Base* AnimNode = NewObject<UAnimGraphNode_Base>(AnimGraph, NodeClass);
			if (!AnimNode)
			{
				OutErrors.Add(FString::Printf(TEXT("%s: failed to create node of class '%s'."), *NodePath, *ClassName));
				continue;
			}
			NewNode = AnimNode;
		}
		else if (ClassName == TEXT("K2Node_VariableGet") || ClassName.EndsWith(TEXT(".K2Node_VariableGet")))
		{
			// K2Node_VariableGet — variable getter (e.g. Get SpineRotation)
			FString VariableName;
			if (!NodeDef->TryGetStringField(TEXT("variableName"), VariableName) || VariableName.IsEmpty())
			{
				OutErrors.Add(FString::Printf(TEXT("%s: K2Node_VariableGet requires a 'variableName' field."), *NodePath));
				continue;
			}

			UK2Node_VariableGet* VarGetNode = NewObject<UK2Node_VariableGet>(AnimGraph);
			if (!VarGetNode)
			{
				OutErrors.Add(FString::Printf(TEXT("%s: failed to create K2Node_VariableGet."), *NodePath));
				continue;
			}

			// Resolve the property on the Blueprint's class hierarchy so that
			// AllocateDefaultPins can determine the correct pin type.
			// SetSelfMember alone doesn't provide enough context for inherited
			// native properties (e.g. SpineRotation from UCoachAnimInstance).
			const FName VarFName(*VariableName);
			FProperty* VarProperty = Blueprint->ParentClass
				? FindFProperty<FProperty>(Blueprint->ParentClass, VarFName)
				: nullptr;
			if (!VarProperty && Blueprint->SkeletonGeneratedClass)
			{
				VarProperty = FindFProperty<FProperty>(Blueprint->SkeletonGeneratedClass, VarFName);
			}
			if (VarProperty)
			{
				VarGetNode->VariableReference.SetFromField<FProperty>(VarProperty, /*bSelfContext=*/true);
			}
			else
			{
				VarGetNode->VariableReference.SetSelfMember(VarFName);
			}
			NewNode = VarGetNode;
		}
		else
		{
			// Neither an AnimGraph node nor a supported K2Node
			OutErrors.Append(AnimResolveErrors);
			continue;
		}

		AnimGraph->AddNode(NewNode, /*bFromUI=*/false, /*bSelectNewNode=*/false);
		NewNode->CreateNewGuid();
		NewNode->PostPlacedNewNode();
		if (NewNode->Pins.Num() == 0)
		{
			NewNode->AllocateDefaultPins();
		}

		// K2Node_VariableGet: the skeleton class may not be compiled yet,
		// so AllocateDefaultPins/ReconstructNode can't resolve the variable.
		// Create the output pin manually from the resolved FProperty.
		if (NewNode->IsA<UK2Node_VariableGet>() && NewNode->Pins.Num() == 0)
		{
			NewNode->ReconstructNode();
			if (NewNode->Pins.Num() == 0)
			{
				// Manual fallback: create pin from the native property type.
				UK2Node_VariableGet* VarNode = CastChecked<UK2Node_VariableGet>(NewNode);
				const FName VarName = VarNode->VariableReference.GetMemberName();
				FProperty* Prop = Blueprint->ParentClass
					? FindFProperty<FProperty>(Blueprint->ParentClass, VarName)
					: nullptr;
				if (Prop)
				{
					FEdGraphPinType PinType;
					if (GetDefault<UEdGraphSchema_K2>()->ConvertPropertyToPinType(Prop, PinType))
					{
						NewNode->CreatePin(EGPD_Output, PinType, VarName);
					}
				}
			}
		}

		// Position
		const TSharedPtr<FJsonObject>* PositionObj = nullptr;
		if (NodeDef->TryGetObjectField(TEXT("position"), PositionObj) && PositionObj)
		{
			double X = 0, Y = 0;
			(*PositionObj)->TryGetNumberField(TEXT("x"), X);
			(*PositionObj)->TryGetNumberField(TEXT("y"), Y);
			NewNode->NodePosX = static_cast<int32>(X);
			NewNode->NodePosY = static_cast<int32>(Y);
		}

		// Comment
		FString NodeComment;
		if (NodeDef->TryGetStringField(TEXT("comment"), NodeComment))
		{
			NewNode->NodeComment = NodeComment;
		}

		// Apply node properties via reflection
		const TSharedPtr<FJsonObject>* PropsObj = nullptr;
		if ((NodeDef->TryGetObjectField(TEXT("nodeProperties"), PropsObj)
			|| NodeDef->TryGetObjectField(TEXT("properties"), PropsObj))
			&& PropsObj)
		{
			TArray<FString> PropErrors;
			FPropertySerializer::ApplyPropertiesFromJson(NewNode, *PropsObj, PropErrors, false, true);
			for (const FString& PropError : PropErrors)
			{
				OutErrors.Add(FString::Printf(TEXT("%s.properties: %s"), *NodePath, *PropError));
			}
		}

		CreatedNodes.Add(NodeId, NewNode);
	}

	if (CreatedNodes.Num() == 0)
	{
		return OutErrors.Num() == 0;
	}

	// Phase 2: Connect pins
	const TArray<TSharedPtr<FJsonValue>>* ConnectionsArray = nullptr;
	if (Payload->TryGetArrayField(TEXT("connections"), ConnectionsArray) && ConnectionsArray)
	{
		for (int32 Index = 0; Index < ConnectionsArray->Num(); ++Index)
		{
			const FString ConnPath = FString::Printf(TEXT("connections[%d]"), Index);
			const TSharedPtr<FJsonObject> ConnDef = (*ConnectionsArray)[Index].IsValid()
				? (*ConnectionsArray)[Index]->AsObject()
				: nullptr;
			if (!ConnDef.IsValid())
			{
				OutErrors.Add(FString::Printf(TEXT("%s: expected an object."), *ConnPath));
				continue;
			}

			// Parse "source" and "target" as "nodeRef:pinName" or separate fields
			FString SourceNodeRef, SourcePinName, TargetNodeRef, TargetPinName;

			FString SourceStr, TargetStr;
			if (ConnDef->TryGetStringField(TEXT("source"), SourceStr) && SourceStr.Contains(TEXT(":")))
			{
				SourceStr.Split(TEXT(":"), &SourceNodeRef, &SourcePinName);
			}
			else
			{
				ConnDef->TryGetStringField(TEXT("sourceNode"), SourceNodeRef);
				ConnDef->TryGetStringField(TEXT("sourcePin"), SourcePinName);
			}

			if (ConnDef->TryGetStringField(TEXT("target"), TargetStr) && TargetStr.Contains(TEXT(":")))
			{
				TargetStr.Split(TEXT(":"), &TargetNodeRef, &TargetPinName);
			}
			else
			{
				ConnDef->TryGetStringField(TEXT("targetNode"), TargetNodeRef);
				ConnDef->TryGetStringField(TEXT("targetPin"), TargetPinName);
			}

			if (SourceNodeRef.IsEmpty() || SourcePinName.IsEmpty()
				|| TargetNodeRef.IsEmpty() || TargetPinName.IsEmpty())
			{
				OutErrors.Add(FString::Printf(
					TEXT("%s: requires source and target in 'nodeRef:pinName' format or separate sourceNode/sourcePin/targetNode/targetPin fields."),
					*ConnPath));
				continue;
			}

			UEdGraphNode* SourceNode = FindNodeById(AnimGraph, SourceNodeRef, CreatedNodes, OutErrors);
			UEdGraphNode* TargetNode = FindNodeById(AnimGraph, TargetNodeRef, CreatedNodes, OutErrors);
			if (!SourceNode || !TargetNode) continue;

			UEdGraphPin* SourcePin = FindPinOnAnimNode(SourceNode, SourcePinName, OutErrors);
			UEdGraphPin* TargetPin = FindPinOnAnimNode(TargetNode, TargetPinName, OutErrors);
			if (!SourcePin || !TargetPin) continue;

			// Break existing connections if requested
			bool bBreakExisting = false;
			ConnDef->TryGetBoolField(TEXT("breakExisting"), bBreakExisting);
			if (bBreakExisting)
			{
				TargetPin->BreakAllPinLinks(/*bNotify=*/false);
			}

			if (!AnimGraph->GetSchema()->TryCreateConnection(SourcePin, TargetPin))
			{
				OutErrors.Add(FString::Printf(
					TEXT("%s: failed to connect %s:%s → %s:%s. Pins may be incompatible."),
					*ConnPath,
					*SourceNodeRef, *SourcePinName,
					*TargetNodeRef, *TargetPinName));
			}
		}
	}

	return OutErrors.Num() == 0;
}

static bool ConnectAnimGraphPins(UBlueprint* Blueprint,
                                 const TSharedPtr<FJsonObject>& Payload,
                                 TArray<FString>& OutErrors)
{
	if (!Blueprint || !Payload.IsValid())
	{
		OutErrors.Add(TEXT("connect_animgraph_pins requires a valid Blueprint and payload."));
		return false;
	}

	FString GraphName;
	Payload->TryGetStringField(TEXT("graphName"), GraphName);
	UEdGraph* AnimGraph = FindAnimGraph(Blueprint, GraphName);
	if (!AnimGraph)
	{
		OutErrors.Add(FString::Printf(
			TEXT("AnimGraph '%s' not found. This operation requires an AnimBlueprint."),
			GraphName.IsEmpty() ? TEXT("AnimGraph") : *GraphName));
		return false;
	}

	TMap<FString, UEdGraphNode*> EmptyMap;
	const TArray<TSharedPtr<FJsonValue>>* ConnectionsArray = nullptr;
	if (!Payload->TryGetArrayField(TEXT("connections"), ConnectionsArray) || !ConnectionsArray)
	{
		OutErrors.Add(TEXT("connect_animgraph_pins requires a 'connections' array."));
		return false;
	}

	// Also handle disconnections
	const TArray<TSharedPtr<FJsonValue>>* DisconnectsArray = nullptr;
	Payload->TryGetArrayField(TEXT("disconnections"), DisconnectsArray);

	// Process disconnections first
	if (DisconnectsArray)
	{
		for (int32 Index = 0; Index < DisconnectsArray->Num(); ++Index)
		{
			const FString DiscPath = FString::Printf(TEXT("disconnections[%d]"), Index);
			const TSharedPtr<FJsonObject> DiscDef = (*DisconnectsArray)[Index].IsValid()
				? (*DisconnectsArray)[Index]->AsObject()
				: nullptr;
			if (!DiscDef.IsValid()) continue;

			FString NodeRef, PinName;
			FString CompactRef;
			if (DiscDef->TryGetStringField(TEXT("pin"), CompactRef) && CompactRef.Contains(TEXT(":")))
			{
				CompactRef.Split(TEXT(":"), &NodeRef, &PinName);
			}
			else
			{
				DiscDef->TryGetStringField(TEXT("node"), NodeRef);
				DiscDef->TryGetStringField(TEXT("pin"), PinName);
			}

			if (NodeRef.IsEmpty() || PinName.IsEmpty())
			{
				OutErrors.Add(FString::Printf(TEXT("%s: requires 'nodeRef:pinName' format."), *DiscPath));
				continue;
			}

			UEdGraphNode* Node = FindNodeById(AnimGraph, NodeRef, EmptyMap, OutErrors);
			if (!Node) continue;

			UEdGraphPin* Pin = FindPinOnAnimNode(Node, PinName, OutErrors);
			if (!Pin) continue;

			Pin->BreakAllPinLinks(/*bNotify=*/false);
		}
	}

	// Process connections
	for (int32 Index = 0; Index < ConnectionsArray->Num(); ++Index)
	{
		const FString ConnPath = FString::Printf(TEXT("connections[%d]"), Index);
		const TSharedPtr<FJsonObject> ConnDef = (*ConnectionsArray)[Index].IsValid()
			? (*ConnectionsArray)[Index]->AsObject()
			: nullptr;
		if (!ConnDef.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s: expected an object."), *ConnPath));
			continue;
		}

		FString SourceNodeRef, SourcePinName, TargetNodeRef, TargetPinName;

		FString SourceStr, TargetStr;
		if (ConnDef->TryGetStringField(TEXT("source"), SourceStr) && SourceStr.Contains(TEXT(":")))
		{
			SourceStr.Split(TEXT(":"), &SourceNodeRef, &SourcePinName);
		}
		else
		{
			ConnDef->TryGetStringField(TEXT("sourceNode"), SourceNodeRef);
			ConnDef->TryGetStringField(TEXT("sourcePin"), SourcePinName);
		}

		if (ConnDef->TryGetStringField(TEXT("target"), TargetStr) && TargetStr.Contains(TEXT(":")))
		{
			TargetStr.Split(TEXT(":"), &TargetNodeRef, &TargetPinName);
		}
		else
		{
			ConnDef->TryGetStringField(TEXT("targetNode"), TargetNodeRef);
			ConnDef->TryGetStringField(TEXT("targetPin"), TargetPinName);
		}

		if (SourceNodeRef.IsEmpty() || SourcePinName.IsEmpty()
			|| TargetNodeRef.IsEmpty() || TargetPinName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(
				TEXT("%s: requires source and target in 'nodeRef:pinName' format."),
				*ConnPath));
			continue;
		}

		UEdGraphNode* SourceNode = FindNodeById(AnimGraph, SourceNodeRef, EmptyMap, OutErrors);
		UEdGraphNode* TargetNode = FindNodeById(AnimGraph, TargetNodeRef, EmptyMap, OutErrors);
		if (!SourceNode || !TargetNode) continue;

		UEdGraphPin* SourcePin = FindPinOnAnimNode(SourceNode, SourcePinName, OutErrors);
		UEdGraphPin* TargetPin = FindPinOnAnimNode(TargetNode, TargetPinName, OutErrors);
		if (!SourcePin || !TargetPin) continue;

		bool bBreakExisting = false;
		ConnDef->TryGetBoolField(TEXT("breakExisting"), bBreakExisting);
		if (bBreakExisting)
		{
			TargetPin->BreakAllPinLinks(/*bNotify=*/false);
		}

		if (!AnimGraph->GetSchema()->TryCreateConnection(SourcePin, TargetPin))
		{
			OutErrors.Add(FString::Printf(
				TEXT("%s: failed to connect %s:%s → %s:%s."),
				*ConnPath,
				*SourceNodeRef, *SourcePinName,
				*TargetNodeRef, *TargetPinName));
		}
	}

	return OutErrors.Num() == 0;
}

static bool ApplyGraphOperation(UBlueprint* Blueprint,
                                const FString& Operation,
                                const TSharedPtr<FJsonObject>& Payload,
                                TArray<FString>& OutErrors,
                                EBlueprintMutationFlags& OutMutationFlags)
{
	if (!Blueprint)
	{
		OutErrors.Add(TEXT("Blueprint is null."));
		return false;
	}

	if (Operation == TEXT("upsert_function_graphs"))
	{
		OutMutationFlags |= EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return UpsertFunctionStubs(Blueprint, GetFunctionArray(Payload), OutErrors);
	}

	if (Operation == TEXT("append_function_call_to_sequence"))
	{
		OutMutationFlags |= EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return AppendFunctionCallToSequence(Blueprint, Payload, OutErrors);
	}

	if (Operation == TEXT("add_animgraph_nodes"))
	{
		OutMutationFlags |= EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return AddAnimGraphNodes(Blueprint, Payload, OutErrors);
	}

	if (Operation == TEXT("connect_animgraph_pins"))
	{
		OutMutationFlags |= EBlueprintMutationFlags::Structural | EBlueprintMutationFlags::Compile;
		return ConnectAnimGraphPins(Blueprint, Payload, OutErrors);
	}

	if (Operation == TEXT("compile"))
	{
		OutMutationFlags |= EBlueprintMutationFlags::Compile;
		return true;
	}

	OutErrors.Add(FString::Printf(
		TEXT("Unsupported Blueprint graph operation '%s'."),
		*Operation));
	return false;
}

static bool ApplyCreatePayload(UBlueprint* Blueprint,
                               const TSharedPtr<FJsonObject>& Payload,
                               TArray<FString>& OutErrors)
{
	bool bSuccess = true;

	if (GetVariablesArray(Payload).Num() > 0)
	{
		bSuccess &= ReplaceVariables(Blueprint, GetVariablesArray(Payload), OutErrors);
	}

	if (GetRootComponentsArray(Payload).Num() > 0)
	{
		bSuccess &= ReplaceComponents(
			Blueprint,
			GetRootComponentsArray(Payload),
			OutErrors);
	}

	if (GetFunctionArray(Payload).Num() > 0)
	{
		bSuccess &= ReplaceFunctionStubs(
			Blueprint,
			GetFunctionArray(Payload),
			OutErrors);
	}

	if (const TSharedPtr<FJsonObject> DefaultsObject = GetClassDefaultsObject(Payload))
	{
		bSuccess &= ApplyClassDefaults(Blueprint, DefaultsObject, OutErrors, false);
	}

	return bSuccess;
}

} // namespace BlueprintAuthoringInternal

TSharedPtr<FJsonObject> FBlueprintAuthoring::Create(
	const FString& AssetPath,
	const FString& ParentClassPath,
	const TSharedPtr<FJsonObject>& PayloadJson,
	const bool bValidateOnly)
{
	using namespace BlueprintAuthoringInternal;

	FAssetMutationContext Context(
		TEXT("create_blueprint"),
		AssetPath,
		TEXT("Blueprint"),
		bValidateOnly);

	UClass* ParentClass = FAuthoringHelpers::ResolveClass(
		ParentClassPath,
		UObject::StaticClass());
	if (!ParentClass)
	{
		Context.AddError(
			TEXT("parent_class_not_found"),
			FString::Printf(TEXT("Parent class not found: %s"), *ParentClassPath),
			ParentClassPath);
		return Context.BuildResult(false);
	}

	if (!FKismetEditorUtilities::CanCreateBlueprintOfClass(ParentClass))
	{
		Context.AddError(
			TEXT("invalid_parent_class"),
			FString::Printf(
				TEXT("Class '%s' cannot be used to create a Blueprint."),
				*ParentClass->GetPathName()),
			ParentClassPath);
		return Context.BuildResult(false);
	}

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(
			TEXT("asset_exists"),
			FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	const FName PreviewName = MakeUniqueObjectName(
		GetTransientPackage(),
		UBlueprint::StaticClass(),
		TEXT("BPPreview"));
	UBlueprint* PreviewBlueprint = FKismetEditorUtilities::CreateBlueprint(
		ParentClass,
		GetTransientPackage(),
		PreviewName,
		BPTYPE_Normal);
	if (!PreviewBlueprint)
	{
		Context.AddError(
			TEXT("preview_create_failed"),
			TEXT("Failed to create transient Blueprint preview."));
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	ApplyCreatePayload(PreviewBlueprint, Payload, ValidationErrors);
	Context.SetValidationSummary(
		ValidationErrors.Num() == 0,
		ValidationErrors.Num() == 0
			? TEXT("Blueprint payload validated.")
			: TEXT("Blueprint payload failed validation."),
		ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, AssetPath);
	}
	if (ValidationErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	FAuthoringHelpers::CompileBlueprint(PreviewBlueprint, Context, TEXT("Blueprint"));
	if (Context.CompileSummary.IsValid()
		&& !Context.CompileSummary->GetBoolField(TEXT("success")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create Blueprint")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(
			TEXT("package_create_failed"),
			FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(
		ParentClass,
		Package,
		AssetName,
		BPTYPE_Normal);
	if (!Blueprint)
	{
		Context.AddError(
			TEXT("asset_create_failed"),
			FString::Printf(TEXT("Failed to create Blueprint asset: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	Blueprint->Modify();

	TArray<FString> ApplyErrors;
	ApplyCreatePayload(Blueprint, Payload, ApplyErrors);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FAuthoringHelpers::CompileBlueprint(Blueprint, Context, TEXT("Blueprint"));
	if (Context.CompileSummary.IsValid()
		&& !Context.CompileSummary->GetBoolField(TEXT("success")))
	{
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(Blueprint);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(Blueprint);
	if (Blueprint->GeneratedClass && Blueprint->GeneratedClass->GetDefaultObject())
	{
		Context.TrackDirtyObject(Blueprint->GeneratedClass->GetDefaultObject());
	}

	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FBlueprintAuthoring::Modify(
	UBlueprint* Blueprint,
	const FString& Operation,
	const TSharedPtr<FJsonObject>& PayloadJson,
	const bool bValidateOnly)
{
	using namespace BlueprintAuthoringInternal;

	const FString AssetPath = Blueprint ? Blueprint->GetPathName() : FString();
	FAssetMutationContext Context(
		TEXT("modify_blueprint_members"),
		AssetPath,
		TEXT("Blueprint"),
		bValidateOnly);

	if (!Blueprint)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("Blueprint is null."));
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);
	const EBlueprintCompileOptions AdditionalCompileOptions =
		GetCompileOptionsForOperation(Operation);
	UBlueprint* WorkingBlueprint = Blueprint;
	if (bValidateOnly)
	{
		// DuplicateObject is unsafe for BPs with inherited components: it triggers
		// PostDuplicateBlueprint → CompileSynchronouslyImpl → CreateDefaultObject → FATAL.
		// patch_class_defaults validates against live CDO via FTemporaryPropertyStorage.
		// patch_component on BPs with Blueprint parents must skip to avoid the crash.
		// reparent validation also skips duplication entirely: transient duplicate compilation
		// can fatal while recreating skeleton defaults during class replacement.
		// BPs with only C++ parents can safely use DuplicateObject for rollback.
		const bool bHasBlueprintParent = Blueprint->ParentClass
			&& Cast<UBlueprintGeneratedClass>(Blueprint->ParentClass) != nullptr;
		const bool bSkipDuplicate = (Operation == TEXT("patch_class_defaults"))
			|| (Operation == TEXT("reparent"))
			|| (Operation == TEXT("patch_component") && bHasBlueprintParent);
		if (!bSkipDuplicate)
		{
			// Use a unique name to prevent CDO class-mismatch crashes during
			// PostDuplicateBlueprint compilation (critical for AnimBlueprints where
			// duplication triggers immediate recompilation via PostDuplicateBlueprint).
			const FName PreviewName = MakeUniqueObjectName(
				GetTransientPackage(),
				Blueprint->GetClass(),
				*FString::Printf(TEXT("%s_BEValidation"), *Blueprint->GetName()));
			WorkingBlueprint = DuplicateObject<UBlueprint>(Blueprint, GetTransientPackage(), PreviewName);
			if (!WorkingBlueprint)
			{
				Context.AddError(
					TEXT("preview_duplicate_failed"),
					TEXT("Failed to duplicate Blueprint for validation."));
				return Context.BuildResult(false);
			}
		}
	}

	TArray<FString> ValidationErrors;
	EBlueprintMutationFlags MutationFlags = EBlueprintMutationFlags::None;
	ApplyOperation(
		WorkingBlueprint,
		Operation,
		Payload,
		ValidationErrors,
		MutationFlags,
		bValidateOnly);
	Context.SetValidationSummary(
		ValidationErrors.Num() == 0,
		ValidationErrors.Num() == 0
			? TEXT("Blueprint payload validated.")
			: TEXT("Blueprint payload failed validation."),
		ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, AssetPath);
	}
	if (ValidationErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Structural))
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WorkingBlueprint);
	}

	if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Compile))
	{
		FAuthoringHelpers::CompileBlueprint(
			WorkingBlueprint,
			Context,
			TEXT("Blueprint"),
			AdditionalCompileOptions);
		if (Context.CompileSummary.IsValid()
			&& !Context.CompileSummary->GetBoolField(TEXT("success")))
		{
			return Context.BuildResult(false);
		}
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify Blueprint")));
	Blueprint->Modify();

	auto RollbackBlueprint = [&Context, Blueprint, &AssetPath]()
	{
		FString ReloadError;
		const bool bRolledBack = ReloadBlueprintPackage(Blueprint, ReloadError);
		if (bRolledBack)
		{
			Context.AddWarning(TEXT("rollback_applied"),
			                   TEXT("Blueprint mutation failed and the package was reloaded from disk to discard in-memory changes."),
			                   AssetPath);
		}
		else
		{
			Context.AddError(TEXT("rollback_failed"),
			                 FString::Printf(TEXT("Blueprint mutation failed and rollback also failed: %s"), *ReloadError),
			                 AssetPath);
		}
	};

	TArray<FString> ApplyErrors;
	MutationFlags = EBlueprintMutationFlags::None;
	ApplyOperation(Blueprint, Operation, Payload, ApplyErrors, MutationFlags);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		RollbackBlueprint();
		return Context.BuildResult(false);
	}

	if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Structural))
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	}
	else if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Defaults))
	{
		FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	}

	if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Compile))
	{
		FAuthoringHelpers::CompileBlueprint(
			Blueprint,
			Context,
			TEXT("Blueprint"),
			AdditionalCompileOptions);
		if (Context.CompileSummary.IsValid()
			&& !Context.CompileSummary->GetBoolField(TEXT("success")))
		{
			RollbackBlueprint();
			return Context.BuildResult(false);
		}
	}

	Blueprint->MarkPackageDirty();
	Context.TrackDirtyObject(Blueprint);
	if (Blueprint->GeneratedClass && Blueprint->GeneratedClass->GetDefaultObject())
	{
		Context.TrackDirtyObject(Blueprint->GeneratedClass->GetDefaultObject());
	}

	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FBlueprintAuthoring::ModifyGraphs(
	UBlueprint* Blueprint,
	const FString& Operation,
	const TSharedPtr<FJsonObject>& PayloadJson,
	const bool bValidateOnly)
{
	using namespace BlueprintAuthoringInternal;

	const FString AssetPath = Blueprint ? Blueprint->GetPathName() : FString();
	FAssetMutationContext Context(
		TEXT("modify_blueprint_graphs"),
		AssetPath,
		TEXT("Blueprint"),
		bValidateOnly);

	if (!Blueprint)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("Blueprint is null."));
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);
	auto BuildGraphMutationResult = [&Context](UBlueprint* TargetBlueprint, const bool bSuccess) -> TSharedPtr<FJsonObject>
	{
		const TSharedPtr<FJsonObject> Result = Context.BuildResult(bSuccess);
		if (!Result.IsValid() || !TargetBlueprint)
		{
			return Result;
		}

		TArray<TSharedPtr<FJsonValue>> FunctionGraphNames;
		for (UEdGraph* Graph : TargetBlueprint->FunctionGraphs)
		{
			if (Graph)
			{
				FunctionGraphNames.Add(MakeShared<FJsonValueString>(Graph->GetName()));
			}
		}
		Result->SetArrayField(TEXT("functionGraphs"), FunctionGraphNames);
		return Result;
	};

	UBlueprint* WorkingBlueprint = Blueprint;
	if (bValidateOnly)
	{
		// Use a unique name to prevent CDO class-mismatch crashes during
		// PostDuplicateBlueprint compilation (critical for AnimBlueprints where
		// duplication triggers immediate recompilation via PostDuplicateBlueprint).
		const FName PreviewName = MakeUniqueObjectName(
			GetTransientPackage(),
			Blueprint->GetClass(),
			*FString::Printf(TEXT("%s_BEValidation"), *Blueprint->GetName()));
		WorkingBlueprint = DuplicateObject<UBlueprint>(Blueprint, GetTransientPackage(), PreviewName);
		if (!WorkingBlueprint)
		{
			Context.AddError(
				TEXT("preview_duplicate_failed"),
				TEXT("Failed to duplicate Blueprint for validation."));
			return Context.BuildResult(false);
		}
	}

	TArray<FString> ValidationErrors;
	EBlueprintMutationFlags MutationFlags = EBlueprintMutationFlags::None;
	ApplyGraphOperation(
		WorkingBlueprint,
		Operation,
		Payload,
		ValidationErrors,
		MutationFlags);
	Context.SetValidationSummary(
		ValidationErrors.Num() == 0,
		ValidationErrors.Num() == 0
			? TEXT("Blueprint graph payload validated.")
			: TEXT("Blueprint graph payload failed validation."),
		ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, AssetPath);
	}
	if (ValidationErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Structural))
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WorkingBlueprint);
	}

	if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Compile))
	{
		FAuthoringHelpers::CompileBlueprint(WorkingBlueprint, Context, TEXT("Blueprint"));
		if (Context.CompileSummary.IsValid()
			&& !Context.CompileSummary->GetBoolField(TEXT("success")))
		{
			return Context.BuildResult(false);
		}
	}

	if (bValidateOnly)
	{
		return BuildGraphMutationResult(WorkingBlueprint, true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify Blueprint Graphs")));
	Blueprint->Modify();

	auto RollbackBlueprint = [&Context, Blueprint, &AssetPath]()
	{
		FString ReloadError;
		const bool bRolledBack = ReloadBlueprintPackage(Blueprint, ReloadError);
		if (bRolledBack)
		{
			Context.AddWarning(TEXT("rollback_applied"),
			                   TEXT("Blueprint graph mutation failed and the package was reloaded from disk to discard in-memory changes."),
			                   AssetPath);
		}
		else
		{
			Context.AddError(TEXT("rollback_failed"),
			                 FString::Printf(TEXT("Blueprint graph mutation failed and rollback also failed: %s"), *ReloadError),
			                 AssetPath);
		}
	};

	TArray<FString> ApplyErrors;
	MutationFlags = EBlueprintMutationFlags::None;
	ApplyGraphOperation(Blueprint, Operation, Payload, ApplyErrors, MutationFlags);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		RollbackBlueprint();
		return Context.BuildResult(false);
	}

	if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Structural))
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	}

	if (EnumHasAnyFlags(MutationFlags, EBlueprintMutationFlags::Compile))
	{
		FAuthoringHelpers::CompileBlueprint(Blueprint, Context, TEXT("Blueprint"));
		if (Context.CompileSummary.IsValid()
			&& !Context.CompileSummary->GetBoolField(TEXT("success")))
		{
			RollbackBlueprint();
			return Context.BuildResult(false);
		}
	}

	Blueprint->MarkPackageDirty();
	Context.TrackDirtyObject(Blueprint);
	if (Blueprint->GeneratedClass && Blueprint->GeneratedClass->GetDefaultObject())
	{
		Context.TrackDirtyObject(Blueprint->GeneratedClass->GetDefaultObject());
	}

	return BuildGraphMutationResult(Blueprint, true);
}
