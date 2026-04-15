#include "Extractors/MaterialInstanceExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "Engine/Font.h"
#include "Engine/Texture.h"
#if __has_include("Materials/MaterialParameters.h")
#include "Materials/MaterialParameters.h"
#else
#include "MaterialTypes.h"
#endif
#include "Materials/Material.h"
#include "Materials/MaterialLayersFunctions.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInterface.h"
#include "SparseVolumeTexture/SparseVolumeTexture.h"
#include "VT/RuntimeVirtualTexture.h"

namespace MaterialInstanceExtractorInternal
{

static void SetNullField(TSharedPtr<FJsonObject>& Object, const TCHAR* FieldName)
{
	Object->SetField(FieldName, MakeShared<FJsonValueNull>());
}

static FString AssociationToString(const EMaterialParameterAssociation Association)
{
	switch (Association)
	{
	case EMaterialParameterAssociation::LayerParameter:
		return TEXT("LayerParameter");
	case EMaterialParameterAssociation::BlendParameter:
		return TEXT("BlendParameter");
	default:
		return TEXT("GlobalParameter");
	}
}

static TSharedPtr<FJsonObject> MakeParameterObject(const UMaterialInterface* MaterialInterface, const FMaterialParameterInfo& ParameterInfo)
{
	TSharedPtr<FJsonObject> ParameterObject = MakeShared<FJsonObject>();
	ParameterObject->SetStringField(TEXT("name"), ParameterInfo.Name.ToString());
	ParameterObject->SetStringField(TEXT("association"), AssociationToString(ParameterInfo.Association));
	if (ParameterInfo.Index != INDEX_NONE)
	{
		ParameterObject->SetNumberField(TEXT("index"), ParameterInfo.Index);
	}

#if WITH_EDITOR
	FName GroupName;
	if (MaterialInterface->GetGroupName(FHashedMaterialParameterInfo(ParameterInfo), GroupName) && !GroupName.IsNone())
	{
		ParameterObject->SetStringField(TEXT("group"), GroupName.ToString());
	}
#endif

	return ParameterObject;
}

static TSharedPtr<FJsonObject> SerializeChannelNames(const FParameterChannelNames& ChannelNames)
{
	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetStringField(TEXT("r"), ChannelNames.R.ToString());
	Result->SetStringField(TEXT("g"), ChannelNames.G.ToString());
	Result->SetStringField(TEXT("b"), ChannelNames.B.ToString());
	Result->SetStringField(TEXT("a"), ChannelNames.A.ToString());
	return Result;
}

static void ApplyParameterMetadata(TSharedPtr<FJsonObject>& ParameterObject, const FMaterialParameterMetadata* Metadata)
{
	if (!ParameterObject.IsValid() || !Metadata)
	{
		return;
	}

	if (!Metadata->Description.IsEmpty())
	{
		ParameterObject->SetStringField(TEXT("description"), Metadata->Description);
	}

	if (!Metadata->AssetPath.IsEmpty())
	{
		ParameterObject->SetStringField(TEXT("sourceAssetPath"), Metadata->AssetPath);
	}

	if (!Metadata->Group.IsNone())
	{
		ParameterObject->SetStringField(TEXT("group"), Metadata->Group.ToString());
	}

	if (Metadata->SortPriority != 0)
	{
		ParameterObject->SetNumberField(TEXT("sortPriority"), Metadata->SortPriority);
	}

	if (Metadata->ExpressionGuid.IsValid())
	{
		ParameterObject->SetStringField(TEXT("expressionGuid"), Metadata->ExpressionGuid.ToString(EGuidFormats::DigitsWithHyphensLower));
	}

	if (!Metadata->ChannelNames.R.IsEmptyOrWhitespace()
		|| !Metadata->ChannelNames.G.IsEmptyOrWhitespace()
		|| !Metadata->ChannelNames.B.IsEmptyOrWhitespace()
		|| !Metadata->ChannelNames.A.IsEmptyOrWhitespace())
	{
		ParameterObject->SetObjectField(TEXT("channelNames"), SerializeChannelNames(Metadata->ChannelNames));
	}

	if (Metadata->ScalarMin != 0.0f || Metadata->ScalarMax != 0.0f)
	{
		ParameterObject->SetNumberField(TEXT("scalarMin"), Metadata->ScalarMin);
		ParameterObject->SetNumberField(TEXT("scalarMax"), Metadata->ScalarMax);
	}
}

static TSharedPtr<FJsonObject> SerializeLinearColor(const FLinearColor& Color)
{
	TSharedPtr<FJsonObject> ColorObject = MakeShared<FJsonObject>();
	ColorObject->SetNumberField(TEXT("r"), Color.R);
	ColorObject->SetNumberField(TEXT("g"), Color.G);
	ColorObject->SetNumberField(TEXT("b"), Color.B);
	ColorObject->SetNumberField(TEXT("a"), Color.A);
	return ColorObject;
}

static TSharedPtr<FJsonObject> SerializeLayerStack(const FMaterialLayersFunctions& Layers)
{
	TSharedPtr<FJsonObject> StackObject = MakeShared<FJsonObject>();

	TArray<TSharedPtr<FJsonValue>> LayerEntries;
	for (int32 LayerIndex = 0; LayerIndex < Layers.Layers.Num(); ++LayerIndex)
	{
		TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
		if (Layers.Layers.IsValidIndex(LayerIndex) && Layers.Layers[LayerIndex])
		{
			Entry->SetStringField(TEXT("layerPath"), Layers.Layers[LayerIndex]->GetPathName());
		}
		else
		{
			SetNullField(Entry, TEXT("layerPath"));
		}

		if (Layers.Blends.IsValidIndex(LayerIndex) && Layers.Blends[LayerIndex])
		{
			Entry->SetStringField(TEXT("blendPath"), Layers.Blends[LayerIndex]->GetPathName());
		}
		else
		{
			SetNullField(Entry, TEXT("blendPath"));
		}

		if (Layers.EditorOnly.LayerGuids.IsValidIndex(LayerIndex))
		{
			Entry->SetStringField(TEXT("layerGuid"), Layers.EditorOnly.LayerGuids[LayerIndex].ToString(EGuidFormats::DigitsWithHyphensLower));
		}

		if (Layers.EditorOnly.LayerNames.IsValidIndex(LayerIndex))
		{
			Entry->SetStringField(TEXT("name"), Layers.EditorOnly.LayerNames[LayerIndex].ToString());
		}

		if (Layers.EditorOnly.LayerStates.IsValidIndex(LayerIndex))
		{
			Entry->SetBoolField(TEXT("visible"), Layers.EditorOnly.LayerStates[LayerIndex]);
		}

		LayerEntries.Add(MakeShared<FJsonValueObject>(Entry));
	}

	StackObject->SetArrayField(TEXT("layers"), LayerEntries);
	return StackObject;
}

} // namespace MaterialInstanceExtractorInternal

