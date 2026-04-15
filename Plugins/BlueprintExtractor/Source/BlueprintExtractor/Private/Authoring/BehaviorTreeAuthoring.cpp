#include "Authoring/BehaviorTreeAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"
#include "PropertySerializer.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "BehaviorTree/BlackboardData.h"
#include "BehaviorTree/BTAuxiliaryNode.h"
#include "BehaviorTree/BTCompositeNode.h"
#include "BehaviorTree/BTDecorator.h"
#include "BehaviorTree/BTService.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/Composites/BTComposite_Selector.h"
#include "BehaviorTree/Composites/BTComposite_SimpleParallel.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace BehaviorTreeAuthoringInternal
{

struct FNodeSelector
{
	FString NodePath;
};

static TSharedPtr<FJsonObject> NormalizePayload(const TSharedPtr<FJsonObject>& PayloadJson)
{
	if (!PayloadJson.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TSharedPtr<FJsonObject>* NestedPayload = nullptr;
	if (PayloadJson->TryGetObjectField(TEXT("behaviorTree"), NestedPayload)
		&& NestedPayload
		&& NestedPayload->IsValid())
	{
		return *NestedPayload;
	}

	return PayloadJson;
}

static bool AppendValidationSummary(FAssetMutationContext& Context,
                                    const TArray<FString>& Errors,
                                    const FString& Summary)
{
	const bool bSuccess = Errors.Num() == 0;
	Context.SetValidationSummary(bSuccess, Summary, Errors);
	for (const FString& Error : Errors)
	{
		Context.AddError(TEXT("validation_error"), Error, Context.AssetPath);
	}
	return bSuccess;
}

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

static bool ParseDecoratorLogicOperation(const FString& OperationString,
                                         EBTDecoratorLogic::Type& OutOperation)
{
	if (OperationString.Equals(TEXT("Test"), ESearchCase::IgnoreCase))
	{
		OutOperation = EBTDecoratorLogic::Test;
		return true;
	}
	if (OperationString.Equals(TEXT("And"), ESearchCase::IgnoreCase))
	{
		OutOperation = EBTDecoratorLogic::And;
		return true;
	}
	if (OperationString.Equals(TEXT("Or"), ESearchCase::IgnoreCase))
	{
		OutOperation = EBTDecoratorLogic::Or;
		return true;
	}
	if (OperationString.Equals(TEXT("Not"), ESearchCase::IgnoreCase))
	{
		OutOperation = EBTDecoratorLogic::Not;
		return true;
	}
	return false;
}

static UBlackboardData* ResolveBlackboardAsset(const FString& BlackboardPath,
                                               TArray<FString>& OutErrors)
{
	if (BlackboardPath.IsEmpty())
	{
		return nullptr;
	}

	UBlackboardData* BlackboardData = LoadObject<UBlackboardData>(nullptr, *BlackboardPath);
	if (!BlackboardData)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to resolve blackboard asset '%s'."),
			*BlackboardPath));
	}
	return BlackboardData;
}

static bool ApplyNodeFields(UBTNode* Node,
                            const TSharedPtr<FJsonObject>& NodeObject,
                            TArray<FString>& OutErrors,
                            const bool bValidationOnly)
{
	if (!Node || !NodeObject.IsValid())
	{
		OutErrors.Add(TEXT("BehaviorTree node payload must be an object."));
		return false;
	}

	FString NodeName;
	if (NodeObject->TryGetStringField(TEXT("nodeName"), NodeName)
		&& !NodeName.IsEmpty())
	{
		Node->NodeName = NodeName;
	}

	const TSharedPtr<FJsonObject>* PropertiesObject = nullptr;
	if (NodeObject->TryGetObjectField(TEXT("properties"), PropertiesObject)
		&& PropertiesObject
		&& PropertiesObject->IsValid())
	{
		return FPropertySerializer::ApplyPropertiesFromJson(
			Node,
			*PropertiesObject,
			OutErrors,
			bValidationOnly,
			true);
	}

	return true;
}

