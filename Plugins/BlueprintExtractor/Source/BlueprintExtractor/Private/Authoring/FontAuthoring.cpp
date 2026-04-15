#include "Authoring/FontAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "AssetToolsModule.h"
#include "AssetImportTask.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Dom/JsonValue.h"
#include "Engine/Font.h"
#include "Engine/FontFace.h"
#include "Factories/FontFactory.h"
#include "Factories/FontFileImportFactory.h"
#include "Fonts/CompositeFont.h"
#include "Misc/EngineVersionComparison.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"

namespace FontAuthoringInternal
{

struct FFontImportItem
{
	int32 Index = INDEX_NONE;
	FString FilePath;
	FString DestinationPath;
	FString DestinationName;
	FString EntryName;
	bool bReplaceExisting = false;
};

static bool TryGetObjectField(const TSharedPtr<FJsonObject>& JsonObject,
                              const TCHAR* FieldName,
                              TSharedPtr<FJsonObject>& OutObject)
{
	if (!JsonObject.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* ExistingObject = nullptr;
	if (JsonObject->TryGetObjectField(FStringView(FieldName), ExistingObject) && ExistingObject && ExistingObject->IsValid())
	{
		OutObject = *ExistingObject;
		return true;
	}

	return false;
}

static FString SanitizeAssetName(const FString& SourceName)
{
	FString Result;
	Result.Reserve(SourceName.Len());

	for (const TCHAR Character : SourceName)
	{
		if (FChar::IsAlnum(Character) || Character == TEXT('_'))
		{
			Result.AppendChar(Character);
		}
		else
		{
			Result.AppendChar(TEXT('_'));
		}
	}

	while (Result.StartsWith(TEXT("_")))
	{
		Result.RightChopInline(1, EAllowShrinking::No);
	}

	return Result.IsEmpty() ? TEXT("ImportedFont") : Result;
}

static bool IsSupportedFontExtension(const FString& FilePath)
{
	const FString Extension = FPaths::GetExtension(FilePath, true).ToLower();
	return Extension == TEXT(".ttf")
		|| Extension == TEXT(".ttc")
		|| Extension == TEXT(".otf")
		|| Extension == TEXT(".otc");
}

static FString BuildFontFaceAssetPath(const FFontImportItem& Item)
{
	const FString AssetName = !Item.DestinationName.IsEmpty()
		? SanitizeAssetName(Item.DestinationName)
		: SanitizeAssetName(FPaths::GetBaseFilename(Item.FilePath));
	return FString::Printf(TEXT("%s/%s"), *Item.DestinationPath, *AssetName);
}

static FString NormalizeFontAssetObjectPath(const FString& AssetPath)
{
	if (AssetPath.IsEmpty())
	{
		return FString();
	}

	int32 LastSlashIndex = INDEX_NONE;
	int32 LastDotIndex = INDEX_NONE;
	const bool bHasSlash = AssetPath.FindLastChar(TEXT('/'), LastSlashIndex);
	const bool bHasDot = AssetPath.FindLastChar(TEXT('.'), LastDotIndex);
	if (bHasDot && (!bHasSlash || LastDotIndex > LastSlashIndex))
	{
		return AssetPath;
	}

	if (bHasSlash && LastSlashIndex + 1 < AssetPath.Len())
	{
		const FString AssetName = AssetPath.Mid(LastSlashIndex + 1);
		if (!AssetName.IsEmpty())
		{
			return FString::Printf(TEXT("%s.%s"), *AssetPath, *AssetName);
		}
	}

	return NormalizeAssetObjectPath(AssetPath);
}

static FName ResolveTypefaceEntryName(const FFontImportItem& Item)
{
	if (!Item.EntryName.IsEmpty())
	{
		return FName(*Item.EntryName);
	}

	return FName(TEXT("Default"));
}

static TSharedPtr<FJsonObject> MakeItemResult(const FFontImportItem& Item,
                                              const FString& Status,
                                              const FString& FontFaceAssetPath = FString(),
                                              const FString& Message = FString())
{
	const TSharedPtr<FJsonObject> ItemObject = MakeShared<FJsonObject>();
	ItemObject->SetNumberField(TEXT("index"), Item.Index);
	ItemObject->SetStringField(TEXT("status"), Status);
	ItemObject->SetStringField(TEXT("filePath"), Item.FilePath);
	ItemObject->SetStringField(TEXT("destinationPath"), Item.DestinationPath);
	if (!Item.DestinationName.IsEmpty())
	{
		ItemObject->SetStringField(TEXT("destinationName"), Item.DestinationName);
	}
	if (!Item.EntryName.IsEmpty())
	{
		ItemObject->SetStringField(TEXT("entryName"), Item.EntryName);
	}
	if (!FontFaceAssetPath.IsEmpty())
	{
		ItemObject->SetStringField(TEXT("fontFaceAssetPath"), FontFaceAssetPath);
	}
	if (!Message.IsEmpty())
	{
		ItemObject->SetStringField(TEXT("message"), Message);
	}
	return ItemObject;
}

static bool ParseItems(const TSharedPtr<FJsonObject>& PayloadJson,
                       TArray<FFontImportItem>& OutItems,
                       FAssetMutationContext& Context)
{
	const TArray<TSharedPtr<FJsonValue>>* ItemValues = nullptr;
	if (!PayloadJson.IsValid() || !PayloadJson->TryGetArrayField(TEXT("items"), ItemValues) || !ItemValues)
	{
		Context.AddError(TEXT("missing_items"), TEXT("import_fonts requires an items array."));
		return false;
	}

	for (int32 Index = 0; Index < ItemValues->Num(); ++Index)
	{
		const TSharedPtr<FJsonObject> ItemObject = (*ItemValues)[Index].IsValid() ? (*ItemValues)[Index]->AsObject() : nullptr;
		if (!ItemObject.IsValid())
		{
			Context.AddError(TEXT("invalid_item"), FString::Printf(TEXT("items[%d] must be an object."), Index), FString::Printf(TEXT("items[%d]"), Index));
			continue;
		}

		FFontImportItem Item;
		Item.Index = Index;
		ItemObject->TryGetStringField(TEXT("file_path"), Item.FilePath);
		ItemObject->TryGetStringField(TEXT("destination_path"), Item.DestinationPath);
		ItemObject->TryGetStringField(TEXT("destination_name"), Item.DestinationName);
		ItemObject->TryGetStringField(TEXT("entry_name"), Item.EntryName);
		ItemObject->TryGetBoolField(TEXT("replace_existing"), Item.bReplaceExisting);

		if (Item.FilePath.IsEmpty())
		{
			Context.AddError(TEXT("missing_file_path"),
				FString::Printf(TEXT("items[%d].file_path is required."), Index),
				FString::Printf(TEXT("items[%d].file_path"), Index));
			continue;
		}
		if (!FPaths::FileExists(Item.FilePath))
		{
			Context.AddError(TEXT("source_not_found"),
				FString::Printf(TEXT("Font file not found: %s"), *Item.FilePath),
				FString::Printf(TEXT("items[%d].file_path"), Index));
			continue;
		}
		if (!IsSupportedFontExtension(Item.FilePath))
		{
			Context.AddError(TEXT("unsupported_extension"),
				FString::Printf(TEXT("Unsupported font extension: %s"), *Item.FilePath),
				FString::Printf(TEXT("items[%d].file_path"), Index));
			continue;
		}
		if (Item.DestinationPath.IsEmpty() || !FPackageName::IsValidLongPackageName(Item.DestinationPath))
		{
			Context.AddError(TEXT("invalid_destination_path"),
				FString::Printf(TEXT("items[%d].destination_path must be a valid long package path."), Index),
				FString::Printf(TEXT("items[%d].destination_path"), Index));
			continue;
		}

		OutItems.Add(Item);
	}

	return Context.Diagnostics.Num() == 0;
}

static UFont* ResolveOrCreateFontAsset(const FString& FontAssetPath,
                                       bool bValidateOnly,
                                       FAssetMutationContext& Context)
{
	if (FontAssetPath.IsEmpty())
	{
		return nullptr;
	}

	const FString ObjectPath = NormalizeFontAssetObjectPath(FontAssetPath);
	if (UFont* ExistingFont = Cast<UFont>(ResolveAssetByPath(ObjectPath)))
	{
		return ExistingFont;
	}

	const FString PackagePath = FPackageName::IsValidObjectPath(FontAssetPath)
		? FPackageName::ObjectPathToPackageName(FontAssetPath)
		: FontAssetPath;
	if (!FPackageName::IsValidLongPackageName(PackagePath))
	{
		Context.AddError(TEXT("invalid_font_asset_path"),
			FString::Printf(TEXT("font_asset_path must be a valid package or object path: %s"), *FontAssetPath),
			FontAssetPath);
		return nullptr;
	}

	if (bValidateOnly)
	{
		return nullptr;
	}

	UPackage* Package = CreatePackage(*PackagePath);
	if (!Package)
	{
		Context.AddError(TEXT("font_package_create_failed"),
			FString::Printf(TEXT("Failed to create package for font asset: %s"), *PackagePath),
			FontAssetPath);
		return nullptr;
	}

	UFontFactory* FontFactory = NewObject<UFontFactory>(GetTransientPackage());
	if (!FontFactory)
	{
		Context.AddError(TEXT("font_factory_create_failed"), TEXT("Failed to allocate UFontFactory."), FontAssetPath);
		return nullptr;
	}

	const FString AssetName = FPackageName::GetLongPackageAssetName(PackagePath);
	UFont* Font = Cast<UFont>(FontFactory->FactoryCreateNew(
		UFont::StaticClass(),
		Package,
		FName(*AssetName),
		RF_Public | RF_Standalone,
		nullptr,
		GWarn));
	if (!Font)
	{
		Context.AddError(TEXT("font_asset_create_failed"),
			FString::Printf(TEXT("Failed to create UFont asset: %s"), *PackagePath),
			FontAssetPath);
		return nullptr;
	}

	Font->FontCacheType = EFontCacheType::Runtime;
	Font->LegacyFontSize = 24;
	FAssetRegistryModule::AssetCreated(Font);
	Package->MarkPackageDirty();
	Context.TrackDirtyObject(Font);
	return Font;
}

static void UpsertCompositeTypeface(UFont* FontAsset,
                                    UFontFace* FontFace,
                                    const FName EntryName)
{
	if (!FontAsset || !FontFace)
	{
		return;
	}

#if UE_VERSION_NEWER_THAN_OR_EQUAL(5, 7, 0)
	FCompositeFont& CompositeFont = FontAsset->GetMutableInternalCompositeFont();
#else
	FCompositeFont& CompositeFont = FontAsset->CompositeFont;
#endif

	FTypeface& DefaultTypeface = CompositeFont.DefaultTypeface;
	FTypefaceEntry* ExistingEntry = DefaultTypeface.Fonts.FindByPredicate([EntryName](const FTypefaceEntry& Entry)
	{
		return Entry.Name == EntryName;
	});

	if (!ExistingEntry)
	{
		ExistingEntry = &DefaultTypeface.Fonts.AddDefaulted_GetRef();
		ExistingEntry->Name = EntryName;
	}

	ExistingEntry->Font = FFontData(FontFace);
	FontAsset->LegacyFontName = EntryName;
	CompositeFont.MakeDirty();
}

} // namespace FontAuthoringInternal

TSharedPtr<FJsonObject> FFontAuthoring::ImportFonts(const TSharedPtr<FJsonObject>& PayloadJson,
                                                    const bool bValidateOnly)
{
	using namespace FontAuthoringInternal;

	FAssetMutationContext Context(TEXT("import_fonts"), TEXT(""), TEXT("Font"), bValidateOnly);

	TArray<FFontImportItem> Items;
	ParseItems(PayloadJson, Items, Context);

	FString FontAssetPath;
	if (PayloadJson.IsValid())
	{
		PayloadJson->TryGetStringField(TEXT("font_asset_path"), FontAssetPath);
	}

	if (!FontAssetPath.IsEmpty())
	{
		ResolveOrCreateFontAsset(FontAssetPath, true, Context);
	}

	const bool bValidationSuccess = Context.Diagnostics.Num() == 0;
	Context.SetValidationSummary(
		bValidationSuccess,
		bValidationSuccess ? TEXT("Font import payload validated.") : TEXT("Font import payload failed validation."));
	if (!bValidationSuccess)
	{
		return Context.BuildResult(false);
	}

	if (bValidateOnly)
	{
		TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
		Result->SetStringField(TEXT("status"), TEXT("validated"));
		Result->SetNumberField(TEXT("itemCount"), Items.Num());
		if (!FontAssetPath.IsEmpty())
		{
			Result->SetStringField(TEXT("fontAssetPath"), NormalizeAssetObjectPath(FontAssetPath));
		}
		return Result;
	}

	UFont* RuntimeFont = ResolveOrCreateFontAsset(FontAssetPath, false, Context);
	if (!FontAssetPath.IsEmpty() && !RuntimeFont)
	{
		return Context.BuildResult(false);
	}

	TArray<TSharedPtr<FJsonValue>> ItemResults;
	int32 SuccessCount = 0;
	int32 FailureCount = 0;

	FAssetToolsModule& AssetToolsModule = FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools"));
	for (const FFontImportItem& Item : Items)
	{
		UAssetImportTask* ImportTask = NewObject<UAssetImportTask>(GetTransientPackage());
		UFontFileImportFactory* FontFactory = NewObject<UFontFileImportFactory>(GetTransientPackage());
		if (!ImportTask || !FontFactory)
		{
			++FailureCount;
			Context.AddError(TEXT("font_import_task_failed"),
				FString::Printf(TEXT("Failed to allocate font import task for %s"), *Item.FilePath),
				Item.FilePath);
			ItemResults.Add(MakeShared<FJsonValueObject>(MakeItemResult(Item, TEXT("failed"), FString(), TEXT("Failed to allocate import task."))));
			continue;
		}

		ImportTask->Filename = Item.FilePath;
		ImportTask->DestinationPath = Item.DestinationPath;
		ImportTask->DestinationName = Item.DestinationName;
		ImportTask->bAutomated = true;
		ImportTask->bAsync = false;
		ImportTask->bSave = false;
		ImportTask->bReplaceExisting = Item.bReplaceExisting;
		ImportTask->bReplaceExistingSettings = Item.bReplaceExisting;
		ImportTask->Factory = FontFactory;

		TArray<UAssetImportTask*> Tasks;
		Tasks.Add(ImportTask);
		AssetToolsModule.Get().ImportAssetTasks(Tasks);

		UFontFace* ImportedFontFace = nullptr;
		for (UObject* ImportedObject : ImportTask->GetObjects())
		{
			if (UFontFace* FontFace = Cast<UFontFace>(ImportedObject))
			{
				ImportedFontFace = FontFace;
				break;
			}
		}

		if (!ImportedFontFace)
		{
			++FailureCount;
			Context.AddError(TEXT("font_import_failed"),
				FString::Printf(TEXT("Failed to import font face from %s"), *Item.FilePath),
				Item.FilePath);
			ItemResults.Add(MakeShared<FJsonValueObject>(MakeItemResult(Item, TEXT("failed"), FString(), TEXT("Font face import returned no UFontFace asset."))));
			continue;
		}

		ImportedFontFace->MarkPackageDirty();
		Context.TrackDirtyObject(ImportedFontFace);

		const FString FontFaceAssetPath = ImportedFontFace->GetPathName();
		if (RuntimeFont)
		{
			RuntimeFont->Modify();
			UpsertCompositeTypeface(RuntimeFont, ImportedFontFace, ResolveTypefaceEntryName(Item));
			RuntimeFont->MarkPackageDirty();
			Context.TrackDirtyObject(RuntimeFont);
		}

		++SuccessCount;
		ItemResults.Add(MakeShared<FJsonValueObject>(MakeItemResult(Item, TEXT("succeeded"), FontFaceAssetPath)));
	}

	FString Status = TEXT("succeeded");
	bool bSuccess = true;
	if (SuccessCount == 0 && FailureCount > 0)
	{
		Status = TEXT("failed");
		bSuccess = false;
	}
	else if (FailureCount > 0)
	{
		Status = TEXT("partial_success");
	}

	TSharedPtr<FJsonObject> Result = Context.BuildResult(bSuccess);
	Result->SetStringField(TEXT("status"), Status);
	Result->SetNumberField(TEXT("itemCount"), Items.Num());
	Result->SetNumberField(TEXT("importedCount"), SuccessCount);
	Result->SetNumberField(TEXT("failedItemCount"), FailureCount);
	Result->SetArrayField(TEXT("items"), ItemResults);
	if (RuntimeFont)
	{
		Result->SetStringField(TEXT("fontAssetPath"), RuntimeFont->GetPathName());
	}
	else if (!FontAssetPath.IsEmpty())
	{
		Result->SetStringField(TEXT("fontAssetPath"), NormalizeAssetObjectPath(FontAssetPath));
	}
	return Result;
}
