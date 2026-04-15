#include "Diagnostics/BlueprintExtractorLogAccess.h"

#include "Algo/Reverse.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/CriticalSection.h"
#include "Logging/TokenizedMessage.h"
#include "MessageLogModule.h"
#include "Misc/DateTime.h"
#include "Misc/EngineVersionComparison.h"
#include "Misc/OutputDeviceRedirector.h"
#include "Modules/ModuleManager.h"
#include "Presentation/MessageLogListingViewModel.h"
#include "Serialization/JsonSerializer.h"

namespace
{

constexpr int32 MaxBufferedOutputLogEntries = 10000;
constexpr int32 DefaultReadLimit = 200;
constexpr int32 MaxReadLimit = 1000;

struct FBlueprintExtractorOutputLogEntry
{
	int64 Sequence = 0;
	FString Category;
	FString Verbosity;
	FString Message;
	FString CapturedAtUtc;
	double EngineTime = -1.0;
};

class FBlueprintExtractorOutputLogCollector final : public FOutputDevice
{
public:
	virtual bool CanBeUsedOnAnyThread() const override
	{
		return true;
	}

	virtual void Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& Category) override
	{
		Serialize(V, Verbosity, Category, -1.0);
	}

	virtual void Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& Category, const double Time) override
	{
		if (V == nullptr)
		{
			return;
		}

		FScopeLock Lock(&Mutex);
		FBlueprintExtractorOutputLogEntry Entry;
		Entry.Sequence = NextSequence++;
		Entry.Category = Category.ToString();
		Entry.Verbosity = [Verbosity]()
		{
			switch (Verbosity & ELogVerbosity::VerbosityMask)
			{
			case ELogVerbosity::Fatal:
				return FString(TEXT("fatal"));
			case ELogVerbosity::Error:
				return FString(TEXT("error"));
			case ELogVerbosity::Warning:
				return FString(TEXT("warning"));
			case ELogVerbosity::Display:
				return FString(TEXT("display"));
			case ELogVerbosity::Log:
				return FString(TEXT("log"));
			case ELogVerbosity::Verbose:
				return FString(TEXT("verbose"));
			case ELogVerbosity::VeryVerbose:
				return FString(TEXT("very_verbose"));
			default:
				return FString(TEXT("unknown"));
			}
		}();
		Entry.Message = FString(V);
		Entry.CapturedAtUtc = FDateTime::UtcNow().ToIso8601();
		Entry.EngineTime = Time;

		Entries.Add(MoveTemp(Entry));
		if (Entries.Num() > MaxBufferedOutputLogEntries)
		{
			const int32 RemoveCount = Entries.Num() - MaxBufferedOutputLogEntries;
			Entries.RemoveAt(0, RemoveCount, EAllowShrinking::No);
		}
	}

	TArray<FBlueprintExtractorOutputLogEntry> Snapshot() const
	{
		FScopeLock Lock(&Mutex);
		return Entries;
	}

private:
	mutable FCriticalSection Mutex;
	TArray<FBlueprintExtractorOutputLogEntry> Entries;
	int64 NextSequence = 1;
};

struct FOutputLogReadOptions
{
	FString Query;
	TSet<FString> Categories;
	TSet<FString> Verbosities;
	FDateTime SinceUtc;
	bool bHasSinceUtc = false;
	double SinceSeconds = -1.0;
	int32 Offset = 0;
	int32 Limit = DefaultReadLimit;
	bool bReverse = true;
};

struct FMessageLogReadOptions
{
	FString Query;
	TSet<FString> Severities;
	TSet<FString> TokenTypes;
	int32 Offset = 0;
	int32 Limit = DefaultReadLimit;
	bool bReverse = true;
	bool bIncludeTokens = false;
};

TUniquePtr<FBlueprintExtractorOutputLogCollector> GOutputLogCollector;
FCriticalSection GKnownMessageLogNamesMutex;
TSet<FName> GKnownMessageLogNames;

FString ToLowerCopy(const FString& Value)
{
	FString Result = Value;
	Result.ToLowerInline();
	return Result;
}

