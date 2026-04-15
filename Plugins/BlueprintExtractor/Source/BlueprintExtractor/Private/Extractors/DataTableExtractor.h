#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UDataTable;

struct FDataTableExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UDataTable* DataTable);
};
