#include "BlueprintExtractorLibrary.h"
#include "BlueprintExtractorModule.h"
#include "BlueprintExtractorSettings.h"
#include "BlueprintExtractorVersion.h"
#include "BlueprintJsonSchema.h"
#include "Extractors/ClassDefaultsExtractor.h"
#include "Extractors/ClassLevelExtractor.h"
#include "Extractors/VariableExtractor.h"
#include "Extractors/ComponentExtractor.h"
#include "Extractors/GraphExtractor.h"
#include "Extractors/TimelineExtractor.h"
#include "Extractors/BytecodeExtractor.h"
#include "Extractors/StateTreeExtractor.h"
#include "Extractors/DataAssetExtractor.h"
#include "Extractors/DataTableExtractor.h"
#include "Extractors/BehaviorTreeExtractor.h"
#include "Extractors/BlackboardExtractor.h"
#include "Extractors/UserDefinedStructExtractor.h"
#include "Extractors/UserDefinedEnumExtractor.h"
#include "Extractors/CurveExtractor.h"
#include "Extractors/CurveTableExtractor.h"
#include "Extractors/MaterialGraphExtractor.h"
#include "Extractors/MaterialInstanceExtractor.h"
#include "Extractors/AnimAssetExtractor.h"
#include "Extractors/WidgetTreeExtractor.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Widget.h"
#include "Components/PanelWidget.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BTCompositeNode.h"
#include "BehaviorTree/BTDecorator.h"
#include "BehaviorTree/BTService.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BehaviorTree/BlackboardData.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Animation/BlendSpace.h"
#include "Curves/CurveBase.h"
#include "Engine/Blueprint.h"
#include "Engine/CurveTable.h"
#include "Engine/DataAsset.h"
#include "Engine/DataTable.h"
#include "Engine/UserDefinedEnum.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "Materials/MaterialInstance.h"
#include "Materials/Material.h"
#include "Materials/MaterialFunction.h"
#include "Materials/MaterialFunctionInterface.h"
#include "StateTree.h"
#include "StateTreeEditorData.h"
#include "StateTreeState.h"
#include "StructUtils/UserDefinedStruct.h"
#include "EdGraphSchema_K2.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Misc/FileHelper.h"

// ---------------------------------------------------------------------------
// JSON file writing helpers (shared by Blueprint and StateTree extraction)
// ---------------------------------------------------------------------------