TArray<TSharedPtr<FJsonValue>> ToJsonStringArray(const TArray<FString>& Values)
{
	TArray<TSharedPtr<FJsonValue>> Result;
	Result.Reserve(Values.Num());
	for (const FString& Value : Values)
	{
		Result.Add(MakeShared<FJsonValueString>(Value));
	}
	return Result;
}

TArray<FString> ReadStringArrayField(const TSharedPtr<FJsonObject>& Object, const TCHAR* FieldName)
{
	TArray<FString> Result;
	if (!Object.IsValid())
	{
		return Result;
	}

	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Object->TryGetArrayField(FieldName, Values) || Values == nullptr)
	{
		return Result;
	}

	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		FString StringValue;
		if (Value.IsValid() && Value->TryGetString(StringValue) && !StringValue.IsEmpty())
		{
			Result.Add(StringValue);
		}
	}

	return Result;
}

TArray<TSharedPtr<FJsonValue>> ToJsonNameCountArray(const TMap<FString, int32>& Counts)
{
	TArray<FString> Keys;
	Counts.GetKeys(Keys);
	Keys.Sort();

	TArray<TSharedPtr<FJsonValue>> Result;
	Result.Reserve(Keys.Num());
	for (const FString& Key : Keys)
	{
		const int32 Count = Counts.FindRef(Key);
		TSharedPtr<FJsonObject> Item = MakeShared<FJsonObject>();
		Item->SetStringField(TEXT("name"), Key);
		Item->SetNumberField(TEXT("count"), Count);
		Result.Add(MakeShared<FJsonValueObject>(Item));
	}
	return Result;
}

bool MatchesTextQuery(const FString& Haystack, const FString& LowerQuery)
{
	return LowerQuery.IsEmpty() || ToLowerCopy(Haystack).Contains(LowerQuery);
}

bool MatchesSetFilter(const FString& Value, const TSet<FString>& LowerFilterSet)
{
	return LowerFilterSet.Num() == 0 || LowerFilterSet.Contains(ToLowerCopy(Value));
}

FString MessageSeverityToString(const EMessageSeverity::Type Severity)
{
	switch (Severity)
	{
	case EMessageSeverity::Error:
		return TEXT("error");
	case EMessageSeverity::PerformanceWarning:
		return TEXT("performance_warning");
	case EMessageSeverity::Warning:
		return TEXT("warning");
	case EMessageSeverity::Info:
		return TEXT("info");
	default:
		return TEXT("unknown");
	}
}

FString MessageTokenTypeToString(const EMessageToken::Type TokenType)
{
	switch (TokenType)
	{
	case EMessageToken::Action:
		return TEXT("action");
	case EMessageToken::Actor:
		return TEXT("actor");
	case EMessageToken::AssetName:
		return TEXT("asset_name");
	case EMessageToken::AssetData:
		return TEXT("asset_data");
	case EMessageToken::Documentation:
		return TEXT("documentation");
	case EMessageToken::Image:
		return TEXT("image");
	case EMessageToken::Object:
		return TEXT("object");
	case EMessageToken::Severity:
		return TEXT("severity");
	case EMessageToken::Text:
		return TEXT("text");
	case EMessageToken::Tutorial:
		return TEXT("tutorial");
	case EMessageToken::URL:
		return TEXT("url");
	case EMessageToken::EdGraph:
		return TEXT("ed_graph");
	case EMessageToken::DynamicText:
		return TEXT("dynamic_text");
	case EMessageToken::Fix:
		return TEXT("fix");
	default:
		return TEXT("unknown");
	}
}

