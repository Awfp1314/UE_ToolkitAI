#include "Extractors/MaterialGraphExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "PropertySerializer.h"

#include "MaterialEditingLibrary.h"
#include "MaterialValueType.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpression.h"
#include "Materials/MaterialExpressionComment.h"
#include "Materials/MaterialExpressionFunctionInput.h"
#include "Materials/MaterialExpressionFunctionOutput.h"
#include "Materials/MaterialExpressionMaterialAttributeLayers.h"
#include "Materials/MaterialFunction.h"
#include "Materials/MaterialFunctionMaterialLayer.h"
#include "Materials/MaterialFunctionMaterialLayerBlend.h"
#include "Materials/MaterialLayersFunctions.h"

namespace MaterialGraphExtractorInternal
{

static FString EnumValueToString(const UEnum* Enum, const int64 Value)
{
	return Enum ? Enum->GetNameStringByValue(Value) : FString::FromInt(Value);
}

static FString MaterialValueTypeToString(const EMaterialValueType ValueType)
{
	switch (ValueType)
	{
	case MCT_Float1: return TEXT("Float1");
	case MCT_Float2: return TEXT("Float2");
	case MCT_Float3: return TEXT("Float3");
	case MCT_Float4: return TEXT("Float4");
	case MCT_Texture2D: return TEXT("Texture2D");
	case MCT_TextureCube: return TEXT("TextureCube");
	case MCT_Texture2DArray: return TEXT("Texture2DArray");
	case MCT_TextureCubeArray: return TEXT("TextureCubeArray");
	case MCT_VolumeTexture: return TEXT("VolumeTexture");
	case MCT_StaticBool: return TEXT("StaticBool");
	case MCT_Unknown: return TEXT("Unknown");
	case MCT_MaterialAttributes: return TEXT("MaterialAttributes");
	case MCT_TextureExternal: return TEXT("TextureExternal");
	case MCT_TextureVirtual: return TEXT("TextureVirtual");
	case MCT_SparseVolumeTexture: return TEXT("SparseVolumeTexture");
	case MCT_VTPageTableResult: return TEXT("VTPageTableResult");
	case MCT_ShadingModel: return TEXT("ShadingModel");
	case MCT_Substrate: return TEXT("Substrate");
	case MCT_LWCScalar: return TEXT("LWCScalar");
	case MCT_LWCVector2: return TEXT("LWCVector2");
	case MCT_LWCVector3: return TEXT("LWCVector3");
	case MCT_LWCVector4: return TEXT("LWCVector4");
	case MCT_Execution: return TEXT("Execution");
	case MCT_VoidStatement: return TEXT("VoidStatement");
	case MCT_Bool: return TEXT("Bool");
	case MCT_UInt1: return TEXT("UInt1");
	case MCT_UInt2: return TEXT("UInt2");
	case MCT_UInt3: return TEXT("UInt3");
	case MCT_UInt4: return TEXT("UInt4");
	case MCT_TextureCollection: return TEXT("TextureCollection");
	case MCT_TextureMeshPaint: return TEXT("TextureMeshPaint");
	case MCT_TextureMaterialCache: return TEXT("TextureMaterialCache");
	default:
		return FString::Printf(TEXT("0x%llx"), static_cast<unsigned long long>(ValueType));
	}
}

static void SetNullField(const TSharedPtr<FJsonObject>& Object, const TCHAR* FieldName)
{
	Object->SetField(FieldName, MakeShared<FJsonValueNull>());
}

static FString ShadingModelToString(const EMaterialShadingModel ShadingModel)
{
	const UEnum* ShadingModelEnum = StaticEnum<EMaterialShadingModel>();
	if (!ShadingModelEnum)
	{
		return FString::FromInt(static_cast<int32>(ShadingModel));
	}

	FString Name = ShadingModelEnum->GetNameStringByValue(static_cast<int64>(ShadingModel));
	Name.RemoveFromStart(TEXT("MSM_"));
	return Name.IsEmpty() ? FString::FromInt(static_cast<int32>(ShadingModel)) : Name;
}

static FString ShadingModelFieldToString(const FMaterialShadingModelField& ShadingModels)
{
	const UEnum* ShadingModelEnum = StaticEnum<EMaterialShadingModel>();
	if (!ShadingModelEnum)
	{
		return FString();
	}

	TArray<FString> Names;
	for (int32 EnumIndex = 0; EnumIndex < ShadingModelEnum->NumEnums() - 1; ++EnumIndex)
	{
		const int64 EnumValue = ShadingModelEnum->GetValueByIndex(EnumIndex);
		if (EnumValue < 0)
		{
			continue;
		}

		const EMaterialShadingModel ShadingModel = static_cast<EMaterialShadingModel>(EnumValue);
		if (ShadingModels.HasShadingModel(ShadingModel))
		{
			Names.Add(ShadingModelToString(ShadingModel));
		}
	}

	return FString::Join(Names, TEXT("|"));
}

static TSharedPtr<FJsonObject> SerializeLinearColor(const FLinearColor& Color)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetNumberField(TEXT("r"), Color.R);
	Result->SetNumberField(TEXT("g"), Color.G);
	Result->SetNumberField(TEXT("b"), Color.B);
	Result->SetNumberField(TEXT("a"), Color.A);
	return Result;
}