static UBTNode* CreateNode(UBehaviorTree* BehaviorTree,
                           const TSharedPtr<FJsonObject>& NodeObject,
                           UClass* RequiredBaseClass,
                           TArray<FString>& OutErrors)
{
	if (!BehaviorTree || !NodeObject.IsValid())
	{
		OutErrors.Add(TEXT("BehaviorTree node payload must be an object."));
		return nullptr;
	}

	FString NodeClassPath;
	if (!NodeObject->TryGetStringField(TEXT("nodeClassPath"), NodeClassPath)
		|| NodeClassPath.IsEmpty())
	{
		OutErrors.Add(TEXT("BehaviorTree nodeClassPath is required."));
		return nullptr;
	}

	UClass* NodeClass = FAuthoringHelpers::ResolveClass(NodeClassPath, RequiredBaseClass);
	if (!NodeClass)
	{
		OutErrors.Add(FString::Printf(
			TEXT("Failed to resolve BehaviorTree node class '%s'."),
			*NodeClassPath));
		return nullptr;
	}

	return NewObject<UBTNode>(
		BehaviorTree,
		NodeClass,
		MakeUniqueObjectName(BehaviorTree, NodeClass, NodeClass->GetFName()));
}

static bool BuildDecoratorLogicArray(const TSharedPtr<FJsonObject>& OwnerObject,
                                     TArray<FBTDecoratorLogic>& OutLogic,
                                     TArray<FString>& OutErrors)
{
	const TArray<TSharedPtr<FJsonValue>>* LogicArray = nullptr;
	if (!OwnerObject.IsValid()
		|| !OwnerObject->TryGetArrayField(TEXT("decoratorLogic"), LogicArray)
		|| !LogicArray)
	{
		return true;
	}

	for (int32 Index = 0; Index < LogicArray->Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> LogicObject =
			(*LogicArray)[Index].IsValid() ? (*LogicArray)[Index]->AsObject() : nullptr;
		if (!LogicObject.IsValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("decoratorLogic[%d] must be an object."),
				Index));
			continue;
		}

		FString OperationString;
		int32 Number = 0;
		if (!LogicObject->TryGetStringField(TEXT("operation"), OperationString))
		{
			OutErrors.Add(FString::Printf(
				TEXT("decoratorLogic[%d].operation is required."),
				Index));
			continue;
		}
		if (!LogicObject->TryGetNumberField(TEXT("number"), Number))
		{
			OutErrors.Add(FString::Printf(
				TEXT("decoratorLogic[%d].number is required."),
				Index));
			continue;
		}

		EBTDecoratorLogic::Type Operation = EBTDecoratorLogic::Invalid;
		if (!ParseDecoratorLogicOperation(OperationString, Operation))
		{
			OutErrors.Add(FString::Printf(
				TEXT("decoratorLogic[%d] has unsupported operation '%s'."),
				Index,
				*OperationString));
			continue;
		}

		OutLogic.Emplace(static_cast<uint8>(Operation), static_cast<uint16>(Number));
	}

	return OutErrors.Num() == 0;
}

static bool BuildServiceArray(UBehaviorTree* BehaviorTree,
                              const TSharedPtr<FJsonObject>& OwnerObject,
                              TArray<TObjectPtr<UBTService>>& OutServices,
                              TArray<FString>& OutErrors,
                              const bool bValidationOnly);

static UBTNode* BuildNodeRecursive(UBehaviorTree* BehaviorTree,
                                   const TSharedPtr<FJsonObject>& NodeObject,
                                   TArray<FString>& OutErrors,
                                   const bool bValidationOnly);

static bool BuildDecoratorArray(UBehaviorTree* BehaviorTree,
                                const TSharedPtr<FJsonObject>& OwnerObject,
                                TArray<TObjectPtr<UBTDecorator>>& OutDecorators,
                                TArray<FString>& OutErrors,
                                const bool bValidationOnly)
{
	const TArray<TSharedPtr<FJsonValue>>* Decorators = nullptr;
	if (!OwnerObject.IsValid()
		|| !OwnerObject->TryGetArrayField(TEXT("decorators"), Decorators)
		|| !Decorators)
	{
		return true;
	}

	for (int32 Index = 0; Index < Decorators->Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> DecoratorObject =
			(*Decorators)[Index].IsValid() ? (*Decorators)[Index]->AsObject() : nullptr;
		UBTNode* DecoratorNode = BuildNodeRecursive(
			BehaviorTree,
			DecoratorObject,
			OutErrors,
			bValidationOnly);
		UBTDecorator* Decorator = Cast<UBTDecorator>(DecoratorNode);
		if (!Decorator)
		{
			OutErrors.Add(FString::Printf(
				TEXT("decorators[%d] must resolve to a decorator node."),
				Index));
			continue;
		}
		OutDecorators.Add(Decorator);
	}

	return OutErrors.Num() == 0;
}