void SeedKnownMessageLogNames()
{
	FScopeLock Lock(&GKnownMessageLogNamesMutex);
	if (GKnownMessageLogNames.Num() > 0)
	{
		return;
	}

	static const TCHAR* SeedNames[] = {
		TEXT("EditorErrors"),
		TEXT("LoadErrors"),
		TEXT("LightingResults"),
		TEXT("PackagingResults"),
		TEXT("MapCheck"),
		TEXT("AssetCheck"),
		TEXT("SlateStyleLog"),
		TEXT("HLODResults"),
		TEXT("PIE"),
		TEXT("BlueprintLog"),
		TEXT("Blueprint"),
		TEXT("AssetTools"),
		TEXT("SourceControl"),
		TEXT("AutomationTestingLog"),
		TEXT("AssetReimport"),
		TEXT("LogVirtualization"),
		TEXT("TranslationEditor"),
		TEXT("LocalizationService"),
		TEXT("BuildAndSubmitErrors"),
		TEXT("UOL"),
		TEXT("AnimBlueprintLog"),
		TEXT("PackedLevelActor"),
	};

	for (const TCHAR* Name : SeedNames)
	{
		GKnownMessageLogNames.Add(FName(Name));
	}
}

void RememberMessageLogName(const FName& Name)
{
	if (Name.IsNone())
	{
		return;
	}

	FScopeLock Lock(&GKnownMessageLogNamesMutex);
	GKnownMessageLogNames.Add(Name);
}

TArray<FName> BuildCandidateMessageLogNames(const TSharedPtr<FJsonObject>& Payload)
{
	SeedKnownMessageLogNames();

	TSet<FName> Names;
	{
		FScopeLock Lock(&GKnownMessageLogNamesMutex);
		for (const FName& KnownName : GKnownMessageLogNames)
		{
			Names.Add(KnownName);
		}
	}

	for (const FString& Name : ReadStringArrayField(Payload, TEXT("candidate_names")))
	{
		if (!Name.IsEmpty())
		{
			Names.Add(FName(*Name));
		}
	}

	TArray<FName> Result = Names.Array();
	Result.Sort([](const FName& A, const FName& B)
	{
		return A.LexicalLess(B);
	});
	return Result;
}

bool ParseOutputLogReadOptions(const TSharedPtr<FJsonObject>& Filters, FOutputLogReadOptions& OutOptions, FString& OutError)
{
	if (!Filters.IsValid())
	{
		return true;
	}

	Filters->TryGetStringField(TEXT("query"), OutOptions.Query);
	OutOptions.Query = ToLowerCopy(OutOptions.Query);

	for (const FString& Category : ReadStringArrayField(Filters, TEXT("categories")))
	{
		OutOptions.Categories.Add(ToLowerCopy(Category));
	}
	for (const FString& Verbosity : ReadStringArrayField(Filters, TEXT("verbosities")))
	{
		OutOptions.Verbosities.Add(ToLowerCopy(Verbosity));
	}

	Filters->TryGetBoolField(TEXT("reverse"), OutOptions.bReverse);
	Filters->TryGetNumberField(TEXT("since_seconds"), OutOptions.SinceSeconds);

	int32 Offset = OutOptions.Offset;
	if (Filters->TryGetNumberField(TEXT("offset"), Offset))
	{
		OutOptions.Offset = FMath::Max(0, Offset);
	}

	int32 Limit = OutOptions.Limit;
	if (Filters->TryGetNumberField(TEXT("limit"), Limit))
	{
		OutOptions.Limit = FMath::Clamp(Limit, 1, MaxReadLimit);
	}

	FString SinceUtc;
	if (Filters->TryGetStringField(TEXT("since_utc"), SinceUtc) && !SinceUtc.IsEmpty())
	{
		if (!FDateTime::ParseIso8601(*SinceUtc, OutOptions.SinceUtc))
		{
			OutError = FString::Printf(TEXT("Invalid since_utc ISO-8601 timestamp: %s"), *SinceUtc);
			return false;
		}
		OutOptions.bHasSinceUtc = true;
	}

	return true;
}

