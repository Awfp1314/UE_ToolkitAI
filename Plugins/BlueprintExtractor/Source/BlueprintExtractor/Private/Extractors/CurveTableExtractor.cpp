#include "Extractors/CurveTableExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "Extractors/CurveExtractor.h"
#include "Curves/RichCurve.h"
#include "Curves/SimpleCurve.h"
#include "Engine/CurveTable.h"

namespace CurveTableExtractorInternal
{

static FString CurveTableModeToString(const ECurveTableMode CurveTableMode)
{
	switch (CurveTableMode)
	{
	case ECurveTableMode::SimpleCurves:
		return TEXT("SimpleCurves");
	case ECurveTableMode::RichCurves:
		return TEXT("RichCurves");
	default:
		return TEXT("Empty");
	}
}

} // namespace CurveTableExtractorInternal

TSharedPtr<FJsonObject> FCurveTableExtractor::Extract(const UCurveTable* CurveTable)
{
	if (!CurveTable)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> CurveTableObject = MakeShared<FJsonObject>();
	CurveTableObject->SetStringField(TEXT("assetPath"), CurveTable->GetPathName());
	CurveTableObject->SetStringField(TEXT("assetName"), CurveTable->GetName());
	CurveTableObject->SetStringField(TEXT("curveTableMode"), CurveTableExtractorInternal::CurveTableModeToString(CurveTable->GetCurveTableMode()));
	CurveTableObject->SetNumberField(TEXT("rowCount"), CurveTable->GetRowMap().Num());

	TArray<TSharedPtr<FJsonValue>> Rows;
	if (CurveTable->GetCurveTableMode() == ECurveTableMode::RichCurves)
	{
		for (const TPair<FName, FRichCurve*>& RowPair : CurveTable->GetRichCurveRowMap())
		{
			TSharedPtr<FJsonObject> RowObject = MakeShared<FJsonObject>();
			RowObject->SetStringField(TEXT("rowName"), RowPair.Key.ToString());
			if (RowPair.Value)
			{
				RowObject->SetObjectField(TEXT("curve"), FCurveExtractor::SerializeRichCurve(*RowPair.Value));
			}
			Rows.Add(MakeShared<FJsonValueObject>(RowObject));
		}
	}
	else if (CurveTable->GetCurveTableMode() == ECurveTableMode::SimpleCurves)
	{
		for (const TPair<FName, FSimpleCurve*>& RowPair : CurveTable->GetSimpleCurveRowMap())
		{
			TSharedPtr<FJsonObject> RowObject = MakeShared<FJsonObject>();
			RowObject->SetStringField(TEXT("rowName"), RowPair.Key.ToString());
			if (RowPair.Value)
			{
				RowObject->SetObjectField(TEXT("curve"), FCurveExtractor::SerializeSimpleCurve(*RowPair.Value));
			}
			Rows.Add(MakeShared<FJsonValueObject>(RowObject));
		}
	}

	CurveTableObject->SetArrayField(TEXT("rows"), Rows);
	Root->SetObjectField(TEXT("curveTable"), CurveTableObject);
	return Root;
}
