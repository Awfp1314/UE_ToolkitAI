#include "NodeExtractors/NodeExtractor_FlowControl.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_SwitchEnum.h"
#include "K2Node_SwitchInteger.h"
#include "K2Node_SwitchString.h"
#include "K2Node_SwitchName.h"
#include "K2Node_ExecutionSequence.h"

bool FNodeExtractor_FlowControl::CanHandle(const UK2Node* Node) const
{
	return Node && (
		Node->IsA<UK2Node_IfThenElse>() ||
		Node->IsA<UK2Node_SwitchEnum>() ||
		Node->IsA<UK2Node_SwitchInteger>() ||
		Node->IsA<UK2Node_SwitchString>() ||
		Node->IsA<UK2Node_SwitchName>() ||
		Node->IsA<UK2Node_ExecutionSequence>()
	);
}

TSharedPtr<FJsonObject> FNodeExtractor_FlowControl::ExtractTypeSpecificData(const UK2Node* Node) const
{
	TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();

	if (Node->IsA<UK2Node_IfThenElse>())
	{
		Data->SetStringField(TEXT("flowType"), TEXT("Branch"));
	}
	else if (const UK2Node_SwitchEnum* SwitchEnum = Cast<UK2Node_SwitchEnum>(Node))
	{
		Data->SetStringField(TEXT("flowType"), TEXT("SwitchEnum"));
		if (SwitchEnum->Enum)
		{
			Data->SetStringField(TEXT("enumPath"), SwitchEnum->Enum->GetPathName());
		}
	}
	else if (Node->IsA<UK2Node_SwitchInteger>())
	{
		Data->SetStringField(TEXT("flowType"), TEXT("SwitchInteger"));
	}
	else if (Node->IsA<UK2Node_SwitchString>())
	{
		Data->SetStringField(TEXT("flowType"), TEXT("SwitchString"));
	}
	else if (Node->IsA<UK2Node_SwitchName>())
	{
		Data->SetStringField(TEXT("flowType"), TEXT("SwitchName"));
	}
	else if (Node->IsA<UK2Node_ExecutionSequence>())
	{
		Data->SetStringField(TEXT("flowType"), TEXT("Sequence"));
	}

	return Data;
}