static bool WriteJsonToFile(const TSharedPtr<FJsonObject>& JsonRoot, const FString& OutputPath)
{
	if (!JsonRoot)
	{
		return false;
	}

	FString OutputString;
	const UBlueprintExtractorSettings* Settings = UBlueprintExtractorSettings::Get();

	if (Settings->bPrettyPrint)
	{
		TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>> Writer =
			TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&OutputString);
		FJsonSerializer::Serialize(JsonRoot.ToSharedRef(), Writer);
	}
	else
	{
		TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
			TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&OutputString);
		FJsonSerializer::Serialize(JsonRoot.ToSharedRef(), Writer);
	}

	FString FullPath = OutputPath;
	if (FPaths::GetExtension(FullPath).IsEmpty())
	{
		FullPath = FPaths::ChangeExtension(FullPath, TEXT("json"));
	}

	return FFileHelper::SaveStringToFile(OutputString, *FullPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

static FString GetAssetPackagePath(const UObject* Asset)
{
	if (!Asset)
	{
		return FString();
	}

	if (const UPackage* Package = Asset->GetOutermost())
	{
		return Package->GetName();
	}

	return Asset->GetPathName();
}

static FString MakeCascadeOutputFileName(const UObject* Asset)
{
	FString SafeName = GetAssetPackagePath(Asset);
	SafeName.RemoveFromStart(TEXT("/Game/"));
	SafeName.RemoveFromStart(TEXT("/"));
	SafeName.ReplaceInline(TEXT("/"), TEXT("--"));
	SafeName.ReplaceInline(TEXT("."), TEXT("--"));

	if (SafeName.IsEmpty())
	{
		SafeName = Asset ? Asset->GetName() : TEXT("UnknownAsset");
	}

	return SafeName + TEXT(".json");
}

// ---------------------------------------------------------------------------
// Cascade reference collection helpers
// ---------------------------------------------------------------------------

static void CollectRefsFromPinType(const FEdGraphPinType& PinType, TArray<FSoftObjectPath>& OutRefs)
{
	if (PinType.PinSubCategoryObject.IsValid())
	{
		UObject* SubObj = PinType.PinSubCategoryObject.Get();
		if (SubObj && SubObj->GetClass()->ClassGeneratedBy)
		{
			if (UBlueprint* RefBP = Cast<UBlueprint>(SubObj->GetClass()->ClassGeneratedBy))
			{
				OutRefs.AddUnique(FSoftObjectPath(RefBP));
			}
		}
		// The sub-object itself might be a class with ClassGeneratedBy
		if (UClass* RefClass = Cast<UClass>(SubObj))
		{
			if (RefClass->ClassGeneratedBy)
			{
				if (UBlueprint* RefBP = Cast<UBlueprint>(RefClass->ClassGeneratedBy))
				{
					OutRefs.AddUnique(FSoftObjectPath(RefBP));
				}
			}
		}
	}
	if (PinType.PinValueType.TerminalSubCategoryObject.IsValid())
	{
		UObject* SubObj = PinType.PinValueType.TerminalSubCategoryObject.Get();
		if (UClass* RefClass = Cast<UClass>(SubObj))
		{
			if (RefClass->ClassGeneratedBy)
			{
				if (UBlueprint* RefBP = Cast<UBlueprint>(RefClass->ClassGeneratedBy))
				{
					OutRefs.AddUnique(FSoftObjectPath(RefBP));
				}
			}
		}
	}
}

// ---------------------------------------------------------------------------
// Blueprint extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractBlueprintToJson(UBlueprint* Blueprint, const FString& OutputPath, EBlueprintExtractionScope Scope, const TArray<FName>& GraphFilter)
{
	if (!Blueprint)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractBlueprintToJson: null Blueprint"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractBlueprintToJsonObject(Blueprint, Scope, GraphFilter);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted Blueprint '%s' to '%s'"), *Blueprint->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

bool UBlueprintExtractorLibrary::ExtractBlueprintToJsonString(UBlueprint* Blueprint, FString& OutJsonString, EBlueprintExtractionScope Scope, const TArray<FName>& GraphFilter, const bool bIncludeClassDefaults)
{
	if (!Blueprint)
	{
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractBlueprintToJsonObject(Blueprint, Scope, GraphFilter, bIncludeClassDefaults);
	if (!JsonRoot)
	{
		return false;
	}

	const UBlueprintExtractorSettings* Settings = UBlueprintExtractorSettings::Get();

	if (Settings->bPrettyPrint)
	{
		TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>> Writer =
			TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&OutJsonString);
		FJsonSerializer::Serialize(JsonRoot.ToSharedRef(), Writer);
	}
	else
	{
		TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
			TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&OutJsonString);
		FJsonSerializer::Serialize(JsonRoot.ToSharedRef(), Writer);
	}

	return true;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractBlueprintToJsonObject(UBlueprint* Blueprint, EBlueprintExtractionScope Scope, const TArray<FName>& GraphFilter, const bool bIncludeClassDefaults)
{
	if (!Blueprint)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> BPObj = MakeShared<FJsonObject>();

	// Asset info
	BPObj->SetStringField(TEXT("assetPath"), Blueprint->GetPathName());
	BPObj->SetStringField(TEXT("assetName"), Blueprint->GetName());
	BPObj->SetStringField(TEXT("blueprintType"), FBlueprintJsonSchema::BlueprintTypeToString(Blueprint->BlueprintType));

	// Class level (always included)
	BPObj->SetObjectField(TEXT("classLevel"), FClassLevelExtractor::Extract(Blueprint));

	if (Scope == EBlueprintExtractionScope::ClassLevel)
	{
		if (bIncludeClassDefaults)
		{
			BPObj->SetObjectField(TEXT("classDefaults"), FClassDefaultsExtractor::Extract(Blueprint));
		}
		Root->SetObjectField(TEXT("blueprint"), BPObj);
		return Root;
	}

	// Variables
	BPObj->SetArrayField(TEXT("variables"), FVariableExtractor::Extract(Blueprint));

	if (Scope == EBlueprintExtractionScope::Variables)
	{
		if (bIncludeClassDefaults)
		{
			BPObj->SetObjectField(TEXT("classDefaults"), FClassDefaultsExtractor::Extract(Blueprint));
		}
		Root->SetObjectField(TEXT("blueprint"), BPObj);
		return Root;
	}

	// Components
	TSharedPtr<FJsonObject> Components = FComponentExtractor::Extract(Blueprint);
	if (Components)
	{
		BPObj->SetObjectField(TEXT("components"), Components);
	}

	// Widget tree (for WidgetBlueprints — uses WidgetTree instead of SCS)
	if (const UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Blueprint))
	{
		const TSharedPtr<FJsonObject> WidgetTree = FWidgetTreeExtractor::Extract(WidgetBP);
		if (WidgetTree.IsValid())
		{
			BPObj->SetObjectField(TEXT("widgetTree"), WidgetTree);
		}
	}

	if (Scope == EBlueprintExtractionScope::Components)
	{
		if (bIncludeClassDefaults)
		{
			BPObj->SetObjectField(TEXT("classDefaults"), FClassDefaultsExtractor::Extract(Blueprint));
		}
		Root->SetObjectField(TEXT("blueprint"), BPObj);
		return Root;
	}

	// Timelines
	BPObj->SetArrayField(TEXT("timelines"), FTimelineExtractor::Extract(Blueprint));

	// Delegates (extracted from variables with delegate pin types)
	TArray<TSharedPtr<FJsonValue>> Delegates;
	for (const FBPVariableDescription& Var : Blueprint->NewVariables)
	{
		if (Var.VarType.PinCategory == UEdGraphSchema_K2::PC_MCDelegate ||
			Var.VarType.PinCategory == UEdGraphSchema_K2::PC_Delegate)
		{
			TSharedPtr<FJsonObject> DelegateObj = MakeShared<FJsonObject>();
			DelegateObj->SetStringField(TEXT("name"), Var.VarName.ToString());
			DelegateObj->SetBoolField(TEXT("isMulticast"), Var.VarType.PinCategory == UEdGraphSchema_K2::PC_MCDelegate);
			DelegateObj->SetObjectField(TEXT("type"), FBlueprintJsonSchema::SerializePinType(Var.VarType));

			// Delegate signature from the referenced function
			if (Var.VarType.PinSubCategoryObject.IsValid())
			{
				if (UFunction* SigFunc = Cast<UFunction>(Var.VarType.PinSubCategoryObject.Get()))
				{
					TArray<TSharedPtr<FJsonValue>> SigInputs;
					TArray<TSharedPtr<FJsonValue>> SigOutputs;

					for (TFieldIterator<FProperty> PropIt(SigFunc); PropIt; ++PropIt)
					{
						FProperty* Param = *PropIt;
						if (!Param->HasAnyPropertyFlags(CPF_Parm))
						{
							continue;
						}

						TSharedPtr<FJsonObject> ParamObj = MakeShared<FJsonObject>();
						ParamObj->SetStringField(TEXT("name"), Param->GetName());
						ParamObj->SetStringField(TEXT("cppType"), Param->GetCPPType());

						if (Param->HasAnyPropertyFlags(CPF_ReturnParm | CPF_OutParm))
						{
							SigOutputs.Add(MakeShared<FJsonValueObject>(ParamObj));
						}
						else
						{
							SigInputs.Add(MakeShared<FJsonValueObject>(ParamObj));
						}
					}

					DelegateObj->SetArrayField(TEXT("signatureInputs"), SigInputs);
					DelegateObj->SetArrayField(TEXT("signatureOutputs"), SigOutputs);
				}
			}

			Delegates.Add(MakeShared<FJsonValueObject>(DelegateObj));
		}
	}
	BPObj->SetArrayField(TEXT("delegates"), Delegates);

	// Graphs
	if (Scope == EBlueprintExtractionScope::FunctionsShallow)
	{
		TArray<TSharedPtr<FJsonValue>> ShallowFunctions;
		for (const UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (Graph && (GraphFilter.Num() == 0 || GraphFilter.Contains(Graph->GetFName())))
			{
				TSharedPtr<FJsonObject> FuncObj = MakeShared<FJsonObject>();
				FuncObj->SetStringField(TEXT("graphName"), Graph->GetName());
				FuncObj->SetStringField(TEXT("graphType"), TEXT("FunctionGraph"));
				ShallowFunctions.Add(MakeShared<FJsonValueObject>(FuncObj));
			}
		}
		for (const UEdGraph* Graph : Blueprint->UbergraphPages)
		{
			if (Graph && (GraphFilter.Num() == 0 || GraphFilter.Contains(Graph->GetFName())))
			{
				TSharedPtr<FJsonObject> FuncObj = MakeShared<FJsonObject>();
				FuncObj->SetStringField(TEXT("graphName"), Graph->GetName());
				FuncObj->SetStringField(TEXT("graphType"), TEXT("EventGraph"));
				ShallowFunctions.Add(MakeShared<FJsonValueObject>(FuncObj));
			}
		}
		BPObj->SetArrayField(TEXT("functions"), ShallowFunctions);
	}
	else
	{
		BPObj->SetArrayField(TEXT("functions"), FGraphExtractor::ExtractAllGraphs(Blueprint, GraphFilter));
	}

	// Bytecode (optional)
	if (Scope == EBlueprintExtractionScope::FullWithBytecode)
	{
		BPObj->SetObjectField(TEXT("bytecode"), FBytecodeExtractor::Extract(Blueprint));
	}

	// Class defaults (CDO overrides vs parent class)
	if (bIncludeClassDefaults)
	{
		BPObj->SetObjectField(TEXT("classDefaults"), FClassDefaultsExtractor::Extract(Blueprint));
	}

	Root->SetObjectField(TEXT("blueprint"), BPObj);
	return Root;
}

