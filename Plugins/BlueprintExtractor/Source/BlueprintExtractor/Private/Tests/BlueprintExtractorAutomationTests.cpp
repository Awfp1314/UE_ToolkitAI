#if WITH_DEV_AUTOMATION_TESTS

#include "BlueprintExtractorSubsystem.h"
#include "BlueprintExtractorModule.h"
#include "Authoring/AssetMutationHelpers.h"

#include "AssetRegistry/AssetData.h"
#include "ContentBrowserModule.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "EdGraphSchema_K2_Actions.h"
#include "EditorFramework/AssetImportData.h"
#include "Engine/Blueprint.h"
#include "Engine/Font.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Editor.h"
#include "K2Node_CallFunction.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_FunctionEntry.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/OverlaySlot.h"
#include "Components/TextBlock.h"
#include "Components/Widget.h"
#include "Components/VerticalBoxSlot.h"
#include "Fonts/SlateFontInfo.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/Actor.h"
#include "HAL/PlatformProcess.h"
#include "IContentBrowserSingleton.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/EngineVersionComparison.h"
#include "Misc/Guid.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "WidgetBlueprint.h"

namespace BlueprintExtractorAutomation
{

static constexpr TCHAR ScratchRoot[] = TEXT("/Game/__GeneratedTests__");
static constexpr TCHAR DefaultMaterialPath[] = TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial");
static constexpr TCHAR WorldGridMaterialPath[] = TEXT("/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial");
static constexpr TCHAR DefaultTexturePath[] = TEXT("/Engine/EngineResources/DefaultTexture.DefaultTexture");
static constexpr TCHAR EngineSkeletonPath[] = TEXT("/Engine/EngineMeshes/SkeletalCube_Skeleton.SkeletalCube_Skeleton");
static constexpr TCHAR EnginePreviewMeshPath[] = TEXT("/Engine/EngineMeshes/SkeletalCube.SkeletalCube");
static constexpr TCHAR StateTreeSchemaPath[] = TEXT("/Script/GameplayStateTreeModule.StateTreeComponentSchema");
static constexpr TCHAR FixtureDataAssetClassPath[] = TEXT("/Script/BlueprintExtractorFixture.BlueprintExtractorFixtureDataAsset");
static constexpr TCHAR FixtureInlineObjectClassPath[] = TEXT("/Script/BlueprintExtractorFixture.BlueprintExtractorFixtureInlineObject");
static constexpr TCHAR FixtureRowStructPath[] = TEXT("/Script/BlueprintExtractorFixture.BlueprintExtractorFixtureRow");
static constexpr TCHAR FixtureBindWidgetParentClassPath[] = TEXT("/Script/BlueprintExtractorFixture.BlueprintExtractorFixtureBindWidgetParent");
static constexpr TCHAR FixtureRenameBindWidgetParentClassPath[] = TEXT("/Script/BlueprintExtractorFixture.BlueprintExtractorFixtureRenameBindWidgetParent");
static constexpr TCHAR FixtureStyledWidgetParentClassPath[] = TEXT("/Script/BlueprintExtractorFixture.BlueprintExtractorFixtureStyledWidgetParent");
static constexpr TCHAR TextureImportSource[] = TEXT("ImportSources/T_Test.png");
static constexpr TCHAR TextureImportSourceAlt[] = TEXT("ImportSources/T_Test_Alt.png");
static constexpr TCHAR MeshImportSource[] = TEXT("ImportSources/SM_Test.obj");

static FString MakeUniqueAssetPath(const FString& Prefix)
{
	return FString::Printf(
		TEXT("%s/%s_%s"),
		ScratchRoot,
		*Prefix,
		*FGuid::NewGuid().ToString(EGuidFormats::Digits));
}

static FString MakeObjectPath(const FString& AssetPath)
{
	return FString::Printf(
		TEXT("%s.%s"),
		*AssetPath,
		*FPackageName::GetLongPackageAssetName(AssetPath));
}

static UClass* ResolveFixtureClass(const TCHAR* ClassPath)
{
	if (UClass* ExistingClass = FindObject<UClass>(nullptr, ClassPath))
	{
		return ExistingClass;
	}

	return LoadClass<UObject>(nullptr, ClassPath);
}

static bool ReparentWidgetBlueprintForTest(FAutomationTestBase& Test,
                                           const FString& WidgetObjectPath,
                                           const TCHAR* ParentClassPath)
{
	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Widget blueprint exists for test reparent"), WidgetBP);
	if (!WidgetBP)
	{
		return false;
	}

	UClass* ParentClass = ResolveFixtureClass(ParentClassPath);
	Test.TestNotNull(TEXT("Fixture parent class resolves for test reparent"), ParentClass);
	if (!ParentClass)
	{
		return false;
	}

	WidgetBP->Modify();
	WidgetBP->ParentClass = ParentClass;
	if (WidgetBP->SimpleConstructionScript)
	{
		WidgetBP->SimpleConstructionScript->ValidateSceneRootNodes();
	}

	FBlueprintEditorUtils::RefreshAllNodes(WidgetBP);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBP);
	return true;
}

static FString MakePackageFilename(const FString& AssetPath)
{
	return FPackageName::LongPackageNameToFilename(
		AssetPath,
		FPackageName::GetAssetPackageExtension());
}

static FString FindSystemFontFile()
{
	const FString WindowsFontsDir = FPaths::Combine(FPlatformMisc::GetEnvironmentVariable(TEXT("WINDIR")), TEXT("Fonts"));
	const TArray<FString> Candidates = {
		FPaths::Combine(WindowsFontsDir, TEXT("arial.ttf")),
		FPaths::Combine(WindowsFontsDir, TEXT("arialbd.ttf")),
		FPaths::Combine(WindowsFontsDir, TEXT("tahoma.ttf")),
		FPaths::Combine(WindowsFontsDir, TEXT("tahomabd.ttf")),
		FPaths::Combine(WindowsFontsDir, TEXT("segoeui.ttf")),
		FPaths::Combine(WindowsFontsDir, TEXT("seguisb.ttf")),
	};

	for (const FString& Candidate : Candidates)
	{
		if (FPaths::FileExists(Candidate))
		{
			return Candidate;
		}
	}

	return FString();
}

static FString SerializeStringArray(const TArray<FString>& Values)
{
	TArray<TSharedPtr<FJsonValue>> JsonValues;
	for (const FString& Value : Values)
	{
		JsonValues.Add(MakeShared<FJsonValueString>(Value));
	}

	FString Output;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Output);
	FJsonSerializer::Serialize(JsonValues, Writer);
	return Output;
}

static TSharedPtr<FJsonObject> ParseJsonObject(FAutomationTestBase& Test,
                                               const FString& RawJson,
                                               const FString& Context)
{
	TSharedPtr<FJsonObject> Parsed;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RawJson);
	Test.TestTrue(*FString::Printf(TEXT("%s returns valid JSON"), *Context), FJsonSerializer::Deserialize(Reader, Parsed) && Parsed.IsValid());
	return Parsed;
}

static bool HasErrorField(const TSharedPtr<FJsonObject>& Parsed)
{
	FString Error;
	return Parsed.IsValid() && Parsed->TryGetStringField(TEXT("error"), Error) && !Error.IsEmpty();
}

static bool IsFailureResult(const TSharedPtr<FJsonObject>& Parsed)
{
	if (!Parsed.IsValid())
	{
		return false;
	}

	if (HasErrorField(Parsed))
	{
		return true;
	}

	return Parsed->HasTypedField<EJson::Boolean>(TEXT("success"))
		&& !Parsed->GetBoolField(TEXT("success"));
}

static TSharedPtr<FJsonObject> ExpectSuccessfulResult(FAutomationTestBase& Test,
                                                      const FString& RawJson,
                                                      const FString& Context)
{
	const TSharedPtr<FJsonObject> Parsed = ParseJsonObject(Test, RawJson, Context);
	if (!Parsed.IsValid())
	{
		return nullptr;
	}

	FString Error;
	const bool bHasError = Parsed->TryGetStringField(TEXT("error"), Error) && !Error.IsEmpty();
	if (bHasError)
	{
		Test.AddInfo(FString::Printf(TEXT("%s returned error payload: %s"), *Context, *RawJson));
	}
	Test.TestFalse(*FString::Printf(TEXT("%s has no error payload"), *Context), bHasError);

	bool bSuccess = true;
	if (Parsed->HasTypedField<EJson::Boolean>(TEXT("success")))
	{
		bSuccess = Parsed->GetBoolField(TEXT("success"));
	}
	if (!bSuccess)
	{
		Test.AddInfo(FString::Printf(TEXT("%s returned failure payload: %s"), *Context, *RawJson));
	}
	Test.TestTrue(*FString::Printf(TEXT("%s succeeded"), *Context), bSuccess);
	return Parsed;
}

static bool ExpectValidateOnlyResult(FAutomationTestBase& Test,
                                     const FString& RawJson,
                                     const FString& Context)
{
	const TSharedPtr<FJsonObject> Parsed = ExpectSuccessfulResult(Test, RawJson, Context);
	if (!Parsed.IsValid())
	{
		return false;
	}

	if (Parsed->HasTypedField<EJson::Boolean>(TEXT("validateOnly")))
	{
		Test.TestTrue(*FString::Printf(TEXT("%s sets validateOnly"), *Context), Parsed->GetBoolField(TEXT("validateOnly")));
	}

	const TArray<TSharedPtr<FJsonValue>>* DirtyPackages = nullptr;
	if (Parsed->TryGetArrayField(TEXT("dirtyPackages"), DirtyPackages) && DirtyPackages)
	{
		Test.TestEqual(*FString::Printf(TEXT("%s leaves no dirty packages"), *Context), DirtyPackages->Num(), 0);
	}

	return true;
}

static TSharedPtr<FJsonObject> ExpectFailureResult(FAutomationTestBase& Test,
                                                   const FString& RawJson,
                                                   const FString& Context)
{
	const TSharedPtr<FJsonObject> Parsed = ParseJsonObject(Test, RawJson, Context);
	if (!Parsed.IsValid())
	{
		return nullptr;
	}

	FString Error;
	const bool bHasErrorString = Parsed->TryGetStringField(TEXT("error"), Error) && !Error.IsEmpty();

	const TArray<TSharedPtr<FJsonValue>>* ErrorsArray = nullptr;
	const bool bHasErrorsArray = Parsed->TryGetArrayField(TEXT("errors"), ErrorsArray) && ErrorsArray != nullptr && ErrorsArray->Num() > 0;

	const TArray<TSharedPtr<FJsonValue>>* DiagnosticsArray = nullptr;
	const bool bHasDiagnosticsArray = Parsed->TryGetArrayField(TEXT("diagnostics"), DiagnosticsArray) && DiagnosticsArray != nullptr && DiagnosticsArray->Num() > 0;

	bool bValidationFailed = false;
	const TSharedPtr<FJsonObject>* ValidationObject = nullptr;
	if (Parsed->TryGetObjectField(TEXT("validation"), ValidationObject) && ValidationObject != nullptr && ValidationObject->IsValid())
	{
		bool bValidationSuccess = true;
		if ((*ValidationObject)->TryGetBoolField(TEXT("success"), bValidationSuccess))
		{
			bValidationFailed = !bValidationSuccess;
		}
	}

	const bool bHasStructuredFailure = bHasErrorString || bHasErrorsArray || bHasDiagnosticsArray || bValidationFailed;
	if (bHasStructuredFailure)
	{
		Test.AddInfo(FString::Printf(TEXT("%s returned error payload: %s"), *Context, *RawJson));
	}
	Test.TestTrue(*FString::Printf(TEXT("%s returns a structured failure payload"), *Context), bHasStructuredFailure);

	bool bSuccess = true;
	if (Parsed->HasTypedField<EJson::Boolean>(TEXT("success")))
	{
		bSuccess = Parsed->GetBoolField(TEXT("success"));
	}
	Test.TestFalse(*FString::Printf(TEXT("%s fails as expected"), *Context), bSuccess);
	return Parsed;
}

static TSharedPtr<FJsonObject> WaitForImportJob(FAutomationTestBase& Test,
                                                UBlueprintExtractorSubsystem* Subsystem,
                                                const FString& InitialJson,
                                                const FString& Context,
                                                FString* OutJobId = nullptr)
{
	const TSharedPtr<FJsonObject> Initial = ParseJsonObject(Test, InitialJson, Context + TEXT(" enqueue"));
	if (!Initial.IsValid())
	{
		return nullptr;
	}

	FString JobId;
	Test.TestTrue(*FString::Printf(TEXT("%s returns a jobId"), *Context), Initial->TryGetStringField(TEXT("jobId"), JobId) && !JobId.IsEmpty());
	if (OutJobId)
	{
		*OutJobId = JobId;
	}

	bool bTerminal = false;
	if (Initial->TryGetBoolField(TEXT("terminal"), bTerminal) && bTerminal)
	{
		return Initial;
	}

	for (int32 PollIndex = 0; PollIndex < 300; ++PollIndex)
	{
		FPlatformProcess::Sleep(0.1f);
		const TSharedPtr<FJsonObject> Polled = ParseJsonObject(
			Test,
			Subsystem->GetImportJob(JobId),
			Context + TEXT(" poll"));
		if (!Polled.IsValid())
		{
			return nullptr;
		}

		if (IsFailureResult(Polled))
		{
			return Polled;
		}

		if (Polled->TryGetBoolField(TEXT("terminal"), bTerminal) && bTerminal)
		{
			return Polled;
		}
	}

	Test.AddError(FString::Printf(TEXT("%s did not complete within polling window"), *Context));
	return nullptr;
}

static bool JsonArrayContainsString(const TSharedPtr<FJsonObject>& Parsed,
                                    const FString& FieldName,
                                    const FString& ExpectedValue)
{
	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Parsed.IsValid() || !Parsed->TryGetArrayField(FieldName, Values) || !Values)
	{
		return false;
	}

	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		if (Value.IsValid() && Value->AsString() == ExpectedValue)
		{
			return true;
		}
	}

	return false;
}

static bool TryGetObjectFieldCopy(const TSharedPtr<FJsonObject>& Parsed,
                                  const TCHAR* FieldName,
                                  TSharedPtr<FJsonObject>& OutObject)
{
	if (!Parsed.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* FieldObject = nullptr;
	if (Parsed->TryGetObjectField(FieldName, FieldObject) && FieldObject && FieldObject->IsValid())
	{
		OutObject = *FieldObject;
		return true;
	}

	return false;
}

static FString SerializeJsonObjectForSearch(const TSharedPtr<FJsonObject>& Parsed)
{
	if (!Parsed.IsValid())
	{
		return FString();
	}

	FString Output;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Output);
	FJsonSerializer::Serialize(Parsed.ToSharedRef(), Writer);
	return Output;
}

static TSharedPtr<FJsonObject> FindArrayObjectByStringField(const TSharedPtr<FJsonObject>& Parsed,
                                                            const TCHAR* ArrayField,
                                                            const TCHAR* ValueField,
                                                            const FString& ExpectedValue)
{
	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Parsed.IsValid() || !Parsed->TryGetArrayField(ArrayField, Values) || !Values)
	{
		return nullptr;
	}

	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		const TSharedPtr<FJsonObject> ValueObject = Value.IsValid() ? Value->AsObject() : nullptr;
		FString CandidateValue;
		if (ValueObject.IsValid() && ValueObject->TryGetStringField(ValueField, CandidateValue) && CandidateValue == ExpectedValue)
		{
			return ValueObject;
		}
	}

	return nullptr;
}

