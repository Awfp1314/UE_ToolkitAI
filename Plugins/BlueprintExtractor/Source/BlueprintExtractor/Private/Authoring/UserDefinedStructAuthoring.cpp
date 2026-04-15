#include "Authoring/UserDefinedStructAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Kismet2/StructureEditorUtils.h"
#include "Misc/PackageName.h"
#include "StructUtils/UserDefinedStruct.h"
#include "UserDefinedStructure/UserDefinedStructEditorData.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/UnrealType.h"

namespace UserDefinedStructAuthoringInternal
{

struct FFieldSelector
{
	FGuid Guid;
	FString Name;
};

static TSharedPtr<FJsonObject> NormalizePayload(
	const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* NestedPayload = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("userDefinedStruct"), NestedPayload)
		&& NestedPayload && NestedPayload->IsValid())
	{
		return *NestedPayload;
	}

	return PayloadJson;
}

static TArray<TSharedPtr<FJsonValue>> GetFieldsArray(
	const TSharedPtr<FJsonObject>& Payload)
{
	const TArray<TSharedPtr<FJsonValue>>* Fields = nullptr;
	if (Payload.IsValid()
		&& Payload->TryGetArrayField(TEXT("fields"), Fields)
		&& Fields)
	{
		return *Fields;
	}

	return {};
}

static FString GetDesiredFieldName(const TSharedPtr<FJsonObject>& FieldObject)
{
	FString FriendlyName;
	if (FieldObject.IsValid()
		&& FieldObject->TryGetStringField(TEXT("friendlyName"), FriendlyName)
		&& !FriendlyName.IsEmpty())
	{
		return FriendlyName;
	}

	FString Name;
	if (FieldObject.IsValid())
	{
		FieldObject->TryGetStringField(TEXT("name"), Name);
	}
	return Name;
}

static bool BuildFieldSelector(const TSharedPtr<FJsonObject>& Payload,
                               FFieldSelector& OutSelector,
                               FString& OutError)
{
	if (!Payload.IsValid())
	{
		OutError = TEXT("Field selector payload must be an object.");
		return false;
	}

	FString GuidString;
	if (Payload->TryGetStringField(TEXT("guid"), GuidString)
		&& !GuidString.IsEmpty())
	{
		OutSelector.Guid = FGuid(GuidString);
		if (!OutSelector.Guid.IsValid())
		{
			OutError = FString::Printf(TEXT("Invalid field guid '%s'."), *GuidString);
			return false;
		}
		return true;
	}

	if ((Payload->TryGetStringField(TEXT("name"), OutSelector.Name)
		 || Payload->TryGetStringField(TEXT("fieldName"), OutSelector.Name))
		&& !OutSelector.Name.IsEmpty())
	{
		return true;
	}

	OutError = TEXT("Field selector requires either guid or name.");
	return false;
}

static FStructVariableDescription* FindField(UUserDefinedStruct* UserDefinedStruct,
                                             const FFieldSelector& Selector)
{
	if (!UserDefinedStruct)
	{
		return nullptr;
	}

	if (Selector.Guid.IsValid())
	{
		return FStructureEditorUtils::GetVarDescByGuid(
			UserDefinedStruct,
			Selector.Guid);
	}

	if (!Selector.Name.IsEmpty())
	{
		for (FStructVariableDescription& Description
		     : FStructureEditorUtils::GetVarDesc(UserDefinedStruct))
		{
			if (Description.VarName.ToString() == Selector.Name
				|| Description.FriendlyName == Selector.Name)
			{
				return &Description;
			}
		}
	}

	return nullptr;
}

static bool AppendValidationSummary(FAssetMutationContext& Context,
                                    const TArray<FString>& Errors,
                                    const FString& Summary)
{
	const bool bSuccess = Errors.Num() == 0;
	Context.SetValidationSummary(bSuccess, Summary, Errors);
	for (const FString& Error : Errors)
	{
		Context.AddError(TEXT("validation_error"), Error, Context.AssetPath);
	}
	return bSuccess;
}

