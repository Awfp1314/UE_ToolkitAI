#include "Extractors/GraphExtractor.h"
#include "BlueprintJsonSchema.h"
#include "BlueprintExtractorModule.h"
#include "NodeExtractors/NodeExtractorBase.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node.h"
#include "Engine/Blueprint.h"

TSharedPtr<FJsonObject> FGraphExtractor::ExtractGraph(const UEdGraph* Graph, const UBlueprint* Blueprint)
{
	if (!ensureMsgf(Graph, TEXT("GraphExtractor: null Graph")))
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> GraphObj = MakeShared<FJsonObject>();

	GraphObj->SetStringField(TEXT("graphName"), Graph->GetName());
	GraphObj->SetStringField(TEXT("graphGuid"), Graph->GraphGuid.ToString());

	// Graph type
	EExtractedGraphType GraphType = DetermineGraphType(Graph, Blueprint);
	FString GraphTypeStr;
	switch (GraphType)
	{
	case EExtractedGraphType::FunctionGraph: GraphTypeStr = TEXT("FunctionGraph"); break;
	case EExtractedGraphType::EventGraph: GraphTypeStr = TEXT("EventGraph"); break;
	case EExtractedGraphType::MacroGraph: GraphTypeStr = TEXT("MacroGraph"); break;
	case EExtractedGraphType::ConstructionScript: GraphTypeStr = TEXT("ConstructionScript"); break;
	case EExtractedGraphType::AnimGraph: GraphTypeStr = TEXT("AnimGraph"); break;
	default: GraphTypeStr = TEXT("Unknown"); break;
	}
	GraphObj->SetStringField(TEXT("graphType"), GraphTypeStr);

	// Function metadata for function graphs
	if (GraphType == EExtractedGraphType::FunctionGraph && Blueprint && Blueprint->GeneratedClass)
	{
		UFunction* Function = Blueprint->GeneratedClass->FindFunctionByName(Graph->GetFName());
		if (Function)
		{
			GraphObj->SetBoolField(TEXT("isPure"), Function->HasAnyFunctionFlags(FUNC_BlueprintPure));
			GraphObj->SetBoolField(TEXT("isStatic"), Function->HasAnyFunctionFlags(FUNC_Static));
			GraphObj->SetBoolField(TEXT("isConst"), Function->HasAnyFunctionFlags(FUNC_Const));
			GraphObj->SetArrayField(TEXT("functionFlags"), FBlueprintJsonSchema::SerializeFunctionFlags(Function->FunctionFlags));

			FString Access = TEXT("Public");
			if (Function->HasAnyFunctionFlags(FUNC_Protected))
			{
				Access = TEXT("Protected");
			}
			else if (Function->HasAnyFunctionFlags(FUNC_Private))
			{
				Access = TEXT("Private");
			}
			GraphObj->SetStringField(TEXT("accessSpecifier"), Access);

			// Function parameters
			TArray<TSharedPtr<FJsonValue>> Inputs;
			TArray<TSharedPtr<FJsonValue>> Outputs;

			for (TFieldIterator<FProperty> PropIt(Function); PropIt; ++PropIt)
			{
				FProperty* Param = *PropIt;
				if (!Param->HasAnyPropertyFlags(CPF_Parm))
				{
					continue;
				}

				TSharedPtr<FJsonObject> ParamObj = MakeShared<FJsonObject>();
				ParamObj->SetStringField(TEXT("name"), Param->GetName());
				ParamObj->SetStringField(TEXT("cppType"), Param->GetCPPType());
				ParamObj->SetArrayField(TEXT("flags"), FBlueprintJsonSchema::SerializePropertyFlags(Param->GetPropertyFlags()));

				if (Param->HasAnyPropertyFlags(CPF_ReturnParm) || Param->HasAnyPropertyFlags(CPF_OutParm))
				{
					Outputs.Add(MakeShared<FJsonValueObject>(ParamObj));
				}
				else
				{
					Inputs.Add(MakeShared<FJsonValueObject>(ParamObj));
				}
			}

			GraphObj->SetArrayField(TEXT("inputs"), Inputs);
			GraphObj->SetArrayField(TEXT("outputs"), Outputs);
		}
	}

	// Extract all nodes
	TArray<TSharedPtr<FJsonValue>> Nodes;
	for (const UEdGraphNode* GraphNode : Graph->Nodes)
	{
		const UK2Node* K2Node = Cast<UK2Node>(GraphNode);
		if (K2Node)
		{
			TSharedPtr<FJsonObject> NodeObj = ExtractNode(K2Node);
			if (NodeObj)
			{
				Nodes.Add(MakeShared<FJsonValueObject>(NodeObj));
			}
		}
	}
	GraphObj->SetArrayField(TEXT("nodes"), Nodes);

	return GraphObj;
}