// ---------------------------------------------------------------------------
// StateTree extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractStateTreeToJson(UStateTree* StateTree, const FString& OutputPath)
{
	if (!StateTree)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractStateTreeToJson: null StateTree"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractStateTreeToJsonObject(StateTree);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted StateTree '%s' to '%s'"), *StateTree->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractStateTreeToJsonObject(UStateTree* StateTree)
{
	return FStateTreeExtractor::Extract(StateTree);
}

// ---------------------------------------------------------------------------
// DataAsset extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractDataAssetToJson(UDataAsset* DataAsset, const FString& OutputPath)
{
	if (!DataAsset)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractDataAssetToJson: null DataAsset"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractDataAssetToJsonObject(DataAsset);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted DataAsset '%s' to '%s'"), *DataAsset->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractDataAssetToJsonObject(UDataAsset* DataAsset)
{
	return FDataAssetExtractor::Extract(DataAsset);
}

// ---------------------------------------------------------------------------
// DataTable extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractDataTableToJson(UDataTable* DataTable, const FString& OutputPath)
{
	if (!DataTable)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractDataTableToJson: null DataTable"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractDataTableToJsonObject(DataTable);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted DataTable '%s' to '%s'"), *DataTable->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractDataTableToJsonObject(UDataTable* DataTable)
{
	return FDataTableExtractor::Extract(DataTable);
}

// ---------------------------------------------------------------------------
// BehaviorTree extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractBehaviorTreeToJson(UBehaviorTree* BehaviorTree, const FString& OutputPath)
{
	if (!BehaviorTree)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractBehaviorTreeToJson: null BehaviorTree"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractBehaviorTreeToJsonObject(BehaviorTree);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted BehaviorTree '%s' to '%s'"), *BehaviorTree->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractBehaviorTreeToJsonObject(UBehaviorTree* BehaviorTree)
{
	return FBehaviorTreeExtractor::Extract(BehaviorTree);
}

