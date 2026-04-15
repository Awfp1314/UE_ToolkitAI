#include "Extractors/ClassDefaultsExtractor.h"
#include "PropertySerializer.h"
#include "Engine/Blueprint.h"

TSharedPtr<FJsonObject> FClassDefaultsExtractor::Extract(const UBlueprint* Blueprint)
{
	if (!Blueprint || !Blueprint->GeneratedClass)
	{
		return MakeShared<FJsonObject>();
	}

	const UObject* GeneratedDefaultObject = Blueprint->GeneratedClass->GetDefaultObject(false);
	const UClass* ParentClass = Blueprint->GeneratedClass->GetSuperClass();
	const UObject* ParentDefaultObject = ParentClass ? ParentClass->GetDefaultObject(false) : nullptr;
	if (!GeneratedDefaultObject)
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject> Overrides = MakeShared<FJsonObject>();
	TSet<FName> SerializedPropertyNames;

	const auto AppendOverridesForClass = [&Overrides, &SerializedPropertyNames, GeneratedDefaultObject, ParentDefaultObject](const UClass* SourceClass)
	{
		if (!SourceClass)
		{
			return;
		}

		for (TFieldIterator<FProperty> PropIt(SourceClass); PropIt; ++PropIt)
		{
			const FProperty* Property = *PropIt;
			if (!Property)
			{
				continue;
			}

			const FName PropertyName = Property->GetFName();
			if (SerializedPropertyNames.Contains(PropertyName))
			{
				continue;
			}
			SerializedPropertyNames.Add(PropertyName);

			if (!Property->HasAnyPropertyFlags(CPF_Edit | CPF_BlueprintVisible))
			{
				continue;
			}

			if (Property->HasAnyPropertyFlags(CPF_Deprecated | CPF_Transient))
			{
				continue;
			}

			const bool bHasMatchingBaselineClass = ParentDefaultObject
				&& ParentDefaultObject->GetClass()->IsChildOf(Property->GetOwnerClass());
			if (bHasMatchingBaselineClass && Property->Identical_InContainer(GeneratedDefaultObject, ParentDefaultObject))
			{
				continue;
			}

			const void* ValuePtr = Property->ContainerPtrToValuePtr<void>(GeneratedDefaultObject);
			const TSharedPtr<FJsonValue> JsonValue = FPropertySerializer::SerializePropertyValue(Property, ValuePtr);
			if (JsonValue.IsValid())
			{
				Overrides->SetField(Property->GetName(), JsonValue);
			}
		}
	};

	AppendOverridesForClass(Blueprint->GeneratedClass);
	AppendOverridesForClass(ParentClass);
	return Overrides;
}
