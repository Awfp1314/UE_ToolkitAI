#include "Authoring/CurveAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Curves/CurveBase.h"
#include "Curves/CurveFloat.h"
#include "Curves/CurveLinearColor.h"
#include "Curves/CurveVector.h"
#include "Curves/RealCurve.h"
#include "Curves/RichCurve.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace CurveAuthoringInternal
{

static FString GetCurveClassName(const UCurveBase* Curve)
{
	if (Cast<UCurveFloat>(Curve))
	{
		return TEXT("CurveFloat");
	}
	if (Cast<UCurveVector>(Curve))
	{
		return TEXT("CurveVector");
	}
	if (Cast<UCurveLinearColor>(Curve))
	{
		return TEXT("CurveLinearColor");
	}
	return TEXT("Curve");
}

static bool ParseCurveType(const FString& CurveType, UClass*& OutCurveClass)
{
	if (CurveType.Equals(TEXT("Float"), ESearchCase::IgnoreCase)
		|| CurveType.Equals(TEXT("CurveFloat"), ESearchCase::IgnoreCase))
	{
		OutCurveClass = UCurveFloat::StaticClass();
		return true;
	}

	if (CurveType.Equals(TEXT("Vector"), ESearchCase::IgnoreCase)
		|| CurveType.Equals(TEXT("CurveVector"), ESearchCase::IgnoreCase))
	{
		OutCurveClass = UCurveVector::StaticClass();
		return true;
	}

	if (CurveType.Equals(TEXT("LinearColor"), ESearchCase::IgnoreCase)
		|| CurveType.Equals(TEXT("CurveLinearColor"), ESearchCase::IgnoreCase))
	{
		OutCurveClass = UCurveLinearColor::StaticClass();
		return true;
	}

	OutCurveClass = nullptr;
	return false;
}

static bool ParseInterpMode(const FString& InterpModeString, ERichCurveInterpMode& OutInterpMode)
{
	if (InterpModeString.IsEmpty() || InterpModeString.Equals(TEXT("None"), ESearchCase::IgnoreCase))
	{
		OutInterpMode = RCIM_None;
		return true;
	}

	if (InterpModeString.Equals(TEXT("Linear"), ESearchCase::IgnoreCase))
	{
		OutInterpMode = RCIM_Linear;
		return true;
	}

	if (InterpModeString.Equals(TEXT("Constant"), ESearchCase::IgnoreCase))
	{
		OutInterpMode = RCIM_Constant;
		return true;
	}

	if (InterpModeString.Equals(TEXT("Cubic"), ESearchCase::IgnoreCase))
	{
		OutInterpMode = RCIM_Cubic;
		return true;
	}

	return false;
}

static bool ParseExtrapolation(const FString& ExtrapolationString, ERichCurveExtrapolation& OutExtrapolation)
{
	if (ExtrapolationString.IsEmpty() || ExtrapolationString.Equals(TEXT("None"), ESearchCase::IgnoreCase))
	{
		OutExtrapolation = RCCE_None;
		return true;
	}

	if (ExtrapolationString.Equals(TEXT("Cycle"), ESearchCase::IgnoreCase))
	{
		OutExtrapolation = RCCE_Cycle;
		return true;
	}

	if (ExtrapolationString.Equals(TEXT("CycleWithOffset"), ESearchCase::IgnoreCase))
	{
		OutExtrapolation = RCCE_CycleWithOffset;
		return true;
	}

	if (ExtrapolationString.Equals(TEXT("Oscillate"), ESearchCase::IgnoreCase))
	{
		OutExtrapolation = RCCE_Oscillate;
		return true;
	}

	if (ExtrapolationString.Equals(TEXT("Linear"), ESearchCase::IgnoreCase))
	{
		OutExtrapolation = RCCE_Linear;
		return true;
	}

	if (ExtrapolationString.Equals(TEXT("Constant"), ESearchCase::IgnoreCase))
	{
		OutExtrapolation = RCCE_Constant;
		return true;
	}

	return false;
}

static void AppendValidationDiagnostics(FAssetMutationContext& Context,
                                        const TArray<FString>& ValidationErrors,
                                        const FString& DiagnosticPath)
{
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, DiagnosticPath);
	}
}

