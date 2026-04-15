#include "Extractors/BytecodeExtractor.h"
#include "BlueprintExtractorModule.h"
#include "Engine/Blueprint.h"
#include "Misc/OutputDeviceNull.h"

TSharedPtr<FJsonObject> FBytecodeExtractor::Extract(const UBlueprint* Blueprint)
{
	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();

	if (!Blueprint || !Blueprint->GeneratedClass)
	{
		return Result;
	}

	for (TFieldIterator<UFunction> FuncIt(Blueprint->GeneratedClass, EFieldIteratorFlags::ExcludeSuper); FuncIt; ++FuncIt)
	{
		UFunction* Function = *FuncIt;
		if (!Function || Function->Script.Num() == 0)
		{
			continue;
		}

		const uint8* ScriptPtr = Function->Script.GetData();
		const int32 ScriptSize = Function->Script.Num();

		// Store raw bytecode as hex for lossless extraction
		FString HexBytecode;
		for (int32 i = 0; i < ScriptSize; ++i)
		{
			HexBytecode += FString::Printf(TEXT("%02X"), ScriptPtr[i]);
			if (i < ScriptSize - 1)
			{
				HexBytecode += TEXT(" ");
			}
		}

		TSharedPtr<FJsonObject> FuncObj = MakeShared<FJsonObject>();
		FuncObj->SetStringField(TEXT("bytecodeHex"), HexBytecode);
		FuncObj->SetNumberField(TEXT("bytecodeSize"), ScriptSize);

		Result->SetObjectField(Function->GetName(), FuncObj);
	}

	return Result;
}
