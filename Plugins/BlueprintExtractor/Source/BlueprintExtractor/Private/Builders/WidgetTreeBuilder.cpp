#include "Builders/WidgetTreeBuilder.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"
#include "Authoring/BlueprintAuthoring.h"
#include "Extractors/ClassDefaultsExtractor.h"
#include "Extractors/WidgetTreeExtractor.h"
#include "PropertySerializer.h"

#include "WidgetBlueprint.h"
#include "Animation/WidgetAnimation.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Widget.h"
#include "Components/ListViewBase.h"
#include "Components/NamedSlot.h"
#include "Components/PanelWidget.h"
#include "Components/PanelSlot.h"
#include "Blueprint/UserWidget.h"
#include "Engine/Font.h"
#include "Fonts/SlateFontInfo.h"
#include "MovieScene.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "JsonObjectConverter.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "EdGraphSchema_K2.h"
#include "BlueprintCompilationManager.h"
#include "KismetCompilerModule.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Kismet2/Kismet2NameValidators.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Modules/ModuleManager.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "WidgetBlueprintEditor.h"
#include "WidgetBlueprintEditorUtils.h"
#include "Logging/TokenizedMessage.h"

#include "CoreGlobals.h"
#include "Misc/PackageName.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectIterator.h"
#include "UObject/Package.h"

#include <initializer_list>

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

namespace WidgetTreeBuilderInternal
{

static TSharedPtr<FJsonObject> MakeErrorResult(const FString& ErrorMessage)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), false);
	Result->SetStringField(TEXT("error"), ErrorMessage);
	return Result;
}

static void AddAssetPathFields(const TSharedPtr<FJsonObject>& Result, const FString& AssetPath)
{
	if (!Result.IsValid())
	{
		return;
	}

	const FString ObjectPath = NormalizeAssetObjectPath(AssetPath);
	FString PackagePath = ObjectPath;
	if (FPackageName::IsValidObjectPath(ObjectPath))
	{
		PackagePath = FPackageName::ObjectPathToPackageName(ObjectPath);
	}

	if (!PackagePath.IsEmpty())
	{
		Result->SetStringField(TEXT("packagePath"), PackagePath);
	}

	if (!ObjectPath.IsEmpty())
	{
		Result->SetStringField(TEXT("objectPath"), ObjectPath);
	}
}

static void AddAssetPathFields(const TSharedPtr<FJsonObject>& Result, const UObject* Asset)
{
	AddAssetPathFields(Result, Asset ? Asset->GetPathName() : FString());
}

static TSharedPtr<FJsonObject> MakeErrorResult(const FString& ErrorMessage, const TArray<FString>& Errors)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), false);
	Result->SetStringField(TEXT("error"), ErrorMessage);

	TArray<TSharedPtr<FJsonValue>> ErrorArray;
	for (const FString& Err : Errors)
	{
		ErrorArray.Add(MakeShared<FJsonValueString>(Err));
	}
	Result->SetArrayField(TEXT("errors"), ErrorArray);
	return Result;
}

static TSharedRef<FJsonValueArray> ErrorsToJsonArray(const TArray<FString>& Errors)
{
	TArray<TSharedPtr<FJsonValue>> Array;
	for (const FString& Err : Errors)
	{
		Array.Add(MakeShared<FJsonValueString>(Err));
	}
	return MakeShared<FJsonValueArray>(Array);
}

static void AddLegacyErrorFields(const TSharedPtr<FJsonObject>& Result, const TArray<FString>& Errors)
{
	if (!Result.IsValid())
	{
		return;
	}

	Result->SetField(TEXT("errors"), ErrorsToJsonArray(Errors));
	if (Errors.Num() > 0)
	{
		Result->SetStringField(TEXT("error"), Errors[0]);
	}
}

static TSharedPtr<FJsonObject> BuildMutationResult(FAssetMutationContext& Context,
                                                   const bool bSuccess,
                                                   const TArray<FString>& Errors)
{
	for (const FString& Error : Errors)
	{
		Context.AddError(TEXT("mutation_error"), Error);
	}

	const TSharedPtr<FJsonObject> Result = Context.BuildResult(bSuccess);
	AddLegacyErrorFields(Result, Errors);
	return Result;
}

static FString GetBlueprintStatusString(const EBlueprintStatus Status)
{
	switch (Status)
	{
	case BS_Unknown:
		return TEXT("Unknown");
	case BS_Dirty:
		return TEXT("Dirty");
	case BS_Error:
		return TEXT("Error");
	case BS_UpToDate:
		return TEXT("UpToDate");
	case BS_BeingCreated:
		return TEXT("BeingCreated");
	case BS_UpToDateWithWarnings:
		return TEXT("UpToDateWithWarnings");
	default:
		return TEXT("Unknown");
	}
}

static TSharedPtr<FJsonValueObject> MakeMessageValue(const FString& Severity, const FString& Message)
{
	const TSharedPtr<FJsonObject> MessageObject = MakeShared<FJsonObject>();
	MessageObject->SetStringField(TEXT("severity"), Severity);
	MessageObject->SetStringField(TEXT("message"), Message);
	return MakeShared<FJsonValueObject>(MessageObject);
}

static TSharedPtr<FJsonObject> MakeCompileResult(const bool bSuccess,
                                                 const FString& StatusString,
                                                 const TArray<TSharedPtr<FJsonValue>>& Errors,
                                                 const TArray<TSharedPtr<FJsonValue>>& Warnings,
                                                 const TArray<TSharedPtr<FJsonValue>>& Messages,
                                                 const int32 ErrorCount,
                                                 const int32 WarningCount)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), bSuccess);
	Result->SetStringField(TEXT("status"), StatusString);
	Result->SetArrayField(TEXT("errors"), Errors);
	Result->SetArrayField(TEXT("warnings"), Warnings);
	Result->SetArrayField(TEXT("messages"), Messages);
	Result->SetNumberField(TEXT("errorCount"), ErrorCount);
	Result->SetNumberField(TEXT("warningCount"), WarningCount);
	return Result;
}

static void CollectCompilerMessages(const FCompilerResultsLog& CompileResults,
                                    TArray<TSharedPtr<FJsonValue>>& OutErrors,
                                    TArray<TSharedPtr<FJsonValue>>& OutWarnings,
                                    TArray<TSharedPtr<FJsonValue>>& OutMessages,
                                    bool* bOutBindWidgetIssue = nullptr,
                                    bool* bOutAbstractClassIssue = nullptr,
                                    bool* bOutListViewEntryIssue = nullptr)
{
	for (const TSharedRef<FTokenizedMessage>& Message : CompileResults.Messages)
	{
		const FString MessageText = Message->ToText().ToString();
		if (bOutBindWidgetIssue
			&& (MessageText.Contains(TEXT("BindWidget"), ESearchCase::IgnoreCase)
				|| MessageText.Contains(TEXT("bound widget"), ESearchCase::IgnoreCase)))
		{
			*bOutBindWidgetIssue = true;
		}
		if (bOutAbstractClassIssue
			&& MessageText.Contains(TEXT("abstract"), ESearchCase::IgnoreCase)
			&& MessageText.Contains(TEXT("widget"), ESearchCase::IgnoreCase))
		{
			*bOutAbstractClassIssue = true;
		}
		if (bOutListViewEntryIssue
			&& (MessageText.Contains(TEXT("EntryWidgetClass"), ESearchCase::IgnoreCase)
				|| MessageText.Contains(TEXT("entry widget"), ESearchCase::IgnoreCase))
			&& MessageText.Contains(TEXT("list"), ESearchCase::IgnoreCase))
		{
			*bOutListViewEntryIssue = true;
		}

		switch (Message->GetSeverity())
		{
		case EMessageSeverity::Error:
			OutErrors.Add(MakeShared<FJsonValueString>(MessageText));
			OutMessages.Add(MakeMessageValue(TEXT("error"), MessageText));
			break;
		case EMessageSeverity::Warning:
		case EMessageSeverity::PerformanceWarning:
			OutWarnings.Add(MakeShared<FJsonValueString>(MessageText));
			OutMessages.Add(MakeMessageValue(TEXT("warning"), MessageText));
			break;
		default:
			OutMessages.Add(MakeMessageValue(TEXT("info"), MessageText));
			break;
		}
	}
}

static TArray<TSharedPtr<FJsonValue>> BuildCompileRecoveryHints(const bool bBindWidgetIssue,
                                                                const bool bAbstractClassIssue,
                                                                const bool bListViewEntryIssue)
{
	TArray<TSharedPtr<FJsonValue>> Hints;

	if (bBindWidgetIssue)
	{
		Hints.Add(MakeShared<FJsonValueString>(TEXT("Check that each native BindWidget property name matches the widget tree exactly and that the widget class is assignable to the native property type.")));
		Hints.Add(MakeShared<FJsonValueString>(TEXT("Re-extract the widget blueprint and compare widget_path names against the parent class BindWidget properties before patching again.")));
	}

	if (bAbstractClassIssue)
	{
		Hints.Add(MakeShared<FJsonValueString>(TEXT("Replace abstract widget classes in the tree with concrete CommonUI/UMG classes before recompiling.")));
	}

	if (bListViewEntryIssue)
	{
		Hints.Add(MakeShared<FJsonValueString>(TEXT("Set entry_widget_class on ListView/ListViewBase widgets to a concrete UUserWidget that implements the required list entry interface.")));
	}

	return Hints;
}

struct FWidgetJsonNodeLocation
{
	TSharedPtr<FJsonObject> Node;
	TSharedPtr<FJsonObject> Parent;
	int32 ChildIndex = INDEX_NONE;
	FString Path;
};

static FString JoinWidgetPath(const FString& ParentPath, const FString& WidgetName)
{
	return ParentPath.IsEmpty() ? WidgetName : ParentPath + TEXT("/") + WidgetName;
}

static FString NormalizeWidgetIdentifier(const FString& Identifier)
{
	FString Normalized = Identifier;
	Normalized.TrimStartAndEndInline();
	Normalized.ReplaceInline(TEXT(">"), TEXT("/"));
	while (Normalized.StartsWith(TEXT("/")))
	{
		Normalized.RightChopInline(1, EAllowShrinking::No);
	}
	while (Normalized.EndsWith(TEXT("/")))
	{
		Normalized.LeftChopInline(1, EAllowShrinking::No);
	}
	return Normalized;
}

static bool IsWidgetPathIdentifier(const FString& Identifier)
{
	return NormalizeWidgetIdentifier(Identifier).Contains(TEXT("/"));
}

static FString NormalizeFontAssetObjectPath(const FString& AssetPath)
{
	if (AssetPath.IsEmpty())
	{
		return FString();
	}

	int32 LastSlashIndex = INDEX_NONE;
	int32 LastDotIndex = INDEX_NONE;
	const bool bHasSlash = AssetPath.FindLastChar(TEXT('/'), LastSlashIndex);
	const bool bHasDot = AssetPath.FindLastChar(TEXT('.'), LastDotIndex);
	if (bHasDot && (!bHasSlash || LastDotIndex > LastSlashIndex))
	{
		return AssetPath;
	}

	if (bHasSlash && LastSlashIndex + 1 < AssetPath.Len())
	{
		const FString AssetName = AssetPath.Mid(LastSlashIndex + 1);
		if (!AssetName.IsEmpty())
		{
			return FString::Printf(TEXT("%s.%s"), *AssetPath, *AssetName);
		}
	}

	return NormalizeAssetObjectPath(AssetPath);
}

static TArray<TSharedPtr<FJsonValue>>& GetMutableChildrenArray(const TSharedPtr<FJsonObject>& ParentNode, const bool bCreateIfMissing)
{
	if (!ParentNode.IsValid())
	{
		static TArray<TSharedPtr<FJsonValue>> EmptyArray;
		return EmptyArray;
	}

	TSharedPtr<FJsonValue>* ExistingField = ParentNode->Values.Find(TEXT("children"));
	if (!ExistingField || !ExistingField->IsValid() || (*ExistingField)->Type != EJson::Array)
	{
		if (bCreateIfMissing)
		{
			ParentNode->SetArrayField(TEXT("children"), {});
			ExistingField = ParentNode->Values.Find(TEXT("children"));
		}
		else
		{
			static TArray<TSharedPtr<FJsonValue>> EmptyArray;
			return EmptyArray;
		}
	}

	check(ExistingField && ExistingField->IsValid());
	return const_cast<TArray<TSharedPtr<FJsonValue>>&>((*ExistingField)->AsArray());
}

