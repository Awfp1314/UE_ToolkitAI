#include "Authoring/AuthoringHelpers.h"

#include "Authoring/AssetMutationHelpers.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "BlueprintCompilationManager.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Logging/TokenizedMessage.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/UObjectIterator.h"
#include "UObject/UnrealType.h"

namespace AuthoringHelpersInternal
{

struct FTemporaryPropertyStorage
{
	explicit FTemporaryPropertyStorage(const FProperty* InProperty)
		: Property(InProperty)
	{
		if (Property)
		{
			Data = FMemory::Malloc(Property->GetSize(), Property->GetMinAlignment());
			Property->InitializeValue(Data);
		}
	}

	~FTemporaryPropertyStorage()
	{
		if (Property && Data)
		{
			Property->DestroyValue(Data);
			FMemory::Free(Data);
		}
	}

	const FProperty* Property = nullptr;
	void* Data = nullptr;
};

static FString GetBlueprintStatusString(const EBlueprintStatus Status)
{
	switch (Status)
	{
	case BS_Unknown:
		return TEXT("Unknown");
	case BS_Dirty:
		return TEXT("Dirty");
	case BS_Error:
		return TEXT("Error");
	case BS_UpToDate:
		return TEXT("UpToDate");
	case BS_BeingCreated:
		return TEXT("BeingCreated");
	case BS_UpToDateWithWarnings:
		return TEXT("UpToDateWithWarnings");
	default:
		return TEXT("Unknown");
	}
}

static TSharedPtr<FJsonValueObject> MakeMessageValue(const FString& Severity, const FString& Message)
{
	const TSharedPtr<FJsonObject> MessageObject = MakeShared<FJsonObject>();
	MessageObject->SetStringField(TEXT("severity"), Severity);
	MessageObject->SetStringField(TEXT("message"), Message);
	return MakeShared<FJsonValueObject>(MessageObject);
}

static TSharedPtr<FJsonObject> MakeCompileResult(const bool bSuccess,
                                                 const FString& StatusString,
                                                 const TArray<TSharedPtr<FJsonValue>>& Errors,
                                                 const TArray<TSharedPtr<FJsonValue>>& Warnings,
                                                 const TArray<TSharedPtr<FJsonValue>>& Messages,
                                                 const int32 ErrorCount,
                                                 const int32 WarningCount)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), bSuccess);
	Result->SetStringField(TEXT("status"), StatusString);
	Result->SetArrayField(TEXT("errors"), Errors);
	Result->SetArrayField(TEXT("warnings"), Warnings);
	Result->SetArrayField(TEXT("messages"), Messages);
	Result->SetNumberField(TEXT("errorCount"), ErrorCount);
	Result->SetNumberField(TEXT("warningCount"), WarningCount);
	return Result;
}

static bool ParseContainerType(const FString& ContainerTypeString, EPinContainerType& OutContainerType)
{
	if (ContainerTypeString.IsEmpty() || ContainerTypeString.Equals(TEXT("None"), ESearchCase::IgnoreCase))
	{
		OutContainerType = EPinContainerType::None;
		return true;
	}

	if (ContainerTypeString.Equals(TEXT("Array"), ESearchCase::IgnoreCase))
	{
		OutContainerType = EPinContainerType::Array;
		return true;
	}

	if (ContainerTypeString.Equals(TEXT("Set"), ESearchCase::IgnoreCase))
	{
		OutContainerType = EPinContainerType::Set;
		return true;
	}

	if (ContainerTypeString.Equals(TEXT("Map"), ESearchCase::IgnoreCase))
	{
		OutContainerType = EPinContainerType::Map;
		return true;
	}

	return false;
}

