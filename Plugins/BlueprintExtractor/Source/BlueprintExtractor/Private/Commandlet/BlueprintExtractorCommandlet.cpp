#include "Commandlet/BlueprintExtractorCommandlet.h"

#include "BlueprintExtractorSubsystem.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/UnrealType.h"

#include <iostream>
#include <string>

DEFINE_LOG_CATEGORY_STATIC(LogBPECommandlet, Log, All);

UBlueprintExtractorCommandlet::UBlueprintExtractorCommandlet()
{
	IsClient = false;
	IsEditor = true; // Load editor-only assets (DataAssets, Blueprints, etc.)
	IsServer = false;
	LogToConsole = false;
}

int32 UBlueprintExtractorCommandlet::Main(const FString& Params)
{
	UE_LOG(LogBPECommandlet, Log, TEXT("BlueprintExtractor commandlet starting."));

	UBlueprintExtractorSubsystem* Subsystem = NewObject<UBlueprintExtractorSubsystem>();
	if (!IsValid(Subsystem))
	{
		UE_LOG(LogBPECommandlet, Error, TEXT("Failed to create UBlueprintExtractorSubsystem instance."));
		return 1;
	}

	// Signal ready to the MCP CommandletAdapter (first stdout output = ready)
	WriteStdout(TEXT("{\"jsonrpc\":\"2.0\",\"id\":0,\"result\":{\"ready\":true}}"));

	// Read JSON-RPC requests from stdin, one per line
	std::string StdLine;
	while (std::getline(std::cin, StdLine))
	{
		if (StdLine.empty())
		{
			continue;
		}

		const FString Line = UTF8_TO_TCHAR(StdLine.c_str());
		const FString Response = ProcessRequest(Subsystem, Line);
		WriteStdout(Response);
	}

	UE_LOG(LogBPECommandlet, Log, TEXT("BlueprintExtractor commandlet finished (stdin closed)."));
	return 0;
}

void UBlueprintExtractorCommandlet::WriteStdout(const FString& Line)
{
	const FTCHARToUTF8 Utf8(*Line);
	std::cout << Utf8.Get() << std::endl;
	std::cout.flush();
}

FString UBlueprintExtractorCommandlet::ProcessRequest(
	UBlueprintExtractorSubsystem* Subsystem,
	const FString& RequestJson)
{
	// Parse JSON-RPC envelope
	TSharedPtr<FJsonObject> Envelope;
	{
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RequestJson);
		if (!FJsonSerializer::Deserialize(Reader, Envelope) || !Envelope.IsValid())
		{
			return MakeJsonRpcError(-1, TEXT("Failed to parse JSON-RPC request"));
		}
	}

	const int64 Id = static_cast<int64>(Envelope->GetNumberField(TEXT("id")));
	const FString Method = Envelope->GetStringField(TEXT("method"));

	if (Method.IsEmpty())
	{
		return MakeJsonRpcError(Id, TEXT("Missing 'method' field"));
	}

	const TSharedPtr<FJsonObject>* ParamsPtr = nullptr;
	TSharedPtr<FJsonObject> Params;
	if (Envelope->TryGetObjectField(TEXT("params"), ParamsPtr) && ParamsPtr && ParamsPtr->IsValid())
	{
		Params = *ParamsPtr;
	}
	else
	{
		Params = MakeShared<FJsonObject>();
	}

	const FString ResultJson = InvokeViaReflection(Subsystem, Method, Params);
	return MakeJsonRpcResult(Id, ResultJson);
}

