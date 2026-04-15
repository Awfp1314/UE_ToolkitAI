#include "Authoring/MaterialInstanceAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "CoreGlobals.h"
#include "Engine/Font.h"
#include "Engine/Texture.h"
#include "Factories/MaterialInstanceConstantFactoryNew.h"
#include "MaterialEditingLibrary.h"
#include "Materials/Material.h"
#include "Materials/MaterialLayersFunctions.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Materials/MaterialInterface.h"
#include "SparseVolumeTexture/SparseVolumeTexture.h"
#include "VT/RuntimeVirtualTexture.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace MaterialInstanceAuthoringInternal
{

static bool ParseColor(const TSharedPtr<FJsonObject>& ColorObject, FLinearColor& OutColor)
{
	if (!ColorObject.IsValid())
	{
		return false;
	}

	double R = 0.0;
	double G = 0.0;
	double B = 0.0;
	double A = 1.0;
	return ColorObject->TryGetNumberField(TEXT("r"), R)
		&& ColorObject->TryGetNumberField(TEXT("g"), G)
		&& ColorObject->TryGetNumberField(TEXT("b"), B)
		&& ColorObject->TryGetNumberField(TEXT("a"), A)
		&& ((OutColor = FLinearColor(static_cast<float>(R), static_cast<float>(G), static_cast<float>(B), static_cast<float>(A))), true);
}

static UMaterialInterface* ResolveParentMaterial(const FString& ParentMaterialPath)
{
	if (ParentMaterialPath.IsEmpty())
	{
		return nullptr;
	}

	return LoadObject<UMaterialInterface>(nullptr, *ParentMaterialPath);
}

static bool ParseAssociation(const FString& AssociationString, EMaterialParameterAssociation& OutAssociation)
{
	if (AssociationString.Equals(TEXT("LayerParameter"), ESearchCase::IgnoreCase)
		|| AssociationString.Equals(TEXT("layer"), ESearchCase::IgnoreCase))
	{
		OutAssociation = EMaterialParameterAssociation::LayerParameter;
		return true;
	}

	if (AssociationString.Equals(TEXT("BlendParameter"), ESearchCase::IgnoreCase)
		|| AssociationString.Equals(TEXT("blend"), ESearchCase::IgnoreCase))
	{
		OutAssociation = EMaterialParameterAssociation::BlendParameter;
		return true;
	}

	if (AssociationString.Equals(TEXT("GlobalParameter"), ESearchCase::IgnoreCase)
		|| AssociationString.Equals(TEXT("global"), ESearchCase::IgnoreCase)
		|| AssociationString.IsEmpty())
	{
		OutAssociation = EMaterialParameterAssociation::GlobalParameter;
		return true;
	}

	return false;
}

static bool BuildParameterInfo(const TSharedPtr<FJsonObject>& Item, FMaterialParameterInfo& OutParameterInfo)
{
	if (!Item.IsValid())
	{
		return false;
	}

	FString Name;
	if (!Item->TryGetStringField(TEXT("name"), Name) || Name.IsEmpty())
	{
		return false;
	}

	EMaterialParameterAssociation Association = EMaterialParameterAssociation::GlobalParameter;
	FString AssociationString;
	if (Item->TryGetStringField(TEXT("association"), AssociationString) && !ParseAssociation(AssociationString, Association))
	{
		return false;
	}

	int32 Index = INDEX_NONE;
	if (Item->HasTypedField<EJson::Number>(TEXT("index")))
	{
		Index = static_cast<int32>(Item->GetNumberField(TEXT("index")));
	}

	OutParameterInfo = FMaterialParameterInfo(FName(*Name), Association, Index);
	return true;
}

static bool ParseLayerStack(const TSharedPtr<FJsonObject>& LayerStackJson,
                            FMaterialLayersFunctions& OutLayers,
                            TArray<FString>& OutErrors)
{
	if (!LayerStackJson.IsValid())
	{
		OutErrors.Add(TEXT("Layer stack payload must be an object."));
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* LayerValues = nullptr;
	if (!LayerStackJson->TryGetArrayField(TEXT("layers"), LayerValues) || !LayerValues)
	{
		OutErrors.Add(TEXT("Layer stack payload requires a layers array."));
		return false;
	}

	OutLayers = FMaterialLayersFunctions();
	OutLayers.Layers.Reset(LayerValues->Num());
	OutLayers.Blends.Reset(LayerValues->Num());
	OutLayers.EditorOnly.LayerNames.Reset(LayerValues->Num());
	OutLayers.EditorOnly.LayerStates.Reset(LayerValues->Num());
	OutLayers.EditorOnly.LayerGuids.Reset(LayerValues->Num());

	for (int32 LayerIndex = 0; LayerIndex < LayerValues->Num(); ++LayerIndex)
	{
		const TSharedPtr<FJsonObject> LayerObject = (*LayerValues)[LayerIndex].IsValid() ? (*LayerValues)[LayerIndex]->AsObject() : nullptr;
		if (!LayerObject.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("Layer stack entry %d must be an object."), LayerIndex));
			return false;
		}

		FString LayerPath;
		if (LayerObject->TryGetStringField(TEXT("layerPath"), LayerPath) && !LayerPath.IsEmpty())
		{
			UMaterialFunctionInterface* LayerAsset = LoadObject<UMaterialFunctionInterface>(nullptr, *LayerPath);
			if (!LayerAsset)
			{
				OutErrors.Add(FString::Printf(TEXT("Failed to load layer asset '%s'."), *LayerPath));
				return false;
			}
			OutLayers.Layers.Add(LayerAsset);
		}
		else
		{
			OutLayers.Layers.Add(nullptr);
		}

		FString BlendPath;
		if (LayerObject->TryGetStringField(TEXT("blendPath"), BlendPath) && !BlendPath.IsEmpty())
		{
			UMaterialFunctionInterface* BlendAsset = LoadObject<UMaterialFunctionInterface>(nullptr, *BlendPath);
			if (!BlendAsset)
			{
				OutErrors.Add(FString::Printf(TEXT("Failed to load blend asset '%s'."), *BlendPath));
				return false;
			}
			OutLayers.Blends.Add(BlendAsset);
		}
		else
		{
			OutLayers.Blends.Add(nullptr);
		}

		FString LayerName;
		LayerObject->TryGetStringField(TEXT("name"), LayerName);
		OutLayers.EditorOnly.LayerNames.Add(FText::FromString(
			LayerName.IsEmpty() ? FString::Printf(TEXT("Layer_%d"), LayerIndex) : LayerName));

		bool bVisible = true;
		LayerObject->TryGetBoolField(TEXT("visible"), bVisible);
		OutLayers.EditorOnly.LayerStates.Add(bVisible);

		FString LayerGuidString;
		FGuid LayerGuid = FGuid::NewGuid();
		if (LayerObject->TryGetStringField(TEXT("layerGuid"), LayerGuidString))
		{
			FGuid::Parse(LayerGuidString, LayerGuid);
		}
		OutLayers.EditorOnly.LayerGuids.Add(LayerGuid);
	}

	return true;
}