bool ParseMessageLogReadOptions(const TSharedPtr<FJsonObject>& Filters, FMessageLogReadOptions& OutOptions)
{
	if (!Filters.IsValid())
	{
		return true;
	}

	Filters->TryGetStringField(TEXT("query"), OutOptions.Query);
	OutOptions.Query = ToLowerCopy(OutOptions.Query);

	for (const FString& Severity : ReadStringArrayField(Filters, TEXT("severities")))
	{
		OutOptions.Severities.Add(ToLowerCopy(Severity));
	}
	for (const FString& TokenType : ReadStringArrayField(Filters, TEXT("token_types")))
	{
		OutOptions.TokenTypes.Add(ToLowerCopy(TokenType));
	}

	Filters->TryGetBoolField(TEXT("reverse"), OutOptions.bReverse);
	Filters->TryGetBoolField(TEXT("include_tokens"), OutOptions.bIncludeTokens);

	int32 Offset = OutOptions.Offset;
	if (Filters->TryGetNumberField(TEXT("offset"), Offset))
	{
		OutOptions.Offset = FMath::Max(0, Offset);
	}

	int32 Limit = OutOptions.Limit;
	if (Filters->TryGetNumberField(TEXT("limit"), Limit))
	{
		OutOptions.Limit = FMath::Clamp(Limit, 1, MaxReadLimit);
	}

	return true;
}

TSharedPtr<FJsonObject> BuildMessageTokenJson(const TSharedRef<IMessageToken>& Token)
{
	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetStringField(TEXT("type"), MessageTokenTypeToString(Token->GetType()));
	Result->SetStringField(TEXT("text"), Token->ToText().ToString());
	return Result;
}

bool MessageMatchesTokenTypeFilter(const TSharedRef<FTokenizedMessage>& Message, const TSet<FString>& LowerTokenTypes)
{
	if (LowerTokenTypes.Num() == 0)
	{
		return true;
	}

	for (const TSharedRef<IMessageToken>& Token : Message->GetMessageTokens())
	{
		if (LowerTokenTypes.Contains(ToLowerCopy(MessageTokenTypeToString(Token->GetType()))))
		{
			return true;
		}
	}

	return false;
}

bool MessageMatchesQuery(const TSharedRef<FTokenizedMessage>& Message, const FString& LowerQuery)
{
	if (LowerQuery.IsEmpty())
	{
		return true;
	}

	if (MatchesTextQuery(Message->ToText().ToString(), LowerQuery))
	{
		return true;
	}

	for (const TSharedRef<IMessageToken>& Token : Message->GetMessageTokens())
	{
		if (MatchesTextQuery(Token->ToText().ToString(), LowerQuery))
		{
			return true;
		}
	}

	return false;
}

TSharedPtr<FJsonObject> BuildMessageLogEntryJson(const TSharedRef<FTokenizedMessage>& Message, const int32 Index, const bool bIncludeTokens)
{
	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetNumberField(TEXT("index"), Index);
	Result->SetStringField(TEXT("severity"), MessageSeverityToString(Message->GetSeverity()));
	Result->SetStringField(TEXT("text"), Message->ToText().ToString());
	Result->SetNumberField(TEXT("tokenCount"), Message->GetMessageTokens().Num());

	const FName Identifier = Message->GetIdentifier();
	if (!Identifier.IsNone())
	{
		Result->SetStringField(TEXT("identifier"), Identifier.ToString());
	}

	const TSharedPtr<IMessageToken> MessageLink = Message->GetMessageLink();
	Result->SetBoolField(TEXT("hasMessageLink"), MessageLink.IsValid());
	if (MessageLink.IsValid())
	{
		Result->SetStringField(TEXT("messageLinkText"), MessageLink->ToText().ToString());
	}

	if (bIncludeTokens)
	{
		TArray<TSharedPtr<FJsonValue>> TokensJson;
		TokensJson.Reserve(Message->GetMessageTokens().Num());
		for (const TSharedRef<IMessageToken>& Token : Message->GetMessageTokens())
		{
			TokensJson.Add(MakeShared<FJsonValueObject>(BuildMessageTokenJson(Token)));
		}
		Result->SetArrayField(TEXT("tokens"), TokensJson);
	}

	return Result;
}

} // namespace