static TSharedPtr<FJsonObject> SerializeMaterialStatistics(const FMaterialStatistics& Stats)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetNumberField(TEXT("numVertexShaderInstructions"), Stats.NumVertexShaderInstructions);
	Result->SetNumberField(TEXT("numPixelShaderInstructions"), Stats.NumPixelShaderInstructions);
	Result->SetNumberField(TEXT("numSamplers"), Stats.NumSamplers);
	Result->SetNumberField(TEXT("numVertexTextureSamples"), Stats.NumVertexTextureSamples);
	Result->SetNumberField(TEXT("numPixelTextureSamples"), Stats.NumPixelTextureSamples);
	Result->SetNumberField(TEXT("numVirtualTextureSamples"), Stats.NumVirtualTextureSamples);
	Result->SetNumberField(TEXT("numUVScalars"), Stats.NumUVScalars);
	Result->SetNumberField(TEXT("numInterpolatorScalars"), Stats.NumInterpolatorScalars);
	return Result;
}

static TSharedPtr<FJsonObject> SerializeLayerStack(const FMaterialLayersFunctions& Layers, const FString& OwnerExpressionGuid = FString())
{
	const TSharedPtr<FJsonObject> StackObject = MakeShared<FJsonObject>();
	if (!OwnerExpressionGuid.IsEmpty())
	{
		StackObject->SetStringField(TEXT("expressionGuid"), OwnerExpressionGuid);
	}

	TArray<TSharedPtr<FJsonValue>> LayerEntries;
	const int32 LayerCount = Layers.Layers.Num();
	for (int32 LayerIndex = 0; LayerIndex < LayerCount; ++LayerIndex)
	{
		const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
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

		if (Layers.EditorOnly.RestrictToLayerRelatives.IsValidIndex(LayerIndex))
		{
			Entry->SetBoolField(TEXT("restrictToLayerRelatives"), Layers.EditorOnly.RestrictToLayerRelatives[LayerIndex]);
		}

		if (Layers.EditorOnly.RestrictToBlendRelatives.IsValidIndex(LayerIndex))
		{
			Entry->SetBoolField(TEXT("restrictToBlendRelatives"), Layers.EditorOnly.RestrictToBlendRelatives[LayerIndex]);
		}

		if (Layers.EditorOnly.LayerLinkStates.IsValidIndex(LayerIndex))
		{
			const UEnum* LinkStateEnum = StaticEnum<EMaterialLayerLinkState>();
			Entry->SetStringField(TEXT("linkState"), EnumValueToString(LinkStateEnum, static_cast<int64>(Layers.EditorOnly.LayerLinkStates[LayerIndex])));
		}

		LayerEntries.Add(MakeShared<FJsonValueObject>(Entry));
	}

	TArray<TSharedPtr<FJsonValue>> DeletedParentLayerGuids;
	for (const FGuid& Guid : Layers.EditorOnly.DeletedParentLayerGuids)
	{
		DeletedParentLayerGuids.Add(MakeShared<FJsonValueString>(Guid.ToString(EGuidFormats::DigitsWithHyphensLower)));
	}

	StackObject->SetArrayField(TEXT("layers"), LayerEntries);
	StackObject->SetArrayField(TEXT("deletedParentLayerGuids"), DeletedParentLayerGuids);
	return StackObject;
}

