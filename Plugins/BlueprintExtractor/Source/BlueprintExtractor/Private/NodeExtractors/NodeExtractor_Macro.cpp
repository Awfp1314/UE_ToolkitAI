#include "NodeExtractors/NodeExtractor_Macro.h"
#include "BlueprintJsonSchema.h"
#include "K2Node_MacroInstance.h"
#include "Engine/Blueprint.h"
#include "Kismet2/BlueprintEditorUtils.h"

bool FNodeExtractor_Macro::CanHandle(const UK2Node* Node) const
{
	return Node && Node->IsA<UK2Node_MacroInstance>();
}

TSharedPtr<FJsonObject> FNodeExtractor_Macro::ExtractTypeSpecificData(const UK2Node* Node) const
{
	const UK2Node_MacroInstance* MacroNode = Cast<UK2Node_MacroInstance>(Node);
	if (!MacroNode)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();

	UEdGraph* MacroGraph = MacroNode->GetMacroGraph();
	if (MacroGraph)
	{
		Data->SetStringField(TEXT("macroName"), MacroGraph->GetName());

		if (UBlueprint* MacroBP = FBlueprintEditorUtils::FindBlueprintForGraph(MacroGraph))
		{
			Data->SetStringField(TEXT("macroSourceBlueprint"), FBlueprintJsonSchema::GetObjectPathString(MacroBP));
		}
	}

	return Data;
}
