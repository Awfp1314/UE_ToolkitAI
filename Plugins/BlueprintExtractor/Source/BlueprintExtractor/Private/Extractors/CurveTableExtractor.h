#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UCurveTable;

struct FCurveTableExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UCurveTable* CurveTable);
};