static TSharedPtr<FJsonObject> SerializeExpressionProperties(const UMaterialExpression* Expression)
{
	TSharedPtr<FJsonObject> Properties = FPropertySerializer::SerializePropertyOverrides(Expression);
	if (!Properties.IsValid())
	{
		Properties = MakeShared<FJsonObject>();
	}

	Properties->RemoveField(TEXT("MaterialExpressionEditorX"));
	Properties->RemoveField(TEXT("MaterialExpressionEditorY"));
	Properties->RemoveField(TEXT("MaterialExpressionGuid"));
	Properties->RemoveField(TEXT("Material"));
	Properties->RemoveField(TEXT("Function"));
	Properties->RemoveField(TEXT("GraphNode"));
	Properties->RemoveField(TEXT("SubgraphExpression"));
	Properties->RemoveField(TEXT("EditorComments"));
	Properties->RemoveField(TEXT("DefaultLayers"));
	return Properties;
}

static TArray<TSharedPtr<FJsonValue>> SerializeExpressionInputs(const UMaterialExpression* Expression)
{
	TArray<TSharedPtr<FJsonValue>> Inputs;
	if (!Expression)
	{
		return Inputs;
	}

	for (int32 InputIndex = 0; InputIndex < Expression->CountInputs(); ++InputIndex)
	{
		const FExpressionInput* Input = Expression->GetInput(InputIndex);
		if (!Input)
		{
			continue;
		}

		const TSharedPtr<FJsonObject> InputObject = MakeShared<FJsonObject>();
		InputObject->SetNumberField(TEXT("inputIndex"), InputIndex);
		InputObject->SetStringField(TEXT("name"), Expression->GetInputName(InputIndex).ToString());
		InputObject->SetStringField(
			TEXT("valueType"),
			MaterialValueTypeToString(const_cast<UMaterialExpression*>(Expression)->GetInputValueType(InputIndex)));
		InputObject->SetBoolField(TEXT("required"), Expression->IsInputConnectionRequired(InputIndex));
		InputObject->SetBoolField(TEXT("connected"), Input->Expression != nullptr);

		if (Input->Expression)
		{
			InputObject->SetStringField(TEXT("expressionGuid"), Input->Expression->MaterialExpressionGuid.ToString(EGuidFormats::DigitsWithHyphensLower));
			InputObject->SetNumberField(TEXT("outputIndex"), Input->OutputIndex);
			if (const FExpressionOutput* Output = Input->Expression->GetOutput(Input->OutputIndex))
			{
				InputObject->SetStringField(TEXT("outputName"), Output->OutputName.ToString());
			}
		}

		Inputs.Add(MakeShared<FJsonValueObject>(InputObject));
	}

	return Inputs;
}

static TArray<TSharedPtr<FJsonValue>> SerializeExpressionOutputs(UMaterialExpression* Expression)
{
	TArray<TSharedPtr<FJsonValue>> Outputs;
	if (!Expression)
	{
		return Outputs;
	}

	TArray<FExpressionOutput>& ExpressionOutputs = Expression->GetOutputs();
	for (int32 OutputIndex = 0; OutputIndex < ExpressionOutputs.Num(); ++OutputIndex)
	{
		const FExpressionOutput& Output = ExpressionOutputs[OutputIndex];
		const TSharedPtr<FJsonObject> OutputObject = MakeShared<FJsonObject>();
		OutputObject->SetNumberField(TEXT("outputIndex"), OutputIndex);
		if (!Output.OutputName.IsNone())
		{
			OutputObject->SetStringField(TEXT("name"), Output.OutputName.ToString());
		}
		OutputObject->SetStringField(TEXT("valueType"), MaterialValueTypeToString(Expression->GetOutputValueType(OutputIndex)));
		Outputs.Add(MakeShared<FJsonValueObject>(OutputObject));
	}

	return Outputs;
}

