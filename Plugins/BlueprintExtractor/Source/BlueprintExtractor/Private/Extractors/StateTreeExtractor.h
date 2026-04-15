#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

class UStateTree;
class UStateTreeState;
class UStateTreeEditorData;
struct FStateTreeEditorNode;
struct FStateTreeTransition;
struct FPropertyBindingPath;
class UScriptStruct;

struct FStateTreeExtractor
{
	static TSharedPtr<FJsonObject> Extract(const UStateTree* StateTree);

private:
	static TSharedPtr<FJsonObject> ExtractState(const UStateTreeState* State);
	static TSharedPtr<FJsonObject> ExtractEditorNode(const FStateTreeEditorNode& EditorNode);
	static TSharedPtr<FJsonObject> ExtractTransition(const FStateTreeTransition& Transition);
	static TSharedPtr<FJsonObject> ExtractStructProperties(const UScriptStruct* ScriptStruct, const uint8* Memory);
	static TSharedPtr<FJsonObject> ExtractPropertyPath(const FPropertyBindingPath& Path);
	static TSharedPtr<FJsonObject> ExtractBindings(const UStateTreeEditorData* EditorData);
};
