#include "Authoring/MaterialGraphAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"
#include "Extractors/MaterialGraphExtractor.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/Font.h"
#include "Engine/Texture.h"
#include "Factories/MaterialFactoryNew.h"
#include "Factories/MaterialFunctionFactoryNew.h"
#include "MaterialEditingLibrary.h"
#include "MaterialValueType.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpression.h"
#include "Materials/MaterialExpressionComment.h"
#include "Materials/MaterialExpressionMaterialAttributeLayers.h"
#include "Materials/MaterialFunction.h"
#include "Materials/MaterialFunctionMaterialLayer.h"
#include "Materials/MaterialFunctionMaterialLayerBlend.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Misc/Guid.h"
#include "Misc/PackageName.h"
#include "SparseVolumeTexture/SparseVolumeTexture.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectGlobals.h"
#include "VT/RuntimeVirtualTexture.h"

namespace MaterialGraphAuthoringInternal
{

enum class EMaterialFunctionAssetKind
{
	Function,
	Layer,
	LayerBlend,
};

struct FCreatedExpressionRecord
{
	FString TempId;
	FString ExpressionGuid;
	FString ClassName;
};

static bool TryGetStringFieldAny(const TSharedPtr<FJsonObject>& Object,
                                 const TArray<FString>& FieldNames,
                                 FString& OutValue)
{
	if (!Object.IsValid())
	{
		return false;
	}

	for (const FString& FieldName : FieldNames)
	{
		if (Object->TryGetStringField(FieldName, OutValue))
		{
			return true;
		}
	}

	return false;
}

static bool TryGetBoolFieldAny(const TSharedPtr<FJsonObject>& Object,
                               const TArray<FString>& FieldNames,
                               bool& OutValue)
{
	if (!Object.IsValid())
	{
		return false;
	}

	for (const FString& FieldName : FieldNames)
	{
		if (Object->TryGetBoolField(FieldName, OutValue))
		{
			return true;
		}
	}

	return false;
}

static bool TryGetNumberFieldAny(const TSharedPtr<FJsonObject>& Object,
                                 const TArray<FString>& FieldNames,
                                 double& OutValue)
{
	if (!Object.IsValid())
	{
		return false;
	}

	for (const FString& FieldName : FieldNames)
	{
		if (Object->TryGetNumberField(FieldName, OutValue))
		{
			return true;
		}
	}

	return false;
}

static bool TryGetObjectFieldAny(const TSharedPtr<FJsonObject>& Object,
                                 const TArray<FString>& FieldNames,
                                 TSharedPtr<FJsonObject>& OutObject)
{
	if (!Object.IsValid())
	{
		return false;
	}

	for (const FString& FieldName : FieldNames)
	{
		const TSharedPtr<FJsonObject>* ObjectValue = nullptr;
		if (Object->TryGetObjectField(FieldName, ObjectValue) && ObjectValue && ObjectValue->IsValid())
		{
			OutObject = *ObjectValue;
			return true;
		}
	}

	return false;
}

static bool TryGetArrayFieldAny(const TSharedPtr<FJsonObject>& Object,
                                const TArray<FString>& FieldNames,
                                const TArray<TSharedPtr<FJsonValue>>*& OutArray)
{
	if (!Object.IsValid())
	{
		return false;
	}

	for (const FString& FieldName : FieldNames)
	{
		if (Object->TryGetArrayField(FieldName, OutArray) && OutArray)
		{
			return true;
		}
	}

	return false;
}

static FString GuidToString(const FGuid& Guid)
{
	return Guid.ToString(EGuidFormats::DigitsWithHyphensLower);
}

static FString ToSnakeCaseFieldName(const FString& FieldName)
{
	FString Result;
	Result.Reserve(FieldName.Len() + 4);

	for (int32 Index = 0; Index < FieldName.Len(); ++Index)
	{
		const TCHAR Character = FieldName[Index];
		const bool bInsertUnderscore = Index > 0
			&& FChar::IsUpper(Character)
			&& (FChar::IsLower(FieldName[Index - 1]) || FChar::IsDigit(FieldName[Index - 1]));

		if (bInsertUnderscore)
		{
			Result.AppendChar(TEXT('_'));
		}

		Result.AppendChar(FChar::ToLower(Character));
	}

	return Result;
}

static TArray<FString> BuildFieldAliases(const FString& FieldName)
{
	TArray<FString> Aliases;
	Aliases.Add(FieldName);

	const FString SnakeCaseField = ToSnakeCaseFieldName(FieldName);
	if (!SnakeCaseField.Equals(FieldName, ESearchCase::CaseSensitive))
	{
		Aliases.Add(SnakeCaseField);
	}

	return Aliases;
}

static bool ParseGuidField(const TSharedPtr<FJsonObject>& Object,
                           const TArray<FString>& FieldNames,
                           FGuid& OutGuid)
{
	FString GuidString;
	if (!TryGetStringFieldAny(Object, FieldNames, GuidString))
	{
		return false;
	}

	return FGuid::Parse(GuidString, OutGuid);
}

static bool ParseMaterialProperty(const FString& PropertyName, EMaterialProperty& OutProperty)
{
	const UEnum* PropertyEnum = StaticEnum<EMaterialProperty>();
	if (!PropertyEnum)
	{
		return false;
	}

	int64 Value = PropertyEnum->GetValueByNameString(PropertyName);
	if (Value == INDEX_NONE)
	{
		Value = PropertyEnum->GetValueByName(FName(*PropertyName));
	}

	if (Value == INDEX_NONE)
	{
		return false;
	}

	OutProperty = static_cast<EMaterialProperty>(Value);
	return true;
}

static bool ParseMaterialUsage(const FString& UsageName, EMaterialUsage& OutUsage)
{
	const UEnum* UsageEnum = StaticEnum<EMaterialUsage>();
	if (!UsageEnum)
	{
		return false;
	}

	int64 Value = UsageEnum->GetValueByNameString(UsageName);
	if (Value == INDEX_NONE)
	{
		Value = UsageEnum->GetValueByName(FName(*UsageName));
	}

	if (Value == INDEX_NONE)
	{
		return false;
	}

	OutUsage = static_cast<EMaterialUsage>(Value);
	return true;
}

static bool ParseMaterialDomain(const FString& DomainName, EMaterialDomain& OutDomain)
{
	const UEnum* DomainEnum = StaticEnum<EMaterialDomain>();
	if (!DomainEnum)
	{
		return false;
	}

	const int64 Value = DomainEnum->GetValueByNameString(DomainName);
	if (Value == INDEX_NONE)
	{
		return false;
	}

	OutDomain = static_cast<EMaterialDomain>(Value);
	return true;
}

static bool ParseBlendMode(const FString& BlendModeName, EBlendMode& OutBlendMode)
{
	const UEnum* BlendEnum = StaticEnum<EBlendMode>();
	if (!BlendEnum)
	{
		return false;
	}

	const int64 Value = BlendEnum->GetValueByNameString(BlendModeName);
	if (Value == INDEX_NONE)
	{
		return false;
	}

	OutBlendMode = static_cast<EBlendMode>(Value);
	return true;
}

static bool ParseShadingModel(const FString& ShadingModelName, EMaterialShadingModel& OutShadingModel)
{
	const UEnum* ShadingModelEnum = StaticEnum<EMaterialShadingModel>();
	if (!ShadingModelEnum)
	{
		return false;
	}

	const FString NormalizedName = ShadingModelName.StartsWith(TEXT("MSM_"))
		? ShadingModelName
		: FString::Printf(TEXT("MSM_%s"), *ShadingModelName);

	const int64 Value = ShadingModelEnum->GetValueByNameString(NormalizedName);
	if (Value == INDEX_NONE)
	{
		return false;
	}

	OutShadingModel = static_cast<EMaterialShadingModel>(Value);
	return OutShadingModel != MSM_MAX;
}

static bool ParseMaterialFunctionAssetKind(const FString& AssetKind, EMaterialFunctionAssetKind& OutKind)
{
	if (AssetKind.Equals(TEXT("layer"), ESearchCase::IgnoreCase))
	{
		OutKind = EMaterialFunctionAssetKind::Layer;
		return true;
	}
	if (AssetKind.Equals(TEXT("layer_blend"), ESearchCase::IgnoreCase))
	{
		OutKind = EMaterialFunctionAssetKind::LayerBlend;
		return true;
	}
	if (AssetKind.Equals(TEXT("function"), ESearchCase::IgnoreCase))
	{
		OutKind = EMaterialFunctionAssetKind::Function;
		return true;
	}
	return false;
}

static UClass* GetMaterialFunctionClassForKind(const EMaterialFunctionAssetKind AssetKind)
{
	switch (AssetKind)
	{
	case EMaterialFunctionAssetKind::Layer:
		return UMaterialFunctionMaterialLayer::StaticClass();
	case EMaterialFunctionAssetKind::LayerBlend:
		return UMaterialFunctionMaterialLayerBlend::StaticClass();
	default:
		return UMaterialFunction::StaticClass();
	}
}

static TSharedPtr<FJsonObject> MakeCompileSummary(bool bSuccess,
                                                  const FString& Status,
                                                  const TArray<FString>& Errors,
                                                  const TArray<FString>& Warnings = {},
                                                  const TSharedPtr<FJsonObject>& Extra = nullptr)
{
	const TSharedPtr<FJsonObject> Summary = MakeShared<FJsonObject>();
	Summary->SetBoolField(TEXT("success"), bSuccess);
	Summary->SetStringField(TEXT("status"), Status);
	Summary->SetNumberField(TEXT("errorCount"), Errors.Num());
	Summary->SetNumberField(TEXT("warningCount"), Warnings.Num());

	TArray<TSharedPtr<FJsonValue>> ErrorValues;
	for (const FString& Error : Errors)
	{
		ErrorValues.Add(MakeShared<FJsonValueString>(Error));
	}
	Summary->SetArrayField(TEXT("errors"), ErrorValues);

	TArray<TSharedPtr<FJsonValue>> WarningValues;
	for (const FString& Warning : Warnings)
	{
		WarningValues.Add(MakeShared<FJsonValueString>(Warning));
	}
	Summary->SetArrayField(TEXT("warnings"), WarningValues);

	if (Extra.IsValid())
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Extra->Values)
		{
			Summary->SetField(Pair.Key, Pair.Value);
		}
	}

	return Summary;
}