static TSharedPtr<FJsonObject> SerializeExpression(UMaterialExpression* Expression)
{
	if (!Expression)
	{
		return nullptr;
	}

	const TSharedPtr<FJsonObject> ExpressionObject = MakeShared<FJsonObject>();
	ExpressionObject->SetStringField(TEXT("class"), Expression->GetClass()->GetPathName());
	ExpressionObject->SetStringField(TEXT("assetClass"), Expression->GetClass()->GetName());
	ExpressionObject->SetStringField(TEXT("expressionGuid"), Expression->MaterialExpressionGuid.ToString(EGuidFormats::DigitsWithHyphensLower));
	ExpressionObject->SetStringField(TEXT("name"), Expression->GetName());
	ExpressionObject->SetNumberField(TEXT("editorX"), Expression->MaterialExpressionEditorX);
	ExpressionObject->SetNumberField(TEXT("editorY"), Expression->MaterialExpressionEditorY);
	ExpressionObject->SetObjectField(TEXT("properties"), SerializeExpressionProperties(Expression));
	ExpressionObject->SetArrayField(TEXT("inputs"), SerializeExpressionInputs(Expression));
	ExpressionObject->SetArrayField(TEXT("outputs"), SerializeExpressionOutputs(Expression));

	if (const UMaterialExpressionMaterialAttributeLayers* LayerExpression = Cast<UMaterialExpressionMaterialAttributeLayers>(Expression))
	{
		ExpressionObject->SetObjectField(
			TEXT("layerStack"),
			SerializeLayerStack(LayerExpression->DefaultLayers, Expression->MaterialExpressionGuid.ToString(EGuidFormats::DigitsWithHyphensLower)));
	}

	return ExpressionObject;
}

static TSharedPtr<FJsonObject> SerializeComment(UMaterialExpressionComment* Comment)
{
	return SerializeExpression(Comment);
}

static TArray<TSharedPtr<FJsonValue>> SerializeMaterialPropertyConnections(UMaterial* Material)
{
	TArray<TSharedPtr<FJsonValue>> Connections;
	if (!Material)
	{
		return Connections;
	}

	const UEnum* PropertyEnum = StaticEnum<EMaterialProperty>();
	if (!PropertyEnum)
	{
		return Connections;
	}

	for (int32 EnumIndex = 0; EnumIndex < PropertyEnum->NumEnums() - 1; ++EnumIndex)
	{
		const int64 EnumValue = PropertyEnum->GetValueByIndex(EnumIndex);
		if (EnumValue < 0)
		{
			continue;
		}

		FExpressionInput* Input = Material->GetExpressionInputForProperty(static_cast<EMaterialProperty>(EnumValue));
		if (!Input || !Input->Expression)
		{
			continue;
		}

		const TSharedPtr<FJsonObject> Connection = MakeShared<FJsonObject>();
		Connection->SetStringField(TEXT("property"), PropertyEnum->GetNameStringByValue(EnumValue));
		Connection->SetStringField(TEXT("expressionGuid"), Input->Expression->MaterialExpressionGuid.ToString(EGuidFormats::DigitsWithHyphensLower));
		Connection->SetNumberField(TEXT("outputIndex"), Input->OutputIndex);
		if (const FExpressionOutput* Output = Input->Expression->GetOutput(Input->OutputIndex))
		{
			Connection->SetStringField(TEXT("outputName"), Output->OutputName.ToString());
		}
		Connections.Add(MakeShared<FJsonValueObject>(Connection));
	}

	return Connections;
}

static TArray<TSharedPtr<FJsonValue>> SerializeParameterGroupData(const UMaterial* Material)
{
	TArray<TSharedPtr<FJsonValue>> Groups;
	if (!Material || !Material->GetEditorOnlyData())
	{
		return Groups;
	}

	for (const FParameterGroupData& GroupData : Material->GetEditorOnlyData()->ParameterGroupData)
	{
		const TSharedPtr<FJsonObject> GroupObject = MakeShared<FJsonObject>();
		GroupObject->SetStringField(TEXT("groupName"), GroupData.GroupName);
		GroupObject->SetNumberField(TEXT("sortPriority"), GroupData.GroupSortPriority);
		Groups.Add(MakeShared<FJsonValueObject>(GroupObject));
	}

	return Groups;
}

