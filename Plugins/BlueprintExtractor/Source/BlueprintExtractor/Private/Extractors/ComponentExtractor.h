#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBlueprint;
class USCS_Node;
class UActorComponent;

struct FComponentExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UBlueprint* Blueprint);

private:
	static TSharedPtr<FJsonObject> ExtractSCSNode(const USCS_Node* Node);
	static TSharedPtr<FJsonObject> ExtractPropertyOverrides(const UActorComponent* ComponentTemplate);
};