static bool ValidatePayload(UMaterialInstanceConstant* MaterialInstance,
                            const TSharedPtr<FJsonObject>& PayloadJson,
                            FAssetMutationContext& Context)
{
	if (!PayloadJson.IsValid())
	{
		Context.SetValidationSummary(true, TEXT("Empty material payload validated."));
		return true;
	}

	bool bSuccess = true;
	TArray<FString> ValidationErrors;

	FString ParentMaterialPath;
	if (PayloadJson->TryGetStringField(TEXT("parentMaterial"), ParentMaterialPath) && !ParentMaterialPath.IsEmpty())
	{
		if (!ResolveParentMaterial(ParentMaterialPath))
		{
			ValidationErrors.Add(FString::Printf(TEXT("Failed to load parent material '%s'"), *ParentMaterialPath));
			bSuccess = false;
		}
	}

	auto ValidateNamedArray = [&](const TCHAR* FieldName, TFunctionRef<bool(const TSharedPtr<FJsonObject>&)> Validator)
	{
		const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
		if (!PayloadJson->TryGetArrayField(FieldName, Items) || !Items)
		{
			return;
		}

		for (const TSharedPtr<FJsonValue>& ItemValue : *Items)
		{
			const TSharedPtr<FJsonObject> Item = ItemValue.IsValid() ? ItemValue->AsObject() : nullptr;
			if (!Item.IsValid() || !Validator(Item))
			{
				ValidationErrors.Add(FString::Printf(TEXT("Invalid payload entry in '%s'"), FieldName));
				bSuccess = false;
			}
		}
	};

	ValidateNamedArray(TEXT("scalarParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FString Name;
		double Value = 0.0;
		return Item->TryGetStringField(TEXT("name"), Name) && Item->TryGetNumberField(TEXT("value"), Value);
	});

	ValidateNamedArray(TEXT("vectorParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FString Name;
		FLinearColor Color;
		const TSharedPtr<FJsonObject>* ColorObject = nullptr;
		return Item->TryGetStringField(TEXT("name"), Name)
			&& Item->TryGetObjectField(TEXT("value"), ColorObject)
			&& ColorObject
			&& ParseColor(*ColorObject, Color);
	});

	ValidateNamedArray(TEXT("textureParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		if (!BuildParameterInfo(Item, ParameterInfo))
		{
			return false;
		}

		if (!Item->HasField(TEXT("value")) || Item->Values[TEXT("value")]->Type == EJson::Null)
		{
			return true;
		}

		FString TexturePath;
		return Item->TryGetStringField(TEXT("value"), TexturePath)
			&& (TexturePath.IsEmpty() || LoadObject<UTexture>(nullptr, *TexturePath) != nullptr);
	});

	ValidateNamedArray(TEXT("runtimeVirtualTextureParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		if (!BuildParameterInfo(Item, ParameterInfo))
		{
			return false;
		}

		if (!Item->HasField(TEXT("value")) || Item->Values[TEXT("value")]->Type == EJson::Null)
		{
			return true;
		}

		FString TexturePath;
		return Item->TryGetStringField(TEXT("value"), TexturePath)
			&& (TexturePath.IsEmpty() || LoadObject<URuntimeVirtualTexture>(nullptr, *TexturePath) != nullptr);
	});

	ValidateNamedArray(TEXT("sparseVolumeTextureParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		if (!BuildParameterInfo(Item, ParameterInfo))
		{
			return false;
		}

		if (!Item->HasField(TEXT("value")) || Item->Values[TEXT("value")]->Type == EJson::Null)
		{
			return true;
		}

		FString TexturePath;
		return Item->TryGetStringField(TEXT("value"), TexturePath)
			&& (TexturePath.IsEmpty() || LoadObject<USparseVolumeTexture>(nullptr, *TexturePath) != nullptr);
	});

	ValidateNamedArray(TEXT("fontParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		if (!BuildParameterInfo(Item, ParameterInfo))
		{
			return false;
		}

		if (!Item->HasField(TEXT("value")) || Item->Values[TEXT("value")]->Type == EJson::Null)
		{
			return !Item->HasField(TEXT("fontPage")) || Item->Values[TEXT("fontPage")]->Type == EJson::Number;
		}

		FString FontPath;
		return Item->TryGetStringField(TEXT("value"), FontPath)
			&& (FontPath.IsEmpty() || LoadObject<UFont>(nullptr, *FontPath) != nullptr)
			&& (!Item->HasField(TEXT("fontPage")) || Item->Values[TEXT("fontPage")]->Type == EJson::Number);
	});

	ValidateNamedArray(TEXT("staticSwitchParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		bool bValue = false;
		return BuildParameterInfo(Item, ParameterInfo) && Item->TryGetBoolField(TEXT("value"), bValue);
	});

	const TSharedPtr<FJsonObject>* LayerStackObject = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("layerStack"), LayerStackObject) || PayloadJson->TryGetObjectField(TEXT("layer_stack"), LayerStackObject))
	{
		TArray<FString> LayerStackErrors;
		FMaterialLayersFunctions ParsedLayers;
		if (!LayerStackObject || !ParseLayerStack(*LayerStackObject, ParsedLayers, LayerStackErrors))
		{
			for (const FString& Error : LayerStackErrors)
			{
				ValidationErrors.Add(Error);
			}
			bSuccess = false;
		}
	}

	Context.SetValidationSummary(
		bSuccess,
		bSuccess ? TEXT("MaterialInstance payload validated.") : TEXT("MaterialInstance payload failed validation."),
		ValidationErrors);

	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, MaterialInstance ? MaterialInstance->GetPathName() : FString());
	}

	return bSuccess;
}

} // namespace MaterialInstanceAuthoringInternal