static FString GetMaterialFunctionKind(const UMaterialFunctionInterface* MaterialFunction)
{
	if (MaterialFunction && MaterialFunction->IsA<UMaterialFunctionMaterialLayerBlend>())
	{
		return TEXT("layer_blend");
	}
	if (MaterialFunction && MaterialFunction->IsA<UMaterialFunctionMaterialLayer>())
	{
		return TEXT("layer");
	}
	return TEXT("function");
}

static TArray<TSharedPtr<FJsonValue>> SerializeFunctionEndpoints(UMaterialFunction* MaterialFunction, UClass* EndpointClass)
{
	TArray<TSharedPtr<FJsonValue>> Endpoints;
	if (!MaterialFunction)
	{
		return Endpoints;
	}

	for (UMaterialExpression* Expression : MaterialFunction->GetExpressions())
	{
		if (!Expression || !Expression->IsA(EndpointClass))
		{
			continue;
		}

		Endpoints.Add(MakeShared<FJsonValueObject>(SerializeExpression(Expression)));
	}

	return Endpoints;
}

} // namespace MaterialGraphExtractorInternal

TSharedPtr<FJsonObject> FMaterialGraphExtractor::ExtractMaterial(const UMaterial* Material, const bool bVerbose)
{
	using namespace MaterialGraphExtractorInternal;

	if (!Material)
	{
		return nullptr;
	}

	const TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	const TSharedPtr<FJsonObject> MaterialObject = MakeShared<FJsonObject>();
	MaterialObject->SetStringField(TEXT("assetPath"), Material->GetPathName());
	MaterialObject->SetStringField(TEXT("assetName"), Material->GetName());
	MaterialObject->SetStringField(TEXT("assetClass"), Material->GetClass()->GetName());
	MaterialObject->SetStringField(TEXT("materialDomain"), EnumValueToString(StaticEnum<EMaterialDomain>(), Material->MaterialDomain.GetValue()));
	MaterialObject->SetStringField(TEXT("blendMode"), EnumValueToString(StaticEnum<EBlendMode>(), Material->BlendMode.GetValue()));
	const FMaterialShadingModelField ShadingModels = Material->GetShadingModels();
	MaterialObject->SetStringField(TEXT("shadingModel"), ShadingModelToString(ShadingModels.GetFirstShadingModel()));
	MaterialObject->SetStringField(TEXT("usedShadingModels"), ShadingModelFieldToString(ShadingModels));
	MaterialObject->SetBoolField(TEXT("twoSided"), Material->TwoSided);
	MaterialObject->SetBoolField(TEXT("fullyRough"), Material->bFullyRough);
	MaterialObject->SetBoolField(TEXT("useMaterialAttributes"), Material->bUseMaterialAttributes);
	MaterialObject->SetNumberField(TEXT("opacityMaskClipValue"), Material->OpacityMaskClipValue);
	MaterialObject->SetArrayField(TEXT("propertyConnections"), SerializeMaterialPropertyConnections(const_cast<UMaterial*>(Material)));
	MaterialObject->SetArrayField(TEXT("parameterGroups"), SerializeParameterGroupData(Material));
	MaterialObject->SetObjectField(TEXT("statistics"), SerializeMaterialStatistics(UMaterialEditingLibrary::GetStatistics(const_cast<UMaterial*>(Material))));

	TArray<TSharedPtr<FJsonValue>> Expressions;
	TArray<TSharedPtr<FJsonValue>> LayerStacks;
	for (UMaterialExpression* Expression : Material->GetExpressions())
	{
		if (!Expression)
		{
			continue;
		}

		Expressions.Add(MakeShared<FJsonValueObject>(SerializeExpression(Expression)));
		if (const UMaterialExpressionMaterialAttributeLayers* LayersExpression = Cast<UMaterialExpressionMaterialAttributeLayers>(Expression))
		{
			LayerStacks.Add(MakeShared<FJsonValueObject>(
				SerializeLayerStack(LayersExpression->DefaultLayers, Expression->MaterialExpressionGuid.ToString(EGuidFormats::DigitsWithHyphensLower))));
		}
	}

	TArray<TSharedPtr<FJsonValue>> Comments;
	for (UMaterialExpressionComment* Comment : Material->GetEditorComments())
	{
		if (Comment)
		{
			Comments.Add(MakeShared<FJsonValueObject>(SerializeComment(Comment)));
		}
	}

	MaterialObject->SetArrayField(TEXT("expressions"), Expressions);
	MaterialObject->SetArrayField(TEXT("comments"), Comments);
	MaterialObject->SetArrayField(TEXT("layerStacks"), LayerStacks);
	MaterialObject->SetBoolField(TEXT("verbose"), bVerbose);

	Root->SetObjectField(TEXT("material"), MaterialObject);
	return Root;
}

