#pragma once

#include "CoreMinimal.h"

class FJsonObject;
class UCurveBase;

class FCurveAuthoring
{
public:
	static TSharedPtr<FJsonObject> Create(const FString& AssetPath,
	                                      const FString& CurveType,
	                                      const TSharedPtr<FJsonObject>& ChannelsJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UCurveBase* Curve,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);
};