TSharedPtr<FJsonObject> FMaterialInstanceExtractor::Extract(const UMaterialInstance* MaterialInstance)
{
	if (!MaterialInstance)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> MaterialObject = MakeShared<FJsonObject>();
	MaterialObject->SetStringField(TEXT("assetPath"), MaterialInstance->GetPathName());
	MaterialObject->SetStringField(TEXT("assetName"), MaterialInstance->GetName());

	if (MaterialInstance->Parent)
	{
		MaterialObject->SetStringField(TEXT("parentMaterial"), MaterialInstance->Parent->GetPathName());
	}

	if (const UMaterial* BaseMaterial = MaterialInstance->GetMaterial())
	{
		MaterialObject->SetStringField(TEXT("baseMaterial"), BaseMaterial->GetPathName());
	}

	{
		TArray<FMaterialParameterInfo> ParameterInfos;
		TArray<FGuid> ParameterIds;
		TMap<FMaterialParameterInfo, FMaterialParameterMetadata> MetadataMap;
		MaterialInstance->GetAllScalarParameterInfo(ParameterInfos, ParameterIds);
		MaterialInstance->GetAllParametersOfType(EMaterialParameterType::Scalar, MetadataMap);

		TArray<TSharedPtr<FJsonValue>> Parameters;
		for (const FMaterialParameterInfo& ParameterInfo : ParameterInfos)
		{
			float Value = 0.0f;
			if (!MaterialInstance->GetScalarParameterValue(FHashedMaterialParameterInfo(ParameterInfo), Value))
			{
				continue;
			}

			TSharedPtr<FJsonObject> ParameterObject = MaterialInstanceExtractorInternal::MakeParameterObject(MaterialInstance, ParameterInfo);
			MaterialInstanceExtractorInternal::ApplyParameterMetadata(ParameterObject, MetadataMap.Find(ParameterInfo));
			ParameterObject->SetNumberField(TEXT("value"), Value);

			float OverrideValue = 0.0f;
			ParameterObject->SetBoolField(TEXT("isOverridden"), MaterialInstance->GetScalarParameterValue(FHashedMaterialParameterInfo(ParameterInfo), OverrideValue, true));
			Parameters.Add(MakeShared<FJsonValueObject>(ParameterObject));
		}
		MaterialObject->SetArrayField(TEXT("scalarParameters"), Parameters);
	}

	{
		TArray<FMaterialParameterInfo> ParameterInfos;
		TArray<FGuid> ParameterIds;
		TMap<FMaterialParameterInfo, FMaterialParameterMetadata> MetadataMap;
		MaterialInstance->GetAllVectorParameterInfo(ParameterInfos, ParameterIds);
		MaterialInstance->GetAllParametersOfType(EMaterialParameterType::Vector, MetadataMap);

		TArray<TSharedPtr<FJsonValue>> Parameters;
		for (const FMaterialParameterInfo& ParameterInfo : ParameterInfos)
		{
			FLinearColor Value = FLinearColor::Black;
			if (!MaterialInstance->GetVectorParameterValue(FHashedMaterialParameterInfo(ParameterInfo), Value))
			{
				continue;
			}

			TSharedPtr<FJsonObject> ParameterObject = MaterialInstanceExtractorInternal::MakeParameterObject(MaterialInstance, ParameterInfo);
			MaterialInstanceExtractorInternal::ApplyParameterMetadata(ParameterObject, MetadataMap.Find(ParameterInfo));
			ParameterObject->SetObjectField(TEXT("value"), MaterialInstanceExtractorInternal::SerializeLinearColor(Value));

			FLinearColor OverrideValue = FLinearColor::Black;
			ParameterObject->SetBoolField(TEXT("isOverridden"), MaterialInstance->GetVectorParameterValue(FHashedMaterialParameterInfo(ParameterInfo), OverrideValue, true));
			Parameters.Add(MakeShared<FJsonValueObject>(ParameterObject));
		}
		MaterialObject->SetArrayField(TEXT("vectorParameters"), Parameters);
	}

	{
		TArray<FMaterialParameterInfo> ParameterInfos;
		TArray<FGuid> ParameterIds;
		TMap<FMaterialParameterInfo, FMaterialParameterMetadata> MetadataMap;
		MaterialInstance->GetAllTextureParameterInfo(ParameterInfos, ParameterIds);
		MaterialInstance->GetAllParametersOfType(EMaterialParameterType::Texture, MetadataMap);

		TArray<TSharedPtr<FJsonValue>> Parameters;
		for (const FMaterialParameterInfo& ParameterInfo : ParameterInfos)
		{
			UTexture* Value = nullptr;
			if (!MaterialInstance->GetTextureParameterValue(FHashedMaterialParameterInfo(ParameterInfo), Value))
			{
				continue;
			}

			TSharedPtr<FJsonObject> ParameterObject = MaterialInstanceExtractorInternal::MakeParameterObject(MaterialInstance, ParameterInfo);
			MaterialInstanceExtractorInternal::ApplyParameterMetadata(ParameterObject, MetadataMap.Find(ParameterInfo));
			if (Value)
			{
				ParameterObject->SetStringField(TEXT("value"), Value->GetPathName());
			}
			else
			{
				ParameterObject->SetField(TEXT("value"), MakeShared<FJsonValueNull>());
			}

			UTexture* OverrideValue = nullptr;
			ParameterObject->SetBoolField(TEXT("isOverridden"), MaterialInstance->GetTextureParameterValue(FHashedMaterialParameterInfo(ParameterInfo), OverrideValue, true));
			Parameters.Add(MakeShared<FJsonValueObject>(ParameterObject));
		}
		MaterialObject->SetArrayField(TEXT("textureParameters"), Parameters);
	}

	{
		TArray<FMaterialParameterInfo> ParameterInfos;
		TArray<FGuid> ParameterIds;
		TMap<FMaterialParameterInfo, FMaterialParameterMetadata> MetadataMap;
		MaterialInstance->GetAllRuntimeVirtualTextureParameterInfo(ParameterInfos, ParameterIds);
		MaterialInstance->GetAllParametersOfType(EMaterialParameterType::RuntimeVirtualTexture, MetadataMap);

		TArray<TSharedPtr<FJsonValue>> Parameters;
		for (const FMaterialParameterInfo& ParameterInfo : ParameterInfos)
		{
			URuntimeVirtualTexture* Value = nullptr;
			if (!MaterialInstance->GetRuntimeVirtualTextureParameterValue(FHashedMaterialParameterInfo(ParameterInfo), Value))
			{
				continue;
			}

			TSharedPtr<FJsonObject> ParameterObject = MaterialInstanceExtractorInternal::MakeParameterObject(MaterialInstance, ParameterInfo);
			MaterialInstanceExtractorInternal::ApplyParameterMetadata(ParameterObject, MetadataMap.Find(ParameterInfo));
			if (Value)
			{
				ParameterObject->SetStringField(TEXT("value"), Value->GetPathName());
			}
			else
			{
				ParameterObject->SetField(TEXT("value"), MakeShared<FJsonValueNull>());
			}
			URuntimeVirtualTexture* OverrideValue = nullptr;
			ParameterObject->SetBoolField(TEXT("isOverridden"), MaterialInstance->GetRuntimeVirtualTextureParameterValue(FHashedMaterialParameterInfo(ParameterInfo), OverrideValue, true));
			Parameters.Add(MakeShared<FJsonValueObject>(ParameterObject));
		}
		MaterialObject->SetArrayField(TEXT("runtimeVirtualTextureParameters"), Parameters);
	}

	{
		TArray<FMaterialParameterInfo> ParameterInfos;
		TArray<FGuid> ParameterIds;
		TMap<FMaterialParameterInfo, FMaterialParameterMetadata> MetadataMap;
		MaterialInstance->GetAllSparseVolumeTextureParameterInfo(ParameterInfos, ParameterIds);
		MaterialInstance->GetAllParametersOfType(EMaterialParameterType::SparseVolumeTexture, MetadataMap);

		TArray<TSharedPtr<FJsonValue>> Parameters;
		for (const FMaterialParameterInfo& ParameterInfo : ParameterInfos)
		{
			USparseVolumeTexture* Value = nullptr;
			if (!MaterialInstance->GetSparseVolumeTextureParameterValue(FHashedMaterialParameterInfo(ParameterInfo), Value))
			{
				continue;
			}

			TSharedPtr<FJsonObject> ParameterObject = MaterialInstanceExtractorInternal::MakeParameterObject(MaterialInstance, ParameterInfo);
			MaterialInstanceExtractorInternal::ApplyParameterMetadata(ParameterObject, MetadataMap.Find(ParameterInfo));
			if (Value)
			{
				ParameterObject->SetStringField(TEXT("value"), Value->GetPathName());
			}
			else
			{
				ParameterObject->SetField(TEXT("value"), MakeShared<FJsonValueNull>());
			}

			USparseVolumeTexture* OverrideValue = nullptr;
			ParameterObject->SetBoolField(TEXT("isOverridden"), MaterialInstance->GetSparseVolumeTextureParameterValue(FHashedMaterialParameterInfo(ParameterInfo), OverrideValue, true));
			Parameters.Add(MakeShared<FJsonValueObject>(ParameterObject));
		}
		MaterialObject->SetArrayField(TEXT("sparseVolumeTextureParameters"), Parameters);
	}

	{
		TArray<FMaterialParameterInfo> ParameterInfos;
		TArray<FGuid> ParameterIds;
		TMap<FMaterialParameterInfo, FMaterialParameterMetadata> MetadataMap;
		MaterialInstance->GetAllFontParameterInfo(ParameterInfos, ParameterIds);
		MaterialInstance->GetAllParametersOfType(EMaterialParameterType::Font, MetadataMap);

		TArray<TSharedPtr<FJsonValue>> Parameters;
		for (const FMaterialParameterInfo& ParameterInfo : ParameterInfos)
		{
			UFont* FontValue = nullptr;
			int32 FontPage = 0;
			if (!MaterialInstance->GetFontParameterValue(FHashedMaterialParameterInfo(ParameterInfo), FontValue, FontPage))
			{
				continue;
			}

			TSharedPtr<FJsonObject> ParameterObject = MaterialInstanceExtractorInternal::MakeParameterObject(MaterialInstance, ParameterInfo);
			MaterialInstanceExtractorInternal::ApplyParameterMetadata(ParameterObject, MetadataMap.Find(ParameterInfo));
			if (FontValue)
			{
				ParameterObject->SetStringField(TEXT("value"), FontValue->GetPathName());
			}
			else
			{
				ParameterObject->SetField(TEXT("value"), MakeShared<FJsonValueNull>());
			}
			ParameterObject->SetNumberField(TEXT("fontPage"), FontPage);
			UFont* OverrideFontValue = nullptr;
			int32 OverrideFontPage = 0;
			ParameterObject->SetBoolField(TEXT("isOverridden"), MaterialInstance->GetFontParameterValue(FHashedMaterialParameterInfo(ParameterInfo), OverrideFontValue, OverrideFontPage, true));
			Parameters.Add(MakeShared<FJsonValueObject>(ParameterObject));
		}
		MaterialObject->SetArrayField(TEXT("fontParameters"), Parameters);
	}

#if WITH_EDITORONLY_DATA
	{
		TArray<FMaterialParameterInfo> ParameterInfos;
		TArray<FGuid> ParameterIds;
		TMap<FMaterialParameterInfo, FMaterialParameterMetadata> MetadataMap;
		MaterialInstance->GetAllStaticSwitchParameterInfo(ParameterInfos, ParameterIds);
		MaterialInstance->GetAllParametersOfType(EMaterialParameterType::StaticSwitch, MetadataMap);

		TArray<TSharedPtr<FJsonValue>> Parameters;
		for (const FMaterialParameterInfo& ParameterInfo : ParameterInfos)
		{
			bool Value = false;
			FGuid ExpressionGuid;
			if (!MaterialInstance->GetStaticSwitchParameterValue(FHashedMaterialParameterInfo(ParameterInfo), Value, ExpressionGuid))
			{
				continue;
			}

			TSharedPtr<FJsonObject> ParameterObject = MaterialInstanceExtractorInternal::MakeParameterObject(MaterialInstance, ParameterInfo);
			MaterialInstanceExtractorInternal::ApplyParameterMetadata(ParameterObject, MetadataMap.Find(ParameterInfo));
			ParameterObject->SetBoolField(TEXT("value"), Value);

			bool OverrideValue = false;
			FGuid OverrideGuid;
			ParameterObject->SetBoolField(TEXT("isOverridden"), MaterialInstance->GetStaticSwitchParameterValue(FHashedMaterialParameterInfo(ParameterInfo), OverrideValue, OverrideGuid, true));
			if (ExpressionGuid.IsValid())
			{
				ParameterObject->SetStringField(TEXT("expressionGuid"), ExpressionGuid.ToString());
			}
			Parameters.Add(MakeShared<FJsonValueObject>(ParameterObject));
		}
		MaterialObject->SetArrayField(TEXT("staticSwitchParameters"), Parameters);
	}
#else
	MaterialObject->SetArrayField(TEXT("staticSwitchParameters"), TArray<TSharedPtr<FJsonValue>>());
#endif

	{
		FMaterialLayersFunctions LayerStack;
		if (MaterialInstance->GetMaterialLayers(LayerStack))
		{
			MaterialObject->SetObjectField(TEXT("layerStack"), MaterialInstanceExtractorInternal::SerializeLayerStack(LayerStack));
		}

		FMaterialLayersFunctions ParentLayerStack;
		if (MaterialInstance->Parent && MaterialInstance->Parent->GetMaterialLayers(ParentLayerStack))
		{
			MaterialObject->SetObjectField(TEXT("parentLayerStack"), MaterialInstanceExtractorInternal::SerializeLayerStack(ParentLayerStack));
		}
	}

	Root->SetObjectField(TEXT("materialInstance"), MaterialObject);
	return Root;
}