static bool AddField(UUserDefinedStruct* UserDefinedStruct,
                     const TSharedPtr<FJsonObject>& FieldObject,
                     FGuid& OutFieldGuid,
                     TArray<FString>& OutErrors)
{
	if (!UserDefinedStruct || !FieldObject.IsValid())
	{
		OutErrors.Add(TEXT("Invalid field payload."));
		return false;
	}

	const TSharedPtr<FJsonObject>* PinTypeObject = nullptr;
	if (!FieldObject->TryGetObjectField(TEXT("pinType"), PinTypeObject)
		|| !PinTypeObject
		|| !PinTypeObject->IsValid())
	{
		OutErrors.Add(TEXT("Field pinType is required when adding a struct field."));
		return false;
	}

	FEdGraphPinType ParsedPinType;
	FString PinTypeError;
	if (!FAuthoringHelpers::ParsePinType(
		    *PinTypeObject,
		    ParsedPinType,
		    PinTypeError))
	{
		OutErrors.Add(PinTypeError);
		return false;
	}

	if (!FStructureEditorUtils::AddVariable(UserDefinedStruct, ParsedPinType))
	{
		OutErrors.Add(TEXT("Failed to add UserDefinedStruct field."));
		return false;
	}

	TArray<FStructVariableDescription>& Fields =
		FStructureEditorUtils::GetVarDesc(UserDefinedStruct);
	if (Fields.Num() == 0)
	{
		OutErrors.Add(
			TEXT("UserDefinedStruct field add succeeded but no fields exist."));
		return false;
	}

	OutFieldGuid = Fields.Last().VarGuid;
	return true;
}

