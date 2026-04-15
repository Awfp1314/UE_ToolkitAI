#include "Extractors/BlackboardExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "PropertySerializer.h"
#include "BehaviorTree/BlackboardData.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Class.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Enum.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_NativeEnum.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Object.h"

namespace BlackboardExtractorInternal
{

struct FBlackboardEntryView
{
	const FBlackboardEntry* Entry = nullptr;
	const UBlackboardData* SourceBlackboard = nullptr;
	bool bInherited = false;
};

static void BuildEffectiveEntries(const UBlackboardData* BlackboardData, TArray<FBlackboardEntryView>& OutEntries)
{
	if (!BlackboardData)
	{
		return;
	}

	if (BlackboardData->Parent)
	{
		BuildEffectiveEntries(BlackboardData->Parent, OutEntries);
		for (FBlackboardEntryView& ExistingEntry : OutEntries)
		{
			ExistingEntry.bInherited = true;
		}
	}

	for (const FBlackboardEntry& Entry : BlackboardData->Keys)
	{
		const int32 ExistingIndex = OutEntries.IndexOfByPredicate([&Entry](const FBlackboardEntryView& ExistingEntry)
		{
			return ExistingEntry.Entry && ExistingEntry.Entry->EntryName == Entry.EntryName;
		});

		const FBlackboardEntryView EntryView{&Entry, BlackboardData, false};
		if (ExistingIndex != INDEX_NONE)
		{
			OutEntries[ExistingIndex] = EntryView;
		}
		else
		{
			OutEntries.Add(EntryView);
		}
	}
}

static void AddKeyTypeDetails(const UBlackboardKeyType* KeyType, const TSharedPtr<FJsonObject>& EntryObject)
{
	if (!KeyType || !EntryObject.IsValid())
	{
		return;
	}

	const TSharedPtr<FJsonObject> Properties = FPropertySerializer::SerializePropertyOverrides(KeyType);
	if (Properties.IsValid() && Properties->Values.Num() > 0)
	{
		EntryObject->SetObjectField(TEXT("properties"), Properties);
	}

	if (const UBlackboardKeyType_Object* ObjectKeyType = Cast<UBlackboardKeyType_Object>(KeyType))
	{
		if (ObjectKeyType->BaseClass)
		{
			EntryObject->SetStringField(TEXT("baseClass"), ObjectKeyType->BaseClass->GetPathName());
		}
	}

	if (const UBlackboardKeyType_Class* ClassKeyType = Cast<UBlackboardKeyType_Class>(KeyType))
	{
		if (ClassKeyType->BaseClass)
		{
			EntryObject->SetStringField(TEXT("baseClass"), ClassKeyType->BaseClass->GetPathName());
		}
	}

	if (const UBlackboardKeyType_Enum* EnumKeyType = Cast<UBlackboardKeyType_Enum>(KeyType))
	{
		if (EnumKeyType->EnumType)
		{
			EntryObject->SetStringField(TEXT("enumType"), EnumKeyType->EnumType->GetPathName());
		}
		if (!EnumKeyType->EnumName.IsEmpty())
		{
			EntryObject->SetStringField(TEXT("enumName"), EnumKeyType->EnumName);
		}
	}

	if (const UBlackboardKeyType_NativeEnum* NativeEnumKeyType = Cast<UBlackboardKeyType_NativeEnum>(KeyType))
	{
		if (NativeEnumKeyType->EnumType)
		{
			EntryObject->SetStringField(TEXT("enumType"), NativeEnumKeyType->EnumType->GetPathName());
		}
		if (!NativeEnumKeyType->EnumName.IsEmpty())
		{
			EntryObject->SetStringField(TEXT("enumName"), NativeEnumKeyType->EnumName);
		}
	}
}

} // namespace BlackboardExtractorInternal

TSharedPtr<FJsonObject> FBlackboardExtractor::Extract(const UBlackboardData* BlackboardData)
{
	if (!BlackboardData)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> BlackboardObject = MakeShared<FJsonObject>();
	BlackboardObject->SetStringField(TEXT("assetPath"), BlackboardData->GetPathName());
	BlackboardObject->SetStringField(TEXT("assetName"), BlackboardData->GetName());

	if (BlackboardData->Parent)
	{
		BlackboardObject->SetStringField(TEXT("parentBlackboard"), BlackboardData->Parent->GetPathName());
	}

	TArray<BlackboardExtractorInternal::FBlackboardEntryView> EffectiveEntries;
	BlackboardExtractorInternal::BuildEffectiveEntries(BlackboardData, EffectiveEntries);

	TArray<TSharedPtr<FJsonValue>> Keys;
	for (const BlackboardExtractorInternal::FBlackboardEntryView& EntryView : EffectiveEntries)
	{
		if (!EntryView.Entry)
		{
			continue;
		}

		TSharedPtr<FJsonObject> EntryObject = MakeShared<FJsonObject>();
		EntryObject->SetStringField(TEXT("entryName"), EntryView.Entry->EntryName.ToString());
		EntryObject->SetBoolField(TEXT("isInstanceSynced"), EntryView.Entry->bInstanceSynced != 0);
		EntryObject->SetBoolField(TEXT("isInherited"), EntryView.bInherited);

		if (EntryView.SourceBlackboard)
		{
			EntryObject->SetStringField(TEXT("sourceBlackboard"), EntryView.SourceBlackboard->GetPathName());
		}

#if WITH_EDITORONLY_DATA
		if (!EntryView.Entry->EntryDescription.IsEmpty())
		{
			EntryObject->SetStringField(TEXT("description"), EntryView.Entry->EntryDescription);
		}
		if (!EntryView.Entry->EntryCategory.IsNone())
		{
			EntryObject->SetStringField(TEXT("category"), EntryView.Entry->EntryCategory.ToString());
		}
#endif

		if (EntryView.Entry->KeyType)
		{
			EntryObject->SetStringField(TEXT("keyType"), EntryView.Entry->KeyType->GetClass()->GetName());
			EntryObject->SetStringField(TEXT("keyTypePath"), EntryView.Entry->KeyType->GetClass()->GetPathName());
			BlackboardExtractorInternal::AddKeyTypeDetails(EntryView.Entry->KeyType, EntryObject);
		}

		Keys.Add(MakeShared<FJsonValueObject>(EntryObject));
	}

	BlackboardObject->SetNumberField(TEXT("keyCount"), Keys.Num());
	BlackboardObject->SetArrayField(TEXT("keys"), Keys);

	Root->SetObjectField(TEXT("blackboard"), BlackboardObject);
	return Root;
}