static bool BuildChildBranch(UBehaviorTree* BehaviorTree,
                             const TSharedPtr<FJsonObject>& ChildObject,
                             FBTCompositeChild& OutChild,
                             TArray<FString>& OutErrors,
                             const bool bValidationOnly)
{
	UBTNode* ChildNode = BuildNodeRecursive(
		BehaviorTree,
		ChildObject,
		OutErrors,
		bValidationOnly);
	if (!ChildNode)
	{
		return false;
	}

	if (UBTCompositeNode* ChildComposite = Cast<UBTCompositeNode>(ChildNode))
	{
		OutChild.ChildComposite = ChildComposite;
	}
	else if (UBTTaskNode* ChildTask = Cast<UBTTaskNode>(ChildNode))
	{
		OutChild.ChildTask = ChildTask;
	}
	else
	{
		OutErrors.Add(TEXT("BehaviorTree child nodes must be composite or task nodes."));
		return false;
	}

	BuildDecoratorArray(
		BehaviorTree,
		ChildObject,
		OutChild.Decorators,
		OutErrors,
		bValidationOnly);
	BuildDecoratorLogicArray(ChildObject, OutChild.DecoratorOps, OutErrors);
	return OutErrors.Num() == 0;
}

static bool BuildCompositeChildren(UBehaviorTree* BehaviorTree,
                                   UBTCompositeNode* CompositeNode,
                                   const TSharedPtr<FJsonObject>& NodeObject,
                                   TArray<FString>& OutErrors,
                                   const bool bValidationOnly)
{
	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (!NodeObject.IsValid()
		|| !NodeObject->TryGetArrayField(TEXT("children"), Children)
		|| !Children)
	{
		return true;
	}

	for (int32 ChildIndex = 0; ChildIndex < Children->Num(); ++ChildIndex)
	{
		const TSharedPtr<FJsonObject> ChildObject =
			(*Children)[ChildIndex].IsValid() ? (*Children)[ChildIndex]->AsObject() : nullptr;
		FBTCompositeChild& Child = CompositeNode->Children.AddDefaulted_GetRef();
		if (!BuildChildBranch(
			    BehaviorTree,
			    ChildObject,
			    Child,
			    OutErrors,
			    bValidationOnly))
		{
			CompositeNode->Children.Pop();
		}
	}

	if (UBTComposite_SimpleParallel* SimpleParallel = Cast<UBTComposite_SimpleParallel>(CompositeNode))
	{
		const bool bValidLayout =
			SimpleParallel->Children.Num() == 2
			&& SimpleParallel->Children[0].ChildTask != nullptr
			&& SimpleParallel->Children[1].ChildComposite != nullptr;
		if (!bValidLayout)
		{
			OutErrors.Add(TEXT("BTComposite_SimpleParallel requires exactly two children: task first, composite second."));
		}
	}

	return OutErrors.Num() == 0;
}

static bool BuildServiceArray(UBehaviorTree* BehaviorTree,
                              const TSharedPtr<FJsonObject>& OwnerObject,
                              TArray<TObjectPtr<UBTService>>& OutServices,
                              TArray<FString>& OutErrors,
                              const bool bValidationOnly)
{
	const TArray<TSharedPtr<FJsonValue>>* Services = nullptr;
	if (!OwnerObject.IsValid()
		|| !OwnerObject->TryGetArrayField(TEXT("services"), Services)
		|| !Services)
	{
		return true;
	}

	for (int32 Index = 0; Index < Services->Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> ServiceObject =
			(*Services)[Index].IsValid() ? (*Services)[Index]->AsObject() : nullptr;
		UBTNode* ServiceNode = BuildNodeRecursive(
			BehaviorTree,
			ServiceObject,
			OutErrors,
			bValidationOnly);
		UBTService* Service = Cast<UBTService>(ServiceNode);
		if (!Service)
		{
			OutErrors.Add(FString::Printf(
				TEXT("services[%d] must resolve to a service node."),
				Index));
			continue;
		}
		OutServices.Add(Service);
	}

	return OutErrors.Num() == 0;
}