static bool ApplyFieldDefinition(UUserDefinedStruct* UserDefinedStruct,
                                 const FGuid FieldGuid,
                                 const TSharedPtr<FJsonObject>& FieldObject,
                                 TArray<FString>& OutErrors,
                                 const bool bReplaceMetadata)
{
	if (!UserDefinedStruct || !FieldObject.IsValid())
	{
		OutErrors.Add(TEXT("Invalid field definition."));
		return false;
	}

	FStructVariableDescription* FieldDescription =
		FStructureEditorUtils::GetVarDescByGuid(UserDefinedStruct, FieldGuid);
	if (!FieldDescription)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Field with guid '%s' was not found."),
			*FieldGuid.ToString()));
		return false;
	}

	const FString DesiredName = GetDesiredFieldName(FieldObject);
	if (!DesiredName.IsEmpty() && FieldDescription->FriendlyName != DesiredName)
	{
		if (!FStructureEditorUtils::RenameVariable(
			    UserDefinedStruct,
			    FieldGuid,
			    DesiredName))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to rename field '%s' to '%s'."),
				*FieldDescription->VarName.ToString(),
				*DesiredName));
			return false;
		}

		FieldDescription = FStructureEditorUtils::GetVarDescByGuid(
			UserDefinedStruct,
			FieldGuid);
	}

	const TSharedPtr<FJsonObject>* PinTypeObject = nullptr;
	if (FieldObject->TryGetObjectField(TEXT("pinType"), PinTypeObject)
		&& PinTypeObject
		&& PinTypeObject->IsValid())
	{
		FEdGraphPinType ParsedPinType;
		FString PinTypeError;
		if (!FAuthoringHelpers::ParsePinType(
			    *PinTypeObject,
			    ParsedPinType,
			    PinTypeError))
		{
			OutErrors.Add(PinTypeError);
			return false;
		}

		if (FieldDescription->ToPinType() != ParsedPinType
			&& !FStructureEditorUtils::ChangeVariableType(
				UserDefinedStruct,
				FieldGuid,
				ParsedPinType))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to change field type for '%s'."),
				*DesiredName));
			return false;
		}

		FieldDescription = FStructureEditorUtils::GetVarDescByGuid(
			UserDefinedStruct,
			FieldGuid);
	}

	bool bNeedsStructureChange = false;

	const TSharedPtr<FJsonObject>* MetadataObject = nullptr;
	if (FieldDescription
		&& (bReplaceMetadata || FieldObject->HasField(TEXT("metadata"))))
	{
		FStructureEditorUtils::ModifyStructData(UserDefinedStruct);

		if (bReplaceMetadata)
		{
			FieldDescription->MetaData.Reset();
		}

		if (FieldObject->TryGetObjectField(TEXT("metadata"), MetadataObject)
			&& MetadataObject
			&& MetadataObject->IsValid())
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair
			     : (*MetadataObject)->Values)
			{
				FString MetadataValue;
				if (!Pair.Value.IsValid()
					|| !Pair.Value->TryGetString(MetadataValue))
				{
					OutErrors.Add(FString::Printf(
						TEXT("Field '%s' metadata '%s' must be a string."),
						*DesiredName,
						*Pair.Key));
					continue;
				}

				if (!FStructureEditorUtils::SetMetaData(
					    UserDefinedStruct,
					    FieldGuid,
					    FName(*Pair.Key),
					    MetadataValue))
				{
					OutErrors.Add(FString::Printf(
						TEXT("Failed to set metadata '%s' on '%s'."),
						*Pair.Key,
						*DesiredName));
				}
			}
		}

		bNeedsStructureChange = true;
	}

	FString Category;
	if (FieldDescription
		&& (FieldObject->TryGetStringField(TEXT("category"), Category)
			|| bReplaceMetadata))
	{
		FStructureEditorUtils::ModifyStructData(UserDefinedStruct);
		FieldDescription->Category =
			Category.IsEmpty() ? NAME_None : FName(*Category);
		bNeedsStructureChange = true;
	}

	FString Tooltip;
	if (FieldObject->TryGetStringField(TEXT("tooltip"), Tooltip))
	{
		if (!FStructureEditorUtils::ChangeVariableTooltip(
			    UserDefinedStruct,
			    FieldGuid,
			    Tooltip))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to change tooltip for field '%s'."),
				*DesiredName));
		}
	}

	auto ApplyOptionalBool = [&](const TCHAR* FieldName,
	                             TFunctionRef<bool(bool)> ApplyFn)
	{
		bool bValue = false;
		if (!FieldObject->TryGetBoolField(FieldName, bValue))
		{
			return;
		}

		if (!ApplyFn(bValue))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to apply '%s' for field '%s'."),
				FieldName,
				*DesiredName));
		}
	};

	ApplyOptionalBool(TEXT("editableOnInstance"), [&](const bool bValue)
	{
		return FStructureEditorUtils::ChangeEditableOnBPInstance(
			UserDefinedStruct,
			FieldGuid,
			bValue);
	});

	ApplyOptionalBool(TEXT("saveGame"), [&](const bool bValue)
	{
		return FStructureEditorUtils::ChangeSaveGameEnabled(
			UserDefinedStruct,
			FieldGuid,
			bValue);
	});

	ApplyOptionalBool(TEXT("multiLineText"), [&](const bool bValue)
	{
		return FStructureEditorUtils::ChangeMultiLineTextEnabled(
			UserDefinedStruct,
			FieldGuid,
			bValue);
	});

	ApplyOptionalBool(TEXT("use3dWidget"), [&](const bool bValue)
	{
		return FStructureEditorUtils::Change3dWidgetEnabled(
			UserDefinedStruct,
			FieldGuid,
			bValue);
	});

	if (FieldObject->HasField(TEXT("defaultValue")))
	{
		const FProperty* Property = FStructureEditorUtils::GetPropertyByGuid(
			UserDefinedStruct,
			FieldGuid);
		if (!Property)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to resolve property for '%s'."),
				*DesiredName));
		}
		else
		{
			const TSharedPtr<FJsonValue>* DefaultValue =
				FieldObject->Values.Find(TEXT("defaultValue"));
			FString ExportText;
			if (!DefaultValue
				|| !FAuthoringHelpers::JsonValueToPropertyExportText(
					Property,
					*DefaultValue,
					ExportText,
					OutErrors,
					UserDefinedStruct))
			{
				OutErrors.Add(FString::Printf(
					TEXT("Failed to convert default value for '%s'."),
					*DesiredName));
			}
			else if (!FStructureEditorUtils::ChangeVariableDefaultValue(
				         UserDefinedStruct,
				         FieldGuid,
				         ExportText))
			{
				OutErrors.Add(FString::Printf(
					TEXT("Failed to apply default value for '%s'."),
					*DesiredName));
			}
		}
	}

	if (bNeedsStructureChange)
	{
		FStructureEditorUtils::OnStructureChanged(
			UserDefinedStruct,
			FStructureEditorUtils::EStructureEditorChangeInfo::Unknown);
	}

	return OutErrors.Num() == 0;
}