FString UBlueprintExtractorCommandlet::InvokeViaReflection(
	UBlueprintExtractorSubsystem* Subsystem,
	const FString& MethodName,
	const TSharedPtr<FJsonObject>& Params)
{
	UFunction* Func = Subsystem->FindFunction(FName(*MethodName));
	if (!Func)
	{
		return FString::Printf(TEXT("{\"error\":\"Method not found: %s\"}"), *MethodName);
	}

	// Allocate parameter buffer
	const int32 ParamsSize = Func->ParmsSize;
	uint8* ParamBuffer = static_cast<uint8*>(FMemory::Malloc(ParamsSize));
	FMemory::Memzero(ParamBuffer, ParamsSize);

	// Initialize default values
	for (TFieldIterator<FProperty> It(Func); It; ++It)
	{
		It->InitializeValue_InContainer(ParamBuffer);
	}

	// Map JSON params to UFUNCTION parameters
	for (TFieldIterator<FProperty> It(Func); It; ++It)
	{
		FProperty* Prop = *It;

		// Skip return value
		if (Prop->HasAnyPropertyFlags(CPF_ReturnParm))
		{
			continue;
		}

		// Skip output parameters
		if (Prop->HasAnyPropertyFlags(CPF_OutParm) && !Prop->HasAnyPropertyFlags(CPF_ReferenceParm))
		{
			continue;
		}

		const FString PropName = Prop->GetName();

		// Try exact name match, then snake_case match
		TSharedPtr<FJsonValue> JsonValue;
		if (Params->HasField(PropName))
		{
			JsonValue = Params->TryGetField(PropName);
		}
		else
		{
			// Try converting snake_case to PascalCase (e.g., asset_path → AssetPath)
			FString PascalName;
			bool bNextUpper = true;
			for (const TCHAR Ch : PropName)
			{
				if (Ch == '_')
				{
					bNextUpper = true;
					continue;
				}
				PascalName += bNextUpper ? FChar::ToUpper(Ch) : Ch;
				bNextUpper = false;
			}
			if (Params->HasField(PascalName))
			{
				JsonValue = Params->TryGetField(PascalName);
			}
		}

		if (!JsonValue.IsValid())
		{
			// Parameter not provided — use default (already initialized)
			continue;
		}

		// Set property value from JSON
		if (const FStrProperty* StrProp = CastField<FStrProperty>(Prop))
		{
			StrProp->SetPropertyValue_InContainer(ParamBuffer, JsonValue->AsString());
		}
		else if (const FBoolProperty* BoolProp = CastField<FBoolProperty>(Prop))
		{
			BoolProp->SetPropertyValue_InContainer(ParamBuffer, JsonValue->AsBool());
		}
		else if (const FIntProperty* IntProp = CastField<FIntProperty>(Prop))
		{
			IntProp->SetPropertyValue_InContainer(ParamBuffer, static_cast<int32>(JsonValue->AsNumber()));
		}
		else if (const FFloatProperty* FloatProp = CastField<FFloatProperty>(Prop))
		{
			FloatProp->SetPropertyValue_InContainer(ParamBuffer, static_cast<float>(JsonValue->AsNumber()));
		}
		else if (const FDoubleProperty* DoubleProp = CastField<FDoubleProperty>(Prop))
		{
			DoubleProp->SetPropertyValue_InContainer(ParamBuffer, JsonValue->AsNumber());
		}
	}

	// Call the function
	Subsystem->ProcessEvent(Func, ParamBuffer);

	// Read return value
	FString ReturnValue;
	for (TFieldIterator<FProperty> It(Func); It; ++It)
	{
		if (It->HasAnyPropertyFlags(CPF_ReturnParm))
		{
			if (const FStrProperty* RetProp = CastField<FStrProperty>(*It))
			{
				ReturnValue = RetProp->GetPropertyValue_InContainer(ParamBuffer);
			}
			break;
		}
	}

	// Cleanup
	for (TFieldIterator<FProperty> It(Func); It; ++It)
	{
		It->DestroyValue_InContainer(ParamBuffer);
	}
	FMemory::Free(ParamBuffer);

	// If the method returned a JSON string, use it directly as the result
	if (ReturnValue.StartsWith(TEXT("{")) || ReturnValue.StartsWith(TEXT("[")))
	{
		return ReturnValue;
	}

	// Wrap non-JSON return values
	if (ReturnValue.IsEmpty())
	{
		return TEXT("{\"success\":true}");
	}

	// Escape for JSON
	FString Escaped = ReturnValue;
	Escaped.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
	Escaped.ReplaceInline(TEXT("\""), TEXT("\\\""));
	return FString::Printf(TEXT("{\"result\":\"%s\"}"), *Escaped);
}

FString UBlueprintExtractorCommandlet::MakeJsonRpcResult(int64 Id, const FString& ResultJson)
{
	return FString::Printf(TEXT("{\"jsonrpc\":\"2.0\",\"id\":%lld,\"result\":%s}"), Id, *ResultJson);
}

FString UBlueprintExtractorCommandlet::MakeJsonRpcError(int64 Id, const FString& Message)
{
	FString Escaped = Message;
	Escaped.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
	Escaped.ReplaceInline(TEXT("\""), TEXT("\\\""));
	return FString::Printf(TEXT("{\"jsonrpc\":\"2.0\",\"id\":%lld,\"error\":\"%s\"}"), Id, *Escaped);
}
