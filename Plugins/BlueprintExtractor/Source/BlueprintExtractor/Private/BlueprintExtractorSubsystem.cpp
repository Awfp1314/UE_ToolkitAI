#include "BlueprintExtractorSubsystem.h"
#include "BlueprintExtractorLibrary.h"
#include "BlueprintExtractorModule.h"
#include "BlueprintExtractorSettings.h"
#include "Diagnostics/BlueprintExtractorLogAccess.h"
#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AnimMontageAuthoring.h"
#include "Authoring/AnimSequenceAuthoring.h"
#include "Authoring/BehaviorTreeAuthoring.h"
#include "Authoring/BlackboardAuthoring.h"
#include "Authoring/BlendSpaceAuthoring.h"
#include "Authoring/BlueprintAuthoring.h"
#include "Authoring/CurveAuthoring.h"
#include "Authoring/CurveTableAuthoring.h"
#include "Authoring/DataAssetAuthoring.h"
#include "Authoring/DataTableAuthoring.h"
#include "Authoring/FontAuthoring.h"
#include "Authoring/WidgetAnimationAuthoring.h"
#include "Capture/CaptureTypes.h"
#include "Import/ImportJobManager.h"
#include "Authoring/MaterialGraphAuthoring.h"
#include "Authoring/MaterialInstanceAuthoring.h"
#include "Authoring/StateTreeAuthoring.h"
#include "Authoring/UserDefinedEnumAuthoring.h"
#include "Authoring/UserDefinedStructAuthoring.h"
#include "PropertySerializer.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/BlendSpace.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BlackboardData.h"
#include "Curves/CurveBase.h"
#include "Engine/Blueprint.h"
#include "Engine/CurveTable.h"
#include "Engine/DataAsset.h"
#include "Engine/DataTable.h"
#include "Engine/UserDefinedEnum.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputTriggers.h"
#include "InputModifiers.h"
#include "InputCoreTypes.h"
#include "Materials/Material.h"
#include "Materials/MaterialFunctionInterface.h"
#include "Materials/MaterialInstance.h"
#include "StateTree.h"
#include "StructUtils/UserDefinedStruct.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "ContentBrowserModule.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Selection.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/Actor.h"
#include "IContentBrowserSingleton.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonReader.h"
#include "Builders/WidgetTreeBuilder.h"
#include "PlayInEditorDataTypes.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Tests/AutomationEditorCommon.h"
#include "WidgetBlueprint.h"
#include "Containers/Ticker.h"
#include "GenericPlatform/GenericPlatformProperties.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/EngineVersionComparison.h"
#include "HAL/PlatformMisc.h"
#include "FileHelpers.h"
#include "Editor/UnrealEdEngine.h"
#include "UnrealEdGlobals.h"
#include "UnrealEdMisc.h"
#include "UObject/UObjectIterator.h"

#include "Debugger/StateTreeDebuggerBridge.h"

#if PLATFORM_WINDOWS
#include "ILiveCodingModule.h"
#endif

static FString MakeErrorJson(const FString& Message)
{
	const TSharedPtr<FJsonObject> ErrorObj = MakeShared<FJsonObject>();
	ErrorObj->SetStringField(TEXT("error"), Message);

	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
	return OutString;
}

static FString SerializeJsonObject(const TSharedPtr<FJsonObject>& JsonObject)
{
	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
	return OutString;
}

static bool ParseOptionalJsonObject(const FString& JsonText, TSharedPtr<FJsonObject>& OutObject, FString& OutError)
{
	OutObject = MakeShared<FJsonObject>();
	if (JsonText.IsEmpty())
	{
		return true;
	}

	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, OutObject) || !OutObject.IsValid())
	{
		OutError = TEXT("Invalid JSON payload");
		return false;
	}

	return true;
}

static void SetSharedEditorContextFields(const TSharedPtr<FJsonObject>& Result, const FBlueprintExtractorModule* Module)
{
	if (!Result.IsValid())
	{
		return;
	}

	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("projectName"), FApp::GetProjectName());
	Result->SetStringField(TEXT("projectFilePath"), FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath()));
	Result->SetStringField(TEXT("projectDir"), FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()));

	if (Module)
	{
		Result->SetStringField(TEXT("instanceId"), Module->GetEditorInstanceId());
		Result->SetStringField(TEXT("engineRoot"), Module->GetEngineRoot());
		Result->SetStringField(TEXT("editorTarget"), Module->GetEditorTarget());
		Result->SetNumberField(TEXT("processId"), Module->GetEditorProcessId());
		Result->SetStringField(TEXT("remoteControlHost"), Module->GetRemoteControlHost());
		Result->SetNumberField(TEXT("remoteControlPort"), Module->GetRemoteControlHttpPort());
		if (!Module->GetLastRegistryHeartbeat().IsEmpty())
		{
			Result->SetStringField(TEXT("lastSeenAt"), Module->GetLastRegistryHeartbeat());
		}
	}
	else
	{
		const FString EngineDir = FPaths::ConvertRelativePathToFull(FPaths::EngineDir());
		Result->SetStringField(TEXT("engineRoot"), FPaths::GetPath(FPaths::GetPath(EngineDir)));
		Result->SetStringField(TEXT("editorTarget"), FString::Printf(TEXT("%sEditor"), FApp::GetProjectName()));
		Result->SetNumberField(TEXT("processId"), static_cast<int32>(FPlatformProcess::GetCurrentProcessId()));
		Result->SetStringField(TEXT("remoteControlHost"), TEXT("127.0.0.1"));
		Result->SetNumberField(TEXT("remoteControlPort"), 30010);
	}
}

static TArray<TSharedPtr<FJsonValue>> ToJsonStringArray(const TArray<FString>& Values)
{
	TArray<TSharedPtr<FJsonValue>> Result;
	Result.Reserve(Values.Num());
	for (const FString& Value : Values)
	{
		if (!Value.IsEmpty())
		{
			Result.Add(MakeShared<FJsonValueString>(Value));
		}
	}
	return Result;
}

static bool CanQueryInteractiveEditorState()
{
	return FApp::CanEverRender() && FSlateApplication::IsInitialized();
}

static void AddUnsupportedSection(TArray<FString>& UnsupportedSections, const TCHAR* SectionName)
{
	UnsupportedSections.AddUnique(SectionName);
}

static void CollectSelectedAssetPaths(TArray<FString>& OutAssetPaths)
{
	if (!CanQueryInteractiveEditorState())
	{
		return;
	}

	FContentBrowserModule& ContentBrowserModule = FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));
	IContentBrowserSingleton& ContentBrowser = ContentBrowserModule.Get();
	TArray<FAssetData> SelectedAssets;
	ContentBrowser.GetSelectedAssets(SelectedAssets);

	for (const FAssetData& AssetData : SelectedAssets)
	{
		const FString PackagePath = AssetData.PackageName.ToString();
		if (!PackagePath.IsEmpty())
		{
			OutAssetPaths.AddUnique(PackagePath);
		}
	}
}

static void CollectSelectedActorNames(TArray<FString>& OutActorNames)
{
	if (!CanQueryInteractiveEditorState() || !GEditor)
	{
		return;
	}

	USelection* SelectedActors = GEditor->GetSelectedActors();
	if (!SelectedActors)
	{
		return;
	}

	for (FSelectionIterator It(*SelectedActors); It; ++It)
	{
		if (const AActor* Actor = Cast<AActor>(*It))
		{
			OutActorNames.AddUnique(Actor->GetActorNameOrLabel());
		}
	}
}

static void CollectOpenAssetEditors(TArray<FString>& OutOpenAssetEditors)
{
	if (!CanQueryInteractiveEditorState() || !GEditor)
	{
		return;
	}

	if (UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>())
	{
		for (UObject* EditedAsset : AssetEditorSubsystem->GetAllEditedAssets())
		{
			if (EditedAsset)
			{
				OutOpenAssetEditors.AddUnique(EditedAsset->GetPathName());
			}
		}
	}
}

static FString GetActiveLevelPath()
{
	if (!GEditor)
	{
		return FString();
	}

	if (UWorld* EditorWorld = GEditor->GetEditorWorldContext().World())
	{
		if (UPackage* WorldPackage = EditorWorld->GetOutermost())
		{
			return WorldPackage->GetName();
		}
	}

	return FString();
}

static TSharedPtr<FJsonObject> BuildPieSummaryJson()
{
	const TSharedPtr<FJsonObject> PieSummary = MakeShared<FJsonObject>();
	const bool bIsPlayingInEditor = GEditor && GEditor->PlayWorld != nullptr;
	const bool bIsSimulatingInEditor = GEditor && GEditor->bIsSimulatingInEditor;
	PieSummary->SetBoolField(TEXT("isPlayingInEditor"), bIsPlayingInEditor);
	PieSummary->SetBoolField(TEXT("isSimulatingInEditor"), bIsSimulatingInEditor);

	if (bIsPlayingInEditor && GEditor->PlayWorld)
	{
		PieSummary->SetStringField(TEXT("worldName"), GEditor->PlayWorld->GetName());
		if (UPackage* WorldPackage = GEditor->PlayWorld->GetOutermost())
		{
			PieSummary->SetStringField(TEXT("worldPath"), WorldPackage->GetName());
		}
	}

	return PieSummary;
}

static FBlueprintExtractorImportJobManager& GetImportJobManager(FBlueprintExtractorImportJobManager*& Manager)
{
	static FBlueprintExtractorImportJobManager* SharedManager = new FBlueprintExtractorImportJobManager();
	Manager = SharedManager;
	return *SharedManager;
}

template <typename AssetType>
static AssetType* LoadAssetByPath(const FString& AssetPath)
{
	if (AssetType* ResolvedAsset = Cast<AssetType>(ResolveAssetByPath(AssetPath)))
	{
		return ResolvedAsset;
	}

	const FString ObjectPath = NormalizeAssetObjectPath(AssetPath);
	if (ObjectPath.IsEmpty())
	{
		return nullptr;
	}

	FString PackagePath = ObjectPath;
	if (FPackageName::IsValidObjectPath(ObjectPath))
	{
		PackagePath = FPackageName::ObjectPathToPackageName(ObjectPath);
	}

	for (TObjectIterator<AssetType> It; It; ++It)
	{
		AssetType* Candidate = *It;
		if (!Candidate || Candidate->HasAnyFlags(RF_ClassDefaultObject))
		{
			continue;
		}

		if (Candidate->GetPathName() == ObjectPath)
		{
			return Candidate;
		}

		if (UPackage* CandidatePackage = Candidate->GetOutermost())
		{
			if (CandidatePackage->GetName() == PackagePath)
			{
				return Candidate;
			}
		}
	}

	return nullptr;
}

namespace EnhancedInputAuthoringInternal
{

static bool ParseJsonObjectInput(const FString& RawJson, TSharedPtr<FJsonObject>& OutObject)
{
	if (RawJson.IsEmpty())
	{
		OutObject = MakeShared<FJsonObject>();
		return true;
	}

	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RawJson);
	return FJsonSerializer::Deserialize(Reader, OutObject) && OutObject.IsValid();
}