static bool FindWidgetJsonNodeRecursive(const TSharedPtr<FJsonObject>& Node,
                                        const FString& CurrentPath,
                                        const FString& NormalizedIdentifier,
                                        const bool bMatchPath,
                                        const TSharedPtr<FJsonObject>& Parent,
                                        const int32 ChildIndex,
                                        FWidgetJsonNodeLocation& OutLocation)
{
	if (!Node.IsValid())
	{
		return false;
	}

	FString NodeName;
	Node->TryGetStringField(TEXT("name"), NodeName);
	const FString NodePath = JoinWidgetPath(CurrentPath, NodeName);
	const bool bMatches = bMatchPath
		? NodePath.Equals(NormalizedIdentifier, ESearchCase::CaseSensitive)
		: NodeName.Equals(NormalizedIdentifier, ESearchCase::CaseSensitive);
	if (bMatches)
	{
		OutLocation.Node = Node;
		OutLocation.Parent = Parent;
		OutLocation.ChildIndex = ChildIndex;
		OutLocation.Path = NodePath;
		return true;
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (!Node->TryGetArrayField(TEXT("children"), Children) || !Children)
	{
		return false;
	}

	for (int32 Index = 0; Index < Children->Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> ChildNode = (*Children)[Index].IsValid() ? (*Children)[Index]->AsObject() : nullptr;
		if (FindWidgetJsonNodeRecursive(ChildNode, NodePath, NormalizedIdentifier, bMatchPath, Node, Index, OutLocation))
		{
			return true;
		}
	}

	return false;
}

static bool FindWidgetJsonNode(const TSharedPtr<FJsonObject>& RootNode,
                               const FString& Identifier,
                               FWidgetJsonNodeLocation& OutLocation)
{
	const FString NormalizedIdentifier = NormalizeWidgetIdentifier(Identifier);
	if (NormalizedIdentifier.IsEmpty())
	{
		return false;
	}

	const bool bMatchPath = IsWidgetPathIdentifier(NormalizedIdentifier);
	return FindWidgetJsonNodeRecursive(RootNode, FString(), NormalizedIdentifier, bMatchPath, nullptr, INDEX_NONE, OutLocation);
}

static bool TryGetStringFieldAnyCase(const TSharedPtr<FJsonObject>& JsonObject,
                                     const TArray<FString>& CandidateFields,
                                     FString& OutValue)
{
	if (!JsonObject.IsValid())
	{
		return false;
	}

	for (const FString& Candidate : CandidateFields)
	{
		if (JsonObject->TryGetStringField(Candidate, OutValue) && !OutValue.IsEmpty())
		{
			return true;
		}
	}

	return false;
}

static bool TryGetBoolFieldAnyCase(const TSharedPtr<FJsonObject>& JsonObject,
                                   const TArray<FString>& CandidateFields,
                                   bool& OutValue)
{
	if (!JsonObject.IsValid())
	{
		return false;
	}

	for (const FString& Candidate : CandidateFields)
	{
		if (JsonObject->TryGetBoolField(Candidate, OutValue))
		{
			return true;
		}
	}

	return false;
}

static bool TryGetObjectField(const TSharedPtr<FJsonObject>& JsonObject,
                              const TCHAR* FieldName,
                              TSharedPtr<FJsonObject>& OutObject)
{
	if (!JsonObject.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* ExistingObject = nullptr;
	if (JsonObject->TryGetObjectField(FStringView(FieldName), ExistingObject) && ExistingObject && ExistingObject->IsValid())
	{
		OutObject = *ExistingObject;
		return true;
	}

	return false;
}

static FString GetWidgetIdentifierFromPayload(const TSharedPtr<FJsonObject>& PayloadJson,
                                              const TArray<FString>& NameFields,
                                              const TArray<FString>& PathFields)
{
	FString Identifier;
	if (TryGetStringFieldAnyCase(PayloadJson, PathFields, Identifier))
	{
		return Identifier;
	}

	if (TryGetStringFieldAnyCase(PayloadJson, NameFields, Identifier))
	{
		return Identifier;
	}

	return FString();
}

static UClass* ResolveWidgetClassByName(const FString& ClassName)
{
	if (ClassName.IsEmpty())
	{
		return nullptr;
	}

	auto IsSupportedWidgetClass = [](UClass* Candidate) -> bool
	{
		return Candidate && Candidate->IsChildOf(UWidget::StaticClass());
	};
	auto GetBlueprintWidgetClass = [&IsSupportedWidgetClass](const UWidgetBlueprint* WidgetBlueprint) -> UClass*
	{
		if (!WidgetBlueprint)
		{
			return nullptr;
		}

		UClass* CandidateClass = WidgetBlueprint->GeneratedClass
			? WidgetBlueprint->GeneratedClass
			: WidgetBlueprint->SkeletonGeneratedClass;
		return IsSupportedWidgetClass(CandidateClass) ? CandidateClass : nullptr;
	};
	auto NormalizeWidgetBlueprintLookupPath = [](const FString& InputPath) -> FString
	{
		if (InputPath.EndsWith(TEXT("_C")))
		{
			return InputPath.LeftChop(2);
		}

		return InputPath;
	};
	auto NormalizeScriptClassName = [](const FString& InputName) -> FString
	{
		if (InputName.Len() > 1 && InputName[0] == TCHAR('U') && FChar::IsUpper(InputName[1]))
		{
			return InputName.RightChop(1);
		}

		return InputName;
	};
	auto TryResolveScriptWidgetClass = [&IsSupportedWidgetClass](const FString& ModuleName, const FString& ScriptClassName) -> UClass*
	{
		if (ModuleName.IsEmpty() || ScriptClassName.IsEmpty())
		{
			return nullptr;
		}

		const FString ScriptPath = FString::Printf(TEXT("/Script/%s.%s"), *ModuleName, *ScriptClassName);
		if (UClass* ExistingClass = FindObject<UClass>(static_cast<UObject*>(nullptr), *ScriptPath))
		{
			return IsSupportedWidgetClass(ExistingClass) ? ExistingClass : nullptr;
		}

		UClass* LoadedClass = StaticLoadClass(UWidget::StaticClass(), nullptr, *ScriptPath);
		return IsSupportedWidgetClass(LoadedClass) ? LoadedClass : nullptr;
	};
	UClass* Resolved = nullptr;

	const bool bLooksLikeObjectPath = ClassName.StartsWith(TEXT("/"));
	const bool bLooksLikeQualifiedPath = ClassName.Contains(TEXT("."));
	if (bLooksLikeQualifiedPath)
	{
		UClass* ResolvedFromPath = FAuthoringHelpers::ResolveClass(ClassName, UWidget::StaticClass());
		if (IsSupportedWidgetClass(ResolvedFromPath))
		{
			return ResolvedFromPath;
		}
	}

	if (bLooksLikeObjectPath)
	{
		const FString BlueprintLookupPath = NormalizeWidgetBlueprintLookupPath(ClassName);
		const FString WidgetBlueprintObjectPath = NormalizeAssetObjectPath(BlueprintLookupPath);
		FString WidgetBlueprintPackagePath = WidgetBlueprintObjectPath;
		if (FPackageName::IsValidObjectPath(WidgetBlueprintObjectPath))
		{
			WidgetBlueprintPackagePath = FPackageName::ObjectPathToPackageName(WidgetBlueprintObjectPath);
		}

		for (TObjectIterator<UWidgetBlueprint> It; It; ++It)
		{
			const UWidgetBlueprint* Candidate = *It;
			if (!Candidate || Candidate->HasAnyFlags(RF_ClassDefaultObject))
			{
				continue;
			}

			if (Candidate->GetPathName() == WidgetBlueprintObjectPath
				|| Candidate->GetOutermost()->GetName() == WidgetBlueprintPackagePath)
			{
				Resolved = GetBlueprintWidgetClass(Candidate);
				if (Resolved)
				{
					return Resolved;
				}
			}
		}

		if (const UWidgetBlueprint* WidgetBlueprint = Cast<UWidgetBlueprint>(ResolveAssetByPath(BlueprintLookupPath)))
		{
			Resolved = GetBlueprintWidgetClass(WidgetBlueprint);
			if (Resolved)
			{
				return Resolved;
			}
		}
	}

	const FString ScriptClassName = NormalizeScriptClassName(ClassName);
	const FString UPrefixedName = TEXT("U") + ScriptClassName;
	Resolved = FindObject<UClass>(static_cast<UObject*>(nullptr), *UPrefixedName);
	if (!Resolved)
	{
		Resolved = FindObject<UClass>(static_cast<UObject*>(nullptr), *ClassName);
	}
	if (!Resolved && ScriptClassName != ClassName)
	{
		Resolved = FindObject<UClass>(static_cast<UObject*>(nullptr), *ScriptClassName);
	}
	if (!Resolved)
	{
		const FString BlueprintGeneratedName = ClassName.EndsWith(TEXT("_C")) ? ClassName : ClassName + TEXT("_C");
		for (TObjectIterator<UClass> It; It; ++It)
		{
			UClass* Candidate = *It;
			if (!IsSupportedWidgetClass(Candidate))
			{
				continue;
			}

			const FString CandidateName = Candidate->GetName();
			if (CandidateName == ClassName
				|| CandidateName == UPrefixedName
				|| CandidateName == BlueprintGeneratedName
				|| Candidate->GetFName().ToString() == ClassName)
			{
				Resolved = Candidate;
				break;
			}
		}
	}

	const bool bLooksLikeCommonUIClass = ScriptClassName.StartsWith(TEXT("Common"), ESearchCase::IgnoreCase)
		|| ClassName.StartsWith(TEXT("Common"), ESearchCase::IgnoreCase);
	if (!Resolved)
	{
		Resolved = bLooksLikeCommonUIClass
			? TryResolveScriptWidgetClass(TEXT("CommonUI"), ScriptClassName)
			: TryResolveScriptWidgetClass(TEXT("UMG"), ScriptClassName);
	}
	if (!Resolved && !bLooksLikeCommonUIClass)
	{
		Resolved = TryResolveScriptWidgetClass(TEXT("CommonUI"), ScriptClassName);
	}

	if (!IsSupportedWidgetClass(Resolved))
	{
		return nullptr;
	}

	return Resolved;
}

static bool IsPanelWidgetClassName(const FString& ClassName)
{
	const UClass* WidgetClass = ResolveWidgetClassByName(ClassName);
	return WidgetClass && WidgetClass->IsChildOf(UPanelWidget::StaticClass());
}

static void AnnotateWidgetPaths(const TSharedPtr<FJsonObject>& Node, const FString& ParentPath = FString())
{
	if (!Node.IsValid())
	{
		return;
	}

	FString NodeName;
	Node->TryGetStringField(TEXT("name"), NodeName);
	const FString WidgetPath = JoinWidgetPath(ParentPath, NodeName);
	Node->SetStringField(TEXT("widgetPath"), WidgetPath);

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (!Node->TryGetArrayField(TEXT("children"), Children) || !Children)
	{
		return;
	}

	for (const TSharedPtr<FJsonValue>& ChildValue : *Children)
	{
		if (ChildValue.IsValid())
		{
			AnnotateWidgetPaths(ChildValue->AsObject(), WidgetPath);
		}
	}
}

static TArray<FWidgetBlueprintEditor*> FindOpenWidgetBlueprintEditors(UWidgetBlueprint* WidgetBP)
{
	TArray<FWidgetBlueprintEditor*> Editors;
	if (!WidgetBP || !GEditor)
	{
		return Editors;
	}

	if (UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>())
	{
		for (IAssetEditorInstance* EditorInstance : AssetEditorSubsystem->FindEditorsForAsset(WidgetBP))
		{
			if (EditorInstance && EditorInstance->GetEditorName() == FName(TEXT("WidgetBlueprintEditor")))
			{
				Editors.Add(static_cast<FWidgetBlueprintEditor*>(EditorInstance));
			}
		}
	}

	return Editors;
}

static void DestroyOpenWidgetBlueprintPreviews(const TArray<FWidgetBlueprintEditor*>& Editors)
{
	for (FWidgetBlueprintEditor* Editor : Editors)
	{
		if (!Editor)
		{
			continue;
		}

		if (UUserWidget* PreviewWidget = Editor->GetPreview())
		{
			FWidgetBlueprintEditorUtils::DestroyUserWidget(PreviewWidget);
			Editor->InvalidatePreview();
		}
	}
}

static void RefreshOpenWidgetBlueprintPreviews(const TArray<FWidgetBlueprintEditor*>& Editors)
{
	for (FWidgetBlueprintEditor* Editor : Editors)
	{
		if (!Editor)
		{
			continue;
		}

		Editor->RefreshPreview();
	}
}

class FWidgetBlueprintPreviewGuard
{
public:
	explicit FWidgetBlueprintPreviewGuard(UWidgetBlueprint* WidgetBP)
		: Editors(FindOpenWidgetBlueprintEditors(WidgetBP))
	{
		DestroyOpenWidgetBlueprintPreviews(Editors);
	}

	~FWidgetBlueprintPreviewGuard()
	{
		RefreshOpenWidgetBlueprintPreviews(Editors);
	}

private:
	TArray<FWidgetBlueprintEditor*> Editors;
};

static TSharedPtr<FJsonObject> BuildWidgetCompileSnapshot(UWidgetBlueprint* WidgetBP)
{
	const TArray<TSharedPtr<FJsonValue>> EmptyArray;
	if (!WidgetBP)
	{
		const TSharedPtr<FJsonObject> MissingCompile = MakeCompileResult(false, TEXT("Missing"), EmptyArray, EmptyArray, EmptyArray, 0, 0);
		MissingCompile->SetBoolField(TEXT("dirty"), false);
		MissingCompile->SetBoolField(TEXT("hasGeneratedClass"), false);
		MissingCompile->SetBoolField(TEXT("needsCompile"), true);
		return MissingCompile;
	}

	const bool bDirty = WidgetBP->GetOutermost() && WidgetBP->GetOutermost()->IsDirty();
	const bool bHasGeneratedClass = WidgetBP->GeneratedClass != nullptr;
	const EBlueprintStatus Status = WidgetBP->Status;
	const bool bNeedsCompile = bDirty || Status == BS_Dirty || !bHasGeneratedClass;
	TArray<TSharedPtr<FJsonValue>> ErrorArray;
	TArray<TSharedPtr<FJsonValue>> WarningArray;
	TArray<TSharedPtr<FJsonValue>> MessageArray;
	int32 ErrorCount = 0;
	int32 WarningCount = 0;
	bool bBindWidgetIssue = false;
	bool bAbstractClassIssue = false;
	bool bListViewEntryIssue = false;

	if (Status == BS_Error)
	{
		FCompilerResultsLog CompileResults;
		CompileResults.bSilentMode = true;
		CompileResults.bAnnotateMentionedNodes = false;
		FWidgetBlueprintPreviewGuard PreviewGuard(WidgetBP);
		FKismetEditorUtilities::CompileBlueprint(WidgetBP, EBlueprintCompileOptions::SkipGarbageCollection, &CompileResults);
		CollectCompilerMessages(CompileResults, ErrorArray, WarningArray, MessageArray, &bBindWidgetIssue, &bAbstractClassIssue, &bListViewEntryIssue);
		ErrorCount = CompileResults.NumErrors;
		WarningCount = CompileResults.NumWarnings;

		if ((WidgetBP->GeneratedClass == nullptr) && ErrorCount == 0)
		{
			const FString GeneratedClassMessage = TEXT("GeneratedClass is null after compilation");
			ErrorArray.Add(MakeShared<FJsonValueString>(GeneratedClassMessage));
			MessageArray.Add(MakeMessageValue(TEXT("error"), GeneratedClassMessage));
			ErrorCount++;
		}
	}
	else if (Status == BS_UpToDateWithWarnings)
	{
		const FString CachedWarningMessage = TEXT("Blueprint is up to date with warnings. Recompilation was skipped because the asset is clean.");
		WarningArray.Add(MakeShared<FJsonValueString>(CachedWarningMessage));
		MessageArray.Add(MakeMessageValue(TEXT("warning"), CachedWarningMessage));
		WarningCount = 1;
	}
	else
	{
		MessageArray.Add(MakeMessageValue(TEXT("info"), TEXT("No compile was triggered while extracting the widget blueprint.")));
	}

	const TSharedPtr<FJsonObject> Compile = MakeCompileResult(Status != BS_Error && ErrorCount == 0 && bHasGeneratedClass,
		GetBlueprintStatusString(Status),
		ErrorArray,
		WarningArray,
		MessageArray,
		ErrorCount,
		WarningCount);
	Compile->SetBoolField(TEXT("dirty"), bDirty);
	Compile->SetBoolField(TEXT("hasGeneratedClass"), bHasGeneratedClass);
	Compile->SetBoolField(TEXT("needsCompile"), bNeedsCompile);
	if (Status == BS_Error)
	{
		const TArray<TSharedPtr<FJsonValue>> RecoveryHints = BuildCompileRecoveryHints(bBindWidgetIssue, bAbstractClassIssue, bListViewEntryIssue);
		if (RecoveryHints.Num() > 0)
		{
			Compile->SetArrayField(TEXT("recoveryHints"), RecoveryHints);
		}
	}

	return Compile;
}

static TSharedPtr<FJsonObject> ExtractWidgetClassDefaults(const UWidgetBlueprint* WidgetBP)
{
	return FClassDefaultsExtractor::Extract(WidgetBP);
}

static TArray<TSharedPtr<FJsonValue>> ExtractWidgetAnimationSummaries(const UWidgetBlueprint* WidgetBP)
{
	TArray<TSharedPtr<FJsonValue>> AnimationValues;
	if (!WidgetBP)
	{
		return AnimationValues;
	}

	for (UWidgetAnimation* Animation : WidgetBP->Animations)
	{
		if (!Animation)
		{
			continue;
		}

		const TSharedPtr<FJsonObject> AnimationObject = MakeShared<FJsonObject>();
		AnimationObject->SetStringField(TEXT("name"), Animation->GetName());

		TArray<TSharedPtr<FJsonValue>> BindingValues;
		for (const FWidgetAnimationBinding& Binding : Animation->AnimationBindings)
		{
			const TSharedPtr<FJsonObject> BindingObject = MakeShared<FJsonObject>();
			BindingObject->SetStringField(TEXT("widgetName"), Binding.WidgetName.ToString());
			BindingObject->SetStringField(TEXT("animationGuid"), Binding.AnimationGuid.ToString(EGuidFormats::DigitsWithHyphensLower));
			BindingValues.Add(MakeShared<FJsonValueObject>(BindingObject));
		}

		AnimationObject->SetArrayField(TEXT("bindings"), BindingValues);
		AnimationValues.Add(MakeShared<FJsonValueObject>(AnimationObject));
	}

	return AnimationValues;
}

static void SyncWidgetVariableGuids(UWidgetBlueprint* WidgetBP)
{
#if WITH_EDITORONLY_DATA
	if (!WidgetBP)
	{
		return;
	}

	const TMap<FName, FGuid> ExistingGuids = WidgetBP->WidgetVariableNameToGuidMap;
	TMap<FName, FGuid> RebuiltGuids;

	WidgetBP->ForEachSourceWidget([&ExistingGuids, &RebuiltGuids](UWidget* Widget)
	{
		if (!Widget)
		{
			return;
		}

		const FName WidgetName = Widget->GetFName();
		const FGuid* ExistingGuid = ExistingGuids.Find(WidgetName);
		const FGuid GuidToUse = (ExistingGuid && ExistingGuid->IsValid())
			? *ExistingGuid
			: FGuid::NewDeterministicGuid(Widget->GetPathName());
		RebuiltGuids.Add(WidgetName, GuidToUse);
	});

	// Preserve animation GUIDs across tree rebuilds because animations are not replaced here.
	for (UWidgetAnimation* Animation : WidgetBP->Animations)
	{
		if (Animation)
		{
			const FName AnimationName = Animation->GetFName();
			const FGuid* ExistingGuid = ExistingGuids.Find(AnimationName);
			const FGuid GuidToUse = (ExistingGuid && ExistingGuid->IsValid())
				? *ExistingGuid
				: FGuid::NewDeterministicGuid(Animation->GetPathName());
			RebuiltGuids.Add(AnimationName, GuidToUse);
		}
	}

	WidgetBP->WidgetVariableNameToGuidMap = MoveTemp(RebuiltGuids);
#endif
}

static void SyncGeneratedWidgetVariables(UWidgetBlueprint* WidgetBP)
{
#if WITH_EDITORONLY_DATA
	if (!WidgetBP)
	{
		return;
	}

	TArray<FBPVariableDescription> PreservedVariables;
	PreservedVariables.Reserve(WidgetBP->GeneratedVariables.Num());

	for (FBPVariableDescription& Variable : WidgetBP->GeneratedVariables)
	{
		const UClass* VariableClass = Cast<UClass>(Variable.VarType.PinSubCategoryObject.Get());
		const bool bIsGeneratedWidgetVariable = Variable.VarType.PinCategory == UEdGraphSchema_K2::PC_Object
			&& VariableClass
			&& VariableClass->IsChildOf(UWidget::StaticClass());
		if (!bIsGeneratedWidgetVariable)
		{
			PreservedVariables.Add(MoveTemp(Variable));
		}
	}

	WidgetBP->GeneratedVariables = MoveTemp(PreservedVariables);

	TArray<UWidget*> SortedWidgets = WidgetBP->GetAllSourceWidgets();
	SortedWidgets.Sort([](const UWidget& Lhs, const UWidget& Rhs) { return Rhs.GetFName().LexicalLess(Lhs.GetFName()); });

	for (UWidget* Widget : SortedWidgets)
	{
		if (!Widget)
		{
			continue;
		}

		const bool bShouldGenerateVariable = Widget->bIsVariable
			|| Widget->IsA<UNamedSlot>()
			|| WidgetBP->Bindings.ContainsByPredicate([&Widget](const FDelegateEditorBinding& Binding)
			{
				return Binding.ObjectName == Widget->GetName();
			});
		if (!bShouldGenerateVariable)
		{
			continue;
		}

		FObjectPropertyBase* ExistingProperty = WidgetBP->ParentClass
			? CastField<FObjectPropertyBase>(WidgetBP->ParentClass->FindPropertyByName(Widget->GetFName()))
			: nullptr;
		if (ExistingProperty
			&& FWidgetBlueprintEditorUtils::IsBindWidgetProperty(ExistingProperty)
			&& Widget->IsA(ExistingProperty->PropertyClass))
		{
			continue;
		}

		UClass* WidgetClass = Widget->GetClass();
		if (UBlueprintGeneratedClass* BPWidgetClass = Cast<UBlueprintGeneratedClass>(WidgetClass))
		{
			WidgetClass = BPWidgetClass->GetAuthoritativeClass();
		}

		const FGuid VarGuid = WidgetBP->WidgetVariableNameToGuidMap.FindRef(Widget->GetFName());
		if (!ensure(VarGuid.IsValid()))
		{
			continue;
		}

		FBPVariableDescription WidgetVariableDesc;
		WidgetVariableDesc.VarName = Widget->GetFName();
		WidgetVariableDesc.VarGuid = VarGuid;
		WidgetVariableDesc.VarType = FEdGraphPinType(
			UEdGraphSchema_K2::PC_Object,
			NAME_None,
			WidgetClass,
			EPinContainerType::None,
			false,
			FEdGraphTerminalType());
		WidgetVariableDesc.FriendlyName = Widget->IsGeneratedName()
			? Widget->GetName()
			: Widget->GetLabelText().ToString();
		WidgetVariableDesc.PropertyFlags = CPF_PersistentInstance | CPF_ExportObject | CPF_InstancedReference | CPF_RepSkip;

		if (Widget->bIsVariable)
		{
			WidgetVariableDesc.PropertyFlags |= CPF_BlueprintVisible | CPF_BlueprintReadOnly | CPF_DisableEditOnInstance;

			const FString& CategoryName = Widget->GetCategoryName();
			WidgetVariableDesc.SetMetaData(TEXT("Category"), *(CategoryName.IsEmpty() ? WidgetBP->GetName() : CategoryName));
		}

		WidgetBP->GeneratedVariables.Add(MoveTemp(WidgetVariableDesc));
	}
#endif
}

static void PruneStaleWidgetReferences(UWidgetBlueprint* WidgetBP)
{
#if WITH_EDITORONLY_DATA
	if (!WidgetBP)
	{
		return;
	}

	TSet<FName> ValidWidgetNames;
	WidgetBP->ForEachSourceWidget([&ValidWidgetNames](UWidget* Widget)
	{
		if (Widget)
		{
			ValidWidgetNames.Add(Widget->GetFName());
		}
	});

	WidgetBP->Bindings.RemoveAll([&ValidWidgetNames](const FDelegateEditorBinding& Binding)
	{
		return !ValidWidgetNames.Contains(FName(*Binding.ObjectName));
	});

	for (UWidgetAnimation* WidgetAnimation : WidgetBP->Animations)
	{
		if (!WidgetAnimation)
		{
			continue;
		}

		WidgetAnimation->AnimationBindings.RemoveAll([&ValidWidgetNames](const FWidgetAnimationBinding& Binding)
		{
			return !ValidWidgetNames.Contains(Binding.WidgetName);
		});
	}
#endif
}

static TSharedPtr<FJsonObject> CloneJsonObject(const TSharedPtr<FJsonObject>& Source)
{
	if (!Source.IsValid())
	{
		return nullptr;
	}

	const TSharedPtr<FJsonObject> Clone = MakeShared<FJsonObject>();
	Clone->Values = Source->Values;
	return Clone;
}

static void MoveJsonFieldIfPresent(const TSharedPtr<FJsonObject>& JsonObject,
                                   const TCHAR* SourceField,
                                   const TCHAR* TargetField)
{
	if (!JsonObject.IsValid() || JsonObject->HasField(TargetField))
	{
		return;
	}

	const TSharedPtr<FJsonValue> ExistingValue = JsonObject->TryGetField(SourceField);
	if (!ExistingValue.IsValid())
	{
		return;
	}

	JsonObject->SetField(TargetField, ExistingValue);
	JsonObject->RemoveField(SourceField);
}

static void NormalizeSlateChildSizeJson(const TSharedPtr<FJsonObject>& SizeJson)
{
	if (!SizeJson.IsValid())
	{
		return;
	}

	MoveJsonFieldIfPresent(SizeJson, TEXT("value"), TEXT("Value"));
	MoveJsonFieldIfPresent(SizeJson, TEXT("sizeRule"), TEXT("SizeRule"));

	FString SizeRule;
	if (!SizeJson->TryGetStringField(TEXT("SizeRule"), SizeRule))
	{
		return;
	}

	if (SizeRule.Equals(TEXT("Auto"), ESearchCase::IgnoreCase)
		|| SizeRule.Equals(TEXT("Automatic"), ESearchCase::IgnoreCase))
	{
		SizeJson->SetStringField(TEXT("SizeRule"), TEXT("Automatic"));
	}
	else if (SizeRule.Equals(TEXT("Fill"), ESearchCase::IgnoreCase))
	{
		SizeJson->SetStringField(TEXT("SizeRule"), TEXT("Fill"));
	}
}

static TSharedPtr<FJsonObject> NormalizeSlotJson(const TSharedPtr<FJsonObject>& SlotJson)
{
	const TSharedPtr<FJsonObject> NormalizedSlot = CloneJsonObject(SlotJson);
	if (!NormalizedSlot.IsValid())
	{
		return nullptr;
	}

	NormalizedSlot->RemoveField(TEXT("slotClass"));
	MoveJsonFieldIfPresent(NormalizedSlot, TEXT("size"), TEXT("Size"));
	MoveJsonFieldIfPresent(NormalizedSlot, TEXT("AutoSize"), TEXT("bAutoSize"));
	MoveJsonFieldIfPresent(NormalizedSlot, TEXT("autoSize"), TEXT("bAutoSize"));
	MoveJsonFieldIfPresent(NormalizedSlot, TEXT("auto_size"), TEXT("bAutoSize"));
	MoveJsonFieldIfPresent(NormalizedSlot, TEXT("zOrder"), TEXT("ZOrder"));
	MoveJsonFieldIfPresent(NormalizedSlot, TEXT("z_order"), TEXT("ZOrder"));

	const TSharedPtr<FJsonObject>* SizeJson = nullptr;
	if (NormalizedSlot->TryGetObjectField(TEXT("Size"), SizeJson) && SizeJson && SizeJson->IsValid())
	{
		NormalizeSlateChildSizeJson(*SizeJson);
	}

	const bool bHasCanvasLayoutAliases =
		NormalizedSlot->HasField(TEXT("Anchors"))
		|| NormalizedSlot->HasField(TEXT("anchors"))
		|| NormalizedSlot->HasField(TEXT("Offsets"))
		|| NormalizedSlot->HasField(TEXT("offsets"))
		|| NormalizedSlot->HasField(TEXT("Alignment"))
		|| NormalizedSlot->HasField(TEXT("alignment"))
		|| NormalizedSlot->HasField(TEXT("AutoSize"))
		|| NormalizedSlot->HasField(TEXT("autoSize"))
		|| NormalizedSlot->HasField(TEXT("auto_size"))
		|| NormalizedSlot->HasField(TEXT("ZOrder"))
		|| NormalizedSlot->HasField(TEXT("zOrder"))
		|| NormalizedSlot->HasField(TEXT("z_order"));
	if (bHasCanvasLayoutAliases)
	{
		TSharedPtr<FJsonObject> LayoutDataObject;
		if (const TSharedPtr<FJsonObject>* ExistingLayoutData = nullptr;
			NormalizedSlot->TryGetObjectField(TEXT("LayoutData"), ExistingLayoutData)
			&& ExistingLayoutData
			&& ExistingLayoutData->IsValid())
		{
			LayoutDataObject = CloneJsonObject(*ExistingLayoutData);
		}
		else
		{
			LayoutDataObject = MakeShared<FJsonObject>();
		}

		auto MoveAnySlotFieldToLayoutData = [&NormalizedSlot, &LayoutDataObject](
			const TCHAR* TargetField,
			std::initializer_list<const TCHAR*> SourceFields)
		{
			if (!LayoutDataObject.IsValid())
			{
				return;
			}

			if (!LayoutDataObject->HasField(TargetField))
			{
				for (const TCHAR* SourceField : SourceFields)
				{
					if (const TSharedPtr<FJsonValue> ExistingValue = NormalizedSlot->TryGetField(SourceField))
					{
						LayoutDataObject->SetField(TargetField, ExistingValue);
						break;
					}
				}
			}

			for (const TCHAR* SourceField : SourceFields)
			{
				NormalizedSlot->RemoveField(SourceField);
			}
		};

		MoveAnySlotFieldToLayoutData(TEXT("Anchors"), { TEXT("Anchors"), TEXT("anchors") });
		MoveAnySlotFieldToLayoutData(TEXT("Offsets"), { TEXT("Offsets"), TEXT("offsets") });
		MoveAnySlotFieldToLayoutData(TEXT("Alignment"), { TEXT("Alignment"), TEXT("alignment") });
		NormalizedSlot->SetObjectField(TEXT("LayoutData"), LayoutDataObject);
	}

	return NormalizedSlot;
}

static TSharedPtr<FJsonObject> NormalizeWidgetPropertiesJson(const TSharedPtr<FJsonObject>& PropertiesJson,
                                                             FString* OutRenameRequest,
                                                             TOptional<bool>* OutVariableRequest = nullptr)
{
	const TSharedPtr<FJsonObject> NormalizedProperties = CloneJsonObject(PropertiesJson);
	if (!NormalizedProperties.IsValid())
	{
		return nullptr;
	}

	if (OutRenameRequest)
	{
		static const TCHAR* RenameFields[] = {
			TEXT("new_name"),
			TEXT("newName"),
			TEXT("name"),
		};

		for (const TCHAR* RenameField : RenameFields)
		{
			if (NormalizedProperties->TryGetStringField(RenameField, *OutRenameRequest))
			{
				NormalizedProperties->RemoveField(RenameField);
				break;
			}
		}
	}

	if (OutVariableRequest)
	{
		static const TCHAR* VariableFields[] = {
			TEXT("is_variable"),
			TEXT("isVariable"),
			TEXT("bIsVariable"),
		};

		for (const TCHAR* VariableField : VariableFields)
		{
			bool bIsVariable = false;
			if (NormalizedProperties->TryGetBoolField(VariableField, bIsVariable))
			{
				*OutVariableRequest = bIsVariable;
				NormalizedProperties->RemoveField(VariableField);
				break;
			}
		}
	}

	static const TCHAR* EntryWidgetClassFields[] = {
		TEXT("entry_widget_class"),
		TEXT("entry_widget_class_path"),
	};

	for (const TCHAR* EntryWidgetClassField : EntryWidgetClassFields)
	{
		if (const TSharedPtr<FJsonValue> EntryWidgetValue = NormalizedProperties->TryGetField(EntryWidgetClassField))
		{
			if (!NormalizedProperties->HasField(TEXT("EntryWidgetClass")))
			{
				NormalizedProperties->SetField(TEXT("EntryWidgetClass"), EntryWidgetValue);
			}
			NormalizedProperties->RemoveField(EntryWidgetClassField);
		}
	}

	return NormalizedProperties;
}

static void ExtractWidgetVariableFlag(const TSharedPtr<FJsonObject>& JsonObject,
                                      TOptional<bool>& OutVariableRequest,
                                      const bool bRemoveConsumedFields = false)
{
	if (!JsonObject.IsValid())
	{
		return;
	}

	static const TCHAR* VariableFields[] = {
		TEXT("is_variable"),
		TEXT("isVariable"),
		TEXT("bIsVariable"),
	};

	for (const TCHAR* VariableField : VariableFields)
	{
		bool bIsVariable = false;
		if (JsonObject->TryGetBoolField(VariableField, bIsVariable))
		{
			OutVariableRequest = bIsVariable;
			if (bRemoveConsumedFields)
			{
				JsonObject->RemoveField(VariableField);
			}
			return;
		}
	}
}

static void MergeJsonObjectFields(const TSharedPtr<FJsonObject>& Target,
                                  const TSharedPtr<FJsonObject>& Patch)
{
	if (!Target.IsValid() || !Patch.IsValid())
	{
		return;
	}

	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Patch->Values)
	{
		Target->SetField(Pair.Key, Pair.Value);
	}
}

static TSharedPtr<FJsonObject> EnsureObjectField(const TSharedPtr<FJsonObject>& Parent, const TCHAR* FieldName)
{
	if (!Parent.IsValid())
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> ExistingObject;
	if (TryGetObjectField(Parent, FieldName, ExistingObject) && ExistingObject.IsValid())
	{
		return ExistingObject;
	}

	ExistingObject = MakeShared<FJsonObject>();
	Parent->SetObjectField(FieldName, ExistingObject);
	return ExistingObject;
}

static bool ApplySnapshotWidgetPatch(const TSharedPtr<FJsonObject>& WidgetNode,
                                     const TSharedPtr<FJsonObject>& PropertiesJson,
                                     const TSharedPtr<FJsonObject>& SlotJson,
                                     const TSharedPtr<FJsonObject>& WidgetOptionsJson,
                                     TArray<FString>& OutErrors)
{
	if (!WidgetNode.IsValid())
	{
		OutErrors.Add(TEXT("Patch operation requires a valid widget node"));
		return false;
	}

	FString RenameRequest;
	TOptional<bool> PropertyVariableRequest;
	const TSharedPtr<FJsonObject> EffectiveProperties = NormalizeWidgetPropertiesJson(PropertiesJson, &RenameRequest, &PropertyVariableRequest);
	if (!RenameRequest.IsEmpty())
	{
		OutErrors.Add(TEXT("Batch widget patches do not support rename fields; use patch_widget directly instead."));
		return false;
	}

	TOptional<bool> EffectiveVariableRequest = PropertyVariableRequest;
	if (!EffectiveVariableRequest.IsSet())
	{
		ExtractWidgetVariableFlag(WidgetOptionsJson, EffectiveVariableRequest, false);
	}

	const TSharedPtr<FJsonObject> EffectiveSlot = NormalizeSlotJson(SlotJson);
	if (EffectiveProperties.IsValid() && EffectiveProperties->Values.Num() > 0)
	{
		const TSharedPtr<FJsonObject> TargetProperties = EnsureObjectField(WidgetNode, TEXT("properties"));
		MergeJsonObjectFields(TargetProperties, EffectiveProperties);
	}

	if (EffectiveSlot.IsValid() && EffectiveSlot->Values.Num() > 0)
	{
		const TSharedPtr<FJsonObject> TargetSlot = EnsureObjectField(WidgetNode, TEXT("slot"));
		MergeJsonObjectFields(TargetSlot, EffectiveSlot);
	}

	if (EffectiveVariableRequest.IsSet())
	{
		WidgetNode->SetBoolField(TEXT("isVariable"), EffectiveVariableRequest.GetValue());
		WidgetNode->RemoveField(TEXT("is_variable"));
		WidgetNode->RemoveField(TEXT("bIsVariable"));
	}

	return true;
}

static FName SanitizeWidgetObjectName(const FString& RequestedName, const FName CurrentName)
{
	const FString SanitizedName = SlugStringForValidName(RequestedName);
	if (SanitizedName.IsEmpty())
	{
		return CurrentName;
	}

	const FName SanitizedFName(*SanitizedName);
	check(SanitizedFName.IsValidXName(INVALID_OBJECTNAME_CHARACTERS));
	return SanitizedFName;
}

static FString SanitizeWidgetObjectNameString(const FString& RequestedName, const FName CurrentName)
{
	const FString SanitizedName = SlugStringForValidName(RequestedName);
	return SanitizedName.IsEmpty() ? CurrentName.ToString() : SanitizedName;
}

static bool ValidateWidgetRename(UWidgetBlueprint* WidgetBP,
                                 UWidget* Widget,
                                 const FString& RequestedName,
                                 TArray<FString>& OutErrors,
                                 FName* OutSanitizedName = nullptr)
{
	if (!WidgetBP || !Widget)
	{
		OutErrors.Add(TEXT("Rename validation requires a valid WidgetBlueprint and widget"));
		return false;
	}

	if (RequestedName.IsEmpty())
	{
		OutErrors.Add(TEXT("Widget rename requires a non-empty name"));
		return false;
	}

	const FName OldName = Widget->GetFName();
	const FName NewName = SanitizeWidgetObjectName(RequestedName, OldName);
	if (OutSanitizedName)
	{
		*OutSanitizedName = NewName;
	}

	FObjectPropertyBase* ExistingProperty = nullptr;
	bool bCompatibleBindWidget = false;
	if (WidgetBP->ParentClass)
	{
		ExistingProperty = CastField<FObjectPropertyBase>(WidgetBP->ParentClass->FindPropertyByName(NewName));
		bCompatibleBindWidget = ExistingProperty
			&& FWidgetBlueprintEditorUtils::IsBindWidgetProperty(ExistingProperty)
			&& Widget->IsA(ExistingProperty->PropertyClass);
	}

	if (ExistingProperty
		&& FWidgetBlueprintEditorUtils::IsBindWidgetProperty(ExistingProperty)
		&& !Widget->IsA(ExistingProperty->PropertyClass))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Widget rename target '%s' is bound to native type '%s', but widget '%s' is '%s'"),
			*NewName.ToString(),
			*ExistingProperty->PropertyClass->GetName(),
			*OldName.ToString(),
			*Widget->GetClass()->GetName()));
		return false;
	}

	FKismetNameValidator Validator(WidgetBP, OldName);
	const EValidatorResult ValidationResult = Validator.IsValid(NewName);
	const bool bSameWidgetName = (NewName == OldName);
	const bool bExistingSameWidget = bSameWidgetName
		&& (ValidationResult == EValidatorResult::AlreadyInUse || ValidationResult == EValidatorResult::ExistingName);
	if (ValidationResult != EValidatorResult::Ok && !bExistingSameWidget && !bCompatibleBindWidget)
	{
		OutErrors.Add(INameValidatorInterface::GetErrorText(NewName.ToString(), ValidationResult).ToString());
		return false;
	}

	if (UWidget* ExistingWidget = WidgetBP->WidgetTree ? WidgetBP->WidgetTree->FindWidget(NewName) : nullptr)
	{
		if (ExistingWidget != Widget)
		{
			OutErrors.Add(FString::Printf(TEXT("Widget name '%s' is already used in the widget tree"), *NewName.ToString()));
			return false;
		}
	}

	return true;
}