// ---------------------------------------------------------------------------
// Blackboard extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractBlackboardToJson(UBlackboardData* BlackboardData, const FString& OutputPath)
{
	if (!BlackboardData)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractBlackboardToJson: null BlackboardData"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractBlackboardToJsonObject(BlackboardData);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted Blackboard '%s' to '%s'"), *BlackboardData->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractBlackboardToJsonObject(UBlackboardData* BlackboardData)
{
	return FBlackboardExtractor::Extract(BlackboardData);
}

// ---------------------------------------------------------------------------
// UserDefinedStruct extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractUserDefinedStructToJson(UUserDefinedStruct* UserDefinedStruct, const FString& OutputPath)
{
	if (!UserDefinedStruct)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractUserDefinedStructToJson: null UserDefinedStruct"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractUserDefinedStructToJsonObject(UserDefinedStruct);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted UserDefinedStruct '%s' to '%s'"), *UserDefinedStruct->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractUserDefinedStructToJsonObject(UUserDefinedStruct* UserDefinedStruct)
{
	return FUserDefinedStructExtractor::Extract(UserDefinedStruct);
}

// ---------------------------------------------------------------------------
// UserDefinedEnum extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractUserDefinedEnumToJson(UUserDefinedEnum* UserDefinedEnum, const FString& OutputPath)
{
	if (!UserDefinedEnum)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractUserDefinedEnumToJson: null UserDefinedEnum"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractUserDefinedEnumToJsonObject(UserDefinedEnum);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted UserDefinedEnum '%s' to '%s'"), *UserDefinedEnum->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractUserDefinedEnumToJsonObject(UUserDefinedEnum* UserDefinedEnum)
{
	return FUserDefinedEnumExtractor::Extract(UserDefinedEnum);
}

// ---------------------------------------------------------------------------
// Curve extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractCurveToJson(UCurveBase* Curve, const FString& OutputPath)
{
	if (!Curve)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractCurveToJson: null Curve"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractCurveToJsonObject(Curve);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted Curve '%s' to '%s'"), *Curve->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractCurveToJsonObject(UCurveBase* Curve)
{
	return FCurveExtractor::Extract(Curve);
}

// ---------------------------------------------------------------------------
// CurveTable extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractCurveTableToJson(UCurveTable* CurveTable, const FString& OutputPath)
{
	if (!CurveTable)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractCurveTableToJson: null CurveTable"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractCurveTableToJsonObject(CurveTable);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted CurveTable '%s' to '%s'"), *CurveTable->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractCurveTableToJsonObject(UCurveTable* CurveTable)
{
	return FCurveTableExtractor::Extract(CurveTable);
}

// ---------------------------------------------------------------------------
// MaterialInstance extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractMaterialInstanceToJson(UMaterialInstance* MaterialInstance, const FString& OutputPath)
{
	if (!MaterialInstance)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractMaterialInstanceToJson: null MaterialInstance"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractMaterialInstanceToJsonObject(MaterialInstance);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted MaterialInstance '%s' to '%s'"), *MaterialInstance->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractMaterialInstanceToJsonObject(UMaterialInstance* MaterialInstance)
{
	return FMaterialInstanceExtractor::Extract(MaterialInstance);
}

bool UBlueprintExtractorLibrary::ExtractMaterialToJson(UMaterial* Material, const FString& OutputPath)
{
	if (!Material)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractMaterialToJson: null Material"));
		return false;
	}

	const TSharedPtr<FJsonObject> JsonRoot = ExtractMaterialToJsonObject(Material);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted Material '%s' to '%s'"), *Material->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractMaterialToJsonObject(UMaterial* Material, const bool bVerbose)
{
	return FMaterialGraphExtractor::ExtractMaterial(Material, bVerbose);
}

bool UBlueprintExtractorLibrary::ExtractMaterialFunctionToJson(UMaterialFunctionInterface* MaterialFunction, const FString& OutputPath)
{
	if (!MaterialFunction)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractMaterialFunctionToJson: null MaterialFunction"));
		return false;
	}

	const TSharedPtr<FJsonObject> JsonRoot = ExtractMaterialFunctionToJsonObject(MaterialFunction);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted MaterialFunction '%s' to '%s'"), *MaterialFunction->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractMaterialFunctionToJsonObject(UMaterialFunctionInterface* MaterialFunction, const bool bVerbose)
{
	return FMaterialGraphExtractor::ExtractMaterialFunction(MaterialFunction, bVerbose);
}

// ---------------------------------------------------------------------------
// Animation asset extraction
// ---------------------------------------------------------------------------

bool UBlueprintExtractorLibrary::ExtractAnimSequenceToJson(UAnimSequence* AnimSequence, const FString& OutputPath)
{
	if (!AnimSequence)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractAnimSequenceToJson: null AnimSequence"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractAnimSequenceToJsonObject(AnimSequence);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted AnimSequence '%s' to '%s'"), *AnimSequence->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractAnimSequenceToJsonObject(UAnimSequence* AnimSequence)
{
	return FAnimAssetExtractor::ExtractAnimSequence(AnimSequence);
}

bool UBlueprintExtractorLibrary::ExtractAnimMontageToJson(UAnimMontage* AnimMontage, const FString& OutputPath)
{
	if (!AnimMontage)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractAnimMontageToJson: null AnimMontage"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractAnimMontageToJsonObject(AnimMontage);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted AnimMontage '%s' to '%s'"), *AnimMontage->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractAnimMontageToJsonObject(UAnimMontage* AnimMontage)
{
	return FAnimAssetExtractor::ExtractAnimMontage(AnimMontage);
}

