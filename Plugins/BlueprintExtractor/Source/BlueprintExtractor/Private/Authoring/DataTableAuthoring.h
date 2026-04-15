#pragma once

#include "CoreMinimal.h"

class FJsonObject;
class FJsonValue;
class UDataTable;

class FDataTableAuthoring
{
public:
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const FString& RowStructPath,
	                                      const TArray<TSharedPtr<FJsonValue>>& Rows,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UDataTable* DataTable,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