struct FMaterialTarget
{
	UMaterial* Material = nullptr;
	UMaterialFunction* MaterialFunction = nullptr;

	bool IsMaterial() const
	{
		return Material != nullptr;
	}

	bool IsFunction() const
	{
		return MaterialFunction != nullptr;
	}

	FString GetAssetPath() const
	{
		return Material ? Material->GetPathName() : (MaterialFunction ? MaterialFunction->GetPathName() : FString());
	}

	FString GetAssetClass() const
	{
		return Material ? TEXT("Material") : TEXT("MaterialFunction");
	}

	UMaterialExpression* FindExpressionByGuid(const FGuid& Guid) const
	{
		if (IsMaterial())
		{
			for (UMaterialExpression* Expression : Material->GetExpressions())
			{
				if (Expression && Expression->MaterialExpressionGuid == Guid)
				{
					return Expression;
				}
			}
			for (UMaterialExpressionComment* Comment : Material->GetEditorComments())
			{
				if (Comment && Comment->MaterialExpressionGuid == Guid)
				{
					return Comment;
				}
			}
		}
		else if (IsFunction())
		{
			for (UMaterialExpression* Expression : MaterialFunction->GetExpressions())
			{
				if (Expression && Expression->MaterialExpressionGuid == Guid)
				{
					return Expression;
				}
			}
			for (UMaterialExpressionComment* Comment : MaterialFunction->GetEditorComments())
			{
				if (Comment && Comment->MaterialExpressionGuid == Guid)
				{
					return Comment;
				}
			}
		}

		return nullptr;
	}

	UMaterialExpression* CreateExpression(UClass* ExpressionClass, UObject* SelectedAsset, const int32 NodePosX, const int32 NodePosY) const
	{
		if (!ExpressionClass)
		{
			return nullptr;
		}

		if (IsMaterial())
		{
			return UMaterialEditingLibrary::CreateMaterialExpressionEx(Material, nullptr, ExpressionClass, SelectedAsset, NodePosX, NodePosY, true);
		}

		if (IsFunction())
		{
			return UMaterialEditingLibrary::CreateMaterialExpressionEx(nullptr, MaterialFunction, ExpressionClass, SelectedAsset, NodePosX, NodePosY, true);
		}

		return nullptr;
	}

	UMaterialExpressionComment* CreateComment(const int32 NodePosX, const int32 NodePosY) const
	{
		UObject* Outer = IsMaterial() ? static_cast<UObject*>(Material) : static_cast<UObject*>(MaterialFunction);
		if (!Outer)
		{
			return nullptr;
		}

		UMaterialExpressionComment* Comment = NewObject<UMaterialExpressionComment>(Outer, NAME_None, RF_Transactional);
		if (!Comment)
		{
			return nullptr;
		}

		Comment->MaterialExpressionEditorX = NodePosX;
		Comment->MaterialExpressionEditorY = NodePosY;
		Comment->UpdateMaterialExpressionGuid(true, true);
		if (IsMaterial())
		{
			Comment->Material = Material;
			Material->GetExpressionCollection().AddComment(Comment);
		}
		else
		{
			MaterialFunction->GetExpressionCollection().AddComment(Comment);
		}
		Comment->MarkPackageDirty();
		return Comment;
	}

	UMaterialExpression* DuplicateExpression(UMaterialExpression* Expression) const
	{
		if (!Expression)
		{
			return nullptr;
		}

		if (UMaterialExpressionComment* Comment = Cast<UMaterialExpressionComment>(Expression))
		{
			UObject* Outer = IsMaterial() ? static_cast<UObject*>(Material) : static_cast<UObject*>(MaterialFunction);
			UMaterialExpressionComment* Duplicated = DuplicateObject(Comment, Outer);
			if (!Duplicated)
			{
				return nullptr;
			}

			Duplicated->UpdateMaterialExpressionGuid(true, true);
			if (IsMaterial())
			{
				Duplicated->Material = Material;
				Material->GetExpressionCollection().AddComment(Duplicated);
			}
			else
			{
				MaterialFunction->GetExpressionCollection().AddComment(Duplicated);
			}
			Duplicated->MarkPackageDirty();
			return Duplicated;
		}

		return UMaterialEditingLibrary::DuplicateMaterialExpression(Material, MaterialFunction, Expression);
	}

	bool DeleteExpression(UMaterialExpression* Expression) const
	{
		if (!Expression)
		{
			return false;
		}

		if (UMaterialExpressionComment* Comment = Cast<UMaterialExpressionComment>(Expression))
		{
			if (IsMaterial())
			{
				Material->GetExpressionCollection().RemoveComment(Comment);
				Material->MarkPackageDirty();
			}
			else if (IsFunction())
			{
				MaterialFunction->GetExpressionCollection().RemoveComment(Comment);
				MaterialFunction->MarkPackageDirty();
			}
			Comment->MarkAsGarbage();
			return true;
		}

		if (IsMaterial())
		{
			UMaterialEditingLibrary::DeleteMaterialExpression(Material, Expression);
			return true;
		}

		if (IsFunction())
		{
			UMaterialEditingLibrary::DeleteMaterialExpressionInFunction(MaterialFunction, Expression);
			return true;
		}

		return false;
	}

	void Layout() const
	{
		if (IsMaterial())
		{
			UMaterialEditingLibrary::LayoutMaterialExpressions(Material);
		}
		else if (IsFunction())
		{
			UMaterialEditingLibrary::LayoutMaterialFunctionExpressions(MaterialFunction);
		}
	}

	TSharedPtr<FJsonObject> Compile() const
	{
		if (IsMaterial())
		{
			UMaterialEditingLibrary::RecompileMaterial(Material);

			TArray<FString> Errors;
			for (UMaterialExpression* Expression : Material->GetExpressions())
			{
				if (Expression && !Expression->LastErrorText.IsEmpty())
				{
					Errors.Add(Expression->LastErrorText);
				}
			}

			const TSharedPtr<FJsonObject> Extra = MakeShared<FJsonObject>();
			const FMaterialStatistics Statistics = UMaterialEditingLibrary::GetStatistics(Material);
			Extra->SetNumberField(TEXT("numVertexShaderInstructions"), Statistics.NumVertexShaderInstructions);
			Extra->SetNumberField(TEXT("numPixelShaderInstructions"), Statistics.NumPixelShaderInstructions);
			Extra->SetNumberField(TEXT("numSamplers"), Statistics.NumSamplers);
			return MakeCompileSummary(Errors.Num() == 0, TEXT("Compiled"), Errors, {}, Extra);
		}

		if (IsFunction())
		{
			UMaterialEditingLibrary::UpdateMaterialFunction(MaterialFunction);

			TArray<FString> Errors;
			for (UMaterialExpression* Expression : MaterialFunction->GetExpressions())
			{
				if (Expression && !Expression->LastErrorText.IsEmpty())
				{
					Errors.Add(Expression->LastErrorText);
				}
			}

			return MakeCompileSummary(Errors.Num() == 0, TEXT("Updated"), Errors);
		}

		return MakeCompileSummary(false, TEXT("InvalidTarget"), {TEXT("No material asset was available to compile.")});
	}
};

static bool RenameExpressionGroup(UMaterialExpression* Expression, const FName OldGroupName, const FName NewGroupName)
{
	if (!Expression)
	{
		return false;
	}

	FNameProperty* GroupProperty = FindFProperty<FNameProperty>(Expression->GetClass(), TEXT("Group"));
	if (!GroupProperty)
	{
		return false;
	}

	if (GroupProperty->GetPropertyValue_InContainer(Expression) != OldGroupName)
	{
		return false;
	}

	Expression->Modify();
	GroupProperty->SetPropertyValue_InContainer(Expression, NewGroupName);
	return true;
}

static bool RenameParameterGroup(const FMaterialTarget& Target,
                                 const FString& OldGroupNameString,
                                 const FString& NewGroupNameString,
                                 FAssetMutationContext& Context)
{
	const FName OldGroupName(*OldGroupNameString);
	const FName NewGroupName(*NewGroupNameString);
	bool bRenamedAny = false;

	auto RenameGroupsInExpressions = [&](auto&& Expressions)
	{
		for (UMaterialExpression* Expression : Expressions)
		{
			if (RenameExpressionGroup(Expression, OldGroupName, NewGroupName))
			{
				Context.TrackChangedObject(Expression);
				bRenamedAny = true;
			}
		}
	};

	if (Target.IsMaterial())
	{
		RenameGroupsInExpressions(Target.Material->GetExpressions());

		if (UMaterialEditorOnlyData* EditorOnlyData = Target.Material->GetEditorOnlyData())
		{
			for (FParameterGroupData& GroupData : EditorOnlyData->ParameterGroupData)
			{
				if (GroupData.GroupName == OldGroupNameString)
				{
					GroupData.GroupName = NewGroupNameString;
					bRenamedAny = true;
				}
			}
		}

		if (bRenamedAny)
		{
			Target.Material->AttemptInsertNewGroupName(NewGroupNameString);
		}
	}
	else if (Target.IsFunction())
	{
		RenameGroupsInExpressions(Target.MaterialFunction->GetExpressions());
	}

	return bRenamedAny;
}