static bool ReplaceFields(UUserDefinedStruct* UserDefinedStruct,
                          const TArray<TSharedPtr<FJsonValue>>& Fields,
                          TArray<FString>& OutErrors)
{
	if (!UserDefinedStruct)
	{
		OutErrors.Add(TEXT("UserDefinedStruct is null."));
		return false;
	}

	if (Fields.Num() == 0)
	{
		OutErrors.Add(
			TEXT("UserDefinedStructs cannot be empty in UE 5.6."));
		return false;
	}

	TArray<FStructVariableDescription>& ExistingFields =
		FStructureEditorUtils::GetVarDesc(UserDefinedStruct);

	while (ExistingFields.Num() > Fields.Num() && ExistingFields.Num() > 1)
	{
		const FGuid FieldGuid = ExistingFields.Last().VarGuid;
		const FString FieldName = ExistingFields.Last().VarName.ToString();
		if (!FStructureEditorUtils::RemoveVariable(UserDefinedStruct, FieldGuid))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to remove trailing field '%s'."),
				*FieldName));
			return false;
		}

		ExistingFields = FStructureEditorUtils::GetVarDesc(UserDefinedStruct);
	}

	while (ExistingFields.Num() < Fields.Num())
	{
		FGuid AddedGuid;
		const TSharedPtr<FJsonObject> FieldObject =
			Fields[ExistingFields.Num()].IsValid()
				? Fields[ExistingFields.Num()]->AsObject()
				: nullptr;
		if (!AddField(UserDefinedStruct, FieldObject, AddedGuid, OutErrors))
		{
			return false;
		}

		ExistingFields = FStructureEditorUtils::GetVarDesc(UserDefinedStruct);
	}

	if (ExistingFields.Num() != Fields.Num())
	{
		OutErrors.Add(TEXT("Failed to reconcile field count."));
		return false;
	}

	for (int32 Index = 0; Index < Fields.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> FieldObject =
			Fields[Index].IsValid() ? Fields[Index]->AsObject() : nullptr;
		if (!FieldObject.IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("fields[%d] must be an object."),
				Index));
			continue;
		}

		const FGuid FieldGuid = ExistingFields[Index].VarGuid;
		ApplyFieldDefinition(
			UserDefinedStruct,
			FieldGuid,
			FieldObject,
			OutErrors,
			true);
		ExistingFields = FStructureEditorUtils::GetVarDesc(UserDefinedStruct);
	}

	return OutErrors.Num() == 0;
}

static bool RenameField(UUserDefinedStruct* UserDefinedStruct,
                        const TSharedPtr<FJsonObject>& Payload,
                        TArray<FString>& OutErrors)
{
	FFieldSelector Selector;
	FString SelectorError;
	if (!BuildFieldSelector(Payload, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	FStructVariableDescription* Field = FindField(UserDefinedStruct, Selector);
	if (!Field)
	{
		OutErrors.Add(TEXT("Struct field selector did not match an existing field."));
		return false;
	}

	FString NewName;
	if (!Payload->TryGetStringField(TEXT("newName"), NewName) || NewName.IsEmpty())
	{
		OutErrors.Add(TEXT("rename_field requires newName."));
		return false;
	}

	if (!FStructureEditorUtils::RenameVariable(
		    UserDefinedStruct,
		    Field->VarGuid,
		    NewName))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to rename field '%s'."),
			*Field->VarName.ToString()));
		return false;
	}

	return true;
}