static UBTNode* BuildNodeRecursive(UBehaviorTree* BehaviorTree,
                                   const TSharedPtr<FJsonObject>& NodeObject,
                                   TArray<FString>& OutErrors,
                                   const bool bValidationOnly)
{
	UBTNode* Node = CreateNode(
		BehaviorTree,
		NodeObject,
		UBTNode::StaticClass(),
		OutErrors);
	if (!Node)
	{
		return nullptr;
	}

	if (!ApplyNodeFields(Node, NodeObject, OutErrors, bValidationOnly))
	{
		return nullptr;
	}

	if (UBTCompositeNode* CompositeNode = Cast<UBTCompositeNode>(Node))
	{
		BuildServiceArray(
			BehaviorTree,
			NodeObject,
			CompositeNode->Services,
			OutErrors,
			bValidationOnly);
		BuildCompositeChildren(
			BehaviorTree,
			CompositeNode,
			NodeObject,
			OutErrors,
			bValidationOnly);
	}
	else if (UBTTaskNode* TaskNode = Cast<UBTTaskNode>(Node))
	{
		BuildServiceArray(
			BehaviorTree,
			NodeObject,
			TaskNode->Services,
			OutErrors,
			bValidationOnly);
		if (NodeObject->HasField(TEXT("children")))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Task node '%s' cannot define children."),
				*TaskNode->GetClass()->GetName()));
		}
	}
	else
	{
		if (NodeObject->HasField(TEXT("children")) || NodeObject->HasField(TEXT("services")))
		{
			OutErrors.Add(FString::Printf(
				TEXT("Node '%s' cannot own children or services."),
				*Node->GetClass()->GetName()));
		}
	}

	return Node;
}

static UBTCompositeNode* CreateDefaultRoot(UBehaviorTree* BehaviorTree)
{
	return NewObject<UBTComposite_Selector>(
		BehaviorTree,
		MakeUniqueObjectName(
			BehaviorTree,
			UBTComposite_Selector::StaticClass(),
			TEXT("BTRoot")));
}

static bool BuildFullTree(UBehaviorTree* BehaviorTree,
                          const TSharedPtr<FJsonObject>& Payload,
                          TArray<FString>& OutErrors,
                          const bool bValidationOnly)
{
	if (!BehaviorTree)
	{
		OutErrors.Add(TEXT("BehaviorTree is null."));
		return false;
	}

	FString BlackboardPath;
	if (Payload.IsValid() && Payload->TryGetStringField(TEXT("blackboardAsset"), BlackboardPath))
	{
		BehaviorTree->BlackboardAsset = ResolveBlackboardAsset(BlackboardPath, OutErrors);
	}

	const TSharedPtr<FJsonObject>* RootNodeObject = nullptr;
	if (Payload.IsValid()
		&& Payload->TryGetObjectField(TEXT("rootNode"), RootNodeObject)
		&& RootNodeObject
		&& RootNodeObject->IsValid())
	{
		UBTNode* RootNode = BuildNodeRecursive(
			BehaviorTree,
			*RootNodeObject,
			OutErrors,
			bValidationOnly);
		BehaviorTree->RootNode = Cast<UBTCompositeNode>(RootNode);
		if (!BehaviorTree->RootNode)
		{
			OutErrors.Add(TEXT("BehaviorTree rootNode must resolve to a composite node."));
			return false;
		}

		BehaviorTree->RootDecorators.Reset();
		BehaviorTree->RootDecoratorOps.Reset();
		BuildDecoratorArray(
			BehaviorTree,
			*RootNodeObject,
			BehaviorTree->RootDecorators,
			OutErrors,
			bValidationOnly);
		BuildDecoratorLogicArray(*RootNodeObject, BehaviorTree->RootDecoratorOps, OutErrors);
	}
	else
	{
		BehaviorTree->RootNode = CreateDefaultRoot(BehaviorTree);
		BehaviorTree->RootDecorators.Reset();
		BehaviorTree->RootDecoratorOps.Reset();
	}

	return OutErrors.Num() == 0;
}

static bool ValidateNodeAfterInitialization(UBTNode* Node,
                                            const FString& NodePath,
                                            TArray<FString>& OutErrors)
{
	if (!Node)
	{
		return false;
	}

#if WITH_EDITOR
	if (const FString ErrorMessage = Node->GetErrorMessage(); !ErrorMessage.IsEmpty())
	{
		OutErrors.Add(FString::Printf(
			TEXT("%s: %s"),
			*NodePath,
			*ErrorMessage));
	}

	if (UBTDecorator* Decorator = Cast<UBTDecorator>(Node))
	{
		if (!Decorator->IsFlowAbortModeValid())
		{
			OutErrors.Add(FString::Printf(
				TEXT("%s: decorator flow abort mode is invalid."),
				*NodePath));
		}
	}
#endif

	return true;
}

