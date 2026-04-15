#include "Authoring/DataTableAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/DataTable.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace DataTableAuthoringInternal
{

struct FScopedStructMemory
{
	explicit FScopedStructMemory(UScriptStruct* InStruct)
		: ScriptStruct(InStruct)
	{
		if (ScriptStruct)
		{
			Data = FMemory::Malloc(ScriptStruct->GetStructureSize(), ScriptStruct->GetMinAlignment());
			ScriptStruct->InitializeStruct(Data);
		}
	}

	~FScopedStructMemory()
	{
		if (ScriptStruct && Data)
		{
			ScriptStruct->DestroyStruct(Data);
			FMemory::Free(Data);
		}
	}

	UScriptStruct* ScriptStruct = nullptr;
	void* Data = nullptr;
};

static UScriptStruct* ResolveRowStruct(const FString& RowStructPath)
{
	if (RowStructPath.IsEmpty())
	{
		return nullptr;
	}

	if (UScriptStruct* LoadedStruct = LoadObject<UScriptStruct>(nullptr, *RowStructPath))
	{
		return LoadedStruct;
	}

	return FindObject<UScriptStruct>(nullptr, *RowStructPath);
}

static void AppendValidationDiagnostics(FAssetMutationContext& Context,
                                        const TArray<FString>& ValidationErrors,
                                        const FString& DiagnosticPath)
{
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, DiagnosticPath);
	}
}

static bool ConvertPropertyArrayToObject(const TArray<TSharedPtr<FJsonValue>>& PropertyArray,
                                         TSharedPtr<FJsonObject>& OutProperties,
                                         TArray<FString>& OutErrors,
                                         const FString& RowPath)
{
	OutProperties = MakeShared<FJsonObject>();

	for (int32 Index = 0; Index < PropertyArray.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> PropertyObject = PropertyArray[Index].IsValid() ? PropertyArray[Index]->AsObject() : nullptr;
		if (!PropertyObject.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.properties[%d]: expected object entry"), *RowPath, Index));
			return false;
		}

		FString PropertyName;
		if (!PropertyObject->TryGetStringField(TEXT("name"), PropertyName) || PropertyName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.properties[%d]: missing property name"), *RowPath, Index));
			return false;
		}

		const TSharedPtr<FJsonValue>* Value = PropertyObject->Values.Find(TEXT("value"));
		if (!Value || !Value->IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.properties[%d]: missing value for '%s'"), *RowPath, Index, *PropertyName));
			return false;
		}

		OutProperties->SetField(PropertyName, *Value);
	}

	return true;
}

static bool ExtractRowPatch(const TSharedPtr<FJsonObject>& RowObject,
                            FName& OutRowName,
                            TSharedPtr<FJsonObject>& OutProperties,
                            TArray<FString>& OutErrors,
                            const FString& RowPath)
{
	if (!RowObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s: expected row object"), *RowPath));
		return false;
	}

	FString RowNameString;
	if (!RowObject->TryGetStringField(TEXT("rowName"), RowNameString) || RowNameString.IsEmpty())
	{
		OutErrors.Add(FString::Printf(TEXT("%s.rowName: missing row name"), *RowPath));
		return false;
	}

	OutRowName = FName(*RowNameString);

	const TSharedPtr<FJsonObject>* ObjectProperties = nullptr;
	if (RowObject->TryGetObjectField(TEXT("values"), ObjectProperties) && ObjectProperties && ObjectProperties->IsValid())
	{
		OutProperties = *ObjectProperties;
		return true;
	}

	if (RowObject->TryGetObjectField(TEXT("properties"), ObjectProperties) && ObjectProperties && ObjectProperties->IsValid())
	{
		OutProperties = *ObjectProperties;
		return true;
	}

	const TArray<TSharedPtr<FJsonValue>>* PropertyArray = nullptr;
	if (RowObject->TryGetArrayField(TEXT("properties"), PropertyArray) && PropertyArray)
	{
		return ConvertPropertyArrayToObject(*PropertyArray, OutProperties, OutErrors, RowPath);
	}

	OutProperties = MakeShared<FJsonObject>();
	return true;
}

static bool ApplyStructPatch(UScriptStruct* RowStruct,
                             void* RowMemory,
                             const TSharedPtr<FJsonObject>& Properties,
                             TArray<FString>& OutErrors,
                             const FString& RowPath,
                             const bool bValidationOnly)
{
	if (!RowStruct || !RowMemory || !Properties.IsValid())
	{
		return true;
	}

	bool bSuccess = true;
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Properties->Values)
	{
		FProperty* Property = RowStruct->FindPropertyByName(FName(*Pair.Key));
		if (!Property)
		{
			OutErrors.Add(FString::Printf(TEXT("%s.%s: property not found on row struct '%s'"),
				*RowPath,
				*Pair.Key,
				*RowStruct->GetName()));
			bSuccess = false;
			continue;
		}

		if (Property->HasAnyPropertyFlags(CPF_Deprecated | CPF_Transient))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.%s: property is not writable"), *RowPath, *Pair.Key));
			bSuccess = false;
			continue;
		}

		void* ValuePtr = Property->ContainerPtrToValuePtr<void>(RowMemory);
		bSuccess &= FPropertySerializer::ApplyJsonValueToProperty(
			Property,
			ValuePtr,
			nullptr,
			Pair.Value,
			OutErrors,
			bValidationOnly);
	}

	return bSuccess;
}