static bool PatchField(UUserDefinedStruct* UserDefinedStruct,
                       const TSharedPtr<FJsonObject>& Payload,
                       TArray<FString>& OutErrors)
{
	const TSharedPtr<FJsonObject>* FieldObject = nullptr;
	TSharedPtr<FJsonObject> EffectiveFieldObject = Payload;
	if (Payload.IsValid()
		&& Payload->TryGetObjectField(TEXT("field"), FieldObject)
		&& FieldObject
		&& FieldObject->IsValid())
	{
		EffectiveFieldObject = *FieldObject;
	}

	FFieldSelector Selector;
	FString SelectorError;
	if (!BuildFieldSelector(EffectiveFieldObject, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	FStructVariableDescription* Field = FindField(UserDefinedStruct, Selector);
	if (!Field)
	{
		OutErrors.Add(TEXT("Struct field selector did not match an existing field."));
		return false;
	}

	return ApplyFieldDefinition(
		UserDefinedStruct,
		Field->VarGuid,
		EffectiveFieldObject,
		OutErrors,
		false);
}

static bool RemoveField(UUserDefinedStruct* UserDefinedStruct,
                        const TSharedPtr<FJsonObject>& Payload,
                        TArray<FString>& OutErrors)
{
	TArray<FStructVariableDescription>& Fields =
		FStructureEditorUtils::GetVarDesc(UserDefinedStruct);
	if (Fields.Num() <= 1)
	{
		OutErrors.Add(
			TEXT("UE 5.6 does not allow removing the final struct field."));
		return false;
	}

	FFieldSelector Selector;
	FString SelectorError;
	if (!BuildFieldSelector(Payload, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	FStructVariableDescription* Field = FindField(UserDefinedStruct, Selector);
	if (!Field)
	{
		OutErrors.Add(TEXT("Struct field selector did not match an existing field."));
		return false;
	}

	const FGuid FieldGuid = Field->VarGuid;
	const FString FieldName = Field->VarName.ToString();
	if (!FStructureEditorUtils::RemoveVariable(UserDefinedStruct, FieldGuid))
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to remove field '%s'."),
			*FieldName));
		return false;
	}

	return true;
}

static bool ReorderFields(UUserDefinedStruct* UserDefinedStruct,
                          const TSharedPtr<FJsonObject>& Payload,
                          TArray<FString>& OutErrors)
{
	const TArray<TSharedPtr<FJsonValue>>* OrderArray = nullptr;
	if (!Payload.IsValid()
		|| !Payload->TryGetArrayField(TEXT("fieldOrder"), OrderArray)
		|| !OrderArray)
	{
		OutErrors.Add(TEXT("reorder_fields requires fieldOrder."));
		return false;
	}

	TArray<FGuid> CurrentOrder;
	for (const FStructVariableDescription& Field
	     : FStructureEditorUtils::GetVarDesc(UserDefinedStruct))
	{
		CurrentOrder.Add(Field.VarGuid);
	}

	if (OrderArray->Num() != CurrentOrder.Num())
	{
		OutErrors.Add(
			TEXT("fieldOrder must contain exactly one selector per field."));
		return false;
	}

	for (int32 TargetIndex = 0; TargetIndex < OrderArray->Num(); ++TargetIndex)
	{
		const TSharedPtr<FJsonObject> SelectorObject =
			(*OrderArray)[TargetIndex].IsValid()
				? (*OrderArray)[TargetIndex]->AsObject()
				: nullptr;
		FFieldSelector Selector;
		FString SelectorError;
		if (!BuildFieldSelector(SelectorObject, Selector, SelectorError))
		{
			OutErrors.Add(FString::Printf(
				TEXT("fieldOrder[%d]: %s"),
				TargetIndex,
				*SelectorError));
			continue;
		}

		FStructVariableDescription* Field = FindField(UserDefinedStruct, Selector);
		if (!Field)
		{
			OutErrors.Add(FString::Printf(
				TEXT("fieldOrder[%d]: selector did not resolve."),
				TargetIndex));
			continue;
		}

		const FGuid DesiredGuid = Field->VarGuid;
		const int32 CurrentIndex = CurrentOrder.IndexOfByKey(DesiredGuid);
		if (CurrentIndex == INDEX_NONE)
		{
			OutErrors.Add(FString::Printf(
				TEXT("fieldOrder[%d]: internal field order mismatch."),
				TargetIndex));
			continue;
		}

		if (CurrentIndex == TargetIndex)
		{
			continue;
		}

		const FGuid RelativeGuid =
			(TargetIndex == 0) ? CurrentOrder[0] : CurrentOrder[TargetIndex - 1];
		const FStructureEditorUtils::EMovePosition Position =
			(TargetIndex == 0)
				? FStructureEditorUtils::PositionAbove
				: FStructureEditorUtils::PositionBelow;

		if (!FStructureEditorUtils::MoveVariable(
			    UserDefinedStruct,
			    DesiredGuid,
			    RelativeGuid,
			    Position))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to move field into position %d."),
				TargetIndex));
			continue;
		}

		CurrentOrder.RemoveAt(CurrentIndex);
		CurrentOrder.Insert(DesiredGuid, TargetIndex);
	}

	return OutErrors.Num() == 0;
}

static bool ApplyOperation(UUserDefinedStruct* UserDefinedStruct,
                           const FString& Operation,
                           const TSharedPtr<FJsonObject>& Payload,
                           TArray<FString>& OutErrors)
{
	if (Operation == TEXT("replace_fields"))
	{
		return ReplaceFields(UserDefinedStruct, GetFieldsArray(Payload), OutErrors);
	}
	if (Operation == TEXT("patch_field"))
	{
		return PatchField(UserDefinedStruct, Payload, OutErrors);
	}
	if (Operation == TEXT("rename_field"))
	{
		return RenameField(UserDefinedStruct, Payload, OutErrors);
	}
	if (Operation == TEXT("remove_field"))
	{
		return RemoveField(UserDefinedStruct, Payload, OutErrors);
	}
	if (Operation == TEXT("reorder_fields"))
	{
		return ReorderFields(UserDefinedStruct, Payload, OutErrors);
	}

	OutErrors.Add(FString::Printf(
		TEXT("Unsupported UserDefinedStruct operation '%s'."),
		*Operation));
	return false;
}

} // namespace UserDefinedStructAuthoringInternal