bool UBlueprintExtractorLibrary::ExtractBlendSpaceToJson(UBlendSpace* BlendSpace, const FString& OutputPath)
{
	if (!BlendSpace)
	{
		UE_LOG(LogBlueprintExtractor, Error, TEXT("ExtractBlendSpaceToJson: null BlendSpace"));
		return false;
	}

	TSharedPtr<FJsonObject> JsonRoot = ExtractBlendSpaceToJsonObject(BlendSpace);
	if (!JsonRoot)
	{
		return false;
	}

	if (WriteJsonToFile(JsonRoot, OutputPath))
	{
		UE_LOG(LogBlueprintExtractor, Log, TEXT("Extracted BlendSpace '%s' to '%s'"), *BlendSpace->GetName(), *OutputPath);
		return true;
	}

	UE_LOG(LogBlueprintExtractor, Error, TEXT("Failed to write JSON to '%s'"), *OutputPath);
	return false;
}

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractBlendSpaceToJsonObject(UBlendSpace* BlendSpace)
{
	return FAnimAssetExtractor::ExtractBlendSpace(BlendSpace);
}

// ---------------------------------------------------------------------------
// Cascade extraction — reference collection
// ---------------------------------------------------------------------------

TArray<FSoftObjectPath> UBlueprintExtractorLibrary::CollectBlueprintReferences(const UBlueprint* Blueprint)
{
	TArray<FSoftObjectPath> Refs;
	if (!Blueprint)
	{
		return Refs;
	}

	// 1. Parent class (if Blueprint-based)
	if (Blueprint->ParentClass && Blueprint->ParentClass->ClassGeneratedBy)
	{
		if (UBlueprint* ParentBP = Cast<UBlueprint>(Blueprint->ParentClass->ClassGeneratedBy))
		{
			Refs.AddUnique(FSoftObjectPath(ParentBP));
		}
	}

	// 2. Implemented interfaces (Blueprint interfaces)
	for (const FBPInterfaceDescription& Iface : Blueprint->ImplementedInterfaces)
	{
		if (Iface.Interface && Iface.Interface->ClassGeneratedBy)
		{
			if (UBlueprint* InterfaceBP = Cast<UBlueprint>(Iface.Interface->ClassGeneratedBy))
			{
				Refs.AddUnique(FSoftObjectPath(InterfaceBP));
			}
		}
	}

	// 3. Variable types referencing Blueprint classes
	for (const FBPVariableDescription& Var : Blueprint->NewVariables)
	{
		CollectRefsFromPinType(Var.VarType, Refs);
	}

	// 4. Graph node pin references (DefaultObject and PinType sub-categories)
	auto ScanGraphs = [&](const auto& Graphs)
	{
		for (const auto& Graph : Graphs)
		{
			if (!Graph)
			{
				continue;
			}
			for (const UEdGraphNode* Node : Graph->Nodes)
			{
				if (!Node)
				{
					continue;
				}
				for (const UEdGraphPin* Pin : Node->Pins)
				{
					if (!Pin)
					{
						continue;
					}
					if (Pin->DefaultObject)
					{
						if (UBlueprint* RefBP = Cast<UBlueprint>(Pin->DefaultObject))
						{
							Refs.AddUnique(FSoftObjectPath(RefBP));
						}
						else if (UClass* RefClass = Cast<UClass>(Pin->DefaultObject))
						{
							if (RefClass->ClassGeneratedBy)
							{
								if (UBlueprint* ClassBP = Cast<UBlueprint>(RefClass->ClassGeneratedBy))
								{
									Refs.AddUnique(FSoftObjectPath(ClassBP));
								}
							}
						}
						else if (UStateTree* RefST = Cast<UStateTree>(Pin->DefaultObject))
						{
							Refs.AddUnique(FSoftObjectPath(RefST));
						}
					}
					CollectRefsFromPinType(Pin->PinType, Refs);
				}
			}
		}
	};

	ScanGraphs(Blueprint->FunctionGraphs);
	ScanGraphs(Blueprint->UbergraphPages);
	ScanGraphs(Blueprint->MacroGraphs);

	// 5. Component classes (Blueprint-based components)
	if (Blueprint->SimpleConstructionScript)
	{
		for (USCS_Node* Node : Blueprint->SimpleConstructionScript->GetAllNodes())
		{
			if (Node && Node->ComponentClass && Node->ComponentClass->ClassGeneratedBy)
			{
				if (UBlueprint* RefBP = Cast<UBlueprint>(Node->ComponentClass->ClassGeneratedBy))
				{
					Refs.AddUnique(FSoftObjectPath(RefBP));
				}
			}
		}
	}

	// 6. Widget tree — Blueprint-based UUserWidget subclasses
	if (const UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Blueprint))
	{
		if (WidgetBP->WidgetTree)
		{
			// Recursive lambda to walk widget tree
			const TFunction<void(const UWidget*)> ScanWidget = [&](const UWidget* Widget)
			{
				if (!Widget)
				{
					return;
				}

				const UClass* WidgetClass = Widget->GetClass();
				if (WidgetClass && WidgetClass->ClassGeneratedBy)
				{
					if (UBlueprint* RefBP = Cast<UBlueprint>(WidgetClass->ClassGeneratedBy))
					{
						Refs.AddUnique(FSoftObjectPath(RefBP));
					}
				}

				if (const UPanelWidget* Panel = Cast<UPanelWidget>(Widget))
				{
					for (int32 i = 0; i < Panel->GetChildrenCount(); i++)
					{
						ScanWidget(Panel->GetChildAt(i));
					}
				}
			};

			ScanWidget(WidgetBP->WidgetTree->RootWidget);
		}
	}

	return Refs;
}