static bool ParseTerminalType(const TSharedPtr<FJsonObject>& ValueTypeObject,
                              FEdGraphTerminalType& OutTerminalType,
                              FString& OutError)
{
	if (!ValueTypeObject.IsValid())
	{
		OutError = TEXT("Pin valueType must be an object for map pins.");
		return false;
	}

	FString Category;
	if (!ValueTypeObject->TryGetStringField(TEXT("category"), Category) || Category.IsEmpty())
	{
		OutError = TEXT("Pin valueType.category is required for map pins.");
		return false;
	}

	OutTerminalType.TerminalCategory = FName(*Category);

	FString SubCategory;
	if (ValueTypeObject->TryGetStringField(TEXT("subCategory"), SubCategory))
	{
		OutTerminalType.TerminalSubCategory = FName(*SubCategory);
	}

	FString SubCategoryObjectPath;
	if (ValueTypeObject->TryGetStringField(TEXT("subCategoryObject"), SubCategoryObjectPath) && !SubCategoryObjectPath.IsEmpty())
	{
		if (UObject* TerminalObject = FAuthoringHelpers::ResolveObject(SubCategoryObjectPath))
		{
			OutTerminalType.TerminalSubCategoryObject = TerminalObject;
		}
		else
		{
			OutError = FString::Printf(TEXT("Failed to load map pin valueType.subCategoryObject '%s'."), *SubCategoryObjectPath);
			return false;
		}
	}

	return true;
}

} // namespace AuthoringHelpersInternal

UObject* FAuthoringHelpers::ResolveObject(const FString& ObjectPath, UClass* RequiredClass)
{
	if (ObjectPath.IsEmpty())
	{
		return nullptr;
	}

	const FString NormalizedObjectPath = NormalizeAssetObjectPath(ObjectPath);
	UClass* SearchClass = RequiredClass ? RequiredClass : UObject::StaticClass();
	if (UObject* FoundObject = FindObject<UObject>(nullptr, *NormalizedObjectPath))
	{
		return !RequiredClass || FoundObject->IsA(RequiredClass) ? FoundObject : nullptr;
	}

	if (NormalizedObjectPath != ObjectPath)
	{
		if (UObject* FoundObject = FindObject<UObject>(nullptr, *ObjectPath))
		{
			return !RequiredClass || FoundObject->IsA(RequiredClass) ? FoundObject : nullptr;
		}
	}

	if (UObject* ResolvedAsset = ResolveAssetByPath(NormalizedObjectPath))
	{
		return !RequiredClass || ResolvedAsset->IsA(RequiredClass) ? ResolvedAsset : nullptr;
	}

	if (NormalizedObjectPath.StartsWith(TEXT("/"))
		&& !NormalizedObjectPath.StartsWith(TEXT("/Script/"))
		&& !DoesAssetExist(NormalizedObjectPath))
	{
		return nullptr;
	}

	if (UObject* LoadedObject = StaticLoadObject(SearchClass, nullptr, *NormalizedObjectPath))
	{
		return LoadedObject;
	}

	if (NormalizedObjectPath != ObjectPath)
	{
		if (UObject* LoadedObject = StaticLoadObject(SearchClass, nullptr, *ObjectPath))
		{
			return LoadedObject;
		}
	}

	return nullptr;
}

UClass* FAuthoringHelpers::ResolveClass(const FString& ClassPath, UClass* RequiredBaseClass)
{
	if (ClassPath.IsEmpty())
	{
		return nullptr;
	}

	if (UClass* FoundClass = FindObject<UClass>(nullptr, *ClassPath))
	{
		return !RequiredBaseClass || FoundClass->IsChildOf(RequiredBaseClass) ? FoundClass : nullptr;
	}

	UClass* SearchBase = RequiredBaseClass ? RequiredBaseClass : UObject::StaticClass();
	const bool bLooksLikeQualifiedPath = ClassPath.StartsWith(TEXT("/"))
		|| ClassPath.Contains(TEXT("."))
		|| ClassPath.EndsWith(TEXT("_C"));
	if (bLooksLikeQualifiedPath)
	{
		const FString NormalizedClassPath = NormalizeAssetObjectPath(ClassPath);
		if (NormalizedClassPath.StartsWith(TEXT("/")) && !NormalizedClassPath.StartsWith(TEXT("/Script/")) && !DoesAssetExist(NormalizedClassPath))
		{
			return nullptr;
		}

		if (UClass* LoadedClass = StaticLoadClass(SearchBase, nullptr, *NormalizedClassPath))
		{
			return LoadedClass;
		}
	}

	if (UObject* LoadedObject = ResolveObject(ClassPath, UClass::StaticClass()))
	{
		UClass* ResolvedClass = Cast<UClass>(LoadedObject);
		if (ResolvedClass && (!RequiredBaseClass || ResolvedClass->IsChildOf(RequiredBaseClass)))
		{
			return ResolvedClass;
		}
	}

	return nullptr;
}