static bool ValidateRows(UScriptStruct* RowStruct,
                         const TArray<TSharedPtr<FJsonValue>>& Rows,
                         const UDataTable* ExistingTable,
                         const bool bReplacingRows,
                         TArray<FString>& OutErrors)
{
	bool bSuccess = true;
	for (int32 Index = 0; Index < Rows.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> RowObject = Rows[Index].IsValid() ? Rows[Index]->AsObject() : nullptr;
		const FString RowPath = FString::Printf(TEXT("rows[%d]"), Index);

		FName RowName = NAME_None;
		TSharedPtr<FJsonObject> Properties;
		if (!ExtractRowPatch(RowObject, RowName, Properties, OutErrors, RowPath))
		{
			bSuccess = false;
			continue;
		}

		FScopedStructMemory WorkingRow(RowStruct);
		if (!WorkingRow.Data)
		{
			OutErrors.Add(FString::Printf(TEXT("%s: failed to allocate row memory"), *RowPath));
			bSuccess = false;
			continue;
		}

		if (ExistingTable && !bReplacingRows)
		{
			if (const uint8* ExistingRow = ExistingTable->FindRowUnchecked(RowName))
			{
				RowStruct->CopyScriptStruct(WorkingRow.Data, ExistingRow);
			}
		}

		bSuccess &= ApplyStructPatch(RowStruct, WorkingRow.Data, Properties, OutErrors, RowPath, true);
	}

	return bSuccess;
}

static bool ApplyRows(UDataTable* DataTable,
                      const TArray<TSharedPtr<FJsonValue>>& Rows,
                      TArray<FString>& OutErrors)
{
	if (!DataTable)
	{
		OutErrors.Add(TEXT("DataTable is null."));
		return false;
	}

	UScriptStruct* RowStruct = const_cast<UScriptStruct*>(DataTable->GetRowStruct());
	if (!RowStruct)
	{
		OutErrors.Add(TEXT("DataTable has no row struct."));
		return false;
	}

	bool bSuccess = true;
	for (int32 Index = 0; Index < Rows.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> RowObject = Rows[Index].IsValid() ? Rows[Index]->AsObject() : nullptr;
		const FString RowPath = FString::Printf(TEXT("rows[%d]"), Index);

		FName RowName = NAME_None;
		TSharedPtr<FJsonObject> Properties;
		if (!ExtractRowPatch(RowObject, RowName, Properties, OutErrors, RowPath))
		{
			bSuccess = false;
			continue;
		}

		FScopedStructMemory WorkingRow(RowStruct);
		if (!WorkingRow.Data)
		{
			OutErrors.Add(FString::Printf(TEXT("%s: failed to allocate row memory"), *RowPath));
			bSuccess = false;
			continue;
		}

		if (const uint8* ExistingRow = DataTable->FindRowUnchecked(RowName))
		{
			RowStruct->CopyScriptStruct(WorkingRow.Data, ExistingRow);
		}

		bSuccess &= ApplyStructPatch(RowStruct, WorkingRow.Data, Properties, OutErrors, RowPath, false);
		if (!bSuccess)
		{
			continue;
		}

		DataTable->AddRow(RowName, static_cast<const uint8*>(WorkingRow.Data), RowStruct);
	}

	return bSuccess;
}

static bool ValidateDeleteRows(const TArray<TSharedPtr<FJsonValue>>& DeleteRows,
                               TArray<FString>& OutErrors)
{
	bool bSuccess = true;
	for (int32 Index = 0; Index < DeleteRows.Num(); ++Index)
	{
		FString RowName;
		if (!DeleteRows[Index].IsValid() || !DeleteRows[Index]->TryGetString(RowName) || RowName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("deleteRows[%d]: expected non-empty row name"), Index));
			bSuccess = false;
		}
	}
	return bSuccess;
}

static TArray<TSharedPtr<FJsonValue>> GetRowsArray(const TSharedPtr<FJsonObject>& PayloadJson)
{
	const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetArrayField(TEXT("rows"), Rows) && Rows)
	{
		return *Rows;
	}
	return {};
}

static TArray<TSharedPtr<FJsonValue>> GetDeleteRowsArray(const TSharedPtr<FJsonObject>& PayloadJson)
{
	const TArray<TSharedPtr<FJsonValue>>* DeleteRows = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetArrayField(TEXT("deleteRows"), DeleteRows) && DeleteRows)
	{
		return *DeleteRows;
	}
	return {};
}

} // namespace DataTableAuthoringInternal