TArray<FSoftObjectPath> UBlueprintExtractorLibrary::CollectStateTreeReferences(const UStateTree* StateTree)
{
	TArray<FSoftObjectPath> Refs;
	if (!StateTree)
	{
		return Refs;
	}

#if WITH_EDITORONLY_DATA
	const UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData);
	if (!EditorData)
	{
		return Refs;
	}

	auto CollectFromNodes = [&](const TArray<FStateTreeEditorNode>& Nodes)
	{
		for (const FStateTreeEditorNode& Node : Nodes)
		{
			if (Node.InstanceObject && Node.InstanceObject->GetClass()->ClassGeneratedBy)
			{
				if (UBlueprint* RefBP = Cast<UBlueprint>(Node.InstanceObject->GetClass()->ClassGeneratedBy))
				{
					Refs.AddUnique(FSoftObjectPath(RefBP));
				}
			}
		}
	};

	TFunction<void(const UStateTreeState*)> ScanState = [&](const UStateTreeState* State)
	{
		if (!State)
		{
			return;
		}

		// Linked asset (another StateTree)
		if (State->Type == EStateTreeStateType::LinkedAsset && State->LinkedAsset)
		{
			Refs.AddUnique(FSoftObjectPath(State->LinkedAsset.Get()));
		}

		// Tasks, enter conditions, considerations
		CollectFromNodes(State->Tasks);
		CollectFromNodes(State->EnterConditions);
		CollectFromNodes(State->Considerations);

		// Single task
		if (State->SingleTask.InstanceObject && State->SingleTask.InstanceObject->GetClass()->ClassGeneratedBy)
		{
			if (UBlueprint* RefBP = Cast<UBlueprint>(State->SingleTask.InstanceObject->GetClass()->ClassGeneratedBy))
			{
				Refs.AddUnique(FSoftObjectPath(RefBP));
			}
		}

		// Transition conditions
		for (const FStateTreeTransition& Trans : State->Transitions)
		{
			CollectFromNodes(Trans.Conditions);
		}

		// Recurse into children
		for (const UStateTreeState* Child : State->Children)
		{
			ScanState(Child);
		}
	};

	// Global evaluators and tasks
	CollectFromNodes(EditorData->Evaluators);
	CollectFromNodes(EditorData->GlobalTasks);

	// All states
	for (const UStateTreeState* State : EditorData->SubTrees)
	{
		ScanState(State);
	}
#endif

	return Refs;
}

TArray<FSoftObjectPath> UBlueprintExtractorLibrary::CollectBehaviorTreeReferences(const UBehaviorTree* BehaviorTree)
{
	TArray<FSoftObjectPath> Refs;
	if (!BehaviorTree)
	{
		return Refs;
	}

	if (BehaviorTree->BlackboardAsset)
	{
		Refs.AddUnique(FSoftObjectPath(BehaviorTree->BlackboardAsset));
	}

	const TFunction<void(const UBTNode*)> CollectNodeRef = [&](const UBTNode* Node)
	{
		if (!Node)
		{
			return;
		}

		if (Node->GetClass()->ClassGeneratedBy)
		{
			if (const UBlueprint* NodeBlueprint = Cast<UBlueprint>(Node->GetClass()->ClassGeneratedBy))
			{
				Refs.AddUnique(FSoftObjectPath(NodeBlueprint));
			}
		}

		if (const UBTCompositeNode* CompositeNode = Cast<UBTCompositeNode>(Node))
		{
			for (const TObjectPtr<UBTService>& Service : CompositeNode->Services)
			{
				CollectNodeRef(Service.Get());
			}

			for (const FBTCompositeChild& Child : CompositeNode->Children)
			{
				for (const TObjectPtr<UBTDecorator>& Decorator : Child.Decorators)
				{
					CollectNodeRef(Decorator.Get());
				}

				if (Child.ChildComposite)
				{
					CollectNodeRef(Child.ChildComposite);
				}
				if (Child.ChildTask)
				{
					CollectNodeRef(Child.ChildTask.Get());
				}
			}
		}
	};

	for (const TObjectPtr<UBTDecorator>& RootDecorator : BehaviorTree->RootDecorators)
	{
		CollectNodeRef(RootDecorator.Get());
	}
	CollectNodeRef(BehaviorTree->RootNode);

	return Refs;
}

TArray<FSoftObjectPath> UBlueprintExtractorLibrary::CollectMaterialReferences(const UMaterial* Material)
{
	TArray<FSoftObjectPath> Refs;
	if (!Material)
	{
		return Refs;
	}

	return Refs;
}

TArray<FSoftObjectPath> UBlueprintExtractorLibrary::CollectMaterialFunctionReferences(const UMaterialFunctionInterface* MaterialFunction)
{
	TArray<FSoftObjectPath> Refs;
	if (!MaterialFunction)
	{
		return Refs;
	}

	return Refs;
}

