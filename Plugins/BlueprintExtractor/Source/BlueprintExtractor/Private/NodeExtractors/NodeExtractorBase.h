#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UK2Node;

class FNodeExtractorBase
{
public:
	virtual ~FNodeExtractorBase() = default;

	virtual bool CanHandle(const UK2Node* Node) const = 0;
	virtual TSharedPtr<FJsonObject> ExtractTypeSpecificData(const UK2Node* Node) const = 0;
	virtual FString GetNodeTypeName() const = 0;
};

class FNodeExtractorRegistry
{
public:
	FNodeExtractorRegistry();

	static FNodeExtractorRegistry& Get();

	void RegisterExtractor(TUniquePtr<FNodeExtractorBase>&& Extractor);

	const FNodeExtractorBase* FindExtractor(const UK2Node* Node) const;

private:
	void RegisterDefaultExtractors();

	TArray<TUniquePtr<FNodeExtractorBase>> Extractors;
};