static bool RenameWidgetTemplate(UWidgetBlueprint* WidgetBP,
                                 UWidget* Widget,
                                 const FString& RequestedName,
                                 TArray<FString>& OutErrors)
{
	FName NewName = NAME_None;
	if (!ValidateWidgetRename(WidgetBP, Widget, RequestedName, OutErrors, &NewName))
	{
		return false;
	}

	const FName OldName = Widget->GetFName();
	if (NewName == OldName)
	{
		const FString EffectiveNewNameString = SanitizeWidgetObjectNameString(RequestedName, OldName);
		if (Widget->GetName() == EffectiveNewNameString)
		{
			return true;
		}
	}

	const FString OldNameString = OldName.ToString();
	const FString NewNameString = SanitizeWidgetObjectNameString(RequestedName, OldName);

	if (NewName != OldName)
	{
		WidgetBP->OnVariableRenamed(OldName, NewName);
	}
	Widget->SetDisplayLabel(RequestedName);
	if (!Widget->Rename(*NewNameString, nullptr, REN_DontCreateRedirectors))
	{
		OutErrors.Add(FString::Printf(TEXT("Failed to rename widget '%s' to '%s'"), *OldNameString, *NewNameString));
		return false;
	}

	if (NewName != OldName)
	{
		FWidgetBlueprintEditorUtils::ReplaceDesiredFocus(WidgetBP, OldName, NewName);
	}

	for (FDelegateEditorBinding& Binding : WidgetBP->Bindings)
	{
		if (Binding.ObjectName == OldNameString)
		{
			Binding.ObjectName = NewNameString;
		}
	}

	for (UWidgetAnimation* WidgetAnimation : WidgetBP->Animations)
	{
		if (!WidgetAnimation)
		{
			continue;
		}

		for (FWidgetAnimationBinding& AnimationBinding : WidgetAnimation->AnimationBindings)
		{
			if (AnimationBinding.WidgetName != OldName)
			{
				continue;
			}

			AnimationBinding.WidgetName = NewName;
			if (WidgetAnimation->MovieScene)
			{
				WidgetAnimation->MovieScene->Modify();
			}
		}
	}

	if (WidgetBP->WidgetTree)
	{
		WidgetBP->WidgetTree->ForEachWidget([OldName, NewName](UWidget* CurrentWidget)
		{
			if (CurrentWidget && CurrentWidget->Navigation)
			{
				CurrentWidget->Navigation->SetFlags(RF_Transactional);
				CurrentWidget->Navigation->Modify();
				CurrentWidget->Navigation->TryToRenameBinding(OldName, NewName);
			}
		});
	}

	if (NewName != OldName)
	{
		FBlueprintEditorUtils::ValidateBlueprintChildVariables(WidgetBP, NewName);
		FBlueprintEditorUtils::ReplaceVariableReferences(WidgetBP, OldName, NewName);
		SyncWidgetVariableGuids(WidgetBP);
	}
	SyncGeneratedWidgetVariables(WidgetBP);
	return true;
}

