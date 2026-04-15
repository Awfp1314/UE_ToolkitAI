#include "Authoring/BlackboardAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "BehaviorTree/BlackboardData.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Class.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Enum.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_NativeEnum.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Object.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace BlackboardAuthoringInternal
{

struct FKeySelector
{
	FString EntryName;
};

static TSharedPtr<FJsonObject> NormalizePayload(const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* NestedPayload = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("blackboard"), NestedPayload)
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

static bool BuildKeySelector(const TSharedPtr<FJsonObject>& Payload,
                             FKeySelector& OutSelector,
                             FString& OutError)
{
	if (!Payload.IsValid())
	{
		OutError = TEXT("Key selector payload must be an object.");
		return false;
	}

	if ((Payload->TryGetStringField(TEXT("entryName"), OutSelector.EntryName)
		 || Payload->TryGetStringField(TEXT("name"), OutSelector.EntryName))
		&& !OutSelector.EntryName.IsEmpty())
	{
		return true;
	}

	OutError = TEXT("Key selector requires entryName.");
	return false;
}

static bool ShouldIncludeLocalKey(const TSharedPtr<FJsonObject>& KeyObject,
                                  const FString& AssetPath)
{
	if (!KeyObject.IsValid())
	{
		return false;
	}

	bool bIsInherited = false;
	KeyObject->TryGetBoolField(TEXT("isInherited"), bIsInherited);
	if (!bIsInherited)
	{
		return true;
	}

	FString SourceBlackboard;
	if (!KeyObject->TryGetStringField(TEXT("sourceBlackboard"), SourceBlackboard)
		|| SourceBlackboard.IsEmpty())
	{
		return false;
	}

	return SourceBlackboard == AssetPath;
}

static TArray<TSharedPtr<FJsonValue>> GetLocalKeysArray(const TSharedPtr<FJsonObject>& Payload,
                                                        const FString& AssetPath)
{
	const TArray<TSharedPtr<FJsonValue>>* Keys = nullptr;
	if (!Payload.IsValid()
		|| !Payload->TryGetArrayField(TEXT("keys"), Keys)
		|| !Keys)
	{
		return {};
	}

	TArray<TSharedPtr<FJsonValue>> LocalKeys;
	for (const TSharedPtr<FJsonValue>& KeyValue : *Keys)
	{
		const TSharedPtr<FJsonObject> KeyObject = KeyValue.IsValid() ? KeyValue->AsObject() : nullptr;
		if (ShouldIncludeLocalKey(KeyObject, AssetPath))
		{
			LocalKeys.Add(KeyValue);
		}
	}

	return LocalKeys;
}

static UBlackboardData* ResolveParentBlackboard(const FString& ParentPath,
                                                TArray<FString>& OutErrors)
{
	if (ParentPath.IsEmpty())
	{
		return nullptr;
	}

	UBlackboardData* ParentBlackboard = LoadObject<UBlackboardData>(nullptr, *ParentPath);
	if (!ParentBlackboard)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to load parent blackboard '%s'."),
			*ParentPath));
	}
	return ParentBlackboard;
}

static UBlackboardKeyType* CreateKeyType(UObject* Outer,
                                         const FString& KeyTypePath,
                                         TArray<FString>& OutErrors)
{
	UClass* KeyTypeClass = FAuthoringHelpers::ResolveClass(
		KeyTypePath,
		UBlackboardKeyType::StaticClass());
	if (!KeyTypeClass)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to resolve blackboard key type '%s'."),
			*KeyTypePath));
		return nullptr;
	}

	return NewObject<UBlackboardKeyType>(
		Outer,
		KeyTypeClass,
		MakeUniqueObjectName(Outer, KeyTypeClass));
}

