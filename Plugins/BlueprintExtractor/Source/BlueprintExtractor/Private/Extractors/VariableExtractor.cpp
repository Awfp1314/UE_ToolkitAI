#include "Extractors/VariableExtractor.h"
#include "BlueprintJsonSchema.h"
#include "BlueprintExtractorModule.h"
#include "Engine/Blueprint.h"

TArray<TSharedPtr<FJsonValue>> FVariableExtractor::Extract(const UBlueprint* Blueprint)
{
	TArray<TSharedPtr<FJsonValue>> Result;

	if (!ensureMsgf(Blueprint, TEXT("VariableExtractor: null Blueprint")))
	{
		return Result;
	}

	for (const FBPVariableDescription& Var : Blueprint->NewVariables)
	{
		TSharedPtr<FJsonObject> VarObj = MakeShared<FJsonObject>();

		VarObj->SetStringField(TEXT("name"), Var.VarName.ToString());
		VarObj->SetObjectField(TEXT("type"), FBlueprintJsonSchema::SerializePinType(Var.VarType));
		VarObj->SetStringField(TEXT("defaultValue"), Var.DefaultValue);
		VarObj->SetArrayField(TEXT("propertyFlags"), FBlueprintJsonSchema::SerializePropertyFlags(Var.PropertyFlags));
		VarObj->SetStringField(TEXT("category"), Var.Category.ToString());

		if (!Var.RepNotifyFunc.IsNone())
		{
			VarObj->SetStringField(TEXT("repNotifyFunc"), Var.RepNotifyFunc.ToString());
		}

		// Variable metadata from MetaDataArray
		TSharedPtr<FJsonObject> MetaObj = MakeShared<FJsonObject>();
		for (const FBPVariableMetaDataEntry& Entry : Var.MetaDataArray)
		{
			MetaObj->SetStringField(Entry.DataKey.ToString(), Entry.DataValue);
		}
		if (MetaObj->Values.Num() > 0)
		{
			VarObj->SetObjectField(TEXT("metadata"), MetaObj);
		}

		Result.Add(MakeShared<FJsonValueObject>(VarObj));
	}

	return Result;
}
