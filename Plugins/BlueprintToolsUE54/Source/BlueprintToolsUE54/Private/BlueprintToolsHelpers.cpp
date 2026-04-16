#include "BlueprintToolsHelpers.h"
#include "BlueprintToolsModule.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Dom/JsonObject.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

FString FBlueprintToolsHelpers::NormalizeAssetObjectPath(const FString& ObjectPath)
{
	if (ObjectPath.IsEmpty())
	{
		return ObjectPath;
	}

	// If it ends with _C, it's already a generated class path
	if (ObjectPath.EndsWith(TEXT("_C")))
	{
		return ObjectPath;
	}

	// If it contains a dot, it might be Package.Asset format
	if (ObjectPath.Contains(TEXT(".")))
	{
		return ObjectPath;
	}

	// If it's a package path like /Game/Blueprints/BP_MyActor
	// Convert to /Game/Blueprints/BP_MyActor.BP_MyActor_C for Blueprint class
	if (ObjectPath.StartsWith(TEXT("/")) && !ObjectPath.StartsWith(TEXT("/Script/")))
	{
		FString PackageName;
		FString AssetName;
		if (ObjectPath.Split(TEXT("/"), &PackageName, &AssetName, ESearchCase::IgnoreCase, ESearchDir::FromEnd))
		{
			return FString::Printf(TEXT("%s/%s.%s_C"), *PackageName, *AssetName, *AssetName);
		}
	}

	return ObjectPath;
}

bool FBlueprintToolsHelpers::DoesAssetExist(const FString& AssetPath)
{
	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	IAssetRegistry& AssetRegistry = AssetRegistryModule.Get();

	FString PackageName = AssetPath;
	if (AssetPath.Contains(TEXT(".")))
	{
		AssetPath.Split(TEXT("."), &PackageName, nullptr);
	}

	return AssetRegistry.GetAssetByObjectPath(FSoftObjectPath(AssetPath)).IsValid();
}

UObject* FBlueprintToolsHelpers::ResolveObject(const FString& ObjectPath, UClass* RequiredClass)
{
	if (ObjectPath.IsEmpty())
	{
		return nullptr;
	}

	const FString NormalizedObjectPath = NormalizeAssetObjectPath(ObjectPath);
	UClass* SearchClass = RequiredClass ? RequiredClass : UObject::StaticClass();

	// Try to find already loaded object
	if (UObject* FoundObject = FindObject<UObject>(nullptr, *NormalizedObjectPath))
	{
		return !RequiredClass || FoundObject->IsA(RequiredClass) ? FoundObject : nullptr;
	}

	// Try original path if different
	if (NormalizedObjectPath != ObjectPath)
	{
		if (UObject* FoundObject = FindObject<UObject>(nullptr, *ObjectPath))
		{
			return !RequiredClass || FoundObject->IsA(RequiredClass) ? FoundObject : nullptr;
		}
	}

	// Try to load the object
	if (UObject* LoadedObject = StaticLoadObject(SearchClass, nullptr, *NormalizedObjectPath))
	{
		return LoadedObject;
	}

	// Try original path
	if (NormalizedObjectPath != ObjectPath)
	{
		if (UObject* LoadedObject = StaticLoadObject(SearchClass, nullptr, *ObjectPath))
		{
			return LoadedObject;
		}
	}

	return nullptr;
}