static bool ApplyKeyTypeProperties(UBlackboardKeyType* KeyType,
                                   const TSharedPtr<FJsonObject>& KeyObject,
                                   TArray<FString>& OutErrors,
                                   const bool bValidationOnly)
{
	if (!KeyType || !KeyObject.IsValid())
	{
		OutErrors.Add(TEXT("Invalid blackboard key type payload."));
		return false;
	}

	bool bSuccess = true;

	FString BaseClassPath;
	if (KeyObject->TryGetStringField(TEXT("baseClass"), BaseClassPath)
		&& !BaseClassPath.IsEmpty())
	{
		UClass* BaseClass = FAuthoringHelpers::ResolveClass(BaseClassPath);
		if (!BaseClass)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to resolve blackboard base class '%s'."),
				*BaseClassPath));
			bSuccess = false;
		}
		else if (UBlackboardKeyType_Object* ObjectKeyType = Cast<UBlackboardKeyType_Object>(KeyType))
		{
			ObjectKeyType->BaseClass = BaseClass;
		}
		else if (UBlackboardKeyType_Class* ClassKeyType = Cast<UBlackboardKeyType_Class>(KeyType))
		{
			ClassKeyType->BaseClass = BaseClass;
		}
		else
		{
			OutErrors.Add(FString::Printf(
				TEXT("Key type '%s' does not support baseClass."),
				*KeyType->GetClass()->GetName()));
			bSuccess = false;
		}
	}

	FString EnumTypePath;
	if (KeyObject->TryGetStringField(TEXT("enumType"), EnumTypePath)
		&& !EnumTypePath.IsEmpty())
	{
		UEnum* EnumType = FAuthoringHelpers::ResolveEnum(EnumTypePath);
		if (!EnumType)
		{
			OutErrors.Add(FString::Printf(
				TEXT("Failed to resolve enum type '%s'."),
				*EnumTypePath));
			bSuccess = false;
		}
		else if (UBlackboardKeyType_Enum* EnumKeyType = Cast<UBlackboardKeyType_Enum>(KeyType))
		{
			EnumKeyType->EnumType = EnumType;
		}
		else if (UBlackboardKeyType_NativeEnum* NativeEnumKeyType = Cast<UBlackboardKeyType_NativeEnum>(KeyType))
		{
			NativeEnumKeyType->EnumType = EnumType;
		}
		else
		{
			OutErrors.Add(FString::Printf(
				TEXT("Key type '%s' does not support enumType."),
				*KeyType->GetClass()->GetName()));
			bSuccess = false;
		}
	}

	FString EnumName;
	if (KeyObject->TryGetStringField(TEXT("enumName"), EnumName))
	{
		if (UBlackboardKeyType_Enum* EnumKeyType = Cast<UBlackboardKeyType_Enum>(KeyType))
		{
			EnumKeyType->EnumName = EnumName;
		}
		else if (UBlackboardKeyType_NativeEnum* NativeEnumKeyType = Cast<UBlackboardKeyType_NativeEnum>(KeyType))
		{
			NativeEnumKeyType->EnumName = EnumName;
		}
		else if (!EnumName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(
				TEXT("Key type '%s' does not support enumName."),
				*KeyType->GetClass()->GetName()));
			bSuccess = false;
		}
	}

	const TSharedPtr<FJsonObject>* PropertiesObject = nullptr;
	if (KeyObject->TryGetObjectField(TEXT("properties"), PropertiesObject)
		&& PropertiesObject
		&& PropertiesObject->IsValid())
	{
		bSuccess &= FPropertySerializer::ApplyPropertiesFromJson(
			KeyType,
			*PropertiesObject,
			OutErrors,
			bValidationOnly,
			true);
	}

#if WITH_EDITOR
	if (!bValidationOnly)
	{
		KeyType->PostEditChange();
	}
#endif

	return bSuccess;
}

static bool BuildKeyEntry(UObject* Outer,
                          const TSharedPtr<FJsonObject>& KeyObject,
                          FBlackboardEntry& OutEntry,
                          TArray<FString>& OutErrors,
                          const bool bValidationOnly)
{
	if (!KeyObject.IsValid())
	{
		OutErrors.Add(TEXT("Blackboard key entry must be an object."));
		return false;
	}

	FString EntryName;
	if (!(KeyObject->TryGetStringField(TEXT("entryName"), EntryName)
		  || KeyObject->TryGetStringField(TEXT("name"), EntryName))
		|| EntryName.IsEmpty())
	{
		OutErrors.Add(TEXT("Blackboard key entryName is required."));
		return false;
	}

	FString KeyTypePath;
	if (!KeyObject->TryGetStringField(TEXT("keyTypePath"), KeyTypePath)
		|| KeyTypePath.IsEmpty())
	{
		OutErrors.Add(FString::Printf(
			TEXT("Blackboard key '%s' requires keyTypePath."),
			*EntryName));
		return false;
	}

	OutEntry.EntryName = FName(*EntryName);
	OutEntry.KeyType = CreateKeyType(Outer, KeyTypePath, OutErrors);
	if (!OutEntry.KeyType)
	{
		return false;
	}

	bool bInstanceSynced = false;
	if (KeyObject->TryGetBoolField(TEXT("isInstanceSynced"), bInstanceSynced))
	{
		OutEntry.bInstanceSynced = bInstanceSynced ? 1U : 0U;
	}

#if WITH_EDITORONLY_DATA
	KeyObject->TryGetStringField(TEXT("description"), OutEntry.EntryDescription);
	FString Category;
	if (KeyObject->TryGetStringField(TEXT("category"), Category) && !Category.IsEmpty())
	{
		OutEntry.EntryCategory = FName(*Category);
	}
	else
	{
		OutEntry.EntryCategory = NAME_None;
	}
#endif

	return ApplyKeyTypeProperties(
		OutEntry.KeyType,
		KeyObject,
		OutErrors,
		bValidationOnly);
}

