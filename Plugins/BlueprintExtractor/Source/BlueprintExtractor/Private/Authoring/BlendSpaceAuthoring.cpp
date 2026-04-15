#include "Authoring/BlendSpaceAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "CoreGlobals.h"
#include "Animation/BlendSpace.h"
#include "Animation/BlendSpace1D.h"
#include "Animation/Skeleton.h"
#include "Engine/SkeletalMesh.h"
#include "Factories/BlendSpaceFactory1D.h"
#include "Factories/BlendSpaceFactoryNew.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace BlendSpaceAuthoringInternal
{

static TSharedPtr<FJsonObject> NormalizePayload(const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* BlendSpaceObject = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("blendSpace"), BlendSpaceObject)
		&& BlendSpaceObject
		&& BlendSpaceObject->IsValid())
	{
		return *BlendSpaceObject;
	}

	return PayloadJson;
}

static TArray<TSharedPtr<FJsonValue>> GetArrayField(const TSharedPtr<FJsonObject>& Payload,
                                                    const TCHAR* FieldName)
{
	const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
	if (Payload.IsValid()
		&& Payload->TryGetArrayField(FieldName, Array)
		&& Array)
	{
		return *Array;
	}

	return {};
}

static bool AppendValidationSummary(FAssetMutationContext& Context,
                                    const TArray<FString>& Errors,
                                    const FString& Summary)
{
	const bool bSuccess = Errors.Num() == 0;
	Context.SetValidationSummary(bSuccess, Summary, Errors);
	for (const FString& Error : Errors)
	{
		Context.AddError(TEXT("validation_error"), Error, Context.AssetPath);
	}
	return bSuccess;
}

static bool TryGetNumberField(const TSharedPtr<FJsonObject>& Object,
                              const TCHAR* FieldName,
                              double& OutValue)
{
	return Object.IsValid() && Object->TryGetNumberField(FieldName, OutValue);
}

static USkeleton* ResolveSkeleton(const TSharedPtr<FJsonObject>& Payload, TArray<FString>& OutErrors)
{
	if (!Payload.IsValid())
	{
		OutErrors.Add(TEXT("BlendSpace payload is missing."));
		return nullptr;
	}

	FString SkeletonPath;
	if (!(Payload->TryGetStringField(TEXT("skeleton"), SkeletonPath)
		|| Payload->TryGetStringField(TEXT("skeletonPath"), SkeletonPath))
		|| SkeletonPath.IsEmpty())
	{
		OutErrors.Add(TEXT("BlendSpace creation requires a skeleton path."));
		return nullptr;
	}

	USkeleton* Skeleton = LoadObject<USkeleton>(nullptr, *SkeletonPath);
	if (!Skeleton)
	{
		OutErrors.Add(FString::Printf(TEXT("Failed to load skeleton '%s'."), *SkeletonPath));
	}

	return Skeleton;
}

static USkeletalMesh* ResolvePreviewMesh(const TSharedPtr<FJsonObject>& Payload,
                                         TArray<FString>& OutErrors)
{
	if (!Payload.IsValid())
	{
		return nullptr;
	}

	FString PreviewMeshPath;
	if (!(Payload->TryGetStringField(TEXT("previewMesh"), PreviewMeshPath)
		|| Payload->TryGetStringField(TEXT("previewSkeletalMesh"), PreviewMeshPath))
		|| PreviewMeshPath.IsEmpty())
	{
		return nullptr;
	}

	USkeletalMesh* PreviewMesh = LoadObject<USkeletalMesh>(nullptr, *PreviewMeshPath);
	if (!PreviewMesh)
	{
		OutErrors.Add(FString::Printf(TEXT("Failed to load preview mesh '%s'."), *PreviewMeshPath));
	}

	return PreviewMesh;
}

static bool IsBlendSpace1DPayload(const TSharedPtr<FJsonObject>& Payload)
{
	bool bIs1D = false;
	return Payload.IsValid() && Payload->TryGetBoolField(TEXT("is1D"), bIs1D) && bIs1D;
}

