#include "NodeExtractors/NodeExtractor_CallFunction.h"
#include "BlueprintJsonSchema.h"
#include "K2Node_CallFunction.h"

bool FNodeExtractor_CallFunction::CanHandle(const UK2Node* Node) const
{
	return Node && Node->IsA<UK2Node_CallFunction>();
}

TSharedPtr<FJsonObject> FNodeExtractor_CallFunction::ExtractTypeSpecificData(const UK2Node* Node) const
{
	const UK2Node_CallFunction* CallNode = Cast<UK2Node_CallFunction>(Node);
	if (!CallNode)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();

	Data->SetStringField(TEXT("functionName"), CallNode->FunctionReference.GetMemberName().ToString());

	if (UClass* OwnerClass = CallNode->FunctionReference.GetMemberParentClass())
	{
		Data->SetStringField(TEXT("ownerClass"), FBlueprintJsonSchema::GetObjectPathString(OwnerClass));
	}

	Data->SetBoolField(TEXT("isPure"), CallNode->IsNodePure());
	Data->SetBoolField(TEXT("isLatent"), CallNode->IsLatentFunction());

	if (const UFunction* Function = CallNode->GetTargetFunction())
	{
		Data->SetBoolField(TEXT("isStatic"), Function->HasAnyFunctionFlags(FUNC_Static));
	}

	return Data;
}
