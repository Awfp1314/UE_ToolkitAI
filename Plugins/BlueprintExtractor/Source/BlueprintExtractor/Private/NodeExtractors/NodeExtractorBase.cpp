#include "NodeExtractors/NodeExtractorBase.h"
#include "NodeExtractors/NodeExtractor_CallFunction.h"
#include "NodeExtractors/NodeExtractor_Event.h"
#include "NodeExtractors/NodeExtractor_Variable.h"
#include "NodeExtractors/NodeExtractor_FlowControl.h"
#include "NodeExtractors/NodeExtractor_Macro.h"
#include "NodeExtractors/NodeExtractor_Timeline.h"

FNodeExtractorRegistry& FNodeExtractorRegistry::Get()
{
	static FNodeExtractorRegistry Instance;
	return Instance;
}

void FNodeExtractorRegistry::RegisterExtractor(TUniquePtr<FNodeExtractorBase>&& Extractor)
{
	Extractors.Add(MoveTemp(Extractor));
}

const FNodeExtractorBase* FNodeExtractorRegistry::FindExtractor(const UK2Node* Node) const
{
	for (const auto& Extractor : Extractors)
	{
		if (Extractor->CanHandle(Node))
		{
			return Extractor.Get();
		}
	}
	return nullptr;
}

FNodeExtractorRegistry::FNodeExtractorRegistry()
{
	RegisterDefaultExtractors();
}

void FNodeExtractorRegistry::RegisterDefaultExtractors()
{
	RegisterExtractor(MakeUnique<FNodeExtractor_CallFunction>());
	RegisterExtractor(MakeUnique<FNodeExtractor_Event>());
	RegisterExtractor(MakeUnique<FNodeExtractor_Variable>());
	RegisterExtractor(MakeUnique<FNodeExtractor_FlowControl>());
	RegisterExtractor(MakeUnique<FNodeExtractor_Macro>());
	RegisterExtractor(MakeUnique<FNodeExtractor_Timeline>());
}