static bool ParseRichCurveKey(const TSharedPtr<FJsonObject>& KeyObject,
                              FRichCurveKey& OutKey,
                              TArray<FString>& OutErrors,
                              const FString& KeyPath)
{
	if (!KeyObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s: expected key object"), *KeyPath));
		return false;
	}

	double Time = 0.0;
	double Value = 0.0;
	if (!KeyObject->TryGetNumberField(TEXT("time"), Time) || !KeyObject->TryGetNumberField(TEXT("value"), Value))
	{
		OutErrors.Add(FString::Printf(TEXT("%s: key requires numeric time and value"), *KeyPath));
		return false;
	}

	OutKey.Time = static_cast<float>(Time);
	OutKey.Value = static_cast<float>(Value);

	double Tangent = 0.0;
	if (KeyObject->TryGetNumberField(TEXT("arriveTangent"), Tangent))
	{
		OutKey.ArriveTangent = static_cast<float>(Tangent);
	}
	if (KeyObject->TryGetNumberField(TEXT("leaveTangent"), Tangent))
	{
		OutKey.LeaveTangent = static_cast<float>(Tangent);
	}

	FString InterpModeString;
	if (KeyObject->TryGetStringField(TEXT("interpMode"), InterpModeString) && !InterpModeString.IsEmpty())
	{
		ERichCurveInterpMode ParsedInterpMode = RCIM_None;
		if (!ParseInterpMode(InterpModeString, ParsedInterpMode))
		{
			OutErrors.Add(FString::Printf(TEXT("%s: invalid interpMode '%s'"), *KeyPath, *InterpModeString));
			return false;
		}
		OutKey.InterpMode = ParsedInterpMode;
	}

	return true;
}

static bool ApplyRichCurvePatch(const TSharedPtr<FJsonObject>& CurveJson,
                                FRichCurve& InOutCurve,
                                TArray<FString>& OutErrors,
                                const FString& CurvePath)
{
	if (!CurveJson.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s: expected channel object"), *CurvePath));
		return false;
	}

	bool bSuccess = true;

	if (CurveJson->HasField(TEXT("defaultValue")))
	{
		const TSharedPtr<FJsonValue>* DefaultValue = CurveJson->Values.Find(TEXT("defaultValue"));
		if (DefaultValue && DefaultValue->IsValid() && (*DefaultValue)->Type == EJson::Null)
		{
			InOutCurve.ClearDefaultValue();
		}
		else
		{
			double Number = 0.0;
			if (CurveJson->TryGetNumberField(TEXT("defaultValue"), Number))
			{
				InOutCurve.SetDefaultValue(static_cast<float>(Number));
			}
			else
			{
				OutErrors.Add(FString::Printf(TEXT("%s.defaultValue: expected number or null"), *CurvePath));
				bSuccess = false;
			}
		}
	}

	FString Extrapolation;
	if (CurveJson->TryGetStringField(TEXT("preInfinityExtrap"), Extrapolation))
	{
		ERichCurveExtrapolation ParsedExtrapolation = RCCE_None;
		if (!ParseExtrapolation(Extrapolation, ParsedExtrapolation))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.preInfinityExtrap: invalid value '%s'"), *CurvePath, *Extrapolation));
			bSuccess = false;
		}
		else
		{
			InOutCurve.PreInfinityExtrap = ParsedExtrapolation;
		}
	}

	if (CurveJson->TryGetStringField(TEXT("postInfinityExtrap"), Extrapolation))
	{
		ERichCurveExtrapolation ParsedExtrapolation = RCCE_None;
		if (!ParseExtrapolation(Extrapolation, ParsedExtrapolation))
		{
			OutErrors.Add(FString::Printf(TEXT("%s.postInfinityExtrap: invalid value '%s'"), *CurvePath, *Extrapolation));
			bSuccess = false;
		}
		else
		{
			InOutCurve.PostInfinityExtrap = ParsedExtrapolation;
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* Keys = nullptr;
	if (CurveJson->TryGetArrayField(TEXT("keys"), Keys) && Keys)
	{
		TArray<FRichCurveKey> ParsedKeys;
		ParsedKeys.Reserve(Keys->Num());

		for (int32 Index = 0; Index < Keys->Num(); ++Index)
		{
			FRichCurveKey ParsedKey;
			const FString KeyPath = FString::Printf(TEXT("%s.keys[%d]"), *CurvePath, Index);
			if (!ParseRichCurveKey((*Keys)[Index].IsValid() ? (*Keys)[Index]->AsObject() : nullptr, ParsedKey, OutErrors, KeyPath))
			{
				bSuccess = false;
				continue;
			}
			ParsedKeys.Add(ParsedKey);
		}

		ParsedKeys.Sort([](const FRichCurveKey& Left, const FRichCurveKey& Right)
		{
			return Left.Time < Right.Time;
		});

		if (bSuccess)
		{
			InOutCurve.SetKeys(ParsedKeys);
		}
	}

	return bSuccess;
}

static FRichCurve* ResolveCurveChannel(UCurveBase* Curve,
                                       const FString& ChannelName,
                                       TArray<FString>& OutErrors,
                                       const FString& Path)
{
	if (UCurveFloat* FloatCurve = Cast<UCurveFloat>(Curve))
	{
		if (ChannelName.Equals(TEXT("default"), ESearchCase::IgnoreCase))
		{
			return &FloatCurve->FloatCurve;
		}
	}
	else if (UCurveVector* VectorCurve = Cast<UCurveVector>(Curve))
	{
		if (ChannelName.Equals(TEXT("x"), ESearchCase::IgnoreCase)) { return &VectorCurve->FloatCurves[0]; }
		if (ChannelName.Equals(TEXT("y"), ESearchCase::IgnoreCase)) { return &VectorCurve->FloatCurves[1]; }
		if (ChannelName.Equals(TEXT("z"), ESearchCase::IgnoreCase)) { return &VectorCurve->FloatCurves[2]; }
	}
	else if (UCurveLinearColor* ColorCurve = Cast<UCurveLinearColor>(Curve))
	{
		if (ChannelName.Equals(TEXT("r"), ESearchCase::IgnoreCase)) { return &ColorCurve->FloatCurves[0]; }
		if (ChannelName.Equals(TEXT("g"), ESearchCase::IgnoreCase)) { return &ColorCurve->FloatCurves[1]; }
		if (ChannelName.Equals(TEXT("b"), ESearchCase::IgnoreCase)) { return &ColorCurve->FloatCurves[2]; }
		if (ChannelName.Equals(TEXT("a"), ESearchCase::IgnoreCase)) { return &ColorCurve->FloatCurves[3]; }
	}

	OutErrors.Add(FString::Printf(TEXT("%s: unsupported channel '%s' for curve type '%s'"),
		*Path,
		*ChannelName,
		*GetCurveClassName(Curve)));
	return nullptr;
}

static bool ApplyCurveChannels(UCurveBase* Curve,
                               const TSharedPtr<FJsonObject>& ChannelsJson,
                               TArray<FString>& OutErrors)
{
	if (!Curve || !ChannelsJson.IsValid())
	{
		return true;
	}

	bool bSuccess = true;
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : ChannelsJson->Values)
	{
		const FString ChannelPath = FString::Printf(TEXT("channels.%s"), *Pair.Key);
		FRichCurve* TargetCurve = ResolveCurveChannel(Curve, Pair.Key, OutErrors, ChannelPath);
		if (!TargetCurve)
		{
			bSuccess = false;
			continue;
		}

		bSuccess &= ApplyRichCurvePatch(Pair.Value.IsValid() ? Pair.Value->AsObject() : nullptr, *TargetCurve, OutErrors, ChannelPath);
	}

	return bSuccess;
}

