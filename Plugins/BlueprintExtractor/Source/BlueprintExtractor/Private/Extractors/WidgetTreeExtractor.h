#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UWidgetBlueprint;
class UWidget;
class UPanelSlot;

enum class ESlateVisibility : uint8;

struct FWidgetTreeExtractor
{
	/** Entry point. Extracts the entire widget tree hierarchy and property bindings.
	 *  Returns nullptr only when the input WidgetBlueprint is null. */
	static TSharedPtr<FJsonObject> Extract(const UWidgetBlueprint* WidgetBP);

private:
	/** Extracts a single widget node: name, class, label, isVariable, visibility,
	 *  slot, properties, and children (recursive for UPanelWidget). */
	static TSharedPtr<FJsonObject> ExtractWidget(const UWidget* Widget);

	/** Extracts slot data: slot class name + CDO-diff properties. */
	static TSharedPtr<FJsonObject> ExtractSlot(const UPanelSlot* Slot);

	/** Generic CDO-diff property extraction. Compares object properties against
	 *  class defaults and exports those that differ. */
	static TSharedPtr<FJsonObject> ExtractPropertyOverrides(const UObject* Object);

	/** Extracts property bindings from UWidgetBlueprint::Bindings.
	 *  Returns nullptr if no bindings exist. */
	static TSharedPtr<FJsonObject> ExtractBindings(const UWidgetBlueprint* WidgetBP);

	/** Converts ESlateVisibility enum value to a human-readable string. */
	static FString VisibilityToString(const ESlateVisibility Visibility);
};
