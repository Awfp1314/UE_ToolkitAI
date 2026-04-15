#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "BlueprintExtractorTypes.h"

class UEdGraph;
class UEdGraphPin;
class UBlueprint;
class UK2Node;

struct FGraphExtractor
{
	static TSharedPtr<FJsonObject> ExtractGraph(const UEdGraph* Graph, const UBlueprint* Blueprint);
	static TArray<TSharedPtr<FJsonValue>> ExtractAllGraphs(const UBlueprint* Blueprint, const TArray<FName>& GraphFilter = {});

private:
	static TSharedPtr<FJsonObject> ExtractNode(const UK2Node* Node);
	static TSharedPtr<FJsonObject> ExtractPin(const UEdGraphPin* Pin);
	static EExtractedGraphType DetermineGraphType(const UEdGraph* Graph, const UBlueprint* Blueprint);
};