UScriptStruct* FAuthoringHelpers::ResolveScriptStruct(const FString& StructPath)
{
	if (StructPath.IsEmpty())
	{
		return nullptr;
	}

	if (UScriptStruct* LoadedStruct = LoadObject<UScriptStruct>(nullptr, *StructPath))
	{
		return LoadedStruct;
	}

	return FindObject<UScriptStruct>(nullptr, *StructPath);
}

UEnum* FAuthoringHelpers::ResolveEnum(const FString& EnumPath)
{
	if (EnumPath.IsEmpty())
	{
		return nullptr;
	}

	if (UEnum* LoadedEnum = LoadObject<UEnum>(nullptr, *EnumPath))
	{
		return LoadedEnum;
	}

	return FindObject<UEnum>(nullptr, *EnumPath);
}

bool FAuthoringHelpers::ParsePinType(const TSharedPtr<FJsonObject>& PinTypeObject,
                                     FEdGraphPinType& OutPinType,
                                     FString& OutError)
{
	using namespace AuthoringHelpersInternal;

	if (!PinTypeObject.IsValid())
	{
		OutError = TEXT("Pin type must be an object.");
		return false;
	}

	FString Category;
	if (!PinTypeObject->TryGetStringField(TEXT("category"), Category) || Category.IsEmpty())
	{
		OutError = TEXT("Pin type category is required.");
		return false;
	}

	OutPinType.ResetToDefaults();
	OutPinType.PinCategory = FName(*Category);

	FString ContainerTypeString;
	if (PinTypeObject->TryGetStringField(TEXT("containerType"), ContainerTypeString))
	{
		if (!ParseContainerType(ContainerTypeString, OutPinType.ContainerType))
		{
			OutError = FString::Printf(TEXT("Unsupported pin container type '%s'."), *ContainerTypeString);
			return false;
		}
	}

	FString SubCategory;
	if (PinTypeObject->TryGetStringField(TEXT("subCategory"), SubCategory))
	{
		OutPinType.PinSubCategory = FName(*SubCategory);
	}

	FString SubCategoryObjectPath;
	if (PinTypeObject->TryGetStringField(TEXT("subCategoryObject"), SubCategoryObjectPath) && !SubCategoryObjectPath.IsEmpty())
	{
		if (UObject* SubCategoryObject = ResolveObject(SubCategoryObjectPath))
		{
			OutPinType.PinSubCategoryObject = SubCategoryObject;
		}
		else
		{
			OutError = FString::Printf(TEXT("Failed to load pin subCategoryObject '%s'."), *SubCategoryObjectPath);
			return false;
		}
	}

	bool bIsReference = false;
	if (PinTypeObject->TryGetBoolField(TEXT("isReference"), bIsReference))
	{
		OutPinType.bIsReference = bIsReference;
	}

	bool bIsConst = false;
	if (PinTypeObject->TryGetBoolField(TEXT("isConst"), bIsConst))
	{
		OutPinType.bIsConst = bIsConst;
	}

	const TSharedPtr<FJsonObject>* ValueTypeObject = nullptr;
	if (OutPinType.ContainerType == EPinContainerType::Map
		&& PinTypeObject->TryGetObjectField(TEXT("valueType"), ValueTypeObject)
		&& ValueTypeObject)
	{
		return ParseTerminalType(*ValueTypeObject, OutPinType.PinValueType, OutError);
	}

	if (OutPinType.ContainerType == EPinContainerType::Map)
	{
		OutError = TEXT("Pin valueType is required for map pins.");
		return false;
	}

	return true;
}

