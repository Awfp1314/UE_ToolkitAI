#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UWidgetAnimation;
class UWidgetBlueprint;

struct FWidgetAnimationAuthoring
{
	static TSharedPtr<FJsonObject> Extract(UWidgetBlueprint* WidgetBlueprint,
	                                       const FString& AnimationName);

	static TSharedPtr<FJsonObject> Create(UWidgetBlueprint* WidgetBlueprint,
	                                      const FString& AnimationName,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TSharedPtr<FJsonObject> Modify(UWidgetBlueprint* WidgetBlueprint,
	                                      const FString& AnimationName,
	                                      const FString& Operation,
	                                      const TSharedPtr<FJsonObject>& PayloadJson,
	                                      bool bValidateOnly);

	static TArray<FString> GetSupportedTrackKinds();
};