TSharedPtr<FJsonObject> FGraphExtractor::ExtractNode(const UK2Node* Node)
{
	if (!Node)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> NodeObj = MakeShared<FJsonObject>();

	NodeObj->SetStringField(TEXT("nodeGuid"), Node->NodeGuid.ToString());
	NodeObj->SetStringField(TEXT("nodeClass"), Node->GetClass()->GetName());
	NodeObj->SetStringField(TEXT("nodeTitle"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());
	NodeObj->SetStringField(TEXT("nodeComment"), Node->NodeComment);
	NodeObj->SetNumberField(TEXT("posX"), Node->NodePosX);
	NodeObj->SetNumberField(TEXT("posY"), Node->NodePosY);

	// Type-specific data from node extractor registry
	const FNodeExtractorRegistry& Registry = FNodeExtractorRegistry::Get();
	const FNodeExtractorBase* Extractor = Registry.FindExtractor(Node);
	if (Extractor)
	{
		TSharedPtr<FJsonObject> TypeData = Extractor->ExtractTypeSpecificData(Node);
		if (TypeData)
		{
			NodeObj->SetStringField(TEXT("extractorType"), Extractor->GetNodeTypeName());
			NodeObj->SetObjectField(TEXT("typeSpecificData"), TypeData);
		}
	}

	// Extract all pins
	TArray<TSharedPtr<FJsonValue>> Pins;
	for (const UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin && !Pin->bHidden)
		{
			TSharedPtr<FJsonObject> PinObj = ExtractPin(Pin);
			if (PinObj)
			{
				Pins.Add(MakeShared<FJsonValueObject>(PinObj));
			}
		}
	}
	NodeObj->SetArrayField(TEXT("pins"), Pins);

	return NodeObj;
}

TSharedPtr<FJsonObject> FGraphExtractor::ExtractPin(const UEdGraphPin* Pin)
{
	if (!Pin)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> PinObj = MakeShared<FJsonObject>();

	PinObj->SetStringField(TEXT("pinName"), Pin->PinName.ToString());
	PinObj->SetStringField(TEXT("pinId"), Pin->PinId.ToString());
	PinObj->SetStringField(TEXT("direction"), Pin->Direction == EGPD_Input ? TEXT("Input") : TEXT("Output"));
	PinObj->SetObjectField(TEXT("type"), FBlueprintJsonSchema::SerializePinType(Pin->PinType));

	if (!Pin->DefaultValue.IsEmpty())
	{
		PinObj->SetStringField(TEXT("defaultValue"), Pin->DefaultValue);
	}
	if (!Pin->AutogeneratedDefaultValue.IsEmpty())
	{
		PinObj->SetStringField(TEXT("autogeneratedDefaultValue"), Pin->AutogeneratedDefaultValue);
	}
	if (Pin->DefaultObject)
	{
		PinObj->SetStringField(TEXT("defaultObject"), FBlueprintJsonSchema::GetObjectPathString(Pin->DefaultObject));
	}
	if (!Pin->DefaultTextValue.IsEmpty())
	{
		PinObj->SetStringField(TEXT("defaultTextValue"), Pin->DefaultTextValue.ToString());
	}

	// Connections (nodeGuid + pinName pairs)
	TArray<TSharedPtr<FJsonValue>> Connections;
	for (const UEdGraphPin* LinkedPin : Pin->LinkedTo)
	{
		if (LinkedPin && LinkedPin->GetOwningNode())
		{
			TSharedPtr<FJsonObject> ConnObj = MakeShared<FJsonObject>();
			ConnObj->SetStringField(TEXT("nodeGuid"), LinkedPin->GetOwningNode()->NodeGuid.ToString());
			ConnObj->SetStringField(TEXT("pinName"), LinkedPin->PinName.ToString());
			Connections.Add(MakeShared<FJsonValueObject>(ConnObj));
		}
	}

	if (Connections.Num() > 0)
	{
		PinObj->SetArrayField(TEXT("connections"), Connections);
	}

	return PinObj;
}