TSharedPtr<FJsonObject> FMaterialGraphExtractor::ExtractMaterialFunction(const UMaterialFunctionInterface* MaterialFunctionInterface, const bool bVerbose)
{
	using namespace MaterialGraphExtractorInternal;

	const UMaterialFunction* MaterialFunction = Cast<UMaterialFunction>(MaterialFunctionInterface);
	if (!MaterialFunction)
	{
		return nullptr;
	}

	const TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	const TSharedPtr<FJsonObject> FunctionObject = MakeShared<FJsonObject>();
	FunctionObject->SetStringField(TEXT("assetPath"), MaterialFunction->GetPathName());
	FunctionObject->SetStringField(TEXT("assetName"), MaterialFunction->GetName());
	FunctionObject->SetStringField(TEXT("assetClass"), MaterialFunction->GetClass()->GetName());
	FunctionObject->SetStringField(TEXT("assetKind"), GetMaterialFunctionKind(MaterialFunction));
	FunctionObject->SetStringField(TEXT("description"), MaterialFunction->Description);
	FunctionObject->SetStringField(TEXT("userExposedCaption"), MaterialFunction->UserExposedCaption);
	FunctionObject->SetBoolField(TEXT("exposeToLibrary"), MaterialFunction->bExposeToLibrary);
	FunctionObject->SetStringField(TEXT("previewBlendMode"), EnumValueToString(StaticEnum<EBlendMode>(), MaterialFunction->PreviewBlendMode.GetValue()));
	FunctionObject->SetStringField(TEXT("previewMaterialDomain"), EnumValueToString(StaticEnum<EMaterialDomain>(), MaterialFunction->PreviewMaterialDomain.GetValue()));

	TArray<TSharedPtr<FJsonValue>> LibraryCategories;
	for (const FText& Category : MaterialFunction->LibraryCategoriesText)
	{
		LibraryCategories.Add(MakeShared<FJsonValueString>(Category.ToString()));
	}
	FunctionObject->SetArrayField(TEXT("libraryCategories"), LibraryCategories);

	TArray<TSharedPtr<FJsonValue>> Expressions;
	for (UMaterialExpression* Expression : MaterialFunction->GetExpressions())
	{
		if (Expression)
		{
			Expressions.Add(MakeShared<FJsonValueObject>(SerializeExpression(Expression)));
		}
	}

	TArray<TSharedPtr<FJsonValue>> Comments;
	for (UMaterialExpressionComment* Comment : MaterialFunction->GetEditorComments())
	{
		if (Comment)
		{
			Comments.Add(MakeShared<FJsonValueObject>(SerializeComment(Comment)));
		}
	}

	FunctionObject->SetArrayField(TEXT("expressions"), Expressions);
	FunctionObject->SetArrayField(TEXT("comments"), Comments);
	FunctionObject->SetArrayField(TEXT("functionInputs"), SerializeFunctionEndpoints(const_cast<UMaterialFunction*>(MaterialFunction), UMaterialExpressionFunctionInput::StaticClass()));
	FunctionObject->SetArrayField(TEXT("functionOutputs"), SerializeFunctionEndpoints(const_cast<UMaterialFunction*>(MaterialFunction), UMaterialExpressionFunctionOutput::StaticClass()));
	FunctionObject->SetBoolField(TEXT("verbose"), bVerbose);

	Root->SetObjectField(TEXT("materialFunction"), FunctionObject);
	return Root;
}
