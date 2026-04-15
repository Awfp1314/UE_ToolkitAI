#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBlueprint;

/** Extracts CDO (Class Default Object) property values that differ from the parent class defaults.
 *  Works for any UBlueprint subclass (regular Blueprint, WidgetBlueprint, AnimBlueprint, etc.).
 *  Only includes properties that are editable (CPF_Edit | CPF_BlueprintVisible)
 *  and have been modified from their parent CDO values. */
struct FClassDefaultsExtractor
{
	/** Extract CDO overrides for the given Blueprint's generated class.
	 *  Returns a JSON object where each key is a property name and the value is the serialized property value.
	 *  Returns an empty object if the Blueprint has no generated class or no overrides. */
	static TSharedPtr<FJsonObject> Extract(const UBlueprint* Blueprint);
};
