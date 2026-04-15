#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UWidgetBlueprint;
class UWidgetTree;
class UWidget;
class UPanelWidget;
class UPanelSlot;

struct FWidgetTreeBuilder
{
	/** Extracts a compact widget-authoring snapshot for a WidgetBlueprint. */
	static TSharedPtr<FJsonObject> ExtractWidgetBlueprint(UWidgetBlueprint* WidgetBP,
	                                                      bool bIncludeClassDefaults = false);

	/** Creates a new WidgetBlueprint asset at the given path with the specified parent class. */
	static TSharedPtr<FJsonObject> CreateWidgetBlueprint(const FString& AssetPath,
	                                                     const FString& ParentClassName);

	/** Clears existing widget tree and builds a new one from JSON. */
	static TSharedPtr<FJsonObject> BuildWidgetTree(UWidgetBlueprint* WidgetBP,
	                                               const TSharedPtr<FJsonObject>& RootWidgetJson,
	                                               bool bValidateOnly = false);

	/** Patches properties and/or slot config on an existing widget by name. */
	static TSharedPtr<FJsonObject> ModifyWidget(UWidgetBlueprint* WidgetBP,
	                                            const FString& WidgetName,
	                                            const TSharedPtr<FJsonObject>& PropertiesJson,
	                                            const TSharedPtr<FJsonObject>& SlotJson,
	                                            const TSharedPtr<FJsonObject>& WidgetOptionsJson,
	                                            bool bValidateOnly = false);

	/** Applies one structural widget-tree mutation using an extracted JSON snapshot as the working model. */
	static TSharedPtr<FJsonObject> ModifyWidgetBlueprintStructure(UWidgetBlueprint* WidgetBP,
	                                                              const FString& Operation,
	                                                              const TSharedPtr<FJsonObject>& PayloadJson,
	                                                              bool bValidateOnly = false);

	/** Applies compact font settings to text widgets in a WidgetBlueprint. */
	static TSharedPtr<FJsonObject> ApplyWidgetFonts(UWidgetBlueprint* WidgetBP,
	                                                const TSharedPtr<FJsonObject>& PayloadJson,
	                                                bool bValidateOnly = false);

	/** Triggers blueprint compile and returns errors/warnings. */
	static TSharedPtr<FJsonObject> CompileWidgetBlueprint(UWidgetBlueprint* WidgetBP);

private:
	/** Recursively creates a single widget node from JSON and adds it to its parent. */
	static UWidget* CreateWidgetFromJson(UWidgetTree* WidgetTree,
	                                     UPanelWidget* Parent,
	                                     const TSharedPtr<FJsonObject>& WidgetJson,
	                                     TArray<FString>& OutErrors);

	/** Resolves a widget class name (short name or full path) to a UClass pointer. */
	static UClass* ResolveWidgetClass(const FString& ClassName);

	/** Sets UPROPERTY values on a UObject from a JSON object using FProperty reflection. */
	static void SetPropertiesFromJson(UObject* Target,
	                                  const TSharedPtr<FJsonObject>& PropertiesJson,
	                                  TArray<FString>& OutErrors);

	/** Sets slot properties from JSON using FProperty reflection on the slot object. */
	static void SetSlotPropertiesFromJson(UPanelSlot* Slot,
	                                      const TSharedPtr<FJsonObject>& SlotJson,
	                                      TArray<FString>& OutErrors);
};