namespace BlueprintExtractorLogAccess
{

void Startup()
{
	SeedKnownMessageLogNames();
	if (GOutputLogCollector.IsValid())
	{
		return;
	}

	GOutputLogCollector = MakeUnique<FBlueprintExtractorOutputLogCollector>();
	if (FOutputDeviceRedirector* Redirector = FOutputDeviceRedirector::Get())
	{
		Redirector->EnableBacklog(true);
		Redirector->AddOutputDevice(GOutputLogCollector.Get());

#if UE_VERSION_OLDER_THAN(5, 7, 0)
		PRAGMA_DISABLE_DEPRECATION_WARNINGS
		Redirector->SerializeBacklog(GOutputLogCollector.Get());
		PRAGMA_ENABLE_DEPRECATION_WARNINGS
#endif
	}
}

void Shutdown()
{
	if (FOutputDeviceRedirector* Redirector = FOutputDeviceRedirector::Get())
	{
		if (GOutputLogCollector.IsValid())
		{
			Redirector->RemoveOutputDevice(GOutputLogCollector.Get());
		}
	}

	GOutputLogCollector.Reset();
}

TSharedPtr<FJsonObject> ReadOutputLog(const TSharedPtr<FJsonObject>& Filters, FString& OutError)
{
	if (!GOutputLogCollector.IsValid())
	{
		OutError = TEXT("Output Log collector is unavailable.");
		return nullptr;
	}

	FOutputLogReadOptions Options;
	if (!ParseOutputLogReadOptions(Filters, Options, OutError))
	{
		return nullptr;
	}

	const TArray<FBlueprintExtractorOutputLogEntry> Snapshot = GOutputLogCollector->Snapshot();
	const FDateTime NowUtc = FDateTime::UtcNow();

	TArray<FBlueprintExtractorOutputLogEntry> MatchedEntries;
	MatchedEntries.Reserve(Snapshot.Num());
	TMap<FString, int32> CategoryCounts;
	TMap<FString, int32> VerbosityCounts;

	for (const FBlueprintExtractorOutputLogEntry& Entry : Snapshot)
	{
		if (!MatchesSetFilter(Entry.Category, Options.Categories))
		{
			continue;
		}
		if (!MatchesSetFilter(Entry.Verbosity, Options.Verbosities))
		{
			continue;
		}
		if (!Options.Query.IsEmpty())
		{
			const bool bMatchesMessage = MatchesTextQuery(Entry.Message, Options.Query);
			const bool bMatchesCategory = MatchesTextQuery(Entry.Category, Options.Query);
			if (!bMatchesMessage && !bMatchesCategory)
			{
				continue;
			}
		}

		if (Options.bHasSinceUtc)
		{
			FDateTime CapturedAtUtc;
			if (!Entry.CapturedAtUtc.IsEmpty() && FDateTime::ParseIso8601(*Entry.CapturedAtUtc, CapturedAtUtc) && CapturedAtUtc < Options.SinceUtc)
			{
				continue;
			}
		}

		if (Options.SinceSeconds >= 0.0)
		{
			FDateTime CapturedAtUtc;
			if (!Entry.CapturedAtUtc.IsEmpty() && FDateTime::ParseIso8601(*Entry.CapturedAtUtc, CapturedAtUtc))
			{
				if ((NowUtc - CapturedAtUtc).GetTotalSeconds() > Options.SinceSeconds)
				{
					continue;
				}
			}
		}

		MatchedEntries.Add(Entry);
		CategoryCounts.FindOrAdd(Entry.Category) += 1;
		VerbosityCounts.FindOrAdd(Entry.Verbosity) += 1;
	}

	if (Options.bReverse)
	{
		Algo::Reverse(MatchedEntries);
	}

	const int32 SafeOffset = FMath::Clamp(Options.Offset, 0, MatchedEntries.Num());
	const int32 AvailableCount = MatchedEntries.Num() - SafeOffset;
	const int32 ReturnedCount = FMath::Min(Options.Limit, AvailableCount);

	TArray<TSharedPtr<FJsonValue>> EntriesJson;
	EntriesJson.Reserve(ReturnedCount);
	for (int32 Index = 0; Index < ReturnedCount; ++Index)
	{
		const FBlueprintExtractorOutputLogEntry& Entry = MatchedEntries[SafeOffset + Index];
		TSharedPtr<FJsonObject> EntryJson = MakeShared<FJsonObject>();
		EntryJson->SetNumberField(TEXT("sequence"), static_cast<double>(Entry.Sequence));
		EntryJson->SetStringField(TEXT("category"), Entry.Category);
		EntryJson->SetStringField(TEXT("verbosity"), Entry.Verbosity);
		EntryJson->SetStringField(TEXT("message"), Entry.Message);
		EntryJson->SetStringField(TEXT("capturedAtUtc"), Entry.CapturedAtUtc);
		if (Entry.EngineTime >= 0.0)
		{
			EntryJson->SetNumberField(TEXT("engineTime"), Entry.EngineTime);
		}
		EntriesJson.Add(MakeShared<FJsonValueObject>(EntryJson));
	}

	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("operation"), TEXT("read_output_log"));
	Result->SetStringField(TEXT("snapshotAtUtc"), NowUtc.ToIso8601());
	Result->SetNumberField(TEXT("bufferedCount"), Snapshot.Num());
	Result->SetNumberField(TEXT("matchedCount"), MatchedEntries.Num());
	Result->SetNumberField(TEXT("returnedCount"), ReturnedCount);
	Result->SetNumberField(TEXT("offset"), SafeOffset);
	Result->SetNumberField(TEXT("limit"), Options.Limit);
	Result->SetBoolField(TEXT("hasMore"), SafeOffset + ReturnedCount < MatchedEntries.Num());
	Result->SetArrayField(TEXT("categoryCounts"), ToJsonNameCountArray(CategoryCounts));
	Result->SetArrayField(TEXT("verbosityCounts"), ToJsonNameCountArray(VerbosityCounts));
	Result->SetArrayField(TEXT("entries"), EntriesJson);
	return Result;
}