static UClass* ResolveExpressionClass(const FString& RequestedClassPath)
{
	if (RequestedClassPath.IsEmpty())
	{
		return nullptr;
	}

	if (UClass* ExactClass = FAuthoringHelpers::ResolveClass(RequestedClassPath, UMaterialExpression::StaticClass()))
	{
		return ExactClass;
	}

	const TArray<FString> CandidatePaths = {
		FString::Printf(TEXT("/Script/Engine.%s"), *RequestedClassPath),
		FString::Printf(TEXT("/Script/Engine.MaterialExpression%s"), *RequestedClassPath),
		FString::Printf(TEXT("/Script/Engine.UMaterialExpression%s"), *RequestedClassPath),
	};

	for (const FString& CandidatePath : CandidatePaths)
	{
		if (UClass* CandidateClass = FAuthoringHelpers::ResolveClass(CandidatePath, UMaterialExpression::StaticClass()))
		{
			return CandidateClass;
		}
	}

	return nullptr;
}

static TObjectPtr<UObject> ResolveSelectedAsset(const FString& AssetPath)
{
	return FAuthoringHelpers::ResolveObject(AssetPath);
}

static bool ApplyJsonProperties(UObject* Target,
                                const TSharedPtr<FJsonObject>& PropertiesJson,
                                TArray<FString>& OutErrors,
                                const bool bValidationOnly)
{
	if (!Target || !PropertiesJson.IsValid())
	{
		return true;
	}

	return FPropertySerializer::ApplyPropertiesFromJson(Target, PropertiesJson, OutErrors, bValidationOnly);
}

static TSharedPtr<FJsonObject> BuildCreatedExpressionsArray(const TArray<FCreatedExpressionRecord>& Records)
{
	const TSharedPtr<FJsonObject> TempIdMap = MakeShared<FJsonObject>();
	TArray<TSharedPtr<FJsonValue>> Entries;
	for (const FCreatedExpressionRecord& Record : Records)
	{
		const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
		if (!Record.TempId.IsEmpty())
		{
			Entry->SetStringField(TEXT("tempId"), Record.TempId);
			TempIdMap->SetStringField(Record.TempId, Record.ExpressionGuid);
		}
		Entry->SetStringField(TEXT("expressionGuid"), Record.ExpressionGuid);
		Entry->SetStringField(TEXT("class"), Record.ClassName);
		Entries.Add(MakeShared<FJsonValueObject>(Entry));
	}

	const TSharedPtr<FJsonObject> Wrapper = MakeShared<FJsonObject>();
	Wrapper->SetArrayField(TEXT("createdExpressions"), Entries);
	Wrapper->SetObjectField(TEXT("tempIdMap"), TempIdMap);
	return Wrapper;
}

static bool ParseLayerLinkState(const FString& LinkStateName, EMaterialLayerLinkState& OutLinkState)
{
	const UEnum* LinkStateEnum = StaticEnum<EMaterialLayerLinkState>();
	if (!LinkStateEnum)
	{
		return false;
	}

	const int64 Value = LinkStateEnum->GetValueByNameString(LinkStateName);
	if (Value == INDEX_NONE)
	{
		return false;
	}

	OutLinkState = static_cast<EMaterialLayerLinkState>(Value);
	return true;
}