static FString BuildWidgetPathFromLiveWidget(const UWidget* Widget)
{
	TArray<FString> Segments;
	const UWidget* CurrentWidget = Widget;
	while (CurrentWidget)
	{
		Segments.Insert(CurrentWidget->GetName(), 0);
		const UPanelWidget* Parent = CurrentWidget->GetParent();
		CurrentWidget = Parent;
	}

	return FString::Join(Segments, TEXT("/"));
}

static UWidget* FindWidgetByIdentifier(UWidgetBlueprint* WidgetBP,
                                       const FString& Identifier,
                                       FString* OutWidgetPath = nullptr)
{
	if (!WidgetBP || !WidgetBP->WidgetTree)
	{
		return nullptr;
	}

	const FString NormalizedIdentifier = NormalizeWidgetIdentifier(Identifier);
	if (NormalizedIdentifier.IsEmpty())
	{
		return nullptr;
	}

	if (!IsWidgetPathIdentifier(NormalizedIdentifier))
	{
		UWidget* Widget = WidgetBP->WidgetTree->FindWidget(FName(*NormalizedIdentifier));
		if (Widget && OutWidgetPath)
		{
			*OutWidgetPath = BuildWidgetPathFromLiveWidget(Widget);
		}
		return Widget;
	}

	TArray<FString> Segments;
	NormalizedIdentifier.ParseIntoArray(Segments, TEXT("/"), true);
	if (Segments.Num() == 0)
	{
		return nullptr;
	}

	UWidget* CurrentWidget = WidgetBP->WidgetTree->RootWidget;
	if (!CurrentWidget || CurrentWidget->GetName() != Segments[0])
	{
		return nullptr;
	}

	for (int32 Index = 1; Index < Segments.Num(); ++Index)
	{
		const UPanelWidget* ParentPanel = Cast<UPanelWidget>(CurrentWidget);
		if (!ParentPanel)
		{
			return nullptr;
		}

		UWidget* NextWidget = nullptr;
		for (int32 ChildIndex = 0; ChildIndex < ParentPanel->GetChildrenCount(); ++ChildIndex)
		{
			UWidget* ChildWidget = ParentPanel->GetChildAt(ChildIndex);
			if (ChildWidget && ChildWidget->GetName() == Segments[Index])
			{
				NextWidget = ChildWidget;
				break;
			}
		}

		if (!NextWidget)
		{
			return nullptr;
		}

		CurrentWidget = NextWidget;
	}

	if (OutWidgetPath)
	{
		*OutWidgetPath = NormalizedIdentifier;
	}
	return CurrentWidget;
}

static FStructProperty* FindSlateFontInfoProperty(UObject* Object)
{
	if (!Object)
	{
		return nullptr;
	}

	FStructProperty* FontProperty = FindFProperty<FStructProperty>(Object->GetClass(), TEXT("Font"));
	if (FontProperty && FontProperty->Struct == TBaseStructure<FSlateFontInfo>::Get())
	{
		return FontProperty;
	}

	return nullptr;
}

// ---------------------------------------------------------------------------
// BindWidget Validation
// ---------------------------------------------------------------------------

struct FBindWidgetRequirement
{
	FName PropertyName;
	const UClass* ExpectedWidgetClass = nullptr;
	bool bOptional = false;
};

/** Introspect the parent C++ class for BindWidget / BindWidgetOptional UPROPERTY declarations. */
static TArray<FBindWidgetRequirement> GetBindWidgetRequirements(const UClass* ParentClass)
{
	TArray<FBindWidgetRequirement> Requirements;
	if (!ParentClass)
	{
		return Requirements;
	}

	for (TFieldIterator<FObjectPropertyBase> PropIt(ParentClass); PropIt; ++PropIt)
	{
		const FObjectPropertyBase* Property = *PropIt;
		if (!Property)
		{
			continue;
		}

		const bool bRequired = Property->HasMetaData(TEXT("BindWidget"));
		const bool bOptional = Property->HasMetaData(TEXT("BindWidgetOptional"));
		if (!bRequired && !bOptional)
		{
			continue;
		}

		FBindWidgetRequirement Req;
		Req.PropertyName = Property->GetFName();
		Req.ExpectedWidgetClass = Property->PropertyClass;
		Req.bOptional = bOptional;
		Requirements.Add(Req);
	}

	return Requirements;
}

/** Collect all widget names and their UClass pointers from a widget tree. */
static void CollectWidgetNamesFromTree(const UWidget* Widget, TMap<FName, const UClass*>& OutWidgets)
{
	if (!Widget)
	{
		return;
	}

	OutWidgets.Add(Widget->GetFName(), Widget->GetClass());

	if (const UPanelWidget* Panel = Cast<UPanelWidget>(Widget))
	{
		for (int32 i = 0; i < Panel->GetChildrenCount(); ++i)
		{
			CollectWidgetNamesFromTree(Panel->GetChildAt(i), OutWidgets);
		}
	}
}

/** Validate widget tree against BindWidget requirements. Returns a JSON object with results. */
static TSharedPtr<FJsonObject> ValidateBindWidgets(const UClass* ParentClass, const UWidget* RootWidget)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();

	const TArray<FBindWidgetRequirement> Requirements = GetBindWidgetRequirements(ParentClass);
	if (Requirements.Num() == 0)
	{
		Result->SetBoolField(TEXT("passed"), true);
		Result->SetStringField(TEXT("message"), TEXT("No BindWidget requirements on parent class."));
		return Result;
	}

	TMap<FName, const UClass*> TreeWidgets;
	CollectWidgetNamesFromTree(RootWidget, TreeWidgets);

	TArray<TSharedPtr<FJsonValue>> Missing;
	TArray<TSharedPtr<FJsonValue>> TypeMismatch;
	bool bAllPassed = true;

	for (const FBindWidgetRequirement& Req : Requirements)
	{
		const UClass** FoundClass = TreeWidgets.Find(Req.PropertyName);
		if (!FoundClass)
		{
			if (!Req.bOptional)
			{
				const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
				Entry->SetStringField(TEXT("name"), Req.PropertyName.ToString());
				Entry->SetStringField(TEXT("expectedClass"), Req.ExpectedWidgetClass ? Req.ExpectedWidgetClass->GetName() : TEXT("UWidget"));
				Entry->SetBoolField(TEXT("required"), true);
				Missing.Add(MakeShared<FJsonValueObject>(Entry));
				bAllPassed = false;
			}
			continue;
		}

		if (Req.ExpectedWidgetClass && *FoundClass && !(*FoundClass)->IsChildOf(Req.ExpectedWidgetClass))
		{
			const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
			Entry->SetStringField(TEXT("name"), Req.PropertyName.ToString());
			Entry->SetStringField(TEXT("expectedClass"), Req.ExpectedWidgetClass->GetName());
			Entry->SetStringField(TEXT("actualClass"), (*FoundClass)->GetName());
			Entry->SetBoolField(TEXT("required"), !Req.bOptional);
			TypeMismatch.Add(MakeShared<FJsonValueObject>(Entry));
			bAllPassed = false;
		}
	}

	Result->SetBoolField(TEXT("passed"), bAllPassed);
	if (Missing.Num() > 0)
	{
		Result->SetArrayField(TEXT("missing"), Missing);
	}
	if (TypeMismatch.Num() > 0)
	{
		Result->SetArrayField(TEXT("typeMismatch"), TypeMismatch);
	}
	if (bAllPassed)
	{
		Result->SetStringField(TEXT("message"), FString::Printf(
			TEXT("All %d BindWidget requirements satisfied."), Requirements.Num()));
	}
	else
	{
		Result->SetStringField(TEXT("message"), FString::Printf(
			TEXT("BindWidget validation failed: %d missing, %d type mismatches."), Missing.Num(), TypeMismatch.Num()));
	}

	return Result;
}

} // namespace WidgetTreeBuilderInternal

// ---------------------------------------------------------------------------
// 1. CreateWidgetBlueprint
// ---------------------------------------------------------------------------

