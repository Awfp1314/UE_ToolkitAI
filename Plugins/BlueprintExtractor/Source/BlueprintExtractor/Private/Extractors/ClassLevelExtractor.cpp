#include "Extractors/ClassLevelExtractor.h"
#include "BlueprintJsonSchema.h"
#include "BlueprintExtractorModule.h"
#include "Engine/Blueprint.h"

TSharedPtr<FJsonObject> FClassLevelExtractor::Extract(const UBlueprint* Blueprint)
{
	if (!ensureMsgf(Blueprint, TEXT("ClassLevelExtractor: null Blueprint")))
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	// Parent class
	if (Blueprint->ParentClass)
	{
		Obj->SetObjectField(TEXT("parentClass"), FBlueprintJsonSchema::SerializeObjectReference(Blueprint->ParentClass));
	}

	// Implemented interfaces
	TArray<TSharedPtr<FJsonValue>> Interfaces;
	for (const FBPInterfaceDescription& Iface : Blueprint->ImplementedInterfaces)
	{
		if (Iface.Interface)
		{
			TSharedPtr<FJsonObject> IfaceObj = MakeShared<FJsonObject>();
			IfaceObj->SetStringField(TEXT("interfaceName"), Iface.Interface->GetName());
			IfaceObj->SetStringField(TEXT("interfacePath"), FBlueprintJsonSchema::GetObjectPathString(Iface.Interface));
			Interfaces.Add(MakeShared<FJsonValueObject>(IfaceObj));
		}
	}
	Obj->SetArrayField(TEXT("implementedInterfaces"), Interfaces);

	// Class flags from generated class
	if (Blueprint->GeneratedClass)
	{
		Obj->SetArrayField(TEXT("classFlags"), FBlueprintJsonSchema::SerializeClassFlags(Blueprint->GeneratedClass->GetClassFlags()));
	}

	// Blueprint metadata
	TSharedPtr<FJsonObject> MetaObj = MakeShared<FJsonObject>();
	MetaObj->SetStringField(TEXT("blueprintCategory"), Blueprint->BlueprintCategory);
	MetaObj->SetStringField(TEXT("blueprintDescription"), Blueprint->BlueprintDescription);
	MetaObj->SetStringField(TEXT("blueprintNamespace"), Blueprint->BlueprintNamespace);
	Obj->SetObjectField(TEXT("metadata"), MetaObj);

	return Obj;
}
