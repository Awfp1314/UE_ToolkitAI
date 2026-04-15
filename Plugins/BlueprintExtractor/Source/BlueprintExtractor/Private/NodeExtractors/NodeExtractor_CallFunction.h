#pragma once

#include "NodeExtractors/NodeExtractorBase.h"

class FNodeExtractor_CallFunction : public FNodeExtractorBase
{
public:
	virtual bool CanHandle(const UK2Node* Node) const override;
	virtual TSharedPtr<FJsonObject> ExtractTypeSpecificData(const UK2Node* Node) const override;
	virtual FString GetNodeTypeName() const override { return TEXT("CallFunction"); }
};