TSharedPtr<FJsonObject> FWidgetTreeBuilder::CreateWidgetBlueprint(const FString& AssetPath,
                                                                   const FString& ParentClassName)
{
	using namespace WidgetTreeBuilderInternal;

	const FString PackageAssetPath = FPackageName::IsValidObjectPath(AssetPath)
		? FPackageName::ObjectPathToPackageName(AssetPath)
		: AssetPath;
	FAssetMutationContext Context(TEXT("create_widget_blueprint"), PackageAssetPath, TEXT("WidgetBlueprint"), false);

	// Determine the parent class name — default to UserWidget
	const FString EffectiveClassName = ParentClassName.IsEmpty() ? TEXT("UserWidget") : ParentClassName;

	// Resolve the parent class
	UClass* ParentClass = ResolveWidgetClassByName(EffectiveClassName);

	if (!ParentClass)
	{
		Context.AddError(TEXT("parent_class_not_found"),
		                 FString::Printf(TEXT("Parent class not found: %s"), *EffectiveClassName),
		                 PackageAssetPath);
		return Context.BuildResult(false);
	}

	{
		const bool bIsUserWidgetSubclass = ParentClass->IsChildOf(UUserWidget::StaticClass());
		if (!bIsUserWidgetSubclass)
		{
			Context.AddError(TEXT("invalid_parent_class"),
			                 FString::Printf(TEXT("Parent class '%s' is not a subclass of UUserWidget"),
			                 *ParentClass->GetName()),
			                 PackageAssetPath);
			return Context.BuildResult(false);
		}
	}

	if (DoesAssetExist(PackageAssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *PackageAssetPath),
		                 PackageAssetPath);
		return Context.BuildResult(false);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create Widget Blueprint")));

	// Create the package
	UPackage* Package = CreatePackage(*PackageAssetPath);
	if (!ensureMsgf(Package, TEXT("WidgetTreeBuilder: Failed to create package at '%s'"), *PackageAssetPath))
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package at: %s"), *PackageAssetPath),
		                 PackageAssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(PackageAssetPath);
	const IKismetCompilerInterface& KismetCompilerModule =
		FModuleManager::LoadModuleChecked<IKismetCompilerInterface>(KISMET_COMPILER_MODULENAME);
	UClass* BlueprintClassType = nullptr;
	UClass* BlueprintGeneratedClassType = nullptr;
	KismetCompilerModule.GetBlueprintTypesForClass(
		ParentClass,
		BlueprintClassType,
		BlueprintGeneratedClassType);
	if (!BlueprintClassType
		|| !BlueprintGeneratedClassType
		|| !BlueprintClassType->IsChildOf(UWidgetBlueprint::StaticClass()))
	{
		Context.AddError(TEXT("invalid_widget_blueprint_type"),
		                 FString::Printf(TEXT("Parent class '%s' does not resolve to a WidgetBlueprint type"), *ParentClass->GetPathName()),
		                 PackageAssetPath);
		return Context.BuildResult(false);
	}

	UWidgetBlueprint* CreatedAsset = Cast<UWidgetBlueprint>(FKismetEditorUtilities::CreateBlueprint(
		ParentClass,
		Package,
		AssetName,
		BPTYPE_Normal,
		BlueprintClassType,
		BlueprintGeneratedClassType));

	if (!CreatedAsset)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("CreateBlueprint failed for: %s"), *PackageAssetPath),
		                 PackageAssetPath);
		return Context.BuildResult(false);
	}

	// Notify asset registry
	FAssetRegistryModule::AssetCreated(CreatedAsset);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(CreatedAsset);
	Context.SetValidationSummary(true, TEXT("WidgetBlueprint creation inputs validated."));

	const TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("assetPath"), PackageAssetPath);
	AddAssetPathFields(Result, CreatedAsset);
	Result->SetStringField(TEXT("parentClass"), ParentClass->GetName());
	return Result;
}

// ---------------------------------------------------------------------------
// 2. ExtractWidgetBlueprint
// ---------------------------------------------------------------------------

TSharedPtr<FJsonObject> FWidgetTreeBuilder::ExtractWidgetBlueprint(UWidgetBlueprint* WidgetBP,
                                                                   const bool bIncludeClassDefaults)
{
	using namespace WidgetTreeBuilderInternal;

	if (!ensureMsgf(WidgetBP, TEXT("WidgetTreeBuilder::ExtractWidgetBlueprint: null WidgetBP")))
	{
		return MakeErrorResult(TEXT("WidgetBlueprint is null"));
	}

	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("operation"), TEXT("extract_widget_blueprint"));
	Result->SetStringField(TEXT("assetPath"), WidgetBP->GetPathName());
	AddAssetPathFields(Result, WidgetBP);
	Result->SetStringField(TEXT("assetClass"), TEXT("WidgetBlueprint"));
	Result->SetStringField(TEXT("parentClass"), WidgetBP->ParentClass ? WidgetBP->ParentClass->GetName() : FString());
	Result->SetStringField(TEXT("parentClassPath"), WidgetBP->ParentClass ? WidgetBP->ParentClass->GetPathName() : FString());
	Result->SetField(TEXT("rootWidget"), MakeShared<FJsonValueNull>());
	Result->SetStringField(TEXT("widgetTreeStatus"), TEXT("unknown"));

	if (const TSharedPtr<FJsonObject> WidgetTreeJson = FWidgetTreeExtractor::Extract(WidgetBP))
	{
		TSharedPtr<FJsonObject> RootWidgetJson;
		if (TryGetObjectField(WidgetTreeJson, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid())
		{
			AnnotateWidgetPaths(RootWidgetJson);
			Result->SetObjectField(TEXT("rootWidget"), RootWidgetJson);
		}
		else
		{
			Result->SetField(TEXT("rootWidget"), MakeShared<FJsonValueNull>());
		}

		FString WidgetTreeStatus;
		if (WidgetTreeJson->TryGetStringField(TEXT("widgetTreeStatus"), WidgetTreeStatus))
		{
			Result->SetStringField(TEXT("widgetTreeStatus"), WidgetTreeStatus);
		}

		FString WidgetTreeError;
		if (WidgetTreeJson->TryGetStringField(TEXT("widgetTreeError"), WidgetTreeError))
		{
			Result->SetStringField(TEXT("widgetTreeError"), WidgetTreeError);
		}

		TSharedPtr<FJsonObject> BindingsJson;
		if (TryGetObjectField(WidgetTreeJson, TEXT("bindings"), BindingsJson) && BindingsJson.IsValid())
		{
			Result->SetObjectField(TEXT("bindings"), BindingsJson);
		}
	}
	else
	{
		Result->SetField(TEXT("rootWidget"), MakeShared<FJsonValueNull>());
		Result->SetStringField(TEXT("widgetTreeStatus"), TEXT("extractor_failed"));
		Result->SetStringField(TEXT("widgetTreeError"), TEXT("Widget tree extraction returned no data."));
	}

	Result->SetArrayField(TEXT("animations"), ExtractWidgetAnimationSummaries(WidgetBP));
	Result->SetObjectField(TEXT("compile"), BuildWidgetCompileSnapshot(WidgetBP));
	if (bIncludeClassDefaults)
	{
		Result->SetObjectField(TEXT("classDefaults"), ExtractWidgetClassDefaults(WidgetBP));
	}

	return Result;
}

// ---------------------------------------------------------------------------
// 3. BuildWidgetTree
// ---------------------------------------------------------------------------

TSharedPtr<FJsonObject> FWidgetTreeBuilder::BuildWidgetTree(UWidgetBlueprint* WidgetBP,
                                                            const TSharedPtr<FJsonObject>& RootWidgetJson,
                                                            const bool bValidateOnly)
{
	using namespace WidgetTreeBuilderInternal;

	const FString AssetPath = WidgetBP ? WidgetBP->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("build_widget_tree"), AssetPath, TEXT("WidgetBlueprint"), bValidateOnly);

	if (!ensureMsgf(WidgetBP, TEXT("WidgetTreeBuilder::BuildWidgetTree: null WidgetBP")))
	{
		Context.AddError(TEXT("null_widget_blueprint"), TEXT("WidgetBlueprint is null"));
		return Context.BuildResult(false);
	}

	if (!RootWidgetJson.IsValid() || RootWidgetJson->Values.Num() == 0)
	{
		Context.AddError(TEXT("empty_widget_tree"), TEXT("RootWidgetJson is null or empty"), AssetPath);
		return Context.BuildResult(false);
	}

	UWidgetTree* WidgetTree = WidgetBP->WidgetTree;
	if (!ensureMsgf(WidgetTree, TEXT("WidgetTreeBuilder::BuildWidgetTree: null WidgetTree")))
	{
		Context.AddError(TEXT("null_widget_tree"), TEXT("WidgetTree is null on the WidgetBlueprint"), AssetPath);
		return Context.BuildResult(false);
	}

	// Preflight the payload on a transient tree so bad JSON never clears the live asset.
	TArray<FString> ValidationErrors;
	UWidgetTree* ValidationTree = NewObject<UWidgetTree>(GetTransientPackage(), NAME_None, RF_Transient);
	UWidget* ValidationRoot = CreateWidgetFromJson(ValidationTree, nullptr, RootWidgetJson, ValidationErrors);
	const bool bValidationSuccess = ValidationRoot != nullptr && ValidationErrors.Num() == 0;
	Context.SetValidationSummary(bValidationSuccess,
		bValidationSuccess ? TEXT("Widget tree payload validated.") : TEXT("Widget tree payload failed validation."),
		ValidationErrors);
	if (!bValidationSuccess)
	{
		return BuildMutationResult(Context, false, ValidationErrors);
	}

	// BindWidget validation: check widget names/types against parent C++ class BindWidget declarations
	TSharedPtr<FJsonObject> BindWidgetValidation;
	if (ValidationRoot && WidgetBP->ParentClass)
	{
		BindWidgetValidation = ValidateBindWidgets(WidgetBP->ParentClass, ValidationRoot);
	}

	if (bValidateOnly)
	{
		TSharedPtr<FJsonObject> Result = BuildMutationResult(Context, true, {});
		if (BindWidgetValidation.IsValid())
		{
			Result->SetObjectField(TEXT("bindWidgetValidation"), BindWidgetValidation);
		}
		return Result;
	}

	FWidgetBlueprintPreviewGuard PreviewGuard(WidgetBP);
	Context.BeginTransaction(FText::FromString(TEXT("Build Widget Tree")));
	WidgetBP->Modify();
	WidgetTree->Modify();

	// Clear existing tree
	{
		TArray<UWidget*> AllWidgets;
		WidgetTree->GetAllWidgets(AllWidgets);

		for (UWidget* Widget : AllWidgets)
		{
			WidgetTree->RemoveWidget(Widget);
		}

		WidgetTree->RootWidget = nullptr;

		// Detach removed widgets from the WidgetTree so the structural recompile
		// does not keep seeing stale source widgets through their Outer chain.
		for (UWidget* Widget : AllWidgets)
		{
			if (Widget && Widget->GetOuter() == WidgetTree)
			{
				Widget->Rename(nullptr, GetTransientPackage());
			}
		}
	}

	// Build the new tree from JSON
	TArray<FString> OutErrors;
	UWidget* RootWidget = CreateWidgetFromJson(WidgetTree, nullptr, RootWidgetJson, OutErrors);

	if (!RootWidget)
	{
		return BuildMutationResult(Context, false, OutErrors);
	}

	WidgetTree->RootWidget = RootWidget;
	SyncWidgetVariableGuids(WidgetBP);
	SyncGeneratedWidgetVariables(WidgetBP);
	PruneStaleWidgetReferences(WidgetBP);

	// Count total widgets
	TArray<UWidget*> FinalWidgets;
	WidgetTree->GetAllWidgets(FinalWidgets);
	const int32 WidgetCount = FinalWidgets.Num();

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBP);
	WidgetBP->MarkPackageDirty();
	Context.TrackDirtyObject(WidgetBP);

	const bool bSuccess = OutErrors.Num() == 0;
	const TSharedPtr<FJsonObject> Result = BuildMutationResult(Context, bSuccess, OutErrors);
	Result->SetNumberField(TEXT("widgetCount"), WidgetCount);
	if (BindWidgetValidation.IsValid())
	{
		Result->SetObjectField(TEXT("bindWidgetValidation"), BindWidgetValidation);
	}
	return Result;
}

// ---------------------------------------------------------------------------
// 4. ModifyWidget
// ---------------------------------------------------------------------------

TSharedPtr<FJsonObject> FWidgetTreeBuilder::ModifyWidget(UWidgetBlueprint* WidgetBP,
                                                         const FString& WidgetName,
                                                         const TSharedPtr<FJsonObject>& PropertiesJson,
                                                         const TSharedPtr<FJsonObject>& SlotJson,
                                                         const TSharedPtr<FJsonObject>& WidgetOptionsJson,
                                                         const bool bValidateOnly)
{
	using namespace WidgetTreeBuilderInternal;

	const FString AssetPath = WidgetBP ? WidgetBP->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_widget"), AssetPath, TEXT("WidgetBlueprint"), bValidateOnly);

	if (!ensureMsgf(WidgetBP, TEXT("WidgetTreeBuilder::ModifyWidget: null WidgetBP")))
	{
		Context.AddError(TEXT("null_widget_blueprint"), TEXT("WidgetBlueprint is null"));
		return Context.BuildResult(false);
	}

	if (WidgetName.IsEmpty())
	{
		Context.AddError(TEXT("empty_widget_name"), TEXT("WidgetName is empty"), AssetPath);
		return Context.BuildResult(false);
	}

	UWidgetTree* WidgetTree = WidgetBP->WidgetTree;
	if (!ensureMsgf(WidgetTree, TEXT("WidgetTreeBuilder::ModifyWidget: null WidgetTree")))
	{
		Context.AddError(TEXT("null_widget_tree"), TEXT("WidgetTree is null on the WidgetBlueprint"), AssetPath);
		return Context.BuildResult(false);
	}

	UWidget* Widget = FindWidgetByIdentifier(WidgetBP, WidgetName);
	if (!Widget)
	{
		Context.AddError(TEXT("widget_not_found"),
		                 FString::Printf(TEXT("Widget not found: %s"), *WidgetName),
		                 WidgetName);
		return Context.BuildResult(false);
	}

	FString RequestedRename;
	TOptional<bool> RequestedVariableFlag;
	const TSharedPtr<FJsonObject> EffectivePropertiesJson = NormalizeWidgetPropertiesJson(PropertiesJson, &RequestedRename, &RequestedVariableFlag);
	if (!RequestedVariableFlag.IsSet())
	{
		ExtractWidgetVariableFlag(WidgetOptionsJson, RequestedVariableFlag, false);
	}
	const TSharedPtr<FJsonObject> EffectiveSlotJson = NormalizeSlotJson(SlotJson);

	TArray<FString> ValidationErrors;
	if (!RequestedRename.IsEmpty())
	{
		ValidateWidgetRename(WidgetBP, Widget, RequestedRename, ValidationErrors);
	}

	if (EffectivePropertiesJson.IsValid() && EffectivePropertiesJson->Values.Num() > 0)
	{
		FPropertySerializer::ApplyPropertiesFromJson(Widget, EffectivePropertiesJson, ValidationErrors, true, true);
	}

	UPanelSlot* Slot = Widget->Slot;
	if (EffectiveSlotJson.IsValid() && EffectiveSlotJson->Values.Num() > 0)
	{
		if (!Slot)
		{
			ValidationErrors.Add(FString::Printf(TEXT("Widget '%s' has no Slot (root widgets have no slot)"), *WidgetName));
		}
		else
		{
			FPropertySerializer::ApplyPropertiesFromJson(Slot, EffectiveSlotJson, ValidationErrors, true, true);
		}
	}

	const bool bValidationSuccess = ValidationErrors.Num() == 0;
	Context.SetValidationSummary(bValidationSuccess,
		bValidationSuccess ? TEXT("Widget modification payload validated.") : TEXT("Widget modification payload failed validation."),
		ValidationErrors);
	if (!bValidationSuccess)
	{
		return BuildMutationResult(Context, false, ValidationErrors);
	}

	if (bValidateOnly)
	{
		return BuildMutationResult(Context, true, {});
	}

	FWidgetBlueprintPreviewGuard PreviewGuard(WidgetBP);
	Context.BeginTransaction(FText::FromString(TEXT("Modify Widget")));
	WidgetBP->Modify();
	Widget->Modify();
	if (Slot)
	{
		Slot->Modify();
	}

	TArray<FString> OutErrors;

	// Apply property changes
	{
		const bool bHasProperties = EffectivePropertiesJson.IsValid() && 0 < EffectivePropertiesJson->Values.Num();
		if (bHasProperties)
		{
			SetPropertiesFromJson(Widget, EffectivePropertiesJson, OutErrors);
		}
	}

	if (RequestedVariableFlag.IsSet())
	{
		Widget->bIsVariable = RequestedVariableFlag.GetValue();
	}

	if (!RequestedRename.IsEmpty())
	{
		RenameWidgetTemplate(WidgetBP, Widget, RequestedRename, OutErrors);
	}

	// Apply slot changes
	{
		const bool bHasSlotData = EffectiveSlotJson.IsValid() && 0 < EffectiveSlotJson->Values.Num();
		if (bHasSlotData)
		{
			if (!Slot)
			{
				OutErrors.Add(FString::Printf(
					TEXT("Widget '%s' has no Slot (root widgets have no slot)"), *WidgetName));
			}
			else
			{
				SetSlotPropertiesFromJson(Slot, EffectiveSlotJson, OutErrors);
			}
		}
	}

	SyncWidgetVariableGuids(WidgetBP);
	SyncGeneratedWidgetVariables(WidgetBP);
	PruneStaleWidgetReferences(WidgetBP);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBP);
	WidgetBP->MarkPackageDirty();
	Context.TrackDirtyObject(WidgetBP);

	const bool bSuccess = OutErrors.Num() == 0;
	const TSharedPtr<FJsonObject> Result = BuildMutationResult(Context, bSuccess, OutErrors);
	Result->SetStringField(TEXT("widgetName"), Widget->GetName());
	Result->SetStringField(TEXT("widgetPath"), BuildWidgetPathFromLiveWidget(Widget));
	Result->SetStringField(TEXT("widgetClass"), Widget->GetClass()->GetName());
	return Result;
}

