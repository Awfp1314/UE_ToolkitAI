#include "Extractors/UserDefinedStructExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "BlueprintJsonSchema.h"
#include "PropertySerializer.h"
#include "Kismet2/StructureEditorUtils.h"
#include "StructUtils/UserDefinedStruct.h"
#include "UserDefinedStructure/UserDefinedStructEditorData.h"

TSharedPtr<FJsonObject> FUserDefinedStructExtractor::Extract(const UUserDefinedStruct* UserDefinedStruct)
{
	if (!UserDefinedStruct)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> StructObject = MakeShared<FJsonObject>();
	StructObject->SetStringField(TEXT("assetPath"), UserDefinedStruct->GetPathName());
	StructObject->SetStringField(TEXT("assetName"), UserDefinedStruct->GetName());
	StructObject->SetStringField(TEXT("structGuid"), UserDefinedStruct->GetCustomGuid().ToString());

	if (const UEnum* StatusEnum = StaticEnum<EUserDefinedStructureStatus>())
	{
		StructObject->SetStringField(TEXT("status"), StatusEnum->GetNameStringByValue(UserDefinedStruct->Status));
	}

	const uint8* DefaultInstance = UserDefinedStruct->GetDefaultInstance();
	const TArray<FStructVariableDescription>& VariableDescriptions = FStructureEditorUtils::GetVarDesc(UserDefinedStruct);

	TArray<TSharedPtr<FJsonValue>> Fields;
	for (const FStructVariableDescription& VariableDescription : VariableDescriptions)
	{
		TSharedPtr<FJsonObject> FieldObject = MakeShared<FJsonObject>();
		FieldObject->SetStringField(TEXT("name"), VariableDescription.VarName.ToString());
		FieldObject->SetStringField(TEXT("guid"), VariableDescription.VarGuid.ToString());
		FieldObject->SetBoolField(TEXT("isInvalidMember"), VariableDescription.bInvalidMember != 0);
		FieldObject->SetBoolField(TEXT("editableOnInstance"), VariableDescription.bDontEditOnInstance == 0);
		FieldObject->SetBoolField(TEXT("saveGame"), VariableDescription.bEnableSaveGame != 0);
		FieldObject->SetBoolField(TEXT("multiLineText"), VariableDescription.bEnableMultiLineText != 0);
		FieldObject->SetBoolField(TEXT("use3dWidget"), VariableDescription.bEnable3dWidget != 0);

		if (!VariableDescription.FriendlyName.IsEmpty())
		{
			FieldObject->SetStringField(TEXT("friendlyName"), VariableDescription.FriendlyName);
		}
		if (!VariableDescription.Category.IsNone())
		{
			FieldObject->SetStringField(TEXT("category"), VariableDescription.Category.ToString());
		}
		if (!VariableDescription.ToolTip.IsEmpty())
		{
			FieldObject->SetStringField(TEXT("tooltip"), VariableDescription.ToolTip);
		}

		FieldObject->SetObjectField(TEXT("pinType"), FBlueprintJsonSchema::SerializePinType(VariableDescription.ToPinType()));

		if (VariableDescription.MetaData.Num() > 0)
		{
			TSharedPtr<FJsonObject> MetadataObject = MakeShared<FJsonObject>();
			for (const TPair<FName, FString>& MetadataPair : VariableDescription.MetaData)
			{
				MetadataObject->SetStringField(MetadataPair.Key.ToString(), MetadataPair.Value);
			}
			FieldObject->SetObjectField(TEXT("metadata"), MetadataObject);
		}

		if (const FProperty* Property = FStructureEditorUtils::GetPropertyByGuid(UserDefinedStruct, VariableDescription.VarGuid))
		{
			FieldObject->SetStringField(TEXT("cppType"), Property->GetCPPType());

			if (DefaultInstance)
			{
				const void* ValuePtr = Property->ContainerPtrToValuePtr<void>(DefaultInstance);
				if (const TSharedPtr<FJsonValue> DefaultValue = FPropertySerializer::SerializePropertyValue(Property, ValuePtr))
				{
					FieldObject->SetField(TEXT("defaultValue"), DefaultValue);
				}
			}
		}
		else if (!VariableDescription.DefaultValue.IsEmpty())
		{
			FieldObject->SetStringField(TEXT("defaultValue"), VariableDescription.DefaultValue);
		}

		Fields.Add(MakeShared<FJsonValueObject>(FieldObject));
	}

	StructObject->SetArrayField(TEXT("fields"), Fields);
	Root->SetObjectField(TEXT("userDefinedStruct"), StructObject);
	return Root;
}