TSharedPtr<FJsonObject> ListMessageLogListings(const TSharedPtr<FJsonObject>& Payload, FString& OutError)
{
	SeedKnownMessageLogNames();

	FMessageLogModule* MessageLogModule = FModuleManager::LoadModulePtr<FMessageLogModule>(TEXT("MessageLog"));
	if (MessageLogModule == nullptr)
	{
		OutError = TEXT("MessageLog module is unavailable.");
		return nullptr;
	}

	bool bIncludeUnregistered = false;
	if (Payload.IsValid())
	{
		Payload->TryGetBoolField(TEXT("include_unregistered"), bIncludeUnregistered);
	}

	const TArray<FName> CandidateNames = BuildCandidateMessageLogNames(Payload);
	TArray<TSharedPtr<FJsonValue>> ListingsJson;

	for (const FName& CandidateName : CandidateNames)
	{
		const bool bRegistered = MessageLogModule->IsRegisteredLogListing(CandidateName);
		if (!bRegistered && !bIncludeUnregistered)
		{
			continue;
		}

		TSharedPtr<FJsonObject> ListingJson = MakeShared<FJsonObject>();
		ListingJson->SetStringField(TEXT("listingName"), CandidateName.ToString());
		ListingJson->SetBoolField(TEXT("registered"), bRegistered);

		if (bRegistered)
		{
			RememberMessageLogName(CandidateName);
			const TSharedRef<IMessageLogListing> Listing = MessageLogModule->GetLogListing(CandidateName);
			ListingJson->SetStringField(TEXT("listingLabel"), Listing->GetLabel().ToString());
			ListingJson->SetNumberField(TEXT("messageCount"), Listing->NumMessages(EMessageSeverity::Info));
			ListingJson->SetNumberField(TEXT("filteredMessageCount"), Listing->GetFilteredMessages().Num());
			ListingJson->SetNumberField(TEXT("filterCount"), Listing->GetMessageFilters().Num());
		}

		ListingsJson.Add(MakeShared<FJsonValueObject>(ListingJson));
	}

	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("operation"), TEXT("list_message_log_listings"));
	Result->SetStringField(TEXT("snapshotAtUtc"), FDateTime::UtcNow().ToIso8601());
	Result->SetStringField(TEXT("discoveryMode"), TEXT("known_candidates"));
	Result->SetNumberField(TEXT("candidateCount"), CandidateNames.Num());
	Result->SetNumberField(TEXT("listingCount"), ListingsJson.Num());
	Result->SetBoolField(TEXT("includeUnregistered"), bIncludeUnregistered);
	Result->SetArrayField(TEXT("listings"), ListingsJson);
	return Result;
}