// ---------------------------------------------------------------------------
// 5. ModifyWidgetBlueprintStructure
// ---------------------------------------------------------------------------

TSharedPtr<FJsonObject> FWidgetTreeBuilder::ModifyWidgetBlueprintStructure(UWidgetBlueprint* WidgetBP,
                                                                           const FString& Operation,
                                                                           const TSharedPtr<FJsonObject>& PayloadJson,
                                                                           const bool bValidateOnly)
{
	using namespace WidgetTreeBuilderInternal;

	FAssetMutationContext Context(TEXT("modify_widget_blueprint"), WidgetBP ? WidgetBP->GetPathName() : FString(), TEXT("WidgetBlueprint"), bValidateOnly);
	if (!ensureMsgf(WidgetBP, TEXT("WidgetTreeBuilder::ModifyWidgetBlueprintStructure: null WidgetBP")))
	{
		Context.AddError(TEXT("null_widget_blueprint"), TEXT("WidgetBlueprint is null"));
		return Context.BuildResult(false);
	}

	if (Operation.IsEmpty())
	{
		Context.AddError(TEXT("empty_operation"), TEXT("WidgetBlueprint structural operation is required"), WidgetBP->GetPathName());
		return Context.BuildResult(false);
	}

	if (Operation == TEXT("patch_class_defaults"))
	{
		const TSharedPtr<FJsonObject> Result = FBlueprintAuthoring::Modify(
			WidgetBP,
			TEXT("patch_class_defaults"),
			PayloadJson,
			bValidateOnly);
		if (!Result.IsValid())
		{
			Context.AddError(TEXT("patch_class_defaults_failed"), TEXT("WidgetBlueprint class-default patch failed"), WidgetBP->GetPathName());
			return Context.BuildResult(false);
		}

		Result->SetStringField(TEXT("operation"), TEXT("modify_widget_blueprint"));
		Result->SetStringField(TEXT("widgetOperation"), Operation);
		return Result;
	}

	const TSharedPtr<FJsonObject> WidgetTreeJson = FWidgetTreeExtractor::Extract(WidgetBP);
	TSharedPtr<FJsonObject> RootWidgetJson;
	if (!WidgetTreeJson.IsValid() || !TryGetObjectField(WidgetTreeJson, TEXT("rootWidget"), RootWidgetJson) || !RootWidgetJson.IsValid())
	{
		Context.AddError(TEXT("empty_widget_tree"), TEXT("WidgetBlueprint has no root widget to mutate"), WidgetBP->GetPathName());
		return Context.BuildResult(false);
	}

	const auto FailWithErrors = [&Context](const FString& Summary, const TArray<FString>& Errors)
	{
		Context.SetValidationSummary(false, Summary, Errors);
		return BuildMutationResult(Context, false, Errors);
	};

	const TSharedPtr<FJsonObject> PendingBatchClassDefaults = MakeShared<FJsonObject>();
	bool bHasPendingBatchClassDefaults = false;

	const auto QueueBatchClassDefaults = [&PendingBatchClassDefaults, &bHasPendingBatchClassDefaults](const TSharedPtr<FJsonObject>& OperationJson, TArray<FString>& OutErrors)
	{
		TSharedPtr<FJsonObject> DefaultsPatch;
		const bool bHasPatch = TryGetObjectField(OperationJson, TEXT("classDefaults"), DefaultsPatch)
			|| TryGetObjectField(OperationJson, TEXT("class_defaults"), DefaultsPatch)
			|| TryGetObjectField(OperationJson, TEXT("properties"), DefaultsPatch);
		if (!bHasPatch || !DefaultsPatch.IsValid())
		{
			OutErrors.Add(TEXT("patch_class_defaults requires classDefaults, class_defaults, or properties object"));
			return false;
		}

		MergeJsonObjectFields(PendingBatchClassDefaults, DefaultsPatch);
		bHasPendingBatchClassDefaults = true;
		return true;
	};

	const auto ApplyInsertChild = [&RootWidgetJson](const TSharedPtr<FJsonObject>& OperationJson, TArray<FString>& OutErrors)
	{
		const FString ParentIdentifier = GetWidgetIdentifierFromPayload(
			OperationJson,
			{TEXT("parent_widget_name"), TEXT("parentWidgetName")},
			{TEXT("parent_widget_path"), TEXT("parentWidgetPath")});
		if (ParentIdentifier.IsEmpty())
		{
			OutErrors.Add(TEXT("insert_child requires parent_widget_name or parent_widget_path"));
			return false;
		}

		TSharedPtr<FJsonObject> ChildWidgetJson;
		if (!OperationJson.IsValid() || !TryGetObjectField(OperationJson, TEXT("child_widget"), ChildWidgetJson) || !ChildWidgetJson.IsValid())
		{
			OutErrors.Add(TEXT("insert_child requires a child_widget object"));
			return false;
		}

		FWidgetJsonNodeLocation ParentLocation;
		if (!FindWidgetJsonNode(RootWidgetJson, ParentIdentifier, ParentLocation) || !ParentLocation.Node.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("Parent widget not found: %s"), *ParentIdentifier));
			return false;
		}

		FString ParentClass;
		ParentLocation.Node->TryGetStringField(TEXT("class"), ParentClass);
		if (!IsPanelWidgetClassName(ParentClass))
		{
			OutErrors.Add(FString::Printf(TEXT("Widget '%s' is not a panel widget and cannot accept children"), *ParentIdentifier));
			return false;
		}

		int32 InsertIndex = INDEX_NONE;
		if (OperationJson->HasTypedField<EJson::Number>(TEXT("index")))
		{
			InsertIndex = static_cast<int32>(OperationJson->GetNumberField(TEXT("index")));
		}

		TArray<TSharedPtr<FJsonValue>>& Children = GetMutableChildrenArray(ParentLocation.Node, true);
		const int32 ResolvedIndex = InsertIndex == INDEX_NONE ? Children.Num() : FMath::Clamp(InsertIndex, 0, Children.Num());
		Children.Insert(MakeShared<FJsonValueObject>(ChildWidgetJson), ResolvedIndex);
		return true;
	};

	const auto ApplyRemoveWidget = [&RootWidgetJson](const TSharedPtr<FJsonObject>& OperationJson, TArray<FString>& OutErrors)
	{
		const FString WidgetIdentifier = GetWidgetIdentifierFromPayload(
			OperationJson,
			{TEXT("widget_name"), TEXT("widgetName")},
			{TEXT("widget_path"), TEXT("widgetPath")});
		if (WidgetIdentifier.IsEmpty())
		{
			OutErrors.Add(TEXT("remove_widget requires widget_name or widget_path"));
			return false;
		}

		FWidgetJsonNodeLocation TargetLocation;
		if (!FindWidgetJsonNode(RootWidgetJson, WidgetIdentifier, TargetLocation) || !TargetLocation.Node.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("Widget not found: %s"), *WidgetIdentifier));
			return false;
		}

		if (!TargetLocation.Parent.IsValid() || TargetLocation.ChildIndex == INDEX_NONE)
		{
			OutErrors.Add(TEXT("remove_widget cannot remove the root widget; use replace_tree instead"));
			return false;
		}

		TArray<TSharedPtr<FJsonValue>>& Siblings = GetMutableChildrenArray(TargetLocation.Parent, false);
		if (!Siblings.IsValidIndex(TargetLocation.ChildIndex))
		{
			OutErrors.Add(TEXT("remove_widget could not resolve the target index"));
			return false;
		}

		Siblings.RemoveAt(TargetLocation.ChildIndex);
		return true;
	};

	const auto ApplyMoveWidget = [&RootWidgetJson](const TSharedPtr<FJsonObject>& OperationJson, TArray<FString>& OutErrors)
	{
		const FString WidgetIdentifier = GetWidgetIdentifierFromPayload(
			OperationJson,
			{TEXT("widget_name"), TEXT("widgetName")},
			{TEXT("widget_path"), TEXT("widgetPath")});
		if (WidgetIdentifier.IsEmpty())
		{
			OutErrors.Add(TEXT("move_widget requires widget_name or widget_path"));
			return false;
		}

		const FString NewParentIdentifier = GetWidgetIdentifierFromPayload(
			OperationJson,
			{TEXT("new_parent_widget_name"), TEXT("newParentWidgetName")},
			{TEXT("new_parent_widget_path"), TEXT("newParentWidgetPath")});

		FWidgetJsonNodeLocation TargetLocation;
		if (!FindWidgetJsonNode(RootWidgetJson, WidgetIdentifier, TargetLocation) || !TargetLocation.Node.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("Widget not found: %s"), *WidgetIdentifier));
			return false;
		}
		if (!TargetLocation.Parent.IsValid() || TargetLocation.ChildIndex == INDEX_NONE)
		{
			OutErrors.Add(TEXT("move_widget cannot move the root widget"));
			return false;
		}

		FWidgetJsonNodeLocation DestinationLocation;
		if (!NewParentIdentifier.IsEmpty())
		{
			if (!FindWidgetJsonNode(RootWidgetJson, NewParentIdentifier, DestinationLocation) || !DestinationLocation.Node.IsValid())
			{
				OutErrors.Add(FString::Printf(TEXT("Destination parent not found: %s"), *NewParentIdentifier));
				return false;
			}
		}
		else
		{
			DestinationLocation.Node = TargetLocation.Parent;
			DestinationLocation.Parent = TargetLocation.Parent;
			DestinationLocation.ChildIndex = TargetLocation.ChildIndex;
		}

		FString DestinationParentClass;
		DestinationLocation.Node->TryGetStringField(TEXT("class"), DestinationParentClass);
		if (!IsPanelWidgetClassName(DestinationParentClass))
		{
			OutErrors.Add(TEXT("move_widget destination must be a panel widget"));
			return false;
		}

		TArray<TSharedPtr<FJsonValue>>& SourceSiblings = GetMutableChildrenArray(TargetLocation.Parent, false);
		if (!SourceSiblings.IsValidIndex(TargetLocation.ChildIndex))
		{
			OutErrors.Add(TEXT("move_widget could not resolve the source index"));
			return false;
		}

		const TSharedPtr<FJsonObject> MovedNode = SourceSiblings[TargetLocation.ChildIndex]->AsObject();
		SourceSiblings.RemoveAt(TargetLocation.ChildIndex);

		const bool bSameParent = DestinationLocation.Node == TargetLocation.Parent;
		TArray<TSharedPtr<FJsonValue>>& DestinationChildren = GetMutableChildrenArray(DestinationLocation.Node, true);
		int32 InsertIndex = DestinationChildren.Num();
		if (OperationJson->HasTypedField<EJson::Number>(TEXT("index")))
		{
			InsertIndex = static_cast<int32>(OperationJson->GetNumberField(TEXT("index")));
		}
		if (bSameParent && InsertIndex > TargetLocation.ChildIndex)
		{
			InsertIndex -= 1;
		}
		InsertIndex = FMath::Clamp(InsertIndex, 0, DestinationChildren.Num());

		if (!bSameParent)
		{
			TSharedPtr<FJsonObject> SlotOverride;
			if (TryGetObjectField(OperationJson, TEXT("slot"), SlotOverride) && SlotOverride.IsValid())
			{
				MovedNode->SetObjectField(TEXT("slot"), NormalizeSlotJson(SlotOverride));
			}
			else
			{
				MovedNode->RemoveField(TEXT("slot"));
			}
		}

		DestinationChildren.Insert(MakeShared<FJsonValueObject>(MovedNode), InsertIndex);
		return true;
	};

	const auto ApplyWrapWidget = [&RootWidgetJson](const TSharedPtr<FJsonObject>& OperationJson, TArray<FString>& OutErrors)
	{
		const FString WidgetIdentifier = GetWidgetIdentifierFromPayload(
			OperationJson,
			{TEXT("widget_name"), TEXT("widgetName")},
			{TEXT("widget_path"), TEXT("widgetPath")});
		if (WidgetIdentifier.IsEmpty())
		{
			OutErrors.Add(TEXT("wrap_widget requires widget_name or widget_path"));
			return false;
		}

		TSharedPtr<FJsonObject> WrapperWidgetJson;
		if (!OperationJson.IsValid() || !TryGetObjectField(OperationJson, TEXT("wrapper_widget"), WrapperWidgetJson) || !WrapperWidgetJson.IsValid())
		{
			OutErrors.Add(TEXT("wrap_widget requires a wrapper_widget object"));
			return false;
		}

		FString WrapperClass;
		WrapperWidgetJson->TryGetStringField(TEXT("class"), WrapperClass);
		if (!IsPanelWidgetClassName(WrapperClass))
		{
			OutErrors.Add(TEXT("wrap_widget requires a panel widget wrapper"));
			return false;
		}

		FWidgetJsonNodeLocation TargetLocation;
		if (!FindWidgetJsonNode(RootWidgetJson, WidgetIdentifier, TargetLocation) || !TargetLocation.Node.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("Widget not found: %s"), *WidgetIdentifier));
			return false;
		}

		const TSharedPtr<FJsonObject> WrappedNode = TargetLocation.Node;
		const TSharedPtr<FJsonObject> WrapperClone = CloneJsonObject(WrapperWidgetJson);
		if (!WrapperClone.IsValid())
		{
			OutErrors.Add(TEXT("wrap_widget failed to clone wrapper_widget"));
			return false;
		}

		if (!WrapperClone->HasField(TEXT("slot")) && WrappedNode->HasField(TEXT("slot")))
		{
			TSharedPtr<FJsonObject> ExistingSlot;
			if (TryGetObjectField(WrappedNode, TEXT("slot"), ExistingSlot) && ExistingSlot.IsValid())
			{
				WrapperClone->SetObjectField(TEXT("slot"), CloneJsonObject(ExistingSlot));
			}
		}

		WrappedNode->RemoveField(TEXT("slot"));
		TArray<TSharedPtr<FJsonValue>>& WrapperChildren = GetMutableChildrenArray(WrapperClone, true);
		WrapperChildren.Insert(MakeShared<FJsonValueObject>(WrappedNode), 0);

		if (!TargetLocation.Parent.IsValid() || TargetLocation.ChildIndex == INDEX_NONE)
		{
			RootWidgetJson = WrapperClone;
			return true;
		}

		TArray<TSharedPtr<FJsonValue>>& Siblings = GetMutableChildrenArray(TargetLocation.Parent, false);
		if (!Siblings.IsValidIndex(TargetLocation.ChildIndex))
		{
			OutErrors.Add(TEXT("wrap_widget could not resolve the target index"));
			return false;
		}

		Siblings[TargetLocation.ChildIndex] = MakeShared<FJsonValueObject>(WrapperClone);
		return true;
	};

	const auto ApplyReplaceWidgetClass = [&RootWidgetJson](const TSharedPtr<FJsonObject>& OperationJson, TArray<FString>& OutErrors)
	{
		const FString WidgetIdentifier = GetWidgetIdentifierFromPayload(
			OperationJson,
			{TEXT("widget_name"), TEXT("widgetName")},
			{TEXT("widget_path"), TEXT("widgetPath")});
		if (WidgetIdentifier.IsEmpty())
		{
			OutErrors.Add(TEXT("replace_widget_class requires widget_name or widget_path"));
			return false;
		}

		FString ReplacementClass;
		if (!TryGetStringFieldAnyCase(OperationJson, {TEXT("replacement_class"), TEXT("replacementClass")}, ReplacementClass))
		{
			OutErrors.Add(TEXT("replace_widget_class requires replacement_class"));
			return false;
		}

		const UClass* ReplacementWidgetClass = ResolveWidgetClassByName(ReplacementClass);
		if (!ReplacementWidgetClass)
		{
			OutErrors.Add(FString::Printf(TEXT("Could not resolve replacement widget class: %s"), *ReplacementClass));
			return false;
		}
		if (ReplacementWidgetClass->HasAnyClassFlags(CLASS_Abstract))
		{
			OutErrors.Add(FString::Printf(TEXT("Replacement widget class '%s' is abstract"), *ReplacementClass));
			return false;
		}

		FWidgetJsonNodeLocation TargetLocation;
		if (!FindWidgetJsonNode(RootWidgetJson, WidgetIdentifier, TargetLocation) || !TargetLocation.Node.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("Widget not found: %s"), *WidgetIdentifier));
			return false;
		}

		const bool bPreserveProperties = !OperationJson->HasTypedField<EJson::Boolean>(TEXT("preserve_properties"))
			|| OperationJson->GetBoolField(TEXT("preserve_properties"));

		TargetLocation.Node->SetStringField(TEXT("class"), ReplacementClass);
		if (!bPreserveProperties)
		{
			TargetLocation.Node->RemoveField(TEXT("properties"));
		}

		TSharedPtr<FJsonObject> PropertiesPatch;
		if (TryGetObjectField(OperationJson, TEXT("properties"), PropertiesPatch) && PropertiesPatch.IsValid())
		{
			const TSharedPtr<FJsonObject> TargetProperties = EnsureObjectField(TargetLocation.Node, TEXT("properties"));
			MergeJsonObjectFields(TargetProperties, PropertiesPatch);
		}

		return true;
	};

	TFunction<bool(const FString&, const TSharedPtr<FJsonObject>&, TArray<FString>&)> ApplyOperation;
	ApplyOperation = [&](const FString& RequestedOperation, const TSharedPtr<FJsonObject>& OperationJson, TArray<FString>& OutErrors) -> bool
	{
		if (RequestedOperation == TEXT("insert_child"))
		{
			return ApplyInsertChild(OperationJson, OutErrors);
		}
		if (RequestedOperation == TEXT("remove_widget"))
		{
			return ApplyRemoveWidget(OperationJson, OutErrors);
		}
		if (RequestedOperation == TEXT("move_widget"))
		{
			return ApplyMoveWidget(OperationJson, OutErrors);
		}
		if (RequestedOperation == TEXT("wrap_widget"))
		{
			return ApplyWrapWidget(OperationJson, OutErrors);
		}
		if (RequestedOperation == TEXT("replace_widget_class"))
		{
			return ApplyReplaceWidgetClass(OperationJson, OutErrors);
		}
		if (RequestedOperation == TEXT("patch_widget"))
		{
			const FString WidgetIdentifier = GetWidgetIdentifierFromPayload(
				OperationJson,
				{TEXT("widget_name"), TEXT("widgetName")},
				{TEXT("widget_path"), TEXT("widgetPath")});
			if (WidgetIdentifier.IsEmpty())
			{
				OutErrors.Add(TEXT("patch_widget requires widget_name or widget_path"));
				return false;
			}

			FWidgetJsonNodeLocation TargetLocation;
			if (!FindWidgetJsonNode(RootWidgetJson, WidgetIdentifier, TargetLocation) || !TargetLocation.Node.IsValid())
			{
				OutErrors.Add(FString::Printf(TEXT("Widget not found: %s"), *WidgetIdentifier));
				return false;
			}

			TSharedPtr<FJsonObject> PropertiesPatch = MakeShared<FJsonObject>();
			TSharedPtr<FJsonObject> SlotPatch = MakeShared<FJsonObject>();
			TryGetObjectField(OperationJson, TEXT("properties"), PropertiesPatch);
			TryGetObjectField(OperationJson, TEXT("slot"), SlotPatch);
			return ApplySnapshotWidgetPatch(TargetLocation.Node, PropertiesPatch, SlotPatch, OperationJson, OutErrors);
		}
		if (RequestedOperation == TEXT("batch"))
		{
			const TArray<TSharedPtr<FJsonValue>>* OperationsArray = nullptr;
			if (!OperationJson->TryGetArrayField(TEXT("operations"), OperationsArray) || !OperationsArray)
			{
				OutErrors.Add(TEXT("batch requires an operations array"));
				return false;
			}

			TArray<TSharedPtr<FJsonObject>> StructuralOperations;
			TArray<TSharedPtr<FJsonObject>> PatchWidgetOperations;

			for (const TSharedPtr<FJsonValue>& OperationValue : *OperationsArray)
			{
				const TSharedPtr<FJsonObject> BatchOperation = OperationValue.IsValid() ? OperationValue->AsObject() : nullptr;
				FString BatchOperationName;
				if (!BatchOperation.IsValid() || !BatchOperation->TryGetStringField(TEXT("operation"), BatchOperationName))
				{
					OutErrors.Add(TEXT("Each batch operation requires an operation field"));
					return false;
				}

				if (BatchOperationName == TEXT("batch") || BatchOperationName == TEXT("compile") || BatchOperationName == TEXT("replace_tree"))
				{
					OutErrors.Add(FString::Printf(TEXT("Unsupported nested widget batch operation: %s"), *BatchOperationName));
					return false;
				}

				if (BatchOperationName == TEXT("patch_class_defaults"))
				{
					if (!QueueBatchClassDefaults(BatchOperation, OutErrors))
					{
						return false;
					}
					continue;
				}

				if (BatchOperationName == TEXT("patch_widget"))
				{
					PatchWidgetOperations.Add(BatchOperation);
					continue;
				}

				StructuralOperations.Add(BatchOperation);
			}

			for (const TSharedPtr<FJsonObject>& StructuralOperation : StructuralOperations)
			{
				FString StructuralOperationName;
				StructuralOperation->TryGetStringField(TEXT("operation"), StructuralOperationName);
				if (!ApplyOperation(StructuralOperationName, StructuralOperation, OutErrors))
				{
					return false;
				}
			}

			for (const TSharedPtr<FJsonObject>& PatchWidgetOperation : PatchWidgetOperations)
			{
				FString PatchWidgetOperationName;
				PatchWidgetOperation->TryGetStringField(TEXT("operation"), PatchWidgetOperationName);
				if (!ApplyOperation(PatchWidgetOperationName, PatchWidgetOperation, OutErrors))
				{
					return false;
				}
			}

			return true;
		}

		OutErrors.Add(FString::Printf(TEXT("Unsupported WidgetBlueprint structure operation: %s"), *RequestedOperation));
		return false;
	};

	TArray<FString> ValidationErrors;
	if (!ApplyOperation(Operation, PayloadJson, ValidationErrors))
	{
		return FailWithErrors(TEXT("WidgetBlueprint structural mutation payload failed validation."), ValidationErrors);
	}

	const TSharedPtr<FJsonObject> BuildResult = BuildWidgetTree(WidgetBP, RootWidgetJson, bValidateOnly);
	if (!BuildResult.IsValid())
	{
		Context.AddError(TEXT("build_failed"), TEXT("Widget tree rebuild failed after structural mutation"), WidgetBP->GetPathName());
		return Context.BuildResult(false);
	}

	if (Operation == TEXT("batch") && bHasPendingBatchClassDefaults)
	{
		const TSharedPtr<FJsonObject> ClassDefaultsPayload = MakeShared<FJsonObject>();
		ClassDefaultsPayload->SetObjectField(TEXT("classDefaults"), CloneJsonObject(PendingBatchClassDefaults));

		const TSharedPtr<FJsonObject> ClassDefaultsResult = FBlueprintAuthoring::Modify(
			WidgetBP,
			TEXT("patch_class_defaults"),
			ClassDefaultsPayload,
			bValidateOnly);
		if (!ClassDefaultsResult.IsValid())
		{
			Context.AddError(TEXT("batch_patch_class_defaults_failed"), TEXT("WidgetBlueprint batch class-default patch failed"), WidgetBP->GetPathName());
			return Context.BuildResult(false);
		}

		bool bClassDefaultsSuccess = true;
		ClassDefaultsResult->TryGetBoolField(TEXT("success"), bClassDefaultsSuccess);
		if (!bClassDefaultsSuccess)
		{
			ClassDefaultsResult->SetStringField(TEXT("operation"), TEXT("modify_widget_blueprint"));
			ClassDefaultsResult->SetStringField(TEXT("widgetOperation"), Operation);
			return ClassDefaultsResult;
		}

		const auto MergeResultArrayField = [&BuildResult, &ClassDefaultsResult](const TCHAR* FieldName)
		{
			const TArray<TSharedPtr<FJsonValue>>* SourceArray = nullptr;
			if (!ClassDefaultsResult->TryGetArrayField(FieldName, SourceArray) || !SourceArray || SourceArray->Num() == 0)
			{
				return;
			}

			const TArray<TSharedPtr<FJsonValue>>* ExistingArray = nullptr;
			TArray<TSharedPtr<FJsonValue>> MergedArray;
			if (BuildResult->TryGetArrayField(FieldName, ExistingArray) && ExistingArray)
			{
				MergedArray = *ExistingArray;
			}

			MergedArray.Append(*SourceArray);
			BuildResult->SetArrayField(FieldName, MergedArray);
		};

		MergeResultArrayField(TEXT("dirtyPackages"));
		MergeResultArrayField(TEXT("changedObjects"));
		MergeResultArrayField(TEXT("diagnostics"));
		MergeResultArrayField(TEXT("warnings"));
		MergeResultArrayField(TEXT("errors"));
	}

	BuildResult->SetStringField(TEXT("operation"), TEXT("modify_widget_blueprint"));
	BuildResult->SetStringField(TEXT("widgetOperation"), Operation);
	return BuildResult;
}