static bool ValidateUpsertKeyEntry(UCurveBase* Curve,
                                   const TSharedPtr<FJsonObject>& Entry,
                                   TArray<FString>& OutErrors,
                                   const FString& EntryPath)
{
	FString ChannelName;
	const TSharedPtr<FJsonObject>* KeyObject = nullptr;
	if (!Entry.IsValid()
		|| !Entry->TryGetStringField(TEXT("channel"), ChannelName)
		|| !Entry->TryGetObjectField(TEXT("key"), KeyObject)
		|| !KeyObject
		|| !KeyObject->IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s: expected channel and key"), *EntryPath));
		return false;
	}

	if (!ResolveCurveChannel(Curve, ChannelName, OutErrors, EntryPath + TEXT(".channel")))
	{
		return false;
	}

	FRichCurveKey ParsedKey;
	return ParseRichCurveKey(*KeyObject, ParsedKey, OutErrors, EntryPath + TEXT(".key"));
}

static bool ValidateDeleteKeyEntry(UCurveBase* Curve,
                                   const TSharedPtr<FJsonObject>& Entry,
                                   TArray<FString>& OutErrors,
                                   const FString& EntryPath)
{
	FString ChannelName;
	double Time = 0.0;
	if (!Entry.IsValid()
		|| !Entry->TryGetStringField(TEXT("channel"), ChannelName)
		|| !Entry->TryGetNumberField(TEXT("time"), Time))
	{
		OutErrors.Add(FString::Printf(TEXT("%s: expected channel and time"), *EntryPath));
		return false;
	}

	return ResolveCurveChannel(Curve, ChannelName, OutErrors, EntryPath + TEXT(".channel")) != nullptr;
}