TArray<FSoftObjectPath> UBlueprintExtractorLibrary::CollectMaterialInstanceReferences(const UMaterialInstance* MaterialInstance)
{
	TArray<FSoftObjectPath> Refs;
	if (!MaterialInstance || !MaterialInstance->Parent)
	{
		return Refs;
	}

	if (const UMaterialInstance* ParentMaterialInstance = Cast<UMaterialInstance>(MaterialInstance->Parent))
	{
		Refs.AddUnique(FSoftObjectPath(ParentMaterialInstance));
	}

	return Refs;
}

TArray<FSoftObjectPath> UBlueprintExtractorLibrary::CollectAnimMontageReferences(const UAnimMontage* AnimMontage)
{
	TArray<FSoftObjectPath> Refs;
	if (!AnimMontage)
	{
		return Refs;
	}

	for (const FSlotAnimationTrack& SlotTrack : AnimMontage->SlotAnimTracks)
	{
		for (const FAnimSegment& Segment : SlotTrack.AnimTrack.AnimSegments)
		{
			if (const UAnimSequenceBase* AnimReference = Segment.GetAnimReference().Get())
			{
				Refs.AddUnique(FSoftObjectPath(AnimReference));
			}
		}
	}

	return Refs;
}

TArray<FSoftObjectPath> UBlueprintExtractorLibrary::CollectBlendSpaceReferences(const UBlendSpace* BlendSpace)
{
	TArray<FSoftObjectPath> Refs;
	if (!BlendSpace)
	{
		return Refs;
	}

	for (const FBlendSample& Sample : BlendSpace->GetBlendSamples())
	{
		if (Sample.Animation)
		{
			Refs.AddUnique(FSoftObjectPath(Sample.Animation));
		}
	}

	return Refs;
}

// ---------------------------------------------------------------------------
// Cascade extraction — BFS loop
// ---------------------------------------------------------------------------