bool FAuthoringHelpers::ApplyStructProperties(const UScriptStruct* ScriptStruct,
                                              void* StructMemory,
                                              const TSharedPtr<FJsonObject>& Properties,
                                              TArray<FString>& OutErrors,
                                              const bool bValidationOnly)
{
	if (!ScriptStruct || !StructMemory || !Properties.IsValid())
	{
		return true;
	}

	bool bSuccess = true;
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Properties->Values)
	{
		// Walk the super-struct chain so inherited properties are found
		FProperty* Property = nullptr;
		for (const UScriptStruct* Current = ScriptStruct; Current && !Property; Current = Cast<UScriptStruct>(Current->GetSuperStruct()))
		{
			Property = Current->FindPropertyByName(FName(*Pair.Key));
		}
		if (!Property)
		{
			OutErrors.Add(FString::Printf(TEXT("Property '%s' was not found on struct '%s'."), *Pair.Key, *ScriptStruct->GetName()));
			bSuccess = false;
			continue;
		}

		if (Property->HasAnyPropertyFlags(CPF_Deprecated | CPF_Transient))
		{
			OutErrors.Add(FString::Printf(TEXT("Property '%s' on struct '%s' is not writable."), *Pair.Key, *ScriptStruct->GetName()));
			bSuccess = false;
			continue;
		}

		void* ValuePtr = Property->ContainerPtrToValuePtr<void>(StructMemory);
		bSuccess &= FPropertySerializer::ApplyJsonValueToProperty(Property, ValuePtr, nullptr, Pair.Value, OutErrors, bValidationOnly);
	}

	return bSuccess;
}

bool FAuthoringHelpers::JsonValueToPropertyExportText(const FProperty* Property,
                                                      const TSharedPtr<FJsonValue>& JsonValue,
                                                      FString& OutText,
                                                      TArray<FString>& OutErrors,
                                                      UObject* OwnerObject)
{
	using namespace AuthoringHelpersInternal;

	if (!Property)
	{
		OutErrors.Add(TEXT("Property was null while converting default value."));
		return false;
	}

	FTemporaryPropertyStorage Storage(Property);
	if (!Storage.Data)
	{
		OutErrors.Add(FString::Printf(TEXT("Failed to allocate temporary storage for property '%s'."), *Property->GetName()));
		return false;
	}

	if (!FPropertySerializer::ApplyJsonValueToProperty(Property, Storage.Data, OwnerObject, JsonValue, OutErrors, false))
	{
		return false;
	}

	Property->ExportText_Direct(OutText, Storage.Data, nullptr, OwnerObject, PPF_None);
	return true;
}

