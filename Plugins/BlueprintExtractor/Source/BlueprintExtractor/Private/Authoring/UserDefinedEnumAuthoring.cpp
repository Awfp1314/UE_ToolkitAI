#include "Authoring/UserDefinedEnumAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/UserDefinedEnum.h"
#include "Kismet2/EnumEditorUtils.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace UserDefinedEnumAuthoringInternal
{

struct FEnumEntryDefinition
{
	FString Name;
	FString DisplayName;
};

static TSharedPtr<FJsonObject> NormalizePayload(
	const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* NestedPayload = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("userDefinedEnum"), NestedPayload)
		&& NestedPayload
		&& NestedPayload->IsValid())
	{
		return *NestedPayload;
	}

	return PayloadJson;
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

static bool IsValidEntryName(const FString& Name)
{
	if (Name.IsEmpty())
	{
		return false;
	}

	const FName ShortName(*Name);
	return ShortName.IsValidXName(INVALID_OBJECTNAME_CHARACTERS)
		&& !UEnum::IsFullEnumName(*Name);
}

static void ReadCurrentEntries(const UUserDefinedEnum* UserDefinedEnum,
                               TArray<FEnumEntryDefinition>& OutEntries)
{
	if (!UserDefinedEnum)
	{
		return;
	}

	const int32 EntryCount = FMath::Max(0, UserDefinedEnum->NumEnums() - 1);
	for (int32 Index = 0; Index < EntryCount; ++Index)
	{
		FEnumEntryDefinition& Entry = OutEntries.AddDefaulted_GetRef();
		Entry.Name = UserDefinedEnum->GetNameStringByIndex(Index);
		Entry.DisplayName =
			UserDefinedEnum->GetDisplayNameTextByIndex(Index).ToString();
	}
}

static bool ExtractEntries(const TSharedPtr<FJsonObject>& Payload,
                           TArray<FEnumEntryDefinition>& OutEntries,
                           TArray<FString>& OutErrors)
{
	const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
	if (!Payload.IsValid()
		|| !Payload->TryGetArrayField(TEXT("entries"), Entries)
		|| !Entries)
	{
		OutErrors.Add(TEXT("entries is required."));
		return false;
	}

	bool bSuccess = true;
	TSet<FString> SeenNames;

	for (int32 Index = 0; Index < Entries->Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> EntryObject =
			(*Entries)[Index].IsValid() ? (*Entries)[Index]->AsObject() : nullptr;
		if (!EntryObject.IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("entries[%d] must be an object."),
				Index));
			bSuccess = false;
			continue;
		}

		FEnumEntryDefinition& Entry = OutEntries.AddDefaulted_GetRef();
		if (!EntryObject->TryGetStringField(TEXT("name"), Entry.Name)
			|| Entry.Name.IsEmpty())
		{
			OutErrors.Add(FString::Printf(
				TEXT("entries[%d].name is required."),
				Index));
			bSuccess = false;
			continue;
		}

		if (SeenNames.Contains(Entry.Name))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Duplicate enum entry name '%s'."),
				*Entry.Name));
			bSuccess = false;
			continue;
		}

		SeenNames.Add(Entry.Name);
		EntryObject->TryGetStringField(TEXT("displayName"), Entry.DisplayName);
	}

	return bSuccess;
}