UClass* FBlueprintToolsHelpers::ResolveClass(const FString& ClassPath, UClass* RequiredBaseClass)
{
	if (ClassPath.IsEmpty())
	{
		return nullptr;
	}

	// Try to find already loaded class
	if (UClass* FoundClass = FindObject<UClass>(nullptr, *ClassPath))
	{
		return !RequiredBaseClass || FoundClass->IsChildOf(RequiredBaseClass) ? FoundClass : nullptr;
	}

	UClass* SearchBase = RequiredBaseClass ? RequiredBaseClass : UObject::StaticClass();
	const FString NormalizedClassPath = NormalizeAssetObjectPath(ClassPath);

	// Try to load the class
	if (UClass* LoadedClass = StaticLoadClass(SearchBase, nullptr, *NormalizedClassPath))
	{
		return LoadedClass;
	}

	// Try as object and cast to class
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

UScriptStruct* FBlueprintToolsHelpers::ResolveScriptStruct(const FString& StructPath)
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

UEnum* FBlueprintToolsHelpers::ResolveEnum(const FString& EnumPath)
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

bool FBlueprintToolsHelpers::ParseContainerType(const FString& ContainerTypeString, EPinContainerType& OutContainerType)
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

bool FBlueprintToolsHelpers::ParseTerminalType(const TSharedPtr<FJsonObject>& ValueTypeObject,
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
		if (UObject* TerminalObject = ResolveObject(SubCategoryObjectPath))
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

bool FBlueprintToolsHelpers::ParsePinType(const TSharedPtr<FJsonObject>& PinTypeObject,
                                         FEdGraphPinType& OutPinType,
                                         FString& OutError)
{
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

	// Parse container type
	FString ContainerTypeString;
	if (PinTypeObject->TryGetStringField(TEXT("containerType"), ContainerTypeString))
	{
		if (!ParseContainerType(ContainerTypeString, OutPinType.ContainerType))
		{
			OutError = FString::Printf(TEXT("Unsupported pin container type '%s'."), *ContainerTypeString);
			return false;
		}
	}

	// Parse sub category
	FString SubCategory;
	if (PinTypeObject->TryGetStringField(TEXT("subCategory"), SubCategory))
	{
		OutPinType.PinSubCategory = FName(*SubCategory);
	}

	// Parse sub category object
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

	// Parse reference flag
	bool bIsReference = false;
	if (PinTypeObject->TryGetBoolField(TEXT("isReference"), bIsReference))
	{
		OutPinType.bIsReference = bIsReference;
	}

	// Parse const flag
	bool bIsConst = false;
	if (PinTypeObject->TryGetBoolField(TEXT("isConst"), bIsConst))
	{
		OutPinType.bIsConst = bIsConst;
	}

	// Parse value type for maps
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

int32 FBlueprintToolsHelpers::FindVariableIndex(const UBlueprint* Blueprint, FName VariableName)
{
	if (!Blueprint)
	{
		return INDEX_NONE;
	}

	for (int32 Idx = 0; Idx < Blueprint->NewVariables.Num(); ++Idx)
	{
		if (Blueprint->NewVariables[Idx].VarName == VariableName)
		{
			return Idx;
		}
	}

	return INDEX_NONE;
}

bool FBlueprintToolsHelpers::CompileBlueprint(UBlueprint* Blueprint,
                                             TArray<TSharedPtr<FJsonValue>>& OutErrors,
                                             TArray<TSharedPtr<FJsonValue>>& OutWarnings)
{
	if (!Blueprint)
	{
		return false;
	}

	FKismetEditorUtilities::CompileBlueprint(Blueprint);

	// Check compilation status
	const bool bSuccess = (Blueprint->Status != BS_Error);

	// TODO: Collect actual compilation errors and warnings from compiler results
	// For now, just check the status
	if (!bSuccess)
	{
		TSharedPtr<FJsonObject> ErrorObj = MakeShared<FJsonObject>();
		ErrorObj->SetStringField(TEXT("message"), TEXT("Blueprint compilation failed"));
		ErrorObj->SetStringField(TEXT("severity"), TEXT("error"));
		OutErrors.Add(MakeShared<FJsonValueObject>(ErrorObj));
	}

	return bSuccess;
}

TSharedPtr<FJsonObject> FBlueprintToolsHelpers::CreateErrorResponse(const FString& ErrorMessage)
{
	TSharedPtr<FJsonObject> ErrorObj = MakeShared<FJsonObject>();
	ErrorObj->SetBoolField(TEXT("success"), false);
	ErrorObj->SetStringField(TEXT("error"), ErrorMessage);
	return ErrorObj;
}

TSharedPtr<FJsonObject> FBlueprintToolsHelpers::CreateSuccessResponse()
{
	TSharedPtr<FJsonObject> SuccessObj = MakeShared<FJsonObject>();
	SuccessObj->SetBoolField(TEXT("success"), true);
	return SuccessObj;
}

FString FBlueprintToolsHelpers::SerializeJsonObject(const TSharedPtr<FJsonObject>& JsonObject)
{
	FString OutString;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutString);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
	return OutString;
}