static bool ValidateCurvePayload(UCurveBase* Curve,
                                 const TSharedPtr<FJsonObject>& PayloadJson,
                                 TArray<FString>& OutErrors)
{
	bool bSuccess = true;

	const TSharedPtr<FJsonObject>* ChannelsJson = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetObjectField(TEXT("channels"), ChannelsJson) && ChannelsJson)
	{
		bSuccess &= ApplyCurveChannels(Curve, *ChannelsJson, OutErrors);
	}

	const TArray<TSharedPtr<FJsonValue>>* DeleteKeys = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetArrayField(TEXT("deleteKeys"), DeleteKeys) && DeleteKeys)
	{
		for (int32 Index = 0; Index < DeleteKeys->Num(); ++Index)
		{
			bSuccess &= ValidateDeleteKeyEntry(Curve, (*DeleteKeys)[Index].IsValid() ? (*DeleteKeys)[Index]->AsObject() : nullptr, OutErrors, FString::Printf(TEXT("deleteKeys[%d]"), Index));
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* UpsertKeys = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetArrayField(TEXT("upsertKeys"), UpsertKeys) && UpsertKeys)
	{
		for (int32 Index = 0; Index < UpsertKeys->Num(); ++Index)
		{
			bSuccess &= ValidateUpsertKeyEntry(Curve, (*UpsertKeys)[Index].IsValid() ? (*UpsertKeys)[Index]->AsObject() : nullptr, OutErrors, FString::Printf(TEXT("upsertKeys[%d]"), Index));
		}
	}

	return bSuccess;
}

static bool ApplyCurvePayload(UCurveBase* Curve,
                              const TSharedPtr<FJsonObject>& PayloadJson,
                              TArray<FString>& OutErrors)
{
	bool bSuccess = true;

	const TSharedPtr<FJsonObject>* ChannelsJson = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetObjectField(TEXT("channels"), ChannelsJson) && ChannelsJson)
	{
		bSuccess &= ApplyCurveChannels(Curve, *ChannelsJson, OutErrors);
	}

	const TArray<TSharedPtr<FJsonValue>>* DeleteKeys = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetArrayField(TEXT("deleteKeys"), DeleteKeys) && DeleteKeys)
	{
		for (int32 Index = 0; Index < DeleteKeys->Num(); ++Index)
		{
			const TSharedPtr<FJsonObject> Entry = (*DeleteKeys)[Index].IsValid() ? (*DeleteKeys)[Index]->AsObject() : nullptr;
			FString ChannelName;
			double Time = 0.0;
			if (!Entry.IsValid() || !Entry->TryGetStringField(TEXT("channel"), ChannelName) || !Entry->TryGetNumberField(TEXT("time"), Time))
			{
				bSuccess = false;
				continue;
			}

			FRichCurve* TargetCurve = ResolveCurveChannel(Curve, ChannelName, OutErrors, FString::Printf(TEXT("deleteKeys[%d].channel"), Index));
			if (!TargetCurve)
			{
				bSuccess = false;
				continue;
			}

			const FKeyHandle KeyHandle = TargetCurve->FindKey(static_cast<float>(Time));
			if (!KeyHandle.IsValid())
			{
				OutErrors.Add(FString::Printf(TEXT("deleteKeys[%d]: no key found at time %g"), Index, Time));
				bSuccess = false;
				continue;
			}

			TargetCurve->DeleteKey(KeyHandle);
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* UpsertKeys = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetArrayField(TEXT("upsertKeys"), UpsertKeys) && UpsertKeys)
	{
		for (int32 Index = 0; Index < UpsertKeys->Num(); ++Index)
		{
			const TSharedPtr<FJsonObject> Entry = (*UpsertKeys)[Index].IsValid() ? (*UpsertKeys)[Index]->AsObject() : nullptr;
			FString ChannelName;
			const TSharedPtr<FJsonObject>* KeyObject = nullptr;
			if (!Entry.IsValid()
				|| !Entry->TryGetStringField(TEXT("channel"), ChannelName)
				|| !Entry->TryGetObjectField(TEXT("key"), KeyObject)
				|| !KeyObject
				|| !KeyObject->IsValid())
			{
				bSuccess = false;
				continue;
			}

			FRichCurve* TargetCurve = ResolveCurveChannel(Curve, ChannelName, OutErrors, FString::Printf(TEXT("upsertKeys[%d].channel"), Index));
			if (!TargetCurve)
			{
				bSuccess = false;
				continue;
			}

			FRichCurveKey ParsedKey;
			if (!ParseRichCurveKey(*KeyObject, ParsedKey, OutErrors, FString::Printf(TEXT("upsertKeys[%d].key"), Index)))
			{
				bSuccess = false;
				continue;
			}

			const FKeyHandle KeyHandle = TargetCurve->UpdateOrAddKey(ParsedKey.Time, ParsedKey.Value);
			FRichCurveKey& ExistingKey = TargetCurve->GetKey(KeyHandle);
			ExistingKey.ArriveTangent = ParsedKey.ArriveTangent;
			ExistingKey.LeaveTangent = ParsedKey.LeaveTangent;
			ExistingKey.InterpMode = ParsedKey.InterpMode;
			TargetCurve->SetKeyInterpMode(KeyHandle, ParsedKey.InterpMode, false);
		}
	}

	return bSuccess;
}

} // namespace CurveAuthoringInternal