static bool RebuildEntries(UUserDefinedEnum* UserDefinedEnum,
                           const TArray<FEnumEntryDefinition>& Entries,
                           TArray<FString>& OutErrors)
{
	if (!UserDefinedEnum)
	{
		OutErrors.Add(TEXT("UserDefinedEnum is null."));
		return false;
	}

	TArray<TPair<FName, int64>> EnumNames;
	EnumNames.Reserve(Entries.Num());

	for (int32 Index = 0; Index < Entries.Num(); ++Index)
	{
		const FEnumEntryDefinition& Entry = Entries[Index];
		if (!IsValidEntryName(Entry.Name))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Enum entry name '%s' is not valid."),
				*Entry.Name));
			continue;
		}

		EnumNames.Emplace(
			*UserDefinedEnum->GenerateFullEnumName(*Entry.Name),
			Index);
	}

	if (OutErrors.Num() > 0)
	{
		return false;
	}

	UserDefinedEnum->Modify();
	UserDefinedEnum->SetEnums(EnumNames, UserDefinedEnum->GetCppForm());
	FEnumEditorUtils::EnsureAllDisplayNamesExist(UserDefinedEnum);

	for (int32 Index = 0; Index < Entries.Num(); ++Index)
	{
		if (!Entries[Index].DisplayName.IsEmpty()
			&& !FEnumEditorUtils::SetEnumeratorDisplayName(
				UserDefinedEnum,
				Index,
				FText::FromString(Entries[Index].DisplayName)))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to set display name for '%s'."),
				*Entries[Index].Name));
		}
	}

	return OutErrors.Num() == 0;
}

static bool FindEntryIndex(const UUserDefinedEnum* UserDefinedEnum,
                           const TSharedPtr<FJsonObject>& Payload,
                           int32& OutIndex,
                           TArray<FString>& OutErrors)
{
	if (!UserDefinedEnum || !Payload.IsValid())
	{
		OutErrors.Add(TEXT("Enum selector payload must be an object."));
		return false;
	}

	FString Name;
	if (!(Payload->TryGetStringField(TEXT("name"), Name)
		  || Payload->TryGetStringField(TEXT("entryName"), Name))
		|| Name.IsEmpty())
	{
		OutErrors.Add(TEXT("Enum selector requires name."));
		return false;
	}

	const int32 EntryCount = FMath::Max(0, UserDefinedEnum->NumEnums() - 1);
	for (int32 Index = 0; Index < EntryCount; ++Index)
	{
		if (UserDefinedEnum->GetNameStringByIndex(Index) == Name)
		{
			OutIndex = Index;
			return true;
		}
	}

	OutErrors.Add(FString::Printf(TEXT("Enum entry '%s' was not found."), *Name));
	return false;
}

static bool ApplyOperation(UUserDefinedEnum* UserDefinedEnum,
                           const FString& Operation,
                           const TSharedPtr<FJsonObject>& Payload,
                           TArray<FString>& OutErrors)
{
	TArray<FEnumEntryDefinition> Entries;
	ReadCurrentEntries(UserDefinedEnum, Entries);

	if (Operation == TEXT("replace_entries"))
	{
		Entries.Reset();
		if (!ExtractEntries(Payload, Entries, OutErrors))
		{
			return false;
		}
		return RebuildEntries(UserDefinedEnum, Entries, OutErrors);
	}

	if (Operation == TEXT("rename_entry"))
	{
		int32 EntryIndex = INDEX_NONE;
		if (!FindEntryIndex(UserDefinedEnum, Payload, EntryIndex, OutErrors))
		{
			return false;
		}

		FString NewName;
		if (!Payload->TryGetStringField(TEXT("newName"), NewName)
			|| NewName.IsEmpty())
		{
			OutErrors.Add(TEXT("rename_entry requires newName."));
			return false;
		}

		Entries[EntryIndex].Name = NewName;
		FString DisplayName;
		if (Payload->TryGetStringField(TEXT("displayName"), DisplayName))
		{
			Entries[EntryIndex].DisplayName = DisplayName;
		}
		return RebuildEntries(UserDefinedEnum, Entries, OutErrors);
	}

	if (Operation == TEXT("remove_entry"))
	{
		int32 EntryIndex = INDEX_NONE;
		if (!FindEntryIndex(UserDefinedEnum, Payload, EntryIndex, OutErrors))
		{
			return false;
		}

		Entries.RemoveAt(EntryIndex);
		return RebuildEntries(UserDefinedEnum, Entries, OutErrors);
	}

	if (Operation == TEXT("reorder_entries"))
	{
		TArray<FEnumEntryDefinition> OrderedEntries;
		if (!ExtractEntries(Payload, OrderedEntries, OutErrors))
		{
			return false;
		}
		return RebuildEntries(UserDefinedEnum, OrderedEntries, OutErrors);
	}

	OutErrors.Add(FString::Printf(
		TEXT("Unsupported UserDefinedEnum operation '%s'."),
		*Operation));
	return false;
}

} // namespace UserDefinedEnumAuthoringInternal