TSharedPtr<FJsonObject> FUserDefinedStructAuthoring::Create(
	const FString& AssetPath,
	const TSharedPtr<FJsonObject>& PayloadJson,
	const bool bValidateOnly)
{
	using namespace UserDefinedStructAuthoringInternal;

	FAssetMutationContext Context(
		TEXT("create_user_defined_struct"),
		AssetPath,
		TEXT("UserDefinedStruct"),
		bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(
			TEXT("asset_exists"),
			FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	const FName PreviewName = MakeUniqueObjectName(
		GetTransientPackage(),
		UUserDefinedStruct::StaticClass(),
		TEXT("UDSPreview"));
	UUserDefinedStruct* PreviewStruct = FStructureEditorUtils::CreateUserDefinedStruct(
		GetTransientPackage(),
		PreviewName,
		RF_Transient);
	if (!PreviewStruct)
	{
		Context.AddError(
			TEXT("preview_create_failed"),
			TEXT("Failed to create transient UserDefinedStruct preview."));
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	ApplyOperation(PreviewStruct, TEXT("replace_fields"), Payload, ValidationErrors);

	FString Tooltip;
	if (Payload->TryGetStringField(TEXT("tooltip"), Tooltip)
		&& !FStructureEditorUtils::ChangeTooltip(PreviewStruct, Tooltip))
	{
		ValidationErrors.Add(TEXT("Failed to apply struct tooltip in preview."));
	}

	if (!AppendValidationSummary(
		    Context,
		    ValidationErrors,
		    TEXT("UserDefinedStruct payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create UserDefinedStruct")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(
			TEXT("package_create_failed"),
			FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UUserDefinedStruct* UserDefinedStruct = FStructureEditorUtils::CreateUserDefinedStruct(
		Package,
		AssetName,
		RF_Public | RF_Standalone);
	if (!UserDefinedStruct)
	{
		Context.AddError(
			TEXT("asset_create_failed"),
			FString::Printf(
				TEXT("Failed to create UserDefinedStruct asset: %s"),
				*AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	UserDefinedStruct->Modify();

	TArray<FString> ApplyErrors;
	ApplyOperation(UserDefinedStruct, TEXT("replace_fields"), Payload, ApplyErrors);
	if (Payload->TryGetStringField(TEXT("tooltip"), Tooltip)
		&& !FStructureEditorUtils::ChangeTooltip(UserDefinedStruct, Tooltip))
	{
		ApplyErrors.Add(TEXT("Failed to apply struct tooltip."));
	}

	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(UserDefinedStruct);
	UserDefinedStruct->MarkPackageDirty();
	Context.TrackDirtyObject(UserDefinedStruct);
	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FUserDefinedStructAuthoring::Modify(
	UUserDefinedStruct* UserDefinedStruct,
	const FString& Operation,
	const TSharedPtr<FJsonObject>& PayloadJson,
	const bool bValidateOnly)
{
	using namespace UserDefinedStructAuthoringInternal;

	const FString AssetPath = UserDefinedStruct
		? UserDefinedStruct->GetPathName()
		: FString();
	FAssetMutationContext Context(
		TEXT("modify_user_defined_struct"),
		AssetPath,
		TEXT("UserDefinedStruct"),
		bValidateOnly);

	if (!UserDefinedStruct)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("UserDefinedStruct is null."));
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);
	UUserDefinedStruct* WorkingStruct = UserDefinedStruct;
	if (bValidateOnly)
	{
		WorkingStruct = DuplicateObject<UUserDefinedStruct>(
			UserDefinedStruct,
			GetTransientPackage());
		if (!WorkingStruct)
		{
			Context.AddError(
				TEXT("preview_duplicate_failed"),
				TEXT("Failed to duplicate UserDefinedStruct for validation."));
			return Context.BuildResult(false);
		}
	}

	TArray<FString> ValidationErrors;
	ApplyOperation(WorkingStruct, Operation, Payload, ValidationErrors);
	if (!AppendValidationSummary(
		    Context,
		    ValidationErrors,
		    TEXT("UserDefinedStruct payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify UserDefinedStruct")));
	UserDefinedStruct->Modify();

	TArray<FString> ApplyErrors;
	ApplyOperation(UserDefinedStruct, Operation, Payload, ApplyErrors);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	UserDefinedStruct->MarkPackageDirty();
	Context.TrackDirtyObject(UserDefinedStruct);
	return Context.BuildResult(true);
}
