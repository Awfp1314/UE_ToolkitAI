#include "Extractors/BehaviorTreeExtractor.h"

#include "BlueprintExtractorVersion.h"
#include "BehaviorTree/BlackboardData.h"
#include "PropertySerializer.h"
#include "BehaviorTree/BTCompositeNode.h"
#include "BehaviorTree/BTDecorator.h"
#include "BehaviorTree/BTNode.h"
#include "BehaviorTree/BTService.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BehaviorTree/BehaviorTree.h"

namespace BehaviorTreeExtractorInternal
{

static FString DecoratorLogicToString(const EBTDecoratorLogic::Type Operation)
{
	switch (Operation)
	{
	case EBTDecoratorLogic::Test:
		return TEXT("Test");
	case EBTDecoratorLogic::And:
		return TEXT("And");
	case EBTDecoratorLogic::Or:
		return TEXT("Or");
	case EBTDecoratorLogic::Not:
		return TEXT("Not");
	default:
		return TEXT("Invalid");
	}
}

static TArray<TSharedPtr<FJsonValue>> MakeDecoratorLogicArray(const TArray<FBTDecoratorLogic>& DecoratorOps)
{
	TArray<TSharedPtr<FJsonValue>> LogicArray;

	for (const FBTDecoratorLogic& DecoratorOp : DecoratorOps)
	{
		TSharedPtr<FJsonObject> LogicObject = MakeShared<FJsonObject>();
		LogicObject->SetStringField(TEXT("operation"), DecoratorLogicToString(DecoratorOp.Operation));
		LogicObject->SetNumberField(TEXT("number"), DecoratorOp.Number);
		LogicArray.Add(MakeShared<FJsonValueObject>(LogicObject));
	}

	return LogicArray;
}

static TSharedPtr<FJsonObject> MakeNodeObject(const UBTNode* Node,
                                              int32& NextNodeIndex,
                                              const FString& NodePath)
{
	if (!Node)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> NodeObject = MakeShared<FJsonObject>();
	NodeObject->SetStringField(TEXT("nodeClass"), Node->GetClass()->GetName());
	NodeObject->SetStringField(TEXT("nodeClassPath"), Node->GetClass()->GetPathName());
	NodeObject->SetStringField(TEXT("nodeName"), Node->GetNodeName());
	NodeObject->SetNumberField(TEXT("nodeIndex"), NextNodeIndex++);
	NodeObject->SetNumberField(TEXT("executionIndex"), Node->GetExecutionIndex());
	NodeObject->SetNumberField(TEXT("treeDepth"), Node->GetTreeDepth());
	NodeObject->SetStringField(TEXT("nodePath"), NodePath);

	const TSharedPtr<FJsonObject> Properties = FPropertySerializer::SerializePropertyOverrides(Node);
	if (Properties.IsValid() && Properties->Values.Num() > 0)
	{
		NodeObject->SetObjectField(TEXT("properties"), Properties);
	}

	return NodeObject;
}

} // namespace BehaviorTreeExtractorInternal