TSharedPtr<FJsonObject> FMaterialInstanceAuthoring::Create(const FString& AssetPath,
                                                           const FString& ParentMaterialPath,
                                                           const bool bValidateOnly)
{
	using namespace MaterialInstanceAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_material_instance"), AssetPath, TEXT("MaterialInstance"), bValidateOnly);

	UMaterialInterface* ParentMaterial = ResolveParentMaterial(ParentMaterialPath);
	if (!ParentMaterial)
	{
		Context.AddError(TEXT("parent_material_not_found"),
		                 FString::Printf(TEXT("Parent material not found: %s"), *ParentMaterialPath),
		                 ParentMaterialPath);
		return Context.BuildResult(false);
	}

	Context.SetValidationSummary(true, TEXT("MaterialInstance creation inputs validated."));

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create Material Instance")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	UMaterialInstanceConstantFactoryNew* Factory = NewObject<UMaterialInstanceConstantFactoryNew>();
	if (!Factory)
	{
		Context.AddError(TEXT("factory_create_failed"), TEXT("Failed to create MaterialInstanceConstant factory."));
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UObject* CreatedObject = Factory->FactoryCreateNew(
		UMaterialInstanceConstant::StaticClass(),
		Package,
		AssetName,
		RF_Public | RF_Standalone,
		nullptr,
		GWarn);

	UMaterialInstanceConstant* MaterialInstance = Cast<UMaterialInstanceConstant>(CreatedObject);
	if (!MaterialInstance)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create MaterialInstance asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	MaterialInstance->Modify();
	MaterialInstance->SetParentEditorOnly(ParentMaterial, true);
	MaterialInstance->PostEditChange();

	FAssetRegistryModule::AssetCreated(MaterialInstance);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(MaterialInstance);

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("parentMaterial"), ParentMaterial->GetPathName());
	return Result;
}

