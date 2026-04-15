#pragma once

#include "CoreMinimal.h"
#include "BlueprintExtractorTypes.generated.h"

UENUM(BlueprintType)
enum class EBlueprintExtractionScope : uint8
{
	ClassLevel,
	Variables,
	Components,
	FunctionsShallow,
	Full,
	FullWithBytecode
};

UENUM()
enum class EExtractedGraphType : uint8
{
	FunctionGraph,
	EventGraph,
	MacroGraph,
	ConstructionScript,
	AnimGraph,
	Unknown
};
