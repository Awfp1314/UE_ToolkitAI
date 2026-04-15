#pragma once

#include "CoreMinimal.h"

class FJsonObject;

namespace BlueprintExtractorLogAccess
{
	void Startup();
	void Shutdown();

	TSharedPtr<FJsonObject> ReadOutputLog(const TSharedPtr<FJsonObject>& Filters, FString& OutError);
	TSharedPtr<FJsonObject> ListMessageLogListings(const TSharedPtr<FJsonObject>& Payload, FString& OutError);
	TSharedPtr<FJsonObject> ReadMessageLog(const FString& ListingName, const TSharedPtr<FJsonObject>& Filters, FString& OutError);
}