TSharedPtr<FJsonObject> FDataTableAuthoring::Create(const FString& AssetPath,
                                                    const FString& RowStructPath,
                                                    const TArray<TSharedPtr<FJsonValue>>& Rows,
                                                    const bool bValidateOnly)
{
	using namespace DataTableAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_data_table"), AssetPath, TEXT("DataTable"), bValidateOnly);

	UScriptStruct* RowStruct = ResolveRowStruct(RowStructPath);
	if (!RowStruct)
	{
		Context.AddError(TEXT("row_struct_not_found"),
		                 FString::Printf(TEXT("Row struct not found: %s"), *RowStructPath),
		                 RowStructPath);
		return Context.BuildResult(false);
	}

	if (!RowStruct->IsChildOf(FTableRowBase::StaticStruct()))
	{
		Context.AddError(TEXT("invalid_row_struct"),
		                 FString::Printf(TEXT("Row struct '%s' must derive from FTableRowBase."), *RowStruct->GetName()),
		                 RowStructPath);
		return Context.BuildResult(false);
	}

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	const bool bValid = ValidateRows(RowStruct, Rows, nullptr, true, ValidationErrors);
	Context.SetValidationSummary(
		bValid,
		bValid ? TEXT("DataTable payload validated.") : TEXT("DataTable payload failed validation."),
		ValidationErrors);
	AppendValidationDiagnostics(Context, ValidationErrors, AssetPath);
	if (!bValid)
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create DataTable")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UDataTable* DataTable = NewObject<UDataTable>(Package, AssetName, RF_Public | RF_Standalone);
	if (!DataTable)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create DataTable asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	DataTable->Modify();
	DataTable->RowStruct = RowStruct;

	TArray<FString> ApplyErrors;
	const bool bApplySuccess = ApplyRows(DataTable, Rows, ApplyErrors);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (!bApplySuccess)
	{
		return Context.BuildResult(false);
	}

	DataTable->PostEditChange();
	FAssetRegistryModule::AssetCreated(DataTable);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(DataTable);

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("rowStructType"), RowStruct->GetPathName());
	Result->SetNumberField(TEXT("rowCount"), DataTable->GetRowMap().Num());
	return Result;
}

TSharedPtr<FJsonObject> FDataTableAuthoring::Modify(UDataTable* DataTable,
                                                    const TSharedPtr<FJsonObject>& PayloadJson,
                                                    const bool bValidateOnly)
{
	using namespace DataTableAuthoringInternal;

	const FString AssetPath = DataTable ? DataTable->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_data_table"), AssetPath, TEXT("DataTable"), bValidateOnly);

	if (!DataTable)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("DataTable is null."));
		return Context.BuildResult(false);
	}

	UScriptStruct* RowStruct = const_cast<UScriptStruct*>(DataTable->GetRowStruct());
	if (!RowStruct)
	{
		Context.AddError(TEXT("missing_row_struct"), TEXT("DataTable has no row struct."), AssetPath);
		return Context.BuildResult(false);
	}

	bool bReplaceRows = false;
	if (PayloadJson.IsValid())
	{
		PayloadJson->TryGetBoolField(TEXT("replaceRows"), bReplaceRows);
	}
	const TArray<TSharedPtr<FJsonValue>> Rows = GetRowsArray(PayloadJson);
	const TArray<TSharedPtr<FJsonValue>> DeleteRows = GetDeleteRowsArray(PayloadJson);

	TArray<FString> ValidationErrors;
	bool bValid = ValidateDeleteRows(DeleteRows, ValidationErrors);
	bValid &= ValidateRows(RowStruct, Rows, DataTable, bReplaceRows, ValidationErrors);
	Context.SetValidationSummary(
		bValid,
		bValid ? TEXT("DataTable payload validated.") : TEXT("DataTable payload failed validation."),
		ValidationErrors);
	AppendValidationDiagnostics(Context, ValidationErrors, AssetPath);
	if (!bValid)
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify DataTable")));
	DataTable->Modify();

	if (bReplaceRows)
	{
		DataTable->EmptyTable();
	}

	if (DeleteRows.Num() > 0)
	{
		for (const TSharedPtr<FJsonValue>& DeleteValue : DeleteRows)
		{
			FString RowName;
			if (DeleteValue.IsValid() && DeleteValue->TryGetString(RowName) && !RowName.IsEmpty())
			{
				DataTable->RemoveRow(FName(*RowName));
			}
		}
	}

	TArray<FString> ApplyErrors;
	const bool bApplySuccess = ApplyRows(DataTable, Rows, ApplyErrors);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (!bApplySuccess)
	{
		return Context.BuildResult(false);
	}

	DataTable->HandleDataTableChanged();
	DataTable->MarkPackageDirty();
	DataTable->PostEditChange();
	Context.TrackDirtyObject(DataTable);

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("rowStructType"), RowStruct->GetPathName());
	Result->SetNumberField(TEXT("rowCount"), DataTable->GetRowMap().Num());
	return Result;
}
