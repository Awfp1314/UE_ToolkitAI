#include "Authoring/CurveTableAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Curves/RealCurve.h"
#include "Curves/RichCurve.h"
#include "Curves/SimpleCurve.h"
#include "Engine/CurveTable.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace CurveTableAuthoringInternal
{

static bool ParseCurveTableMode(const FString& CurveTableMode, ECurveTableMode& OutMode)
{
	if (CurveTableMode.Equals(TEXT("RichCurves"), ESearchCase::IgnoreCase))
	{
		OutMode = ECurveTableMode::RichCurves;
		return true;
	}

	if (CurveTableMode.Equals(TEXT("SimpleCurves"), ESearchCase::IgnoreCase))
	{
		OutMode = ECurveTableMode::SimpleCurves;
		return true;
	}

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

static bool ParseCurveTableRow(const TSharedPtr<FJsonObject>& RowObject,
                               FName& OutRowName,
                               TSharedPtr<FJsonObject>& OutCurveJson,
                               TArray<FString>& OutErrors,
                               const FString& RowPath)
{
	if (!RowObject.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s: expected row object"), *RowPath));
		return false;
	}

	FString RowNameString;
	if (!RowObject->TryGetStringField(TEXT("rowName"), RowNameString) || RowNameString.IsEmpty())
	{
		OutErrors.Add(FString::Printf(TEXT("%s.rowName: missing row name"), *RowPath));
		return false;
	}

	const TSharedPtr<FJsonObject>* CurveObject = nullptr;
	if (!RowObject->TryGetObjectField(TEXT("curve"), CurveObject) || !CurveObject || !CurveObject->IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s.curve: expected curve object"), *RowPath));
		return false;
	}

	OutRowName = FName(*RowNameString);
	OutCurveJson = *CurveObject;
	return true;
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
		OutErrors.Add(FString::Printf(TEXT("%s: expected curve object"), *CurvePath));
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
			if (!ParseRichCurveKey((*Keys)[Index].IsValid() ? (*Keys)[Index]->AsObject() : nullptr,
				ParsedKey,
				OutErrors,
				FString::Printf(TEXT("%s.keys[%d]"), *CurvePath, Index)))
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

static bool ApplySimpleCurvePatch(const TSharedPtr<FJsonObject>& CurveJson,
                                  FSimpleCurve& InOutCurve,
                                  TArray<FString>& OutErrors,
                                  const FString& CurvePath)
{
	if (!CurveJson.IsValid())
	{
		OutErrors.Add(FString::Printf(TEXT("%s: expected curve object"), *CurvePath));
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
		TArray<FSimpleCurveKey> ParsedKeys;
		ParsedKeys.Reserve(Keys->Num());
		ERichCurveInterpMode InterpMode = InOutCurve.GetKeyInterpMode();
		bool bHasInterpMode = false;

		for (int32 Index = 0; Index < Keys->Num(); ++Index)
		{
			const TSharedPtr<FJsonObject> KeyObject = (*Keys)[Index].IsValid() ? (*Keys)[Index]->AsObject() : nullptr;
			if (!KeyObject.IsValid())
			{
				OutErrors.Add(FString::Printf(TEXT("%s.keys[%d]: expected key object"), *CurvePath, Index));
				bSuccess = false;
				continue;
			}

			FSimpleCurveKey ParsedKey;
			double Time = 0.0;
			double Value = 0.0;
			if (!KeyObject->TryGetNumberField(TEXT("time"), Time) || !KeyObject->TryGetNumberField(TEXT("value"), Value))
			{
				OutErrors.Add(FString::Printf(TEXT("%s.keys[%d]: key requires numeric time and value"), *CurvePath, Index));
				bSuccess = false;
				continue;
			}

			FString InterpModeString;
			if (KeyObject->TryGetStringField(TEXT("interpMode"), InterpModeString) && !InterpModeString.IsEmpty())
			{
				ERichCurveInterpMode ParsedInterpMode = RCIM_Linear;
				if (!ParseInterpMode(InterpModeString, ParsedInterpMode))
				{
					OutErrors.Add(FString::Printf(TEXT("%s.keys[%d]: invalid interpMode '%s'"), *CurvePath, Index, *InterpModeString));
					bSuccess = false;
					continue;
				}

				if (ParsedInterpMode == RCIM_Cubic)
				{
					OutErrors.Add(FString::Printf(TEXT("%s.keys[%d]: SimpleCurves cannot use cubic interpolation"), *CurvePath, Index));
					bSuccess = false;
					continue;
				}

				if (bHasInterpMode && ParsedInterpMode != InterpMode)
				{
					OutErrors.Add(FString::Printf(TEXT("%s.keys[%d]: all keys in a SimpleCurve must use the same interpMode"), *CurvePath, Index));
					bSuccess = false;
					continue;
				}

				InterpMode = ParsedInterpMode;
				bHasInterpMode = true;
			}

			ParsedKey.Time = static_cast<float>(Time);
			ParsedKey.Value = static_cast<float>(Value);
			ParsedKeys.Add(ParsedKey);
		}

		ParsedKeys.Sort([](const FSimpleCurveKey& Left, const FSimpleCurveKey& Right)
		{
			return Left.Time < Right.Time;
		});

		if (bSuccess)
		{
			InOutCurve.SetKeys(ParsedKeys);
			InOutCurve.SetKeyInterpMode(InterpMode);
		}
	}

	return bSuccess;
}

static bool ValidateCurveTableRows(const TArray<TSharedPtr<FJsonValue>>& Rows,
                                   const ECurveTableMode CurveTableMode,
                                   const UCurveTable* ExistingCurveTable,
                                   const bool bReplacingRows,
                                   TArray<FString>& OutErrors)
{
	bool bSuccess = true;

	for (int32 Index = 0; Index < Rows.Num(); ++Index)
	{
		const FString RowPath = FString::Printf(TEXT("rows[%d]"), Index);
		const TSharedPtr<FJsonObject> RowObject = Rows[Index].IsValid() ? Rows[Index]->AsObject() : nullptr;

		FName RowName = NAME_None;
		TSharedPtr<FJsonObject> CurveJson;
		if (!ParseCurveTableRow(RowObject, RowName, CurveJson, OutErrors, RowPath))
		{
			bSuccess = false;
			continue;
		}

		if (CurveTableMode == ECurveTableMode::SimpleCurves)
		{
			FSimpleCurve WorkingCurve;
			if (ExistingCurveTable && !bReplacingRows)
			{
				if (const FSimpleCurve* ExistingCurve = ExistingCurveTable->FindSimpleCurve(RowName, TEXT("CurveTableValidation"), false))
				{
					WorkingCurve = *ExistingCurve;
				}
			}
			bSuccess &= ApplySimpleCurvePatch(CurveJson, WorkingCurve, OutErrors, RowPath + TEXT(".curve"));
		}
		else
		{
			FRichCurve WorkingCurve;
			if (ExistingCurveTable && !bReplacingRows)
			{
				if (const FRichCurve* ExistingCurve = ExistingCurveTable->FindRichCurve(RowName, TEXT("CurveTableValidation"), false))
				{
					WorkingCurve = *ExistingCurve;
				}
			}
			bSuccess &= ApplyRichCurvePatch(CurveJson, WorkingCurve, OutErrors, RowPath + TEXT(".curve"));
		}
	}

	return bSuccess;
}

static bool ValidateDeleteRows(const TArray<TSharedPtr<FJsonValue>>& DeleteRows,
                               TArray<FString>& OutErrors)
{
	bool bSuccess = true;
	for (int32 Index = 0; Index < DeleteRows.Num(); ++Index)
	{
		FString RowName;
		if (!DeleteRows[Index].IsValid() || !DeleteRows[Index]->TryGetString(RowName) || RowName.IsEmpty())
		{
			OutErrors.Add(FString::Printf(TEXT("deleteRows[%d]: expected non-empty row name"), Index));
			bSuccess = false;
		}
	}
	return bSuccess;
}

static bool ApplyRows(UCurveTable* CurveTable,
                      const TArray<TSharedPtr<FJsonValue>>& Rows,
                      const ECurveTableMode CurveTableMode,
                      TArray<FString>& OutErrors)
{
	bool bSuccess = true;

	for (int32 Index = 0; Index < Rows.Num(); ++Index)
	{
		const FString RowPath = FString::Printf(TEXT("rows[%d]"), Index);
		const TSharedPtr<FJsonObject> RowObject = Rows[Index].IsValid() ? Rows[Index]->AsObject() : nullptr;

		FName RowName = NAME_None;
		TSharedPtr<FJsonObject> CurveJson;
		if (!ParseCurveTableRow(RowObject, RowName, CurveJson, OutErrors, RowPath))
		{
			bSuccess = false;
			continue;
		}

		if (CurveTableMode == ECurveTableMode::SimpleCurves)
		{
			FSimpleCurve WorkingCurve;
			if (const FSimpleCurve* ExistingCurve = CurveTable->FindSimpleCurve(RowName, TEXT("CurveTableApply"), false))
			{
				WorkingCurve = *ExistingCurve;
			}

			if (!ApplySimpleCurvePatch(CurveJson, WorkingCurve, OutErrors, RowPath + TEXT(".curve")))
			{
				bSuccess = false;
				continue;
			}

			FSimpleCurve* ExistingCurve = CurveTable->FindSimpleCurve(RowName, TEXT("CurveTableApply"), false);
			FSimpleCurve& TargetCurve = ExistingCurve ? *ExistingCurve : CurveTable->AddSimpleCurve(RowName);
			TargetCurve = WorkingCurve;
		}
		else
		{
			FRichCurve WorkingCurve;
			if (const FRichCurve* ExistingCurve = CurveTable->FindRichCurve(RowName, TEXT("CurveTableApply"), false))
			{
				WorkingCurve = *ExistingCurve;
			}

			if (!ApplyRichCurvePatch(CurveJson, WorkingCurve, OutErrors, RowPath + TEXT(".curve")))
			{
				bSuccess = false;
				continue;
			}

			FRichCurve* ExistingCurve = CurveTable->FindRichCurve(RowName, TEXT("CurveTableApply"), false);
			FRichCurve& TargetCurve = ExistingCurve ? *ExistingCurve : CurveTable->AddRichCurve(RowName);
			TargetCurve = WorkingCurve;
		}
	}

	return bSuccess;
}

static TArray<TSharedPtr<FJsonValue>> GetRowsArray(const TSharedPtr<FJsonObject>& PayloadJson)
{
	const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetArrayField(TEXT("rows"), Rows) && Rows)
	{
		return *Rows;
	}
	return {};
}

static TArray<TSharedPtr<FJsonValue>> GetDeleteRowsArray(const TSharedPtr<FJsonObject>& PayloadJson)
{
	const TArray<TSharedPtr<FJsonValue>>* DeleteRows = nullptr;
	if (PayloadJson.IsValid() && PayloadJson->TryGetArrayField(TEXT("deleteRows"), DeleteRows) && DeleteRows)
	{
		return *DeleteRows;
	}
	return {};
}

} // namespace CurveTableAuthoringInternal

TSharedPtr<FJsonObject> FCurveTableAuthoring::Create(const FString& AssetPath,
                                                     const FString& CurveTableMode,
                                                     const TArray<TSharedPtr<FJsonValue>>& Rows,
                                                     const bool bValidateOnly)
{
	using namespace CurveTableAuthoringInternal;

	FAssetMutationContext Context(TEXT("create_curve_table"), AssetPath, TEXT("CurveTable"), bValidateOnly);

	ECurveTableMode ParsedMode = ECurveTableMode::Empty;
	if (!ParseCurveTableMode(CurveTableMode, ParsedMode))
	{
		Context.AddError(TEXT("invalid_curve_table_mode"),
		                 FString::Printf(TEXT("Unsupported curve table mode '%s'"), *CurveTableMode),
		                 CurveTableMode);
		return Context.BuildResult(false);
	}

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(TEXT("asset_exists"),
		                 FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	const bool bValid = ValidateCurveTableRows(Rows, ParsedMode, nullptr, true, ValidationErrors);
	Context.SetValidationSummary(
		bValid,
		bValid ? TEXT("CurveTable payload validated.") : TEXT("CurveTable payload failed validation."),
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

	Context.BeginTransaction(FText::FromString(TEXT("Create Curve Table")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(TEXT("package_create_failed"),
		                 FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UCurveTable* CurveTable = NewObject<UCurveTable>(Package, AssetName, RF_Public | RF_Standalone);
	if (!CurveTable)
	{
		Context.AddError(TEXT("asset_create_failed"),
		                 FString::Printf(TEXT("Failed to create CurveTable asset: %s"), *AssetPath),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	CurveTable->Modify();

	if (Rows.Num() == 0)
	{
		if (ParsedMode == ECurveTableMode::SimpleCurves)
		{
			CurveTable->AddSimpleCurve(FName(TEXT("__bootstrap__")));
		}
		else
		{
			CurveTable->AddRichCurve(FName(TEXT("__bootstrap__")));
		}
		CurveTable->RemoveRow(FName(TEXT("__bootstrap__")));
	}
	else
	{
		TArray<FString> ApplyErrors;
		if (!ApplyRows(CurveTable, Rows, ParsedMode, ApplyErrors))
		{
			for (const FString& Error : ApplyErrors)
			{
				Context.AddError(TEXT("apply_error"), Error, AssetPath);
			}
			return Context.BuildResult(false);
		}
	}

	CurveTable->MarkPackageDirty();
	CurveTable->PostEditChange();
	FAssetRegistryModule::AssetCreated(CurveTable);
	Context.TrackDirtyObject(CurveTable);

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("curveTableMode"), CurveTableMode);
	Result->SetNumberField(TEXT("rowCount"), CurveTable->GetRowMap().Num());
	return Result;
}

TSharedPtr<FJsonObject> FCurveTableAuthoring::Modify(UCurveTable* CurveTable,
                                                     const TSharedPtr<FJsonObject>& PayloadJson,
                                                     const bool bValidateOnly)
{
	using namespace CurveTableAuthoringInternal;

	const FString AssetPath = CurveTable ? CurveTable->GetPathName() : FString();
	FAssetMutationContext Context(TEXT("modify_curve_table"), AssetPath, TEXT("CurveTable"), bValidateOnly);

	if (!CurveTable)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("CurveTable is null."));
		return Context.BuildResult(false);
	}

	const ECurveTableMode ExistingMode = CurveTable->GetCurveTableMode();
	if (ExistingMode == ECurveTableMode::Empty)
	{
		Context.AddError(TEXT("empty_curve_table"),
		                 TEXT("CurveTable has no established mode. Recreate it with create_curve_table instead."),
		                 AssetPath);
		return Context.BuildResult(false);
	}

	bool bReplaceRows = false;
	if (PayloadJson.IsValid())
	{
		PayloadJson->TryGetBoolField(TEXT("replaceRows"), bReplaceRows);
	}
	const TArray<TSharedPtr<FJsonValue>> Rows = GetRowsArray(PayloadJson);
	const TArray<TSharedPtr<FJsonValue>> DeleteRows = GetDeleteRowsArray(PayloadJson);

	TArray<FString> ValidationErrors;
	bool bValid = ValidateDeleteRows(DeleteRows, ValidationErrors);
	bValid &= ValidateCurveTableRows(Rows, ExistingMode, CurveTable, bReplaceRows, ValidationErrors);
	Context.SetValidationSummary(
		bValid,
		bValid ? TEXT("CurveTable payload validated.") : TEXT("CurveTable payload failed validation."),
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

	Context.BeginTransaction(FText::FromString(TEXT("Modify Curve Table")));
	CurveTable->Modify();

	if (bReplaceRows)
	{
		CurveTable->EmptyTable();
	}

	for (const TSharedPtr<FJsonValue>& DeleteValue : DeleteRows)
	{
		FString RowName;
		if (DeleteValue.IsValid() && DeleteValue->TryGetString(RowName) && !RowName.IsEmpty())
		{
			CurveTable->RemoveRow(FName(*RowName));
		}
	}

	TArray<FString> ApplyErrors;
	if (!ApplyRows(CurveTable, Rows, ExistingMode, ApplyErrors))
	{
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, AssetPath);
		}
		return Context.BuildResult(false);
	}

	CurveTable->MarkPackageDirty();
	CurveTable->PostEditChange();
	Context.TrackDirtyObject(CurveTable);

	TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
	Result->SetStringField(TEXT("curveTableMode"),
		ExistingMode == ECurveTableMode::RichCurves ? TEXT("RichCurves") : TEXT("SimpleCurves"));
	Result->SetNumberField(TEXT("rowCount"), CurveTable->GetRowMap().Num());
	return Result;
}
