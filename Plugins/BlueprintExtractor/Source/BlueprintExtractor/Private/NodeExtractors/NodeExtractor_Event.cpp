#include "NodeExtractors/NodeExtractor_Event.h"
#include "BlueprintJsonSchema.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"

bool FNodeExtractor_Event::CanHandle(const UK2Node* Node) const
{
	return Node && (
		Node->IsA<UK2Node_Event>() ||
		Node->IsA<UK2Node_FunctionEntry>() ||
		Node->IsA<UK2Node_FunctionResult>()
	);
}

TSharedPtr<FJsonObject> FNodeExtractor_Event::ExtractTypeSpecificData(const UK2Node* Node) const
{
	TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();

	if (const UK2Node_Event* EventNode = Cast<UK2Node_Event>(Node))
	{
		Data->SetStringField(TEXT("eventName"), EventNode->EventReference.GetMemberName().ToString());

		if (UClass* OwnerClass = EventNode->EventReference.GetMemberParentClass())
		{
			Data->SetStringField(TEXT("ownerClass"), FBlueprintJsonSchema::GetObjectPathString(OwnerClass));
		}

		Data->SetBoolField(TEXT("isOverride"), EventNode->bOverrideFunction);
		Data->SetStringField(TEXT("nodeSubtype"), TEXT("Event"));
	}
	else if (const UK2Node_FunctionEntry* EntryNode = Cast<UK2Node_FunctionEntry>(Node))
	{
		Data->SetStringField(TEXT("nodeSubtype"), TEXT("FunctionEntry"));
		Data->SetNumberField(TEXT("extraFlags"), static_cast<double>(EntryNode->GetExtraFlags()));
	}
	else if (Cast<UK2Node_FunctionResult>(Node))
	{
		Data->SetStringField(TEXT("nodeSubtype"), TEXT("FunctionResult"));
	}

	return Data;
}
