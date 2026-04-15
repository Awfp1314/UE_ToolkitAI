#pragma once

#include "CoreMinimal.h"

struct FContentBrowserExtension
{
	static void RegisterMenuExtension(FDelegateHandle& OutHandle);
	static void UnregisterMenuExtension(FDelegateHandle& InHandle);
};