// ---------------------------------------------------------------------------
// 6. ApplyWidgetFonts
// ---------------------------------------------------------------------------

TSharedPtr<FJsonObject> FWidgetTreeBuilder::ApplyWidgetFonts(UWidgetBlueprint* WidgetBP,
                                                             const TSharedPtr<FJsonObject>& PayloadJson,
                                                             const bool bValidateOnly)
{
	using namespace WidgetTreeBuilderInternal;

	const FString AssetPath = WidgetBP ? WidgetBP->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("apply_widget_fonts"), AssetPath, TEXT("WidgetBlueprint"), bValidateOnly);
	if (!ensureMsgf(WidgetBP, TEXT("WidgetTreeBuilder::ApplyWidgetFonts: null WidgetBP")))
	{
		Context.AddError(TEXT("null_widget_blueprint"), TEXT("WidgetBlueprint is null"));
		return Context.BuildResult(false);
	}

	const TArray<TSharedPtr<FJsonValue>>* TargetValues = nullptr;
	if (!PayloadJson.IsValid() || !PayloadJson->TryGetArrayField(TEXT("targets"), TargetValues) || !TargetValues)
	{
		Context.AddError(TEXT("missing_targets"), TEXT("apply_widget_fonts requires a targets array"), AssetPath);
		return Context.BuildResult(false);
	}

	struct FResolvedFontTarget
	{
		int32 Index = INDEX_NONE;
		FString Identifier;
		FString WidgetPath;
		FString FontAssetPath;
		FString Typeface;
		int32 Size = 0;
		UWidget* Widget = nullptr;
		UFont* FontAsset = nullptr;
		FStructProperty* FontProperty = nullptr;
	};

	TArray<FResolvedFontTarget> ResolvedTargets;
	TArray<FString> ValidationErrors;
	TArray<FString> ValidationWarnings;
	for (int32 Index = 0; Index < TargetValues->Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> TargetObject = (*TargetValues)[Index].IsValid() ? (*TargetValues)[Index]->AsObject() : nullptr;
		if (!TargetObject.IsValid())
		{
			ValidationErrors.Add(FString::Printf(TEXT("targets[%d] must be an object"), Index));
			continue;
		}

		FResolvedFontTarget Target;
		Target.Index = Index;
		Target.Identifier = GetWidgetIdentifierFromPayload(
			TargetObject,
			{TEXT("widget_name"), TEXT("widgetName")},
			{TEXT("widget_path"), TEXT("widgetPath")});
		if (Target.Identifier.IsEmpty())
		{
			ValidationErrors.Add(FString::Printf(TEXT("targets[%d] requires widget_name or widget_path"), Index));
			continue;
		}

		if (!TryGetStringFieldAnyCase(TargetObject, {TEXT("font_asset"), TEXT("fontAsset")}, Target.FontAssetPath))
		{
			ValidationErrors.Add(FString::Printf(TEXT("targets[%d] requires font_asset"), Index));
			continue;
		}

		if (!TargetObject->TryGetNumberField(TEXT("size"), Target.Size) || Target.Size <= 0)
		{
			ValidationErrors.Add(FString::Printf(TEXT("targets[%d].size must be a positive integer"), Index));
			continue;
		}

		TryGetStringFieldAnyCase(TargetObject, {TEXT("typeface"), TEXT("typeface_name"), TEXT("typefaceName")}, Target.Typeface);

		Target.FontAsset = Cast<UFont>(ResolveAssetByPath(NormalizeFontAssetObjectPath(Target.FontAssetPath)));
		if (!Target.FontAsset)
		{
			ValidationErrors.Add(FString::Printf(TEXT("targets[%d].font_asset does not resolve to a UFont: %s"), Index, *Target.FontAssetPath));
			continue;
		}

		Target.Widget = FindWidgetByIdentifier(WidgetBP, Target.Identifier, &Target.WidgetPath);
		if (!Target.Widget)
		{
			ValidationWarnings.Add(FString::Printf(TEXT("Widget not found for font target '%s'"), *Target.Identifier));
			continue;
		}

		Target.FontProperty = FindSlateFontInfoProperty(Target.Widget);
		if (!Target.FontProperty)
		{
			ValidationWarnings.Add(FString::Printf(TEXT("Widget '%s' does not expose a Font property and was skipped"), *Target.WidgetPath));
			continue;
		}

		ResolvedTargets.Add(Target);
	}

	const bool bValidationSuccess = ValidationErrors.Num() == 0;
	Context.SetValidationSummary(
		bValidationSuccess,
		bValidationSuccess ? TEXT("Widget font payload validated.") : TEXT("Widget font payload failed validation."),
		ValidationErrors);
	for (const FString& Warning : ValidationWarnings)
	{
		Context.AddWarning(TEXT("font_target_warning"), Warning, AssetPath);
	}
	if (!bValidationSuccess)
	{
		return BuildMutationResult(Context, false, ValidationErrors);
	}

	if (bValidateOnly)
	{
		const TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
		Result->SetStringField(TEXT("status"), ValidationWarnings.Num() > 0 ? TEXT("validated_with_warnings") : TEXT("validated"));
		Result->SetNumberField(TEXT("targetCount"), TargetValues->Num());
		Result->SetNumberField(TEXT("applicableTargetCount"), ResolvedTargets.Num());
		Result->SetNumberField(TEXT("warningCount"), ValidationWarnings.Num());
		return Result;
	}

	FWidgetBlueprintPreviewGuard PreviewGuard(WidgetBP);
	Context.BeginTransaction(FText::FromString(TEXT("Apply Widget Fonts")));
	WidgetBP->Modify();

	TArray<TSharedPtr<FJsonValue>> TargetResults;
	for (const FResolvedFontTarget& Target : ResolvedTargets)
	{
		check(Target.Widget && Target.FontProperty && Target.FontAsset);
		Target.Widget->Modify();

		FSlateFontInfo* FontInfo = Target.FontProperty->ContainerPtrToValuePtr<FSlateFontInfo>(Target.Widget);
		if (!ensure(FontInfo))
		{
			continue;
		}

		FontInfo->FontObject = Target.FontAsset;
		FontInfo->TypefaceFontName = Target.Typeface.IsEmpty() ? FName(TEXT("Default")) : FName(*Target.Typeface);
		FontInfo->Size = Target.Size;

		const TSharedPtr<FJsonObject> TargetResult = MakeShared<FJsonObject>();
		TargetResult->SetNumberField(TEXT("index"), Target.Index);
		TargetResult->SetStringField(TEXT("widgetPath"), Target.WidgetPath);
		TargetResult->SetStringField(TEXT("widgetName"), Target.Widget->GetName());
		TargetResult->SetStringField(TEXT("fontAssetPath"), Target.FontAsset->GetPathName());
		TargetResult->SetStringField(TEXT("typeface"), FontInfo->TypefaceFontName.ToString());
		TargetResult->SetNumberField(TEXT("size"), FontInfo->Size);
		TargetResult->SetStringField(TEXT("status"), TEXT("applied"));
		TargetResults.Add(MakeShared<FJsonValueObject>(TargetResult));
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBP);
	WidgetBP->MarkPackageDirty();
	Context.TrackDirtyObject(WidgetBP);

	const TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("status"), ValidationWarnings.Num() > 0 ? TEXT("partial_success") : TEXT("succeeded"));
	Result->SetNumberField(TEXT("targetCount"), TargetValues->Num());
	Result->SetNumberField(TEXT("appliedCount"), ResolvedTargets.Num());
	Result->SetNumberField(TEXT("warningCount"), ValidationWarnings.Num());
	Result->SetArrayField(TEXT("targets"), TargetResults);
	return Result;
}

