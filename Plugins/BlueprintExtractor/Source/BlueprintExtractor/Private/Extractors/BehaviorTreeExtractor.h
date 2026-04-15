#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

class UBehaviorTree;
class UBTNode;
class UBTCompositeNode;
class UBTDecorator;
struct FBTDecoratorLogic;

struct FBehaviorTreeExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UBehaviorTree* BehaviorTree);

private:
	static TSharedPtr<FJsonObject> ExtractNode(const UBTNode* Node, int32& NextNodeIndex);
	static TSharedPtr<FJsonObject> ExtractCompositeNode(const UBTCompositeNode* CompositeNode, int32& NextNodeIndex);
	static TArray<TSharedPtr<FJsonValue>> ExtractDecoratorNodes(const TArray<TObjectPtr<UBTDecorator>>& Decorators, int32& NextNodeIndex);
	static TArray<TSharedPtr<FJsonValue>> ExtractDecoratorLogic(const TArray<FBTDecoratorLogic>& DecoratorOps);
};