static bool ParseLayerStackObject(const TSharedPtr<FJsonObject>& StackObject,
                                  FMaterialLayersFunctions& OutLayers,
                                  TArray<FString>& OutErrors)
{
	if (!StackObject.IsValid())
	{
		OutErrors.Add(TEXT("Layer stack payload must be an object."));
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* LayerEntries = nullptr;
	if (!TryGetArrayFieldAny(StackObject, {TEXT("layers")}, LayerEntries))
	{
		OutErrors.Add(TEXT("Layer stack payload requires a 'layers' array."));
		return false;
	}

	OutLayers.Empty();
	for (const TSharedPtr<FJsonValue>& EntryValue : *LayerEntries)
	{
		const TSharedPtr<FJsonObject> Entry = EntryValue.IsValid() ? EntryValue->AsObject() : nullptr;
		if (!Entry.IsValid())
		{
			OutErrors.Add(TEXT("Layer stack entries must be objects."));
			return false;
		}

		FString LayerPath;
		TryGetStringFieldAny(Entry, {TEXT("layerPath"), TEXT("layer_path")}, LayerPath);
		UMaterialFunctionInterface* LayerAsset = LayerPath.IsEmpty()
			? nullptr
			: Cast<UMaterialFunctionInterface>(FAuthoringHelpers::ResolveObject(LayerPath, UMaterialFunctionInterface::StaticClass()));
		if (!LayerPath.IsEmpty() && !LayerAsset)
		{
			OutErrors.Add(FString::Printf(TEXT("Failed to load layer asset '%s'."), *LayerPath));
			return false;
		}

		FString BlendPath;
		TryGetStringFieldAny(Entry, {TEXT("blendPath"), TEXT("blend_path")}, BlendPath);
		UMaterialFunctionInterface* BlendAsset = BlendPath.IsEmpty()
			? nullptr
			: Cast<UMaterialFunctionInterface>(FAuthoringHelpers::ResolveObject(BlendPath, UMaterialFunctionInterface::StaticClass()));
		if (!BlendPath.IsEmpty() && !BlendAsset)
		{
			OutErrors.Add(FString::Printf(TEXT("Failed to load blend asset '%s'."), *BlendPath));
			return false;
		}

		FGuid LayerGuid = FGuid::NewGuid();
		FString LayerGuidString;
		if (TryGetStringFieldAny(Entry, {TEXT("layerGuid"), TEXT("layer_guid")}, LayerGuidString) && !FGuid::Parse(LayerGuidString, LayerGuid))
		{
			OutErrors.Add(FString::Printf(TEXT("Invalid layerGuid '%s'."), *LayerGuidString));
			return false;
		}

		FString LayerName;
		TryGetStringFieldAny(Entry, {TEXT("name")}, LayerName);
		bool bVisible = true;
		TryGetBoolFieldAny(Entry, {TEXT("visible"), TEXT("enabled")}, bVisible);
		bool bRestrictToLayerRelatives = false;
		TryGetBoolFieldAny(Entry, {TEXT("restrictToLayerRelatives"), TEXT("restrict_to_layer_relatives")}, bRestrictToLayerRelatives);
		bool bRestrictToBlendRelatives = false;
		TryGetBoolFieldAny(Entry, {TEXT("restrictToBlendRelatives"), TEXT("restrict_to_blend_relatives")}, bRestrictToBlendRelatives);

		EMaterialLayerLinkState LinkState = EMaterialLayerLinkState::NotFromParent;
		FString LinkStateString;
		if (TryGetStringFieldAny(Entry, {TEXT("linkState"), TEXT("link_state")}, LinkStateString) && !ParseLayerLinkState(LinkStateString, LinkState))
		{
			OutErrors.Add(FString::Printf(TEXT("Invalid linkState '%s'."), *LinkStateString));
			return false;
		}

		OutLayers.Layers.Add(LayerAsset);
		OutLayers.Blends.Add(BlendAsset);
		OutLayers.EditorOnly.LayerGuids.Add(LayerGuid);
		OutLayers.EditorOnly.LayerNames.Add(FText::FromString(LayerName));
		OutLayers.EditorOnly.LayerStates.Add(bVisible);
		OutLayers.EditorOnly.RestrictToLayerRelatives.Add(bRestrictToLayerRelatives);
		OutLayers.EditorOnly.RestrictToBlendRelatives.Add(bRestrictToBlendRelatives);
		OutLayers.EditorOnly.LayerLinkStates.Add(LinkState);
	}

	return true;
}

static bool ApplyMaterialSettings(UMaterial* Material,
                                  const TSharedPtr<FJsonObject>& SettingsJson,
                                  TArray<FString>& OutErrors,
                                  const bool bValidationOnly)
{
	if (!Material || !SettingsJson.IsValid())
	{
		return true;
	}

	const TSharedPtr<FJsonObject> ReflectedSettings = MakeShared<FJsonObject>();
	ReflectedSettings->Values = SettingsJson->Values;
	for (const FString& FieldName : {
		     FString(TEXT("materialDomain")),
		     FString(TEXT("material_domain")),
		     FString(TEXT("blendMode")),
		     FString(TEXT("blend_mode")),
		     FString(TEXT("shadingModel")),
		     FString(TEXT("shading_model")),
		     FString(TEXT("twoSided")),
		     FString(TEXT("two_sided")),
		     FString(TEXT("fullyRough")),
		     FString(TEXT("fully_rough")),
		     FString(TEXT("useMaterialAttributes")),
		     FString(TEXT("use_material_attributes")),
		     FString(TEXT("opacityMaskClipValue")),
		     FString(TEXT("opacity_mask_clip_value")),
		     FString(TEXT("usageFlags")),
		     FString(TEXT("usage_flags")) })
	{
		ReflectedSettings->RemoveField(FieldName);
	}

	if (!ApplyJsonProperties(Material, ReflectedSettings, OutErrors, bValidationOnly))
	{
		return false;
	}

	FString EnumString;
	if (TryGetStringFieldAny(SettingsJson, {TEXT("materialDomain"), TEXT("material_domain")}, EnumString))
	{
		EMaterialDomain Domain = MD_Surface;
		if (!ParseMaterialDomain(EnumString, Domain))
		{
			OutErrors.Add(FString::Printf(TEXT("Invalid material domain '%s'."), *EnumString));
			return false;
		}
		if (!bValidationOnly)
		{
			Material->MaterialDomain = Domain;
		}
	}

	if (TryGetStringFieldAny(SettingsJson, {TEXT("blendMode"), TEXT("blend_mode")}, EnumString))
	{
		EBlendMode BlendMode = BLEND_Opaque;
		if (!ParseBlendMode(EnumString, BlendMode))
		{
			OutErrors.Add(FString::Printf(TEXT("Invalid blend mode '%s'."), *EnumString));
			return false;
		}
		if (!bValidationOnly)
		{
			Material->BlendMode = BlendMode;
		}
	}

	if (TryGetStringFieldAny(SettingsJson, {TEXT("shadingModel"), TEXT("shading_model")}, EnumString))
	{
		EMaterialShadingModel ShadingModel = MSM_DefaultLit;
		if (!ParseShadingModel(EnumString, ShadingModel))
		{
			OutErrors.Add(FString::Printf(TEXT("Invalid shading model '%s'."), *EnumString));
			return false;
		}
		if (!bValidationOnly)
		{
			Material->SetShadingModel(ShadingModel);
		}
	}

	bool bBoolValue = false;
	if (TryGetBoolFieldAny(SettingsJson, {TEXT("twoSided"), TEXT("two_sided")}, bBoolValue) && !bValidationOnly)
	{
		Material->TwoSided = bBoolValue;
	}
	if (TryGetBoolFieldAny(SettingsJson, {TEXT("fullyRough"), TEXT("fully_rough")}, bBoolValue) && !bValidationOnly)
	{
		Material->bFullyRough = bBoolValue;
	}
	if (TryGetBoolFieldAny(SettingsJson, {TEXT("useMaterialAttributes"), TEXT("use_material_attributes")}, bBoolValue) && !bValidationOnly)
	{
		Material->bUseMaterialAttributes = bBoolValue;
	}

	double NumberValue = 0.0;
	if (TryGetNumberFieldAny(SettingsJson, {TEXT("opacityMaskClipValue"), TEXT("opacity_mask_clip_value")}, NumberValue) && !bValidationOnly)
	{
		Material->OpacityMaskClipValue = static_cast<float>(NumberValue);
	}

	const TArray<TSharedPtr<FJsonValue>>* UsageValues = nullptr;
	if (TryGetArrayFieldAny(SettingsJson, {TEXT("usageFlags"), TEXT("usage_flags")}, UsageValues))
	{
		for (const TSharedPtr<FJsonValue>& UsageValue : *UsageValues)
		{
			EMaterialUsage Usage = MATUSAGE_StaticMesh;
			if (!ParseMaterialUsage(UsageValue->AsString(), Usage))
			{
				OutErrors.Add(FString::Printf(TEXT("Invalid material usage '%s'."), *UsageValue->AsString()));
				return false;
			}

			if (!bValidationOnly)
			{
				bool bNeedsRecompile = false;
				UMaterialEditingLibrary::SetMaterialUsage(Material, Usage, bNeedsRecompile);
			}
		}
	}

	return true;
}

static bool ApplyMaterialFunctionSettings(UMaterialFunction* MaterialFunction,
                                          const TSharedPtr<FJsonObject>& SettingsJson,
                                          TArray<FString>& OutErrors,
                                          const bool bValidationOnly)
{
	if (!MaterialFunction || !SettingsJson.IsValid())
	{
		return true;
	}

	const TSharedPtr<FJsonObject> ReflectedSettings = MakeShared<FJsonObject>();
	ReflectedSettings->Values = SettingsJson->Values;
	for (const FString& FieldName : {
		     FString(TEXT("description")),
		     FString(TEXT("userExposedCaption")),
		     FString(TEXT("user_exposed_caption")),
		     FString(TEXT("exposeToLibrary")),
		     FString(TEXT("expose_to_library")),
		     FString(TEXT("previewBlendMode")),
		     FString(TEXT("preview_blend_mode")),
		     FString(TEXT("previewMaterialDomain")),
		     FString(TEXT("preview_material_domain")),
		     FString(TEXT("libraryCategories")),
		     FString(TEXT("library_categories")) })
	{
		ReflectedSettings->RemoveField(FieldName);
	}

	if (!ApplyJsonProperties(MaterialFunction, ReflectedSettings, OutErrors, bValidationOnly))
	{
		return false;
	}

	FString StringValue;
	if (TryGetStringFieldAny(SettingsJson, {TEXT("description")}, StringValue) && !bValidationOnly)
	{
		MaterialFunction->Description = StringValue;
	}
	if (TryGetStringFieldAny(SettingsJson, {TEXT("userExposedCaption"), TEXT("user_exposed_caption")}, StringValue) && !bValidationOnly)
	{
		MaterialFunction->UserExposedCaption = StringValue;
	}

	bool bBoolValue = false;
	if (TryGetBoolFieldAny(SettingsJson, {TEXT("exposeToLibrary"), TEXT("expose_to_library")}, bBoolValue) && !bValidationOnly)
	{
		MaterialFunction->bExposeToLibrary = bBoolValue;
	}

	if (TryGetStringFieldAny(SettingsJson, {TEXT("previewBlendMode"), TEXT("preview_blend_mode")}, StringValue))
	{
		EBlendMode PreviewBlendMode = BLEND_Opaque;
		if (!ParseBlendMode(StringValue, PreviewBlendMode))
		{
			OutErrors.Add(FString::Printf(TEXT("Invalid preview blend mode '%s'."), *StringValue));
			return false;
		}
		if (!bValidationOnly)
		{
			MaterialFunction->PreviewBlendMode = PreviewBlendMode;
		}
	}

	if (TryGetStringFieldAny(SettingsJson, {TEXT("previewMaterialDomain"), TEXT("preview_material_domain")}, StringValue))
	{
		EMaterialDomain PreviewMaterialDomain = MD_Surface;
		if (!ParseMaterialDomain(StringValue, PreviewMaterialDomain))
		{
			OutErrors.Add(FString::Printf(TEXT("Invalid preview material domain '%s'."), *StringValue));
			return false;
		}
		if (!bValidationOnly)
		{
			MaterialFunction->PreviewMaterialDomain = PreviewMaterialDomain;
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* CategoryValues = nullptr;
	if (TryGetArrayFieldAny(SettingsJson, {TEXT("libraryCategories"), TEXT("library_categories")}, CategoryValues))
	{
		if (!bValidationOnly)
		{
			MaterialFunction->LibraryCategoriesText.Reset();
			for (const TSharedPtr<FJsonValue>& CategoryValue : *CategoryValues)
			{
				MaterialFunction->LibraryCategoriesText.Add(FText::FromString(CategoryValue->AsString()));
			}
		}
	}

	return true;
}

static FMaterialTarget MakeTarget(UMaterial* Material)
{
	FMaterialTarget Target;
	Target.Material = Material;
	return Target;
}

static FMaterialTarget MakeTarget(UMaterialFunction* MaterialFunction)
{
	FMaterialTarget Target;
	Target.MaterialFunction = MaterialFunction;
	return Target;
}

static UMaterialExpression* ResolveExpressionRef(const FMaterialTarget& Target,
                                                 const TSharedPtr<FJsonObject>& Operation,
                                                 const TMap<FString, FGuid>& TempIdToGuid,
                                                 const TMap<FString, TObjectPtr<UMaterialExpression>>& TempIdToExpressions,
                                                 const FString& GuidField,
                                                 const FString& TempIdField,
                                                 TArray<FString>& OutErrors)
{
	FGuid ExpressionGuid;
	if (ParseGuidField(Operation, BuildFieldAliases(GuidField), ExpressionGuid))
	{
		if (UMaterialExpression* Expression = Target.FindExpressionByGuid(ExpressionGuid))
		{
			return Expression;
		}

		OutErrors.Add(FString::Printf(TEXT("No expression found for guid '%s'."), *GuidToString(ExpressionGuid)));
		return nullptr;
	}

	FString TempId;
	if (TryGetStringFieldAny(Operation, BuildFieldAliases(TempIdField), TempId))
	{
		if (const TObjectPtr<UMaterialExpression>* ValidationExpression = TempIdToExpressions.Find(TempId))
		{
			return ValidationExpression->Get();
		}

		const FGuid* MappedGuid = TempIdToGuid.Find(TempId);
		if (!MappedGuid)
		{
			OutErrors.Add(FString::Printf(TEXT("No created expression found for temp_id '%s'."), *TempId));
			return nullptr;
		}

		if (UMaterialExpression* Expression = Target.FindExpressionByGuid(*MappedGuid))
		{
			return Expression;
		}

		OutErrors.Add(FString::Printf(TEXT("No expression found for temp_id '%s'."), *TempId));
		return nullptr;
	}

	OutErrors.Add(TEXT("Expression selector missing required expression_guid or temp_id."));
	return nullptr;
}

struct FResolvedMaterialOutputSelector
{
	int32 OutputIndex = INDEX_NONE;
	FString OutputName;
	const FExpressionOutput* Output = nullptr;
};

struct FResolvedMaterialInputSelector
{
	int32 InputIndex = INDEX_NONE;
	FString InputName;
	FExpressionInput* Input = nullptr;
};

static bool ResolveMaterialOutputSelector(UMaterialExpression* Expression,
                                          const TSharedPtr<FJsonObject>& Operation,
                                          FResolvedMaterialOutputSelector& OutSelector,
                                          TArray<FString>& OutErrors)
{
	if (!Expression)
	{
		OutErrors.Add(TEXT("connect_expressions requires a source expression."));
		return false;
	}

	TArray<FExpressionOutput>& Outputs = Expression->GetOutputs();
	if (Outputs.Num() == 0)
	{
		OutErrors.Add(FString::Printf(TEXT("Expression '%s' exposes no outputs."), *Expression->GetName()));
		return false;
	}

	FString RequestedName;
	const bool bHasRequestedName = TryGetStringFieldAny(Operation, {TEXT("fromOutputName"), TEXT("from_output_name")}, RequestedName)
		&& !RequestedName.IsEmpty();

	int32 RequestedIndex = INDEX_NONE;
	double RequestedIndexValue = 0.0;
	const bool bHasRequestedIndex = TryGetNumberFieldAny(Operation, {TEXT("fromOutputIndex"), TEXT("from_output_index")}, RequestedIndexValue);
	if (bHasRequestedIndex)
	{
		RequestedIndex = static_cast<int32>(RequestedIndexValue);
	}

	int32 ResolvedIndexFromName = INDEX_NONE;
	if (bHasRequestedName)
	{
		for (int32 OutputIndex = 0; OutputIndex < Outputs.Num(); ++OutputIndex)
		{
			if (Outputs[OutputIndex].OutputName.ToString().Equals(RequestedName, ESearchCase::IgnoreCase))
			{
				ResolvedIndexFromName = OutputIndex;
				break;
			}
		}

		if (ResolvedIndexFromName == INDEX_NONE)
		{
			OutErrors.Add(FString::Printf(TEXT("Output '%s' not found on expression '%s'."), *RequestedName, *Expression->GetName()));
			return false;
		}
	}

	if (bHasRequestedIndex && !Outputs.IsValidIndex(RequestedIndex))
	{
		OutErrors.Add(FString::Printf(TEXT("Output index %d is out of range for expression '%s'."), RequestedIndex, *Expression->GetName()));
		return false;
	}

	int32 ResolvedIndex = 0;
	if (bHasRequestedName && bHasRequestedIndex)
	{
		if (ResolvedIndexFromName != RequestedIndex)
		{
			OutErrors.Add(FString::Printf(TEXT("Source output selector conflict on expression '%s': name '%s' resolves to index %d but index %d was requested."),
				*Expression->GetName(),
				*RequestedName,
				ResolvedIndexFromName,
				RequestedIndex));
			return false;
		}
		ResolvedIndex = RequestedIndex;
	}
	else if (bHasRequestedName)
	{
		ResolvedIndex = ResolvedIndexFromName;
	}
	else if (bHasRequestedIndex)
	{
		ResolvedIndex = RequestedIndex;
	}

	OutSelector.OutputIndex = ResolvedIndex;
	OutSelector.Output = &Outputs[ResolvedIndex];
	OutSelector.OutputName = Outputs[ResolvedIndex].OutputName.ToString();
	return true;
}

static bool ResolveMaterialInputSelector(UMaterialExpression* Expression,
                                         const TSharedPtr<FJsonObject>& Operation,
                                         FResolvedMaterialInputSelector& OutSelector,
                                         TArray<FString>& OutErrors)
{
	if (!Expression)
	{
		OutErrors.Add(TEXT("connect_expressions requires a destination expression."));
		return false;
	}

	const int32 InputCount = Expression->CountInputs();
	if (InputCount <= 0)
	{
		OutErrors.Add(FString::Printf(TEXT("Expression '%s' exposes no inputs."), *Expression->GetName()));
		return false;
	}

	FString RequestedName;
	const bool bHasRequestedName = TryGetStringFieldAny(Operation, {TEXT("toInputName"), TEXT("to_input_name")}, RequestedName)
		&& !RequestedName.IsEmpty();

	int32 RequestedIndex = INDEX_NONE;
	double RequestedIndexValue = 0.0;
	const bool bHasRequestedIndex = TryGetNumberFieldAny(Operation, {TEXT("toInputIndex"), TEXT("to_input_index")}, RequestedIndexValue);
	if (bHasRequestedIndex)
	{
		RequestedIndex = static_cast<int32>(RequestedIndexValue);
	}

	int32 ResolvedIndexFromName = INDEX_NONE;
	if (bHasRequestedName)
	{
		for (int32 InputIndex = 0; InputIndex < InputCount; ++InputIndex)
		{
			if (Expression->GetInputName(InputIndex).ToString().Equals(RequestedName, ESearchCase::IgnoreCase))
			{
				ResolvedIndexFromName = InputIndex;
				break;
			}
		}

		if (ResolvedIndexFromName == INDEX_NONE)
		{
			OutErrors.Add(FString::Printf(TEXT("Input '%s' not found on expression '%s'."), *RequestedName, *Expression->GetName()));
			return false;
		}
	}

	if (bHasRequestedIndex && (RequestedIndex < 0 || RequestedIndex >= InputCount))
	{
		OutErrors.Add(FString::Printf(TEXT("Input index %d is out of range for expression '%s'."), RequestedIndex, *Expression->GetName()));
		return false;
	}

	int32 ResolvedIndex = 0;
	if (bHasRequestedName && bHasRequestedIndex)
	{
		if (ResolvedIndexFromName != RequestedIndex)
		{
			OutErrors.Add(FString::Printf(TEXT("Destination input selector conflict on expression '%s': name '%s' resolves to index %d but index %d was requested."),
				*Expression->GetName(),
				*RequestedName,
				ResolvedIndexFromName,
				RequestedIndex));
			return false;
		}
		ResolvedIndex = RequestedIndex;
	}
	else if (bHasRequestedName)
	{
		ResolvedIndex = ResolvedIndexFromName;
	}
	else if (bHasRequestedIndex)
	{
		ResolvedIndex = RequestedIndex;
	}

	FExpressionInput* Input = Expression->GetInput(ResolvedIndex);
	if (!Input)
	{
		OutErrors.Add(FString::Printf(TEXT("Input index %d could not be resolved on expression '%s'."), ResolvedIndex, *Expression->GetName()));
		return false;
	}

	OutSelector.InputIndex = ResolvedIndex;
	OutSelector.InputName = Expression->GetInputName(ResolvedIndex).ToString();
	OutSelector.Input = Input;
	return true;
}

static void ApplyResolvedExpressionConnection(FExpressionInput& TargetInput,
                                              UMaterialExpression* SourceExpression,
                                              const FResolvedMaterialOutputSelector& OutputSelector)
{
	TargetInput.Expression = SourceExpression;
	TargetInput.OutputIndex = OutputSelector.OutputIndex;
	if (OutputSelector.Output)
	{
		TargetInput.Mask = OutputSelector.Output->Mask;
		TargetInput.MaskR = OutputSelector.Output->MaskR;
		TargetInput.MaskG = OutputSelector.Output->MaskG;
		TargetInput.MaskB = OutputSelector.Output->MaskB;
		TargetInput.MaskA = OutputSelector.Output->MaskA;
	}
	else
	{
		TargetInput.Mask = 0;
		TargetInput.MaskR = 0;
		TargetInput.MaskG = 0;
		TargetInput.MaskB = 0;
		TargetInput.MaskA = 0;
	}
}

static bool DisconnectExpressionInput(UMaterialExpression* Expression,
                                      const TSharedPtr<FJsonObject>& Operation,
                                      TArray<FString>& OutErrors)
{
	if (!Expression)
	{
		OutErrors.Add(TEXT("disconnect_expression_input requires a target expression."));
		return false;
	}

	int32 InputIndex = INDEX_NONE;
	double InputIndexValue = 0.0;
	if (TryGetNumberFieldAny(Operation, {TEXT("inputIndex"), TEXT("input_index")}, InputIndexValue))
	{
		InputIndex = static_cast<int32>(InputIndexValue);
	}
	else
	{
		FString InputName;
		if (!TryGetStringFieldAny(Operation, {TEXT("inputName"), TEXT("input_name")}, InputName))
		{
			OutErrors.Add(TEXT("disconnect_expression_input requires input_name or input_index."));
			return false;
		}

		for (int32 CandidateIndex = 0; CandidateIndex < Expression->CountInputs(); ++CandidateIndex)
		{
			if (Expression->GetInputName(CandidateIndex).ToString().Equals(InputName, ESearchCase::IgnoreCase))
			{
				InputIndex = CandidateIndex;
				break;
			}
		}
	}

	FExpressionInput* Input = InputIndex != INDEX_NONE ? Expression->GetInput(InputIndex) : nullptr;
	if (!Input)
	{
		OutErrors.Add(TEXT("disconnect_expression_input could not resolve the requested input."));
		return false;
	}

	Input->Expression = nullptr;
	Input->OutputIndex = 0;
	Input->Mask = 0;
	Input->MaskR = 0;
	Input->MaskG = 0;
	Input->MaskB = 0;
	Input->MaskA = 0;
	return true;
}

static bool ApplyOperations(const FMaterialTarget& Target,
                            const TSharedPtr<FJsonObject>& PayloadJson,
                            FAssetMutationContext& Context,
                            const bool bValidationOnly,
                            bool& bOutCompileAfter,
                            bool& bOutLayoutAfter,
                            TArray<FCreatedExpressionRecord>& OutCreatedExpressions)
{
	bOutCompileAfter = true;
	bOutLayoutAfter = false;

	if (!PayloadJson.IsValid())
	{
		Context.SetValidationSummary(true, TEXT("Empty material payload validated."));
		return true;
	}

	TryGetBoolFieldAny(PayloadJson, {TEXT("compileAfter"), TEXT("compile_after")}, bOutCompileAfter);
	TryGetBoolFieldAny(PayloadJson, {TEXT("layoutAfter"), TEXT("layout_after")}, bOutLayoutAfter);

	const TArray<TSharedPtr<FJsonValue>>* Operations = nullptr;
	if (!TryGetArrayFieldAny(PayloadJson, {TEXT("operations")}, Operations))
	{
		Context.SetValidationSummary(true, TEXT("Material payload validated with no operations."));
		return true;
	}

	TMap<FString, FGuid> TempIdToGuid;
	TMap<FString, TObjectPtr<UMaterialExpression>> TempIdToExpressions;
	TArray<FString> ValidationErrors;

	for (const TSharedPtr<FJsonValue>& OperationValue : *Operations)
	{
		const TSharedPtr<FJsonObject> Operation = OperationValue.IsValid() ? OperationValue->AsObject() : nullptr;
		if (!Operation.IsValid())
		{
			ValidationErrors.Add(TEXT("Material operations must be objects."));
			continue;
		}

		FString OperationName;
		if (!TryGetStringFieldAny(Operation, {TEXT("operation")}, OperationName))
		{
			ValidationErrors.Add(TEXT("Material operation is missing required 'operation' field."));
			continue;
		}

		if (OperationName == TEXT("add_expression") || OperationName == TEXT("add_comment"))
		{
			FString ClassName;
			if (OperationName == TEXT("add_comment"))
			{
				ClassName = TEXT("/Script/Engine.MaterialExpressionComment");
			}
			else if (!TryGetStringFieldAny(Operation, {TEXT("expressionClass"), TEXT("expression_class")}, ClassName))
			{
				ValidationErrors.Add(TEXT("add_expression requires expression_class."));
				continue;
			}

			UClass* ExpressionClass = ResolveExpressionClass(ClassName);
			if (!ExpressionClass)
			{
				ValidationErrors.Add(FString::Printf(TEXT("Failed to resolve material expression class '%s'."), *ClassName));
				continue;
			}

			UObject* SelectedAsset = nullptr;
			FString SelectedAssetPath;
			if (TryGetStringFieldAny(Operation, {TEXT("selectedAssetPath"), TEXT("selected_asset_path")}, SelectedAssetPath))
			{
				SelectedAsset = ResolveSelectedAsset(SelectedAssetPath);
				if (!SelectedAsset)
				{
					ValidationErrors.Add(FString::Printf(TEXT("Failed to resolve selected_asset_path '%s'."), *SelectedAssetPath));
					continue;
				}
			}

			double X = 0.0;
			double Y = 0.0;
			TryGetNumberFieldAny(Operation, {TEXT("nodePosX"), TEXT("node_pos_x"), TEXT("editorX"), TEXT("editor_x")}, X);
			TryGetNumberFieldAny(Operation, {TEXT("nodePosY"), TEXT("node_pos_y"), TEXT("editorY"), TEXT("editor_y")}, Y);

			TSharedPtr<FJsonObject> PropertiesJson;
			TryGetObjectFieldAny(Operation, {TEXT("properties")}, PropertiesJson);

			if (bValidationOnly)
			{
				UMaterialExpression* ValidationExpression = NewObject<UMaterialExpression>(GetTransientPackage(), ExpressionClass);
				TArray<FString> PropertyErrors;
				if (!ApplyJsonProperties(ValidationExpression, PropertiesJson, PropertyErrors, true))
				{
					ValidationErrors.Append(PropertyErrors);
					continue;
				}

				FString TempId;
				if (TryGetStringFieldAny(Operation, {TEXT("tempId"), TEXT("temp_id")}, TempId) && !TempId.IsEmpty())
				{
					TempIdToExpressions.Add(TempId, ValidationExpression);
				}
			}
			else
			{
				UMaterialExpression* CreatedExpression = (OperationName == TEXT("add_comment"))
					? static_cast<UMaterialExpression*>(Target.CreateComment(static_cast<int32>(X), static_cast<int32>(Y)))
					: Target.CreateExpression(ExpressionClass, SelectedAsset, static_cast<int32>(X), static_cast<int32>(Y));
				if (!CreatedExpression)
				{
					Context.AddError(TEXT("create_expression_failed"),
					                 FString::Printf(TEXT("Failed to create material expression '%s'."), *ClassName),
					                 Target.GetAssetPath());
					continue;
				}

				TArray<FString> PropertyErrors;
				if (!ApplyJsonProperties(CreatedExpression, PropertiesJson, PropertyErrors, false))
				{
					for (const FString& Error : PropertyErrors)
					{
						Context.AddError(TEXT("expression_property_error"), Error, Target.GetAssetPath());
					}
				}

				CreatedExpression->MarkPackageDirty();
				Context.TrackChangedObject(CreatedExpression);

				FString TempId;
				TryGetStringFieldAny(Operation, {TEXT("tempId"), TEXT("temp_id")}, TempId);
				TempIdToGuid.Add(TempId, CreatedExpression->MaterialExpressionGuid);
				OutCreatedExpressions.Add({TempId, GuidToString(CreatedExpression->MaterialExpressionGuid), CreatedExpression->GetClass()->GetName()});
			}
		}
		else if (OperationName == TEXT("duplicate_expression"))
		{
			UMaterialExpression* SourceExpression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("sourceExpressionGuid"), TEXT("sourceTempId"), ValidationErrors);
			if (!SourceExpression)
			{
				continue;
			}

			if (bValidationOnly)
			{
				UMaterialExpression* ValidationDuplicate = DuplicateObject<UMaterialExpression>(SourceExpression, GetTransientPackage());
				if (!ValidationDuplicate)
				{
					ValidationErrors.Add(TEXT("Failed to duplicate validation material expression."));
					continue;
				}

				FString TempId;
				if (TryGetStringFieldAny(Operation, {TEXT("tempId"), TEXT("temp_id")}, TempId) && !TempId.IsEmpty())
				{
					TempIdToExpressions.Add(TempId, ValidationDuplicate);
				}
			}
			else
			{
				UMaterialExpression* DuplicatedExpression = Target.DuplicateExpression(SourceExpression);
				if (!DuplicatedExpression)
				{
					Context.AddError(TEXT("duplicate_expression_failed"),
					                 TEXT("Failed to duplicate material expression."),
					                 Target.GetAssetPath());
					continue;
				}

				double X = DuplicatedExpression->MaterialExpressionEditorX;
				double Y = DuplicatedExpression->MaterialExpressionEditorY;
				TryGetNumberFieldAny(Operation, {TEXT("nodePosX"), TEXT("node_pos_x"), TEXT("editorX"), TEXT("editor_x")}, X);
				TryGetNumberFieldAny(Operation, {TEXT("nodePosY"), TEXT("node_pos_y"), TEXT("editorY"), TEXT("editor_y")}, Y);
				DuplicatedExpression->MaterialExpressionEditorX = static_cast<int32>(X);
				DuplicatedExpression->MaterialExpressionEditorY = static_cast<int32>(Y);

				FString TempId;
				TryGetStringFieldAny(Operation, {TEXT("tempId"), TEXT("temp_id")}, TempId);
				TempIdToGuid.Add(TempId, DuplicatedExpression->MaterialExpressionGuid);
				OutCreatedExpressions.Add({TempId, GuidToString(DuplicatedExpression->MaterialExpressionGuid), DuplicatedExpression->GetClass()->GetName()});
				Context.TrackChangedObject(DuplicatedExpression);
			}
		}
		else if (OperationName == TEXT("delete_expression") || OperationName == TEXT("delete_comment"))
		{
			UMaterialExpression* Expression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("expressionGuid"), TEXT("tempId"), ValidationErrors);
			if (!Expression)
			{
				continue;
			}

			if (OperationName == TEXT("delete_comment") && !Cast<UMaterialExpressionComment>(Expression))
			{
				ValidationErrors.Add(TEXT("delete_comment requires an expression_guid that points to a MaterialExpressionComment."));
				continue;
			}

			if (!bValidationOnly && !Target.DeleteExpression(Expression))
			{
				Context.AddError(TEXT("delete_expression_failed"),
				                 TEXT("Failed to delete material expression."),
				                 Target.GetAssetPath());
			}

			if (bValidationOnly)
			{
				FString TempId;
				if (TryGetStringFieldAny(Operation, {TEXT("tempId"), TEXT("temp_id")}, TempId))
				{
					TempIdToExpressions.Remove(TempId);
				}
			}
		}
		else if (OperationName == TEXT("set_expression_properties"))
		{
			UMaterialExpression* Expression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("expressionGuid"), TEXT("tempId"), ValidationErrors);
			if (!Expression)
			{
				continue;
			}

			TSharedPtr<FJsonObject> PropertiesJson;
			if (!TryGetObjectFieldAny(Operation, {TEXT("properties")}, PropertiesJson))
			{
				ValidationErrors.Add(TEXT("set_expression_properties requires a properties object."));
				continue;
			}

			TArray<FString> PropertyErrors;
			if (!ApplyJsonProperties(Expression, PropertiesJson, PropertyErrors, bValidationOnly))
			{
				if (bValidationOnly)
				{
					ValidationErrors.Append(PropertyErrors);
				}
				else
				{
					for (const FString& Error : PropertyErrors)
					{
						Context.AddError(TEXT("expression_property_error"), Error, Target.GetAssetPath());
					}
				}
			}

			if (!bValidationOnly)
			{
				Context.TrackChangedObject(Expression);
			}
		}
		else if (OperationName == TEXT("move_expression"))
		{
			UMaterialExpression* Expression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("expressionGuid"), TEXT("tempId"), ValidationErrors);
			if (!Expression)
			{
				continue;
			}

			double X = 0.0;
			double Y = 0.0;
			if (!TryGetNumberFieldAny(Operation, {TEXT("nodePosX"), TEXT("node_pos_x"), TEXT("editorX"), TEXT("editor_x")}, X)
				|| !TryGetNumberFieldAny(Operation, {TEXT("nodePosY"), TEXT("node_pos_y"), TEXT("editorY"), TEXT("editor_y")}, Y))
			{
				ValidationErrors.Add(TEXT("move_expression requires node_pos_x and node_pos_y."));
				continue;
			}

			if (!bValidationOnly)
			{
				Expression->MaterialExpressionEditorX = static_cast<int32>(X);
				Expression->MaterialExpressionEditorY = static_cast<int32>(Y);
				Context.TrackChangedObject(Expression);
			}
		}
		else if (OperationName == TEXT("connect_expressions"))
		{
			UMaterialExpression* FromExpression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("fromExpressionGuid"), TEXT("fromTempId"), ValidationErrors);
			UMaterialExpression* ToExpression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("toExpressionGuid"), TEXT("toTempId"), ValidationErrors);
			if (!FromExpression || !ToExpression)
			{
				continue;
			}

			FResolvedMaterialOutputSelector OutputSelector;
			if (!ResolveMaterialOutputSelector(FromExpression, Operation, OutputSelector, ValidationErrors))
			{
				continue;
			}

			FResolvedMaterialInputSelector InputSelector;
			if (!ResolveMaterialInputSelector(ToExpression, Operation, InputSelector, ValidationErrors))
			{
				continue;
			}

			if (!bValidationOnly)
			{
				ApplyResolvedExpressionConnection(*InputSelector.Input, FromExpression, OutputSelector);
				Context.TrackChangedObject(ToExpression);
			}
		}
		else if (OperationName == TEXT("disconnect_expression_input"))
		{
			UMaterialExpression* Expression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("expressionGuid"), TEXT("tempId"), ValidationErrors);
			if (!Expression)
			{
				continue;
			}

			if (!DisconnectExpressionInput(Expression, Operation, ValidationErrors))
			{
				continue;
			}

			if (!bValidationOnly)
			{
				Context.TrackChangedObject(Expression);
			}
		}
		else if (OperationName == TEXT("connect_material_property"))
		{
			if (!Target.IsMaterial())
			{
				ValidationErrors.Add(TEXT("connect_material_property is only valid for UMaterial assets."));
				continue;
			}

			UMaterialExpression* FromExpression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("fromExpressionGuid"), TEXT("fromTempId"), ValidationErrors);
			if (!FromExpression)
			{
				continue;
			}

			FString PropertyName;
			if (!TryGetStringFieldAny(Operation, {TEXT("materialProperty"), TEXT("material_property")}, PropertyName))
			{
				ValidationErrors.Add(TEXT("connect_material_property requires material_property."));
				continue;
			}

			EMaterialProperty Property = MP_BaseColor;
			if (!ParseMaterialProperty(PropertyName, Property))
			{
				ValidationErrors.Add(FString::Printf(TEXT("Invalid material property '%s'."), *PropertyName));
				continue;
			}

			FResolvedMaterialOutputSelector OutputSelector;
			if (!ResolveMaterialOutputSelector(FromExpression, Operation, OutputSelector, ValidationErrors))
			{
				continue;
			}

			if (!bValidationOnly)
			{
				if (FExpressionInput* Input = Target.Material->GetExpressionInputForProperty(Property))
				{
					ApplyResolvedExpressionConnection(*Input, FromExpression, OutputSelector);
					Context.TrackChangedObject(Target.Material);
				}
				else
				{
					Context.AddError(TEXT("connect_material_property_failed"),
					                 TEXT("Failed to resolve the requested material property input."),
					                 Target.GetAssetPath());
				}
			}
		}
		else if (OperationName == TEXT("disconnect_material_property"))
		{
			if (!Target.IsMaterial())
			{
				ValidationErrors.Add(TEXT("disconnect_material_property is only valid for UMaterial assets."));
				continue;
			}

			FString PropertyName;
			if (!TryGetStringFieldAny(Operation, {TEXT("materialProperty"), TEXT("material_property")}, PropertyName))
			{
				ValidationErrors.Add(TEXT("disconnect_material_property requires material_property."));
				continue;
			}

			EMaterialProperty Property = MP_BaseColor;
			if (!ParseMaterialProperty(PropertyName, Property))
			{
				ValidationErrors.Add(FString::Printf(TEXT("Invalid material property '%s'."), *PropertyName));
				continue;
			}

			if (!bValidationOnly)
			{
				if (FExpressionInput* Input = Target.Material->GetExpressionInputForProperty(Property))
				{
					Input->Expression = nullptr;
					Input->OutputIndex = 0;
					Input->Mask = 0;
					Input->MaskR = 0;
					Input->MaskG = 0;
					Input->MaskB = 0;
					Input->MaskA = 0;
				}
			}
		}
		else if (OperationName == TEXT("rename_parameter_group"))
		{
			FString OldGroupName;
			FString NewGroupName;
			if (!TryGetStringFieldAny(Operation, {TEXT("oldGroupName"), TEXT("old_group_name")}, OldGroupName)
				|| !TryGetStringFieldAny(Operation, {TEXT("newGroupName"), TEXT("new_group_name")}, NewGroupName))
			{
				ValidationErrors.Add(TEXT("rename_parameter_group requires old_group_name and new_group_name."));
				continue;
			}

			if (!bValidationOnly)
			{
				const bool bRenamed = RenameParameterGroup(Target, OldGroupName, NewGroupName, Context);
				if (!bRenamed)
				{
					Context.AddError(TEXT("rename_parameter_group_failed"),
					                 FString::Printf(TEXT("Failed to rename parameter group '%s'."), *OldGroupName),
					                 Target.GetAssetPath());
				}
			}
		}
		else if (OperationName == TEXT("set_material_settings"))
		{
			if (!Target.IsMaterial())
			{
				ValidationErrors.Add(TEXT("set_material_settings is only valid for UMaterial assets."));
				continue;
			}

			TSharedPtr<FJsonObject> SettingsJson;
			if (!TryGetObjectFieldAny(Operation, {TEXT("settings")}, SettingsJson))
			{
				SettingsJson = Operation;
			}

			if (!ApplyMaterialSettings(Target.Material, SettingsJson, ValidationErrors, bValidationOnly))
			{
				continue;
			}
		}
		else if (OperationName == TEXT("set_layer_stack"))
		{
			if (Target.IsFunction())
			{
				ValidationErrors.Add(TEXT("set_layer_stack is not valid for material function assets."));
				continue;
			}

			UMaterialExpression* Expression = ResolveExpressionRef(Target, Operation, TempIdToGuid, TempIdToExpressions, TEXT("expressionGuid"), TEXT("tempId"), ValidationErrors);
			UMaterialExpressionMaterialAttributeLayers* LayerExpression = Cast<UMaterialExpressionMaterialAttributeLayers>(Expression);
			if (!LayerExpression)
			{
				ValidationErrors.Add(TEXT("set_layer_stack requires expression_guid for a MaterialExpressionMaterialAttributeLayers node."));
				continue;
			}

			TSharedPtr<FJsonObject> LayerStackJson;
			if (!TryGetObjectFieldAny(Operation, {TEXT("layerStack"), TEXT("layer_stack")}, LayerStackJson))
			{
				LayerStackJson = Operation;
			}

			FMaterialLayersFunctions ParsedLayers;
			if (!ParseLayerStackObject(LayerStackJson, ParsedLayers, ValidationErrors))
			{
				continue;
			}

			if (!bValidationOnly)
			{
				LayerExpression->DefaultLayers = ParsedLayers;
				Context.TrackChangedObject(LayerExpression);
			}
		}
		else
		{
			ValidationErrors.Add(FString::Printf(TEXT("Unsupported material graph operation: %s"), *OperationName));
		}
	}

	Context.SetValidationSummary(
		ValidationErrors.Num() == 0,
		ValidationErrors.Num() == 0 ? TEXT("Material graph payload validated.") : TEXT("Material graph payload failed validation."),
		ValidationErrors);

	if (ValidationErrors.Num() > 0)
	{
		for (const FString& Error : ValidationErrors)
		{
			Context.AddError(TEXT("validation_error"), Error, Target.GetAssetPath());
		}
		return false;
	}

	return true;
}

} // namespace MaterialGraphAuthoringInternal

