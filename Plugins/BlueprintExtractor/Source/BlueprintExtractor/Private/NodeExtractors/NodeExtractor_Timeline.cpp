#include "NodeExtractors/NodeExtractor_Timeline.h"
#include "K2Node_Timeline.h"

bool FNodeExtractor_Timeline::CanHandle(const UK2Node* Node) const
{
	return Node && Node->IsA<UK2Node_Timeline>();
}

TSharedPtr<FJsonObject> FNodeExtractor_Timeline::ExtractTypeSpecificData(const UK2Node* Node) const
{
	const UK2Node_Timeline* TimelineNode = Cast<UK2Node_Timeline>(Node);
	if (!TimelineNode)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();

	Data->SetStringField(TEXT("timelineName"), TimelineNode->TimelineName.ToString());

	return Data;
}