TSharedPtr<FJsonObject> ReadMessageLog(const FString& ListingName, const TSharedPtr<FJsonObject>& Filters, FString& OutError)
{
	if (ListingName.IsEmpty())
	{
		OutError = TEXT("listing_name is required.");
		return nullptr;
	}

	FMessageLogModule* MessageLogModule = FModuleManager::LoadModulePtr<FMessageLogModule>(TEXT("MessageLog"));
	if (MessageLogModule == nullptr)
	{
		OutError = TEXT("MessageLog module is unavailable.");
		return nullptr;
	}

	const FName LogName(*ListingName);
	RememberMessageLogName(LogName);
	if (!MessageLogModule->IsRegisteredLogListing(LogName))
	{
		OutError = FString::Printf(TEXT("Message Log listing is not registered: %s. Call list_message_log_listings to inspect known registered listings or pass candidate_names."), *ListingName);
		return nullptr;
	}

	FMessageLogReadOptions Options;
	ParseMessageLogReadOptions(Filters, Options);

	const TSharedRef<IMessageLogListing> Listing = MessageLogModule->GetLogListing(LogName);
	const TArray<TSharedRef<FTokenizedMessage>>& Messages = Listing->GetFilteredMessages();

	TArray<TSharedRef<FTokenizedMessage>> MatchedMessages;
	MatchedMessages.Reserve(Messages.Num());
	TMap<FString, int32> SeverityCounts;

	for (const TSharedRef<FTokenizedMessage>& Message : Messages)
	{
		const FString Severity = MessageSeverityToString(Message->GetSeverity());
		if (!MatchesSetFilter(Severity, Options.Severities))
		{
			continue;
		}
		if (!MessageMatchesTokenTypeFilter(Message, Options.TokenTypes))
		{
			continue;
		}
		if (!MessageMatchesQuery(Message, Options.Query))
		{
			continue;
		}

		MatchedMessages.Add(Message);
		SeverityCounts.FindOrAdd(Severity) += 1;
	}

	if (Options.bReverse)
	{
		Algo::Reverse(MatchedMessages);
	}

	const int32 SafeOffset = FMath::Clamp(Options.Offset, 0, MatchedMessages.Num());
	const int32 AvailableCount = MatchedMessages.Num() - SafeOffset;
	const int32 ReturnedCount = FMath::Min(Options.Limit, AvailableCount);

	TArray<TSharedPtr<FJsonValue>> EntriesJson;
	EntriesJson.Reserve(ReturnedCount);
	for (int32 Index = 0; Index < ReturnedCount; ++Index)
	{
		EntriesJson.Add(MakeShared<FJsonValueObject>(
			BuildMessageLogEntryJson(MatchedMessages[SafeOffset + Index], SafeOffset + Index, Options.bIncludeTokens)));
	}

	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("operation"), TEXT("read_message_log"));
	Result->SetStringField(TEXT("snapshotAtUtc"), FDateTime::UtcNow().ToIso8601());
	Result->SetStringField(TEXT("listingName"), Listing->GetName().ToString());
	Result->SetStringField(TEXT("listingLabel"), Listing->GetLabel().ToString());
	Result->SetNumberField(TEXT("messageCount"), Listing->NumMessages(EMessageSeverity::Info));
	Result->SetNumberField(TEXT("filteredMessageCount"), Messages.Num());
	Result->SetNumberField(TEXT("matchedCount"), MatchedMessages.Num());
	Result->SetNumberField(TEXT("returnedCount"), ReturnedCount);
	Result->SetNumberField(TEXT("offset"), SafeOffset);
	Result->SetNumberField(TEXT("limit"), Options.Limit);
	Result->SetBoolField(TEXT("hasMore"), SafeOffset + ReturnedCount < MatchedMessages.Num());
	Result->SetNumberField(TEXT("filterCount"), Listing->GetMessageFilters().Num());
	Result->SetArrayField(TEXT("severityCounts"), ToJsonNameCountArray(SeverityCounts));
	Result->SetArrayField(TEXT("entries"), EntriesJson);
	return Result;
}

} // namespace BlueprintExtractorLogAccess