static bool ParseJsonArrayInput(const FString& RawJson, TArray<TSharedPtr<FJsonValue>>& OutArray)
{
	if (RawJson.IsEmpty())
	{
		OutArray.Reset();
		return true;
	}

	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RawJson);
	return FJsonSerializer::Deserialize(Reader, OutArray);
}

static TSharedPtr<FJsonObject> CloneJsonObject(const TSharedPtr<FJsonObject>& Source)
{
	if (!Source.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Source->Values)
	{
		Result->SetField(Pair.Key, Pair.Value);
	}
	return Result;
}

static void RemapField(const TSharedPtr<FJsonObject>& Object, const TCHAR* SourceField, const TCHAR* TargetField)
{
	if (!Object.IsValid() || !Object->HasField(SourceField))
	{
		return;
	}

	if (!Object->HasField(TargetField))
	{
		if (const TSharedPtr<FJsonValue> Existing = Object->TryGetField(SourceField))
		{
			Object->SetField(TargetField, Existing);
		}
	}

	Object->RemoveField(SourceField);
}

static TSharedPtr<FJsonObject> NormalizeInputActionProperties(const TSharedPtr<FJsonObject>& Properties)
{
	const TSharedPtr<FJsonObject> Result = CloneJsonObject(Properties);
	RemapField(Result, TEXT("action_description"), TEXT("ActionDescription"));
	RemapField(Result, TEXT("trigger_when_paused"), TEXT("bTriggerWhenPaused"));
	RemapField(Result, TEXT("consume_input"), TEXT("bConsumeInput"));
	RemapField(Result, TEXT("consumes_action_and_axis_mappings"), TEXT("bConsumesActionAndAxisMappings"));
	RemapField(Result, TEXT("reserve_all_mappings"), TEXT("bReserveAllMappings"));
	RemapField(Result, TEXT("trigger_events_that_consume_legacy_keys"), TEXT("TriggerEventsThatConsumeLegacyKeys"));
	RemapField(Result, TEXT("accumulation_behavior"), TEXT("AccumulationBehavior"));
	return Result;
}

static TSharedPtr<FJsonObject> NormalizeInputMappingContextProperties(const TSharedPtr<FJsonObject>& Properties)
{
	const TSharedPtr<FJsonObject> Result = CloneJsonObject(Properties);
	RemapField(Result, TEXT("context_description"), TEXT("ContextDescription"));
	RemapField(Result, TEXT("registration_tracking_mode"), TEXT("RegistrationTrackingMode"));
	RemapField(Result, TEXT("input_mode_filter_options"), TEXT("InputModeFilterOptions"));
	return Result;
}

static bool ResolveInputActionValueType(const FString& ValueTypeName, EInputActionValueType& OutValueType)
{
	if (ValueTypeName.IsEmpty())
	{
		return true;
	}

	if (ValueTypeName.Equals(TEXT("boolean"), ESearchCase::IgnoreCase))
	{
		OutValueType = EInputActionValueType::Boolean;
		return true;
	}
	if (ValueTypeName.Equals(TEXT("axis_1d"), ESearchCase::IgnoreCase))
	{
		OutValueType = EInputActionValueType::Axis1D;
		return true;
	}
	if (ValueTypeName.Equals(TEXT("axis_2d"), ESearchCase::IgnoreCase))
	{
		OutValueType = EInputActionValueType::Axis2D;
		return true;
	}
	if (ValueTypeName.Equals(TEXT("axis_3d"), ESearchCase::IgnoreCase))
	{
		OutValueType = EInputActionValueType::Axis3D;
		return true;
	}

	return false;
}

static void CleanupFailedCreate(UObject* CreatedObject, UPackage* Package)
{
	if (CreatedObject)
	{
		CreatedObject->ClearFlags(RF_Public | RF_Standalone);
		CreatedObject->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors | REN_ForceNoResetLoaders | REN_NonTransactional);
		CreatedObject->MarkAsGarbage();
	}

	if (Package)
	{
		Package->SetDirtyFlag(false);
	}
}

static bool ApplyInputActionProperties(UInputAction* InputAction,
                                       const FString& ValueTypeName,
                                       const TSharedPtr<FJsonObject>& PropertiesJson,
                                       TArray<FString>& OutErrors,
                                       const bool bValidationOnly)
{
	EInputActionValueType ValueType = InputAction ? InputAction->ValueType : EInputActionValueType::Boolean;
	if (!ResolveInputActionValueType(ValueTypeName, ValueType))
	{
		OutErrors.Add(FString::Printf(TEXT("Unsupported value_type '%s'. Expected boolean, axis_1d, axis_2d, or axis_3d."), *ValueTypeName));
	}

	const TSharedPtr<FJsonObject> NormalizedProperties = NormalizeInputActionProperties(PropertiesJson);
	const bool bPropertiesApplied = FPropertySerializer::ApplyPropertiesFromJson(
		InputAction,
		NormalizedProperties,
		OutErrors,
		bValidationOnly,
		true);

	if (!bValidationOnly && InputAction)
	{
		InputAction->ValueType = ValueType;
	}

	return bPropertiesApplied && OutErrors.Num() == 0;
}

static bool ApplyInputMappingContextProperties(UInputMappingContext* MappingContext,
                                               const TSharedPtr<FJsonObject>& PropertiesJson,
                                               TArray<FString>& OutErrors,
                                               const bool bValidationOnly)
{
	return FPropertySerializer::ApplyPropertiesFromJson(
		MappingContext,
		NormalizeInputMappingContextProperties(PropertiesJson),
		OutErrors,
		bValidationOnly,
		true);
}

static bool ApplyMappings(UInputMappingContext* MappingContext,
                          const TArray<TSharedPtr<FJsonValue>>& MappingValues,
                          const bool bReplaceMappings,
                          TArray<FString>& OutErrors,
                          const bool bValidationOnly)
{
	if (!MappingContext)
	{
		OutErrors.Add(TEXT("InputMappingContext is null."));
		return false;
	}

	if (!bValidationOnly && bReplaceMappings)
	{
		MappingContext->UnmapAll();
	}

	for (const TSharedPtr<FJsonValue>& Value : MappingValues)
	{
		const TSharedPtr<FJsonObject> MappingObject = Value.IsValid() ? Value->AsObject() : nullptr;
		if (!MappingObject.IsValid())
		{
			OutErrors.Add(TEXT("Each mapping entry must be a JSON object."));
			continue;
		}

		FString ActionPath;
		if (!MappingObject->TryGetStringField(TEXT("action"), ActionPath) || ActionPath.IsEmpty())
		{
			OutErrors.Add(TEXT("Each mapping entry requires action."));
			continue;
		}

		UInputAction* InputAction = LoadAssetByPath<UInputAction>(ActionPath);
		if (!InputAction)
		{
			OutErrors.Add(FString::Printf(TEXT("InputAction not found: %s"), *ActionPath));
			continue;
		}

		FString KeyName;
		if (!MappingObject->TryGetStringField(TEXT("key"), KeyName) || KeyName.IsEmpty())
		{
			OutErrors.Add(TEXT("Each mapping entry requires key."));
			continue;
		}

		const FKey Key(*KeyName);
		if (!Key.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("Invalid input key: %s"), *KeyName));
			continue;
		}

		if (!bValidationOnly)
		{
			MappingContext->MapKey(InputAction, Key);
		}
	}

	return OutErrors.Num() == 0;
}

} // namespace EnhancedInputAuthoringInternal

