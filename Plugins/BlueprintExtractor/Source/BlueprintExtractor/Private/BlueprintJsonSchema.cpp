#include "BlueprintJsonSchema.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"

TSharedPtr<FJsonObject> FBlueprintJsonSchema::SerializePinType(const FEdGraphPinType& PinType)
{
	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	Obj->SetStringField(TEXT("category"), PinType.PinCategory.ToString());

	FString ContainerStr = TEXT("None");
	if (PinType.ContainerType == EPinContainerType::Array)
	{
		ContainerStr = TEXT("Array");
	}
	else if (PinType.ContainerType == EPinContainerType::Set)
	{
		ContainerStr = TEXT("Set");
	}
	else if (PinType.ContainerType == EPinContainerType::Map)
	{
		ContainerStr = TEXT("Map");
	}
	Obj->SetStringField(TEXT("containerType"), ContainerStr);

	if (PinType.PinSubCategoryObject.IsValid())
	{
		Obj->SetStringField(TEXT("subCategoryObject"), GetObjectPathString(PinType.PinSubCategoryObject.Get()));
	}

	if (!PinType.PinSubCategory.IsNone())
	{
		Obj->SetStringField(TEXT("subCategory"), PinType.PinSubCategory.ToString());
	}

	if (PinType.bIsReference)
	{
		Obj->SetBoolField(TEXT("isReference"), true);
	}

	if (PinType.bIsConst)
	{
		Obj->SetBoolField(TEXT("isConst"), true);
	}

	if (PinType.ContainerType == EPinContainerType::Map)
	{
		TSharedPtr<FJsonObject> ValueType = MakeShared<FJsonObject>();
		ValueType->SetStringField(TEXT("category"), PinType.PinValueType.TerminalCategory.ToString());
		if (PinType.PinValueType.TerminalSubCategoryObject.IsValid())
		{
			ValueType->SetStringField(TEXT("subCategoryObject"), GetObjectPathString(PinType.PinValueType.TerminalSubCategoryObject.Get()));
		}
		if (!PinType.PinValueType.TerminalSubCategory.IsNone())
		{
			ValueType->SetStringField(TEXT("subCategory"), PinType.PinValueType.TerminalSubCategory.ToString());
		}
		Obj->SetObjectField(TEXT("valueType"), ValueType);
	}

	return Obj;
}

TArray<TSharedPtr<FJsonValue>> FBlueprintJsonSchema::SerializePropertyFlags(uint64 Flags)
{
	TArray<TSharedPtr<FJsonValue>> Result;

#define CHECK_FLAG(Flag) if ((Flags & Flag) != 0) { Result.Add(MakeShared<FJsonValueString>(TEXT(#Flag))); }
	CHECK_FLAG(CPF_Edit);
	CHECK_FLAG(CPF_BlueprintVisible);
	CHECK_FLAG(CPF_BlueprintReadOnly);
	CHECK_FLAG(CPF_Net);
	CHECK_FLAG(CPF_SaveGame);
	CHECK_FLAG(CPF_EditConst);
	CHECK_FLAG(CPF_DisableEditOnInstance);
	CHECK_FLAG(CPF_DisableEditOnTemplate);
	CHECK_FLAG(CPF_Transient);
	CHECK_FLAG(CPF_Config);
	CHECK_FLAG(CPF_RepNotify);
	CHECK_FLAG(CPF_Interp);
	CHECK_FLAG(CPF_ExposeOnSpawn);
	CHECK_FLAG(CPF_BlueprintAssignable);
	CHECK_FLAG(CPF_BlueprintCallable);
#undef CHECK_FLAG

	return Result;
}

TArray<TSharedPtr<FJsonValue>> FBlueprintJsonSchema::SerializeFunctionFlags(uint32 Flags)
{
	TArray<TSharedPtr<FJsonValue>> Result;

#define CHECK_FLAG(Flag) if ((Flags & Flag) != 0) { Result.Add(MakeShared<FJsonValueString>(TEXT(#Flag))); }
	CHECK_FLAG(FUNC_BlueprintCallable);
	CHECK_FLAG(FUNC_BlueprintPure);
	CHECK_FLAG(FUNC_BlueprintEvent);
	CHECK_FLAG(FUNC_Static);
	CHECK_FLAG(FUNC_Const);
	CHECK_FLAG(FUNC_Net);
	CHECK_FLAG(FUNC_NetServer);
	CHECK_FLAG(FUNC_NetClient);
	CHECK_FLAG(FUNC_NetMulticast);
	CHECK_FLAG(FUNC_BlueprintAuthorityOnly);
	CHECK_FLAG(FUNC_HasOutParms);
	CHECK_FLAG(FUNC_Native);
	CHECK_FLAG(FUNC_Public);
	CHECK_FLAG(FUNC_Protected);
	CHECK_FLAG(FUNC_Private);
#undef CHECK_FLAG

	return Result;
}

TArray<TSharedPtr<FJsonValue>> FBlueprintJsonSchema::SerializeClassFlags(uint32 Flags)
{
	TArray<TSharedPtr<FJsonValue>> Result;

#define CHECK_FLAG(Flag) if ((Flags & Flag) != 0) { Result.Add(MakeShared<FJsonValueString>(TEXT(#Flag))); }
	CHECK_FLAG(CLASS_Abstract);
	CHECK_FLAG(CLASS_DefaultConfig);
	CHECK_FLAG(CLASS_Transient);
	CHECK_FLAG(CLASS_Config);
	CHECK_FLAG(CLASS_Interface);
	CHECK_FLAG(CLASS_Deprecated);
	CHECK_FLAG(CLASS_MinimalAPI);
#undef CHECK_FLAG

	return Result;
}

FString FBlueprintJsonSchema::GetObjectPathString(const UObject* Object)
{
	if (!Object)
	{
		return FString();
	}
	return Object->GetPathName();
}

FString FBlueprintJsonSchema::BlueprintTypeToString(EBlueprintType Type)
{
	switch (Type)
	{
	case BPTYPE_Normal: return TEXT("Normal");
	case BPTYPE_Const: return TEXT("Const");
	case BPTYPE_MacroLibrary: return TEXT("MacroLibrary");
	case BPTYPE_Interface: return TEXT("Interface");
	case BPTYPE_LevelScript: return TEXT("LevelScript");
	case BPTYPE_FunctionLibrary: return TEXT("FunctionLibrary");
	default: return TEXT("Unknown");
	}
}

TSharedPtr<FJsonObject> FBlueprintJsonSchema::SerializeObjectReference(const UClass* Class)
{
	if (!Class)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();
	Obj->SetStringField(TEXT("className"), Class->GetName());
	Obj->SetStringField(TEXT("classPath"), GetObjectPathString(Class));
	Obj->SetBoolField(TEXT("isNative"), Class->IsNative());
	return Obj;
}