static TSharedPtr<FJsonObject> FindWidgetNodeByPath(const TSharedPtr<FJsonObject>& Node,
                                                    const FString& TargetPath,
                                                    const FString& ParentPath = FString())
{
	if (!Node.IsValid())
	{
		return nullptr;
	}

	FString NodeName;
	Node->TryGetStringField(TEXT("name"), NodeName);
	const FString NodePath = ParentPath.IsEmpty() ? NodeName : ParentPath + TEXT("/") + NodeName;
	if (NodePath == TargetPath)
	{
		return Node;
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (!Node->TryGetArrayField(TEXT("children"), Children) || !Children)
	{
		return nullptr;
	}

	for (const TSharedPtr<FJsonValue>& ChildValue : *Children)
	{
		const TSharedPtr<FJsonObject> ChildObject = ChildValue.IsValid() ? ChildValue->AsObject() : nullptr;
		if (const TSharedPtr<FJsonObject> Found = FindWidgetNodeByPath(ChildObject, TargetPath, NodePath))
		{
			return Found;
		}
	}

	return nullptr;
}

static TSharedPtr<FJsonObject> FindStateTreeStateByPath(const TSharedPtr<FJsonObject>& StateObject,
                                                        const FString& TargetPath)
{
	if (!StateObject.IsValid())
	{
		return nullptr;
	}

	FString StatePath;
	if (StateObject->TryGetStringField(TEXT("statePath"), StatePath) && StatePath == TargetPath)
	{
		return StateObject;
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (!StateObject->TryGetArrayField(TEXT("children"), Children) || !Children)
	{
		return nullptr;
	}

	for (const TSharedPtr<FJsonValue>& ChildValue : *Children)
	{
		const TSharedPtr<FJsonObject> ChildObject = ChildValue.IsValid() ? ChildValue->AsObject() : nullptr;
		if (const TSharedPtr<FJsonObject> Found = FindStateTreeStateByPath(ChildObject, TargetPath))
		{
			return Found;
		}
	}

	return nullptr;
}

static TSharedPtr<FJsonObject> FindExtractedStateTreeStateByPath(const TSharedPtr<FJsonObject>& ExtractResult,
                                                                 const FString& TargetPath)
{
	TSharedPtr<FJsonObject> StateTreeJson;
	if (!TryGetObjectFieldCopy(ExtractResult, TEXT("stateTree"), StateTreeJson))
	{
		return nullptr;
	}

	const TArray<TSharedPtr<FJsonValue>>* States = nullptr;
	if (!StateTreeJson->TryGetArrayField(TEXT("states"), States) || !States)
	{
		return nullptr;
	}

	for (const TSharedPtr<FJsonValue>& StateValue : *States)
	{
		const TSharedPtr<FJsonObject> StateObject = StateValue.IsValid() ? StateValue->AsObject() : nullptr;
		if (const TSharedPtr<FJsonObject> Found = FindStateTreeStateByPath(StateObject, TargetPath))
		{
			return Found;
		}
	}

	return nullptr;
}

static TSharedPtr<FJsonObject> GetFirstTransitionTargetState(const TSharedPtr<FJsonObject>& StateObject)
{
	if (!StateObject.IsValid())
	{
		return nullptr;
	}

	const TArray<TSharedPtr<FJsonValue>>* Transitions = nullptr;
	if (!StateObject->TryGetArrayField(TEXT("transitions"), Transitions) || !Transitions || Transitions->Num() == 0)
	{
		return nullptr;
	}

	const TSharedPtr<FJsonObject> TransitionObject = (*Transitions)[0].IsValid() ? (*Transitions)[0]->AsObject() : nullptr;
	TSharedPtr<FJsonObject> TargetStateObject;
	return TryGetObjectFieldCopy(TransitionObject, TEXT("targetState"), TargetStateObject) ? TargetStateObject : nullptr;
}

static UEdGraph* FindFunctionGraphByName(UBlueprint* Blueprint, const FName GraphName)
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

static UK2Node_FunctionEntry* FindFunctionEntryNodeInGraph(UEdGraph* Graph)
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

static UEdGraphPin* FindNodePinByName(UEdGraphNode* Node, const FString& PinName)
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

static bool SeedSequenceInitializerGraph(FAutomationTestBase& Test,
                                         UBlueprint* Blueprint,
                                         const FString& GraphName)
{
	if (!Blueprint)
	{
		Test.AddError(TEXT("Cannot seed a sequence graph on a null Blueprint."));
		return false;
	}

	UEdGraph* TargetGraph = FindFunctionGraphByName(Blueprint, FName(*GraphName));
	Test.TestNotNull(TEXT("Target function graph exists for sequence seeding"), TargetGraph);
	if (!TargetGraph)
	{
		return false;
	}

	UK2Node_FunctionEntry* EntryNode = FindFunctionEntryNodeInGraph(TargetGraph);
	Test.TestNotNull(TEXT("Target function graph exposes a function entry node"), EntryNode);
	if (!EntryNode)
	{
		return false;
	}

	UK2Node_ExecutionSequence* SequenceNode = FEdGraphSchemaAction_K2NewNode::SpawnNode<UK2Node_ExecutionSequence>(
		TargetGraph,
		FVector2D(320.0f, 0.0f),
		EK2NewNodeFlags::None,
		[](UK2Node_ExecutionSequence*) {});
	Test.TestNotNull(TEXT("Sequence node is spawned for initializer coverage"), SequenceNode);
	if (!SequenceNode)
	{
		return false;
	}

	UEdGraphPin* EntryThenPin = FindNodePinByName(EntryNode, TEXT("then"));
	UEdGraphPin* SequenceExecutePin = FindNodePinByName(SequenceNode, TEXT("execute"));
	Test.TestNotNull(TEXT("Initializer entry exposes then pin"), EntryThenPin);
	Test.TestNotNull(TEXT("Sequence node exposes execute pin"), SequenceExecutePin);
	if (!EntryThenPin || !SequenceExecutePin)
	{
		return false;
	}

	const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
	const bool bConnected = Schema && Schema->TryCreateConnection(EntryThenPin, SequenceExecutePin);
	Test.TestTrue(TEXT("Initializer entry is wired into the sequence node"), bConnected);
	if (!bConnected)
	{
		return false;
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	return true;
}

static UBlueprintExtractorSubsystem* GetSubsystem(FAutomationTestBase& Test)
{
	Test.TestNotNull(TEXT("GEditor is available"), GEditor);
	return GEditor ? GEditor->GetEditorSubsystem<UBlueprintExtractorSubsystem>() : nullptr;
}

static bool RunValidateOnlyCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateBlueprint(
			MakeUniqueAssetPath(TEXT("BP_Validate")),
			TEXT("/Script/Engine.Actor"),
			TEXT("{}"),
			true),
		TEXT("CreateBlueprint validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateDataAsset(
			MakeUniqueAssetPath(TEXT("DA_Validate")),
			FixtureDataAssetClassPath,
			TEXT(R"json({"Count":3})json"),
			true),
		TEXT("CreateDataAsset validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateDataTable(
			MakeUniqueAssetPath(TEXT("DT_Validate")),
			FixtureRowStructPath,
			TEXT(R"json([{"rowName":"Default","values":{"Count":1}}])json"),
			true),
		TEXT("CreateDataTable validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateCurve(
			MakeUniqueAssetPath(TEXT("C_Validate")),
			TEXT("Float"),
			TEXT("{}"),
			true),
		TEXT("CreateCurve validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateCurveTable(
			MakeUniqueAssetPath(TEXT("CT_Validate")),
			TEXT("SimpleCurves"),
			TEXT("[]"),
			true),
		TEXT("CreateCurveTable validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateMaterialInstance(
			MakeUniqueAssetPath(TEXT("MI_Validate")),
			DefaultMaterialPath,
			true),
		TEXT("CreateMaterialInstance validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateMaterial(
			MakeUniqueAssetPath(TEXT("M_Validate")),
			DefaultTexturePath,
			TEXT(R"json({"twoSided":true,"blendMode":"BLEND_Opaque"})json"),
			true),
		TEXT("CreateMaterial validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateMaterialFunction(
			MakeUniqueAssetPath(TEXT("MF_Validate")),
			TEXT("function"),
			TEXT(R"json({"description":"Validate function"})json"),
			true),
		TEXT("CreateMaterialFunction validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateMaterialFunction(
			MakeUniqueAssetPath(TEXT("MFL_Validate")),
			TEXT("layer"),
			TEXT("{}"),
			true),
		TEXT("CreateMaterialLayer validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateMaterialFunction(
			MakeUniqueAssetPath(TEXT("MFLB_Validate")),
			TEXT("layer_blend"),
			TEXT("{}"),
			true),
		TEXT("CreateMaterialLayerBlend validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateUserDefinedStruct(
			MakeUniqueAssetPath(TEXT("S_Validate")),
			TEXT(R"json({"fields":[{"name":"Count","pinType":{"category":"int"}}]})json"),
			true),
		TEXT("CreateUserDefinedStruct validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateUserDefinedEnum(
			MakeUniqueAssetPath(TEXT("E_Validate")),
			TEXT(R"json({"entries":[{"name":"Alpha"},{"name":"Beta"}]})json"),
			true),
		TEXT("CreateUserDefinedEnum validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateBlackboard(
			MakeUniqueAssetPath(TEXT("BB_Validate")),
			TEXT(R"json({"keys":[{"entryName":"TargetActor","keyTypePath":"/Script/AIModule.BlackboardKeyType_Object","baseClass":"/Script/Engine.Actor"}]})json"),
			true),
		TEXT("CreateBlackboard validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateBehaviorTree(
			MakeUniqueAssetPath(TEXT("BT_Validate")),
			TEXT("{}"),
			true),
		TEXT("CreateBehaviorTree validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateStateTree(
			MakeUniqueAssetPath(TEXT("ST_Validate")),
			FString::Printf(TEXT(R"json({"schemaClassPath":"%s"})json"), StateTreeSchemaPath),
			true),
		TEXT("CreateStateTree validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateAnimSequence(
			MakeUniqueAssetPath(TEXT("AS_Validate")),
			FString::Printf(TEXT(R"json({"skeleton":"%s","previewMesh":"%s"})json"), EngineSkeletonPath, EnginePreviewMeshPath),
			true),
		TEXT("CreateAnimSequence validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateAnimMontage(
			MakeUniqueAssetPath(TEXT("AM_Validate")),
			FString::Printf(TEXT(R"json({"skeleton":"%s","previewMesh":"%s"})json"), EngineSkeletonPath, EnginePreviewMeshPath),
			true),
		TEXT("CreateAnimMontage validate_only"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateBlendSpace(
			MakeUniqueAssetPath(TEXT("BS_Validate")),
			FString::Printf(TEXT(R"json({"skeleton":"%s","previewMesh":"%s","is1D":true,"axisX":{"name":"Speed","min":0.0,"max":600.0,"gridDivisions":4}})json"), EngineSkeletonPath, EnginePreviewMeshPath),
			true),
		TEXT("CreateBlendSpace validate_only"));

	const TSharedPtr<FJsonObject> ProjectContext = ExpectSuccessfulResult(
		Test,
		Subsystem->GetProjectAutomationContext(),
		TEXT("GetProjectAutomationContext"));
	if (ProjectContext.IsValid())
	{
		FString InstanceId;
		double ProcessId = 0.0;
		double RemoteControlPort = 0.0;
		FString RemoteControlHost;
		FString EngineVersion;
		FString LastSeenAt;
		Test.TestTrue(TEXT("Project automation context returns instanceId"), ProjectContext->TryGetStringField(TEXT("instanceId"), InstanceId) && !InstanceId.IsEmpty());
		Test.TestTrue(TEXT("Project automation context returns processId"), ProjectContext->TryGetNumberField(TEXT("processId"), ProcessId) && ProcessId > 0.0);
		Test.TestTrue(TEXT("Project automation context returns remoteControlHost"), ProjectContext->TryGetStringField(TEXT("remoteControlHost"), RemoteControlHost) && !RemoteControlHost.IsEmpty());
		Test.TestTrue(TEXT("Project automation context returns remoteControlPort"), ProjectContext->TryGetNumberField(TEXT("remoteControlPort"), RemoteControlPort) && RemoteControlPort > 0.0);
		Test.TestTrue(TEXT("Project automation context returns engineVersion"), ProjectContext->TryGetStringField(TEXT("engineVersion"), EngineVersion) && !EngineVersion.IsEmpty());
		Test.TestTrue(TEXT("Project automation context returns lastSeenAt"), ProjectContext->TryGetStringField(TEXT("lastSeenAt"), LastSeenAt) && !LastSeenAt.IsEmpty());
		Test.TestTrue(TEXT("Project automation context reports isPlayingInEditor"), ProjectContext->HasTypedField<EJson::Boolean>(TEXT("isPlayingInEditor")));
		bool bIsPlayingInEditor = true;
		Test.TestTrue(TEXT("Project automation context is not playing in editor during headless tests"), ProjectContext->TryGetBoolField(TEXT("isPlayingInEditor"), bIsPlayingInEditor) && !bIsPlayingInEditor);

		if (const FBlueprintExtractorModule* Module = FModuleManager::GetModulePtr<FBlueprintExtractorModule>(TEXT("BlueprintExtractor")))
		{
			Test.TestTrue(TEXT("BlueprintExtractor module registry file exists"), FPaths::FileExists(Module->GetRegistryFilePath()));
			Test.TestEqual(TEXT("Project automation context instanceId matches module"), InstanceId, Module->GetEditorInstanceId());
		}
	}

	return true;
}

static bool RunProjectControlCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	if (!FApp::CanEverRender() || !FSlateApplication::IsInitialized())
	{
		Test.AddInfo(TEXT("Skipping PIE/project-control coverage because rendering is unavailable. Run this filter without -NullRHI."));
		return true;
	}

	const TSharedPtr<FJsonObject> StartResult = ExpectSuccessfulResult(
		Test,
		Subsystem->StartPIE(),
		TEXT("StartPIE"));
	if (!StartResult.IsValid())
	{
		return false;
	}

	bool bScheduled = false;
	bool bSimulate = true;
	Test.TestTrue(TEXT("StartPIE reports scheduled"), StartResult->TryGetBoolField(TEXT("scheduled"), bScheduled) && bScheduled);
	Test.TestTrue(TEXT("StartPIE reports simulate=false by default"), StartResult->TryGetBoolField(TEXT("simulate"), bSimulate) && !bSimulate);

	const TSharedPtr<FJsonObject> StopResult = ExpectSuccessfulResult(
		Test,
		Subsystem->StopPIE(),
		TEXT("StopPIE"));
	if (!StopResult.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> RelaunchResult = ExpectSuccessfulResult(
		Test,
		Subsystem->RelaunchPIE(),
		TEXT("RelaunchPIE"));
	if (!RelaunchResult.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> EditorScreenshot = ExpectSuccessfulResult(
		Test,
		Subsystem->CaptureEditorScreenshot(),
		TEXT("CaptureEditorScreenshot"));
	if (!EditorScreenshot.IsValid())
	{
		return false;
	}

	FString CaptureType;
	FString ArtifactPath;
	Test.TestTrue(TEXT("Editor screenshot reports capture type"), EditorScreenshot->TryGetStringField(TEXT("captureType"), CaptureType) && CaptureType == TEXT("editor_screenshot"));
	Test.TestTrue(TEXT("Editor screenshot returns an artifact path"), EditorScreenshot->TryGetStringField(TEXT("artifactPath"), ArtifactPath) && !ArtifactPath.IsEmpty());
	Test.TestTrue(TEXT("Editor screenshot artifact exists"), FPaths::FileExists(ArtifactPath));

	const FString RuntimeScreenshotJson = Subsystem->CaptureRuntimeScreenshot();
	const TSharedPtr<FJsonObject> RuntimeScreenshot = ParseJsonObject(Test, RuntimeScreenshotJson, TEXT("CaptureRuntimeScreenshot without active PIE"));
	if (!RuntimeScreenshot.IsValid())
	{
		return false;
	}

	FString RuntimeError;
	Test.TestTrue(TEXT("Runtime screenshot fails cleanly when PIE is inactive"), RuntimeScreenshot->TryGetStringField(TEXT("error"), RuntimeError) && RuntimeError.Contains(TEXT("active PIE session")));

	return true;
}

static bool RunEditorContextCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const TSharedPtr<FJsonObject> HeadlessContext = ExpectSuccessfulResult(
		Test,
		Subsystem->GetEditorContext(),
		TEXT("GetEditorContext"));
	if (!HeadlessContext.IsValid())
	{
		return false;
	}

	Test.TestTrue(TEXT("Editor context returns instanceId"), HeadlessContext->HasTypedField<EJson::String>(TEXT("instanceId")));
	Test.TestTrue(TEXT("Editor context returns projectFilePath"), HeadlessContext->HasTypedField<EJson::String>(TEXT("projectFilePath")));
	Test.TestTrue(TEXT("Editor context returns selectedAssetPaths array"), HeadlessContext->HasTypedField<EJson::Array>(TEXT("selectedAssetPaths")));
	Test.TestTrue(TEXT("Editor context returns selectedActorNames array"), HeadlessContext->HasTypedField<EJson::Array>(TEXT("selectedActorNames")));
	Test.TestTrue(TEXT("Editor context returns openAssetEditors array"), HeadlessContext->HasTypedField<EJson::Array>(TEXT("openAssetEditors")));
	Test.TestTrue(TEXT("Editor context returns pieSummary object"), HeadlessContext->HasTypedField<EJson::Object>(TEXT("pieSummary")));

	if (!FApp::CanEverRender() || !FSlateApplication::IsInitialized())
	{
		bool bPartial = false;
		Test.TestTrue(TEXT("Headless editor context reports partial=true"), HeadlessContext->TryGetBoolField(TEXT("partial"), bPartial) && bPartial);
		Test.TestTrue(TEXT("Headless editor context marks selected_asset_paths unsupported"), JsonArrayContainsString(HeadlessContext, TEXT("unsupportedSections"), TEXT("selected_asset_paths")));
		Test.TestTrue(TEXT("Headless editor context marks selected_actor_names unsupported"), JsonArrayContainsString(HeadlessContext, TEXT("unsupportedSections"), TEXT("selected_actor_names")));
		Test.TestTrue(TEXT("Headless editor context marks open_asset_editors unsupported"), JsonArrayContainsString(HeadlessContext, TEXT("unsupportedSections"), TEXT("open_asset_editors")));
		return true;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_EditorContext"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);
	const TSharedPtr<FJsonObject> CreateWidgetResult = ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(WidgetAssetPath, TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint editor context"));
	if (!CreateWidgetResult.IsValid())
	{
		return false;
	}

	UWidgetBlueprint* WidgetBlueprint = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetAssetPath));
	if (!WidgetBlueprint)
	{
		Test.AddError(TEXT("Editor context coverage failed to resolve the created widget blueprint."));
		return false;
	}

	UAssetEditorSubsystem* AssetEditorSubsystem = GEditor ? GEditor->GetEditorSubsystem<UAssetEditorSubsystem>() : nullptr;
	if (!AssetEditorSubsystem)
	{
		Test.AddError(TEXT("Editor context coverage requires UAssetEditorSubsystem."));
		return false;
	}

	AssetEditorSubsystem->OpenEditorForAsset(WidgetBlueprint);

	FContentBrowserModule& ContentBrowserModule = FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));
	TArray<FAssetData> AssetsToSync;
	AssetsToSync.Add(FAssetData(WidgetBlueprint));
	ContentBrowserModule.Get().SyncBrowserToAssets(AssetsToSync);

	UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!EditorWorld)
	{
		Test.AddError(TEXT("Editor context coverage requires an editor world."));
		return false;
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.Name = MakeUniqueObjectName(EditorWorld, AActor::StaticClass(), TEXT("BPEditorContextActor"));
	SpawnParams.ObjectFlags |= RF_Transient;
	AActor* SelectedActor = EditorWorld->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, SpawnParams);
	if (!SelectedActor)
	{
		Test.AddError(TEXT("Editor context coverage failed to spawn an actor for selection."));
		return false;
	}

	GEditor->SelectNone(false, true, false);
	GEditor->SelectActor(SelectedActor, true, true, true);
	FPlatformProcess::Sleep(0.1f);
	const FString SelectedActorName = SelectedActor->GetActorNameOrLabel();

	const TSharedPtr<FJsonObject> InteractiveContext = ExpectSuccessfulResult(
		Test,
		Subsystem->GetEditorContext(),
		TEXT("GetEditorContext interactive"));

	GEditor->SelectActor(SelectedActor, false, true, true);
	EditorWorld->DestroyActor(SelectedActor);
	AssetEditorSubsystem->CloseAllEditorsForAsset(WidgetBlueprint);

	if (!InteractiveContext.IsValid())
	{
		return false;
	}

	bool bPartial = true;
	Test.TestTrue(TEXT("Interactive editor context reports partial=false"), InteractiveContext->TryGetBoolField(TEXT("partial"), bPartial) && !bPartial);
	Test.TestTrue(TEXT("Interactive editor context returns the selected asset package path"), JsonArrayContainsString(InteractiveContext, TEXT("selectedAssetPaths"), WidgetAssetPath));
	Test.TestTrue(TEXT("Interactive editor context returns the selected actor name"), JsonArrayContainsString(InteractiveContext, TEXT("selectedActorNames"), SelectedActorName));
	Test.TestTrue(TEXT("Interactive editor context returns the open widget editor object path"), JsonArrayContainsString(InteractiveContext, TEXT("openAssetEditors"), WidgetObjectPath));

	FString ActiveLevel;
	Test.TestTrue(TEXT("Interactive editor context returns activeLevel"), InteractiveContext->TryGetStringField(TEXT("activeLevel"), ActiveLevel) && !ActiveLevel.IsEmpty());

	TSharedPtr<FJsonObject> PieSummary;
	Test.TestTrue(TEXT("Interactive editor context exposes pieSummary"), TryGetObjectFieldCopy(InteractiveContext, TEXT("pieSummary"), PieSummary) && PieSummary.IsValid());
	if (PieSummary.IsValid())
	{
		bool bIsPlayingInEditor = true;
		Test.TestTrue(TEXT("Interactive editor context reports PIE inactive"), PieSummary->TryGetBoolField(TEXT("isPlayingInEditor"), bIsPlayingInEditor) && !bIsPlayingInEditor);
	}

	return true;
}

static bool RunEditorLogCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const TSharedPtr<FJsonObject> OutputLogResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ReadOutputLog(TEXT("{\"limit\":25,\"reverse\":true}")),
		TEXT("ReadOutputLog"));
	if (!OutputLogResult.IsValid())
	{
		return false;
	}

	Test.TestTrue(TEXT("Output log returns bufferedCount"), OutputLogResult->HasTypedField<EJson::Number>(TEXT("bufferedCount")));
	Test.TestTrue(TEXT("Output log returns entries array"), OutputLogResult->HasTypedField<EJson::Array>(TEXT("entries")));

	const TSharedPtr<FJsonObject> ListingsResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ListMessageLogListings(TEXT("{\"candidate_names\":[\"PIE\",\"MapCheck\"],\"include_unregistered\":true}")),
		TEXT("ListMessageLogListings"));
	if (!ListingsResult.IsValid())
	{
		return false;
	}

	Test.TestTrue(TEXT("Message log listing probe returns candidateCount"), ListingsResult->HasTypedField<EJson::Number>(TEXT("candidateCount")));
	Test.TestTrue(TEXT("Message log listing probe returns listings array"), ListingsResult->HasTypedField<EJson::Array>(TEXT("listings")));

	const TSharedPtr<FJsonObject> ReadMessageLogResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ReadMessageLog(TEXT("PIE"), TEXT("{\"limit\":25,\"reverse\":true}")),
		TEXT("ReadMessageLog"));
	if (!ReadMessageLogResult.IsValid())
	{
		return false;
	}

	FString ListingName;
	Test.TestTrue(TEXT("ReadMessageLog returns listingName"), ReadMessageLogResult->TryGetStringField(TEXT("listingName"), ListingName) && ListingName == TEXT("PIE"));
	Test.TestTrue(TEXT("ReadMessageLog returns entries array"), ReadMessageLogResult->HasTypedField<EJson::Array>(TEXT("entries")));
	return true;
}