static bool ResolveAssetClassFilter(const FString& ClassFilter, FTopLevelAssetPath& OutClassPath, bool& bOutRecursiveClasses)
{
	bOutRecursiveClasses = false;

	if (ClassFilter.IsEmpty())
	{
		return false;
	}

	if (ClassFilter.Equals(TEXT("Blueprint"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UBlueprint::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("AnimBlueprint"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UAnimBlueprint::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("WidgetBlueprint"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UWidgetBlueprint::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("StateTree"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UStateTree::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("BehaviorTree"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UBehaviorTree::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("Blackboard"), ESearchCase::IgnoreCase)
		|| ClassFilter.Equals(TEXT("BlackboardData"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UBlackboardData::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("DataTable"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UDataTable::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("DataAsset"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UDataAsset::StaticClass()->GetClassPathName();
		bOutRecursiveClasses = true;
		return true;
	}

	if (ClassFilter.Equals(TEXT("UserDefinedStruct"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UUserDefinedStruct::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("UserDefinedEnum"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UUserDefinedEnum::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("Curve"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UCurveBase::StaticClass()->GetClassPathName();
		bOutRecursiveClasses = true;
		return true;
	}

	if (ClassFilter.Equals(TEXT("CurveTable"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UCurveTable::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("MaterialInstance"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UMaterialInstance::StaticClass()->GetClassPathName();
		bOutRecursiveClasses = true;
		return true;
	}

	if (ClassFilter.Equals(TEXT("Material"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UMaterial::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("MaterialFunction"), ESearchCase::IgnoreCase)
		|| ClassFilter.Equals(TEXT("MaterialLayer"), ESearchCase::IgnoreCase)
		|| ClassFilter.Equals(TEXT("MaterialLayerBlend"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UMaterialFunctionInterface::StaticClass()->GetClassPathName();
		bOutRecursiveClasses = true;
		return true;
	}

	if (ClassFilter.Equals(TEXT("AnimSequence"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UAnimSequence::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("AnimMontage"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UAnimMontage::StaticClass()->GetClassPathName();
		return true;
	}

	if (ClassFilter.Equals(TEXT("BlendSpace"), ESearchCase::IgnoreCase))
	{
		OutClassPath = UBlendSpace::StaticClass()->GetClassPathName();
		bOutRecursiveClasses = true;
		return true;
	}

	return false;
}

EBlueprintExtractionScope UBlueprintExtractorSubsystem::ParseScope(const FString& ScopeString)
{
	if (ScopeString == TEXT("ClassLevel"))       { return EBlueprintExtractionScope::ClassLevel; }
	if (ScopeString == TEXT("Variables"))        { return EBlueprintExtractionScope::Variables; }
	if (ScopeString == TEXT("Components"))       { return EBlueprintExtractionScope::Components; }
	if (ScopeString == TEXT("FunctionsShallow")) { return EBlueprintExtractionScope::FunctionsShallow; }
	if (ScopeString == TEXT("FullWithBytecode")) { return EBlueprintExtractionScope::FullWithBytecode; }
	return EBlueprintExtractionScope::Full;
}

UBlueprintExtractorSubsystem::~UBlueprintExtractorSubsystem()
{
	if (StateTreeDebuggerBridgeInstance)
	{
		StateTreeDebuggerBridgeInstance->Shutdown();
	}
	ImportJobManager = nullptr;
}

FString UBlueprintExtractorSubsystem::ExtractBlueprint(const FString& AssetPath, const FString& Scope, const FString& GraphFilter, const bool bIncludeClassDefaults)
{
	const EBlueprintExtractionScope ParsedScope = ParseScope(Scope);

	UBlueprint* Blueprint = LoadAssetByPath<UBlueprint>(AssetPath);
	if (Blueprint == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	// Parse comma-separated graph filter into TArray<FName>
	TArray<FName> ParsedFilter;
	if (!GraphFilter.IsEmpty())
	{
		TArray<FString> Parts;
		GraphFilter.ParseIntoArray(Parts, TEXT(","), true);
		for (const FString& Part : Parts)
		{
			ParsedFilter.Add(FName(*Part.TrimStartAndEnd()));
		}
	}

	FString OutString;
	UBlueprintExtractorLibrary::ExtractBlueprintToJsonString(Blueprint, OutString, ParsedScope, ParsedFilter, bIncludeClassDefaults);
	return OutString;
}

FString UBlueprintExtractorSubsystem::ExtractStateTree(const FString& AssetPath)
{
	UStateTree* StateTree = LoadAssetByPath<UStateTree>(AssetPath);
	if (StateTree == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractStateTreeToJsonObject(StateTree);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract StateTree"));
	}

	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
	return OutString;
}

FString UBlueprintExtractorSubsystem::ExtractDataAsset(const FString& AssetPath)
{
	UDataAsset* DataAsset = LoadAssetByPath<UDataAsset>(AssetPath);
	if (DataAsset == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractDataAssetToJsonObject(DataAsset);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract DataAsset"));
	}

	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
	return OutString;
}

FString UBlueprintExtractorSubsystem::ExtractDataTable(const FString& AssetPath)
{
	UDataTable* DataTable = LoadAssetByPath<UDataTable>(AssetPath);
	if (DataTable == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractDataTableToJsonObject(DataTable);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract DataTable"));
	}

	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
	return OutString;
}

FString UBlueprintExtractorSubsystem::ExtractBehaviorTree(const FString& AssetPath)
{
	UBehaviorTree* BehaviorTree = LoadAssetByPath<UBehaviorTree>(AssetPath);
	if (BehaviorTree == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractBehaviorTreeToJsonObject(BehaviorTree);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract BehaviorTree"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractBlackboard(const FString& AssetPath)
{
	UBlackboardData* BlackboardData = LoadAssetByPath<UBlackboardData>(AssetPath);
	if (BlackboardData == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractBlackboardToJsonObject(BlackboardData);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract Blackboard"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractUserDefinedStruct(const FString& AssetPath)
{
	UUserDefinedStruct* UserDefinedStruct = LoadAssetByPath<UUserDefinedStruct>(AssetPath);
	if (UserDefinedStruct == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractUserDefinedStructToJsonObject(UserDefinedStruct);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract UserDefinedStruct"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractUserDefinedEnum(const FString& AssetPath)
{
	UUserDefinedEnum* UserDefinedEnum = LoadAssetByPath<UUserDefinedEnum>(AssetPath);
	if (UserDefinedEnum == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractUserDefinedEnumToJsonObject(UserDefinedEnum);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract UserDefinedEnum"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractCurve(const FString& AssetPath)
{
	UCurveBase* Curve = LoadAssetByPath<UCurveBase>(AssetPath);
	if (Curve == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractCurveToJsonObject(Curve);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract Curve"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractCurveTable(const FString& AssetPath)
{
	UCurveTable* CurveTable = LoadAssetByPath<UCurveTable>(AssetPath);
	if (CurveTable == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractCurveTableToJsonObject(CurveTable);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract CurveTable"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractMaterialInstance(const FString& AssetPath)
{
	UMaterialInstance* MaterialInstance = LoadAssetByPath<UMaterialInstance>(AssetPath);
	if (MaterialInstance == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a MaterialInstance: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractMaterialInstanceToJsonObject(MaterialInstance);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract MaterialInstance"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractMaterial(const FString& AssetPath, const bool bVerbose)
{
	UMaterial* Material = LoadAssetByPath<UMaterial>(AssetPath);
	if (!Material)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a Material: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractMaterialToJsonObject(Material, bVerbose);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract Material"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractMaterialFunction(const FString& AssetPath, const bool bVerbose)
{
	UMaterialFunctionInterface* MaterialFunction = LoadAssetByPath<UMaterialFunctionInterface>(AssetPath);
	if (!MaterialFunction)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a MaterialFunction asset: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractMaterialFunctionToJsonObject(MaterialFunction, bVerbose);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract MaterialFunction asset"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractAnimSequence(const FString& AssetPath)
{
	UAnimSequence* AnimSequence = LoadAssetByPath<UAnimSequence>(AssetPath);
	if (AnimSequence == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractAnimSequenceToJsonObject(AnimSequence);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract AnimSequence"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractAnimMontage(const FString& AssetPath)
{
	UAnimMontage* AnimMontage = LoadAssetByPath<UAnimMontage>(AssetPath);
	if (AnimMontage == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractAnimMontageToJsonObject(AnimMontage);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract AnimMontage"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractBlendSpace(const FString& AssetPath)
{
	UBlendSpace* BlendSpace = LoadAssetByPath<UBlendSpace>(AssetPath);
	if (BlendSpace == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> JsonObject = UBlueprintExtractorLibrary::ExtractBlendSpaceToJsonObject(BlendSpace);
	if (!JsonObject.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract BlendSpace"));
	}

	return SerializeJsonObject(JsonObject);
}

FString UBlueprintExtractorSubsystem::ExtractCascade(const FString& AssetPathsJson,
                                                      const FString& Scope,
                                                      const int32 MaxDepth,
                                                      const FString& GraphFilter)
{
	TArray<TSharedPtr<FJsonValue>> JsonValues;
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(AssetPathsJson);
		if (!FJsonSerializer::Deserialize(Reader, JsonValues))
		{
			return MakeErrorJson(TEXT("Invalid JSON array for AssetPathsJson"));
		}
	}

	const EBlueprintExtractionScope ParsedScope = ParseScope(Scope);

	// Parse comma-separated graph filter into TArray<FName>
	TArray<FName> ParsedFilter;
	if (!GraphFilter.IsEmpty())
	{
		TArray<FString> Parts;
		GraphFilter.ParseIntoArray(Parts, TEXT(","), true);
		for (const FString& Part : Parts)
		{
			ParsedFilter.Add(FName(*Part.TrimStartAndEnd()));
		}
	}

	TArray<UObject*> LoadedAssets;
	TArray<TSharedPtr<FJsonValue>> SkippedAssets;
	for (const TSharedPtr<FJsonValue>& Value : JsonValues)
	{
		const FString AssetPath = Value->AsString();

		UObject* Asset = ResolveAssetByPath(AssetPath);
		if (Asset != nullptr)
		{
			LoadedAssets.Add(Asset);
		}
		else
		{
			const TSharedPtr<FJsonObject> FailedItem = MakeShared<FJsonObject>();
			FailedItem->SetStringField(TEXT("assetPath"), AssetPath);
			FailedItem->SetStringField(TEXT("assetType"), TEXT("Unknown"));
			FailedItem->SetNumberField(TEXT("depth"), 0);
			FailedItem->SetStringField(TEXT("status"), TEXT("skipped"));
			FailedItem->SetStringField(TEXT("error"), TEXT("Failed to load asset"));
			SkippedAssets.Add(MakeShared<FJsonValueObject>(FailedItem));
		}
	}

	const UBlueprintExtractorSettings* Settings = UBlueprintExtractorSettings::Get();
	const FString OutputDir = Settings->GetResolvedOutputDirectoryPath();

	TSharedPtr<FJsonObject> ResultObj = UBlueprintExtractorLibrary::ExtractWithCascade(LoadedAssets, OutputDir, ParsedScope, MaxDepth, ParsedFilter);
	if (!ResultObj.IsValid())
	{
		return MakeErrorJson(TEXT("Cascade extraction failed"));
	}

	TArray<TSharedPtr<FJsonValue>> AssetsArray;
	const TArray<TSharedPtr<FJsonValue>>* ExistingAssets = nullptr;
	if (ResultObj->TryGetArrayField(TEXT("assets"), ExistingAssets) && ExistingAssets)
	{
		AssetsArray = *ExistingAssets;
	}
	AssetsArray.Append(SkippedAssets);
	ResultObj->SetArrayField(TEXT("assets"), AssetsArray);
	ResultObj->SetNumberField(TEXT("total_count"), AssetsArray.Num());
	ResultObj->SetNumberField(TEXT("skipped_count"), SkippedAssets.Num());
	ResultObj->SetStringField(TEXT("output_directory"), OutputDir);
	return SerializeJsonObject(ResultObj);
}

FString UBlueprintExtractorSubsystem::SearchAssets(const FString& Query, const FString& ClassFilter, const int32 MaxResults)
{
	FARFilter Filter;
	Filter.PackagePaths.Add(TEXT("/Game"));
	Filter.bRecursivePaths = true;
	Filter.bIncludeOnlyOnDiskAssets = true;

	bool bRecursiveClasses = false;
	FTopLevelAssetPath ClassPath;
	const bool bFilterResolved = ResolveAssetClassFilter(ClassFilter, ClassPath, bRecursiveClasses);
	if (bFilterResolved)
	{
		Filter.ClassPaths.Add(ClassPath);
		Filter.bRecursiveClasses = bRecursiveClasses;
	}

	TArray<FAssetData> AssetDatas;
	IAssetRegistry::Get()->GetAssets(Filter, AssetDatas);
	AssetDatas.Sort([](const FAssetData& A, const FAssetData& B)
	{
		if (A.AssetName != B.AssetName)
		{
			return A.AssetName.LexicalLess(B.AssetName);
		}

		return A.GetObjectPathString() < B.GetObjectPathString();
	});

	TArray<TSharedPtr<FJsonValue>> ResultArray;
	const int32 ResultLimit = FMath::Max(1, MaxResults);
	for (const FAssetData& AssetData : AssetDatas)
	{
		const FString AssetName  = AssetData.AssetName.ToString();
		const FString AssetClass = AssetData.AssetClassPath.GetAssetName().ToString();

		const bool bNameMatches = Query.IsEmpty() || AssetName.Contains(Query, ESearchCase::IgnoreCase);
		const bool bClassMatches = ClassFilter.IsEmpty()
			|| bFilterResolved
			|| AssetClass.Equals(ClassFilter, ESearchCase::IgnoreCase);

		if (bNameMatches && bClassMatches)
		{
			const TSharedPtr<FJsonObject> AssetObj = MakeShared<FJsonObject>();
			AssetObj->SetStringField(TEXT("path"),  AssetData.GetObjectPathString());
			AssetObj->SetStringField(TEXT("name"),  AssetName);
			AssetObj->SetStringField(TEXT("class"), AssetClass);
			ResultArray.Add(MakeShared<FJsonValueObject>(AssetObj));

			if (ResultArray.Num() >= ResultLimit)
			{
				break;
			}
		}
	}

	const TSharedPtr<FJsonObject> ResultObj = MakeShared<FJsonObject>();
	ResultObj->SetStringField(TEXT("query"), Query);
	ResultObj->SetStringField(TEXT("classFilter"), ClassFilter);
	ResultObj->SetNumberField(TEXT("maxResults"), ResultLimit);
	ResultObj->SetArrayField(TEXT("results"), ResultArray);
	return SerializeJsonObject(ResultObj);
}

FString UBlueprintExtractorSubsystem::ListAssets(const FString& PackagePath,
                                                  const bool bRecursive,
                                                  const FString& ClassFilter)
{
	TArray<TSharedPtr<FJsonValue>> ResultArray;

	// When non-recursive, include immediate subdirectories so users can browse the folder tree
	if (!bRecursive)
	{
		TArray<FString> SubPaths;
		IAssetRegistry::Get()->GetSubPaths(PackagePath, SubPaths, false);
		for (const FString& SubPath : SubPaths)
		{
			const FString FolderName = FPaths::GetCleanFilename(SubPath);
			const TSharedPtr<FJsonObject> FolderObj = MakeShared<FJsonObject>();
			FolderObj->SetStringField(TEXT("path"), SubPath);
			FolderObj->SetStringField(TEXT("name"), FolderName);
			FolderObj->SetStringField(TEXT("class"), TEXT("Folder"));
			ResultArray.Add(MakeShared<FJsonValueObject>(FolderObj));
		}
	}

	TArray<FAssetData> AssetDatas;
	IAssetRegistry::Get()->GetAssetsByPath(FName(*PackagePath), AssetDatas, bRecursive);

	for (const FAssetData& AssetData : AssetDatas)
	{
		const FString AssetClass = AssetData.AssetClassPath.GetAssetName().ToString();

		if (!ClassFilter.IsEmpty() && AssetClass != ClassFilter)
		{
			continue;
		}

		const TSharedPtr<FJsonObject> AssetObj = MakeShared<FJsonObject>();
		AssetObj->SetStringField(TEXT("path"),  AssetData.GetObjectPathString());
		AssetObj->SetStringField(TEXT("name"),  AssetData.AssetName.ToString());
		AssetObj->SetStringField(TEXT("class"), AssetClass);
		ResultArray.Add(MakeShared<FJsonValueObject>(AssetObj));
	}

	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(ResultArray, Writer);
	return OutString;
}

FString UBlueprintExtractorSubsystem::CreateWidgetBlueprint(const FString& AssetPath, const FString& ParentClass)
{
	const TSharedPtr<FJsonObject> Result = FWidgetTreeBuilder::CreateWidgetBlueprint(AssetPath, ParentClass);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create WidgetBlueprint"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ExtractWidgetBlueprint(const FString& AssetPath, const bool bIncludeClassDefaults)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> Result = FWidgetTreeBuilder::ExtractWidgetBlueprint(WidgetBP, bIncludeClassDefaults);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract WidgetBlueprint authoring snapshot"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ExtractWidgetAnimation(const FString& AssetPath, const FString& AnimationName)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> Result = FWidgetAnimationAuthoring::Extract(WidgetBP, AnimationName);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to extract widget animation"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateWidgetAnimation(const FString& AssetPath,
                                                            const FString& AnimationName,
                                                            const FString& PayloadJson,
                                                            const bool bValidateOnly)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FWidgetAnimationAuthoring::Create(
		WidgetBP,
		AnimationName,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create widget animation"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyWidgetAnimation(const FString& AssetPath,
                                                            const FString& AnimationName,
                                                            const FString& Operation,
                                                            const FString& PayloadJson,
                                                            const bool bValidateOnly)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FWidgetAnimationAuthoring::Modify(
		WidgetBP,
		AnimationName,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify widget animation"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::BuildWidgetTree(const FString& AssetPath,
                                                      const FString& WidgetTreeJson,
                                                      const bool bValidateOnly)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedJson;
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(WidgetTreeJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedJson) || !ParsedJson.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for WidgetTreeJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FWidgetTreeBuilder::BuildWidgetTree(WidgetBP, ParsedJson, bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to build widget tree"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyWidget(const FString& AssetPath,
                                                   const FString& WidgetName,
                                                   const FString& PropertiesJson,
                                                   const FString& SlotJson,
                                                   const FString& WidgetOptionsJson,
                                                   const bool bValidateOnly)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedProperties;
	if (!PropertiesJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PropertiesJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedProperties))
		{
			return MakeErrorJson(TEXT("Invalid JSON for PropertiesJson"));
		}
	}
	if (!ParsedProperties.IsValid())
	{
		ParsedProperties = MakeShared<FJsonObject>();
	}

	TSharedPtr<FJsonObject> ParsedSlot;
	if (!SlotJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(SlotJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedSlot))
		{
			return MakeErrorJson(TEXT("Invalid JSON for SlotJson"));
		}
	}
	if (!ParsedSlot.IsValid())
	{
		ParsedSlot = MakeShared<FJsonObject>();
	}

	TSharedPtr<FJsonObject> ParsedWidgetOptions;
	if (!WidgetOptionsJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(WidgetOptionsJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedWidgetOptions) || !ParsedWidgetOptions.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for WidgetOptionsJson"));
		}
	}
	if (!ParsedWidgetOptions.IsValid())
	{
		ParsedWidgetOptions = MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject> Result = FWidgetTreeBuilder::ModifyWidget(
		WidgetBP,
		WidgetName,
		ParsedProperties,
		ParsedSlot,
		ParsedWidgetOptions,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify widget"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyWidgetBlueprintStructure(const FString& AssetPath,
                                                                    const FString& Operation,
                                                                    const FString& PayloadJson,
                                                                    const bool bValidateOnly)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FWidgetTreeBuilder::ModifyWidgetBlueprintStructure(
		WidgetBP,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify WidgetBlueprint structure"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CompileWidgetBlueprint(const FString& AssetPath)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> Result = FWidgetTreeBuilder::CompileWidgetBlueprint(WidgetBP);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to compile WidgetBlueprint"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CaptureWidgetPreview(const FString& AssetPath, int32 Width, int32 Height)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	FBlueprintExtractorCaptureMetadata Metadata;
	FString Error;
	if (!BlueprintExtractorCapture::CaptureWidgetPreview(WidgetBP, Width, Height, Metadata, Error))
	{
		return MakeErrorJson(Error);
	}

	const TSharedPtr<FJsonObject> Result = BlueprintExtractorCapture::CaptureMetadataToJson(Metadata);
	Result->SetStringField(TEXT("operation"), TEXT("capture_widget_preview"));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CaptureEditorScreenshot()
{
	FBlueprintExtractorCaptureMetadata Metadata;
	FString Error;
	if (!BlueprintExtractorCapture::CaptureEditorScreenshot(Metadata, Error))
	{
		return MakeErrorJson(Error);
	}

	const TSharedPtr<FJsonObject> Result = BlueprintExtractorCapture::CaptureMetadataToJson(Metadata);
	Result->SetStringField(TEXT("operation"), TEXT("capture_editor_screenshot"));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CaptureRuntimeScreenshot()
{
	FBlueprintExtractorCaptureMetadata Metadata;
	FString Error;
	if (!BlueprintExtractorCapture::CaptureRuntimeScreenshot(TEXT("runtime"), Metadata, Error))
	{
		return MakeErrorJson(Error);
	}

	const TSharedPtr<FJsonObject> Result = BlueprintExtractorCapture::CaptureMetadataToJson(Metadata);
	Result->SetStringField(TEXT("operation"), TEXT("capture_runtime_screenshot"));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CaptureWidgetMotionCheckpoints(const FString& AssetPath, const FString& PayloadJson)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	FBlueprintExtractorMotionCaptureResult MotionResult;
	FString Error;
	if (!BlueprintExtractorCapture::CaptureWidgetMotionCheckpoints(WidgetBP, ParsedPayload, MotionResult, Error))
	{
		return MakeErrorJson(Error);
	}

	const TSharedPtr<FJsonObject> Result = BlueprintExtractorCapture::MotionCaptureResultToJson(MotionResult);
	Result->SetStringField(TEXT("operation"), TEXT("capture_widget_motion_checkpoints"));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CompareCaptureToReference(const FString& CaptureIdOrPath,
                                                               const FString& ReferenceIdOrPath,
                                                               double Tolerance)
{
	FBlueprintExtractorCaptureCompareResult ComparisonResult;
	FString Error;
	if (!BlueprintExtractorCapture::CompareCaptureToReference(
		CaptureIdOrPath,
		ReferenceIdOrPath,
		Tolerance,
		ComparisonResult,
		Error))
	{
		return MakeErrorJson(Error);
	}

	const TSharedPtr<FJsonObject> Result = BlueprintExtractorCapture::CaptureCompareResultToJson(ComparisonResult);
	Result->SetStringField(TEXT("operation"), TEXT("compare_capture_to_reference"));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ListCaptures(const FString& AssetPathFilter)
{
	TArray<FBlueprintExtractorCaptureMetadata> Captures;
	FString Error;
	if (!BlueprintExtractorCapture::ListCaptures(AssetPathFilter, Captures, Error))
	{
		return MakeErrorJson(Error);
	}

	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("operation"), TEXT("list_captures"));
	Result->SetStringField(TEXT("assetPathFilter"), AssetPathFilter);
	Result->SetNumberField(TEXT("captureCount"), Captures.Num());

	TArray<TSharedPtr<FJsonValue>> CaptureValues;
	CaptureValues.Reserve(Captures.Num());
	for (const FBlueprintExtractorCaptureMetadata& Capture : Captures)
	{
		CaptureValues.Add(MakeShared<FJsonValueObject>(BlueprintExtractorCapture::CaptureMetadataToJson(Capture)));
	}

	Result->SetArrayField(TEXT("captures"), CaptureValues);
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CleanupCaptures(int32 MaxAgeDays)
{
	int32 DeletedCount = 0;
	int64 FreedBytes = 0;
	FString Error;
	if (!BlueprintExtractorCapture::CleanupCaptures(MaxAgeDays, DeletedCount, FreedBytes, Error))
	{
		return MakeErrorJson(Error);
	}

	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("operation"), TEXT("cleanup_captures"));
	Result->SetNumberField(TEXT("deletedCount"), DeletedCount);
	Result->SetNumberField(TEXT("freedBytes"), static_cast<double>(FreedBytes));
	Result->SetNumberField(TEXT("maxAgeDays"), FMath::Max(0, MaxAgeDays));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ImportFonts(const FString& PayloadJson, const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FFontAuthoring::ImportFonts(ParsedPayload, bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to import fonts"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ApplyWidgetFonts(const FString& AssetPath,
                                                       const FString& PayloadJson,
                                                       const bool bValidateOnly)
{
	UWidgetBlueprint* WidgetBP = LoadAssetByPath<UWidgetBlueprint>(AssetPath);
	if (WidgetBP == nullptr)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a WidgetBlueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FWidgetTreeBuilder::ApplyWidgetFonts(WidgetBP, ParsedPayload, bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to apply widget fonts"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::SaveAssets(const FString& AssetPathsJson)
{
	TArray<TSharedPtr<FJsonValue>> JsonValues;
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(AssetPathsJson);
		if (!FJsonSerializer::Deserialize(Reader, JsonValues))
		{
			return MakeErrorJson(TEXT("Invalid JSON array for AssetPathsJson"));
		}
	}

	TArray<FString> AssetPaths;
	for (const TSharedPtr<FJsonValue>& Value : JsonValues)
	{
		if (Value.IsValid())
		{
			AssetPaths.Add(Value->AsString());
		}
	}

	const TSharedPtr<FJsonObject> Result = FAssetMutationContext::SaveAssets(AssetPaths);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to save assets"));
	}

	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(Result.ToSharedRef(), Writer);
	return OutString;
}

FString UBlueprintExtractorSubsystem::CreateDataAsset(const FString& AssetPath,
                                                      const FString& AssetClassPath,
                                                      const FString& PropertiesJson,
                                                      const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedProperties = MakeShared<FJsonObject>();
	if (!PropertiesJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PropertiesJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedProperties) || !ParsedProperties.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PropertiesJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FDataAssetAuthoring::Create(
		AssetPath,
		AssetClassPath,
		ParsedProperties,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create DataAsset"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyDataAsset(const FString& AssetPath,
                                                      const FString& PropertiesJson,
                                                      const bool bValidateOnly)
{
	UDataAsset* DataAsset = LoadAssetByPath<UDataAsset>(AssetPath);
	if (!DataAsset)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a DataAsset: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedProperties = MakeShared<FJsonObject>();
	if (!PropertiesJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PropertiesJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedProperties) || !ParsedProperties.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PropertiesJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FDataAssetAuthoring::Modify(
		DataAsset,
		ParsedProperties,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify DataAsset"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateInputAction(const FString& AssetPath,
                                                        const FString& ValueType,
                                                        const FString& PropertiesJson,
                                                        const bool bValidateOnly)
{
	using namespace EnhancedInputAuthoringInternal;

	TSharedPtr<FJsonObject> ParsedProperties;
	if (!ParseJsonObjectInput(PropertiesJson, ParsedProperties))
	{
		return MakeErrorJson(TEXT("Invalid JSON for PropertiesJson"));
	}

	FAssetMutationContext Context(TEXT("create_input_action"), AssetPath, TEXT("InputAction"), bValidateOnly);
	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return SerializeJsonObject(Context.BuildResult(false));
	}

	UInputAction* PreviewAction = NewObject<UInputAction>(GetTransientPackage(), UInputAction::StaticClass());
	TArray<FString> ValidationErrors;
	ApplyInputActionProperties(PreviewAction, ValueType, ParsedProperties, ValidationErrors, true);
	Context.SetValidationSummary(ValidationErrors.Num() == 0,
	                             ValidationErrors.Num() == 0 ? TEXT("InputAction payload validated.") : TEXT("InputAction payload failed validation."),
	                             ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, AssetPath);
	}
	if (ValidationErrors.Num() > 0)
	{
		return SerializeJsonObject(Context.BuildResult(false));
	}

	if (bValidateOnly)
	{
		return SerializeJsonObject(Context.BuildResult(true));
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create InputAction")));
	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return SerializeJsonObject(Context.BuildResult(false));
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UInputAction* InputAction = NewObject<UInputAction>(Package, UInputAction::StaticClass(), AssetName, RF_Public | RF_Standalone);
	if (!InputAction)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create InputAction asset: %s"), *AssetPath),
		                 AssetPath);
		return SerializeJsonObject(Context.BuildResult(false));
	}

	InputAction->Modify();
	TArray<FString> ApplyErrors;
	ApplyInputActionProperties(InputAction, ValueType, ParsedProperties, ApplyErrors, false);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		CleanupFailedCreate(InputAction, Package);
		return SerializeJsonObject(Context.BuildResult(false));
	}

	FAssetRegistryModule::AssetCreated(InputAction);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(InputAction);
	return SerializeJsonObject(Context.BuildResult(true));
}

FString UBlueprintExtractorSubsystem::ModifyInputAction(const FString& AssetPath,
                                                        const FString& ValueType,
                                                        const FString& PropertiesJson,
                                                        const bool bValidateOnly)
{
	using namespace EnhancedInputAuthoringInternal;

	UInputAction* InputAction = LoadAssetByPath<UInputAction>(AssetPath);
	if (!InputAction)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not an InputAction: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedProperties;
	if (!ParseJsonObjectInput(PropertiesJson, ParsedProperties))
	{
		return MakeErrorJson(TEXT("Invalid JSON for PropertiesJson"));
	}

	FAssetMutationContext Context(TEXT("modify_input_action"), AssetPath, TEXT("InputAction"), bValidateOnly);
	TArray<FString> ValidationErrors;
	ApplyInputActionProperties(InputAction, ValueType, ParsedProperties, ValidationErrors, true);
	Context.SetValidationSummary(ValidationErrors.Num() == 0,
	                             ValidationErrors.Num() == 0 ? TEXT("InputAction payload validated.") : TEXT("InputAction payload failed validation."),
	                             ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, AssetPath);
	}
	if (ValidationErrors.Num() > 0)
	{
		return SerializeJsonObject(Context.BuildResult(false));
	}

	if (bValidateOnly)
	{
		return SerializeJsonObject(Context.BuildResult(true));
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify InputAction")));
	InputAction->Modify();
	TArray<FString> ApplyErrors;
	ApplyInputActionProperties(InputAction, ValueType, ParsedProperties, ApplyErrors, false);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return SerializeJsonObject(Context.BuildResult(false));
	}

	InputAction->MarkPackageDirty();
	Context.TrackDirtyObject(InputAction);
	return SerializeJsonObject(Context.BuildResult(true));
}

FString UBlueprintExtractorSubsystem::CreateInputMappingContext(const FString& AssetPath,
                                                                const FString& PropertiesJson,
                                                                const FString& MappingsJson,
                                                                const bool bValidateOnly)
{
	using namespace EnhancedInputAuthoringInternal;

	TSharedPtr<FJsonObject> ParsedProperties;
	if (!ParseJsonObjectInput(PropertiesJson, ParsedProperties))
	{
		return MakeErrorJson(TEXT("Invalid JSON for PropertiesJson"));
	}

	TArray<TSharedPtr<FJsonValue>> ParsedMappings;
	if (!ParseJsonArrayInput(MappingsJson, ParsedMappings))
	{
		return MakeErrorJson(TEXT("Invalid JSON for MappingsJson"));
	}

	FAssetMutationContext Context(TEXT("create_input_mapping_context"), AssetPath, TEXT("InputMappingContext"), bValidateOnly);
	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return SerializeJsonObject(Context.BuildResult(false));
	}

	UInputMappingContext* PreviewContext = NewObject<UInputMappingContext>(GetTransientPackage(), UInputMappingContext::StaticClass());
	TArray<FString> ValidationErrors;
	ApplyInputMappingContextProperties(PreviewContext, ParsedProperties, ValidationErrors, true);
	ApplyMappings(PreviewContext, ParsedMappings, true, ValidationErrors, true);
	Context.SetValidationSummary(ValidationErrors.Num() == 0,
	                             ValidationErrors.Num() == 0 ? TEXT("InputMappingContext payload validated.") : TEXT("InputMappingContext payload failed validation."),
	                             ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, AssetPath);
	}
	if (ValidationErrors.Num() > 0)
	{
		return SerializeJsonObject(Context.BuildResult(false));
	}

	if (bValidateOnly)
	{
		return SerializeJsonObject(Context.BuildResult(true));
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create InputMappingContext")));
	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return SerializeJsonObject(Context.BuildResult(false));
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UInputMappingContext* MappingContext = NewObject<UInputMappingContext>(Package, UInputMappingContext::StaticClass(), AssetName, RF_Public | RF_Standalone);
	if (!MappingContext)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create InputMappingContext asset: %s"), *AssetPath),
		                 AssetPath);
		return SerializeJsonObject(Context.BuildResult(false));
	}

	MappingContext->Modify();
	TArray<FString> ApplyErrors;
	ApplyInputMappingContextProperties(MappingContext, ParsedProperties, ApplyErrors, false);
	ApplyMappings(MappingContext, ParsedMappings, true, ApplyErrors, false);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		CleanupFailedCreate(MappingContext, Package);
		return SerializeJsonObject(Context.BuildResult(false));
	}

	FAssetRegistryModule::AssetCreated(MappingContext);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(MappingContext);
	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetNumberField(TEXT("mappingCount"), MappingContext->GetMappings().Num());
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyInputMappingContext(const FString& AssetPath,
                                                                const FString& PropertiesJson,
                                                                const bool bReplaceMappings,
                                                                const FString& MappingsJson,
                                                                const bool bValidateOnly)
{
	using namespace EnhancedInputAuthoringInternal;

	UInputMappingContext* MappingContext = LoadAssetByPath<UInputMappingContext>(AssetPath);
	if (!MappingContext)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not an InputMappingContext: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedProperties;
	if (!ParseJsonObjectInput(PropertiesJson, ParsedProperties))
	{
		return MakeErrorJson(TEXT("Invalid JSON for PropertiesJson"));
	}

	TArray<TSharedPtr<FJsonValue>> ParsedMappings;
	if (!ParseJsonArrayInput(MappingsJson, ParsedMappings))
	{
		return MakeErrorJson(TEXT("Invalid JSON for MappingsJson"));
	}

	FAssetMutationContext Context(TEXT("modify_input_mapping_context"), AssetPath, TEXT("InputMappingContext"), bValidateOnly);
	TArray<FString> ValidationErrors;
	ApplyInputMappingContextProperties(MappingContext, ParsedProperties, ValidationErrors, true);
	ApplyMappings(MappingContext, ParsedMappings, bReplaceMappings, ValidationErrors, true);
	Context.SetValidationSummary(ValidationErrors.Num() == 0,
	                             ValidationErrors.Num() == 0 ? TEXT("InputMappingContext payload validated.") : TEXT("InputMappingContext payload failed validation."),
	                             ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, AssetPath);
	}
	if (ValidationErrors.Num() > 0)
	{
		return SerializeJsonObject(Context.BuildResult(false));
	}

	if (bValidateOnly)
	{
		return SerializeJsonObject(Context.BuildResult(true));
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify InputMappingContext")));
	MappingContext->Modify();
	TArray<FString> ApplyErrors;
	ApplyInputMappingContextProperties(MappingContext, ParsedProperties, ApplyErrors, false);
	ApplyMappings(MappingContext, ParsedMappings, bReplaceMappings, ApplyErrors, false);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return SerializeJsonObject(Context.BuildResult(false));
	}

	MappingContext->MarkPackageDirty();
	Context.TrackDirtyObject(MappingContext);
	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetNumberField(TEXT("mappingCount"), MappingContext->GetMappings().Num());
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateDataTable(const FString& AssetPath,
                                                      const FString& RowStructPath,
                                                      const FString& RowsJson,
                                                      const bool bValidateOnly)
{
	TArray<TSharedPtr<FJsonValue>> ParsedRows;
	if (!RowsJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RowsJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedRows))
		{
			return MakeErrorJson(TEXT("Invalid JSON array for RowsJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FDataTableAuthoring::Create(
		AssetPath,
		RowStructPath,
		ParsedRows,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create DataTable"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyDataTable(const FString& AssetPath,
                                                      const FString& PayloadJson,
                                                      const bool bValidateOnly)
{
	UDataTable* DataTable = LoadAssetByPath<UDataTable>(AssetPath);
	if (!DataTable)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a DataTable: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FDataTableAuthoring::Modify(
		DataTable,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify DataTable"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateCurve(const FString& AssetPath,
                                                  const FString& CurveType,
                                                  const FString& ChannelsJson,
                                                  const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedChannels = MakeShared<FJsonObject>();
	if (!ChannelsJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ChannelsJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedChannels) || !ParsedChannels.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for ChannelsJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FCurveAuthoring::Create(
		AssetPath,
		CurveType,
		ParsedChannels,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create curve"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyCurve(const FString& AssetPath,
                                                  const FString& PayloadJson,
                                                  const bool bValidateOnly)
{
	UCurveBase* Curve = LoadAssetByPath<UCurveBase>(AssetPath);
	if (!Curve)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a Curve asset: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FCurveAuthoring::Modify(
		Curve,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify curve"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateCurveTable(const FString& AssetPath,
                                                       const FString& CurveTableMode,
                                                       const FString& RowsJson,
                                                       const bool bValidateOnly)
{
	TArray<TSharedPtr<FJsonValue>> ParsedRows;
	if (!RowsJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RowsJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedRows))
		{
			return MakeErrorJson(TEXT("Invalid JSON array for RowsJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FCurveTableAuthoring::Create(
		AssetPath,
		CurveTableMode,
		ParsedRows,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create CurveTable"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyCurveTable(const FString& AssetPath,
                                                       const FString& PayloadJson,
                                                       const bool bValidateOnly)
{
	UCurveTable* CurveTable = LoadAssetByPath<UCurveTable>(AssetPath);
	if (!CurveTable)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a CurveTable: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FCurveTableAuthoring::Modify(
		CurveTable,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify CurveTable"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateMaterialInstance(const FString& AssetPath,
                                                             const FString& ParentMaterialPath,
                                                             const bool bValidateOnly)
{
	const TSharedPtr<FJsonObject> Result = FMaterialInstanceAuthoring::Create(
		AssetPath,
		ParentMaterialPath,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create MaterialInstance"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyMaterialInstance(const FString& AssetPath,
                                                             const FString& PayloadJson,
                                                             const bool bValidateOnly)
{
	UMaterialInstance* MaterialInstance = LoadAssetByPath<UMaterialInstance>(AssetPath);
	if (!MaterialInstance)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a MaterialInstance: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FMaterialInstanceAuthoring::Modify(
		MaterialInstance,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify MaterialInstance"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateMaterial(const FString& AssetPath,
                                                     const FString& InitialTexturePath,
                                                     const FString& SettingsJson,
                                                     const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedSettings = MakeShared<FJsonObject>();
	if (!SettingsJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(SettingsJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedSettings) || !ParsedSettings.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for SettingsJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FMaterialGraphAuthoring::CreateMaterial(
		AssetPath,
		InitialTexturePath,
		ParsedSettings,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create Material"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyMaterial(const FString& AssetPath,
                                                     const FString& PayloadJson,
                                                     const bool bValidateOnly)
{
	UMaterial* Material = LoadAssetByPath<UMaterial>(AssetPath);
	if (!Material)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a Material: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FMaterialGraphAuthoring::ModifyMaterial(
		Material,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify Material"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateMaterialFunction(const FString& AssetPath,
                                                             const FString& AssetKind,
                                                             const FString& SettingsJson,
                                                             const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedSettings = MakeShared<FJsonObject>();
	if (!SettingsJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(SettingsJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedSettings) || !ParsedSettings.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for SettingsJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FMaterialGraphAuthoring::CreateMaterialFunction(
		AssetPath,
		AssetKind,
		ParsedSettings,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create MaterialFunction asset"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyMaterialFunction(const FString& AssetPath,
                                                             const FString& PayloadJson,
                                                             const bool bValidateOnly)
{
	UMaterialFunctionInterface* MaterialFunction = LoadAssetByPath<UMaterialFunctionInterface>(AssetPath);
	if (!MaterialFunction)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found or not a MaterialFunction asset: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FMaterialGraphAuthoring::ModifyMaterialFunction(
		MaterialFunction,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify MaterialFunction asset"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CompileMaterialAsset(const FString& AssetPath)
{
	UObject* Asset = ResolveAssetByPath(AssetPath);
	if (!Asset)
	{
		return MakeErrorJson(FString::Printf(TEXT("Asset not found: %s"), *AssetPath));
	}

	const TSharedPtr<FJsonObject> Result = FMaterialGraphAuthoring::CompileMaterialAsset(Asset);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to compile material asset"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateUserDefinedStruct(
	const FString& AssetPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FUserDefinedStructAuthoring::Create(
		AssetPath,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create UserDefinedStruct"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyUserDefinedStruct(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UUserDefinedStruct* UserDefinedStruct = LoadAssetByPath<UUserDefinedStruct>(AssetPath);
	if (!UserDefinedStruct)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not a UserDefinedStruct: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FUserDefinedStructAuthoring::Modify(
		UserDefinedStruct,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify UserDefinedStruct"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateUserDefinedEnum(
	const FString& AssetPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FUserDefinedEnumAuthoring::Create(
		AssetPath,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create UserDefinedEnum"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyUserDefinedEnum(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UUserDefinedEnum* UserDefinedEnum = LoadAssetByPath<UUserDefinedEnum>(AssetPath);
	if (!UserDefinedEnum)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not a UserDefinedEnum: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FUserDefinedEnumAuthoring::Modify(
		UserDefinedEnum,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify UserDefinedEnum"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateBlackboard(
	const FString& AssetPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBlackboardAuthoring::Create(
		AssetPath,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create Blackboard"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyBlackboard(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UBlackboardData* BlackboardData = LoadAssetByPath<UBlackboardData>(AssetPath);
	if (!BlackboardData)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not a BlackboardData: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBlackboardAuthoring::Modify(
		BlackboardData,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify Blackboard"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateBehaviorTree(
	const FString& AssetPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBehaviorTreeAuthoring::Create(
		AssetPath,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create BehaviorTree"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyBehaviorTree(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UBehaviorTree* BehaviorTree = LoadAssetByPath<UBehaviorTree>(AssetPath);
	if (!BehaviorTree)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not a BehaviorTree: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBehaviorTreeAuthoring::Modify(
		BehaviorTree,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify BehaviorTree"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateStateTree(
	const FString& AssetPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FStateTreeAuthoring::Create(
		AssetPath,
		ParsedPayload,
		bValidateOnly);
	// Safety fallback — BuildResult should always return a valid pointer,
	// but guard against edge cases where the context is somehow empty.
	if (!Result.IsValid())
	{
		TSharedPtr<FJsonObject> Fallback = MakeShared<FJsonObject>();
		Fallback->SetBoolField(TEXT("success"), false);
		Fallback->SetStringField(TEXT("error"), TEXT("StateTree creation failed with no diagnostic context — this is a bug, please report"));
		return SerializeJsonObject(Fallback);
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyStateTree(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UStateTree* StateTree = LoadAssetByPath<UStateTree>(AssetPath);
	if (!StateTree)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not a StateTree: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FStateTreeAuthoring::Modify(
		StateTree,
		Operation,
		ParsedPayload,
		bValidateOnly);
	// Safety fallback — BuildResult should always return a valid pointer,
	// but guard against edge cases where the context is somehow empty.
	if (!Result.IsValid())
	{
		TSharedPtr<FJsonObject> Fallback = MakeShared<FJsonObject>();
		Fallback->SetBoolField(TEXT("success"), false);
		Fallback->SetStringField(TEXT("error"), TEXT("StateTree modification failed with no diagnostic context"));
		return SerializeJsonObject(Fallback);
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateAnimSequence(
	const FString& AssetPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FAnimSequenceAuthoring::Create(
		AssetPath,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create AnimSequence"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyAnimSequence(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UAnimSequence* AnimSequence = LoadAssetByPath<UAnimSequence>(AssetPath);
	if (!AnimSequence)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not an AnimSequence: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FAnimSequenceAuthoring::Modify(
		AnimSequence,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify AnimSequence"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateAnimMontage(
	const FString& AssetPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FAnimMontageAuthoring::Create(
		AssetPath,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create AnimMontage"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyAnimMontage(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UAnimMontage* AnimMontage = LoadAssetByPath<UAnimMontage>(AssetPath);
	if (!AnimMontage)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not an AnimMontage: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FAnimMontageAuthoring::Modify(
		AnimMontage,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify AnimMontage"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateBlendSpace(
	const FString& AssetPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBlendSpaceAuthoring::Create(
		AssetPath,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create BlendSpace"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyBlendSpace(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UBlendSpace* BlendSpace = LoadAssetByPath<UBlendSpace>(AssetPath);
	if (!BlendSpace)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not a BlendSpace: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBlendSpaceAuthoring::Modify(
		BlendSpace,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify BlendSpace"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::CreateBlueprint(
	const FString& AssetPath,
	const FString& ParentClassPath,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBlueprintAuthoring::Create(
		AssetPath,
		ParentClassPath,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to create Blueprint"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyBlueprintMembers(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UBlueprint* Blueprint = LoadAssetByPath<UBlueprint>(AssetPath);
	if (!Blueprint)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not a Blueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBlueprintAuthoring::Modify(
		Blueprint,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify Blueprint members"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ModifyBlueprintGraphs(
	const FString& AssetPath,
	const FString& Operation,
	const FString& PayloadJson,
	const bool bValidateOnly)
{
	UBlueprint* Blueprint = LoadAssetByPath<UBlueprint>(AssetPath);
	if (!Blueprint)
	{
		return MakeErrorJson(
			FString::Printf(TEXT("Asset not found or not a Blueprint: %s"), *AssetPath));
	}

	TSharedPtr<FJsonObject> ParsedPayload = MakeShared<FJsonObject>();
	if (!PayloadJson.IsEmpty())
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
		if (!FJsonSerializer::Deserialize(Reader, ParsedPayload) || !ParsedPayload.IsValid())
		{
			return MakeErrorJson(TEXT("Invalid JSON for PayloadJson"));
		}
	}

	const TSharedPtr<FJsonObject> Result = FBlueprintAuthoring::ModifyGraphs(
		Blueprint,
		Operation,
		ParsedPayload,
		bValidateOnly);
	if (!Result.IsValid())
	{
		return MakeErrorJson(TEXT("Failed to modify Blueprint graphs"));
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ImportAssets(const FString& PayloadJson, const bool bValidateOnly)
{
	return SerializeJsonObject(
		GetImportJobManager(ImportJobManager).EnqueueImportJob(
			TEXT("import_assets"),
			PayloadJson,
			bValidateOnly));
}

FString UBlueprintExtractorSubsystem::ReimportAssets(const FString& PayloadJson, const bool bValidateOnly)
{
	return SerializeJsonObject(
		GetImportJobManager(ImportJobManager).EnqueueReimportJob(
			TEXT("reimport_assets"),
			PayloadJson,
			bValidateOnly));
}

FString UBlueprintExtractorSubsystem::ImportTextures(const FString& PayloadJson, const bool bValidateOnly)
{
	return SerializeJsonObject(
		GetImportJobManager(ImportJobManager).EnqueueTextureImportJob(
			TEXT("import_textures"),
			PayloadJson,
			bValidateOnly));
}

FString UBlueprintExtractorSubsystem::ImportMeshes(const FString& PayloadJson, const bool bValidateOnly)
{
	return SerializeJsonObject(
		GetImportJobManager(ImportJobManager).EnqueueMeshImportJob(
			TEXT("import_meshes"),
			PayloadJson,
			bValidateOnly));
}

FString UBlueprintExtractorSubsystem::GetImportJob(const FString& JobId)
{
	return SerializeJsonObject(
		GetImportJobManager(ImportJobManager).GetImportJob(JobId));
}

FString UBlueprintExtractorSubsystem::ListImportJobs(const bool bIncludeCompleted)
{
	return SerializeJsonObject(
		GetImportJobManager(ImportJobManager).ListImportJobs(bIncludeCompleted));
}

FString UBlueprintExtractorSubsystem::GetProjectAutomationContext()
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	const FBlueprintExtractorModule* Module = FModuleManager::GetModulePtr<FBlueprintExtractorModule>(TEXT("BlueprintExtractor"));
	Result->SetStringField(TEXT("operation"), TEXT("get_project_automation_context"));
	SetSharedEditorContextFields(Result, Module);

	const FString EngineDir = FPaths::ConvertRelativePathToFull(FPaths::EngineDir());
	Result->SetStringField(TEXT("engineDir"), EngineDir);
	Result->SetStringField(TEXT("engineRoot"), Module ? Module->GetEngineRoot() : FPaths::GetPath(FPaths::GetPath(EngineDir)));
	Result->SetStringField(TEXT("engineVersion"), Module ? Module->GetEngineVersion() : FEngineVersion::Current().ToString());
	Result->SetStringField(TEXT("editorTarget"), Module ? Module->GetEditorTarget() : FString::Printf(TEXT("%sEditor"), FApp::GetProjectName()));
	Result->SetNumberField(TEXT("processId"), Module ? Module->GetEditorProcessId() : static_cast<int32>(FPlatformProcess::GetCurrentProcessId()));
	Result->SetStringField(TEXT("remoteControlHost"), Module ? Module->GetRemoteControlHost() : TEXT("127.0.0.1"));
	Result->SetNumberField(TEXT("remoteControlPort"), Module ? Module->GetRemoteControlHttpPort() : 30010);
	if (Module && !Module->GetLastRegistryHeartbeat().IsEmpty())
	{
		Result->SetStringField(TEXT("lastSeenAt"), Module->GetLastRegistryHeartbeat());
	}
	Result->SetStringField(TEXT("hostPlatform"), ANSI_TO_TCHAR(FPlatformProperties::PlatformName()));
	Result->SetBoolField(TEXT("isPlayingInEditor"), GEditor && GEditor->PlayWorld != nullptr);

	bool bSupportsLiveCoding = false;
	bool bLiveCodingAvailable = false;
	bool bLiveCodingEnabled = false;
	bool bLiveCodingStarted = false;
	FString LiveCodingError;

#if PLATFORM_WINDOWS
	bSupportsLiveCoding = true;
	if (FModuleManager::Get().ModuleExists(TEXT("LiveCoding")))
	{
		if (ILiveCodingModule* LiveCodingModule = FModuleManager::LoadModulePtr<ILiveCodingModule>(TEXT("LiveCoding")))
		{
			bLiveCodingAvailable = true;
			bLiveCodingEnabled = LiveCodingModule->IsEnabledForSession();
			bLiveCodingStarted = LiveCodingModule->HasStarted();
			if (!LiveCodingModule->CanEnableForSession() && !bLiveCodingEnabled)
			{
				LiveCodingError = LiveCodingModule->GetEnableErrorText().ToString();
			}
		}
	}
#endif

	Result->SetBoolField(TEXT("supportsLiveCoding"), bSupportsLiveCoding);
	Result->SetBoolField(TEXT("liveCodingAvailable"), bLiveCodingAvailable);
	Result->SetBoolField(TEXT("liveCodingEnabled"), bLiveCodingEnabled);
	Result->SetBoolField(TEXT("liveCodingStarted"), bLiveCodingStarted);
	if (!LiveCodingError.IsEmpty())
	{
		Result->SetStringField(TEXT("liveCodingError"), LiveCodingError);
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::GetEditorContext()
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	const FBlueprintExtractorModule* Module = FModuleManager::GetModulePtr<FBlueprintExtractorModule>(TEXT("BlueprintExtractor"));
	Result->SetStringField(TEXT("operation"), TEXT("get_editor_context"));
	SetSharedEditorContextFields(Result, Module);

	TArray<FString> UnsupportedSections;
	if (!CanQueryInteractiveEditorState())
	{
		AddUnsupportedSection(UnsupportedSections, TEXT("selected_asset_paths"));
		AddUnsupportedSection(UnsupportedSections, TEXT("selected_actor_names"));
		AddUnsupportedSection(UnsupportedSections, TEXT("open_asset_editors"));
	}

	TArray<FString> SelectedAssetPaths;
	CollectSelectedAssetPaths(SelectedAssetPaths);
	Result->SetArrayField(TEXT("selectedAssetPaths"), ToJsonStringArray(SelectedAssetPaths));

	TArray<FString> SelectedActorNames;
	CollectSelectedActorNames(SelectedActorNames);
	Result->SetArrayField(TEXT("selectedActorNames"), ToJsonStringArray(SelectedActorNames));

	TArray<FString> OpenAssetEditors;
	CollectOpenAssetEditors(OpenAssetEditors);
	Result->SetArrayField(TEXT("openAssetEditors"), ToJsonStringArray(OpenAssetEditors));

	const FString ActiveLevel = GetActiveLevelPath();
	if (!ActiveLevel.IsEmpty())
	{
		Result->SetStringField(TEXT("activeLevel"), ActiveLevel);
	}
	Result->SetObjectField(TEXT("pieSummary"), BuildPieSummaryJson());
	Result->SetBoolField(TEXT("partial"), UnsupportedSections.Num() > 0);
	Result->SetArrayField(TEXT("unsupportedSections"), ToJsonStringArray(UnsupportedSections));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ReadOutputLog(const FString& FilterJson)
{
	TSharedPtr<FJsonObject> ParsedFilters;
	FString ParseError;
	if (!ParseOptionalJsonObject(FilterJson, ParsedFilters, ParseError))
	{
		return MakeErrorJson(ParseError);
	}

	FString Error;
	const TSharedPtr<FJsonObject> Result = BlueprintExtractorLogAccess::ReadOutputLog(ParsedFilters, Error);
	if (!Result.IsValid())
	{
		return MakeErrorJson(Error);
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ListMessageLogListings(const FString& PayloadJson)
{
	TSharedPtr<FJsonObject> ParsedPayload;
	FString ParseError;
	if (!ParseOptionalJsonObject(PayloadJson, ParsedPayload, ParseError))
	{
		return MakeErrorJson(ParseError);
	}

	FString Error;
	const TSharedPtr<FJsonObject> Result = BlueprintExtractorLogAccess::ListMessageLogListings(ParsedPayload, Error);
	if (!Result.IsValid())
	{
		return MakeErrorJson(Error);
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ReadMessageLog(const FString& ListingName, const FString& FilterJson)
{
	TSharedPtr<FJsonObject> ParsedFilters;
	FString ParseError;
	if (!ParseOptionalJsonObject(FilterJson, ParsedFilters, ParseError))
	{
		return MakeErrorJson(ParseError);
	}

	FString Error;
	const TSharedPtr<FJsonObject> Result = BlueprintExtractorLogAccess::ReadMessageLog(ListingName, ParsedFilters, Error);
	if (!Result.IsValid())
	{
		return MakeErrorJson(Error);
	}

	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::StartPIE(const bool bSimulateInEditor)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetStringField(TEXT("operation"), TEXT("start_pie"));
	Result->SetBoolField(TEXT("simulate"), bSimulateInEditor);

	if (!GEditor)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("message"), TEXT("Editor instance is unavailable."));
		return SerializeJsonObject(Result);
	}
	if (!GUnrealEd)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("message"), TEXT("UnrealEd engine instance is unavailable."));
		return SerializeJsonObject(Result);
	}

	const bool bAlreadyPlaying = GEditor->PlayWorld != nullptr || GEditor->bIsSimulatingInEditor;
	Result->SetBoolField(TEXT("wasPlayingInEditor"), bAlreadyPlaying);
	if (bAlreadyPlaying)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetBoolField(TEXT("scheduled"), false);
		Result->SetBoolField(TEXT("isPlayingInEditor"), true);
		Result->SetStringField(TEXT("message"), TEXT("A Play-In-Editor session is already active. Stop PIE first or use relaunch_pie."));
		return SerializeJsonObject(Result);
	}

	FRequestPlaySessionParams SessionParams;
	if (bSimulateInEditor)
	{
		SessionParams.WorldType = EPlaySessionWorldType::SimulateInEditor;
	}
	FAutomationEditorCommonUtils::SetPlaySessionStartToActiveViewport(SessionParams);

	GUnrealEd->RequestPlaySession(SessionParams);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetBoolField(TEXT("scheduled"), true);
	Result->SetBoolField(TEXT("isPlayingInEditor"), GEditor->PlayWorld != nullptr || GEditor->bIsSimulatingInEditor);
	Result->SetStringField(
		TEXT("message"),
		bSimulateInEditor
			? TEXT("Simulate-In-Editor session requested.")
			: TEXT("Play-In-Editor session requested."));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::StopPIE()
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetStringField(TEXT("operation"), TEXT("stop_pie"));

	if (!GEditor)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("message"), TEXT("Editor instance is unavailable."));
		return SerializeJsonObject(Result);
	}
	if (!GUnrealEd)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("message"), TEXT("UnrealEd engine instance is unavailable."));
		return SerializeJsonObject(Result);
	}

	const bool bWasPlaying = GEditor->PlayWorld != nullptr || GEditor->bIsSimulatingInEditor;
	Result->SetBoolField(TEXT("wasPlayingInEditor"), bWasPlaying);
	if (!bWasPlaying)
	{
		Result->SetBoolField(TEXT("success"), true);
		Result->SetBoolField(TEXT("scheduled"), false);
		Result->SetBoolField(TEXT("isPlayingInEditor"), false);
		Result->SetStringField(TEXT("message"), TEXT("No active Play-In-Editor session was running."));
		return SerializeJsonObject(Result);
	}

	GUnrealEd->RequestEndPlayMap();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetBoolField(TEXT("scheduled"), true);
	Result->SetBoolField(TEXT("isPlayingInEditor"), GEditor->PlayWorld != nullptr || GEditor->bIsSimulatingInEditor);
	Result->SetStringField(TEXT("message"), TEXT("Play-In-Editor stop requested."));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::RelaunchPIE(const bool bSimulateInEditor)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetStringField(TEXT("operation"), TEXT("relaunch_pie"));
	Result->SetBoolField(TEXT("simulate"), bSimulateInEditor);

	if (!GEditor)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("message"), TEXT("Editor instance is unavailable."));
		return SerializeJsonObject(Result);
	}
	if (!GUnrealEd)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("message"), TEXT("UnrealEd engine instance is unavailable."));
		return SerializeJsonObject(Result);
	}

	const bool bWasPlaying = GEditor->PlayWorld != nullptr || GEditor->bIsSimulatingInEditor;
	Result->SetBoolField(TEXT("wasPlayingInEditor"), bWasPlaying);
	if (!bWasPlaying)
	{
		Result->SetBoolField(TEXT("success"), true);
		Result->SetBoolField(TEXT("scheduled"), false);
		Result->SetBoolField(TEXT("isPlayingInEditor"), false);
		Result->SetStringField(TEXT("message"), TEXT("No active Play-In-Editor session was running."));
		return SerializeJsonObject(Result);
	}

	GUnrealEd->RequestEndPlayMap();

	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([bSimulateInEditor](float)
		{
			if (!GEditor)
			{
				return false;
			}

			FRequestPlaySessionParams SessionParams;
			if (bSimulateInEditor)
		{
			SessionParams.WorldType = EPlaySessionWorldType::SimulateInEditor;
		}
		FAutomationEditorCommonUtils::SetPlaySessionStartToActiveViewport(SessionParams);

			GUnrealEd->RequestPlaySession(SessionParams);
			return false;
		}),
		0.1f);

	Result->SetBoolField(TEXT("success"), true);
	Result->SetBoolField(TEXT("scheduled"), true);
	Result->SetBoolField(TEXT("isPlayingInEditor"), GEditor->PlayWorld != nullptr || GEditor->bIsSimulatingInEditor);
	Result->SetStringField(
		TEXT("message"),
		bSimulateInEditor
			? TEXT("Simulate-In-Editor relaunch requested.")
			: TEXT("Play-In-Editor relaunch requested."));
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::TriggerLiveCoding(const bool bEnableForSession, const bool bWaitForCompletion)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetStringField(TEXT("operation"), TEXT("trigger_live_coding"));

#if PLATFORM_WINDOWS
	if (!FModuleManager::Get().ModuleExists(TEXT("LiveCoding")))
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetBoolField(TEXT("supported"), true);
		Result->SetBoolField(TEXT("available"), false);
		Result->SetStringField(TEXT("compileResult"), TEXT("Unavailable"));
		Result->SetStringField(TEXT("message"), TEXT("Live Coding module is not available in this editor build."));
		return SerializeJsonObject(Result);
	}

	ILiveCodingModule* LiveCodingModule = FModuleManager::LoadModulePtr<ILiveCodingModule>(TEXT("LiveCoding"));
	if (!LiveCodingModule)
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetBoolField(TEXT("supported"), true);
		Result->SetBoolField(TEXT("available"), false);
		Result->SetStringField(TEXT("compileResult"), TEXT("Unavailable"));
		Result->SetStringField(TEXT("message"), TEXT("Failed to load the Live Coding module."));
		return SerializeJsonObject(Result);
	}

	Result->SetBoolField(TEXT("supported"), true);
	Result->SetBoolField(TEXT("available"), true);
	if (bEnableForSession && !LiveCodingModule->IsEnabledForSession())
	{
		if (!LiveCodingModule->CanEnableForSession())
		{
			Result->SetBoolField(TEXT("success"), false);
			Result->SetBoolField(TEXT("enabledForSession"), false);
			Result->SetStringField(TEXT("compileResult"), TEXT("Unavailable"));
			Result->SetStringField(TEXT("message"), LiveCodingModule->GetEnableErrorText().ToString());
			return SerializeJsonObject(Result);
		}

		LiveCodingModule->EnableForSession(true);
	}

	ELiveCodingCompileResult CompileResult = ELiveCodingCompileResult::NotStarted;
	const ELiveCodingCompileFlags CompileFlags = bWaitForCompletion
		? ELiveCodingCompileFlags::WaitForCompletion
		: ELiveCodingCompileFlags::None;
	const bool bCompileRequested = LiveCodingModule->Compile(CompileFlags, &CompileResult);

	const auto CompileResultToString = [](const ELiveCodingCompileResult InResult)
	{
		switch (InResult)
		{
		case ELiveCodingCompileResult::Success: return TEXT("Success");
		case ELiveCodingCompileResult::NoChanges: return TEXT("NoChanges");
		case ELiveCodingCompileResult::InProgress: return TEXT("InProgress");
		case ELiveCodingCompileResult::CompileStillActive: return TEXT("CompileStillActive");
		case ELiveCodingCompileResult::NotStarted: return TEXT("NotStarted");
		case ELiveCodingCompileResult::Failure: return TEXT("Failure");
		case ELiveCodingCompileResult::Cancelled: return TEXT("Cancelled");
		default: return TEXT("Unknown");
		}
	};

	Result->SetBoolField(TEXT("enabledForSession"), LiveCodingModule->IsEnabledForSession());
	Result->SetBoolField(TEXT("started"), LiveCodingModule->HasStarted());
	Result->SetStringField(TEXT("compileResult"), CompileResultToString(CompileResult));

	const bool bNoChanges = CompileResult == ELiveCodingCompileResult::NoChanges;
	Result->SetBoolField(TEXT("success"),
		bCompileRequested &&
		(CompileResult == ELiveCodingCompileResult::Success
			|| bNoChanges
			|| CompileResult == ELiveCodingCompileResult::InProgress));
	Result->SetBoolField(TEXT("noOp"), bNoChanges);
	if (bNoChanges)
	{
		Result->SetStringField(TEXT("hint"),
			TEXT("Live Coding detected no source changes. If an external build already compiled .obj files, ")
			TEXT("the source timestamps may not have updated. Use build_and_restart strategy instead, or ")
			TEXT("touch the source files to update their timestamps before retrying."));
	}
	Result->SetStringField(
		TEXT("message"),
		bCompileRequested ? TEXT("Live Coding compile request completed.") : TEXT("Live Coding compile request failed to start."));
	return SerializeJsonObject(Result);
#else
	Result->SetBoolField(TEXT("success"), false);
	Result->SetBoolField(TEXT("supported"), false);
	Result->SetBoolField(TEXT("available"), false);
	Result->SetBoolField(TEXT("enabledForSession"), false);
	Result->SetStringField(TEXT("compileResult"), TEXT("Unsupported"));
	Result->SetStringField(TEXT("message"), TEXT("Live Coding automation is only supported on Windows editor builds."));
	return SerializeJsonObject(Result);
#endif
}

FString UBlueprintExtractorSubsystem::RestartEditor(const bool bWarn,
                                                    const FString& AdditionalCommandLine,
                                                    const bool bSaveDirtyAssets,
                                                    const bool bRelaunch)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("operation"), TEXT("restart_editor"));
	Result->SetBoolField(TEXT("scheduled"), true);
	Result->SetBoolField(TEXT("relaunch"), bRelaunch);
	if (!AdditionalCommandLine.IsEmpty())
	{
		Result->SetStringField(TEXT("additionalCommandLine"), AdditionalCommandLine);
	}

	if (bSaveDirtyAssets)
	{
		constexpr bool bPromptUserToSave = false;
		constexpr bool bSaveMapPackages = true;
		constexpr bool bSaveContentPackages = true;
		const bool bSaved = FEditorFileUtils::SaveDirtyPackages(
			bPromptUserToSave, bSaveMapPackages, bSaveContentPackages);
		Result->SetBoolField(TEXT("dirtyPackagesSaved"), bSaved);
	}

	if (!bRelaunch && !AdditionalCommandLine.IsEmpty())
	{
		Result->SetStringField(TEXT("additionalCommandLineNote"), TEXT("additionalCommandLine is ignored when bRelaunch is false."));
	}

	Result->SetStringField(TEXT("message"), bRelaunch ? TEXT("Editor restart scheduled.") : TEXT("Editor shutdown scheduled."));

	const FString CommandLineCopy = AdditionalCommandLine;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([bWarn, CommandLineCopy, bRelaunch](float)
		{
			if (bRelaunch)
			{
				const TOptional<FString> RestartCommandLine = CommandLineCopy.IsEmpty()
					? TOptional<FString>()
					: TOptional<FString>(CommandLineCopy);
				FUnrealEdMisc::Get().RestartEditor(bWarn, RestartCommandLine);
			}
			else
			{
				FPlatformMisc::RequestExit(false);
			}
			return false;
		}),
		0.0f);

	return SerializeJsonObject(Result);
}

// ============================================================
// StateTree Debugger
// ============================================================

FString UBlueprintExtractorSubsystem::StartStateTreeDebugger(const FString& AssetPath)
{
	if (!StateTreeDebuggerBridgeInstance)
	{
		StateTreeDebuggerBridgeInstance = MakeShared<FStateTreeDebuggerBridge>();
	}
	const TSharedPtr<FJsonObject> Result = StateTreeDebuggerBridgeInstance->Start(AssetPath);
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::StopStateTreeDebugger()
{
	if (!StateTreeDebuggerBridgeInstance)
	{
		return MakeErrorJson(TEXT("No debugger bridge instance."));
	}
	const TSharedPtr<FJsonObject> Result = StateTreeDebuggerBridgeInstance->Stop();
	return SerializeJsonObject(Result);
}

FString UBlueprintExtractorSubsystem::ReadStateTreeDebugger(const FString& PayloadJson)
{
	if (!StateTreeDebuggerBridgeInstance || !StateTreeDebuggerBridgeInstance->IsActive())
	{
		return MakeErrorJson(TEXT("No active StateTree debugger session. Call StartStateTreeDebugger first."));
	}
	const TSharedPtr<FJsonObject> Result = StateTreeDebuggerBridgeInstance->Read(PayloadJson);
	return SerializeJsonObject(Result);
}