static uint16 InitializeRuntimeNode(UBehaviorTree* BehaviorTree,
                                    UBTNode* Node,
                                    UBTCompositeNode* ParentNode,
                                    const int32 ParentChildIndex,
                                    const uint8 TreeDepth,
                                    uint16& NextExecutionIndex,
                                    const FString& NodePath,
                                    TArray<FString>& OutErrors)
{
	if (!Node || !BehaviorTree)
	{
		return NextExecutionIndex;
	}

	const uint16 ThisExecutionIndex = NextExecutionIndex++;
	Node->InitializeNode(ParentNode, ThisExecutionIndex, 0, TreeDepth);
	Node->InitializeFromAsset(*BehaviorTree);

	if (UBTAuxiliaryNode* AuxiliaryNode = Cast<UBTAuxiliaryNode>(Node))
	{
		if (ParentChildIndex != INDEX_NONE)
		{
			AuxiliaryNode->InitializeParentLink(static_cast<uint8>(ParentChildIndex));
		}
	}

	ValidateNodeAfterInitialization(Node, NodePath, OutErrors);

	if (UBTCompositeNode* CompositeNode = Cast<UBTCompositeNode>(Node))
	{
		for (int32 ServiceIndex = 0; ServiceIndex < CompositeNode->Services.Num(); ++ServiceIndex)
		{
			const FString ServicePath = FString::Printf(
				TEXT("%s.services[%d]"),
				*NodePath,
				ServiceIndex);
			InitializeRuntimeNode(
				BehaviorTree,
				CompositeNode->Services[ServiceIndex],
				CompositeNode,
				INDEX_NONE,
				TreeDepth,
				NextExecutionIndex,
				ServicePath,
				OutErrors);
		}

		for (int32 ChildIndex = 0; ChildIndex < CompositeNode->Children.Num(); ++ChildIndex)
		{
			FBTCompositeChild& Child = CompositeNode->Children[ChildIndex];
			const FString ChildPath = FString::Printf(
				TEXT("%s.children[%d]"),
				*NodePath,
				ChildIndex);

			for (int32 DecoratorIndex = 0; DecoratorIndex < Child.Decorators.Num(); ++DecoratorIndex)
			{
				const FString DecoratorPath = FString::Printf(
					TEXT("%s.decorators[%d]"),
					*ChildPath,
					DecoratorIndex);
				InitializeRuntimeNode(
					BehaviorTree,
					Child.Decorators[DecoratorIndex],
					CompositeNode,
					ChildIndex,
					TreeDepth,
					NextExecutionIndex,
					DecoratorPath,
					OutErrors);
			}

			if (Child.ChildComposite)
			{
				InitializeRuntimeNode(
					BehaviorTree,
					Child.ChildComposite,
					CompositeNode,
					ChildIndex,
					TreeDepth + 1,
					NextExecutionIndex,
					ChildPath,
					OutErrors);
			}
			else if (Child.ChildTask)
			{
				InitializeRuntimeNode(
					BehaviorTree,
					Child.ChildTask,
					CompositeNode,
					ChildIndex,
					TreeDepth + 1,
					NextExecutionIndex,
					ChildPath,
					OutErrors);
			}
		}

		CompositeNode->InitializeComposite(
			NextExecutionIndex > 0 ? static_cast<uint16>(NextExecutionIndex - 1) : ThisExecutionIndex);
	}
	else if (UBTTaskNode* TaskNode = Cast<UBTTaskNode>(Node))
	{
		for (int32 ServiceIndex = 0; ServiceIndex < TaskNode->Services.Num(); ++ServiceIndex)
		{
			const FString ServicePath = FString::Printf(
				TEXT("%s.services[%d]"),
				*NodePath,
				ServiceIndex);
			InitializeRuntimeNode(
				BehaviorTree,
				TaskNode->Services[ServiceIndex],
				ParentNode,
				ParentChildIndex,
				TreeDepth,
				NextExecutionIndex,
				ServicePath,
				OutErrors);
		}
	}

	return ThisExecutionIndex;
}