static FBlackboardEntry* FindLocalKey(UBlackboardData* BlackboardData,
                                      const FKeySelector& Selector)
{
	if (!BlackboardData)
	{
		return nullptr;
	}

	for (FBlackboardEntry& Entry : BlackboardData->Keys)
	{
		if (Entry.EntryName.ToString() == Selector.EntryName)
		{
			return &Entry;
		}
	}

	return nullptr;
}

static bool FinalizeBlackboard(UBlackboardData* BlackboardData,
                               TArray<FString>& OutErrors,
                               const bool bValidationOnly)
{
	if (!BlackboardData)
	{
		OutErrors.Add(TEXT("BlackboardData is null."));
		return false;
	}

	BlackboardData->UpdateParentKeys();
	BlackboardData->UpdateKeyIDs();
	BlackboardData->UpdateIfHasSynchronizedKeys();

#if WITH_EDITOR
	if (!bValidationOnly)
	{
		BlackboardData->PostEditChange();
	}
#endif

	if (!BlackboardData->IsValid())
	{
		OutErrors.Add(TEXT("Blackboard asset is invalid after applying changes."));
	}

	if (!bValidationOnly)
	{
		BlackboardData->PropagateKeyChangesToDerivedBlackboardAssets();
	}

	return OutErrors.Num() == 0;
}

static bool ReplaceKeys(UBlackboardData* BlackboardData,
                        const TSharedPtr<FJsonObject>& Payload,
                        TArray<FString>& OutErrors,
                        const bool bValidationOnly)
{
	if (!BlackboardData)
	{
		OutErrors.Add(TEXT("BlackboardData is null."));
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>> Keys = GetLocalKeysArray(
		Payload,
		BlackboardData->GetPathName());
	TArray<FBlackboardEntry> NewKeys;
	TSet<FString> SeenNames;

	for (int32 Index = 0; Index < Keys.Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> KeyObject = Keys[Index].IsValid() ? Keys[Index]->AsObject() : nullptr;
		FBlackboardEntry& NewEntry = NewKeys.AddDefaulted_GetRef();
		if (!BuildKeyEntry(BlackboardData, KeyObject, NewEntry, OutErrors, bValidationOnly))
		{
			NewKeys.Pop();
			continue;
		}

		const FString EntryName = NewEntry.EntryName.ToString();
		if (SeenNames.Contains(EntryName))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Duplicate blackboard key '%s'."),
				*EntryName));
			NewKeys.Pop();
			continue;
		}

		SeenNames.Add(EntryName);
	}

	if (OutErrors.Num() > 0)
	{
		return false;
	}

	BlackboardData->Keys = MoveTemp(NewKeys);
	return FinalizeBlackboard(BlackboardData, OutErrors, bValidationOnly);
}

static bool PatchKey(UBlackboardData* BlackboardData,
                     const TSharedPtr<FJsonObject>& Payload,
                     TArray<FString>& OutErrors,
                     const bool bValidationOnly)
{
	const TSharedPtr<FJsonObject>* KeyObject = nullptr;
	TSharedPtr<FJsonObject> EffectivePayload = Payload;
	if (Payload.IsValid()
		&& Payload->TryGetObjectField(TEXT("key"), KeyObject)
		&& KeyObject
		&& KeyObject->IsValid())
	{
		EffectivePayload = *KeyObject;
	}

	FKeySelector Selector;
	FString SelectorError;
	if (!BuildKeySelector(EffectivePayload, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	FBlackboardEntry* ExistingEntry = FindLocalKey(BlackboardData, Selector);
	if (!ExistingEntry)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Local blackboard key '%s' was not found."),
			*Selector.EntryName));
		return false;
	}

	FString NewEntryName;
	if ((EffectivePayload->TryGetStringField(TEXT("newEntryName"), NewEntryName)
		 || EffectivePayload->TryGetStringField(TEXT("entryName"), NewEntryName))
		&& !NewEntryName.IsEmpty())
	{
		ExistingEntry->EntryName = FName(*NewEntryName);
	}

	bool bInstanceSynced = false;
	if (EffectivePayload->TryGetBoolField(TEXT("isInstanceSynced"), bInstanceSynced))
	{
		ExistingEntry->bInstanceSynced = bInstanceSynced ? 1U : 0U;
	}

