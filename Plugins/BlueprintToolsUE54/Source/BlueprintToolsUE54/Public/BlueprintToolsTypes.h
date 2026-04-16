#pragma once

#include "CoreMinimal.h"
#include "BlueprintToolsTypes.generated.h"

UENUM(BlueprintType)
enum class EBlueprintExtractionScope : uint8
{
	/** Only class-level metadata */
	ClassLevel,
	/** Class + variables */
	Variables,
	/** Class + variables + components */
	Components,
	/** Class + variables + components + function signatures */
	FunctionsShallow,
	/** Full extraction including graphs */
	Full
};