static bool FinalizeBehaviorTree(UBehaviorTree* BehaviorTree,
                                 TArray<FString>& OutErrors,
                                 const bool bValidationOnly)
{
	if (!BehaviorTree)
	{
		OutErrors.Add(TEXT("BehaviorTree is null."));
		return false;
	}

	if (!BehaviorTree->RootNode)
	{
		OutErrors.Add(TEXT("BehaviorTree root node is required."));
		return false;
	}

	uint16 NextExecutionIndex = 0;
	InitializeRuntimeNode(
		BehaviorTree,
		BehaviorTree->RootNode,
		nullptr,
		INDEX_NONE,
		0,
		NextExecutionIndex,
		TEXT("root"),
		OutErrors);

	for (int32 DecoratorIndex = 0; DecoratorIndex < BehaviorTree->RootDecorators.Num(); ++DecoratorIndex)
	{
		const FString DecoratorPath = FString::Printf(
			TEXT("root.decorators[%d]"),
			DecoratorIndex);
		InitializeRuntimeNode(
			BehaviorTree,
			BehaviorTree->RootDecorators[DecoratorIndex],
			nullptr,
			INDEX_NONE,
			0,
			NextExecutionIndex,
			DecoratorPath,
			OutErrors);
	}

#if WITH_EDITOR
	if (!bValidationOnly)
	{
		BehaviorTree->PostEditChange();
	}
#endif

	return OutErrors.Num() == 0;
}

static void BuildPathMapForNode(UBTNode* Node,
                                const FString& NodePath,
                                TMap<FString, UBTNode*>& OutNodes)
{
	if (!Node)
	{
		return;
	}

	OutNodes.Add(NodePath, Node);

	if (UBTCompositeNode* CompositeNode = Cast<UBTCompositeNode>(Node))
	{
		for (int32 ServiceIndex = 0; ServiceIndex < CompositeNode->Services.Num(); ++ServiceIndex)
		{
			BuildPathMapForNode(
				CompositeNode->Services[ServiceIndex],
				FString::Printf(TEXT("%s.services[%d]"), *NodePath, ServiceIndex),
				OutNodes);
		}

		for (int32 ChildIndex = 0; ChildIndex < CompositeNode->Children.Num(); ++ChildIndex)
		{
			FBTCompositeChild& Child = CompositeNode->Children[ChildIndex];
			const FString ChildPath = FString::Printf(
				TEXT("%s.children[%d]"),
				*NodePath,
				ChildIndex);

			for (int32 DecoratorIndex = 0; DecoratorIndex < Child.Decorators.Num(); ++DecoratorIndex)
			{
				BuildPathMapForNode(
					Child.Decorators[DecoratorIndex],
					FString::Printf(TEXT("%s.decorators[%d]"), *ChildPath, DecoratorIndex),
					OutNodes);
			}

			if (Child.ChildComposite)
			{
				BuildPathMapForNode(Child.ChildComposite, ChildPath, OutNodes);
			}
			else if (Child.ChildTask)
			{
				BuildPathMapForNode(Child.ChildTask, ChildPath, OutNodes);
			}
		}
	}
	else if (UBTTaskNode* TaskNode = Cast<UBTTaskNode>(Node))
	{
		for (int32 ServiceIndex = 0; ServiceIndex < TaskNode->Services.Num(); ++ServiceIndex)
		{
			BuildPathMapForNode(
				TaskNode->Services[ServiceIndex],
				FString::Printf(TEXT("%s.services[%d]"), *NodePath, ServiceIndex),
				OutNodes);
		}
	}
}

static void BuildTreePathMap(UBehaviorTree* BehaviorTree, TMap<FString, UBTNode*>& OutNodes)
{
	if (!BehaviorTree || !BehaviorTree->RootNode)
	{
		return;
	}

	BuildPathMapForNode(BehaviorTree->RootNode, TEXT("root"), OutNodes);
	for (int32 DecoratorIndex = 0; DecoratorIndex < BehaviorTree->RootDecorators.Num(); ++DecoratorIndex)
	{
		BuildPathMapForNode(
			BehaviorTree->RootDecorators[DecoratorIndex],
			FString::Printf(TEXT("root.decorators[%d]"), DecoratorIndex),
			OutNodes);
	}
}