#if WITH_EDITORONLY_DATA
	EffectivePayload->TryGetStringField(TEXT("description"), ExistingEntry->EntryDescription);
	FString Category;
	if (EffectivePayload->TryGetStringField(TEXT("category"), Category))
	{
		ExistingEntry->EntryCategory = Category.IsEmpty() ? NAME_None : FName(*Category);
	}
#endif

	FString RequestedKeyTypePath;
	if (EffectivePayload->TryGetStringField(TEXT("keyTypePath"), RequestedKeyTypePath)
		&& !RequestedKeyTypePath.IsEmpty()
		&& (!ExistingEntry->KeyType
			|| ExistingEntry->KeyType->GetClass()->GetPathName() != RequestedKeyTypePath))
	{
		ExistingEntry->KeyType = CreateKeyType(BlackboardData, RequestedKeyTypePath, OutErrors);
	}

	if (!ExistingEntry->KeyType)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Blackboard key '%s' has no key type."),
			*ExistingEntry->EntryName.ToString()));
		return false;
	}

	if (!ApplyKeyTypeProperties(
		    ExistingEntry->KeyType,
		    EffectivePayload,
		    OutErrors,
		    bValidationOnly))
	{
		return false;
	}

	return FinalizeBlackboard(BlackboardData, OutErrors, bValidationOnly);
}

static bool RemoveKey(UBlackboardData* BlackboardData,
                      const TSharedPtr<FJsonObject>& Payload,
                      TArray<FString>& OutErrors,
                      const bool bValidationOnly)
{
	FKeySelector Selector;
	FString SelectorError;
	if (!BuildKeySelector(Payload, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	const int32 RemoveIndex = BlackboardData
		? BlackboardData->Keys.IndexOfByPredicate([&Selector](const FBlackboardEntry& Entry)
		  {
			  return Entry.EntryName.ToString() == Selector.EntryName;
		  })
		: INDEX_NONE;
	if (RemoveIndex == INDEX_NONE)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Local blackboard key '%s' was not found."),
			*Selector.EntryName));
		return false;
	}

	BlackboardData->Keys.RemoveAt(RemoveIndex);
	return FinalizeBlackboard(BlackboardData, OutErrors, bValidationOnly);
}

static bool SetParent(UBlackboardData* BlackboardData,
                      const TSharedPtr<FJsonObject>& Payload,
                      TArray<FString>& OutErrors,
                      const bool bValidationOnly)
{
	if (!BlackboardData)
	{
		OutErrors.Add(TEXT("BlackboardData is null."));
		return false;
	}

	FString ParentPath;
	if (!Payload.IsValid())
	{
		OutErrors.Add(TEXT("set_parent payload must be an object."));
		return false;
	}

	Payload->TryGetStringField(TEXT("parentBlackboard"), ParentPath);
	if (ParentPath.IsEmpty())
	{
		Payload->TryGetStringField(TEXT("parentAsset"), ParentPath);
	}

	UBlackboardData* ParentBlackboard = ResolveParentBlackboard(ParentPath, OutErrors);
	if (ParentBlackboard && ParentBlackboard == BlackboardData)
	{
		OutErrors.Add(TEXT("Blackboard parent cannot reference itself."));
		return false;
	}

	BlackboardData->Parent = ParentBlackboard;
	return FinalizeBlackboard(BlackboardData, OutErrors, bValidationOnly);
}