TSharedPtr<FJsonObject> FCurveAuthoring::Create(const FString& AssetPath,
                                                const FString& CurveType,
                                                const TSharedPtr<FJsonObject>& ChannelsJson,
                                                const bool bValidateOnly)
{
	using namespace CurveAuthoringInternal;

	UClass* CurveClass = nullptr;
	FAssetMutationContext Context(TEXT("create_curve"), AssetPath, TEXT("Curve"), bValidateOnly);
	if (!ParseCurveType(CurveType, CurveClass) || !CurveClass)
	{
		Context.AddError(TEXT("invalid_curve_type"),
		                 FString::Printf(TEXT("Unsupported curve type '%s'"), *CurveType),
		                 CurveType);
		return Context.BuildResult(false);
	}

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	UCurveBase* PreviewCurve = NewObject<UCurveBase>(GetTransientPackage(), CurveClass);
	TSharedPtr<FJsonObject> ValidationPayload = MakeShared<FJsonObject>();
	ValidationPayload->SetObjectField(TEXT("channels"), ChannelsJson.IsValid() ? ChannelsJson : MakeShared<FJsonObject>());

	TArray<FString> ValidationErrors;
	const bool bValid = PreviewCurve && ValidateCurvePayload(PreviewCurve, ValidationPayload, ValidationErrors);
	Context.SetValidationSummary(
		bValid,
		bValid ? TEXT("Curve payload validated.") : TEXT("Curve payload failed validation."),
		ValidationErrors);
	AppendValidationDiagnostics(Context, ValidationErrors, AssetPath);
	if (!bValid)
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create Curve")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UCurveBase* Curve = NewObject<UCurveBase>(Package, CurveClass, AssetName, RF_Public | RF_Standalone);
	if (!Curve)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create curve asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	Curve->Modify();

	TArray<FString> ApplyErrors;
	const bool bApplySuccess = ApplyCurveChannels(Curve, ChannelsJson, ApplyErrors);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (!bApplySuccess)
	{
		return Context.BuildResult(false);
	}

	Curve->MarkPackageDirty();
	Curve->PostEditChange();
	FAssetRegistryModule::AssetCreated(Curve);
	Context.TrackDirtyObject(Curve);

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("curveType"), CurveClass->GetName());
	return Result;
}

TSharedPtr<FJsonObject> FCurveAuthoring::Modify(UCurveBase* Curve,
                                                const TSharedPtr<FJsonObject>& PayloadJson,
                                                const bool bValidateOnly)
{
	using namespace CurveAuthoringInternal;

	const FString AssetPath = Curve ? Curve->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_curve"), AssetPath, Curve ? GetCurveClassName(Curve) : TEXT("Curve"), bValidateOnly);

	if (!Curve)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("Curve is null."));
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	const bool bValid = ValidateCurvePayload(Curve, PayloadJson, ValidationErrors);
	Context.SetValidationSummary(
		bValid,
		bValid ? TEXT("Curve payload validated.") : TEXT("Curve payload failed validation."),
		ValidationErrors);
	AppendValidationDiagnostics(Context, ValidationErrors, AssetPath);
	if (!bValid)
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify Curve")));
	Curve->Modify();

	TArray<FString> ApplyErrors;
	const bool bApplySuccess = ApplyCurvePayload(Curve, PayloadJson, ApplyErrors);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (!bApplySuccess)
	{
		return Context.BuildResult(false);
	}

	Curve->MarkPackageDirty();
	Curve->PostEditChange();
	Context.TrackDirtyObject(Curve);

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("curveType"), GetCurveClassName(Curve));
	return Result;
}