namespace
{

static TSharedPtr<FJsonObject> ExtractNodeAtPath(const UBTNode* Node,
                                                 int32& NextNodeIndex,
                                                 const FString& NodePath);

static TArray<TSharedPtr<FJsonValue>> ExtractTaskServices(const UBTTaskNode* TaskNode,
                                                          int32& NextNodeIndex,
                                                          const FString& NodePath)
{
	TArray<TSharedPtr<FJsonValue>> Services;
	if (!TaskNode)
	{
		return Services;
	}

	for (int32 ServiceIndex = 0; ServiceIndex < TaskNode->Services.Num(); ++ServiceIndex)
	{
		if (const UBTService* Service = TaskNode->Services[ServiceIndex].Get())
		{
			const FString ServicePath = FString::Printf(
				TEXT("%s.services[%d]"),
				*NodePath,
				ServiceIndex);
			if (const TSharedPtr<FJsonObject> ServiceObject =
				    ExtractNodeAtPath(Service, NextNodeIndex, ServicePath))
			{
				Services.Add(MakeShared<FJsonValueObject>(ServiceObject));
			}
		}
	}

	return Services;
}

static TArray<TSharedPtr<FJsonValue>> ExtractDecoratorNodesAtPath(
	const TArray<TObjectPtr<UBTDecorator>>& Decorators,
	int32& NextNodeIndex,
	const FString& OwnerPath)
{
	TArray<TSharedPtr<FJsonValue>> DecoratorArray;

	for (int32 DecoratorIndex = 0; DecoratorIndex < Decorators.Num(); ++DecoratorIndex)
	{
		if (const UBTDecorator* Decorator = Decorators[DecoratorIndex].Get())
		{
			const FString DecoratorPath = FString::Printf(
				TEXT("%s.decorators[%d]"),
				*OwnerPath,
				DecoratorIndex);
			if (const TSharedPtr<FJsonObject> DecoratorObject =
				    ExtractNodeAtPath(Decorator, NextNodeIndex, DecoratorPath))
			{
				DecoratorArray.Add(MakeShared<FJsonValueObject>(DecoratorObject));
			}
		}
	}

	return DecoratorArray;
}

static TSharedPtr<FJsonObject> ExtractCompositeNodeAtPath(const UBTCompositeNode* CompositeNode,
                                                          int32& NextNodeIndex,
                                                          const FString& NodePath)
{
	TSharedPtr<FJsonObject> NodeObject = BehaviorTreeExtractorInternal::MakeNodeObject(
		CompositeNode,
		NextNodeIndex,
		NodePath);
	if (!NodeObject.IsValid())
	{
		return nullptr;
	}

	TArray<TSharedPtr<FJsonValue>> Services;
	for (int32 ServiceIndex = 0; ServiceIndex < CompositeNode->Services.Num(); ++ServiceIndex)
	{
		if (const UBTService* Service = CompositeNode->Services[ServiceIndex].Get())
		{
			const FString ServicePath = FString::Printf(
				TEXT("%s.services[%d]"),
				*NodePath,
				ServiceIndex);
			if (const TSharedPtr<FJsonObject> ServiceObject =
				    ExtractNodeAtPath(Service, NextNodeIndex, ServicePath))
			{
				Services.Add(MakeShared<FJsonValueObject>(ServiceObject));
			}
		}
	}
	NodeObject->SetArrayField(TEXT("services"), Services);

	TArray<TSharedPtr<FJsonValue>> Children;
	for (int32 ChildIndex = 0; ChildIndex < CompositeNode->Children.Num(); ++ChildIndex)
	{
		const FBTCompositeChild& Child = CompositeNode->Children[ChildIndex];
		const UBTNode* ChildNode = Child.ChildComposite
			? static_cast<const UBTNode*>(Child.ChildComposite.Get())
			: static_cast<const UBTNode*>(Child.ChildTask.Get());
		if (!ChildNode)
		{
			continue;
		}

		const FString ChildPath = FString::Printf(
			TEXT("%s.children[%d]"),
			*NodePath,
			ChildIndex);
		const TSharedPtr<FJsonObject> ChildObject =
			ExtractNodeAtPath(ChildNode, NextNodeIndex, ChildPath);
		if (!ChildObject.IsValid())
		{
			continue;
		}

		ChildObject->SetArrayField(
			TEXT("decorators"),
			ExtractDecoratorNodesAtPath(Child.Decorators, NextNodeIndex, ChildPath));
		ChildObject->SetArrayField(
			TEXT("decoratorLogic"),
			BehaviorTreeExtractorInternal::MakeDecoratorLogicArray(Child.DecoratorOps));
		Children.Add(MakeShared<FJsonValueObject>(ChildObject));
	}
	NodeObject->SetArrayField(TEXT("children"), Children);

	return NodeObject;
}

static TSharedPtr<FJsonObject> ExtractNodeAtPath(const UBTNode* Node,
                                                 int32& NextNodeIndex,
                                                 const FString& NodePath)
{
	if (const UBTCompositeNode* CompositeNode = Cast<UBTCompositeNode>(Node))
	{
		return ExtractCompositeNodeAtPath(CompositeNode, NextNodeIndex, NodePath);
	}

	TSharedPtr<FJsonObject> NodeObject = BehaviorTreeExtractorInternal::MakeNodeObject(
		Node,
		NextNodeIndex,
		NodePath);
	if (const UBTTaskNode* TaskNode = Cast<UBTTaskNode>(Node))
	{
		NodeObject->SetArrayField(
			TEXT("services"),
			ExtractTaskServices(TaskNode, NextNodeIndex, NodePath));
	}
	return NodeObject;
}

} // namespace