static bool ApplyAxisPatch(UBlendSpace* BlendSpace,
                           const TSharedPtr<FJsonObject>& AxisObject,
                           const int32 AxisIndex,
                           TArray<FString>& OutErrors)
{
	if (!BlendSpace || !AxisObject.IsValid())
	{
		return true;
	}

	FBlendParameter& Axis = const_cast<FBlendParameter&>(BlendSpace->GetBlendParameter(AxisIndex));
	FString Name;
	if (AxisObject->TryGetStringField(TEXT("name"), Name))
	{
		Axis.DisplayName = Name;
	}

	double NumberValue = 0.0;
	if (TryGetNumberField(AxisObject, TEXT("min"), NumberValue))
	{
		Axis.Min = static_cast<float>(NumberValue);
	}
	if (TryGetNumberField(AxisObject, TEXT("max"), NumberValue))
	{
		Axis.Max = static_cast<float>(NumberValue);
	}
	if (TryGetNumberField(AxisObject, TEXT("gridDivisions"), NumberValue))
	{
		Axis.GridNum = FMath::Max(1, static_cast<int32>(NumberValue));
	}

	bool bBoolValue = false;
	if (AxisObject->TryGetBoolField(TEXT("snapToGrid"), bBoolValue))
	{
		Axis.bSnapToGrid = bBoolValue;
	}
	if (AxisObject->TryGetBoolField(TEXT("wrapInput"), bBoolValue))
	{
		Axis.bWrapInput = bBoolValue;
	}

	if (Axis.Min >= Axis.Max)
	{
		OutErrors.Add(FString::Printf(TEXT("axis%s: min must be less than max."),
			AxisIndex == 0 ? TEXT("X") : TEXT("Y")));
		return false;
	}

	return true;
}

static bool ReplaceSamples(UBlendSpace* BlendSpace,
                           const TArray<TSharedPtr<FJsonValue>>& Samples,
                           TArray<FString>& OutErrors)
{
	for (int32 Index = BlendSpace->GetNumberOfBlendSamples() - 1; Index >= 0; --Index)
	{
		BlendSpace->DeleteSample(Index);
	}

	for (int32 SampleIndex = 0; SampleIndex < Samples.Num(); ++SampleIndex)
	{
		const FString SamplePath = FString::Printf(TEXT("samples[%d]"), SampleIndex);
		const TSharedPtr<FJsonObject> SampleObject = Samples[SampleIndex].IsValid() ? Samples[SampleIndex]->AsObject() : nullptr;
		if (!SampleObject.IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s: expected sample object."), *SamplePath));
			return false;
		}

		FString AnimationPath;
		if (!(SampleObject->TryGetStringField(TEXT("animation"), AnimationPath)
			|| SampleObject->TryGetStringField(TEXT("animSequence"), AnimationPath))
			|| AnimationPath.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.animation: missing animation reference."), *SamplePath));
			return false;
		}

		UAnimSequence* Animation = LoadObject<UAnimSequence>(nullptr, *AnimationPath);
		if (!Animation)
		{
			OutErrors.Add(FString::Printf(TEXT("%s.animation: failed to load animation '%s'."),
				*SamplePath,
				*AnimationPath));
			return false;
		}

		if (!BlendSpace->IsAnimationCompatible(Animation))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.animation: animation is not compatible with this BlendSpace."),
				*SamplePath));
			return false;
		}

		const TSharedPtr<FJsonObject>* SampleValueObject = nullptr;
		if (!SampleObject->TryGetObjectField(TEXT("sampleValue"), SampleValueObject)
			|| !SampleValueObject
			|| !SampleValueObject->IsValid())
		{
			OutErrors.Add(FString::Printf(TEXT("%s.sampleValue: missing sampleValue object."), *SamplePath));
			return false;
		}

		double X = 0.0;
		double Y = 0.0;
		double Z = 0.0;
		if (!(*SampleValueObject)->TryGetNumberField(TEXT("x"), X)
			|| !(*SampleValueObject)->TryGetNumberField(TEXT("y"), Y)
			|| !(*SampleValueObject)->TryGetNumberField(TEXT("z"), Z))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.sampleValue: expected numeric x, y, and z values."), *SamplePath));
			return false;
		}

		const int32 AddedIndex = BlendSpace->AddSample(
			Animation,
			FVector(static_cast<float>(X), static_cast<float>(Y), static_cast<float>(Z)));
		if (AddedIndex == INDEX_NONE)
		{
			OutErrors.Add(FString::Printf(TEXT("%s: failed to add BlendSpace sample."), *SamplePath));
			return false;
		}

		double RateScale = 1.0;
		if (TryGetNumberField(SampleObject, TEXT("rateScale"), RateScale))
		{
			FBlendSample& AddedSample = const_cast<FBlendSample&>(BlendSpace->GetBlendSample(AddedIndex));
			AddedSample.RateScale = static_cast<float>(RateScale);
		}
	}

	return true;
}

