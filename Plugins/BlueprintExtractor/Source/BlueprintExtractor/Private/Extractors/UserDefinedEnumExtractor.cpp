#include "Extractors/UserDefinedEnumExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "Engine/UserDefinedEnum.h"

TSharedPtr<FJsonObject> FUserDefinedEnumExtractor::Extract(const UUserDefinedEnum* UserDefinedEnum)
{
	if (!UserDefinedEnum)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> EnumObject = MakeShared<FJsonObject>();
	EnumObject->SetStringField(TEXT("assetPath"), UserDefinedEnum->GetPathName());
	EnumObject->SetStringField(TEXT("assetName"), UserDefinedEnum->GetName());
	EnumObject->SetStringField(TEXT("cppType"), UserDefinedEnum->GetName());

	TArray<TSharedPtr<FJsonValue>> Entries;
	const int32 EntryCount = FMath::Max(0, UserDefinedEnum->NumEnums() - 1);
	for (int32 Index = 0; Index < EntryCount; ++Index)
	{
		TSharedPtr<FJsonObject> EntryObject = MakeShared<FJsonObject>();
		EntryObject->SetStringField(TEXT("name"), UserDefinedEnum->GetNameStringByIndex(Index));
		EntryObject->SetStringField(TEXT("displayName"), UserDefinedEnum->GetDisplayNameTextByIndex(Index).ToString());
		EntryObject->SetNumberField(TEXT("value"), static_cast<double>(UserDefinedEnum->GetValueByIndex(Index)));
		Entries.Add(MakeShared<FJsonValueObject>(EntryObject));
	}

	EnumObject->SetArrayField(TEXT("entries"), Entries);
	Root->SetObjectField(TEXT("userDefinedEnum"), EnumObject);
	return Root;
}
