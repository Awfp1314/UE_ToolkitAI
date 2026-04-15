#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"

#include "BlueprintExtractorTypes.h"

#include "BlueprintExtractorSubsystem.generated.h"

class FBlueprintExtractorImportJobManager;
class FStateTreeDebuggerBridge;

/** Editor subsystem exposing blueprint extraction as string-based methods
 *  for remote invocation via the Web Remote Control API. */
UCLASS()
class BLUEPRINTEXTRACTOR_API UBlueprintExtractorSubsystem : public UEditorSubsystem
{
	GENERATED_BODY()

// ============================================================
// Private Functions
// ============================================================
private:
	static EBlueprintExtractionScope ParseScope(const FString& ScopeString);
	FBlueprintExtractorImportJobManager* ImportJobManager = nullptr;
	TSharedPtr<FStateTreeDebuggerBridge> StateTreeDebuggerBridgeInstance;

// ============================================================
// Public Interface
// ============================================================
public:
	virtual ~UBlueprintExtractorSubsystem() override;

	/** Extracts a Blueprint asset to a JSON string. Returns an error JSON object on failure.
	 *  GraphFilter is a comma-separated list of graph names to extract. Empty = all graphs.
	 *  bIncludeClassDefaults includes CDO property values that differ from the parent class. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractBlueprint(const FString& AssetPath, const FString& Scope = TEXT("Full"), const FString& GraphFilter = TEXT(""), const bool bIncludeClassDefaults = false);

	/** Extracts a StateTree asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractStateTree(const FString& AssetPath);

	/** Extracts a DataAsset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractDataAsset(const FString& AssetPath);

	/** Extracts a DataTable to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractDataTable(const FString& AssetPath);

	/** Extracts a BehaviorTree to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractBehaviorTree(const FString& AssetPath);

	/** Extracts a Blackboard asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractBlackboard(const FString& AssetPath);

	/** Extracts a UserDefinedStruct asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractUserDefinedStruct(const FString& AssetPath);

	/** Extracts a UserDefinedEnum asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractUserDefinedEnum(const FString& AssetPath);

	/** Extracts a curve asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractCurve(const FString& AssetPath);

	/** Extracts a CurveTable asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractCurveTable(const FString& AssetPath);

	/** Extracts a MaterialInstance asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractMaterialInstance(const FString& AssetPath);

	/** Extracts a base Material asset to a compact JSON graph snapshot. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractMaterial(const FString& AssetPath, const bool bVerbose = false);

	/** Extracts a MaterialFunction, MaterialLayer, or MaterialLayerBlend asset to a compact JSON graph snapshot. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractMaterialFunction(const FString& AssetPath, const bool bVerbose = false);

	/** Extracts an AnimSequence asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractAnimSequence(const FString& AssetPath);

	/** Extracts an AnimMontage asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractAnimMontage(const FString& AssetPath);

	/** Extracts a BlendSpace asset to a JSON string. Returns an error JSON object on failure. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractBlendSpace(const FString& AssetPath);

	/** Extracts multiple assets with cascade reference following. Returns extraction summary JSON.
	 *  GraphFilter is a comma-separated list of graph names to extract. Empty = all graphs. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractCascade(const FString& AssetPathsJson,
	                       const FString& Scope = TEXT("Full"),
	                       const int32 MaxDepth = 3,
	                       const FString& GraphFilter = TEXT(""));

	/** Searches assets by name query and optional class filter. Returns a JSON array. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString SearchAssets(const FString& Query, const FString& ClassFilter = TEXT("Blueprint"), const int32 MaxResults = 50);

	/** Lists assets under a package path. Returns a JSON array. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ListAssets(const FString& PackagePath,
	                   const bool bRecursive = true,
	                   const FString& ClassFilter = TEXT(""));

	/** Creates a new WidgetBlueprint asset. Returns JSON with asset path and status. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateWidgetBlueprint(const FString& AssetPath, const FString& ParentClass);

	/** Extracts a compact authoring snapshot for a WidgetBlueprint. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractWidgetBlueprint(const FString& AssetPath, const bool bIncludeClassDefaults = false);

	/** Extract one authored widget animation timeline from a WidgetBlueprint. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ExtractWidgetAnimation(const FString& AssetPath, const FString& AnimationName);

	/** Create a named widget animation with optional initial timeline payload. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateWidgetAnimation(const FString& AssetPath,
	                              const FString& AnimationName,
	                              const FString& PayloadJson = TEXT(""),
	                              const bool bValidateOnly = false);

	/** Modify a named widget animation timeline or metadata. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyWidgetAnimation(const FString& AssetPath,
	                              const FString& AnimationName,
	                              const FString& Operation,
	                              const FString& PayloadJson = TEXT(""),
	                              const bool bValidateOnly = false);

	/** Builds/replaces the entire widget hierarchy from JSON. Returns JSON with widget count and errors. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString BuildWidgetTree(const FString& AssetPath,
	                        const FString& WidgetTreeJson,
	                        const bool bValidateOnly = false);

	/** Patches properties on an existing widget. Returns JSON with success/error. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyWidget(const FString& AssetPath,
	                     const FString& WidgetName,
	                     const FString& PropertiesJson,
	                     const FString& SlotJson,
	                     const FString& WidgetOptionsJson = TEXT(""),
	                     const bool bValidateOnly = false);

	/** Applies a structural widget-tree mutation using a compact JSON payload. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyWidgetBlueprintStructure(const FString& AssetPath,
	                                       const FString& Operation,
	                                       const FString& PayloadJson,
	                                       const bool bValidateOnly = false);

	/** Compiles a WidgetBlueprint. Returns JSON array of errors/warnings. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CompileWidgetBlueprint(const FString& AssetPath);

	/** Renders a WidgetBlueprint offscreen to a PNG capture under Saved/BlueprintExtractor/Captures. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CaptureWidgetPreview(const FString& AssetPath, int32 Width = 512, int32 Height = 512);

	/** Captures the active editor viewport to a PNG artifact under Saved/BlueprintExtractor/Captures. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CaptureEditorScreenshot();

	/** Captures the active PIE viewport to a PNG artifact under Saved/BlueprintExtractor/Captures. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CaptureRuntimeScreenshot();

	/** Renders one or more widget animation checkpoints to offscreen captures. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CaptureWidgetMotionCheckpoints(const FString& AssetPath, const FString& PayloadJson);

	/** Compares two PNG captures or reference images and records a diff capture. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CompareCaptureToReference(const FString& CaptureIdOrPath,
	                                  const FString& ReferenceIdOrPath,
	                                  double Tolerance = 0.01);

	/** Lists saved capture metadata, optionally filtered to one asset path. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ListCaptures(const FString& AssetPathFilter = TEXT(""));

	/** Deletes old captures from Saved/BlueprintExtractor/Captures. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CleanupCaptures(int32 MaxAgeDays = 7);

	/** Imports one or more font files into UFontFace assets and optionally updates a runtime UFont. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ImportFonts(const FString& PayloadJson, const bool bValidateOnly = false);

	/** Applies compact font settings to text widgets in an existing WidgetBlueprint. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ApplyWidgetFonts(const FString& AssetPath,
	                         const FString& PayloadJson,
	                         const bool bValidateOnly = false);

	/** Saves one or more dirty asset packages explicitly. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString SaveAssets(const FString& AssetPathsJson);

	/** Creates a new DataAsset of the specified concrete class. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateDataAsset(const FString& AssetPath,
	                        const FString& AssetClassPath,
	                        const FString& PropertiesJson = TEXT(""),
	                        const bool bValidateOnly = false);

	/** Applies a reflected property patch to an existing DataAsset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyDataAsset(const FString& AssetPath,
	                        const FString& PropertiesJson,
	                        const bool bValidateOnly = false);

	/** Creates a dedicated Enhanced InputAction asset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateInputAction(const FString& AssetPath,
	                          const FString& ValueType = TEXT("boolean"),
	                          const FString& PropertiesJson = TEXT(""),
	                          const bool bValidateOnly = false);

	/** Modifies a dedicated Enhanced InputAction asset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyInputAction(const FString& AssetPath,
	                          const FString& ValueType = TEXT(""),
	                          const FString& PropertiesJson = TEXT(""),
	                          const bool bValidateOnly = false);

	/** Creates a dedicated Enhanced InputMappingContext asset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateInputMappingContext(const FString& AssetPath,
	                                  const FString& PropertiesJson = TEXT(""),
	                                  const FString& MappingsJson = TEXT("[]"),
	                                  const bool bValidateOnly = false);

	/** Modifies a dedicated Enhanced InputMappingContext asset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyInputMappingContext(const FString& AssetPath,
	                                  const FString& PropertiesJson = TEXT(""),
	                                  const bool bReplaceMappings = false,
	                                  const FString& MappingsJson = TEXT("[]"),
	                                  const bool bValidateOnly = false);

	/** Creates a new DataTable with the specified row struct and optional rows. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateDataTable(const FString& AssetPath,
	                        const FString& RowStructPath,
	                        const FString& RowsJson = TEXT("[]"),
	                        const bool bValidateOnly = false);

	/** Upserts, deletes, or replaces rows in an existing DataTable. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyDataTable(const FString& AssetPath,
	                        const FString& PayloadJson,
	                        const bool bValidateOnly = false);

	/** Creates a new curve asset of the specified concrete curve type. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateCurve(const FString& AssetPath,
	                    const FString& CurveType,
	                    const FString& ChannelsJson = TEXT("{}"),
	                    const bool bValidateOnly = false);

	/** Modifies an existing curve asset by patching channels and key operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyCurve(const FString& AssetPath,
	                    const FString& PayloadJson,
	                    const bool bValidateOnly = false);

	/** Creates a new CurveTable with the specified mode and optional rows. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateCurveTable(const FString& AssetPath,
	                         const FString& CurveTableMode,
	                         const FString& RowsJson = TEXT("[]"),
	                         const bool bValidateOnly = false);

	/** Upserts, deletes, or replaces rows in an existing CurveTable. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyCurveTable(const FString& AssetPath,
	                         const FString& PayloadJson,
	                         const bool bValidateOnly = false);

	/** Creates a new MaterialInstanceConstant from a parent material/interface. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateMaterialInstance(const FString& AssetPath,
	                               const FString& ParentMaterialPath,
	                               const bool bValidateOnly = false);

	/** Applies material override operations to an existing MaterialInstanceConstant. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyMaterialInstance(const FString& AssetPath,
	                               const FString& PayloadJson,
	                               const bool bValidateOnly = false);

	/** Creates a new base Material asset with optional initial texture and settings payload. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateMaterial(const FString& AssetPath,
	                       const FString& InitialTexturePath = TEXT(""),
	                       const FString& SettingsJson = TEXT(""),
	                       const bool bValidateOnly = false);

	/** Applies graph and settings operations to an existing Material asset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyMaterial(const FString& AssetPath,
	                       const FString& PayloadJson,
	                       const bool bValidateOnly = false);

	/** Creates a new MaterialFunction-family asset. asset_kind: function, layer, or layer_blend. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateMaterialFunction(const FString& AssetPath,
	                               const FString& AssetKind = TEXT("function"),
	                               const FString& SettingsJson = TEXT(""),
	                               const bool bValidateOnly = false);

	/** Applies graph and settings operations to an existing MaterialFunction-family asset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyMaterialFunction(const FString& AssetPath,
	                               const FString& PayloadJson,
	                               const bool bValidateOnly = false);

	/** Recompiles or refreshes a material-family asset without saving it. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CompileMaterialAsset(const FString& AssetPath);

	/** Creates a new UserDefinedStruct asset from extractor-shaped field payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateUserDefinedStruct(const FString& AssetPath,
	                                const FString& PayloadJson = TEXT(""),
	                                const bool bValidateOnly = false);

	/** Modifies an existing UserDefinedStruct with field-level operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyUserDefinedStruct(const FString& AssetPath,
	                                const FString& Operation,
	                                const FString& PayloadJson = TEXT(""),
	                                const bool bValidateOnly = false);

	/** Creates a new UserDefinedEnum asset from extractor-shaped entry payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateUserDefinedEnum(const FString& AssetPath,
	                              const FString& PayloadJson = TEXT(""),
	                              const bool bValidateOnly = false);

	/** Modifies an existing UserDefinedEnum with entry-level operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyUserDefinedEnum(const FString& AssetPath,
	                              const FString& Operation,
	                              const FString& PayloadJson = TEXT(""),
	                              const bool bValidateOnly = false);

	/** Creates a new Blackboard asset from extractor-shaped key payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateBlackboard(const FString& AssetPath,
	                         const FString& PayloadJson = TEXT(""),
	                         const bool bValidateOnly = false);

	/** Modifies an existing Blackboard asset with declarative key operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyBlackboard(const FString& AssetPath,
	                         const FString& Operation,
	                         const FString& PayloadJson = TEXT(""),
	                         const bool bValidateOnly = false);

	/** Creates a new BehaviorTree asset from extractor-shaped tree payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateBehaviorTree(const FString& AssetPath,
	                           const FString& PayloadJson = TEXT(""),
	                           const bool bValidateOnly = false);

	/** Modifies an existing BehaviorTree asset with declarative tree operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyBehaviorTree(const FString& AssetPath,
	                           const FString& Operation,
	                           const FString& PayloadJson = TEXT(""),
	                           const bool bValidateOnly = false);

	/** Creates a new StateTree asset from extractor-shaped tree payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateStateTree(const FString& AssetPath,
	                        const FString& PayloadJson = TEXT(""),
	                        const bool bValidateOnly = false);

	/** Modifies an existing StateTree asset with declarative tree operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyStateTree(const FString& AssetPath,
	                        const FString& Operation,
	                        const FString& PayloadJson = TEXT(""),
	                        const bool bValidateOnly = false);

	/** Creates a new AnimSequence asset from extractor-shaped metadata payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateAnimSequence(const FString& AssetPath,
	                           const FString& PayloadJson = TEXT(""),
	                           const bool bValidateOnly = false);

	/** Modifies an existing AnimSequence asset with metadata authoring operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyAnimSequence(const FString& AssetPath,
	                           const FString& Operation,
	                           const FString& PayloadJson = TEXT(""),
	                           const bool bValidateOnly = false);

	/** Creates a new AnimMontage asset from extractor-shaped metadata payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateAnimMontage(const FString& AssetPath,
	                          const FString& PayloadJson = TEXT(""),
	                          const bool bValidateOnly = false);

	/** Modifies an existing AnimMontage asset with metadata authoring operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyAnimMontage(const FString& AssetPath,
	                          const FString& Operation,
	                          const FString& PayloadJson = TEXT(""),
	                          const bool bValidateOnly = false);

	/** Creates a new BlendSpace asset from extractor-shaped sample and axis payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateBlendSpace(const FString& AssetPath,
	                         const FString& PayloadJson = TEXT(""),
	                         const bool bValidateOnly = false);

	/** Modifies an existing BlendSpace asset with sample and axis operations. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyBlendSpace(const FString& AssetPath,
	                         const FString& Operation,
	                         const FString& PayloadJson = TEXT(""),
	                         const bool bValidateOnly = false);

	/** Creates a new Blueprint asset with optional member payloads. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString CreateBlueprint(const FString& AssetPath,
	                        const FString& ParentClassPath,
	                        const FString& PayloadJson = TEXT(""),
	                        const bool bValidateOnly = false);

	/** Modifies member authoring surfaces on an existing Blueprint asset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyBlueprintMembers(const FString& AssetPath,
	                               const FString& Operation,
	                               const FString& PayloadJson = TEXT(""),
	                               const bool bValidateOnly = false);

	/** Applies targeted graph-authoring operations to an existing Blueprint asset. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ModifyBlueprintGraphs(const FString& AssetPath,
	                              const FString& Operation,
	                              const FString& PayloadJson = TEXT(""),
	                              const bool bValidateOnly = false);

	/** Enqueues a generic async import job. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ImportAssets(const FString& PayloadJson, const bool bValidateOnly = false);

	/** Enqueues an async reimport job for explicit asset paths. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ReimportAssets(const FString& PayloadJson, const bool bValidateOnly = false);

	/** Enqueues an async texture-focused import job. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ImportTextures(const FString& PayloadJson, const bool bValidateOnly = false);

	/** Enqueues an async mesh-focused import job. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ImportMeshes(const FString& PayloadJson, const bool bValidateOnly = false);

	/** Returns the current state of a previously enqueued import job. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString GetImportJob(const FString& JobId);

	/** Lists session-scoped import jobs. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ListImportJobs(const bool bIncludeCompleted = true);

	/** Returns current project/editor context to the MCP host for build and reconnect orchestration. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString GetProjectAutomationContext();

	/** Returns a bounded read-only snapshot of the current editor context for MCP inspection. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString GetEditorContext();

	/** Returns filtered entries from the editor Output Log ring buffer captured by the plugin module. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ReadOutputLog(const FString& FilterJson = TEXT(""));

	/** Lists registered Message Log listings from known built-in and caller-supplied candidate names. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ListMessageLogListings(const FString& PayloadJson = TEXT(""));

	/** Returns filtered messages from one registered Message Log listing. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ReadMessageLog(const FString& ListingName, const FString& FilterJson = TEXT(""));

	/** Requests a Play-In-Editor or Simulate-In-Editor session. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString StartPIE(const bool bSimulateInEditor = false);

	/** Stops the active Play-In-Editor or Simulate-In-Editor session if one exists. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString StopPIE();

	/** Stops the current PIE session if needed, then schedules a fresh launch. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString RelaunchPIE(const bool bSimulateInEditor = false);

	/** Triggers an in-editor Live Coding compile when supported. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString TriggerLiveCoding(const bool bEnableForSession = true, const bool bWaitForCompletion = true);

	/** Schedules an editor restart after the current remote call returns. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString RestartEditor(const bool bWarn = false, const FString& AdditionalCommandLine = TEXT(""), const bool bSaveDirtyAssets = false, const bool bRelaunch = true);

	/** Starts a StateTree debugger trace session. Optionally filters to a specific StateTree asset.
	 *  Requires PIE to be running. Returns JSON with session status. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString StartStateTreeDebugger(const FString& AssetPath = TEXT(""));

	/** Stops the active StateTree debugger session. */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString StopStateTreeDebugger();

	/** Reads StateTree debugger data: instances, events, active states.
	 *  PayloadJson: { instanceId?, maxEvents?, scrubTime? } */
	UFUNCTION(BlueprintCallable, Category="Blueprint Extractor")
	FString ReadStateTreeDebugger(const FString& PayloadJson = TEXT(""));
};