static bool ApplyOperation(UBlackboardData* BlackboardData,
                           const FString& Operation,
                           const TSharedPtr<FJsonObject>& Payload,
                           TArray<FString>& OutErrors,
                           const bool bValidationOnly)
{
	if (Operation == TEXT("replace_keys"))
	{
		return ReplaceKeys(BlackboardData, Payload, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("patch_key"))
	{
		return PatchKey(BlackboardData, Payload, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("remove_key"))
	{
		return RemoveKey(BlackboardData, Payload, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("set_parent"))
	{
		return SetParent(BlackboardData, Payload, OutErrors, bValidationOnly);
	}

	OutErrors.Add(FString::Printf(
		TEXT("Unsupported Blackboard operation '%s'."),
		*Operation));
	return false;
}

} // namespace BlackboardAuthoringInternal

TSharedPtr<FJsonObject> FBlackboardAuthoring::Create(const FString& AssetPath,
                                                     const TSharedPtr<FJsonObject>& PayloadJson,
                                                     const bool bValidateOnly)
{
	using namespace BlackboardAuthoringInternal;

	FAssetMutationContext Context(
		TEXT("create_blackboard"),
		AssetPath,
		TEXT("BlackboardData"),
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

	UBlackboardData* PreviewBlackboard = NewObject<UBlackboardData>(
		GetTransientPackage(),
		MakeUniqueObjectName(GetTransientPackage(), UBlackboardData::StaticClass(), TEXT("BBPreview")),
		RF_Transient);
	if (!PreviewBlackboard)
	{
		Context.AddError(
			TEXT("preview_create_failed"),
			TEXT("Failed to create transient Blackboard preview."));
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	if (Payload->HasField(TEXT("parentBlackboard")))
	{
		SetParent(PreviewBlackboard, Payload, ValidationErrors, true);
	}
	if (Payload->HasField(TEXT("keys")))
	{
		ReplaceKeys(PreviewBlackboard, Payload, ValidationErrors, true);
	}

	if (!AppendValidationSummary(
		    Context,
		    ValidationErrors,
		    TEXT("Blackboard payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create Blackboard")));

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
	UBlackboardData* BlackboardData = NewObject<UBlackboardData>(
		Package,
		AssetName,
		RF_Public | RF_Standalone | RF_Transactional);
	if (!BlackboardData)
	{
		Context.AddError(
			TEXT("asset_create_failed"),
			FString::Printf(TEXT("Failed to create Blackboard asset: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	BlackboardData->Modify();

	TArray<FString> ApplyErrors;
	if (Payload->HasField(TEXT("parentBlackboard")))
	{
		SetParent(BlackboardData, Payload, ApplyErrors, false);
	}
	if (Payload->HasField(TEXT("keys")))
	{
		ReplaceKeys(BlackboardData, Payload, ApplyErrors, false);
	}

	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(BlackboardData);
	BlackboardData->MarkPackageDirty();
	Context.TrackDirtyObject(BlackboardData);
	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FBlackboardAuthoring::Modify(UBlackboardData* BlackboardData,
                                                     const FString& Operation,
                                                     const TSharedPtr<FJsonObject>& PayloadJson,
                                                     const bool bValidateOnly)
{
	using namespace BlackboardAuthoringInternal;

	const FString AssetPath = BlackboardData ? BlackboardData->GetPathName() : FString();
	FAssetMutationContext Context(
		TEXT("modify_blackboard"),
		AssetPath,
		TEXT("BlackboardData"),
		bValidateOnly);

	if (!BlackboardData)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("BlackboardData is null."));
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);
	UBlackboardData* WorkingBlackboard = BlackboardData;
	if (bValidateOnly)
	{
		WorkingBlackboard = DuplicateObject<UBlackboardData>(
			BlackboardData,
			GetTransientPackage());
		if (!WorkingBlackboard)
		{
			Context.AddError(
				TEXT("preview_duplicate_failed"),
				TEXT("Failed to duplicate BlackboardData for validation."));
			return Context.BuildResult(false);
		}
	}

	TArray<FString> ValidationErrors;
	ApplyOperation(
		WorkingBlackboard,
		Operation,
		Payload,
		ValidationErrors,
		true);
	if (!AppendValidationSummary(
		    Context,
		    ValidationErrors,
		    TEXT("Blackboard payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify Blackboard")));
	BlackboardData->Modify();

	TArray<FString> ApplyErrors;
	ApplyOperation(
		BlackboardData,
		Operation,
		Payload,
		ApplyErrors,
		false);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	BlackboardData->MarkPackageDirty();
	Context.TrackDirtyObject(BlackboardData);
	return Context.BuildResult(true);
}