static bool PatchSample(UBlendSpace* BlendSpace,
                        const TSharedPtr<FJsonObject>& Payload,
                        TArray<FString>& OutErrors)
{
	if (!BlendSpace || !Payload.IsValid())
	{
		OutErrors.Add(TEXT("patch_sample requires a BlendSpace and payload."));
		return false;
	}

	double SampleIndexValue = -1.0;
	const TSharedPtr<FJsonObject>* SelectorObject = nullptr;
	const TSharedPtr<FJsonObject> Selector = (Payload->TryGetObjectField(TEXT("selector"), SelectorObject)
		&& SelectorObject
		&& SelectorObject->IsValid())
		? *SelectorObject
		: Payload;
	if (!(Selector->TryGetNumberField(TEXT("sampleIndex"), SampleIndexValue)
		|| Selector->TryGetNumberField(TEXT("index"), SampleIndexValue)))
	{
		OutErrors.Add(TEXT("patch_sample requires sampleIndex."));
		return false;
	}

	const int32 SampleIndex = static_cast<int32>(SampleIndexValue);
	if (!BlendSpace->IsValidBlendSampleIndex(SampleIndex))
	{
		OutErrors.Add(FString::Printf(TEXT("patch_sample: invalid sampleIndex %d."), SampleIndex));
		return false;
	}

	const TSharedPtr<FJsonObject>* SamplePatchObject = nullptr;
	const TSharedPtr<FJsonObject> PatchObject = (Payload->TryGetObjectField(TEXT("sample"), SamplePatchObject)
		&& SamplePatchObject
		&& SamplePatchObject->IsValid())
		? *SamplePatchObject
		: Payload;

	if (!PatchObject.IsValid())
	{
		OutErrors.Add(TEXT("patch_sample requires a sample payload."));
		return false;
	}

	if (PatchObject->HasField(TEXT("sampleValue")))
	{
		const TSharedPtr<FJsonObject>* SampleValueObject = nullptr;
		if (!PatchObject->TryGetObjectField(TEXT("sampleValue"), SampleValueObject)
			|| !SampleValueObject
			|| !SampleValueObject->IsValid())
		{
			OutErrors.Add(TEXT("sample.sampleValue must be an object."));
			return false;
		}

		double X = 0.0;
		double Y = 0.0;
		double Z = 0.0;
		if (!(*SampleValueObject)->TryGetNumberField(TEXT("x"), X)
			|| !(*SampleValueObject)->TryGetNumberField(TEXT("y"), Y)
			|| !(*SampleValueObject)->TryGetNumberField(TEXT("z"), Z))
		{
			OutErrors.Add(TEXT("sample.sampleValue requires numeric x, y, and z values."));
			return false;
		}

		if (!BlendSpace->EditSampleValue(
			SampleIndex,
			FVector(static_cast<float>(X), static_cast<float>(Y), static_cast<float>(Z))))
		{
			OutErrors.Add(TEXT("Failed to update BlendSpace sample position."));
			return false;
		}
	}

	FString AnimationPath;
	if ((PatchObject->TryGetStringField(TEXT("animation"), AnimationPath)
	     || PatchObject->TryGetStringField(TEXT("animSequence"), AnimationPath))
	    && !AnimationPath.IsEmpty())
	{
		UAnimSequence* Animation = LoadObject<UAnimSequence>(nullptr, *AnimationPath);
		if (!Animation)
		{
			OutErrors.Add(FString::Printf(TEXT("sample.animation: failed to load animation '%s'."),
				*AnimationPath));
			return false;
		}

		if (!BlendSpace->IsAnimationCompatible(Animation) || !BlendSpace->ReplaceSampleAnimation(SampleIndex, Animation))
		{
			OutErrors.Add(TEXT("Failed to update BlendSpace sample animation."));
			return false;
		}
	}

	double RateScale = 1.0;
	if (TryGetNumberField(PatchObject, TEXT("rateScale"), RateScale))
	{
		FBlendSample& Sample = const_cast<FBlendSample&>(BlendSpace->GetBlendSample(SampleIndex));
		Sample.RateScale = static_cast<float>(RateScale);
	}

	return true;
}