EExtractedGraphType FGraphExtractor::DetermineGraphType(const UEdGraph* Graph, const UBlueprint* Blueprint)
{
	if (!Graph || !Blueprint)
	{
		return EExtractedGraphType::Unknown;
	}

	static const FName UserConstructionScriptName(TEXT("UserConstructionScript"));
	if (Graph->GetFName() == UserConstructionScriptName)
	{
		return EExtractedGraphType::ConstructionScript;
	}

	for (const UEdGraph* FuncGraph : Blueprint->FunctionGraphs)
	{
		if (FuncGraph == Graph)
		{
			return EExtractedGraphType::FunctionGraph;
		}
	}

	for (const UEdGraph* EventGraph : Blueprint->UbergraphPages)
	{
		if (EventGraph == Graph)
		{
			return EExtractedGraphType::EventGraph;
		}
	}

	for (const UEdGraph* MacroGraph : Blueprint->MacroGraphs)
	{
		if (MacroGraph == Graph)
		{
			return EExtractedGraphType::MacroGraph;
		}
	}

	// AnimGraph detection: check schema class name or graph name
	if (Graph->GetSchema() && Graph->GetSchema()->GetClass()->GetName().Contains(TEXT("Anim")))
	{
		return EExtractedGraphType::AnimGraph;
	}
	static const FName AnimGraphName(TEXT("AnimGraph"));
	if (Graph->GetFName() == AnimGraphName)
	{
		return EExtractedGraphType::AnimGraph;
	}

	return EExtractedGraphType::Unknown;
}

TArray<TSharedPtr<FJsonValue>> FGraphExtractor::ExtractAllGraphs(const UBlueprint* Blueprint, const TArray<FName>& GraphFilter)
{
	TArray<TSharedPtr<FJsonValue>> Result;

	if (!ensureMsgf(Blueprint, TEXT("GraphExtractor: null Blueprint")))
	{
		return Result;
	}

	// When GraphFilter is non-empty, only extract graphs whose name is in the filter
	auto ShouldInclude = [&GraphFilter](const UEdGraph* Graph) -> bool
	{
		if (GraphFilter.Num() == 0) { return true; }
		return GraphFilter.Contains(Graph->GetFName());
	};

	// Function graphs
	for (const UEdGraph* Graph : Blueprint->FunctionGraphs)
	{
		if (Graph && ShouldInclude(Graph))
		{
			TSharedPtr<FJsonObject> GraphObj = ExtractGraph(Graph, Blueprint);
			if (GraphObj)
			{
				Result.Add(MakeShared<FJsonValueObject>(GraphObj));
			}
		}
	}

	// Event graphs (ubergraph pages)
	for (const UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (Graph && ShouldInclude(Graph))
		{
			TSharedPtr<FJsonObject> GraphObj = ExtractGraph(Graph, Blueprint);
			if (GraphObj)
			{
				Result.Add(MakeShared<FJsonValueObject>(GraphObj));
			}
		}
	}

	// Macro graphs
	for (const UEdGraph* Graph : Blueprint->MacroGraphs)
	{
		if (Graph && ShouldInclude(Graph))
		{
			TSharedPtr<FJsonObject> GraphObj = ExtractGraph(Graph, Blueprint);
			if (GraphObj)
			{
				Result.Add(MakeShared<FJsonValueObject>(GraphObj));
			}
		}
	}

	// Collect all graphs extracted so far to detect any remaining (e.g. AnimBlueprint anim graphs)
	TSet<const UEdGraph*> ExtractedGraphs;
	ExtractedGraphs.Append(Blueprint->FunctionGraphs);
	ExtractedGraphs.Append(Blueprint->UbergraphPages);
	ExtractedGraphs.Append(Blueprint->MacroGraphs);

	// Iterate all subobjects of the Blueprint to find UEdGraph instances not yet extracted
	TArray<UObject*> Subobjects;
	GetObjectsWithOuter(Blueprint, Subobjects, /*bIncludeNestedObjects=*/true);
	for (UObject* Subobject : Subobjects)
	{
		UEdGraph* Graph = Cast<UEdGraph>(Subobject);
		if (Graph && !ExtractedGraphs.Contains(Graph) && ShouldInclude(Graph))
		{
			TSharedPtr<FJsonObject> GraphObj = ExtractGraph(Graph, Blueprint);
			if (GraphObj)
			{
				Result.Add(MakeShared<FJsonValueObject>(GraphObj));
			}
			ExtractedGraphs.Add(Graph);
		}
	}

	return Result;
}
