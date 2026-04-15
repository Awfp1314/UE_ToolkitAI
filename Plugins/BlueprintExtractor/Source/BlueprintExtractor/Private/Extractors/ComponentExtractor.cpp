#include "Extractors/ComponentExtractor.h"
#include "BlueprintJsonSchema.h"
#include "BlueprintExtractorModule.h"
#include "PropertySerializer.h"
#include "Engine/Blueprint.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "Components/ActorComponent.h"
#include "UObject/SoftObjectPtr.h"
#include "UObject/UnrealType.h"

TSharedPtr<FJsonObject> FComponentExtractor::Extract(const UBlueprint* Blueprint)
{
	if (!ensureMsgf(Blueprint, TEXT("ComponentExtractor: null Blueprint")))
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();

	USimpleConstructionScript* SCS = Blueprint->SimpleConstructionScript;
	if (!SCS)
	{
		return Result;
	}

	const TArray<USCS_Node*>& RootNodes = SCS->GetRootNodes();
	TArray<TSharedPtr<FJsonValue>> RootComponents;

	for (const USCS_Node* Node : RootNodes)
	{
		if (Node)
		{
			RootComponents.Add(MakeShared<FJsonValueObject>(ExtractSCSNode(Node)));
		}
	}

	Result->SetArrayField(TEXT("rootComponents"), RootComponents);

	return Result;
}

TSharedPtr<FJsonObject> FComponentExtractor::ExtractSCSNode(const USCS_Node* Node)
{
	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	Obj->SetStringField(TEXT("componentName"), Node->GetVariableName().ToString());

	if (Node->ComponentClass)
	{
		Obj->SetStringField(TEXT("componentClass"), Node->ComponentClass->GetPathName());
	}

	if (!Node->AttachToName.IsNone())
	{
		Obj->SetStringField(TEXT("attachToName"), Node->AttachToName.ToString());
	}

	// Property overrides vs CDO
	if (Node->ComponentTemplate)
	{
		TSharedPtr<FJsonObject> Overrides = ExtractPropertyOverrides(Node->ComponentTemplate);
		if (Overrides && Overrides->Values.Num() > 0)
		{
			Obj->SetObjectField(TEXT("propertyOverrides"), Overrides);
		}
	}

	// Children
	TArray<TSharedPtr<FJsonValue>> Children;
	for (const USCS_Node* Child : Node->GetChildNodes())
	{
		if (Child)
		{
			Children.Add(MakeShared<FJsonValueObject>(ExtractSCSNode(Child)));
		}
	}

	if (Children.Num() > 0)
	{
		Obj->SetArrayField(TEXT("children"), Children);
	}

	return Obj;
}

TSharedPtr<FJsonObject> FComponentExtractor::ExtractPropertyOverrides(const UActorComponent* ComponentTemplate)
{
	TSharedPtr<FJsonObject> Overrides = MakeShared<FJsonObject>();

	if (!ComponentTemplate)
	{
		return Overrides;
	}

	UClass* ComponentClass = ComponentTemplate->GetClass();
	const UObject* CDO = ComponentClass->GetDefaultObject();

	for (TFieldIterator<FProperty> PropIt(ComponentClass); PropIt; ++PropIt)
	{
		FProperty* Property = *PropIt;

		if (!Property->HasAnyPropertyFlags(CPF_Edit | CPF_BlueprintVisible))
		{
			continue;
		}

		if (!Property->Identical_InContainer(ComponentTemplate, CDO))
		{
			const void* ValuePtr = Property->ContainerPtrToValuePtr<void>(ComponentTemplate);
			const TSharedPtr<FJsonValue> JsonValue = FPropertySerializer::SerializePropertyValue(Property, ValuePtr);
			if (JsonValue)
			{
				Overrides->SetField(Property->GetName(), JsonValue);
			}

			// Structs containing soft object pointers (e.g. FStateTreeReference)
			// may not serialize the inner path through the generic converter.
			// Extract soft object paths explicitly as dot-notation overrides.
			if (FStructProperty* StructProp = CastField<FStructProperty>(Property))
			{
				const void* StructPtr = StructProp->ContainerPtrToValuePtr<void>(ComponentTemplate);
				for (TFieldIterator<FProperty> InnerIt(StructProp->Struct); InnerIt; ++InnerIt)
				{
					if (FSoftObjectProperty* SoftProp = CastField<FSoftObjectProperty>(*InnerIt))
					{
						const FSoftObjectPtr& SoftPtr = *SoftProp->GetPropertyValuePtr_InContainer(
							const_cast<void*>(StructPtr));
						if (!SoftPtr.IsNull())
						{
							FString Path = SoftPtr.ToSoftObjectPath().ToString();
							Overrides->SetStringField(
								FString::Printf(TEXT("%s.%s"), *Property->GetName(), *SoftProp->GetName()),
								Path);
						}
					}
				}
			}
		}
	}

	return Overrides;
}