static bool BuildNodeSelector(const TSharedPtr<FJsonObject>& Payload,
                              FNodeSelector& OutSelector,
                              FString& OutError)
{
	if (!Payload.IsValid())
	{
		OutError = TEXT("Node selector payload must be an object.");
		return false;
	}

	if ((Payload->TryGetStringField(TEXT("nodePath"), OutSelector.NodePath)
		 || Payload->TryGetStringField(TEXT("attachmentPath"), OutSelector.NodePath))
		&& !OutSelector.NodePath.IsEmpty())
	{
		return true;
	}

	OutError = TEXT("BehaviorTree node selector requires nodePath or attachmentPath.");
	return false;
}

static bool PatchSelectedNode(UBehaviorTree* BehaviorTree,
                              const TSharedPtr<FJsonObject>& Payload,
                              TArray<FString>& OutErrors,
                              const bool bValidationOnly)
{
	const TSharedPtr<FJsonObject>* NodeObject = nullptr;
	TSharedPtr<FJsonObject> EffectivePayload = Payload;
	if (Payload.IsValid()
		&& Payload->TryGetObjectField(TEXT("node"), NodeObject)
		&& NodeObject
		&& NodeObject->IsValid())
	{
		EffectivePayload = *NodeObject;
	}
	else if (Payload.IsValid()
		&& Payload->TryGetObjectField(TEXT("attachment"), NodeObject)
		&& NodeObject
		&& NodeObject->IsValid())
	{
		EffectivePayload = *NodeObject;
	}

	FNodeSelector Selector;
	FString SelectorError;
	if (!BuildNodeSelector(EffectivePayload, Selector, SelectorError))
	{
		OutErrors.Add(SelectorError);
		return false;
	}

	TMap<FString, UBTNode*> NodeMap;
	BuildTreePathMap(BehaviorTree, NodeMap);
	UBTNode** ExistingNode = NodeMap.Find(Selector.NodePath);
	if (!ExistingNode || !*ExistingNode)
	{
		OutErrors.Add(FString::Printf(
			TEXT("BehaviorTree nodePath '%s' was not found."),
			*Selector.NodePath));
		return false;
	}

	if (!ApplyNodeFields(*ExistingNode, EffectivePayload, OutErrors, bValidationOnly))
	{
		return false;
	}

	return FinalizeBehaviorTree(BehaviorTree, OutErrors, bValidationOnly);
}

static bool SetBlackboard(UBehaviorTree* BehaviorTree,
                          const TSharedPtr<FJsonObject>& Payload,
                          TArray<FString>& OutErrors,
                          const bool bValidationOnly)
{
	if (!BehaviorTree || !Payload.IsValid())
	{
		OutErrors.Add(TEXT("set_blackboard payload must be an object."));
		return false;
	}

	FString BlackboardPath;
	Payload->TryGetStringField(TEXT("blackboardAsset"), BlackboardPath);
	if (BlackboardPath.IsEmpty())
	{
		Payload->TryGetStringField(TEXT("blackboardPath"), BlackboardPath);
	}

	BehaviorTree->BlackboardAsset = ResolveBlackboardAsset(BlackboardPath, OutErrors);
	return FinalizeBehaviorTree(BehaviorTree, OutErrors, bValidationOnly);
}

static bool ApplyOperation(UBehaviorTree* BehaviorTree,
                           const FString& Operation,
                           const TSharedPtr<FJsonObject>& Payload,
                           TArray<FString>& OutErrors,
                           const bool bValidationOnly)
{
	if (Operation == TEXT("replace_tree"))
	{
		BehaviorTree->RootNode = nullptr;
		BehaviorTree->RootDecorators.Reset();
		BehaviorTree->RootDecoratorOps.Reset();
		if (!BuildFullTree(BehaviorTree, Payload, OutErrors, bValidationOnly))
		{
			return false;
		}
		return FinalizeBehaviorTree(BehaviorTree, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("patch_node") || Operation == TEXT("patch_attachment"))
	{
		return PatchSelectedNode(BehaviorTree, Payload, OutErrors, bValidationOnly);
	}
	if (Operation == TEXT("set_blackboard"))
	{
		return SetBlackboard(BehaviorTree, Payload, OutErrors, bValidationOnly);
	}

	OutErrors.Add(FString::Printf(
		TEXT("Unsupported BehaviorTree operation '%s'."),
		*Operation));
	return false;
}

} // namespace BehaviorTreeAuthoringInternal