bool FAuthoringHelpers::CompileBlueprint(UBlueprint* Blueprint,
                                         FAssetMutationContext& Context,
                                         const FString& AssetKind,
                                         const EBlueprintCompileOptions AdditionalCompileOptions)
{
	using namespace AuthoringHelpersInternal;

	if (!Blueprint)
	{
		Context.AddError(TEXT("compile_target_missing"), TEXT("Blueprint compile target is null."));
		return false;
	}

	if (GCompilingBlueprint || Blueprint->bBeingCompiled || !FBlueprintCompilationManager::IsGeneratedClassLayoutReady())
	{
		const FString BusyMessage = TEXT("Blueprint compilation is already in progress. Retry after the current compile finishes.");
		const TArray<TSharedPtr<FJsonValue>> EmptyArray;
		TArray<TSharedPtr<FJsonValue>> WarningArray;
		TArray<TSharedPtr<FJsonValue>> MessageArray;
		WarningArray.Add(MakeShared<FJsonValueString>(BusyMessage));
		MessageArray.Add(MakeMessageValue(TEXT("warning"), BusyMessage));
		Context.SetCompileSummary(MakeCompileResult(false, TEXT("Busy"), EmptyArray, WarningArray, MessageArray, 0, 1));
		Context.AddWarning(TEXT("compile_busy"), BusyMessage, Blueprint->GetPathName());
		return false;
	}

	FCompilerResultsLog CompileResults;
	CompileResults.bSilentMode = true;
	CompileResults.bAnnotateMentionedNodes = false;
	const EBlueprintCompileOptions CompileOptions = AdditionalCompileOptions | EBlueprintCompileOptions::SkipGarbageCollection;
	FKismetEditorUtilities::CompileBlueprint(Blueprint, CompileOptions, &CompileResults);

	const EBlueprintStatus Status = Blueprint->Status;
	const FString StatusString = GetBlueprintStatusString(Status);

	TArray<TSharedPtr<FJsonValue>> ErrorArray;
	TArray<TSharedPtr<FJsonValue>> WarningArray;
	TArray<TSharedPtr<FJsonValue>> MessageArray;
	int32 ErrorCount = CompileResults.NumErrors;
	int32 WarningCount = CompileResults.NumWarnings;

	for (const TSharedRef<FTokenizedMessage>& Message : CompileResults.Messages)
	{
		const FString MessageText = Message->ToText().ToString();
		switch (Message->GetSeverity())
		{
		case EMessageSeverity::Error:
			ErrorArray.Add(MakeShared<FJsonValueString>(MessageText));
			MessageArray.Add(MakeMessageValue(TEXT("error"), MessageText));
			break;
		case EMessageSeverity::Warning:
		case EMessageSeverity::PerformanceWarning:
			WarningArray.Add(MakeShared<FJsonValueString>(MessageText));
			MessageArray.Add(MakeMessageValue(TEXT("warning"), MessageText));
			break;
		default:
			MessageArray.Add(MakeMessageValue(TEXT("info"), MessageText));
			break;
		}
	}

	if (!Blueprint->GeneratedClass && ErrorCount == 0)
	{
		const FString GeneratedClassMessage = TEXT("GeneratedClass is null after compilation.");
		ErrorArray.Add(MakeShared<FJsonValueString>(GeneratedClassMessage));
		MessageArray.Add(MakeMessageValue(TEXT("error"), GeneratedClassMessage));
		++ErrorCount;
	}

	const bool bSuccess = (Status != BS_Error) && (ErrorCount == 0);
	Context.SetCompileSummary(MakeCompileResult(bSuccess, StatusString, ErrorArray, WarningArray, MessageArray, ErrorCount, WarningCount));

	if (!bSuccess)
	{
		FString ErrorSummary = FString::Printf(TEXT("%s compile failed with %d errors and %d warnings."), *AssetKind, ErrorCount, WarningCount);
		constexpr int32 MaxInlineErrors = 5;
		const int32 InlineCount = FMath::Min(ErrorArray.Num(), MaxInlineErrors);
		for (int32 Idx = 0; Idx < InlineCount; ++Idx)
		{
			FString ErrorText;
			if (ErrorArray[Idx].IsValid() && ErrorArray[Idx]->TryGetString(ErrorText))
			{
				ErrorSummary += FString::Printf(TEXT("\n  [%d] %s"), Idx + 1, *ErrorText);
			}
		}
		if (ErrorArray.Num() > MaxInlineErrors)
		{
			ErrorSummary += FString::Printf(TEXT("\n  ... and %d more (see compileSummary.errors)"), ErrorArray.Num() - MaxInlineErrors);
		}
		Context.AddError(TEXT("compile_failed"), ErrorSummary, Blueprint->GetPathName());
	}
	else if (WarningCount > 0)
	{
		Context.AddWarning(TEXT("compile_warning"),
		                   FString::Printf(TEXT("%s compile completed with %d warnings."), *AssetKind, WarningCount),
		                   Blueprint->GetPathName());
	}

	return bSuccess;
}