static bool SetAxes(UBlendSpace* BlendSpace,
                    const TSharedPtr<FJsonObject>& Payload,
                    TArray<FString>& OutErrors)
{
	const TSharedPtr<FJsonObject>* AxisXObject = nullptr;
	if (Payload.IsValid() && Payload->TryGetObjectField(TEXT("axisX"), AxisXObject) && AxisXObject && AxisXObject->IsValid())
	{
		if (!ApplyAxisPatch(BlendSpace, *AxisXObject, 0, OutErrors))
		{
			return false;
		}
	}

	const TSharedPtr<FJsonObject>* AxisYObject = nullptr;
	if (Payload.IsValid() && Payload->TryGetObjectField(TEXT("axisY"), AxisYObject) && AxisYObject && AxisYObject->IsValid())
	{
		if (BlendSpace->IsA<UBlendSpace1D>())
		{
			OutErrors.Add(TEXT("axisY is not supported for UBlendSpace1D assets."));
			return false;
		}
		if (!ApplyAxisPatch(BlendSpace, *AxisYObject, 1, OutErrors))
		{
			return false;
		}
	}

	return true;
}

static bool FinalizeBlendSpace(UBlendSpace* BlendSpace, TArray<FString>& OutErrors)
{
	if (!BlendSpace)
	{
		OutErrors.Add(TEXT("BlendSpace is null."));
		return false;
	}

	BlendSpace->ValidateSampleData();
	BlendSpace->ResampleData();
	return OutErrors.Num() == 0;
}

static bool ApplyCreatePayload(UBlendSpace* BlendSpace,
                               const TSharedPtr<FJsonObject>& Payload,
                               TArray<FString>& OutErrors)
{
	const TArray<TSharedPtr<FJsonValue>> Samples = GetArrayField(Payload, TEXT("samples"));
	if (Samples.Num() > 0 && !ReplaceSamples(BlendSpace, Samples, OutErrors))
	{
		return false;
	}

	if (!SetAxes(BlendSpace, Payload, OutErrors))
	{
		return false;
	}

	return FinalizeBlendSpace(BlendSpace, OutErrors);
}

static bool ApplyModifyOperation(UBlendSpace* BlendSpace,
                                 const FString& Operation,
                                 const TSharedPtr<FJsonObject>& Payload,
                                 TArray<FString>& OutErrors)
{
	if (Operation.Equals(TEXT("replace_samples"), ESearchCase::IgnoreCase))
	{
		if (!ReplaceSamples(BlendSpace, GetArrayField(Payload, TEXT("samples")), OutErrors))
		{
			return false;
		}
		return FinalizeBlendSpace(BlendSpace, OutErrors);
	}

	if (Operation.Equals(TEXT("patch_sample"), ESearchCase::IgnoreCase))
	{
		if (!PatchSample(BlendSpace, Payload, OutErrors))
		{
			return false;
		}
		return FinalizeBlendSpace(BlendSpace, OutErrors);
	}

	if (Operation.Equals(TEXT("set_axes"), ESearchCase::IgnoreCase))
	{
		if (!SetAxes(BlendSpace, Payload, OutErrors))
		{
			return false;
		}
		return FinalizeBlendSpace(BlendSpace, OutErrors);
	}

	OutErrors.Add(FString::Printf(TEXT("Unsupported BlendSpace operation '%s'."), *Operation));
	return false;
}

static UBlendSpace* CreateBlendSpaceAsset(UObject* Outer,
                                          const FName AssetName,
                                          USkeleton* Skeleton,
                                          USkeletalMesh* PreviewMesh,
                                          const bool bIs1D)
{
	if (!Outer || !Skeleton)
	{
		return nullptr;
	}

	UFactory* Factory = bIs1D
		? static_cast<UFactory*>(NewObject<UBlendSpaceFactory1D>())
		: static_cast<UFactory*>(NewObject<UBlendSpaceFactoryNew>());
	if (!Factory)
	{
		return nullptr;
	}

	if (UBlendSpaceFactory1D* Factory1D = Cast<UBlendSpaceFactory1D>(Factory))
	{
		Factory1D->TargetSkeleton = Skeleton;
		Factory1D->PreviewSkeletalMesh = PreviewMesh;
	}
	else if (UBlendSpaceFactoryNew* Factory2D = Cast<UBlendSpaceFactoryNew>(Factory))
	{
		Factory2D->TargetSkeleton = Skeleton;
		Factory2D->PreviewSkeletalMesh = PreviewMesh;
	}

	return Cast<UBlendSpace>(Factory->FactoryCreateNew(
		bIs1D ? UBlendSpace1D::StaticClass() : UBlendSpace::StaticClass(),
		Outer,
		AssetName,
		Outer == GetTransientPackage() ? RF_Transient : RF_Public | RF_Standalone,
		nullptr,
		GWarn));
}

} // namespace BlendSpaceAuthoringInternal