TSharedPtr<FJsonObject> FMaterialGraphAuthoring::CreateMaterial(const FString& AssetPath,
                                                                const FString& InitialTexturePath,
                                                                const TSharedPtr<FJsonObject>& SettingsJson,
                                                                const bool bValidateOnly)
{
	using namespace MaterialGraphAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_material"), AssetPath, TEXT("Material"), bValidateOnly);
	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_already_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	UTexture* InitialTexture = nullptr;
	if (!InitialTexturePath.IsEmpty())
	{
		InitialTexture = Cast<UTexture>(ResolveSelectedAsset(InitialTexturePath));
		if (!InitialTexture)
		{
			Context.AddError(TEXT("initial_texture_not_found"),
			                 FString::Printf(TEXT("Initial texture not found: %s"), *InitialTexturePath),
			                 InitialTexturePath);
			return Context.BuildResult(false);
		}
	}

	{
		UMaterial* ValidationMaterial = NewObject<UMaterial>(GetTransientPackage());
		TArray<FString> ValidationErrors;
		if (!ApplyMaterialSettings(ValidationMaterial, SettingsJson, ValidationErrors, true))
		{
			Context.SetValidationSummary(false, TEXT("Material creation payload failed validation."), ValidationErrors);
			for (const FString& Error : ValidationErrors)
			{
				Context.AddError(TEXT("validation_error"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
	}

	Context.SetValidationSummary(true, TEXT("Material creation inputs validated."));
	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create Material")));
	UPackage* Package = CreatePackage(*AssetPath);
	UMaterialFactoryNew* Factory = Package ? NewObject<UMaterialFactoryNew>() : nullptr;
	if (!Package || !Factory)
	{
		Context.AddError(TEXT("factory_create_failed"), TEXT("Failed to create package or material factory."), AssetPath);
		return Context.BuildResult(false);
	}

	Factory->InitialTexture = InitialTexture;
	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UMaterial* Material = Cast<UMaterial>(Factory->FactoryCreateNew(
		UMaterial::StaticClass(),
		Package,
		AssetName,
		RF_Public | RF_Standalone,
		nullptr,
		GWarn));
	if (!Material)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create Material asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	Material->Modify();
	TArray<FString> ApplyErrors;
	if (!ApplyMaterialSettings(Material, SettingsJson, ApplyErrors, false))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("settings_apply_failed"), Error, AssetPath);
		}
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(Material);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(Material);
	Context.SetCompileSummary(MakeTarget(Material).Compile());

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	if (!InitialTexturePath.IsEmpty())
	{
		Result->SetStringField(TEXT("initialTexturePath"), InitialTexturePath);
	}
	return Result;
}

TSharedPtr<FJsonObject> FMaterialGraphAuthoring::CreateMaterialFunction(const FString& AssetPath,
                                                                        const FString& AssetKind,
                                                                        const TSharedPtr<FJsonObject>& SettingsJson,
                                                                        const bool bValidateOnly)
{
	using namespace MaterialGraphAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_material_function"), AssetPath, TEXT("MaterialFunction"), bValidateOnly);
	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_already_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	EMaterialFunctionAssetKind ParsedKind = EMaterialFunctionAssetKind::Function;
	if (!ParseMaterialFunctionAssetKind(AssetKind, ParsedKind))
	{
		Context.AddError(TEXT("invalid_asset_kind"),
		                 FString::Printf(TEXT("Unsupported material function asset_kind: %s"), *AssetKind),
		                 AssetKind);
		return Context.BuildResult(false);
	}

	{
		UMaterialFunction* ValidationFunction = NewObject<UMaterialFunction>(GetTransientPackage());
		TArray<FString> ValidationErrors;
		if (!ApplyMaterialFunctionSettings(ValidationFunction, SettingsJson, ValidationErrors, true))
		{
			Context.SetValidationSummary(false, TEXT("Material function creation payload failed validation."), ValidationErrors);
			for (const FString& Error : ValidationErrors)
			{
				Context.AddError(TEXT("validation_error"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
	}

	Context.SetValidationSummary(true, TEXT("Material function creation inputs validated."));
	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create Material Function")));
	UPackage* Package = CreatePackage(*AssetPath);
	UMaterialFunctionFactoryNew* Factory = Package ? NewObject<UMaterialFunctionFactoryNew>() : nullptr;
	if (!Package || !Factory)
	{
		Context.AddError(TEXT("factory_create_failed"), TEXT("Failed to create package or material function factory."), AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UMaterialFunction* MaterialFunction = Cast<UMaterialFunction>(Factory->FactoryCreateNew(
		GetMaterialFunctionClassForKind(ParsedKind),
		Package,
		AssetName,
		RF_Public | RF_Standalone,
		nullptr,
		GWarn));
	if (!MaterialFunction)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create MaterialFunction asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	MaterialFunction->Modify();
	TArray<FString> ApplyErrors;
	if (!ApplyMaterialFunctionSettings(MaterialFunction, SettingsJson, ApplyErrors, false))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("settings_apply_failed"), Error, AssetPath);
		}
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(MaterialFunction);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(MaterialFunction);
	Context.SetCompileSummary(MakeTarget(MaterialFunction).Compile());

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("assetKind"), AssetKind);
	return Result;
}

TSharedPtr<FJsonObject> FMaterialGraphAuthoring::ModifyMaterial(UMaterial* Material,
                                                                const TSharedPtr<FJsonObject>& PayloadJson,
                                                                const bool bValidateOnly)
{
	using namespace MaterialGraphAuthoringInternal;

	const FString AssetPath = Material ? Material->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_material"), AssetPath, TEXT("Material"), bValidateOnly);
	if (!Material)
	{
		Context.AddError(TEXT("invalid_material"), TEXT("Material is null."), AssetPath);
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject>* SettingsObject = nullptr;
	const TSharedPtr<FJsonObject> SettingsJson =
		PayloadJson.IsValid() && PayloadJson->TryGetObjectField(TEXT("settings"), SettingsObject) && SettingsObject && SettingsObject->IsValid()
			? *SettingsObject
			: nullptr;

	if (SettingsJson.IsValid())
	{
		TArray<FString> SettingsErrors;
		if (!ApplyMaterialSettings(Material, SettingsJson, SettingsErrors, true))
		{
			Context.SetValidationSummary(false, TEXT("Material settings payload failed validation."), SettingsErrors);
			for (const FString& Error : SettingsErrors)
			{
				Context.AddError(TEXT("validation_error"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
	}

	const FMaterialTarget Target = MakeTarget(Material);
	bool bCompileAfter = true;
	bool bLayoutAfter = false;
	TArray<FCreatedExpressionRecord> CreatedExpressions;
	if (bValidateOnly)
	{
		if (!ApplyOperations(Target, PayloadJson, Context, true, bCompileAfter, bLayoutAfter, CreatedExpressions))
		{
			return Context.BuildResult(false);
		}
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify Material")));
	Material->Modify();
	if (SettingsJson.IsValid())
	{
		TArray<FString> ApplyErrors;
		if (!ApplyMaterialSettings(Material, SettingsJson, ApplyErrors, false))
		{
			for (const FString& Error : ApplyErrors)
			{
				Context.AddError(TEXT("settings_apply_failed"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
	}

	if (!ApplyOperations(Target, PayloadJson, Context, false, bCompileAfter, bLayoutAfter, CreatedExpressions))
	{
		return Context.BuildResult(false);
	}
	if (bLayoutAfter)
	{
		Target.Layout();
	}
	Material->MarkPackageDirty();
	Context.TrackDirtyObject(Material);
	if (bCompileAfter)
	{
		Context.SetCompileSummary(Target.Compile());
	}

	TSharedPtr<FJsonObject> Result = Context.BuildResult(Context.Diagnostics.FilterByPredicate([](const FAssetMutationDiagnostic& Diagnostic)
	{
		return Diagnostic.Severity == TEXT("error");
	}).Num() == 0);
	const TSharedPtr<FJsonObject> CreatedSummary = BuildCreatedExpressionsArray(CreatedExpressions);
	Result->SetArrayField(TEXT("createdExpressions"), CreatedSummary->GetArrayField(TEXT("createdExpressions")));
	Result->SetObjectField(TEXT("tempIdMap"), CreatedSummary->GetObjectField(TEXT("tempIdMap")));
	Result->SetBoolField(TEXT("compileAfter"), bCompileAfter);
	Result->SetBoolField(TEXT("layoutAfter"), bLayoutAfter);
	return Result;
}

TSharedPtr<FJsonObject> FMaterialGraphAuthoring::ModifyMaterialFunction(UMaterialFunctionInterface* MaterialFunctionInterface,
                                                                        const TSharedPtr<FJsonObject>& PayloadJson,
                                                                        const bool bValidateOnly)
{
	using namespace MaterialGraphAuthoringInternal;

	UMaterialFunction* MaterialFunction = Cast<UMaterialFunction>(MaterialFunctionInterface);
	const FString AssetPath = MaterialFunction ? MaterialFunction->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_material_function"), AssetPath, TEXT("MaterialFunction"), bValidateOnly);
	if (!MaterialFunction)
	{
		Context.AddError(TEXT("invalid_material_function"), TEXT("MaterialFunction must be a concrete UMaterialFunction asset."), AssetPath);
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject>* SettingsObject = nullptr;
	const TSharedPtr<FJsonObject> SettingsJson =
		PayloadJson.IsValid() && PayloadJson->TryGetObjectField(TEXT("settings"), SettingsObject) && SettingsObject && SettingsObject->IsValid()
			? *SettingsObject
			: nullptr;

	if (SettingsJson.IsValid())
	{
		TArray<FString> SettingsErrors;
		if (!ApplyMaterialFunctionSettings(MaterialFunction, SettingsJson, SettingsErrors, true))
		{
			Context.SetValidationSummary(false, TEXT("Material function settings payload failed validation."), SettingsErrors);
			for (const FString& Error : SettingsErrors)
			{
				Context.AddError(TEXT("validation_error"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
	}

	const FMaterialTarget Target = MakeTarget(MaterialFunction);
	bool bCompileAfter = true;
	bool bLayoutAfter = false;
	TArray<FCreatedExpressionRecord> CreatedExpressions;
	if (bValidateOnly)
	{
		if (!ApplyOperations(Target, PayloadJson, Context, true, bCompileAfter, bLayoutAfter, CreatedExpressions))
		{
			return Context.BuildResult(false);
		}
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify Material Function")));
	MaterialFunction->Modify();
	if (SettingsJson.IsValid())
	{
		TArray<FString> ApplyErrors;
		if (!ApplyMaterialFunctionSettings(MaterialFunction, SettingsJson, ApplyErrors, false))
		{
			for (const FString& Error : ApplyErrors)
			{
				Context.AddError(TEXT("settings_apply_failed"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
	}

	if (!ApplyOperations(Target, PayloadJson, Context, false, bCompileAfter, bLayoutAfter, CreatedExpressions))
	{
		return Context.BuildResult(false);
	}
	if (bLayoutAfter)
	{
		Target.Layout();
	}
	MaterialFunction->MarkPackageDirty();
	Context.TrackDirtyObject(MaterialFunction);
	if (bCompileAfter)
	{
		Context.SetCompileSummary(Target.Compile());
	}

	TSharedPtr<FJsonObject> Result = Context.BuildResult(Context.Diagnostics.FilterByPredicate([](const FAssetMutationDiagnostic& Diagnostic)
	{
		return Diagnostic.Severity == TEXT("error");
	}).Num() == 0);
	const TSharedPtr<FJsonObject> CreatedSummary = BuildCreatedExpressionsArray(CreatedExpressions);
	Result->SetArrayField(TEXT("createdExpressions"), CreatedSummary->GetArrayField(TEXT("createdExpressions")));
	Result->SetObjectField(TEXT("tempIdMap"), CreatedSummary->GetObjectField(TEXT("tempIdMap")));
	Result->SetBoolField(TEXT("compileAfter"), bCompileAfter);
	Result->SetBoolField(TEXT("layoutAfter"), bLayoutAfter);
	return Result;
}

TSharedPtr<FJsonObject> FMaterialGraphAuthoring::CompileMaterialAsset(UObject* Asset)
{
	using namespace MaterialGraphAuthoringInternal;

	const FString AssetPath = Asset ? Asset->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("compile_material_asset"), AssetPath, TEXT("MaterialAsset"), false);
	if (!Asset)
	{
		Context.AddError(TEXT("invalid_asset"), TEXT("Material asset is null."), AssetPath);
		return Context.BuildResult(false);
	}

	if (UMaterial* Material = Cast<UMaterial>(Asset))
	{
		Context.SetCompileSummary(MakeTarget(Material).Compile());
		return Context.BuildResult(true);
	}

	if (UMaterialFunction* MaterialFunction = Cast<UMaterialFunction>(Asset))
	{
		Context.SetCompileSummary(MakeTarget(MaterialFunction).Compile());
		return Context.BuildResult(true);
	}

	if (UMaterialInstanceConstant* MaterialInstance = Cast<UMaterialInstanceConstant>(Asset))
	{
		UMaterialEditingLibrary::UpdateMaterialInstance(MaterialInstance);
		Context.TrackDirtyObject(MaterialInstance);
		Context.SetCompileSummary(MakeCompileSummary(true, TEXT("Updated"), {}));
		return Context.BuildResult(true);
	}

	Context.AddError(TEXT("unsupported_asset_type"),
	                 TEXT("compile_material_asset only supports UMaterial, UMaterialFunction, and UMaterialInstanceConstant assets."),
	                 AssetPath);
	return Context.BuildResult(false);
}