TSharedPtr<FJsonObject> FUserDefinedEnumAuthoring::Create(
	const FString& AssetPath,
	const TSharedPtr<FJsonObject>& PayloadJson,
	const bool bValidateOnly)
{
	using namespace UserDefinedEnumAuthoringInternal;

	FAssetMutationContext Context(
		TEXT("create_user_defined_enum"),
		AssetPath,
		TEXT("UserDefinedEnum"),
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
		UUserDefinedEnum::StaticClass(),
		TEXT("UDEPreview"));
	UUserDefinedEnum* PreviewEnum = Cast<UUserDefinedEnum>(
		FEnumEditorUtils::CreateUserDefinedEnum(
			GetTransientPackage(),
			PreviewName,
			RF_Public | RF_Transient));
	if (!PreviewEnum)
	{
		Context.AddError(
			TEXT("preview_create_failed"),
			TEXT("Failed to create transient UserDefinedEnum preview."));
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	if (Payload->HasField(TEXT("entries")))
	{
		ApplyOperation(PreviewEnum, TEXT("replace_entries"), Payload, ValidationErrors);
	}

	if (!AppendValidationSummary(
		    Context,
		    ValidationErrors,
		    TEXT("UserDefinedEnum payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create UserDefinedEnum")));

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
	UUserDefinedEnum* UserDefinedEnum = Cast<UUserDefinedEnum>(
		FEnumEditorUtils::CreateUserDefinedEnum(
			Package,
			AssetName,
			RF_Public | RF_Standalone));
	if (!UserDefinedEnum)
	{
		Context.AddError(
			TEXT("asset_create_failed"),
			FString::Printf(TEXT("Failed to create UserDefinedEnum asset: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	TArray<FString> ApplyErrors;
	if (Payload->HasField(TEXT("entries")))
	{
		ApplyOperation(UserDefinedEnum, TEXT("replace_entries"), Payload, ApplyErrors);
	}

	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(UserDefinedEnum);
	UserDefinedEnum->MarkPackageDirty();
	Context.TrackDirtyObject(UserDefinedEnum);
	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FUserDefinedEnumAuthoring::Modify(
	UUserDefinedEnum* UserDefinedEnum,
	const FString& Operation,
	const TSharedPtr<FJsonObject>& PayloadJson,
	const bool bValidateOnly)
{
	using namespace UserDefinedEnumAuthoringInternal;

	const FString AssetPath = UserDefinedEnum
		? UserDefinedEnum->GetPathName()
		: FString();
	FAssetMutationContext Context(
		TEXT("modify_user_defined_enum"),
		AssetPath,
		TEXT("UserDefinedEnum"),
		bValidateOnly);

	if (!UserDefinedEnum)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("UserDefinedEnum is null."));
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);
	UUserDefinedEnum* WorkingEnum = UserDefinedEnum;
	if (bValidateOnly)
	{
		WorkingEnum = DuplicateObject<UUserDefinedEnum>(
			UserDefinedEnum,
			GetTransientPackage());
		if (!WorkingEnum)
		{
			Context.AddError(
				TEXT("preview_duplicate_failed"),
				TEXT("Failed to duplicate UserDefinedEnum for validation."));
			return Context.BuildResult(false);
		}
	}

	TArray<FString> ValidationErrors;
	ApplyOperation(WorkingEnum, Operation, Payload, ValidationErrors);
	if (!AppendValidationSummary(
		    Context,
		    ValidationErrors,
		    TEXT("UserDefinedEnum payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify UserDefinedEnum")));
	UserDefinedEnum->Modify();

	TArray<FString> ApplyErrors;
	ApplyOperation(UserDefinedEnum, Operation, Payload, ApplyErrors);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	UserDefinedEnum->MarkPackageDirty();
	Context.TrackDirtyObject(UserDefinedEnum);
	return Context.BuildResult(true);
}