TSharedPtr<FJsonObject> FBehaviorTreeAuthoring::Create(const FString& AssetPath,
                                                       const TSharedPtr<FJsonObject>& PayloadJson,
                                                       const bool bValidateOnly)
{
	using namespace BehaviorTreeAuthoringInternal;

	FAssetMutationContext Context(
		TEXT("create_behavior_tree"),
		AssetPath,
		TEXT("BehaviorTree"),
		bValidateOnly);
	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);

	if (DoesAssetExist(AssetPath))
	{
		Context.AddError(
			TEXT("asset_exists"),
			FString::Printf(TEXT("Asset already exists: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	UBehaviorTree* PreviewTree = NewObject<UBehaviorTree>(
		GetTransientPackage(),
		MakeUniqueObjectName(GetTransientPackage(), UBehaviorTree::StaticClass(), TEXT("BTPreview")),
		RF_Transient);
	if (!PreviewTree)
	{
		Context.AddError(
			TEXT("preview_create_failed"),
			TEXT("Failed to create transient BehaviorTree preview."));
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	BuildFullTree(PreviewTree, Payload, ValidationErrors, true);
	FinalizeBehaviorTree(PreviewTree, ValidationErrors, true);

	if (!AppendValidationSummary(
		    Context,
		    ValidationErrors,
		    TEXT("BehaviorTree payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create BehaviorTree")));

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		Context.AddError(
			TEXT("package_create_failed"),
			FString::Printf(TEXT("Failed to create package: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	const FName AssetName = FPackageName::GetShortFName(AssetPath);
	UBehaviorTree* BehaviorTree = NewObject<UBehaviorTree>(
		Package,
		AssetName,
		RF_Public | RF_Standalone | RF_Transactional);
	if (!BehaviorTree)
	{
		Context.AddError(
			TEXT("asset_create_failed"),
			FString::Printf(TEXT("Failed to create BehaviorTree asset: %s"), *AssetPath),
			AssetPath);
		return Context.BuildResult(false);
	}

	BehaviorTree->Modify();

	TArray<FString> ApplyErrors;
	BuildFullTree(BehaviorTree, Payload, ApplyErrors, false);
	FinalizeBehaviorTree(BehaviorTree, ApplyErrors, false);

	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	FAssetRegistryModule::AssetCreated(BehaviorTree);
	BehaviorTree->MarkPackageDirty();
	Context.TrackDirtyObject(BehaviorTree);
	return Context.BuildResult(true);
}

TSharedPtr<FJsonObject> FBehaviorTreeAuthoring::Modify(UBehaviorTree* BehaviorTree,
                                                       const FString& Operation,
                                                       const TSharedPtr<FJsonObject>& PayloadJson,
                                                       const bool bValidateOnly)
{
	using namespace BehaviorTreeAuthoringInternal;

	const FString AssetPath = BehaviorTree ? BehaviorTree->GetPathName() : FString();
	FAssetMutationContext Context(
		TEXT("modify_behavior_tree"),
		AssetPath,
		TEXT("BehaviorTree"),
		bValidateOnly);

	if (!BehaviorTree)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("BehaviorTree is null."));
		return Context.BuildResult(false);
	}

	const TSharedPtr<FJsonObject> Payload = NormalizePayload(PayloadJson);
	UBehaviorTree* WorkingTree = BehaviorTree;
	if (bValidateOnly)
	{
		WorkingTree = DuplicateObject<UBehaviorTree>(
			BehaviorTree,
			GetTransientPackage());
		if (!WorkingTree)
		{
			Context.AddError(
				TEXT("preview_duplicate_failed"),
				TEXT("Failed to duplicate BehaviorTree for validation."));
			return Context.BuildResult(false);
		}
	}

	TArray<FString> ValidationErrors;
	ApplyOperation(WorkingTree, Operation, Payload, ValidationErrors, true);
	if (!AppendValidationSummary(
		    Context,
		    ValidationErrors,
		    TEXT("BehaviorTree payload validated.")))
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		return Context.BuildResult(true);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify BehaviorTree")));
	BehaviorTree->Modify();

	TArray<FString> ApplyErrors;
	ApplyOperation(BehaviorTree, Operation, Payload, ApplyErrors, false);
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, AssetPath);
	}
	if (ApplyErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	BehaviorTree->MarkPackageDirty();
	Context.TrackDirtyObject(BehaviorTree);
	return Context.BuildResult(true);
}