TSharedPtr<FJsonObject> UBlueprintExtractorLibrary::ExtractWithCascade(const TArray<UObject*>& InitialAssets, const FString& OutputDir, EBlueprintExtractionScope Scope, int32 MaxDepth, const TArray<FName>& GraphFilter)
{
	struct FPendingAsset
	{
		UObject* Asset;
		int32 Depth;
	};

	TSet<FString> Visited;
	TArray<FPendingAsset> Queue;

	// Seed with initial assets at depth 0
	for (UObject* Asset : InitialAssets)
	{
		if (!Asset)
		{
			continue;
		}
		FString AssetPath = Asset->GetPathName();
		if (!Visited.Contains(AssetPath))
		{
			Visited.Add(AssetPath);
			Queue.Add({Asset, 0});
		}
	}

	int32 SuccessCount = 0;
	int32 ProcessIndex = 0;
	TArray<TSharedPtr<FJsonValue>> Manifest;

	while (ProcessIndex < Queue.Num())
	{
		FPendingAsset Current = Queue[ProcessIndex++];

		const FString FileName = MakeCascadeOutputFileName(Current.Asset);
		const FString FullPath = OutputDir / FileName;
		const FString AssetPath = GetAssetPackagePath(Current.Asset);

		bool bSuccess = false;
		FString AssetType = TEXT("Unknown");
		FString ErrorMessage;
		TArray<FSoftObjectPath> Refs;

		if (UBlueprint* BP = Cast<UBlueprint>(Current.Asset))
		{
			AssetType = TEXT("Blueprint");
			bSuccess = ExtractBlueprintToJson(BP, FullPath, Scope, GraphFilter);
			if (Current.Depth < MaxDepth)
			{
				Refs = CollectBlueprintReferences(BP);
			}
		}
		else if (UStateTree* ST = Cast<UStateTree>(Current.Asset))
		{
			AssetType = TEXT("StateTree");
			bSuccess = ExtractStateTreeToJson(ST, FullPath);
			if (Current.Depth < MaxDepth)
			{
				Refs = CollectStateTreeReferences(ST);
			}
		}
		else if (UBehaviorTree* BT = Cast<UBehaviorTree>(Current.Asset))
		{
			AssetType = TEXT("BehaviorTree");
			bSuccess = ExtractBehaviorTreeToJson(BT, FullPath);
			if (Current.Depth < MaxDepth)
			{
				Refs = CollectBehaviorTreeReferences(BT);
			}
		}
		else if (UBlackboardData* BlackboardData = Cast<UBlackboardData>(Current.Asset))
		{
			AssetType = TEXT("Blackboard");
			bSuccess = ExtractBlackboardToJson(BlackboardData, FullPath);
			if (Current.Depth < MaxDepth && BlackboardData->Parent)
			{
				Refs.AddUnique(FSoftObjectPath(BlackboardData->Parent));
			}
		}
		else if (UDataAsset* DA = Cast<UDataAsset>(Current.Asset))
		{
			AssetType = TEXT("DataAsset");
			bSuccess = ExtractDataAssetToJson(DA, FullPath);
		}
		else if (UDataTable* DT = Cast<UDataTable>(Current.Asset))
		{
			AssetType = TEXT("DataTable");
			bSuccess = ExtractDataTableToJson(DT, FullPath);
		}
		else if (UUserDefinedStruct* UserDefinedStruct = Cast<UUserDefinedStruct>(Current.Asset))
		{
			AssetType = TEXT("UserDefinedStruct");
			bSuccess = ExtractUserDefinedStructToJson(UserDefinedStruct, FullPath);
		}
		else if (UUserDefinedEnum* UserDefinedEnum = Cast<UUserDefinedEnum>(Current.Asset))
		{
			AssetType = TEXT("UserDefinedEnum");
			bSuccess = ExtractUserDefinedEnumToJson(UserDefinedEnum, FullPath);
		}
		else if (UCurveBase* Curve = Cast<UCurveBase>(Current.Asset))
		{
			AssetType = TEXT("Curve");
			bSuccess = ExtractCurveToJson(Curve, FullPath);
		}
		else if (UCurveTable* CurveTable = Cast<UCurveTable>(Current.Asset))
		{
			AssetType = TEXT("CurveTable");
			bSuccess = ExtractCurveTableToJson(CurveTable, FullPath);
		}
		else if (UMaterialInstance* MaterialInstance = Cast<UMaterialInstance>(Current.Asset))
		{
			AssetType = TEXT("MaterialInstance");
			bSuccess = ExtractMaterialInstanceToJson(MaterialInstance, FullPath);
			if (Current.Depth < MaxDepth)
			{
				Refs = CollectMaterialInstanceReferences(MaterialInstance);
			}
		}
		else if (UMaterial* Material = Cast<UMaterial>(Current.Asset))
		{
			AssetType = TEXT("Material");
			bSuccess = ExtractMaterialToJson(Material, FullPath);
			if (Current.Depth < MaxDepth)
			{
				Refs = CollectMaterialReferences(Material);
			}
		}
		else if (UMaterialFunctionInterface* MaterialFunction = Cast<UMaterialFunctionInterface>(Current.Asset))
		{
			AssetType = TEXT("MaterialFunction");
			bSuccess = ExtractMaterialFunctionToJson(MaterialFunction, FullPath);
			if (Current.Depth < MaxDepth)
			{
				Refs = CollectMaterialFunctionReferences(MaterialFunction);
			}
		}
		else if (UAnimSequence* AnimSequence = Cast<UAnimSequence>(Current.Asset))
		{
			AssetType = TEXT("AnimSequence");
			bSuccess = ExtractAnimSequenceToJson(AnimSequence, FullPath);
		}
		else if (UAnimMontage* AnimMontage = Cast<UAnimMontage>(Current.Asset))
		{
			AssetType = TEXT("AnimMontage");
			bSuccess = ExtractAnimMontageToJson(AnimMontage, FullPath);
			if (Current.Depth < MaxDepth)
			{
				Refs = CollectAnimMontageReferences(AnimMontage);
			}
		}
		else if (UBlendSpace* BlendSpace = Cast<UBlendSpace>(Current.Asset))
		{
			AssetType = TEXT("BlendSpace");
			bSuccess = ExtractBlendSpaceToJson(BlendSpace, FullPath);
			if (Current.Depth < MaxDepth)
			{
				Refs = CollectBlendSpaceReferences(BlendSpace);
			}
		}
		else
		{
			ErrorMessage = TEXT("Unsupported asset type");
		}

		if (bSuccess)
		{
			SuccessCount++;
			if (Current.Depth > 0)
			{
				UE_LOG(LogBlueprintExtractor, Log, TEXT("  Cascade [depth %d]: %s"), Current.Depth, *Current.Asset->GetName());
			}
		}
		else if (ErrorMessage.IsEmpty())
		{
			ErrorMessage = TEXT("Extraction returned false");
		}

		TSharedPtr<FJsonObject> ManifestItem = MakeShared<FJsonObject>();
		ManifestItem->SetStringField(TEXT("assetPath"), AssetPath);
		ManifestItem->SetStringField(TEXT("assetType"), AssetType);
		ManifestItem->SetStringField(TEXT("outputFile"), FileName);
		ManifestItem->SetNumberField(TEXT("depth"), Current.Depth);
		ManifestItem->SetStringField(TEXT("status"), bSuccess ? TEXT("extracted") : TEXT("failed"));
		if (!ErrorMessage.IsEmpty())
		{
			ManifestItem->SetStringField(TEXT("error"), ErrorMessage);
		}
		Manifest.Add(MakeShared<FJsonValueObject>(ManifestItem));

		// Enqueue discovered references
		for (const FSoftObjectPath& Ref : Refs)
		{
			FString RefPath = Ref.ToString();
			if (Visited.Contains(RefPath))
			{
				continue;
			}
			Visited.Add(RefPath);

			UObject* RefAsset = Ref.TryLoad();
			if (RefAsset && (Cast<UBlueprint>(RefAsset)
				|| Cast<UStateTree>(RefAsset)
				|| Cast<UBehaviorTree>(RefAsset)
				|| Cast<UBlackboardData>(RefAsset)
				|| Cast<UUserDefinedStruct>(RefAsset)
				|| Cast<UUserDefinedEnum>(RefAsset)
				|| Cast<UCurveBase>(RefAsset)
				|| Cast<UCurveTable>(RefAsset)
				|| Cast<UMaterial>(RefAsset)
				|| Cast<UMaterialFunctionInterface>(RefAsset)
				|| Cast<UMaterialInstance>(RefAsset)
				|| Cast<UAnimSequence>(RefAsset)
				|| Cast<UAnimMontage>(RefAsset)
				|| Cast<UBlendSpace>(RefAsset)))
			{
				Queue.Add({RefAsset, Current.Depth + 1});
			}
		}
	}

	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetNumberField(TEXT("extracted_count"), SuccessCount);
	Result->SetNumberField(TEXT("total_count"), Manifest.Num());
	Result->SetArrayField(TEXT("assets"), Manifest);
	return Result;
}