TSharedPtr<FJsonObject> FBehaviorTreeExtractor::Extract(const UBehaviorTree* BehaviorTree)
{
	if (!BehaviorTree)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schemaVersion"), BlueprintExtractor::SchemaVersion);

	TSharedPtr<FJsonObject> BehaviorTreeObject = MakeShared<FJsonObject>();
	BehaviorTreeObject->SetStringField(TEXT("assetPath"), BehaviorTree->GetPathName());
	BehaviorTreeObject->SetStringField(TEXT("assetName"), BehaviorTree->GetName());

	if (BehaviorTree->BlackboardAsset)
	{
		BehaviorTreeObject->SetStringField(TEXT("blackboardAsset"), BehaviorTree->BlackboardAsset->GetPathName());
	}

	int32 NextNodeIndex = 0;
	if (BehaviorTree->RootNode)
	{
		TSharedPtr<FJsonObject> RootNode = ExtractNodeAtPath(
			BehaviorTree->RootNode,
			NextNodeIndex,
			TEXT("root"));
		if (RootNode.IsValid())
		{
			RootNode->SetArrayField(
				TEXT("decorators"),
				ExtractDecoratorNodesAtPath(BehaviorTree->RootDecorators, NextNodeIndex, TEXT("root")));
			RootNode->SetArrayField(TEXT("decoratorLogic"), ExtractDecoratorLogic(BehaviorTree->RootDecoratorOps));
			BehaviorTreeObject->SetObjectField(TEXT("rootNode"), RootNode);
		}
	}

	Root->SetObjectField(TEXT("behaviorTree"), BehaviorTreeObject);
	return Root;
}

TSharedPtr<FJsonObject> FBehaviorTreeExtractor::ExtractNode(const UBTNode* Node, int32& NextNodeIndex)
{
	if (const UBTCompositeNode* CompositeNode = Cast<UBTCompositeNode>(Node))
	{
		return ExtractCompositeNode(CompositeNode, NextNodeIndex);
	}

	return BehaviorTreeExtractorInternal::MakeNodeObject(Node, NextNodeIndex, TEXT(""));
}

TSharedPtr<FJsonObject> FBehaviorTreeExtractor::ExtractCompositeNode(const UBTCompositeNode* CompositeNode, int32& NextNodeIndex)
{
	return ExtractCompositeNodeAtPath(CompositeNode, NextNodeIndex, TEXT(""));
}

TArray<TSharedPtr<FJsonValue>> FBehaviorTreeExtractor::ExtractDecoratorNodes(const TArray<TObjectPtr<UBTDecorator>>& Decorators, int32& NextNodeIndex)
{
	return ExtractDecoratorNodesAtPath(Decorators, NextNodeIndex, TEXT(""));
}

TArray<TSharedPtr<FJsonValue>> FBehaviorTreeExtractor::ExtractDecoratorLogic(const TArray<FBTDecoratorLogic>& DecoratorOps)
{
	TArray<TSharedPtr<FJsonValue>> LogicArray;
	return BehaviorTreeExtractorInternal::MakeDecoratorLogicArray(DecoratorOps);
}
