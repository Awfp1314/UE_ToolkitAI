#include "NodeExtractors/NodeExtractor_Variable.h"
#include "BlueprintJsonSchema.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"

bool FNodeExtractor_Variable::CanHandle(const UK2Node* Node) const
{
	return Node && (Node->IsA<UK2Node_VariableGet>() || Node->IsA<UK2Node_VariableSet>());
}

TSharedPtr<FJsonObject> FNodeExtractor_Variable::ExtractTypeSpecificData(const UK2Node* Node) const
{
	TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();

	if (const UK2Node_VariableGet* GetNode = Cast<UK2Node_VariableGet>(Node))
	{
		Data->SetStringField(TEXT("variableName"), GetNode->GetVarName().ToString());
		Data->SetStringField(TEXT("accessType"), TEXT("Get"));
		Data->SetBoolField(TEXT("isPure"), true);

		if (UClass* VarClass = GetNode->VariableReference.GetMemberParentClass())
		{
			Data->SetStringField(TEXT("ownerClass"), FBlueprintJsonSchema::GetObjectPathString(VarClass));
		}
	}
	else if (const UK2Node_VariableSet* SetNode = Cast<UK2Node_VariableSet>(Node))
	{
		Data->SetStringField(TEXT("variableName"), SetNode->GetVarName().ToString());
		Data->SetStringField(TEXT("accessType"), TEXT("Set"));
		Data->SetBoolField(TEXT("isPure"), false);

		if (UClass* VarClass = SetNode->VariableReference.GetMemberParentClass())
		{
			Data->SetStringField(TEXT("ownerClass"), FBlueprintJsonSchema::GetObjectPathString(VarClass));
		}
	}

	return Data;
}