static bool RunRoundTripCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString BlueprintAssetPath = MakeUniqueAssetPath(TEXT("BP_Smoke"));
	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_Smoke"));
	const FString DataAssetPath = MakeUniqueAssetPath(TEXT("DA_Smoke"));
	const FString StructAssetPath = MakeUniqueAssetPath(TEXT("S_Smoke"));
	const FString EnumAssetPath = MakeUniqueAssetPath(TEXT("E_Smoke"));
	const FString DataTableAssetPath = MakeUniqueAssetPath(TEXT("DT_Smoke"));
	const FString CurveAssetPath = MakeUniqueAssetPath(TEXT("C_Smoke"));
	const FString CurveTableAssetPath = MakeUniqueAssetPath(TEXT("CT_Smoke"));
	const FString MaterialInstanceAssetPath = MakeUniqueAssetPath(TEXT("MI_Smoke"));
	const FString BlackboardAssetPath = MakeUniqueAssetPath(TEXT("BB_Smoke"));
	const FString BehaviorTreeAssetPath = MakeUniqueAssetPath(TEXT("BT_Smoke"));
	const FString StateTreeAssetPath = MakeUniqueAssetPath(TEXT("ST_Smoke"));
	const FString AnimSequenceAssetPath = MakeUniqueAssetPath(TEXT("AS_Smoke"));
	const FString AnimMontageAssetPath = MakeUniqueAssetPath(TEXT("AM_Smoke"));
	const FString BlendSpaceAssetPath = MakeUniqueAssetPath(TEXT("BS_Smoke"));
	const FString BlueprintObjectPath = MakeObjectPath(BlueprintAssetPath);
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);
	const FString DataAssetObjectPath = MakeObjectPath(DataAssetPath);
	const FString StructObjectPath = MakeObjectPath(StructAssetPath);
	const FString EnumObjectPath = MakeObjectPath(EnumAssetPath);
	const FString DataTableObjectPath = MakeObjectPath(DataTableAssetPath);
	const FString CurveObjectPath = MakeObjectPath(CurveAssetPath);
	const FString CurveTableObjectPath = MakeObjectPath(CurveTableAssetPath);
	const FString MaterialInstanceObjectPath = MakeObjectPath(MaterialInstanceAssetPath);
	const FString BlackboardObjectPath = MakeObjectPath(BlackboardAssetPath);
	const FString BehaviorTreeObjectPath = MakeObjectPath(BehaviorTreeAssetPath);
	const FString StateTreeObjectPath = MakeObjectPath(StateTreeAssetPath);
	const FString AnimSequenceObjectPath = MakeObjectPath(AnimSequenceAssetPath);
	const FString AnimMontageObjectPath = MakeObjectPath(AnimMontageAssetPath);
	const FString BlendSpaceObjectPath = MakeObjectPath(BlendSpaceAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateBlueprint(
			BlueprintAssetPath,
			TEXT("/Script/Engine.Actor"),
			TEXT("{}"),
			false),
		TEXT("CreateBlueprint"));

	Test.TestFalse(TEXT("Blueprint .uasset file is not written before SaveAssets"), FPaths::FileExists(MakePackageFilename(BlueprintAssetPath)));

	const TSharedPtr<FJsonObject> CreateWidgetResult = ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint"));
	FString WidgetPackagePath = WidgetAssetPath;
	FString CreatedWidgetObjectPath = WidgetObjectPath;
	if (CreateWidgetResult.IsValid())
	{
		Test.TestTrue(TEXT("CreateWidgetBlueprint returns packagePath"), CreateWidgetResult->TryGetStringField(TEXT("packagePath"), WidgetPackagePath));
		Test.TestTrue(TEXT("CreateWidgetBlueprint returns objectPath"), CreateWidgetResult->TryGetStringField(TEXT("objectPath"), CreatedWidgetObjectPath));
		Test.TestEqual(TEXT("CreateWidgetBlueprint packagePath matches the requested asset path"), WidgetPackagePath, WidgetAssetPath);
		Test.TestEqual(TEXT("CreateWidgetBlueprint objectPath matches the generated object path"), CreatedWidgetObjectPath, WidgetObjectPath);
	}
	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetPackagePath,
			TEXT(R"json({"class":"CanvasPanel","name":"RootCanvas","is_variable":true,"children":[{"class":"TextBlock","name":"TitleText","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidget(
			WidgetPackagePath,
			TEXT("TitleText"),
			TEXT(R"json({"RenderOpacity":0.5})json"),
			TEXT("{}"),
			TEXT("{}"),
			false),
		TEXT("ModifyWidget"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetPackagePath),
		TEXT("CompileWidgetBlueprint"));

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Widget blueprint exists after initial compile"), WidgetBP);

	const FName RootCanvasName(TEXT("RootCanvas"));
	const FName TitleTextName(TEXT("TitleText"));
	const FName BodyTextName(TEXT("BodyText"));
	FGuid RootCanvasGuid;
	if (WidgetBP)
	{
		Test.TestTrue(TEXT("Initial root widget GUID is tracked"), WidgetBP->WidgetVariableNameToGuidMap.Contains(RootCanvasName));
		Test.TestTrue(TEXT("Initial child widget GUID is tracked"), WidgetBP->WidgetVariableNameToGuidMap.Contains(TitleTextName));
		RootCanvasGuid = WidgetBP->WidgetVariableNameToGuidMap.FindRef(RootCanvasName);
		Test.TestTrue(TEXT("Initial root widget GUID is valid"), RootCanvasGuid.IsValid());
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetPackagePath,
			TEXT(R"json({"class":"CanvasPanel","name":"RootCanvas","is_variable":true,"children":[{"class":"TextBlock","name":"BodyText","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree rebuild"));

	WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Widget blueprint exists after rebuild"), WidgetBP);
	if (WidgetBP)
	{
		Test.TestTrue(TEXT("Rebuilt root widget GUID is preserved"), WidgetBP->WidgetVariableNameToGuidMap.FindRef(RootCanvasName) == RootCanvasGuid);
		Test.TestTrue(TEXT("Rebuilt child widget GUID is added before compile"), WidgetBP->WidgetVariableNameToGuidMap.Contains(BodyTextName));
		Test.TestFalse(TEXT("Removed child widget GUID is pruned during rebuild"), WidgetBP->WidgetVariableNameToGuidMap.Contains(TitleTextName));
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetPackagePath),
		TEXT("CompileWidgetBlueprint after rebuild"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateDataAsset(
			DataAssetPath,
			FixtureDataAssetClassPath,
			TEXT(R"json({"Count":7})json"),
			false),
		TEXT("CreateDataAsset"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyDataAsset(
			DataAssetObjectPath,
			TEXT(R"json({"Count":8})json"),
			false),
		TEXT("ModifyDataAsset"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateUserDefinedStruct(
			StructAssetPath,
			TEXT(R"json({"fields":[{"name":"Count","pinType":{"category":"int"}}]})json"),
			false),
		TEXT("CreateUserDefinedStruct"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateUserDefinedEnum(
			EnumAssetPath,
			TEXT(R"json({"entries":[{"name":"Alpha"},{"name":"Beta"}]})json"),
			false),
		TEXT("CreateUserDefinedEnum"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateDataTable(
			DataTableAssetPath,
			FixtureRowStructPath,
			TEXT(R"json([{"rowName":"Default","values":{"Count":1}}])json"),
			false),
		TEXT("CreateDataTable"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyDataTable(
			DataTableObjectPath,
			TEXT(R"json({"rows":[{"rowName":"Default","values":{"Count":2}}]})json"),
			false),
		TEXT("ModifyDataTable"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateCurve(
			CurveAssetPath,
			TEXT("Float"),
			TEXT(R"json({"default":{"keys":[{"time":0.0,"value":0.0},{"time":1.0,"value":1.0}]}})json"),
			false),
		TEXT("CreateCurve"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateCurveTable(
			CurveTableAssetPath,
			TEXT("SimpleCurves"),
			TEXT(R"json([{"rowName":"CurveA","curve":{"keys":[{"time":0.0,"value":0.0},{"time":1.0,"value":1.0}]}}])json"),
			false),
		TEXT("CreateCurveTable"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateMaterialInstance(
			MaterialInstanceAssetPath,
			DefaultMaterialPath,
			false),
		TEXT("CreateMaterialInstance"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateBlackboard(
			BlackboardAssetPath,
			TEXT(R"json({"keys":[{"entryName":"TargetActor","keyTypePath":"/Script/AIModule.BlackboardKeyType_Object","baseClass":"/Script/Engine.Actor"}]})json"),
			false),
		TEXT("CreateBlackboard"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateBehaviorTree(
			BehaviorTreeAssetPath,
			FString::Printf(TEXT(R"json({"blackboardAsset":"%s"})json"), *BlackboardObjectPath),
			false),
		TEXT("CreateBehaviorTree"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlackboard(
			BlackboardObjectPath,
			TEXT("patch_key"),
			TEXT(R"json({"entryName":"TargetActor","isInstanceSynced":true})json"),
			false),
		TEXT("ModifyBlackboard patch_key"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBehaviorTree(
			BehaviorTreeObjectPath,
			TEXT("replace_tree"),
			TEXT("{}"),
			false),
		TEXT("ModifyBehaviorTree replace_tree"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateStateTree(
			StateTreeAssetPath,
			FString::Printf(TEXT(R"json({"schemaClassPath":"%s"})json"), StateTreeSchemaPath),
			false),
		TEXT("CreateStateTree"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyStateTree(
			StateTreeObjectPath,
			TEXT("set_schema"),
			FString::Printf(TEXT(R"json({"schemaClassPath":"%s"})json"), StateTreeSchemaPath),
			false),
		TEXT("ModifyStateTree set_schema"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateAnimSequence(
			AnimSequenceAssetPath,
			FString::Printf(TEXT(R"json({"skeleton":"%s","previewMesh":"%s"})json"), EngineSkeletonPath, EnginePreviewMeshPath),
			false),
		TEXT("CreateAnimSequence"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyAnimSequence(
			AnimSequenceObjectPath,
			TEXT("replace_notifies"),
			TEXT(R"json({"notifies":[]})json"),
			false),
		TEXT("ModifyAnimSequence replace_notifies"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateAnimMontage(
			AnimMontageAssetPath,
			FString::Printf(TEXT(R"json({"skeleton":"%s","previewMesh":"%s"})json"), EngineSkeletonPath, EnginePreviewMeshPath),
			false),
		TEXT("CreateAnimMontage"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyAnimMontage(
			AnimMontageObjectPath,
			TEXT("replace_notifies"),
			TEXT(R"json({"notifies":[]})json"),
			false),
		TEXT("ModifyAnimMontage replace_notifies"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateBlendSpace(
			BlendSpaceAssetPath,
			FString::Printf(TEXT(R"json({"skeleton":"%s","previewMesh":"%s","is1D":true,"axisX":{"name":"Speed","min":0.0,"max":600.0,"gridDivisions":4}})json"), EngineSkeletonPath, EnginePreviewMeshPath),
			false),
		TEXT("CreateBlendSpace"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ AnimSequenceObjectPath, AnimMontageObjectPath, BlendSpaceObjectPath })),
		TEXT("SaveAssets for animation assets before modification"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlendSpace(
			BlendSpaceObjectPath,
			TEXT("set_axes"),
			TEXT(R"json({"axisX":{}})json"),
			false),
		TEXT("ModifyBlendSpace set_axes"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintMembers(
			BlueprintObjectPath,
			TEXT("replace_variables"),
			TEXT(R"json({"variables":[{"name":"Count","pinType":{"category":"int"},"defaultValue":"5"}]})json"),
			false),
		TEXT("ModifyBlueprintMembers replace_variables"));

	const TArray<FString> AssetsToSave = {
		BlueprintObjectPath,
		WidgetPackagePath,
		DataAssetObjectPath,
		StructObjectPath,
		EnumObjectPath,
		DataTableObjectPath,
		CurveObjectPath,
		CurveTableObjectPath,
		MaterialInstanceObjectPath,
		BlackboardObjectPath,
		BehaviorTreeObjectPath,
		StateTreeObjectPath,
		AnimSequenceObjectPath,
		AnimMontageObjectPath,
		BlendSpaceObjectPath,
	};
	const TSharedPtr<FJsonObject> SaveResult = ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray(AssetsToSave)),
		TEXT("SaveAssets"));
	if (SaveResult.IsValid() && SaveResult->HasTypedField<EJson::Boolean>(TEXT("saved")))
	{
		Test.TestTrue(TEXT("SaveAssets reports saved=true"), SaveResult->GetBoolField(TEXT("saved")));
	}

	Test.TestTrue(TEXT("Blueprint .uasset file exists after SaveAssets"), FPaths::FileExists(MakePackageFilename(BlueprintAssetPath)));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractBlueprint(BlueprintObjectPath, TEXT("Variables"), TEXT("")),
		TEXT("ExtractBlueprint"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractBlueprint(WidgetObjectPath, TEXT("Components"), TEXT("")),
		TEXT("ExtractWidgetBlueprint as Blueprint"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractDataAsset(DataAssetObjectPath),
		TEXT("ExtractDataAsset"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractUserDefinedStruct(StructObjectPath),
		TEXT("ExtractUserDefinedStruct"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractUserDefinedEnum(EnumObjectPath),
		TEXT("ExtractUserDefinedEnum"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractDataTable(DataTableObjectPath),
		TEXT("ExtractDataTable"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractCurve(CurveObjectPath),
		TEXT("ExtractCurve"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractCurveTable(CurveTableObjectPath),
		TEXT("ExtractCurveTable"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractMaterialInstance(MaterialInstanceObjectPath),
		TEXT("ExtractMaterialInstance"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractBlackboard(BlackboardObjectPath),
		TEXT("ExtractBlackboard"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractBehaviorTree(BehaviorTreeObjectPath),
		TEXT("ExtractBehaviorTree"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractStateTree(StateTreeObjectPath),
		TEXT("ExtractStateTree"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractAnimSequence(AnimSequenceObjectPath),
		TEXT("ExtractAnimSequence"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractAnimMontage(AnimMontageObjectPath),
		TEXT("ExtractAnimMontage"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractBlendSpace(BlendSpaceObjectPath),
		TEXT("ExtractBlendSpace"));

	const TSharedPtr<FJsonObject> DuplicateBlueprintResult = ParseJsonObject(
		Test,
		Subsystem->CreateBlueprint(
			BlueprintAssetPath,
			TEXT("/Script/Engine.Actor"),
			TEXT("{}"),
			false),
		TEXT("Duplicate CreateBlueprint"));
	Test.TestTrue(TEXT("Duplicate CreateBlueprint is rejected"), IsFailureResult(DuplicateBlueprintResult));

	return true;
}

static bool RunStateTreeTransitionTargetCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString StateTreeAssetPath = MakeUniqueAssetPath(TEXT("ST_TransitionTargets"));
	const FString StateTreeObjectPath = MakeObjectPath(StateTreeAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateStateTree(
			StateTreeAssetPath,
			FString::Printf(TEXT(R"json({"schemaClassPath":"%s"})json"), StateTreeSchemaPath),
			false),
		TEXT("CreateStateTree transition target fixture"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyStateTree(
			StateTreeObjectPath,
			TEXT("replace_tree"),
			FString::Printf(
				TEXT(R"json({"schemaClassPath":"%s","states":[{"name":"Root","type":"State","children":[{"name":"TrainerAlert","type":"State"},{"name":"RallyActive","type":"State"}]}]})json"),
				StateTreeSchemaPath),
			false),
		TEXT("ModifyStateTree replace_tree transition target fixture"));

	const TSharedPtr<FJsonObject> InitialExtract = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractStateTree(StateTreeObjectPath),
		TEXT("ExtractStateTree transition target fixture"));
	if (!InitialExtract.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> TrainerAlertState = FindExtractedStateTreeStateByPath(InitialExtract, TEXT("Root/TrainerAlert"));
	const TSharedPtr<FJsonObject> RallyActiveState = FindExtractedStateTreeStateByPath(InitialExtract, TEXT("Root/RallyActive"));
	Test.TestNotNull(TEXT("ExtractStateTree returns TrainerAlert state"), TrainerAlertState.Get());
	Test.TestNotNull(TEXT("ExtractStateTree returns RallyActive state"), RallyActiveState.Get());
	if (!TrainerAlertState.IsValid() || !RallyActiveState.IsValid())
	{
		return false;
	}

	FString TrainerAlertId;
	FString TrainerAlertPath;
	FString RallyActiveId;
	FString RallyActivePath;
	Test.TestTrue(TEXT("TrainerAlert extract exposes id"), TrainerAlertState->TryGetStringField(TEXT("id"), TrainerAlertId) && !TrainerAlertId.IsEmpty());
	Test.TestTrue(TEXT("TrainerAlert extract exposes statePath"), TrainerAlertState->TryGetStringField(TEXT("statePath"), TrainerAlertPath) && !TrainerAlertPath.IsEmpty());
	Test.TestTrue(TEXT("RallyActive extract exposes id"), RallyActiveState->TryGetStringField(TEXT("id"), RallyActiveId) && !RallyActiveId.IsEmpty());
	Test.TestTrue(TEXT("RallyActive extract exposes statePath"), RallyActiveState->TryGetStringField(TEXT("statePath"), RallyActivePath) && !RallyActivePath.IsEmpty());
	if (TrainerAlertId.IsEmpty() || TrainerAlertPath.IsEmpty() || RallyActiveId.IsEmpty() || RallyActivePath.IsEmpty())
	{
		return false;
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyStateTree(
			StateTreeObjectPath,
			TEXT("patch_state"),
			FString::Printf(
				TEXT(R"json({"stateId":"%s","state":{"description":"Selector patched by extracted id"}})json"),
				*TrainerAlertId),
			false),
		TEXT("ModifyStateTree patch_state selector by extracted stateId"));

	const TSharedPtr<FJsonObject> AfterSelectorExtract = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractStateTree(StateTreeObjectPath),
		TEXT("ExtractStateTree after patch_state selector by extracted stateId"));
	const TSharedPtr<FJsonObject> AfterSelectorTrainer = FindExtractedStateTreeStateByPath(AfterSelectorExtract, TrainerAlertPath);
	Test.TestNotNull(TEXT("ExtractStateTree still returns TrainerAlert after selector patch"), AfterSelectorTrainer.Get());
	if (!AfterSelectorTrainer.IsValid())
	{
		return false;
	}

	FString SelectorDescription;
	Test.TestTrue(
		TEXT("patch_state selected TrainerAlert by extracted stateId"),
		AfterSelectorTrainer->TryGetStringField(TEXT("description"), SelectorDescription)
			&& SelectorDescription == TEXT("Selector patched by extracted id"));

	const auto ExpectTransitionTarget = [&](const FString& PayloadJson, const FString& ContextLabel) -> bool
	{
		ExpectSuccessfulResult(
			Test,
			Subsystem->ModifyStateTree(
				StateTreeObjectPath,
				TEXT("patch_state"),
				PayloadJson,
				false),
			ContextLabel);

		const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
			Test,
			Subsystem->ExtractStateTree(StateTreeObjectPath),
			ContextLabel + TEXT(" extract"));
		const TSharedPtr<FJsonObject> PatchedTrainer = FindExtractedStateTreeStateByPath(ExtractResult, TrainerAlertPath);
		Test.TestNotNull(*FString::Printf(TEXT("%s returns TrainerAlert after patch"), *ContextLabel), PatchedTrainer.Get());
		if (!PatchedTrainer.IsValid())
		{
			return false;
		}

		const TSharedPtr<FJsonObject> TargetState = GetFirstTransitionTargetState(PatchedTrainer);
		Test.TestNotNull(*FString::Printf(TEXT("%s returns targetState"), *ContextLabel), TargetState.Get());
		if (!TargetState.IsValid())
		{
			return false;
		}

		FString TargetStateId;
		FString TargetStateName;
		const bool bHasTargetStateId = TargetState->TryGetStringField(TEXT("stateId"), TargetStateId) && !TargetStateId.IsEmpty();
		const bool bHasTargetStateName = TargetState->TryGetStringField(TEXT("stateName"), TargetStateName) && !TargetStateName.IsEmpty();
		Test.TestTrue(*FString::Printf(TEXT("%s resolves extracted RallyActive id"), *ContextLabel), bHasTargetStateId && TargetStateId == RallyActiveId);
		Test.TestTrue(*FString::Printf(TEXT("%s resolves RallyActive by name"), *ContextLabel), bHasTargetStateName && TargetStateName == TEXT("RallyActive"));
		return bHasTargetStateId && bHasTargetStateName;
	};

	if (!ExpectTransitionTarget(
			FString::Printf(
				TEXT(R"json({"stateId":"%s","state":{"transitions":[{"trigger":"OnTick","targetState":{"stateId":"%s","linkType":"GotoState"}}]}})json"),
				*TrainerAlertId,
				*RallyActiveId),
			TEXT("ModifyStateTree patch_state targetState by extracted stateId")))
	{
		return false;
	}

	if (!ExpectTransitionTarget(
			FString::Printf(
				TEXT(R"json({"stateId":"%s","state":{"transitions":[{"trigger":"OnTick","targetState":{"statePath":"%s","linkType":"GotoState"}}]}})json"),
				*TrainerAlertId,
				*RallyActivePath),
			TEXT("ModifyStateTree patch_state targetState by extracted statePath")))
	{
		return false;
	}

	if (!ExpectTransitionTarget(
			FString::Printf(
				TEXT(R"json({"stateId":"%s","state":{"transitions":[{"trigger":"OnTick","targetState":{"stateName":"RallyActive","linkType":"GotoState"}}]}})json"),
				*TrainerAlertId),
			TEXT("ModifyStateTree patch_state targetState by unique stateName")))
	{
		return false;
	}

	const FString AmbiguousStateTreeAssetPath = MakeUniqueAssetPath(TEXT("ST_TransitionTargetsAmbiguous"));
	const FString AmbiguousStateTreeObjectPath = MakeObjectPath(AmbiguousStateTreeAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateStateTree(
			AmbiguousStateTreeAssetPath,
			FString::Printf(TEXT(R"json({"schemaClassPath":"%s"})json"), StateTreeSchemaPath),
			false),
		TEXT("CreateStateTree ambiguous transition target fixture"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyStateTree(
			AmbiguousStateTreeObjectPath,
			TEXT("replace_tree"),
			FString::Printf(
				TEXT(R"json({"schemaClassPath":"%s","states":[{"name":"Root","type":"State","children":[{"name":"SourceState","type":"State"},{"name":"BranchA","type":"State","children":[{"name":"SharedTarget","type":"State"}]},{"name":"BranchB","type":"State","children":[{"name":"SharedTarget","type":"State"}]}]}]})json"),
				StateTreeSchemaPath),
			false),
		TEXT("ModifyStateTree replace_tree ambiguous transition target fixture"));

	const TSharedPtr<FJsonObject> AmbiguousFailure = ExpectFailureResult(
		Test,
		Subsystem->ModifyStateTree(
			AmbiguousStateTreeObjectPath,
			TEXT("patch_state"),
			TEXT(R"json({"statePath":"Root/SourceState","state":{"transitions":[{"trigger":"OnTick","targetState":{"stateName":"SharedTarget","linkType":"GotoState"}}]}})json"),
			false),
		TEXT("ModifyStateTree patch_state ambiguous targetState.stateName"));
	if (!AmbiguousFailure.IsValid())
	{
		return false;
	}

	const FString FailurePayloadText = SerializeJsonObjectForSearch(AmbiguousFailure);
	Test.TestTrue(TEXT("Ambiguous stateName surfaces a validation error"), FailurePayloadText.Contains(TEXT("stateName 'SharedTarget' is ambiguous")));
	Test.TestFalse(TEXT("Ambiguous stateName does not fall through to None compile error"), FailurePayloadText.Contains(TEXT("Failed to resolve transition to state 'None'")));

	const FString LinkedSubtreeAssetPath = MakeUniqueAssetPath(TEXT("ST_TransitionTargetsLinkedSubtree"));
	const FString LinkedSubtreeObjectPath = MakeObjectPath(LinkedSubtreeAssetPath);
	const FString LinkedStateTreeAssetPath = MakeUniqueAssetPath(TEXT("ST_TransitionTargetsLinkedAsset"));
	const FString LinkedStateTreeObjectPath = MakeObjectPath(LinkedStateTreeAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateStateTree(
			LinkedSubtreeAssetPath,
			FString::Printf(TEXT(R"json({"schemaClassPath":"%s","states":[{"name":"Root","type":"State"}]})json"), StateTreeSchemaPath),
			false),
		TEXT("CreateStateTree linked subtree fixture"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateStateTree(
			LinkedStateTreeAssetPath,
			FString::Printf(TEXT(R"json({"schemaClassPath":"%s"})json"), StateTreeSchemaPath),
			false),
		TEXT("CreateStateTree linked-asset transition fixture"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyStateTree(
			LinkedStateTreeObjectPath,
			TEXT("replace_tree"),
			FString::Printf(
				TEXT(R"json({"schemaClassPath":"%s","states":[{"name":"Root","type":"State","children":[{"name":"TrainerAlert","type":"LinkedAsset","linkedAsset":"%s"},{"name":"GoToDestination","type":"State"}]}]})json"),
				StateTreeSchemaPath,
				*LinkedSubtreeObjectPath),
			false),
		TEXT("ModifyStateTree replace_tree linked-asset transition fixture"));

	const TSharedPtr<FJsonObject> LinkedAssetFailure = ExpectFailureResult(
		Test,
		Subsystem->ModifyStateTree(
			LinkedStateTreeObjectPath,
			TEXT("patch_state"),
			TEXT(R"json({"statePath":"Root/TrainerAlert","state":{"transitions":[{"trigger":"OnTick","targetState":{"statePath":"Root/GoToDestination","linkType":"GotoState"}}]}})json"),
			false),
		TEXT("ModifyStateTree patch_state linked-asset goto target"));
	if (!LinkedAssetFailure.IsValid())
	{
		return false;
	}

	const FString LinkedAssetFailureText = SerializeJsonObjectForSearch(LinkedAssetFailure);
	Test.TestTrue(TEXT("LinkedAsset transition failure mentions LinkedAsset topology"), LinkedAssetFailureText.Contains(TEXT("LinkedAsset state")));
	Test.TestTrue(TEXT("LinkedAsset transition failure recommends enterConditions workaround"), LinkedAssetFailureText.Contains(TEXT("enterConditions")));
	Test.TestFalse(TEXT("LinkedAsset transition failure does not fall through to None compile error"), LinkedAssetFailureText.Contains(TEXT("Failed to resolve transition to state 'None'")));
	return true;
}

static bool RunAnimMontageAuthoringCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString FailedPreviewAssetPath = MakeUniqueAssetPath(TEXT("AM_FailedPreview"));
	const FString DifferentAssetPath = MakeUniqueAssetPath(TEXT("AM_AfterFailedPreviewOther"));
	const FString SequenceLengthAssetPath = MakeUniqueAssetPath(TEXT("AM_SequenceLengthHint"));

	ExpectFailureResult(
		Test,
		Subsystem->CreateAnimMontage(
			FailedPreviewAssetPath,
			FString::Printf(
				TEXT(R"json({"skeleton":"%s","previewMesh":"%s","sections":[{"sectionName":"Late","startTime":1.0}]})json"),
				EngineSkeletonPath,
				EnginePreviewMeshPath),
			true),
		TEXT("CreateAnimMontage validate_only invalid preview payload"));

	Test.TestFalse(
		TEXT("Failed validate_only does not leave a phantom montage at the requested path"),
		DoesAssetExist(FailedPreviewAssetPath));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateAnimMontage(
			DifferentAssetPath,
			FString::Printf(TEXT(R"json({"skeleton":"%s","previewMesh":"%s"})json"), EngineSkeletonPath, EnginePreviewMeshPath),
			false),
		TEXT("CreateAnimMontage different path after failed validate_only"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateAnimMontage(
			FailedPreviewAssetPath,
			FString::Printf(TEXT(R"json({"skeleton":"%s","previewMesh":"%s"})json"), EngineSkeletonPath, EnginePreviewMeshPath),
			false),
		TEXT("CreateAnimMontage same path after failed validate_only"));

	const bool bSequenceLengthValidationSucceeded = ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateAnimMontage(
			SequenceLengthAssetPath,
			FString::Printf(
				TEXT(R"json({"skeleton":"%s","previewMesh":"%s","sequenceLength":5.0,"sections":[{"sectionName":"Intro","startTime":0.0},{"sectionName":"Late","startTime":4.0}],"notifies":[{"notifyName":"LateCue","time":4.5}]})json"),
				EngineSkeletonPath,
				EnginePreviewMeshPath),
			true),
		TEXT("CreateAnimMontage validate_only honors sequenceLength for late sections and notifies"));

	Test.TestTrue(TEXT("AnimMontage sequenceLength hint allows late metadata validation"), bSequenceLengthValidationSucceeded);
	Test.TestFalse(TEXT("sequenceLength validate_only does not create an asset"), DoesAssetExist(SequenceLengthAssetPath));
	return bSequenceLengthValidationSucceeded;
}

static bool RunInlineInstancedDataAssetCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString PreviewDataAssetPath = MakeUniqueAssetPath(TEXT("DA_InlineGraphPreview"));
	const FString DataAssetPath = MakeUniqueAssetPath(TEXT("DA_InlineGraph"));
	const FString DataAssetObjectPath = MakeObjectPath(DataAssetPath);

	ExpectValidateOnlyResult(
		Test,
		Subsystem->CreateDataAsset(
			PreviewDataAssetPath,
			FixtureDataAssetClassPath,
			FString::Printf(
				TEXT(R"json({"Count":7,"InlineObject":{"classPath":"%s","properties":{"Label":"Root","Count":11,"Child":{"classPath":"%s","properties":{"Label":"Leaf","Count":12}}}}})json"),
				FixtureInlineObjectClassPath,
				FixtureInlineObjectClassPath),
			true),
		TEXT("CreateDataAsset validate_only inline object graph"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateDataAsset(
			DataAssetPath,
			FixtureDataAssetClassPath,
			FString::Printf(
				TEXT(R"json({"Count":7,"InlineObject":{"classPath":"%s","properties":{"Label":"Root","Count":11,"Child":{"classPath":"%s","properties":{"Label":"Leaf","Count":12}}}}})json"),
				FixtureInlineObjectClassPath,
				FixtureInlineObjectClassPath),
			false),
		TEXT("CreateDataAsset inline object graph"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ DataAssetObjectPath })),
		TEXT("SaveAssets inline object graph data asset"));

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractDataAsset(DataAssetObjectPath),
		TEXT("ExtractDataAsset inline object graph"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> DataAssetJson;
	Test.TestTrue(TEXT("Inline object extract returns dataAsset payload"), TryGetObjectFieldCopy(ExtractResult, TEXT("dataAsset"), DataAssetJson) && DataAssetJson.IsValid());
	if (!DataAssetJson.IsValid())
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* PropertiesArray = nullptr;
	Test.TestTrue(TEXT("Inline object extract includes properties array"), DataAssetJson->TryGetArrayField(TEXT("properties"), PropertiesArray) && PropertiesArray && PropertiesArray->Num() > 0);
	if (!PropertiesArray)
	{
		return false;
	}

	const TSharedPtr<FJsonObject> InlineObjectProperty = FindArrayObjectByStringField(DataAssetJson, TEXT("properties"), TEXT("name"), TEXT("InlineObject"));
	Test.TestNotNull(TEXT("Inline object property is present"), InlineObjectProperty.Get());
	if (!InlineObjectProperty.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> InlineObjectValue;
	Test.TestTrue(TEXT("Inline object property exposes nested value"), TryGetObjectFieldCopy(InlineObjectProperty, TEXT("value"), InlineObjectValue) && InlineObjectValue.IsValid());
	if (!InlineObjectValue.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> InlineProperties;
	Test.TestTrue(TEXT("Inline object value exposes nested properties"), TryGetObjectFieldCopy(InlineObjectValue, TEXT("properties"), InlineProperties) && InlineProperties.IsValid());
	if (!InlineProperties.IsValid())
	{
		return false;
	}

	Test.TestEqual(TEXT("Inline object root label round-trips"), InlineProperties->GetStringField(TEXT("Label")), FString(TEXT("Root")));
	Test.TestEqual(TEXT("Inline object root count round-trips"), static_cast<int32>(InlineProperties->GetNumberField(TEXT("Count"))), 11);

	TSharedPtr<FJsonObject> InlineChildValue;
	Test.TestTrue(TEXT("Inline object nested child is present"), TryGetObjectFieldCopy(InlineProperties, TEXT("Child"), InlineChildValue) && InlineChildValue.IsValid());
	if (!InlineChildValue.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> InlineChildProperties;
	Test.TestTrue(TEXT("Inline object nested child exposes properties"), TryGetObjectFieldCopy(InlineChildValue, TEXT("properties"), InlineChildProperties) && InlineChildProperties.IsValid());
	if (!InlineChildProperties.IsValid())
	{
		return false;
	}

	Test.TestEqual(TEXT("Inline child label round-trips"), InlineChildProperties->GetStringField(TEXT("Label")), FString(TEXT("Leaf")));
	Test.TestEqual(TEXT("Inline child count round-trips"), static_cast<int32>(InlineChildProperties->GetNumberField(TEXT("Count"))), 12);

	ExpectValidateOnlyResult(
		Test,
		Subsystem->ModifyDataAsset(
			DataAssetObjectPath,
			TEXT(R"json({"Count":8,"InlineObject":{"properties":{"Label":"RootModified","Count":13,"Child":{"properties":{"Label":"LeafModified","Count":14}}}}})json"),
			true),
		TEXT("ModifyDataAsset validate_only inline object graph"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyDataAsset(
			DataAssetObjectPath,
			TEXT(R"json({"Count":8,"InlineObject":{"properties":{"Label":"RootModified","Count":13,"Child":{"properties":{"Label":"LeafModified","Count":14}}}}})json"),
			false),
		TEXT("ModifyDataAsset inline object graph"));

	const TSharedPtr<FJsonObject> ModifiedExtract = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractDataAsset(DataAssetObjectPath),
		TEXT("ExtractDataAsset modified inline object graph"));
	if (!ModifiedExtract.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> ModifiedDataAssetJson;
	Test.TestTrue(TEXT("Modified inline object extract returns dataAsset payload"), TryGetObjectFieldCopy(ModifiedExtract, TEXT("dataAsset"), ModifiedDataAssetJson) && ModifiedDataAssetJson.IsValid());
	if (!ModifiedDataAssetJson.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> ModifiedInlineObjectProperty = FindArrayObjectByStringField(ModifiedDataAssetJson, TEXT("properties"), TEXT("name"), TEXT("InlineObject"));
	Test.TestNotNull(TEXT("Modified inline object property is present"), ModifiedInlineObjectProperty.Get());
	if (!ModifiedInlineObjectProperty.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> ModifiedInlineObjectValue;
	Test.TestTrue(TEXT("Modified inline object exposes nested value"), TryGetObjectFieldCopy(ModifiedInlineObjectProperty, TEXT("value"), ModifiedInlineObjectValue) && ModifiedInlineObjectValue.IsValid());
	if (!ModifiedInlineObjectValue.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> ModifiedInlineProperties;
	Test.TestTrue(TEXT("Modified inline object value exposes nested properties"), TryGetObjectFieldCopy(ModifiedInlineObjectValue, TEXT("properties"), ModifiedInlineProperties) && ModifiedInlineProperties.IsValid());
	if (!ModifiedInlineProperties.IsValid())
	{
		return false;
	}

	Test.TestEqual(TEXT("Modified inline root label round-trips"), ModifiedInlineProperties->GetStringField(TEXT("Label")), FString(TEXT("RootModified")));
	Test.TestEqual(TEXT("Modified inline root count round-trips"), static_cast<int32>(ModifiedInlineProperties->GetNumberField(TEXT("Count"))), 13);

	TSharedPtr<FJsonObject> ModifiedInlineChildValue;
	Test.TestTrue(TEXT("Modified inline child is present"), TryGetObjectFieldCopy(ModifiedInlineProperties, TEXT("Child"), ModifiedInlineChildValue) && ModifiedInlineChildValue.IsValid());
	if (!ModifiedInlineChildValue.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> ModifiedInlineChildProperties;
	Test.TestTrue(TEXT("Modified inline child exposes properties"), TryGetObjectFieldCopy(ModifiedInlineChildValue, TEXT("properties"), ModifiedInlineChildProperties) && ModifiedInlineChildProperties.IsValid());
	if (!ModifiedInlineChildProperties.IsValid())
	{
		return false;
	}

	Test.TestEqual(TEXT("Modified inline child label round-trips"), ModifiedInlineChildProperties->GetStringField(TEXT("Label")), FString(TEXT("LeafModified")));
	Test.TestEqual(TEXT("Modified inline child count round-trips"), static_cast<int32>(ModifiedInlineChildProperties->GetNumberField(TEXT("Count"))), 14);

	return true;
}

static bool RunMaterialCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString MaterialAssetPath = MakeUniqueAssetPath(TEXT("M_GraphSmoke"));
	const FString MaterialFunctionAssetPath = MakeUniqueAssetPath(TEXT("MF_GraphSmoke"));
	const FString MaterialLayerAssetPath = MakeUniqueAssetPath(TEXT("MFL_GraphSmoke"));
	const FString MaterialLayerBlendAssetPath = MakeUniqueAssetPath(TEXT("MFLB_GraphSmoke"));
	const FString MaterialInstanceAssetPath = MakeUniqueAssetPath(TEXT("MI_GraphSmoke"));

	const FString MaterialObjectPath = MakeObjectPath(MaterialAssetPath);
	const FString MaterialFunctionObjectPath = MakeObjectPath(MaterialFunctionAssetPath);
	const FString MaterialLayerObjectPath = MakeObjectPath(MaterialLayerAssetPath);
	const FString MaterialLayerBlendObjectPath = MakeObjectPath(MaterialLayerBlendAssetPath);
	const FString MaterialInstanceObjectPath = MakeObjectPath(MaterialInstanceAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateMaterial(
			MaterialAssetPath,
			DefaultTexturePath,
			TEXT(R"json({"twoSided":true,"blendMode":"BLEND_Opaque","materialDomain":"MD_Surface"})json"),
			false),
		TEXT("CreateMaterial"));

	const FString MaterialPayload = TEXT(R"json({
		"compileAfter":true,
		"layoutAfter":true,
		"operations":[
			{"operation":"add_expression","expressionClass":"/Script/Engine.MaterialExpressionVectorParameter","tempId":"baseColor","editorX":-420,"editorY":-80,"properties":{"ParameterName":"BaseColorTint","Group":"Surface","DefaultValue":{"r":0.25,"g":0.5,"b":0.75,"a":1.0}}},
			{"operation":"add_expression","expressionClass":"/Script/Engine.MaterialExpressionScalarParameter","tempId":"roughness","editorX":-420,"editorY":120,"properties":{"ParameterName":"SurfaceRoughness","Group":"Surface","DefaultValue":0.35}},
			{"operation":"add_expression","expressionClass":"/Script/Engine.MaterialExpressionAdd","tempId":"unusedAdd","editorX":-120,"editorY":220},
			{"operation":"add_expression","expressionClass":"/Script/Engine.MaterialExpressionLinearInterpolate","tempId":"lerpNode","editorX":60,"editorY":20},
			{"operation":"connect_material_property","fromTempId":"baseColor","materialProperty":"MP_BaseColor"},
			{"operation":"connect_material_property","fromTempId":"baseColor","fromOutputIndex":1,"materialProperty":"MP_Roughness"},
			{"operation":"connect_expressions","fromTempId":"roughness","toTempId":"unusedAdd","toInputName":"A"},
			{"operation":"connect_expressions","fromTempId":"roughness","toTempId":"lerpNode","toInputIndex":2},
			{"operation":"disconnect_expression_input","tempId":"unusedAdd","inputName":"A"},
			{"operation":"move_expression","tempId":"unusedAdd","editorX":-40,"editorY":260},
			{"operation":"set_expression_properties","tempId":"roughness","properties":{"DefaultValue":0.45}},
			{"operation":"rename_parameter_group","oldGroupName":"Surface","newGroupName":"Shading"},
			{"operation":"add_comment","tempId":"note","editorX":-520,"editorY":-220,"properties":{"Text":"Material smoke"}},
			{"operation":"duplicate_expression","sourceTempId":"roughness","tempId":"roughnessCopy","editorX":-420,"editorY":260},
			{"operation":"delete_expression","tempId":"roughnessCopy"},
			{"operation":"delete_comment","tempId":"note"},
			{"operation":"set_material_settings","settings":{"twoSided":true,"opacityMaskClipValue":0.33,"usageFlags":["MATUSAGE_StaticMesh"]}}
		]
	})json");

	ExpectValidateOnlyResult(
		Test,
		Subsystem->ModifyMaterial(MaterialObjectPath, MaterialPayload, true),
		TEXT("ModifyMaterial validate_only"));

	const TSharedPtr<FJsonObject> ModifyMaterialResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyMaterial(MaterialObjectPath, MaterialPayload, false),
		TEXT("ModifyMaterial"));
	if (ModifyMaterialResult.IsValid())
	{
		TSharedPtr<FJsonObject> TempIdMap;
		Test.TestTrue(TEXT("ModifyMaterial returns created expression tempId map"), TryGetObjectFieldCopy(ModifyMaterialResult, TEXT("tempIdMap"), TempIdMap) && TempIdMap.IsValid());
		FString BaseColorGuid;
		FString RoughnessGuid;
		FString LerpNodeGuid;
		Test.TestTrue(TEXT("ModifyMaterial tempId map contains baseColor"), TempIdMap.IsValid() && TempIdMap->TryGetStringField(TEXT("baseColor"), BaseColorGuid) && !BaseColorGuid.IsEmpty());
		Test.TestTrue(TEXT("ModifyMaterial tempId map contains roughness"), TempIdMap.IsValid() && TempIdMap->TryGetStringField(TEXT("roughness"), RoughnessGuid) && !RoughnessGuid.IsEmpty());
		Test.TestTrue(TEXT("ModifyMaterial tempId map contains lerpNode"), TempIdMap.IsValid() && TempIdMap->TryGetStringField(TEXT("lerpNode"), LerpNodeGuid) && !LerpNodeGuid.IsEmpty());

		const FString ConflictPayload = FString::Printf(
			TEXT(R"json({"operations":[{"operation":"connect_expressions","fromExpressionGuid":"%s","toExpressionGuid":"%s","toInputName":"A","toInputIndex":2}]})json"),
			*RoughnessGuid,
			*LerpNodeGuid);
		ExpectFailureResult(
			Test,
			Subsystem->ModifyMaterial(MaterialObjectPath, ConflictPayload, true),
			TEXT("ModifyMaterial selector conflict validate_only"));
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileMaterialAsset(MaterialObjectPath),
		TEXT("CompileMaterialAsset material"));

	const TSharedPtr<FJsonObject> ExtractMaterialResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractMaterial(MaterialObjectPath, false),
		TEXT("ExtractMaterial"));
	if (!ExtractMaterialResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> MaterialJson;
	Test.TestTrue(TEXT("ExtractMaterial returns a material object"), TryGetObjectFieldCopy(ExtractMaterialResult, TEXT("material"), MaterialJson) && MaterialJson.IsValid());
	if (!MaterialJson.IsValid())
	{
		return false;
	}

	Test.TestEqual(TEXT("ExtractMaterial preserves the material path"), MaterialJson->GetStringField(TEXT("assetPath")), MaterialObjectPath);
	Test.TestEqual(TEXT("ExtractMaterial reports shading model"), MaterialJson->GetStringField(TEXT("shadingModel")), FString(TEXT("DefaultLit")));
	Test.TestTrue(TEXT("ExtractMaterial reports used shading models"), MaterialJson->GetStringField(TEXT("usedShadingModels")).Contains(TEXT("DefaultLit")));
	Test.TestNotNull(
		TEXT("ExtractMaterial reports BaseColor property connection"),
		FindArrayObjectByStringField(MaterialJson, TEXT("propertyConnections"), TEXT("property"), TEXT("MP_BaseColor")).Get());
	const TSharedPtr<FJsonObject> RoughnessConnection = FindArrayObjectByStringField(MaterialJson, TEXT("propertyConnections"), TEXT("property"), TEXT("MP_Roughness"));
	Test.TestNotNull(TEXT("ExtractMaterial reports Roughness property connection"), RoughnessConnection.Get());
	if (RoughnessConnection.IsValid())
	{
		double RoughnessOutputIndex = -1.0;
		Test.TestTrue(TEXT("Roughness property connection reports output index"), RoughnessConnection->TryGetNumberField(TEXT("outputIndex"), RoughnessOutputIndex));
		Test.TestEqual(TEXT("Roughness property connection preserves from_output_index"), static_cast<int32>(RoughnessOutputIndex), 1);
	}
	Test.TestNotNull(
		TEXT("ExtractMaterial reports renamed parameter group"),
		FindArrayObjectByStringField(MaterialJson, TEXT("parameterGroups"), TEXT("groupName"), TEXT("Shading")).Get());

	TSharedPtr<FJsonObject> ModifyTempIdMap;
	if (ModifyMaterialResult.IsValid())
	{
		Test.TestTrue(TEXT("ModifyMaterial result still exposes tempIdMap"), TryGetObjectFieldCopy(ModifyMaterialResult, TEXT("tempIdMap"), ModifyTempIdMap) && ModifyTempIdMap.IsValid());
	}
	if (ModifyTempIdMap.IsValid())
	{
		FString RoughnessGuid;
		FString LerpNodeGuid;
		Test.TestTrue(TEXT("Modify tempId map keeps roughness guid"), ModifyTempIdMap->TryGetStringField(TEXT("roughness"), RoughnessGuid));
		Test.TestTrue(TEXT("Modify tempId map keeps lerp guid"), ModifyTempIdMap->TryGetStringField(TEXT("lerpNode"), LerpNodeGuid));

		const TSharedPtr<FJsonObject> LerpNodeObject = FindArrayObjectByStringField(MaterialJson, TEXT("expressions"), TEXT("expressionGuid"), LerpNodeGuid);
		Test.TestNotNull(TEXT("ExtractMaterial includes the Lerp node"), LerpNodeObject.Get());
		if (LerpNodeObject.IsValid())
		{
			const TSharedPtr<FJsonObject> AlphaInput = FindArrayObjectByStringField(LerpNodeObject, TEXT("inputs"), TEXT("name"), TEXT("Alpha"));
			Test.TestNotNull(TEXT("ExtractMaterial reports the Lerp Alpha input"), AlphaInput.Get());
			if (AlphaInput.IsValid())
			{
				FString ConnectedExpressionGuid;
				Test.TestTrue(TEXT("Lerp Alpha input reports source expression guid"), AlphaInput->TryGetStringField(TEXT("expressionGuid"), ConnectedExpressionGuid));
				Test.TestEqual(TEXT("Lerp Alpha input preserves to_input_index wiring"), ConnectedExpressionGuid, RoughnessGuid);
			}
		}
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateMaterialInstance(
			MaterialInstanceAssetPath,
			MaterialObjectPath,
			false),
		TEXT("CreateMaterialInstance from generated material"));

	const FString MaterialInstancePayload = TEXT(R"json({
		"scalarParameters":[{"name":"SurfaceRoughness","value":0.6}],
		"vectorParameters":[{"name":"BaseColorTint","value":{"r":0.9,"g":0.2,"b":0.1,"a":1.0}}]
	})json");

	ExpectValidateOnlyResult(
		Test,
		Subsystem->ModifyMaterialInstance(MaterialInstanceObjectPath, MaterialInstancePayload, true),
		TEXT("ModifyMaterialInstance validate_only material graph"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyMaterialInstance(MaterialInstanceObjectPath, MaterialInstancePayload, false),
		TEXT("ModifyMaterialInstance material graph"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileMaterialAsset(MaterialInstanceObjectPath),
		TEXT("CompileMaterialAsset material instance"));

	const TSharedPtr<FJsonObject> ExtractMaterialInstanceResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractMaterialInstance(MaterialInstanceObjectPath),
		TEXT("ExtractMaterialInstance graph"));
	if (!ExtractMaterialInstanceResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> MaterialInstanceJson;
	Test.TestTrue(TEXT("ExtractMaterialInstance returns a materialInstance object"), TryGetObjectFieldCopy(ExtractMaterialInstanceResult, TEXT("materialInstance"), MaterialInstanceJson) && MaterialInstanceJson.IsValid());
	if (MaterialInstanceJson.IsValid())
	{
		Test.TestNotNull(
			TEXT("ExtractMaterialInstance exposes vector parameter override"),
			FindArrayObjectByStringField(MaterialInstanceJson, TEXT("vectorParameters"), TEXT("name"), TEXT("BaseColorTint")).Get());
		Test.TestNotNull(
			TEXT("ExtractMaterialInstance exposes scalar parameter override"),
			FindArrayObjectByStringField(MaterialInstanceJson, TEXT("scalarParameters"), TEXT("name"), TEXT("SurfaceRoughness")).Get());
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateMaterialFunction(
			MaterialFunctionAssetPath,
			TEXT("function"),
			TEXT("{}"),
			false),
		TEXT("CreateMaterialFunction"));

	const FString MaterialFunctionPayload = TEXT(R"json({
		"compileAfter":true,
		"layoutAfter":true,
		"operations":[
			{"operation":"add_expression","expressionClass":"/Script/Engine.MaterialExpressionFunctionInput","tempId":"inputColor","editorX":-320,"editorY":0,"properties":{"InputName":"InputColor","InputType":"FunctionInput_Vector3"}},
			{"operation":"add_expression","expressionClass":"/Script/Engine.MaterialExpressionFunctionOutput","tempId":"resultOutput","editorX":40,"editorY":0,"properties":{"OutputName":"Result"}},
			{"operation":"connect_expressions","fromTempId":"inputColor","toTempId":"resultOutput"}
		]
	})json");

	ExpectValidateOnlyResult(
		Test,
		Subsystem->ModifyMaterialFunction(MaterialFunctionObjectPath, MaterialFunctionPayload, true),
		TEXT("ModifyMaterialFunction validate_only"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyMaterialFunction(MaterialFunctionObjectPath, MaterialFunctionPayload, false),
		TEXT("ModifyMaterialFunction"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileMaterialAsset(MaterialFunctionObjectPath),
		TEXT("CompileMaterialAsset material function"));

	const TSharedPtr<FJsonObject> ExtractMaterialFunctionResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractMaterialFunction(MaterialFunctionObjectPath, false),
		TEXT("ExtractMaterialFunction"));
	if (!ExtractMaterialFunctionResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> MaterialFunctionJson;
	Test.TestTrue(TEXT("ExtractMaterialFunction returns a materialFunction object"), TryGetObjectFieldCopy(ExtractMaterialFunctionResult, TEXT("materialFunction"), MaterialFunctionJson) && MaterialFunctionJson.IsValid());
	if (MaterialFunctionJson.IsValid())
	{
		Test.TestEqual(TEXT("Material function extract reports the correct kind"), MaterialFunctionJson->GetStringField(TEXT("assetKind")), FString(TEXT("function")));

		const TArray<TSharedPtr<FJsonValue>>* FunctionInputs = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* FunctionOutputs = nullptr;
		Test.TestTrue(TEXT("Material function extract lists function inputs"), MaterialFunctionJson->TryGetArrayField(TEXT("functionInputs"), FunctionInputs) && FunctionInputs && FunctionInputs->Num() == 1);
		Test.TestTrue(TEXT("Material function extract lists function outputs"), MaterialFunctionJson->TryGetArrayField(TEXT("functionOutputs"), FunctionOutputs) && FunctionOutputs && FunctionOutputs->Num() == 1);
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateMaterialFunction(
			MaterialLayerAssetPath,
			TEXT("layer"),
			TEXT("{}"),
			false),
		TEXT("CreateMaterialFunction layer"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateMaterialFunction(
			MaterialLayerBlendAssetPath,
			TEXT("layer_blend"),
			TEXT("{}"),
			false),
		TEXT("CreateMaterialFunction layer_blend"));

	const TSharedPtr<FJsonObject> ExtractLayerResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractMaterialFunction(MaterialLayerObjectPath, false),
		TEXT("ExtractMaterialLayer"));
	if (ExtractLayerResult.IsValid())
	{
		TSharedPtr<FJsonObject> LayerJson;
		Test.TestTrue(TEXT("ExtractMaterialLayer returns a materialFunction object"), TryGetObjectFieldCopy(ExtractLayerResult, TEXT("materialFunction"), LayerJson) && LayerJson.IsValid());
		if (LayerJson.IsValid())
		{
			Test.TestEqual(TEXT("Material layer extract reports the correct kind"), LayerJson->GetStringField(TEXT("assetKind")), FString(TEXT("layer")));
		}
	}

	const TSharedPtr<FJsonObject> ExtractLayerBlendResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractMaterialFunction(MaterialLayerBlendObjectPath, false),
		TEXT("ExtractMaterialLayerBlend"));
	if (ExtractLayerBlendResult.IsValid())
	{
		TSharedPtr<FJsonObject> LayerBlendJson;
		Test.TestTrue(TEXT("ExtractMaterialLayerBlend returns a materialFunction object"), TryGetObjectFieldCopy(ExtractLayerBlendResult, TEXT("materialFunction"), LayerBlendJson) && LayerBlendJson.IsValid());
		if (LayerBlendJson.IsValid())
		{
			Test.TestEqual(TEXT("Material layer blend extract reports the correct kind"), LayerBlendJson->GetStringField(TEXT("assetKind")), FString(TEXT("layer_blend")));
		}
	}

	const TArray<FString> AssetsToSave = {
		MaterialObjectPath,
		MaterialFunctionObjectPath,
		MaterialLayerObjectPath,
		MaterialLayerBlendObjectPath,
		MaterialInstanceObjectPath,
	};

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray(AssetsToSave)),
		TEXT("SaveAssets material coverage"));

	Test.TestTrue(TEXT("Material .uasset file exists after SaveAssets"), FPaths::FileExists(MakePackageFilename(MaterialAssetPath)));
	return true;
}

static bool RunImportCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString ImportRoot = FString::Printf(TEXT("%s/Imported"), ScratchRoot);
	const FString TextureAssetPath = ImportRoot + TEXT("/T_Imported");
	const FString MeshAssetPath = ImportRoot + TEXT("/SM_Imported");
	const FString TextureObjectPath = MakeObjectPath(TextureAssetPath);
	const FString MeshObjectPath = MakeObjectPath(MeshAssetPath);

	const TSharedPtr<FJsonObject> TextureImportResult = WaitForImportJob(
		Test,
		Subsystem,
		Subsystem->ImportTextures(
			FString::Printf(
				TEXT(R"json({"items":[{"file_path":"%s","destination_path":"%s","destination_name":"T_Imported","options":{"srgb":false,"flip_green_channel":true}}]})json"),
				TextureImportSource,
				*ImportRoot),
			false),
		TEXT("ImportTextures"));
	Test.TestTrue(TEXT("Texture import completes"), TextureImportResult.IsValid());
	Test.TestTrue(
		TEXT("Texture import reports imported object path"),
		JsonArrayContainsString(TextureImportResult, TEXT("importedObjects"), TextureObjectPath));

	const TSharedPtr<FJsonObject> MeshImportResult = WaitForImportJob(
		Test,
		Subsystem,
		Subsystem->ImportMeshes(
			FString::Printf(
				TEXT(R"json({"items":[{"file_path":"%s","destination_path":"%s","destination_name":"SM_Imported","options":{"mesh_type":"static","combine_meshes":true,"generate_collision":true}}]})json"),
				MeshImportSource,
				*ImportRoot),
			false),
		TEXT("ImportMeshes"));
	Test.TestTrue(TEXT("Mesh import completes"), MeshImportResult.IsValid());
	Test.TestTrue(
		TEXT("Mesh import reports imported object path"),
		JsonArrayContainsString(MeshImportResult, TEXT("importedObjects"), MeshObjectPath));

	UTexture* ImportedTexture = Cast<UTexture>(ResolveAssetByPath(TextureObjectPath));
	Test.TestNotNull(TEXT("Imported texture exists"), ImportedTexture);
	if (ImportedTexture)
	{
		Test.TestFalse(TEXT("Imported texture applied sRGB override"), ImportedTexture->SRGB);
	}

	const TSharedPtr<FJsonObject> ReimportResult = WaitForImportJob(
		Test,
		Subsystem,
		Subsystem->ReimportAssets(
			FString::Printf(
				TEXT(R"json({"items":[{"asset_path":"%s","file_path":"%s"}]})json"),
				*TextureObjectPath,
				TextureImportSourceAlt),
			false),
		TEXT("ReimportAssets"));
	Test.TestTrue(TEXT("Texture reimport completes"), ReimportResult.IsValid());
	Test.TestTrue(
		TEXT("Texture reimport reports imported object path"),
		JsonArrayContainsString(ReimportResult, TEXT("importedObjects"), TextureObjectPath));

	ImportedTexture = Cast<UTexture>(ResolveAssetByPath(TextureObjectPath));
	if (ImportedTexture && ImportedTexture->AssetImportData)
	{
		Test.TestTrue(
			TEXT("Reimport updates texture source path"),
			ImportedTexture->AssetImportData->GetFirstFilename().EndsWith(TEXT("T_Test_Alt.png")));
	}

	const TSharedPtr<FJsonObject> ReplaceExistingResult = WaitForImportJob(
		Test,
		Subsystem,
		Subsystem->ImportTextures(
			FString::Printf(
				TEXT(R"json({"items":[{"file_path":"%s","destination_path":"%s","destination_name":"T_Imported","replace_existing":true}]})json"),
				TextureImportSource,
				*ImportRoot),
			false),
		TEXT("ImportTextures replace_existing"));
	Test.TestTrue(TEXT("Replace-existing import completes"), ReplaceExistingResult.IsValid());

	const TSharedPtr<FJsonObject> MissingSourceResult = ParseJsonObject(
		Test,
		Subsystem->ImportAssets(
			FString::Printf(
				TEXT(R"json({"items":[{"file_path":"ImportSources/DoesNotExist.png","destination_path":"%s","destination_name":"Missing"}]})json"),
				*ImportRoot),
			false),
		TEXT("ImportAssets missing source"));
	Test.TestTrue(TEXT("Missing source import fails"), IsFailureResult(MissingSourceResult));

	const TSharedPtr<FJsonObject> UnsupportedMeshResult = ParseJsonObject(
		Test,
		Subsystem->ImportMeshes(
			FString::Printf(
				TEXT(R"json({"items":[{"file_path":"%s","destination_path":"%s","destination_name":"BadMesh","options":{"mesh_type":"static"}}]})json"),
				TextureImportSource,
				*ImportRoot),
			false),
		TEXT("ImportMeshes unsupported extension"));
	Test.TestTrue(TEXT("Unsupported mesh helper extension fails"), IsFailureResult(UnsupportedMeshResult));

	const TArray<FString> AssetsToSave = {TextureObjectPath, MeshObjectPath};
	const TSharedPtr<FJsonObject> SaveResult = ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray(AssetsToSave)),
		TEXT("Save imported assets"));
	if (SaveResult.IsValid() && SaveResult->HasTypedField<EJson::Boolean>(TEXT("saved")))
	{
		Test.TestTrue(TEXT("Save imported assets reports saved=true"), SaveResult->GetBoolField(TEXT("saved")));
	}

	Test.TestTrue(
		TEXT("Imported texture package exists after SaveAssets"),
		FPaths::FileExists(MakePackageFilename(TextureAssetPath)));
	Test.TestTrue(
		TEXT("Imported mesh package exists after SaveAssets"),
		FPaths::FileExists(MakePackageFilename(MeshAssetPath)));
	return true;
}

static bool RunMissingAssetCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString MissingAssetPath = TEXT("/Game/__GeneratedTests__/Missing/BP_NotFound.BP_NotFound");
	const TSharedPtr<FJsonObject> ExtractBlueprintResult = ParseJsonObject(
		Test,
		Subsystem->ExtractBlueprint(MissingAssetPath, TEXT("Variables"), TEXT("")),
		TEXT("ExtractBlueprint missing asset"));
	Test.TestTrue(TEXT("ExtractBlueprint missing asset returns an error"), HasErrorField(ExtractBlueprintResult));

	const TSharedPtr<FJsonObject> SaveAssetsResult = ParseJsonObject(
		Test,
		Subsystem->SaveAssets(TEXT("[\"/Game/__GeneratedTests__/Missing/BP_NotFound.BP_NotFound\"]")),
		TEXT("SaveAssets missing asset"));
	if (SaveAssetsResult.IsValid() && SaveAssetsResult->HasTypedField<EJson::Boolean>(TEXT("success")))
	{
		Test.TestFalse(TEXT("SaveAssets missing asset reports success=false"), SaveAssetsResult->GetBoolField(TEXT("success")));
	}

	return true;
}

static bool RunAbstractWidgetClassCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_AbstractClassGuard"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for abstract child guard"));

	const TSharedPtr<FJsonObject> BuildResult = ParseJsonObject(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"CanvasPanel","name":"RootCanvas","is_variable":true,"children":[{"class":"UserWidget","name":"TitleBarArea","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree rejects abstract child class"));

	Test.TestTrue(TEXT("BuildWidgetTree rejects abstract child classes"), IsFailureResult(BuildResult));

	FString Error;
	if (BuildResult.IsValid() && BuildResult->TryGetStringField(TEXT("error"), Error))
	{
		Test.TestTrue(TEXT("BuildWidgetTree reports an abstract-class error"), Error.Contains(TEXT("abstract")));
	}

	return true;
}

static bool RunBindWidgetParentCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_BindWidgetParent"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for BindWidget parent"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","children":[{"class":"HorizontalBox","name":"TitleBarArea","is_variable":true,"children":[{"class":"TextBlock","name":"TitleText","is_variable":true,"slot":{"Size":{"value":1,"sizeRule":"Fill"}}},{"class":"Button","name":"MinimizeButton","is_variable":true},{"class":"Button","name":"MaximizeButton","is_variable":true},{"class":"Button","name":"CloseButton","is_variable":true}]},{"class":"NamedSlot","name":"ContentSlot","is_variable":true,"slot":{"Size":{"value":1,"sizeRule":"Fill"}}}]})json"),
			false),
		TEXT("BuildWidgetTree for BindWidget parent"));

	if (!ReparentWidgetBlueprintForTest(Test, WidgetObjectPath, FixtureBindWidgetParentClassPath))
	{
		return false;
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ WidgetObjectPath })),
		TEXT("SaveAssets for BindWidget parent"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint for BindWidget parent"));

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("BindWidget parent widget blueprint exists"), WidgetBP);
	if (!WidgetBP)
	{
		return false;
	}

	auto HasGeneratedVariable = [WidgetBP](const TCHAR* VariableName)
	{
		return WidgetBP->GeneratedVariables.ContainsByPredicate([VariableName](const FBPVariableDescription& Variable)
		{
			return Variable.VarName == FName(VariableName);
		});
	};

	Test.TestFalse(TEXT("TitleBarArea uses native BindWidget property instead of generated variable"), HasGeneratedVariable(TEXT("TitleBarArea")));
	Test.TestFalse(TEXT("TitleText uses native BindWidget property instead of generated variable"), HasGeneratedVariable(TEXT("TitleText")));
	Test.TestFalse(TEXT("MinimizeButton uses native BindWidget property instead of generated variable"), HasGeneratedVariable(TEXT("MinimizeButton")));
	Test.TestFalse(TEXT("MaximizeButton uses native BindWidget property instead of generated variable"), HasGeneratedVariable(TEXT("MaximizeButton")));
	Test.TestFalse(TEXT("CloseButton uses native BindWidget property instead of generated variable"), HasGeneratedVariable(TEXT("CloseButton")));
	Test.TestFalse(TEXT("ContentSlot uses native BindWidget property instead of generated variable"), HasGeneratedVariable(TEXT("ContentSlot")));

	return true;
}

static bool RunWidgetRenameCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_RenameBindWidget"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for widget rename"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"CanvasPanel","name":"RootCanvas","children":[{"class":"Image","name":"Shortcuticon","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree for widget rename"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidget(
			WidgetObjectPath,
			TEXT("Shortcuticon"),
			TEXT(R"json({"name":"ShortcutIcon"})json"),
			TEXT("{}"),
			TEXT("{}"),
			false),
		TEXT("ModifyWidget rename"));

	if (!ReparentWidgetBlueprintForTest(Test, WidgetObjectPath, FixtureRenameBindWidgetParentClassPath))
	{
		return false;
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ WidgetObjectPath })),
		TEXT("SaveAssets after widget rename"));

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Renamed widget blueprint exists"), WidgetBP);
	if (!WidgetBP)
	{
		return false;
	}

	UWidget* RenamedWidget = WidgetBP->WidgetTree->FindWidget(TEXT("ShortcutIcon"));
	Test.TestNotNull(TEXT("Renamed widget exists"), RenamedWidget);
	if (RenamedWidget)
	{
		Test.TestEqual(TEXT("Renamed widget preserves requested casing"), RenamedWidget->GetName(), FString(TEXT("ShortcutIcon")));
	}

	const bool bHasGeneratedVariable = WidgetBP->GeneratedVariables.ContainsByPredicate([](const FBPVariableDescription& Variable)
	{
		return Variable.VarName == FName(TEXT("ShortcutIcon"));
	});
	Test.TestFalse(TEXT("Native BindWidget rename does not create generated variable"), bHasGeneratedVariable);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint after widget rename"));

	return true;
}

static bool RunWidgetSlotAliasCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_SlotAlias"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for slot alias"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","children":[{"class":"Border","name":"TitleBarArea","is_variable":true,"slot":{"Size":{"value":1,"sizeRule":"Fill"}}}]})json"),
			false),
		TEXT("BuildWidgetTree for slot alias"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidget(
			WidgetObjectPath,
			TEXT("TitleBarArea"),
			TEXT("{}"),
			TEXT(R"json({"Size":{"value":0,"sizeRule":"Auto"}})json"),
			TEXT("{}"),
			false),
		TEXT("ModifyWidget slot alias"));

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Slot alias widget blueprint exists"), WidgetBP);
	if (!WidgetBP)
	{
		return false;
	}

	UWidget* TitleBarArea = WidgetBP->WidgetTree->FindWidget(TEXT("TitleBarArea"));
	Test.TestNotNull(TEXT("TitleBarArea exists"), TitleBarArea);

	UVerticalBoxSlot* VerticalSlot = TitleBarArea ? Cast<UVerticalBoxSlot>(TitleBarArea->Slot) : nullptr;
	Test.TestNotNull(TEXT("TitleBarArea uses a VerticalBox slot"), VerticalSlot);
	if (VerticalSlot)
	{
		const FSlateChildSize SlotSize = VerticalSlot->GetSize();
		Test.TestEqual(TEXT("Auto alias maps to Automatic"), static_cast<int32>(SlotSize.SizeRule), static_cast<int32>(ESlateSizeRule::Automatic));
		Test.TestEqual(TEXT("Slot value override is applied"), SlotSize.Value, 0.0f);
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"CanvasPanel","name":"CanvasRoot","children":[{"class":"Border","name":"AnchoredPanel","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree for canvas slot alias"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidget(
			WidgetObjectPath,
			TEXT("AnchoredPanel"),
			TEXT("{}"),
			TEXT(R"json({"Anchors":{"Minimum":{"X":0.25,"Y":0.0},"Maximum":{"X":0.75,"Y":1.0}},"Offsets":{"Left":8.0,"Top":12.0,"Right":-16.0,"Bottom":-20.0},"Alignment":{"X":0.5,"Y":0.0},"AutoSize":true,"ZOrder":7})json"),
			TEXT("{}"),
			false),
		TEXT("ModifyWidget canvas slot aliases"));

	WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Canvas slot alias widget blueprint exists"), WidgetBP);
	if (!WidgetBP)
	{
		return false;
	}

	UWidget* AnchoredPanel = WidgetBP->WidgetTree->FindWidget(TEXT("AnchoredPanel"));
	Test.TestNotNull(TEXT("AnchoredPanel exists"), AnchoredPanel);

	UCanvasPanelSlot* CanvasSlot = AnchoredPanel ? Cast<UCanvasPanelSlot>(AnchoredPanel->Slot) : nullptr;
	Test.TestNotNull(TEXT("AnchoredPanel uses a CanvasPanel slot"), CanvasSlot);
	if (CanvasSlot)
	{
		Test.TestEqual(TEXT("Canvas anchor minimum X alias is applied"), CanvasSlot->GetAnchors().Minimum.X, 0.25);
		Test.TestEqual(TEXT("Canvas anchor maximum X alias is applied"), CanvasSlot->GetAnchors().Maximum.X, 0.75);
		Test.TestEqual(TEXT("Canvas offsets left alias is applied"), CanvasSlot->GetOffsets().Left, 8.0f);
		Test.TestEqual(TEXT("Canvas offsets top alias is applied"), CanvasSlot->GetOffsets().Top, 12.0f);
		Test.TestEqual(TEXT("Canvas offsets right alias is applied"), CanvasSlot->GetOffsets().Right, -16.0f);
		Test.TestEqual(TEXT("Canvas offsets bottom alias is applied"), CanvasSlot->GetOffsets().Bottom, -20.0f);
		Test.TestEqual(TEXT("Canvas alignment X alias is applied"), CanvasSlot->GetAlignment().X, 0.5);
		Test.TestEqual(TEXT("Canvas alignment Y alias is applied"), CanvasSlot->GetAlignment().Y, 0.0);
		Test.TestTrue(TEXT("Canvas autosize alias is applied"), CanvasSlot->GetAutoSize());
		Test.TestEqual(TEXT("Canvas ZOrder alias is applied"), CanvasSlot->GetZOrder(), 7);
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint after slot alias"));

	return true;
}

static bool RunWidgetVariableAndClassDefaultsCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_StyledWindow"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for widget defaults"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","children":[{"class":"Image","name":"TitleBarBg","properties":{"RenderOpacity":0.75}},{"class":"TextBlock","name":"TitleText","properties":{"Text":"Window Title"}}]})json"),
			false),
		TEXT("BuildWidgetTree for widget defaults"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintMembers(
			WidgetObjectPath,
			TEXT("reparent"),
			FString::Printf(TEXT(R"json({"parentClassPath":"%s"})json"), FixtureStyledWidgetParentClassPath),
			false),
		TEXT("ModifyBlueprintMembers reparent styled widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidget(
			WidgetObjectPath,
			TEXT("TitleBarBg"),
			TEXT("{}"),
			TEXT("{}"),
			TEXT(R"json({"is_variable":true})json"),
			false),
		TEXT("ModifyWidget toggles is_variable"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("patch_widget"),
			TEXT(R"json({"widget_name":"TitleText","is_variable":true})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure patch_widget toggles is_variable"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("patch_class_defaults"),
			TEXT(R"json({"classDefaults":{"ActiveTitleBarMaterial":"/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial","InactiveTitleBarMaterial":"/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"}})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure patch_class_defaults"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("patch_class_defaults"),
			TEXT(R"json({"class_defaults":{"ActiveTitleBarMaterial":"/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"}})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure patch_class_defaults snake_case"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ WidgetObjectPath })),
		TEXT("SaveAssets for widget defaults"));

	// Verify CDO values survive patch_class_defaults without an explicit compile.
	// patch_class_defaults no longer triggers an internal compile, so values must
	// be present on the CDO immediately after patching.
	{
		UWidgetBlueprint* PreCompileBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
		const UObject* PreCompileCDO = PreCompileBP && PreCompileBP->GeneratedClass
			? PreCompileBP->GeneratedClass->GetDefaultObject(false) : nullptr;
		Test.TestNotNull(TEXT("CDO exists after patch_class_defaults (before compile)"), PreCompileCDO);
		if (PreCompileCDO)
		{
			const FObjectPropertyBase* PreActiveProp = CastField<FObjectPropertyBase>(
				PreCompileCDO->GetClass()->FindPropertyByName(TEXT("ActiveTitleBarMaterial")));
			Test.TestNotNull(TEXT("ActiveTitleBarMaterial property found before compile"), PreActiveProp);
			if (PreActiveProp)
			{
				const UObject* PreActiveVal = PreActiveProp->GetObjectPropertyValue_InContainer(PreCompileCDO);
				Test.TestEqual(TEXT("ActiveTitleBarMaterial survives patch without compile"),
					GetPathNameSafe(PreActiveVal), FString(DefaultMaterialPath));
			}
		}
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint after widget defaults"));

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Styled widget blueprint exists"), WidgetBP);
	if (!WidgetBP)
	{
		return false;
	}

	UImage* TitleBarBg = WidgetBP->WidgetTree ? Cast<UImage>(WidgetBP->WidgetTree->FindWidget(TEXT("TitleBarBg"))) : nullptr;
	UTextBlock* TitleText = WidgetBP->WidgetTree ? Cast<UTextBlock>(WidgetBP->WidgetTree->FindWidget(TEXT("TitleText"))) : nullptr;
	Test.TestNotNull(TEXT("TitleBarBg exists"), TitleBarBg);
	Test.TestNotNull(TEXT("TitleText exists"), TitleText);
	if (TitleBarBg)
	{
		Test.TestTrue(TEXT("ModifyWidget sets bIsVariable on existing widgets"), TitleBarBg->bIsVariable);
		Test.TestEqual(TEXT("patch_class_defaults does not mutate widget template properties"), TitleBarBg->GetRenderOpacity(), 0.75f);
	}
	if (TitleText)
	{
		Test.TestTrue(TEXT("patch_widget accepts is_variable aliases"), TitleText->bIsVariable);
	}

	const bool bHasGeneratedTitleBarVariable = WidgetBP->GeneratedVariables.ContainsByPredicate([](const FBPVariableDescription& Variable)
	{
		return Variable.VarName == FName(TEXT("TitleBarBg"));
	});
	const bool bHasGeneratedTitleTextVariable = WidgetBP->GeneratedVariables.ContainsByPredicate([](const FBPVariableDescription& Variable)
	{
		return Variable.VarName == FName(TEXT("TitleText"));
	});
	Test.TestFalse(TEXT("Native BindWidget TitleBarBg still avoids generated variables"), bHasGeneratedTitleBarVariable);
	Test.TestFalse(TEXT("Native BindWidget TitleText still avoids generated variables"), bHasGeneratedTitleTextVariable);

	const UObject* GeneratedDefaults = WidgetBP->GeneratedClass ? WidgetBP->GeneratedClass->GetDefaultObject(false) : nullptr;
	Test.TestNotNull(TEXT("Generated widget class defaults exist"), GeneratedDefaults);
	if (GeneratedDefaults)
	{
		const FObjectPropertyBase* ActiveMaterialProperty = CastField<FObjectPropertyBase>(GeneratedDefaults->GetClass()->FindPropertyByName(TEXT("ActiveTitleBarMaterial")));
		const FObjectPropertyBase* InactiveMaterialProperty = CastField<FObjectPropertyBase>(GeneratedDefaults->GetClass()->FindPropertyByName(TEXT("InactiveTitleBarMaterial")));
		Test.TestNotNull(TEXT("ActiveTitleBarMaterial default property exists"), ActiveMaterialProperty);
		Test.TestNotNull(TEXT("InactiveTitleBarMaterial default property exists"), InactiveMaterialProperty);
		if (ActiveMaterialProperty)
		{
			const UObject* ActiveMaterial = ActiveMaterialProperty->GetObjectPropertyValue_InContainer(GeneratedDefaults);
			Test.TestEqual(TEXT("ActiveTitleBarMaterial default patched"), GetPathNameSafe(ActiveMaterial), FString(DefaultMaterialPath));
		}
		if (InactiveMaterialProperty)
		{
			const UObject* InactiveMaterial = InactiveMaterialProperty->GetObjectPropertyValue_InContainer(GeneratedDefaults);
			Test.TestEqual(TEXT("InactiveTitleBarMaterial default patched"), GetPathNameSafe(InactiveMaterial), FString(DefaultMaterialPath));
		}
	}

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath, true),
		TEXT("ExtractWidgetBlueprint include_class_defaults"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> ClassDefaultsJson;
	Test.TestTrue(TEXT("ExtractWidgetBlueprint surfaces classDefaults"), TryGetObjectFieldCopy(ExtractResult, TEXT("classDefaults"), ClassDefaultsJson) && ClassDefaultsJson.IsValid());
	FString ExtractedParentClassPath;
	Test.TestTrue(TEXT("ExtractWidgetBlueprint surfaces the resolved parentClassPath"), ExtractResult->TryGetStringField(TEXT("parentClassPath"), ExtractedParentClassPath));
	Test.TestEqual(TEXT("Short-name widget parent resolution preserves the project class path"), ExtractedParentClassPath, FString(FixtureStyledWidgetParentClassPath));
	if (ClassDefaultsJson.IsValid())
	{
		FString ActiveDefaultPath;
		Test.TestTrue(TEXT("classDefaults contains ActiveTitleBarMaterial"), ClassDefaultsJson->TryGetStringField(TEXT("ActiveTitleBarMaterial"), ActiveDefaultPath));
		if (!ActiveDefaultPath.IsEmpty())
		{
			Test.TestEqual(TEXT("classDefaults serializes object references as object paths"), ActiveDefaultPath, FString(DefaultMaterialPath));
		}
	}

	return true;
}

static bool RunWidgetBatchClassDefaultsCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_BatchClassDefaults"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for batch class defaults"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","is_variable":true,"children":[{"class":"Image","name":"TitleBarBg","properties":{"RenderOpacity":0.5}},{"class":"TextBlock","name":"TitleText","properties":{"Text":"Before Batch"}}]})json"),
			false),
		TEXT("BuildWidgetTree for batch class defaults"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintMembers(
			WidgetObjectPath,
			TEXT("reparent"),
			FString::Printf(TEXT(R"json({"parentClassPath":"%s"})json"), FixtureStyledWidgetParentClassPath),
			false),
		TEXT("ModifyBlueprintMembers reparent batch class defaults widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ WidgetObjectPath })),
		TEXT("SaveAssets for batch class defaults"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("batch"),
			FString::Printf(
				TEXT(R"json({"operations":[{"operation":"insert_child","parent_widget_name":"WindowRoot","child_widget":{"class":"TextBlock","name":"FooterText","properties":{"Text":"Footer"}}},{"operation":"patch_widget","widget_name":"TitleText","properties":{"Text":"After Batch"}},{"operation":"patch_class_defaults","classDefaults":{"ActiveTitleBarMaterial":"%s","InactiveTitleBarMaterial":"%s"}},{"operation":"patch_class_defaults","class_defaults":{"ActiveTitleBarMaterial":"%s"}}]})json"),
				DefaultMaterialPath,
				DefaultMaterialPath,
				WorldGridMaterialPath),
			false),
		TEXT("ModifyWidgetBlueprintStructure batch with patch_class_defaults"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint after batch class defaults"));

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath, true),
		TEXT("ExtractWidgetBlueprint after batch class defaults"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> RootWidgetJson;
	Test.TestTrue(TEXT("Batch class defaults extract returns a rootWidget"), TryGetObjectFieldCopy(ExtractResult, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid());
	if (!RootWidgetJson.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> FooterTextNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/FooterText"));
	Test.TestNotNull(TEXT("Batch structural insert is preserved"), FooterTextNode.Get());

	const TSharedPtr<FJsonObject> TitleTextNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/TitleText"));
	Test.TestNotNull(TEXT("Batch patch_widget target exists"), TitleTextNode.Get());
	if (TitleTextNode.IsValid())
	{
		TSharedPtr<FJsonObject> TitleProperties;
		Test.TestTrue(TEXT("Batch patch_widget target surfaces properties"), TryGetObjectFieldCopy(TitleTextNode, TEXT("properties"), TitleProperties) && TitleProperties.IsValid());
		if (TitleProperties.IsValid())
		{
			FString TitleText;
			Test.TestTrue(TEXT("Batch patch_widget target surfaces Text"), TitleProperties->TryGetStringField(TEXT("Text"), TitleText));
			Test.TestEqual(TEXT("Batch patch_widget runs after structural ops"), TitleText, FString(TEXT("After Batch")));
		}
	}

	TSharedPtr<FJsonObject> ClassDefaultsJson;
	Test.TestTrue(TEXT("Batch class defaults extract surfaces classDefaults"), TryGetObjectFieldCopy(ExtractResult, TEXT("classDefaults"), ClassDefaultsJson) && ClassDefaultsJson.IsValid());
	if (ClassDefaultsJson.IsValid())
	{
		FString ActiveMaterialPath;
		FString InactiveMaterialPath;
		Test.TestTrue(TEXT("Batch class defaults extract surfaces ActiveTitleBarMaterial"), ClassDefaultsJson->TryGetStringField(TEXT("ActiveTitleBarMaterial"), ActiveMaterialPath));
		Test.TestTrue(TEXT("Batch class defaults extract surfaces InactiveTitleBarMaterial"), ClassDefaultsJson->TryGetStringField(TEXT("InactiveTitleBarMaterial"), InactiveMaterialPath));
		Test.TestEqual(TEXT("Later batch patch_class_defaults entries win per key"), ActiveMaterialPath, FString(WorldGridMaterialPath));
		Test.TestEqual(TEXT("Unshadowed batch class default keys are preserved"), InactiveMaterialPath, FString(DefaultMaterialPath));
	}

	return true;
}

static bool RunNonVariableWidgetSelectorCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_NonVariableSelectors"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for non-variable selectors"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","is_variable":true,"children":[{"class":"TextBlock","name":"NameOnlyText","properties":{"Text":"Name Before"}},{"class":"VerticalBox","name":"ContentRoot","children":[{"class":"TextBlock","name":"PathText","properties":{"Text":"Path Before"}},{"class":"TextBlock","name":"PatchByNameText","properties":{"Text":"Patch Name Before"}},{"class":"TextBlock","name":"PatchByPathText","properties":{"Text":"Patch Path Before"}},{"class":"TextBlock","name":"RemoveByNameText","properties":{"Text":"Remove Name"}},{"class":"TextBlock","name":"RemoveByPathText","properties":{"Text":"Remove Path"}}]}]})json"),
			false),
		TEXT("BuildWidgetTree for non-variable selectors"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidget(
			WidgetObjectPath,
			TEXT("NameOnlyText"),
			TEXT(R"json({"Text":"Name After"})json"),
			TEXT("{}"),
			TEXT("{}"),
			false),
		TEXT("ModifyWidget by widget_name on non-variable widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidget(
			WidgetObjectPath,
			TEXT("WindowRoot/ContentRoot/PathText"),
			TEXT(R"json({"Text":"Path After"})json"),
			TEXT("{}"),
			TEXT("{}"),
			false),
		TEXT("ModifyWidget by widget_path on non-variable widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("patch_widget"),
			TEXT(R"json({"widget_name":"PatchByNameText","properties":{"Text":"Patch Name After"}})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure patch_widget by widget_name on non-variable widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("patch_widget"),
			TEXT(R"json({"widget_path":"WindowRoot/ContentRoot/PatchByPathText","properties":{"Text":"Patch Path After"}})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure patch_widget by widget_path on non-variable widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("remove_widget"),
			TEXT(R"json({"widget_name":"RemoveByNameText"})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure remove_widget by widget_name on non-variable widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("remove_widget"),
			TEXT(R"json({"widget_path":"WindowRoot/ContentRoot/RemoveByPathText"})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure remove_widget by widget_path on non-variable widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint after non-variable selector mutations"));

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath),
		TEXT("ExtractWidgetBlueprint after non-variable selector mutations"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> RootWidgetJson;
	Test.TestTrue(TEXT("Non-variable selector extract returns a rootWidget"), TryGetObjectFieldCopy(ExtractResult, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid());
	if (!RootWidgetJson.IsValid())
	{
		return false;
	}

	const auto ExpectTextAtPath = [&Test, &RootWidgetJson](const TCHAR* WidgetPath, const TCHAR* ExpectedText, const TCHAR* AssertionPrefix)
	{
		const TSharedPtr<FJsonObject> Node = FindWidgetNodeByPath(RootWidgetJson, WidgetPath);
		Test.TestNotNull(*FString::Printf(TEXT("%s node exists"), AssertionPrefix), Node.Get());
		if (!Node.IsValid())
		{
			return;
		}

		TSharedPtr<FJsonObject> PropertiesJson;
		Test.TestTrue(*FString::Printf(TEXT("%s properties exist"), AssertionPrefix), TryGetObjectFieldCopy(Node, TEXT("properties"), PropertiesJson) && PropertiesJson.IsValid());
		if (!PropertiesJson.IsValid())
		{
			return;
		}

		FString ActualText;
		Test.TestTrue(*FString::Printf(TEXT("%s text exists"), AssertionPrefix), PropertiesJson->TryGetStringField(TEXT("Text"), ActualText));
		if (!ActualText.IsEmpty())
		{
			Test.TestEqual(*FString::Printf(TEXT("%s text matches"), AssertionPrefix), ActualText, FString(ExpectedText));
		}
	};

	ExpectTextAtPath(TEXT("WindowRoot/NameOnlyText"), TEXT("Name After"), TEXT("modify_widget by name"));
	ExpectTextAtPath(TEXT("WindowRoot/ContentRoot/PathText"), TEXT("Path After"), TEXT("modify_widget by path"));
	ExpectTextAtPath(TEXT("WindowRoot/ContentRoot/PatchByNameText"), TEXT("Patch Name After"), TEXT("patch_widget by name"));
	ExpectTextAtPath(TEXT("WindowRoot/ContentRoot/PatchByPathText"), TEXT("Patch Path After"), TEXT("patch_widget by path"));

	const TSharedPtr<FJsonObject> RemovedByNameNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/ContentRoot/RemoveByNameText"));
	const TSharedPtr<FJsonObject> RemovedByPathNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/ContentRoot/RemoveByPathText"));
	Test.TestNull(TEXT("remove_widget by widget_name deletes non-variable children"), RemovedByNameNode.Get());
	Test.TestNull(TEXT("remove_widget by widget_path deletes non-variable children"), RemovedByPathNode.Get());

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Non-variable selector widget blueprint exists"), WidgetBP);
	if (WidgetBP)
	{
		Test.TestFalse(
			TEXT("WidgetVariableNameToGuidMap prunes removed non-variable widget names (widget_name selector)"),
			WidgetBP->WidgetVariableNameToGuidMap.Contains(FName(TEXT("RemoveByNameText"))));
		Test.TestFalse(
			TEXT("WidgetVariableNameToGuidMap prunes removed non-variable widget names (widget_path selector)"),
			WidgetBP->WidgetVariableNameToGuidMap.Contains(FName(TEXT("RemoveByPathText"))));
	}

	return true;
}

static bool RunWidgetFontCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString FontFilePath = FindSystemFontFile();
	Test.TestFalse(TEXT("A Windows system font file is available for import coverage"), FontFilePath.IsEmpty());
	if (FontFilePath.IsEmpty())
	{
		return false;
	}

	const FString FontDestinationPath = MakeUniqueAssetPath(TEXT("Fonts"));
	const FString FontAssetPath = FontDestinationPath + TEXT("/F_WindowRuntime");
	const FString FontAssetObjectPath = MakeObjectPath(FontAssetPath);
	const FString PrimaryFaceName = TEXT("Face_One");
	const FString SecondaryFaceName = TEXT("Face_Two");

	const FString FontImportPayload = FString::Printf(
		TEXT(R"json({"items":[{"file_path":"%s","destination_path":"%s","destination_name":"%s","entry_name":"Regular","replace_existing":true}],"font_asset_path":"%s"})json"),
		*FontFilePath.ReplaceCharWithEscapedChar(),
		*FontDestinationPath,
		*PrimaryFaceName,
		*FontAssetPath);

	ExpectValidateOnlyResult(
		Test,
		Subsystem->ImportFonts(FontImportPayload, true),
		TEXT("ImportFonts validate_only"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ImportFonts(FontImportPayload, false),
		TEXT("ImportFonts create runtime font"));

	const FString SecondImportPayload = FString::Printf(
		TEXT(R"json({"items":[{"file_path":"%s","destination_path":"%s","destination_name":"%s","entry_name":"Regular","replace_existing":true}],"font_asset_path":"%s"})json"),
		*FontFilePath.ReplaceCharWithEscapedChar(),
		*FontDestinationPath,
		*SecondaryFaceName,
		*FontAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->ImportFonts(SecondImportPayload, false),
		TEXT("ImportFonts updates existing typeface entry deterministically"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ FontAssetObjectPath })),
		TEXT("SaveAssets for imported runtime font"));

	UFont* RuntimeFont = Cast<UFont>(ResolveAssetByPath(FontAssetObjectPath));
	Test.TestNotNull(TEXT("Runtime UFont asset exists"), RuntimeFont);
	if (RuntimeFont)
	{
		Test.TestEqual(TEXT("Runtime font uses runtime cache"), static_cast<int32>(RuntimeFont->FontCacheType), static_cast<int32>(EFontCacheType::Runtime));
#if UE_VERSION_NEWER_THAN_OR_EQUAL(5, 7, 0)
		const FCompositeFont& CompositeFont = RuntimeFont->GetInternalCompositeFont();
#else
		const FCompositeFont& CompositeFont = RuntimeFont->CompositeFont;
#endif
		Test.TestEqual(TEXT("Repeated entry_name updates keep a single typeface entry"), CompositeFont.DefaultTypeface.Fonts.Num(), 1);
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_Fonts"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for font coverage"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","children":[{"class":"TextBlock","name":"TitleText","is_variable":true,"properties":{"Text":"Window"}},{"class":"Image","name":"IconImage","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree for font coverage"));

	const FString ApplyFontsPayload = FString::Printf(
		TEXT(R"json({"targets":[{"widget_name":"TitleText","font_asset":"%s","typeface":"Regular","size":28},{"widget_name":"IconImage","font_asset":"%s","typeface":"Regular","size":18},{"widget_path":"WindowRoot/MissingText","font_asset":"%s","typeface":"Regular","size":16}]})json"),
		*FontAssetPath,
		*FontAssetPath,
		*FontAssetPath);

	ExpectValidateOnlyResult(
		Test,
		Subsystem->ApplyWidgetFonts(WidgetObjectPath, ApplyFontsPayload, true),
		TEXT("ApplyWidgetFonts validate_only"));

	const TSharedPtr<FJsonObject> ApplyFontsResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ApplyWidgetFonts(WidgetObjectPath, ApplyFontsPayload, false),
		TEXT("ApplyWidgetFonts"));
	if (!ApplyFontsResult.IsValid())
	{
		return false;
	}

	if (ApplyFontsResult->HasTypedField<EJson::Number>(TEXT("warningCount")))
	{
		Test.TestEqual(TEXT("ApplyWidgetFonts reports warnings for unmatched/non-text targets"), static_cast<int32>(ApplyFontsResult->GetNumberField(TEXT("warningCount"))), 2);
	}

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Font coverage widget blueprint exists"), WidgetBP);
	if (!WidgetBP)
	{
		return false;
	}

	UTextBlock* TitleText = WidgetBP->WidgetTree ? Cast<UTextBlock>(WidgetBP->WidgetTree->FindWidget(TEXT("TitleText"))) : nullptr;
	Test.TestNotNull(TEXT("TitleText exists after font application"), TitleText);
	if (TitleText)
	{
		Test.TestEqual(TEXT("TitleText font asset updated"), GetPathNameSafe(TitleText->GetFont().FontObject), FontAssetObjectPath);
		Test.TestEqual(TEXT("TitleText typeface updated"), TitleText->GetFont().TypefaceFontName, FName(TEXT("Regular")));
		Test.TestEqual(TEXT("TitleText size updated"), TitleText->GetFont().Size, 28.0f);
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint after font application"));

	return true;
}

static bool RunWidgetStructureCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_StructureOps"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);
	const FString AssetChildWidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_StructureAssetChild"));
	const FString AssetChildWidgetObjectPath = MakeObjectPath(AssetChildWidgetAssetPath);
	const FString GeneratedChildWidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_StructureGeneratedChild"));
	const FString GeneratedChildWidgetObjectPath = MakeObjectPath(GeneratedChildWidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for structure ops"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			AssetChildWidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for asset child widget"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			GeneratedChildWidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for generated class child widget"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","is_variable":true,"children":[{"class":"HorizontalBox","name":"HeaderRow","is_variable":true,"children":[{"class":"TextBlock","name":"TitleText","is_variable":true,"properties":{"Text":"Window"}},{"class":"Border","name":"ActionHost","is_variable":true}]},{"class":"VerticalBox","name":"ContentRoot","is_variable":true,"children":[{"class":"TextBlock","name":"BodyText","is_variable":true,"properties":{"Text":"Body"}}]}]})json"),
			false),
		TEXT("BuildWidgetTree for structure ops"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ AssetChildWidgetObjectPath, GeneratedChildWidgetObjectPath })),
		TEXT("SaveAssets for child widget class references"));

	ExpectValidateOnlyResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("batch"),
			FString::Printf(
				TEXT(R"json({"operations":[{"operation":"insert_child","parent_widget_path":"WindowRoot/HeaderRow","child_widget":{"class":"Button","name":"HelpButton","is_variable":true}},{"operation":"insert_child","parent_widget_path":"WindowRoot/ContentRoot","child_widget":{"class":"%s","name":"AssetPanel","is_variable":true}},{"operation":"insert_child","parent_widget_path":"WindowRoot/ContentRoot","child_widget":{"class":"%s_C","name":"GeneratedPanel","is_variable":true}},{"operation":"wrap_widget","widget_path":"WindowRoot/ContentRoot/BodyText","wrapper_widget":{"class":"Border","name":"BodyFrame"}},{"operation":"move_widget","widget_path":"WindowRoot/HeaderRow/ActionHost","new_parent_widget_path":"WindowRoot/ContentRoot","index":0},{"operation":"patch_widget","widget_path":"WindowRoot/HeaderRow/TitleText","properties":{"Text":"Window Title"}}]})json"),
				*AssetChildWidgetAssetPath,
				*GeneratedChildWidgetObjectPath),
			true),
		TEXT("ModifyWidgetBlueprintStructure validate_only batch"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("batch"),
			FString::Printf(
				TEXT(R"json({"operations":[{"operation":"insert_child","parent_widget_path":"WindowRoot/HeaderRow","child_widget":{"class":"Button","name":"HelpButton","is_variable":true}},{"operation":"insert_child","parent_widget_path":"WindowRoot/ContentRoot","child_widget":{"class":"%s","name":"AssetPanel","is_variable":true}},{"operation":"insert_child","parent_widget_path":"WindowRoot/ContentRoot","child_widget":{"class":"%s_C","name":"GeneratedPanel","is_variable":true}},{"operation":"wrap_widget","widget_path":"WindowRoot/ContentRoot/BodyText","wrapper_widget":{"class":"Border","name":"BodyFrame"}},{"operation":"move_widget","widget_path":"WindowRoot/HeaderRow/ActionHost","new_parent_widget_path":"WindowRoot/ContentRoot","index":0},{"operation":"patch_widget","widget_path":"WindowRoot/HeaderRow/TitleText","properties":{"Text":"Window Title"}}]})json"),
				*AssetChildWidgetAssetPath,
				*GeneratedChildWidgetObjectPath),
			false),
		TEXT("ModifyWidgetBlueprintStructure batch"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("replace_widget_class"),
			TEXT(R"json({"widget_path":"WindowRoot/ContentRoot/ActionHost","replacement_class":"SizeBox","preserve_properties":false})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure replace_widget_class"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("remove_widget"),
			TEXT(R"json({"widget_path":"WindowRoot/HeaderRow/HelpButton"})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure remove_widget"));

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath),
		TEXT("ExtractWidgetBlueprint after structure ops"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	Test.TestEqual(
		TEXT("ExtractWidgetBlueprint reports the expected operation"),
		ExtractResult->GetStringField(TEXT("operation")),
		FString(TEXT("extract_widget_blueprint")));

	TSharedPtr<FJsonObject> RootWidgetJson;
	Test.TestTrue(TEXT("ExtractWidgetBlueprint returns a rootWidget"), TryGetObjectFieldCopy(ExtractResult, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid());
	if (!RootWidgetJson.IsValid())
	{
		return false;
	}

	FString RootWidgetPath;
	Test.TestTrue(TEXT("Root widget exposes widgetPath"), RootWidgetJson->TryGetStringField(TEXT("widgetPath"), RootWidgetPath));
	Test.TestEqual(TEXT("Root widgetPath is annotated"), RootWidgetPath, FString(TEXT("WindowRoot")));

	const TSharedPtr<FJsonObject> ActionHostNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/ContentRoot/ActionHost"));
	Test.TestNotNull(TEXT("Moved ActionHost exists under ContentRoot"), ActionHostNode.Get());
	if (ActionHostNode.IsValid())
	{
		FString WidgetClass;
		ActionHostNode->TryGetStringField(TEXT("class"), WidgetClass);
		Test.TestEqual(TEXT("replace_widget_class updates the class"), WidgetClass, FString(TEXT("SizeBox")));
	}

	const TSharedPtr<FJsonObject> BodyTextNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/ContentRoot/BodyFrame/BodyText"));
	Test.TestNotNull(TEXT("wrap_widget preserves the child inside the wrapper"), BodyTextNode.Get());
	const TSharedPtr<FJsonObject> AssetPanelNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/ContentRoot/AssetPanel"));
	Test.TestNotNull(TEXT("Custom widget insert accepts Blueprint asset package paths"), AssetPanelNode.Get());
	const TSharedPtr<FJsonObject> GeneratedPanelNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/ContentRoot/GeneratedPanel"));
	Test.TestNotNull(TEXT("Custom widget insert accepts generated Blueprint class paths"), GeneratedPanelNode.Get());

	const TSharedPtr<FJsonObject> RemovedHelpButton = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/HeaderRow/HelpButton"));
	Test.TestNull(TEXT("remove_widget removes the HelpButton"), RemovedHelpButton.Get());

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint after structure ops"));

	return true;
}

static bool RunBlueprintGraphAuthoringCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString BlueprintAssetPath = MakeUniqueAssetPath(TEXT("BP_GraphAuthoring"));
	const FString BlueprintObjectPath = MakeObjectPath(BlueprintAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateBlueprint(
			BlueprintAssetPath,
			TEXT("/Script/Engine.Actor"),
			TEXT("{}"),
			false),
		TEXT("CreateBlueprint for graph authoring"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintGraphs(
			BlueprintObjectPath,
			TEXT("upsert_function_graphs"),
			TEXT(R"json({"functionGraphs":[{"graphName":"Alpha","category":"Smoke"}]})json"),
			false),
		TEXT("ModifyBlueprintGraphs upsert Alpha"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintGraphs(
			BlueprintObjectPath,
			TEXT("upsert_function_graphs"),
			TEXT(R"json({"functionGraphs":[{"graphName":"Beta","category":"Smoke"}]})json"),
			false),
		TEXT("ModifyBlueprintGraphs upsert Beta"));

	const TSharedPtr<FJsonObject> CompileGraphResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintGraphs(
			BlueprintObjectPath,
			TEXT("compile"),
			TEXT("{}"),
			false),
		TEXT("ModifyBlueprintGraphs compile"));
	if (!CompileGraphResult.IsValid())
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* FunctionGraphs = nullptr;
	Test.TestTrue(TEXT("ModifyBlueprintGraphs compile returns function graph names"), CompileGraphResult->TryGetArrayField(TEXT("functionGraphs"), FunctionGraphs) && FunctionGraphs != nullptr);
	if (!FunctionGraphs)
	{
		return false;
	}

	bool bHasAlpha = false;
	bool bHasBeta = false;
	for (const TSharedPtr<FJsonValue>& GraphValue : *FunctionGraphs)
	{
		const FString GraphName = GraphValue.IsValid() ? GraphValue->AsString() : FString();
		if (GraphName.IsEmpty())
		{
			continue;
		}

		if (GraphName == TEXT("Alpha"))
		{
			bHasAlpha = true;
		}
		else if (GraphName == TEXT("Beta"))
		{
			bHasBeta = true;
		}
	}
	Test.TestTrue(TEXT("upsert_function_graphs adds the first named graph"), bHasAlpha);
	Test.TestTrue(TEXT("upsert_function_graphs preserves unrelated graphs"), bHasBeta);

	return true;
}

static bool RunWidgetStructureFailureRecoveryCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_StructureFailure"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for structure failure"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","is_variable":true,"children":[{"class":"VerticalBox","name":"ContentRoot","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree for structure failure"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ WidgetAssetPath })),
		TEXT("SaveAssets baseline structure failure widget"));

	const TSharedPtr<FJsonObject> FailureResult = ExpectFailureResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("insert_child"),
			TEXT(R"json({"parent_widget_path":"WindowRoot/MissingParent","child_widget":{"class":"TextBlock","name":"ShouldNotExist","properties":{"Text":"Unexpected"}}})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure invalid insert_child"));
	if (!FailureResult.IsValid())
	{
		return false;
	}

	Test.TestEqual(
		TEXT("Invalid widget structure mutation reports the expected operation"),
		FailureResult->GetStringField(TEXT("operation")),
		FString(TEXT("modify_widget_blueprint")));

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath),
		TEXT("ExtractWidgetBlueprint after invalid structure mutation"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> RootWidgetJson;
	Test.TestTrue(TEXT("ExtractWidgetBlueprint returns a rootWidget after invalid structure mutation"), TryGetObjectFieldCopy(ExtractResult, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid());
	if (!RootWidgetJson.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> ContentRootNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/ContentRoot"));
	Test.TestNotNull(TEXT("Saved widget root remains extractable after invalid structure mutation"), ContentRootNode.Get());
	const TSharedPtr<FJsonObject> MissingChildNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/MissingParent/ShouldNotExist"));
	Test.TestNull(TEXT("Invalid widget child is not persisted after structure failure"), MissingChildNode.Get());

	return true;
}

static bool RunWidgetCompileFailureExtractionCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_CompileFailureExtract"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("UserWidget")),
		TEXT("CreateWidgetBlueprint for compile failure extraction"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"CanvasPanel","name":"WindowRoot","is_variable":true,"children":[{"class":"ListView","name":"BrokenListView","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree for compile failure extraction"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ WidgetObjectPath })),
		TEXT("SaveAssets before compile failure extraction"));

	UWidgetBlueprint* CompileFailureWidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Compile failure widget blueprint exists before compile"), CompileFailureWidgetBP);
	if (!CompileFailureWidgetBP)
	{
		return false;
	}

	FCompilerResultsLog CompileResults;
	CompileResults.bSilentMode = true;
	CompileResults.bAnnotateMentionedNodes = false;
	FKismetEditorUtilities::CompileBlueprint(
		CompileFailureWidgetBP,
		EBlueprintCompileOptions::SkipGarbageCollection,
		&CompileResults);
	Test.TestEqual(
		TEXT("Compile failure widget blueprint settles in Error status"),
		static_cast<int32>(CompileFailureWidgetBP->Status),
		static_cast<int32>(BS_Error));
	Test.TestTrue(
		TEXT("Silent compile captures widget compile errors for extract coverage"),
		CompileResults.NumErrors > 0);

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath),
		TEXT("ExtractWidgetBlueprint after compile failure"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> CompileJson;
	Test.TestTrue(TEXT("ExtractWidgetBlueprint includes a compile snapshot after compile failure"), TryGetObjectFieldCopy(ExtractResult, TEXT("compile"), CompileJson) && CompileJson.IsValid());
	if (CompileJson.IsValid())
	{
		Test.TestEqual(TEXT("Compile snapshot reports Error status"), CompileJson->GetStringField(TEXT("status")), FString(TEXT("Error")));
		const TArray<TSharedPtr<FJsonValue>>* Errors = nullptr;
		Test.TestTrue(TEXT("Compile snapshot includes compile errors"), CompileJson->TryGetArrayField(TEXT("errors"), Errors) && Errors != nullptr && Errors->Num() > 0);
		const TArray<TSharedPtr<FJsonValue>>* Messages = nullptr;
		Test.TestTrue(TEXT("Compile snapshot includes normalized messages"), CompileJson->TryGetArrayField(TEXT("messages"), Messages) && Messages != nullptr && Messages->Num() > 0);
	}

	FString WidgetTreeStatus;
	Test.TestTrue(TEXT("ExtractWidgetBlueprint includes widgetTreeStatus after compile failure"), ExtractResult->TryGetStringField(TEXT("widgetTreeStatus"), WidgetTreeStatus) && !WidgetTreeStatus.IsEmpty());

	TSharedPtr<FJsonObject> RootWidgetJson;
	const bool bHasRootWidget = TryGetObjectFieldCopy(ExtractResult, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid();
	if (bHasRootWidget)
	{
		Test.TestEqual(TEXT("Compile failure keeps a degraded live widget tree when available"), WidgetTreeStatus, FString(TEXT("ok")));
		const TSharedPtr<FJsonObject> BrokenListViewNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/BrokenListView"));
		Test.TestNotNull(TEXT("Degraded extract still returns the authored tree snapshot"), BrokenListViewNode.Get());
	}
	else
	{
		Test.TestTrue(TEXT("ExtractWidgetBlueprint still returns the rootWidget field when the tree cannot be recovered"), ExtractResult->HasField(TEXT("rootWidget")));
		FString WidgetTreeError;
		Test.TestTrue(TEXT("Missing rootWidget is accompanied by widgetTreeError"), ExtractResult->TryGetStringField(TEXT("widgetTreeError"), WidgetTreeError) && !WidgetTreeError.IsEmpty());
	}

	return true;
}

static bool RunOverrideCoupledWidgetPropertyCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_SizeBoxOverrides"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("/Script/UMG.UserWidget")),
		TEXT("CreateWidgetBlueprint for override-coupled property coverage"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","is_variable":true,"children":[{"class":"SizeBox","name":"ActionHost","is_variable":true,"children":[{"class":"TextBlock","name":"ActionLabel","is_variable":true,"properties":{"Text":"Action"}}]}]})json"),
			false),
		TEXT("BuildWidgetTree for override-coupled property coverage"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidget(
			WidgetObjectPath,
			TEXT("ActionHost"),
			TEXT(R"json({"WidthOverride":320.0,"HeightOverride":48.0,"MinDesiredHeight":24.0})json"),
			TEXT("{}"),
			TEXT("{}"),
			false),
		TEXT("ModifyWidget applies override-coupled SizeBox properties"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint after override-coupled SizeBox properties"));

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath),
		TEXT("ExtractWidgetBlueprint after override-coupled SizeBox properties"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> RootWidgetJson;
	Test.TestTrue(TEXT("Override-coupled extract returns a rootWidget"), TryGetObjectFieldCopy(ExtractResult, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid());
	if (!RootWidgetJson.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> ActionHostNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/ActionHost"));
	Test.TestNotNull(TEXT("SizeBox node is present after override-coupled patch"), ActionHostNode.Get());
	if (!ActionHostNode.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> PropertiesJson;
	Test.TestTrue(TEXT("SizeBox extract includes patched properties"), TryGetObjectFieldCopy(ActionHostNode, TEXT("properties"), PropertiesJson) && PropertiesJson.IsValid());
	if (!PropertiesJson.IsValid())
	{
		return false;
	}

	Test.TestTrue(TEXT("WidthOverride was applied"), FMath::IsNearlyEqual(PropertiesJson->GetNumberField(TEXT("WidthOverride")), 320.0));
	Test.TestTrue(TEXT("HeightOverride was applied"), FMath::IsNearlyEqual(PropertiesJson->GetNumberField(TEXT("HeightOverride")), 48.0));
	Test.TestTrue(TEXT("MinDesiredHeight was applied"), FMath::IsNearlyEqual(PropertiesJson->GetNumberField(TEXT("MinDesiredHeight")), 24.0));

	bool bOverrideWidth = false;
	bool bOverrideHeight = false;
	bool bOverrideMinDesiredHeight = false;
	Test.TestTrue(TEXT("bOverride_WidthOverride auto-enables"), PropertiesJson->TryGetBoolField(TEXT("bOverride_WidthOverride"), bOverrideWidth) && bOverrideWidth);
	Test.TestTrue(TEXT("bOverride_HeightOverride auto-enables"), PropertiesJson->TryGetBoolField(TEXT("bOverride_HeightOverride"), bOverrideHeight) && bOverrideHeight);
	Test.TestTrue(TEXT("bOverride_MinDesiredHeight auto-enables"), PropertiesJson->TryGetBoolField(TEXT("bOverride_MinDesiredHeight"), bOverrideMinDesiredHeight) && bOverrideMinDesiredHeight);

	return true;
}

static bool RunWidgetPropertyDiagnosticsCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString CheckBoxWidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_CheckBoxDiagnostics"));
	const FString CheckBoxWidgetObjectPath = MakeObjectPath(CheckBoxWidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			CheckBoxWidgetAssetPath,
			TEXT("/Script/UMG.UserWidget")),
		TEXT("CreateWidgetBlueprint for CheckBox diagnostics"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			CheckBoxWidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","is_variable":true,"children":[{"class":"CheckBox","name":"ToggleBox","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree for CheckBox diagnostics"));

	const FString CheckBoxFailureJson = Subsystem->ModifyWidget(
		CheckBoxWidgetObjectPath,
		TEXT("ToggleBox"),
		TEXT(R"json({"WidgetStyles":"Bad"})json"),
		TEXT("{}"),
		TEXT("{}"),
		false);
	ExpectFailureResult(Test, CheckBoxFailureJson, TEXT("ModifyWidget invalid CheckBox property"));
	Test.TestTrue(TEXT("CheckBox property failure reports the resolved class"), CheckBoxFailureJson.Contains(TEXT("resolved class 'CheckBox")));
	Test.TestTrue(TEXT("CheckBox property failure reports the native parent"), CheckBoxFailureJson.Contains(TEXT("native parent: ContentWidget")));
	Test.TestTrue(TEXT("CheckBox property failure reports nearby editable suggestions"), CheckBoxFailureJson.Contains(TEXT("Closest editable properties: WidgetStyle")));

	const FString CommonUIButtonAssetPath = MakeUniqueAssetPath(TEXT("WBP_CommonUIButtonDiagnostics"));
	const FString CommonUIButtonObjectPath = MakeObjectPath(CommonUIButtonAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			CommonUIButtonAssetPath,
			TEXT("/Script/CommonUI.CommonButtonBase")),
		TEXT("CreateWidgetBlueprint for CommonUI diagnostics"));

	const FString CommonUIFailureJson = Subsystem->ModifyWidgetBlueprintStructure(
		CommonUIButtonObjectPath,
		TEXT("patch_class_defaults"),
		TEXT(R"json({"classDefaults":{"BackgroundColor":"#FFFFFFFF"}})json"),
		false);
	ExpectFailureResult(Test, CommonUIFailureJson, TEXT("ModifyWidgetBlueprintStructure invalid CommonUI class default"));
	Test.TestTrue(TEXT("CommonUI property failure reports the resolved class"), CommonUIFailureJson.Contains(TEXT("resolved class")));
	Test.TestTrue(TEXT("CommonUI property failure identifies unsupported wrapper surfaces"), CommonUIFailureJson.Contains(TEXT("CommonUI unsupported surface")));

	return true;
}

static bool RunBlueprintGraphAppendAndRollbackCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString BlueprintAssetPath = MakeUniqueAssetPath(TEXT("BP_GraphAppend"));
	const FString BlueprintObjectPath = MakeObjectPath(BlueprintAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateBlueprint(
			BlueprintAssetPath,
			TEXT("/Script/Engine.Actor"),
			TEXT("{}"),
			false),
		TEXT("CreateBlueprint for append coverage"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintMembers(
			BlueprintObjectPath,
			TEXT("replace_function_stubs"),
			TEXT(R"json({"functionStubs":[{"graphName":"BpInitialize","category":"Settings"},{"graphName":"ApplyForcedRallyServeMode","category":"Settings"}]})json"),
			false),
		TEXT("ModifyBlueprintMembers replace_function_stubs for append coverage"));

	UBlueprint* Blueprint = Cast<UBlueprint>(ResolveAssetByPath(BlueprintObjectPath));
	Test.TestNotNull(TEXT("Append coverage blueprint exists"), Blueprint);
	if (!Blueprint)
	{
		return false;
	}

	if (!SeedSequenceInitializerGraph(Test, Blueprint, TEXT("BpInitialize")))
	{
		return false;
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintMembers(
			BlueprintObjectPath,
			TEXT("compile"),
			TEXT("{}"),
			false),
		TEXT("ModifyBlueprintMembers compile seeded initializer graph"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ BlueprintAssetPath })),
		TEXT("SaveAssets baseline append coverage blueprint"));

	const TSharedPtr<FJsonObject> AppendResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintGraphs(
			BlueprintObjectPath,
			TEXT("append_function_call_to_sequence"),
			TEXT(R"json({"graphName":"BpInitialize","functionName":"ApplyForcedRallyServeMode","sequenceNodeTitle":"Sequence","posX":640.0,"posY":0.0})json"),
			false),
		TEXT("ModifyBlueprintGraphs append_function_call_to_sequence"));
	if (!AppendResult.IsValid())
	{
		return false;
	}

	Test.TestTrue(TEXT("Append coverage returns the initializer graph name"), JsonArrayContainsString(AppendResult, TEXT("functionGraphs"), TEXT("BpInitialize")));
	Test.TestTrue(TEXT("Append coverage preserves the target function graph name"), JsonArrayContainsString(AppendResult, TEXT("functionGraphs"), TEXT("ApplyForcedRallyServeMode")));

	const TSharedPtr<FJsonObject> ExtractAfterAppend = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractBlueprint(
			BlueprintObjectPath,
			TEXT("Full"),
			TEXT("BpInitialize")),
		TEXT("ExtractBlueprint after append_function_call_to_sequence"));
	if (!ExtractAfterAppend.IsValid())
	{
		return false;
	}

	const FString SerializedAppendExtract = SerializeJsonObjectForSearch(ExtractAfterAppend);
	Test.TestTrue(TEXT("Extracted initializer graph includes the appended function call name"), SerializedAppendExtract.Contains(TEXT("ApplyForcedRallyServeMode")));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ BlueprintAssetPath })),
		TEXT("SaveAssets appended graph coverage blueprint"));

	const TSharedPtr<FJsonObject> FailureResult = ExpectFailureResult(
		Test,
		Subsystem->ModifyBlueprintGraphs(
			BlueprintObjectPath,
			TEXT("append_function_call_to_sequence"),
			TEXT(R"json({"graphName":"MissingInitializerGraph","functionName":"ApplyForcedRallyServeMode"})json"),
			false),
		TEXT("ModifyBlueprintGraphs invalid append_function_call_to_sequence"));
	if (!FailureResult.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> ExtractAfterFailure = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractBlueprint(
			BlueprintObjectPath,
			TEXT("FunctionsShallow"),
			TEXT("BpInitialize,ApplyForcedRallyServeMode")),
		TEXT("ExtractBlueprint after invalid append mutation"));
	if (!ExtractAfterFailure.IsValid())
	{
		return false;
	}

	const FString SerializedFailureExtract = SerializeJsonObjectForSearch(ExtractAfterFailure);
	Test.TestTrue(TEXT("Blueprint remains extractable after invalid graph mutation"), SerializedFailureExtract.Contains(TEXT("BpInitialize")));
	Test.TestTrue(TEXT("Invalid graph mutation preserves the callable target graph"), SerializedFailureExtract.Contains(TEXT("ApplyForcedRallyServeMode")));

	return true;
}

static bool RunBlueprintReparentCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString BlueprintAssetPath = MakeUniqueAssetPath(TEXT("BP_Reparent"));
	const FString BlueprintObjectPath = MakeObjectPath(BlueprintAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateBlueprint(
			BlueprintAssetPath,
			TEXT("/Script/Engine.Actor"),
			TEXT("{}"),
			false),
		TEXT("CreateBlueprint for reparent coverage"));

	UBlueprint* Blueprint = Cast<UBlueprint>(ResolveAssetByPath(BlueprintObjectPath));
	Test.TestNotNull(TEXT("Reparent coverage blueprint exists"), Blueprint);
	if (!Blueprint || !Blueprint->ParentClass)
	{
		return false;
	}

	const FString OriginalParentClassPath = Blueprint->ParentClass->GetPathName();

	const bool bValidateOnlySucceeded = ExpectValidateOnlyResult(
		Test,
		Subsystem->ModifyBlueprintMembers(
			BlueprintObjectPath,
			TEXT("reparent"),
			TEXT(R"json({"parentClassPath":"/Script/Engine.Pawn"})json"),
			true),
		TEXT("ModifyBlueprintMembers reparent validate_only"));
	if (!bValidateOnlySucceeded)
	{
		return false;
	}

	Blueprint = Cast<UBlueprint>(ResolveAssetByPath(BlueprintObjectPath));
	Test.TestNotNull(TEXT("Reparent coverage blueprint still exists after validate_only"), Blueprint);
	if (!Blueprint || !Blueprint->ParentClass)
	{
		return false;
	}

	Test.TestEqual(
		TEXT("Validate-only reparent leaves the parent class unchanged"),
		Blueprint->ParentClass->GetPathName(),
		OriginalParentClassPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintMembers(
			BlueprintObjectPath,
			TEXT("reparent"),
			TEXT(R"json({"parentClassPath":"/Script/Engine.Pawn"})json"),
			false),
		TEXT("ModifyBlueprintMembers reparent to Pawn"));

	Blueprint = Cast<UBlueprint>(ResolveAssetByPath(BlueprintObjectPath));
	Test.TestNotNull(TEXT("Reparented blueprint exists"), Blueprint);
	if (!Blueprint || !Blueprint->ParentClass)
	{
		return false;
	}

	Test.TestEqual(
		TEXT("Reparent updates the Blueprint parent class"),
		Blueprint->ParentClass->GetPathName(),
		FString(TEXT("/Script/Engine.Pawn")));

	const FString InvalidReparentJson = Subsystem->ModifyBlueprintMembers(
		BlueprintObjectPath,
		TEXT("reparent"),
		TEXT(R"json({"parentClassPath":"/Script/UMG.UserWidget"})json"),
		true);
	ExpectFailureResult(
		Test,
		InvalidReparentJson,
		TEXT("ModifyBlueprintMembers invalid reparent target"));
	Test.TestTrue(
		TEXT("Invalid reparent reports an actor compatibility error"),
		InvalidReparentJson.Contains(TEXT("not compatible with Actor-based Blueprints")));

	return true;
}

static bool RunCommonUIWidgetCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_CommonUIRoundTrip"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("CommonActivatableWidget")),
		TEXT("CreateWidgetBlueprint for CommonUI"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"VerticalBox","name":"WindowRoot","is_variable":true,"children":[{"class":"HorizontalBox","name":"HeaderRow","is_variable":true,"children":[{"class":"TextBlock","name":"TitleText","is_variable":true,"properties":{"Text":"Common Window"}},{"class":"Button","name":"CloseButton","is_variable":true}]},{"class":"NamedSlot","name":"ContentSlot","is_variable":true}]})json"),
			false),
		TEXT("BuildWidgetTree for CommonUI"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			WidgetObjectPath,
			TEXT("insert_child"),
			TEXT(R"json({"parent_widget_path":"WindowRoot/HeaderRow","index":1,"child_widget":{"class":"Button","name":"SecondaryButton","is_variable":true}})json"),
			false),
		TEXT("ModifyWidgetBlueprintStructure insert_child for CommonUI"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint for CommonUI"));

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath),
		TEXT("ExtractWidgetBlueprint for CommonUI"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	Test.TestEqual(
		TEXT("CommonUI extract reports the expected parentClass"),
		ExtractResult->GetStringField(TEXT("parentClass")),
		FString(TEXT("CommonActivatableWidget")));

	TSharedPtr<FJsonObject> RootWidgetJson;
	Test.TestTrue(TEXT("CommonUI extract returns a rootWidget"), TryGetObjectFieldCopy(ExtractResult, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid());
	if (!RootWidgetJson.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> SecondaryButtonNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("WindowRoot/HeaderRow/SecondaryButton"));
	Test.TestNotNull(TEXT("CommonUI structural insert is reflected in extract_widget_blueprint"), SecondaryButtonNode.Get());
	return true;
}

static bool RunCommonUIButtonStyleCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	if (!FApp::CanEverRender() || !FSlateApplication::IsInitialized())
	{
		Test.AddInfo(TEXT("Skipping CommonUI button style visual coverage because rendering is unavailable. Run this test with -NoNullRHI."));
		return true;
	}

	const FString StyleAssetPath = MakeUniqueAssetPath(TEXT("BP_CommonUIButtonStyle"));
	const FString StyleObjectPath = MakeObjectPath(StyleAssetPath);
	const FString StyleClassPath = StyleObjectPath + TEXT("_C");
	const FString ButtonAssetPath = MakeUniqueAssetPath(TEXT("WBP_CommonUIButtonStyled"));
	const FString ButtonObjectPath = MakeObjectPath(ButtonAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateBlueprint(
			StyleAssetPath,
			TEXT("/Script/CommonUI.CommonButtonStyle"),
			TEXT("{}"),
			false),
		TEXT("CreateBlueprint for CommonUI button style"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyBlueprintMembers(
			StyleObjectPath,
			TEXT("patch_class_defaults"),
			FString::Printf(
				TEXT(R"json({"classDefaults":{"NormalBase":{"DrawAs":"Image","ResourceObject":"%s","ImageSize":{"X":240.0,"Y":72.0}},"NormalHovered":{"DrawAs":"Image","ResourceObject":"%s","ImageSize":{"X":260.0,"Y":72.0}},"Disabled":{"DrawAs":"Image","ResourceObject":"%s","ImageSize":{"X":240.0,"Y":72.0}},"ButtonPadding":{"Left":12.0,"Top":6.0,"Right":12.0,"Bottom":6.0},"MinWidth":240,"MinHeight":72}})json"),
				DefaultTexturePath,
				DefaultTexturePath,
				DefaultTexturePath),
			false),
		TEXT("ModifyBlueprintMembers patch_class_defaults for CommonUI button style"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ StyleObjectPath })),
		TEXT("SaveAssets CommonUI button style before extract"));

	const TSharedPtr<FJsonObject> StyleExtract = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractBlueprint(
			StyleObjectPath,
			TEXT("ClassLevel"),
			TEXT(""),
			true),
		TEXT("ExtractBlueprint for CommonUI button style"));
	if (!StyleExtract.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> StyleBlueprintJson;
	TSharedPtr<FJsonObject> StyleClassDefaults;
	Test.TestTrue(TEXT("CommonUI button style extract returns a blueprint payload"), TryGetObjectFieldCopy(StyleExtract, TEXT("blueprint"), StyleBlueprintJson) && StyleBlueprintJson.IsValid());
	Test.TestTrue(TEXT("CommonUI button style extract surfaces classDefaults"), StyleBlueprintJson.IsValid() && TryGetObjectFieldCopy(StyleBlueprintJson, TEXT("classDefaults"), StyleClassDefaults) && StyleClassDefaults.IsValid());
	if (StyleClassDefaults.IsValid())
	{
		double MinWidth = 0.0;
		TSharedPtr<FJsonObject> NormalBaseJson;
		Test.TestTrue(TEXT("CommonUI button style classDefaults surfaces MinWidth"), StyleClassDefaults->TryGetNumberField(TEXT("MinWidth"), MinWidth));
		Test.TestTrue(TEXT("CommonUI button style classDefaults surfaces NormalBase"), TryGetObjectFieldCopy(StyleClassDefaults, TEXT("NormalBase"), NormalBaseJson) && NormalBaseJson.IsValid());
		Test.TestEqual(TEXT("CommonUI button style classDefaults preserve MinWidth"), MinWidth, 240.0);
		if (NormalBaseJson.IsValid())
		{
			FString ResourceObjectPath;
			Test.TestTrue(TEXT("CommonUI button style NormalBase surfaces ResourceObject"), NormalBaseJson->TryGetStringField(TEXT("ResourceObject"), ResourceObjectPath));
			Test.TestTrue(TEXT("CommonUI button style NormalBase preserves the texture reference"), ResourceObjectPath.Contains(FString(DefaultTexturePath)));
		}
	}

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			ButtonAssetPath,
			TEXT("/Script/CommonUI.CommonButtonBase")),
		TEXT("CreateWidgetBlueprint for CommonUI styled button"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			ButtonAssetPath,
			TEXT(R"json({"class":"TextBlock","name":"ButtonLabel","is_variable":true,"properties":{"Text":"Styled Button","ColorAndOpacity":{"SpecifiedColor":{"R":1.0,"G":1.0,"B":1.0,"A":1.0}}}})json"),
			false),
		TEXT("BuildWidgetTree for CommonUI styled button content"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(ButtonObjectPath),
		TEXT("CompileWidgetBlueprint before CommonUI style apply"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ ButtonObjectPath })),
		TEXT("SaveAssets CommonUI styled button before baseline capture"));

	const TSharedPtr<FJsonObject> BeforeCapture = ExpectSuccessfulResult(
		Test,
		Subsystem->CaptureWidgetPreview(ButtonObjectPath, 320, 180),
		TEXT("CaptureWidgetPreview before CommonUI style apply"));
	if (!BeforeCapture.IsValid())
	{
		return false;
	}

	FString BeforeCaptureId;
	Test.TestTrue(TEXT("Baseline CommonUI button capture returns a captureId"), BeforeCapture->TryGetStringField(TEXT("captureId"), BeforeCaptureId) && !BeforeCaptureId.IsEmpty());

	ExpectSuccessfulResult(
		Test,
		Subsystem->ModifyWidgetBlueprintStructure(
			ButtonObjectPath,
			TEXT("patch_class_defaults"),
			FString::Printf(
				TEXT(R"json({"classDefaults":{"Style":"%s"}})json"),
				*StyleClassPath),
			false),
		TEXT("ModifyWidgetBlueprintStructure patch_class_defaults Style for CommonUI button"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(ButtonObjectPath),
		TEXT("CompileWidgetBlueprint after CommonUI style apply"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->SaveAssets(SerializeStringArray({ StyleObjectPath, ButtonObjectPath })),
		TEXT("SaveAssets CommonUI styled button after style apply"));

	const TSharedPtr<FJsonObject> StyledExtract = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(ButtonObjectPath, true),
		TEXT("ExtractWidgetBlueprint after CommonUI style apply"));
	if (!StyledExtract.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> StyledClassDefaults;
	Test.TestTrue(TEXT("CommonUI styled button extract surfaces classDefaults"), TryGetObjectFieldCopy(StyledExtract, TEXT("classDefaults"), StyledClassDefaults) && StyledClassDefaults.IsValid());
	if (StyledClassDefaults.IsValid())
	{
		FString AppliedStylePath;
		Test.TestTrue(TEXT("CommonUI styled button classDefaults surfaces Style"), StyledClassDefaults->TryGetStringField(TEXT("Style"), AppliedStylePath));
		Test.TestEqual(TEXT("CommonUI styled button preserves the applied Style class reference"), AppliedStylePath, StyleClassPath);
	}

	const TSharedPtr<FJsonObject> AfterCapture = ExpectSuccessfulResult(
		Test,
		Subsystem->CaptureWidgetPreview(ButtonObjectPath, 320, 180),
		TEXT("CaptureWidgetPreview after CommonUI style apply"));
	if (!AfterCapture.IsValid())
	{
		return false;
	}

	FString AfterCaptureId;
	Test.TestTrue(TEXT("Styled CommonUI button capture returns a captureId"), AfterCapture->TryGetStringField(TEXT("captureId"), AfterCaptureId) && !AfterCaptureId.IsEmpty());

	const TSharedPtr<FJsonObject> StyleCompare = ExpectSuccessfulResult(
		Test,
		Subsystem->CompareCaptureToReference(AfterCaptureId, BeforeCaptureId, 0.0),
		TEXT("CompareCaptureToReference CommonUI style before/after"));
	if (!StyleCompare.IsValid())
	{
		return false;
	}

	bool bPass = true;
	double MismatchPercentage = 0.0;
	Test.TestTrue(TEXT("CommonUI style capture comparison reports a visual delta"), StyleCompare->TryGetBoolField(TEXT("pass"), bPass) && !bPass);
	Test.TestTrue(TEXT("CommonUI style capture comparison reports mismatch percentage"), StyleCompare->TryGetNumberField(TEXT("mismatchPercentage"), MismatchPercentage) && MismatchPercentage > 0.0);

	return true;
}

static bool RunOverlaySlotRoundTripCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	const FString WidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_OverlaySlotRoundTrip"));
	const FString WidgetObjectPath = MakeObjectPath(WidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(
			WidgetAssetPath,
			TEXT("/Script/UMG.UserWidget")),
		TEXT("CreateWidgetBlueprint overlay slot round trip"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			WidgetObjectPath,
			TEXT(R"json({"class":"Overlay","name":"OverlayRoot","is_variable":true,"children":[{"class":"TextBlock","name":"LeftText","is_variable":true,"slot":{"HorizontalAlignment":"HAlign_Right"},"properties":{"Text":"Overlay slot regression"}}]})json"),
			false),
		TEXT("BuildWidgetTree overlay slot round trip"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(WidgetObjectPath),
		TEXT("CompileWidgetBlueprint overlay slot round trip"));

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(ResolveAssetByPath(WidgetObjectPath));
	Test.TestNotNull(TEXT("Overlay slot widget blueprint exists"), WidgetBP);
	if (!WidgetBP || !WidgetBP->WidgetTree)
	{
		return false;
	}

	UTextBlock* LeftText = Cast<UTextBlock>(WidgetBP->WidgetTree->FindWidget(TEXT("LeftText")));
	Test.TestNotNull(TEXT("Overlay slot child exists"), LeftText);
	UOverlaySlot* OverlaySlot = LeftText ? Cast<UOverlaySlot>(LeftText->Slot) : nullptr;
	Test.TestNotNull(TEXT("Overlay slot child has an OverlaySlot"), OverlaySlot);
	if (OverlaySlot)
	{
		Test.TestEqual(TEXT("BuildWidgetTree applies OverlaySlot HorizontalAlignment"), OverlaySlot->GetHorizontalAlignment(), HAlign_Right);
	}

	const TSharedPtr<FJsonObject> ExtractResult = ExpectSuccessfulResult(
		Test,
		Subsystem->ExtractWidgetBlueprint(WidgetObjectPath, false),
		TEXT("ExtractWidgetBlueprint overlay slot round trip"));
	if (!ExtractResult.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> RootWidgetJson;
	Test.TestTrue(TEXT("Overlay slot extract returns a rootWidget"), TryGetObjectFieldCopy(ExtractResult, TEXT("rootWidget"), RootWidgetJson) && RootWidgetJson.IsValid());
	if (!RootWidgetJson.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> LeftTextNode = FindWidgetNodeByPath(RootWidgetJson, TEXT("OverlayRoot/LeftText"));
	Test.TestNotNull(TEXT("Overlay slot extract includes the child node"), LeftTextNode.Get());
	if (!LeftTextNode.IsValid())
	{
		return false;
	}

	TSharedPtr<FJsonObject> SlotJson;
	Test.TestTrue(TEXT("Overlay slot extract includes slot data"), TryGetObjectFieldCopy(LeftTextNode, TEXT("slot"), SlotJson) && SlotJson.IsValid());
	if (SlotJson.IsValid())
	{
		FString HorizontalAlignment;
		Test.TestTrue(TEXT("Overlay slot extract reports HorizontalAlignment"), SlotJson->TryGetStringField(TEXT("HorizontalAlignment"), HorizontalAlignment));
		Test.TestEqual(TEXT("Overlay slot extract preserves HorizontalAlignment"), HorizontalAlignment, FString(TEXT("HAlign_Right")));
	}

	return true;
}

static bool RunWidgetCaptureVerificationCoverage(FAutomationTestBase& Test)
{
	UBlueprintExtractorSubsystem* Subsystem = GetSubsystem(Test);
	if (!Subsystem)
	{
		return false;
	}

	if (!FApp::CanEverRender() || !FSlateApplication::IsInitialized())
	{
		Test.AddInfo(TEXT("Skipping widget capture verification because rendering is unavailable. Run this filter without -NullRHI to exercise the visual lane."));
		return true;
	}

	const FString PrimaryWidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_CapturePrimary"));
	const FString PrimaryWidgetObjectPath = MakeObjectPath(PrimaryWidgetAssetPath);
	const FString SecondaryWidgetAssetPath = MakeUniqueAssetPath(TEXT("WBP_CaptureSecondary"));
	const FString SecondaryWidgetObjectPath = MakeObjectPath(SecondaryWidgetAssetPath);

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(PrimaryWidgetAssetPath, TEXT("/Script/UMG.UserWidget")),
		TEXT("CreateWidgetBlueprint capture primary"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			PrimaryWidgetObjectPath,
			TEXT(R"json({"class":"CanvasPanel","name":"Root","is_variable":true,"children":[{"class":"TextBlock","name":"Label","is_variable":true,"properties":{"Text":"Capture Primary"}}]})json"),
			false),
		TEXT("BuildWidgetTree capture primary"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(PrimaryWidgetObjectPath),
		TEXT("CompileWidgetBlueprint capture primary"));

	ExpectSuccessfulResult(
		Test,
		Subsystem->CreateWidgetBlueprint(SecondaryWidgetAssetPath, TEXT("/Script/UMG.UserWidget")),
		TEXT("CreateWidgetBlueprint capture secondary"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->BuildWidgetTree(
			SecondaryWidgetObjectPath,
			TEXT(R"json({"class":"CanvasPanel","name":"Root","is_variable":true,"children":[{"class":"TextBlock","name":"Label","is_variable":true,"properties":{"Text":"Capture Secondary"}}]})json"),
			false),
		TEXT("BuildWidgetTree capture secondary"));
	ExpectSuccessfulResult(
		Test,
		Subsystem->CompileWidgetBlueprint(SecondaryWidgetObjectPath),
		TEXT("CompileWidgetBlueprint capture secondary"));

	const TSharedPtr<FJsonObject> PrimaryCapture = ExpectSuccessfulResult(
		Test,
		Subsystem->CaptureWidgetPreview(PrimaryWidgetObjectPath, 320, 180),
		TEXT("CaptureWidgetPreview primary"));
	const TSharedPtr<FJsonObject> SecondaryCapture = ExpectSuccessfulResult(
		Test,
		Subsystem->CaptureWidgetPreview(SecondaryWidgetObjectPath, 320, 180),
		TEXT("CaptureWidgetPreview secondary"));
	if (!PrimaryCapture.IsValid() || !SecondaryCapture.IsValid())
	{
		return false;
	}

	FString PrimaryCaptureId;
	FString PrimaryArtifactPath;
	FString PrimaryMetadataPath;
	Test.TestTrue(TEXT("Primary capture returns a captureId"), PrimaryCapture->TryGetStringField(TEXT("captureId"), PrimaryCaptureId) && !PrimaryCaptureId.IsEmpty());
	Test.TestTrue(TEXT("Primary capture returns artifactPath"), PrimaryCapture->TryGetStringField(TEXT("artifactPath"), PrimaryArtifactPath) && !PrimaryArtifactPath.IsEmpty());
	Test.TestTrue(TEXT("Primary capture returns metadataPath"), PrimaryCapture->TryGetStringField(TEXT("metadataPath"), PrimaryMetadataPath) && !PrimaryMetadataPath.IsEmpty());
	Test.TestEqual(TEXT("Primary capture reports widget_preview type"), PrimaryCapture->GetStringField(TEXT("captureType")), FString(TEXT("widget_preview")));
	Test.TestTrue(TEXT("Primary capture artifact exists"), FPaths::FileExists(PrimaryArtifactPath));
	Test.TestTrue(TEXT("Primary capture metadata exists"), FPaths::FileExists(PrimaryMetadataPath));

	FString SecondaryCaptureId;
	Test.TestTrue(TEXT("Secondary capture returns a captureId"), SecondaryCapture->TryGetStringField(TEXT("captureId"), SecondaryCaptureId) && !SecondaryCaptureId.IsEmpty());

	const TSharedPtr<FJsonObject> SelfCompare = ExpectSuccessfulResult(
		Test,
		Subsystem->CompareCaptureToReference(PrimaryCaptureId, PrimaryCaptureId, 0.0),
		TEXT("CompareCaptureToReference self"));
	if (!SelfCompare.IsValid())
	{
		return false;
	}

	bool bSelfPass = false;
	double SelfRmse = 1.0;
	FString SelfDiffArtifactPath;
	Test.TestTrue(TEXT("Self comparison passes"), SelfCompare->TryGetBoolField(TEXT("pass"), bSelfPass) && bSelfPass);
	Test.TestTrue(TEXT("Self comparison has zero RMSE"), SelfCompare->TryGetNumberField(TEXT("rmse"), SelfRmse) && FMath::IsNearlyZero(SelfRmse));
	Test.TestTrue(TEXT("Self comparison returns a diffArtifactPath"), SelfCompare->TryGetStringField(TEXT("diffArtifactPath"), SelfDiffArtifactPath) && !SelfDiffArtifactPath.IsEmpty());
	Test.TestTrue(TEXT("Self comparison diff artifact exists"), FPaths::FileExists(SelfDiffArtifactPath));

	const TSharedPtr<FJsonObject> MismatchCompare = ExpectSuccessfulResult(
		Test,
		Subsystem->CompareCaptureToReference(PrimaryCaptureId, SecondaryCaptureId, 0.0),
		TEXT("CompareCaptureToReference mismatch"));
	if (!MismatchCompare.IsValid())
	{
		return false;
	}

	bool bMismatchPass = true;
	double MismatchRmse = 0.0;
	double MismatchPercentage = 0.0;
	Test.TestTrue(TEXT("Mismatch comparison returns pass=false"), MismatchCompare->TryGetBoolField(TEXT("pass"), bMismatchPass) && !bMismatchPass);
	Test.TestTrue(TEXT("Mismatch comparison returns RMSE"), MismatchCompare->TryGetNumberField(TEXT("rmse"), MismatchRmse) && MismatchRmse > 0.0);
	Test.TestTrue(TEXT("Mismatch comparison reports mismatch percentage"), MismatchCompare->TryGetNumberField(TEXT("mismatchPercentage"), MismatchPercentage) && MismatchPercentage > 0.0);

	const TSharedPtr<FJsonObject> ListedCaptures = ExpectSuccessfulResult(
		Test,
		Subsystem->ListCaptures(PrimaryWidgetObjectPath),
		TEXT("ListCaptures primary asset"));
	if (!ListedCaptures.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject> ListedPrimaryCapture = FindArrayObjectByStringField(
		ListedCaptures,
		TEXT("captures"),
		TEXT("captureId"),
		PrimaryCaptureId);
	Test.TestNotNull(TEXT("ListCaptures includes the primary capture"), ListedPrimaryCapture.Get());

	const TSharedPtr<FJsonObject> CleanupResult = ExpectSuccessfulResult(
		Test,
		Subsystem->CleanupCaptures(0),
		TEXT("CleanupCaptures"));
	if (!CleanupResult.IsValid())
	{
		return false;
	}

	double DeletedCount = 0.0;
	Test.TestTrue(TEXT("CleanupCaptures deletes the capture artifacts"), CleanupResult->TryGetNumberField(TEXT("deletedCount"), DeletedCount) && DeletedCount >= 1.0);
	Test.TestFalse(TEXT("Primary capture artifact no longer exists after cleanup"), FPaths::FileExists(PrimaryArtifactPath));
	return true;
}

} // namespace BlueprintExtractorAutomation

BEGIN_DEFINE_SPEC(
	FBlueprintExtractorAutomationSpec,
	"BlueprintExtractor",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
END_DEFINE_SPEC(FBlueprintExtractorAutomationSpec)

void FBlueprintExtractorAutomationSpec::Define()
{
	using namespace BlueprintExtractorAutomation;

	Describe(TEXT("Errors"), [this]()
	{
		It(TEXT("AssetNotFound"), [this]()
		{
			TestTrue(TEXT("Missing asset coverage completes"), RunMissingAssetCoverage(*this));
		});

		It(TEXT("WidgetTreeRejectsAbstractClass"), [this]()
		{
			TestTrue(TEXT("Abstract widget class coverage completes"), RunAbstractWidgetClassCoverage(*this));
		});
	});

	Describe(TEXT("ProjectControl"), [this]()
	{
		It(TEXT("EditorContext"), [this]()
		{
			TestTrue(TEXT("Editor context coverage completes"), RunEditorContextCoverage(*this));
		});

		It(TEXT("PIEAndScreenshots"), [this]()
		{
			TestTrue(TEXT("PIE and screenshot coverage completes"), RunProjectControlCoverage(*this));
		});

		It(TEXT("EditorLogs"), [this]()
		{
			TestTrue(TEXT("Editor log coverage completes"), RunEditorLogCoverage(*this));
		});
	});

	Describe(TEXT("Authoring"), [this]()
	{
		It(TEXT("ValidateOnly"), [this]()
		{
			TestTrue(TEXT("Validate-only coverage completes"), RunValidateOnlyCoverage(*this));
		});

		It(TEXT("RoundTrip"), [this]()
		{
			TestTrue(TEXT("Round-trip coverage completes"), RunRoundTripCoverage(*this));
		});

		It(TEXT("StateTreeTransitionTargets"), [this]()
		{
			TestTrue(TEXT("StateTree transition target coverage completes"), RunStateTreeTransitionTargetCoverage(*this));
		});

		It(TEXT("AnimMontageAuthoring"), [this]()
		{
			TestTrue(TEXT("AnimMontage authoring coverage completes"), RunAnimMontageAuthoringCoverage(*this));
		});

		It(TEXT("DataAssetInlineInstancedGraph"), [this]()
		{
			TestTrue(TEXT("Inline instanced DataAsset coverage completes"), RunInlineInstancedDataAssetCoverage(*this));
		});

		It(TEXT("MaterialGraphRoundTrip"), [this]()
		{
			TestTrue(TEXT("Material graph coverage completes"), RunMaterialCoverage(*this));
		});

		It(TEXT("OverlaySlotRoundTrip"), [this]()
		{
			TestTrue(TEXT("Overlay slot round-trip coverage completes"), RunOverlaySlotRoundTripCoverage(*this));
		});

		It(TEXT("WidgetCaptureVerification"), [this]()
		{
			TestTrue(TEXT("Widget capture verification coverage completes"), RunWidgetCaptureVerificationCoverage(*this));
		});

		It(TEXT("ImportJobs"), [this]()
		{
			TestTrue(TEXT("Import job coverage completes"), RunImportCoverage(*this));
		});

		It(TEXT("BindWidgetParentRoundTrip"), [this]()
		{
			TestTrue(TEXT("BindWidget parent coverage completes"), RunBindWidgetParentCoverage(*this));
		});

		It(TEXT("WidgetRename"), [this]()
		{
			TestTrue(TEXT("Widget rename coverage completes"), RunWidgetRenameCoverage(*this));
		});

		It(TEXT("WidgetSlotAliases"), [this]()
		{
			TestTrue(TEXT("Widget slot alias coverage completes"), RunWidgetSlotAliasCoverage(*this));
		});

		It(TEXT("WidgetVariableAndClassDefaults"), [this]()
		{
			TestTrue(TEXT("Widget variable and class-default coverage completes"), RunWidgetVariableAndClassDefaultsCoverage(*this));
		});

		It(TEXT("WidgetFonts"), [this]()
		{
			TestTrue(TEXT("Widget font coverage completes"), RunWidgetFontCoverage(*this));
		});

		It(TEXT("WidgetStructureOps"), [this]()
		{
			TestTrue(TEXT("Widget structure coverage completes"), RunWidgetStructureCoverage(*this));
		});

		It(TEXT("WidgetStructureFailureRecovery"), [this]()
		{
			TestTrue(TEXT("Widget failure recovery coverage completes"), RunWidgetStructureFailureRecoveryCoverage(*this));
		});

		It(TEXT("WidgetCompileFailureExtraction"), [this]()
		{
			TestTrue(TEXT("Widget compile failure extraction coverage completes"), RunWidgetCompileFailureExtractionCoverage(*this));
		});

		It(TEXT("WidgetOverrideCoupledProperties"), [this]()
		{
			TestTrue(TEXT("Widget override-coupled property coverage completes"), RunOverrideCoupledWidgetPropertyCoverage(*this));
		});

		It(TEXT("WidgetPropertyDiagnostics"), [this]()
		{
			TestTrue(TEXT("Widget property diagnostics coverage completes"), RunWidgetPropertyDiagnosticsCoverage(*this));
		});

		It(TEXT("WidgetBatchClassDefaults"), [this]()
		{
			TestTrue(TEXT("Widget batch class-default coverage completes"), RunWidgetBatchClassDefaultsCoverage(*this));
		});

		It(TEXT("WidgetNonVariableSelectors"), [this]()
		{
			TestTrue(TEXT("Widget non-variable selector coverage completes"), RunNonVariableWidgetSelectorCoverage(*this));
		});

		It(TEXT("BlueprintGraphAuthoring"), [this]()
		{
			TestTrue(TEXT("Blueprint graph authoring coverage completes"), RunBlueprintGraphAuthoringCoverage(*this));
		});

		It(TEXT("BlueprintGraphAppendAndRollback"), [this]()
		{
			TestTrue(TEXT("Blueprint graph append and rollback coverage completes"), RunBlueprintGraphAppendAndRollbackCoverage(*this));
		});

		It(TEXT("BlueprintReparent"), [this]()
		{
			TestTrue(TEXT("Blueprint reparent coverage completes"), RunBlueprintReparentCoverage(*this));
		});

		It(TEXT("CommonUIWidgetRoundTrip"), [this]()
		{
			TestTrue(TEXT("CommonUI widget coverage completes"), RunCommonUIWidgetCoverage(*this));
		});

		It(TEXT("CommonUIButtonStyleRoundTrip"), [this]()
		{
			TestTrue(TEXT("CommonUI button style coverage completes"), RunCommonUIButtonStyleCoverage(*this));
		});
	});
}

#endif // WITH_DEV_AUTOMATION_TESTS