TSharedPtr<FJsonObject> FMaterialInstanceAuthoring::Modify(UMaterialInstance* MaterialInstance,
                                                           const TSharedPtr<FJsonObject>& PayloadJson,
                                                           const bool bValidateOnly)
{
	using namespace MaterialInstanceAuthoringInternal;

	UMaterialInstanceConstant* ConstantInstance = Cast<UMaterialInstanceConstant>(MaterialInstance);
	const FString AssetPath = MaterialInstance ? MaterialInstance->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_material_instance"), AssetPath, TEXT("MaterialInstance"), bValidateOnly);

	if (!ConstantInstance)
	{
		Context.AddError(TEXT("invalid_material_instance"),
		                 TEXT("MaterialInstance must be a UMaterialInstanceConstant for authoring operations."),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	if (!MaterialInstanceAuthoringInternal::ValidatePayload(ConstantInstance, PayloadJson, Context))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify Material Instance")));
	ConstantInstance->Modify();

	FString ParentMaterialPath;
	if (PayloadJson.IsValid() && PayloadJson->TryGetStringField(TEXT("parentMaterial"), ParentMaterialPath) && !ParentMaterialPath.IsEmpty())
	{
		if (UMaterialInterface* ParentMaterial = MaterialInstanceAuthoringInternal::ResolveParentMaterial(ParentMaterialPath))
		{
			ConstantInstance->SetParentEditorOnly(ParentMaterial, true);
		}
	}

	auto ApplyNamedArray = [&](const TCHAR* FieldName, TFunctionRef<bool(const TSharedPtr<FJsonObject>&)> ApplyFn)
	{
		const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
		if (!PayloadJson.IsValid() || !PayloadJson->TryGetArrayField(FieldName, Items) || !Items)
		{
			return;
		}

		for (const TSharedPtr<FJsonValue>& ItemValue : *Items)
		{
			const TSharedPtr<FJsonObject> Item = ItemValue.IsValid() ? ItemValue->AsObject() : nullptr;
			if (!Item.IsValid() || !ApplyFn(Item))
			{
				Context.AddError(TEXT("apply_error"),
				                 FString::Printf(TEXT("Failed to apply '%s' payload entry."), FieldName),
				                 AssetPath);
			}
		}
	};

	ApplyNamedArray(TEXT("scalarParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		double Value = 0.0;
		if (!BuildParameterInfo(Item, ParameterInfo)
			|| !Item->TryGetNumberField(TEXT("value"), Value))
		{
			return false;
		}

		// UE 5.6/5.7's MaterialEditingLibrary setters do not report success reliably.
		ConstantInstance->SetScalarParameterValueEditorOnly(ParameterInfo, static_cast<float>(Value));
		return true;
	});

	ApplyNamedArray(TEXT("vectorParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		FLinearColor Color;
		const TSharedPtr<FJsonObject>* ColorObject = nullptr;
		if (!BuildParameterInfo(Item, ParameterInfo)
			|| !Item->TryGetObjectField(TEXT("value"), ColorObject)
			|| !ColorObject
			|| !MaterialInstanceAuthoringInternal::ParseColor(*ColorObject, Color))
		{
			return false;
		}

		ConstantInstance->SetVectorParameterValueEditorOnly(ParameterInfo, Color);
		return true;
	});

	ApplyNamedArray(TEXT("textureParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		if (!BuildParameterInfo(Item, ParameterInfo))
		{
			return false;
		}

		if (!Item->HasField(TEXT("value")) || Item->Values[TEXT("value")]->Type == EJson::Null)
		{
			ConstantInstance->SetTextureParameterValueEditorOnly(ParameterInfo, nullptr);
			return true;
		}

		FString TexturePath;
		UTexture* Texture = Item->TryGetStringField(TEXT("value"), TexturePath)
			? LoadObject<UTexture>(nullptr, *TexturePath)
			: nullptr;
		if (!Texture)
		{
			return false;
		}

		ConstantInstance->SetTextureParameterValueEditorOnly(ParameterInfo, Texture);
		return true;
	});

	ApplyNamedArray(TEXT("runtimeVirtualTextureParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		if (!BuildParameterInfo(Item, ParameterInfo))
		{
			return false;
		}

		if (!Item->HasField(TEXT("value")) || Item->Values[TEXT("value")]->Type == EJson::Null)
		{
			ConstantInstance->SetRuntimeVirtualTextureParameterValueEditorOnly(ParameterInfo, nullptr);
			return true;
		}

		FString TexturePath;
		URuntimeVirtualTexture* Texture = Item->TryGetStringField(TEXT("value"), TexturePath)
			? LoadObject<URuntimeVirtualTexture>(nullptr, *TexturePath)
			: nullptr;
		if (!Texture)
		{
			return false;
		}

		ConstantInstance->SetRuntimeVirtualTextureParameterValueEditorOnly(ParameterInfo, Texture);
		return true;
	});

	ApplyNamedArray(TEXT("sparseVolumeTextureParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		if (!BuildParameterInfo(Item, ParameterInfo))
		{
			return false;
		}

		if (!Item->HasField(TEXT("value")) || Item->Values[TEXT("value")]->Type == EJson::Null)
		{
			ConstantInstance->SetSparseVolumeTextureParameterValueEditorOnly(ParameterInfo, nullptr);
			return true;
		}

		FString TexturePath;
		USparseVolumeTexture* Texture = Item->TryGetStringField(TEXT("value"), TexturePath)
			? LoadObject<USparseVolumeTexture>(nullptr, *TexturePath)
			: nullptr;
		if (!Texture)
		{
			return false;
		}

		ConstantInstance->SetSparseVolumeTextureParameterValueEditorOnly(ParameterInfo, Texture);
		return true;
	});

	ApplyNamedArray(TEXT("fontParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		if (!BuildParameterInfo(Item, ParameterInfo))
		{
			return false;
		}

		UFont* Font = nullptr;
		if (Item->HasField(TEXT("value")) && Item->Values[TEXT("value")]->Type != EJson::Null)
		{
			FString FontPath;
			if (!Item->TryGetStringField(TEXT("value"), FontPath))
			{
				return false;
			}
			Font = LoadObject<UFont>(nullptr, *FontPath);
			if (!Font)
			{
				return false;
			}
		}

		int32 FontPage = 0;
		if (Item->HasTypedField<EJson::Number>(TEXT("fontPage")))
		{
			FontPage = static_cast<int32>(Item->GetNumberField(TEXT("fontPage")));
		}

		ConstantInstance->SetFontParameterValueEditorOnly(ParameterInfo, Font, FontPage);
		return true;
	});

	ApplyNamedArray(TEXT("staticSwitchParameters"), [&](const TSharedPtr<FJsonObject>& Item)
	{
		FMaterialParameterInfo ParameterInfo;
		bool bValue = false;
		if (!BuildParameterInfo(Item, ParameterInfo)
			|| !Item->TryGetBoolField(TEXT("value"), bValue))
		{
			return false;
		}

		ConstantInstance->SetStaticSwitchParameterValueEditorOnly(ParameterInfo, bValue);
		return true;
	});

	if (PayloadJson.IsValid())
	{
		const TSharedPtr<FJsonObject>* LayerStackObject = nullptr;
		if (PayloadJson->TryGetObjectField(TEXT("layerStack"), LayerStackObject) || PayloadJson->TryGetObjectField(TEXT("layer_stack"), LayerStackObject))
		{
			TArray<FString> LayerStackErrors;
			FMaterialLayersFunctions ParsedLayers;
			if (!LayerStackObject || !ParseLayerStack(*LayerStackObject, ParsedLayers, LayerStackErrors))
			{
				for (const FString& Error : LayerStackErrors)
				{
					Context.AddError(TEXT("layer_stack_apply_error"), Error, AssetPath);
				}
			}
			else if (!ConstantInstance->SetMaterialLayers(ParsedLayers))
			{
				Context.AddError(TEXT("layer_stack_apply_error"), TEXT("Failed to apply material layer stack."), AssetPath);
			}
		}
	}

	UMaterialEditingLibrary::UpdateMaterialInstance(ConstantInstance);
	ConstantInstance->PostEditChange();
	ConstantInstance->MarkPackageDirty();
	Context.TrackDirtyObject(ConstantInstance);
	return Context.BuildResult(Context.Diagnostics.FilterByPredicate([](const FAssetMutationDiagnostic& Diagnostic)
	{
		return Diagnostic.Severity == TEXT("error");
	}).Num() == 0);
}