// ---------------------------------------------------------------------------
// 7. CompileWidgetBlueprint
// ---------------------------------------------------------------------------

TSharedPtr<FJsonObject> FWidgetTreeBuilder::CompileWidgetBlueprint(UWidgetBlueprint* WidgetBP)
{
	using namespace WidgetTreeBuilderInternal;

	const FString AssetPath = WidgetBP ? WidgetBP->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("compile_widget_blueprint"), AssetPath, TEXT("WidgetBlueprint"), false);

	if (!ensureMsgf(WidgetBP, TEXT("WidgetTreeBuilder::CompileWidgetBlueprint: null WidgetBP")))
	{
		Context.AddError(TEXT("null_widget_blueprint"), TEXT("WidgetBlueprint is null"));
		return Context.BuildResult(false);
	}

	if (GCompilingBlueprint || WidgetBP->bBeingCompiled || !FBlueprintCompilationManager::IsGeneratedClassLayoutReady())
	{
		const FString BusyMessage = TEXT("Blueprint compilation is already in progress. Retry after the current compile finishes.");
		const TArray<TSharedPtr<FJsonValue>> EmptyArray;
		TArray<TSharedPtr<FJsonValue>> WarningArray;
		TArray<TSharedPtr<FJsonValue>> MessageArray;
		WarningArray.Add(MakeShared<FJsonValueString>(BusyMessage));
		MessageArray.Add(MakeMessageValue(TEXT("warning"), BusyMessage));
		const TSharedPtr<FJsonObject> CompileResult = MakeCompileResult(false, TEXT("Busy"), EmptyArray, WarningArray, MessageArray, 0, 1);
		Context.SetCompileSummary(CompileResult);
		Context.AddWarning(TEXT("compile_busy"), BusyMessage, AssetPath);
		return Context.BuildResult(false);
	}

	const bool bHasGeneratedClass = (WidgetBP->GeneratedClass != nullptr);
	const bool bCanUseCachedStatus = bHasGeneratedClass
		&& !WidgetBP->GetOutermost()->IsDirty()
		&& ((WidgetBP->Status == BS_UpToDate) || (WidgetBP->Status == BS_UpToDateWithWarnings));
	if (bCanUseCachedStatus)
	{
		const TArray<TSharedPtr<FJsonValue>> EmptyArray;
		TArray<TSharedPtr<FJsonValue>> WarningArray;
		TArray<TSharedPtr<FJsonValue>> MessageArray;
		int32 WarningCount = 0;

		if (WidgetBP->Status == BS_UpToDateWithWarnings)
		{
			const FString CachedWarningMessage = TEXT("Blueprint is already up to date with warnings. Recompilation was skipped because the asset is clean.");
			WarningArray.Add(MakeShared<FJsonValueString>(CachedWarningMessage));
			MessageArray.Add(MakeMessageValue(TEXT("warning"), CachedWarningMessage));
			WarningCount = 1;
		}
		else
		{
			MessageArray.Add(MakeMessageValue(TEXT("info"), TEXT("Blueprint is already up to date. Recompilation was skipped because the asset is clean.")));
		}

		const TSharedPtr<FJsonObject> CompileResult = MakeCompileResult(true, GetBlueprintStatusString(WidgetBP->Status), EmptyArray, WarningArray, MessageArray, 0, WarningCount);
		Context.SetCompileSummary(CompileResult);
		if (WarningCount > 0)
		{
			Context.AddWarning(TEXT("compile_warning"), TEXT("Blueprint is already up to date with warnings."), AssetPath);
		}
		return Context.BuildResult(true);
	}

	FCompilerResultsLog CompileResults;
	CompileResults.bSilentMode = true;
	CompileResults.bAnnotateMentionedNodes = false;
	FWidgetBlueprintPreviewGuard PreviewGuard(WidgetBP);
	FKismetEditorUtilities::CompileBlueprint(WidgetBP, EBlueprintCompileOptions::SkipGarbageCollection, &CompileResults);

	// Determine success from blueprint status
	const EBlueprintStatus Status = WidgetBP->Status;
	const FString StatusString = GetBlueprintStatusString(Status);

	TArray<TSharedPtr<FJsonValue>> ErrorArray;
	TArray<TSharedPtr<FJsonValue>> WarningArray;
	TArray<TSharedPtr<FJsonValue>> MessageArray;
	int32 ErrorCount = CompileResults.NumErrors;
	int32 WarningCount = CompileResults.NumWarnings;
	bool bBindWidgetIssue = false;
	bool bAbstractClassIssue = false;
	bool bListViewEntryIssue = false;

	for (const TSharedRef<FTokenizedMessage>& Message : CompileResults.Messages)
	{
		const FString MessageText = Message->ToText().ToString();
		if (MessageText.Contains(TEXT("BindWidget"), ESearchCase::IgnoreCase)
			|| MessageText.Contains(TEXT("bound widget"), ESearchCase::IgnoreCase))
		{
			bBindWidgetIssue = true;
		}
		if (MessageText.Contains(TEXT("abstract"), ESearchCase::IgnoreCase)
			&& MessageText.Contains(TEXT("widget"), ESearchCase::IgnoreCase))
		{
			bAbstractClassIssue = true;
		}
		if ((MessageText.Contains(TEXT("EntryWidgetClass"), ESearchCase::IgnoreCase)
			|| MessageText.Contains(TEXT("entry widget"), ESearchCase::IgnoreCase))
			&& MessageText.Contains(TEXT("list"), ESearchCase::IgnoreCase))
		{
			bListViewEntryIssue = true;
		}

		switch (Message->GetSeverity())
		{
		case EMessageSeverity::Error:
			ErrorArray.Add(MakeShared<FJsonValueString>(MessageText));
			MessageArray.Add(MakeMessageValue(TEXT("error"), MessageText));
			break;
		case EMessageSeverity::Warning:
		case EMessageSeverity::PerformanceWarning:
			WarningArray.Add(MakeShared<FJsonValueString>(MessageText));
			MessageArray.Add(MakeMessageValue(TEXT("warning"), MessageText));
			break;
		default:
			MessageArray.Add(MakeMessageValue(TEXT("info"), MessageText));
			break;
		}
	}

	if ((WidgetBP->GeneratedClass == nullptr) && ErrorCount == 0)
	{
		const FString GeneratedClassMessage = TEXT("GeneratedClass is null after compilation");
		ErrorArray.Add(MakeShared<FJsonValueString>(GeneratedClassMessage));
		MessageArray.Add(MakeMessageValue(TEXT("error"), GeneratedClassMessage));
		ErrorCount++;
	}

	const bool bSuccess = (Status != BS_Error) && (ErrorCount == 0);
	const TSharedPtr<FJsonObject> CompileResult = MakeCompileResult(bSuccess, StatusString, ErrorArray, WarningArray, MessageArray, ErrorCount, WarningCount);
	const TArray<TSharedPtr<FJsonValue>> RecoveryHints = BuildCompileRecoveryHints(bBindWidgetIssue, bAbstractClassIssue, bListViewEntryIssue);
	if (RecoveryHints.Num() > 0)
	{
		CompileResult->SetArrayField(TEXT("recoveryHints"), RecoveryHints);
	}
	Context.SetCompileSummary(CompileResult);
	if (!bSuccess)
	{
		Context.AddError(TEXT("compile_failed"),
		                 FString::Printf(TEXT("WidgetBlueprint compile failed with %d errors and %d warnings."), ErrorCount, WarningCount),
		                 AssetPath);
		if (bBindWidgetIssue)
		{
			Context.AddWarning(TEXT("bindwidget_recovery_hint"),
			                   TEXT("Compile output suggests a BindWidget name or type mismatch. Re-extract the widget and compare it against the native parent properties."),
			                   AssetPath);
		}
	}
	else if (WarningCount > 0)
	{
		Context.AddWarning(TEXT("compile_warning"),
		                   FString::Printf(TEXT("WidgetBlueprint compile completed with %d warnings."), WarningCount),
		                   AssetPath);
	}
	return Context.BuildResult(bSuccess);
}

// ---------------------------------------------------------------------------
// 5. CreateWidgetFromJson (Private, Recursive)
// ---------------------------------------------------------------------------

UWidget* FWidgetTreeBuilder::CreateWidgetFromJson(UWidgetTree* WidgetTree,
                                                  UPanelWidget* Parent,
                                                  const TSharedPtr<FJsonObject>& WidgetJson,
                                                  TArray<FString>& OutErrors)
{
	if (!WidgetJson.IsValid())
	{
		OutErrors.Add(TEXT("CreateWidgetFromJson: received null JSON"));
		return nullptr;
	}

	if (!WidgetTree)
	{
		OutErrors.Add(TEXT("CreateWidgetFromJson: WidgetTree is null"));
		return nullptr;
	}

	// Read required "class"
	FString ClassName;
	if (!WidgetJson->TryGetStringField(TEXT("class"), ClassName) || ClassName.IsEmpty())
	{
		OutErrors.Add(TEXT("Widget JSON missing required 'class' field"));
		return nullptr;
	}

	// Read required "name"
	FString WidgetName;
	if (!WidgetJson->TryGetStringField(TEXT("name"), WidgetName) || WidgetName.IsEmpty())
	{
		OutErrors.Add(FString::Printf(TEXT("Widget JSON of class '%s' missing required 'name' field"), *ClassName));
		return nullptr;
	}

	// Resolve class
	UClass* ResolvedClass = ResolveWidgetClass(ClassName);
	if (!ResolvedClass)
	{
		OutErrors.Add(FString::Printf(TEXT("Could not resolve widget class: %s"), *ClassName));
		return nullptr;
	}

	if (ResolvedClass->HasAnyClassFlags(CLASS_Abstract))
	{
		OutErrors.Add(FString::Printf(TEXT("Widget class '%s' is abstract and cannot be instantiated in a widget tree"), *ClassName));
		return nullptr;
	}

	// Construct the widget
	UWidget* Widget = WidgetTree->ConstructWidget<UWidget>(ResolvedClass, FName(*WidgetName));
	if (!Widget)
	{
		OutErrors.Add(FString::Printf(TEXT("ConstructWidget failed for class '%s', name '%s'"),
			*ClassName, *WidgetName));
		return nullptr;
	}

	// Read is_variable / isVariable
	{
		bool bIsVariable = false;
		if (WidgetJson->TryGetBoolField(TEXT("is_variable"), bIsVariable)
			|| WidgetJson->TryGetBoolField(TEXT("isVariable"), bIsVariable)
			|| WidgetJson->TryGetBoolField(TEXT("bIsVariable"), bIsVariable))
		{
			Widget->bIsVariable = bIsVariable;
		}
	}

	{
		FString DisplayLabel;
		if (WidgetJson->TryGetStringField(TEXT("displayLabel"), DisplayLabel) && !DisplayLabel.IsEmpty())
		{
			Widget->SetDisplayLabel(DisplayLabel);
		}
	}

	// Add to parent if present
	if (Parent)
	{
		UPanelSlot* NewSlot = Parent->AddChild(Widget);
		if (!NewSlot)
		{
			OutErrors.Add(FString::Printf(TEXT("Failed to add widget '%s' as child of '%s'"),
				*WidgetName, *Parent->GetName()));
		}
	}

	// Apply slot properties
	{
		if (WidgetJson->HasField(TEXT("slot")) && Widget->Slot)
		{
			const TSharedPtr<FJsonObject> SlotJsonObj = WidgetTreeBuilderInternal::NormalizeSlotJson(WidgetJson->GetObjectField(TEXT("slot")));
			if (SlotJsonObj.IsValid())
			{
				SetSlotPropertiesFromJson(Widget->Slot, SlotJsonObj, OutErrors);
			}
		}
	}

	// Apply widget properties
	{
		if (WidgetJson->HasField(TEXT("properties")))
		{
			const TSharedPtr<FJsonObject> PropsJsonObj = WidgetJson->GetObjectField(TEXT("properties"));
			if (PropsJsonObj.IsValid())
			{
				SetPropertiesFromJson(Widget, PropsJsonObj, OutErrors);
			}
		}
	}

	// Recursively create children
	{
		if (WidgetJson->HasField(TEXT("children")))
		{
			const TArray<TSharedPtr<FJsonValue>>& ChildrenArray = WidgetJson->GetArrayField(TEXT("children"));

			UPanelWidget* PanelWidget = Cast<UPanelWidget>(Widget);
			if (!PanelWidget)
			{
				OutErrors.Add(FString::Printf(
					TEXT("Widget '%s' (class '%s') has children but is not a UPanelWidget"),
					*WidgetName, *ClassName));
			}
			else
			{
				for (const TSharedPtr<FJsonValue>& ChildValue : ChildrenArray)
				{
					if (!ChildValue.IsValid())
					{
						OutErrors.Add(TEXT("Null entry in children array"));
						continue;
					}

					const TSharedPtr<FJsonObject> ChildJson = ChildValue->AsObject();
					if (!ChildJson.IsValid())
					{
						OutErrors.Add(TEXT("Non-object entry in children array"));
						continue;
					}

					CreateWidgetFromJson(WidgetTree, PanelWidget, ChildJson, OutErrors);
				}
			}
		}
	}

	return Widget;
}

// ---------------------------------------------------------------------------
// 6. ResolveWidgetClass (Private)
// ---------------------------------------------------------------------------

UClass* FWidgetTreeBuilder::ResolveWidgetClass(const FString& ClassName)
{
	return WidgetTreeBuilderInternal::ResolveWidgetClassByName(ClassName);
}

// ---------------------------------------------------------------------------
// 7. SetPropertiesFromJson (Private — THE CORE METHOD)
// ---------------------------------------------------------------------------

void FWidgetTreeBuilder::SetPropertiesFromJson(UObject* Target,
                                               const TSharedPtr<FJsonObject>& PropertiesJson,
                                               TArray<FString>& OutErrors)
{
	if (!Target || !PropertiesJson.IsValid())
	{
		return;
	}

	FPropertySerializer::ApplyPropertiesFromJson(Target, PropertiesJson, OutErrors, false, true);
}

// ---------------------------------------------------------------------------
// 8. SetSlotPropertiesFromJson (Private — Thin Wrapper)
// ---------------------------------------------------------------------------

void FWidgetTreeBuilder::SetSlotPropertiesFromJson(UPanelSlot* Slot,
                                                   const TSharedPtr<FJsonObject>& SlotJson,
                                                   TArray<FString>& OutErrors)
{
	if (!Slot || !SlotJson.IsValid())
	{
		return;
	}

	SetPropertiesFromJson(Slot, SlotJson, OutErrors);
}