TSharedPtr<FJsonObject> FBlendSpaceAuthoring::Create(const FString& AssetPath,
                                                     const TSharedPtr<FJsonObject>& PayloadJson,
                                                     const bool bValidateOnly)
{
	using namespace BlendSpaceAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_blend_space"), AssetPath, TEXT("BlendSpace"), bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	USkeleton* Skeleton = ResolveSkeleton(Payload, ValidationErrors);
	USkeletalMesh* PreviewMesh = ResolvePreviewMesh(Payload, ValidationErrors);
	const bool bIs1D = IsBlendSpace1DPayload(Payload);

	UBlendSpace* PreviewBlendSpace = nullptr;
	if (Skeleton)
	{
		PreviewBlendSpace = CreateBlendSpaceAsset(
			GetTransientPackage(),
			MakeUniqueObjectName(GetTransientPackage(), bIs1D ? UBlendSpace1D::StaticClass() : UBlendSpace::StaticClass(), TEXT("PreviewBlendSpace")),
			Skeleton,
			PreviewMesh,
			bIs1D);
		if (!PreviewBlendSpace)
		{
			ValidationErrors.Add(TEXT("Failed to create transient BlendSpace preview asset."));
		}
	}

	if (PreviewBlendSpace)
	{
		ApplyCreatePayload(PreviewBlendSpace, Payload, ValidationErrors);
	}

	if (!AppendValidationSummary(Context, ValidationErrors, TEXT("BlendSpace payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create BlendSpace")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	UBlendSpace* BlendSpace = CreateBlendSpaceAsset(
		Package,
		FPackageName::GetShortFName(AssetPath),
		Skeleton,
		PreviewMesh,
		bIs1D);
	if (!BlendSpace)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create BlendSpace asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	BlendSpace->Modify();

	TArray<FString> ApplyErrors;
	if (!ApplyCreatePayload(BlendSpace, Payload, ApplyErrors))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, AssetPath);
		}
		UObject* AssetPtr = BlendSpace;
		CleanupFailedCreateAsset(AssetPtr);
		return Context.BuildResult(false);
	}

	BlendSpace->PostEditChange();
	FAssetRegistryModule::AssetCreated(BlendSpace);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(BlendSpace);
	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FBlendSpaceAuthoring::Modify(UBlendSpace* BlendSpace,
                                                     const FString& Operation,
                                                     const TSharedPtr<FJsonObject>& PayloadJson,
                                                     const bool bValidateOnly)
{
	using namespace BlendSpaceAuthoringInternal;

	const FString AssetPath = BlendSpace ? BlendSpace->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_blend_space"), AssetPath, TEXT("BlendSpace"), bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (!BlendSpace)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("BlendSpace is null."));
		return Context.BuildResult(false);
	}

	UBlendSpace* PreviewBlendSpace = Cast<UBlendSpace>(StaticDuplicateObject(BlendSpace, GetTransientPackage()));
	TArray<FString> ValidationErrors;
	if (!PreviewBlendSpace)
	{
		ValidationErrors.Add(TEXT("Failed to duplicate BlendSpace for validation preview."));
	}
	else
	{
		ApplyModifyOperation(PreviewBlendSpace, Operation, Payload, ValidationErrors);
	}

	if (!AppendValidationSummary(Context, ValidationErrors, TEXT("BlendSpace payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify BlendSpace")));
	BlendSpace->Modify();

	TArray<FString> ApplyErrors;
	if (!ApplyModifyOperation(BlendSpace, Operation, Payload, ApplyErrors))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, AssetPath);
		}
		return Context.BuildResult(false);
	}

	BlendSpace->PostEditChange();
	BlendSpace->MarkPackageDirty();
	Context.TrackDirtyObject(BlendSpace);
	return Context.BuildResult(true);
}
