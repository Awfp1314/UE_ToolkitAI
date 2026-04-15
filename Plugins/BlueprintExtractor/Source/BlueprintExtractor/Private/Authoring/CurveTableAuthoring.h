#pragma once

#include "CoreMinimal.h"

class FJsonObject;
class FJsonValue;
class UCurveTable;

class FCurveTableAuthoring
{
public:
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const FString& CurveTableMode,
	                                      const TArray<TSharedPtr<FJsonValue>>& Rows,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UCurveTable* CurveTable,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
