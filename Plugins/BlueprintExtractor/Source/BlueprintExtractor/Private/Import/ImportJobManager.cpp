#include "Import/ImportJobManager.h"

#include "Authoring/AssetMutationHelpers.h"

#include "Animation/Skeleton.h"
#include "AssetImportTask.h"
#include "AssetToolsModule.h"
#include "Async/Async.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "EditorFramework/AssetImportData.h"
#include "EditorReimportHandler.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Factories/FbxImportUI.h"
#include "Factories/FbxStaticMeshImportData.h"
#include "Factories/TextureFactory.h"
#include "HAL/FileManager.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "InterchangeManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/StrongObjectPtr.h"

namespace BlueprintExtractorImport
{

enum class EImportJobKind : uint8
{
	Generic,
	Reimport,
	Texture,
	Mesh,
};

enum class EImportItemState : uint8
{
	Queued,
	Downloading,
	Staged,
	Importing,
	Succeeded,
	Failed,
};

enum class EImportJobState : uint8
{
	Queued,
	Running,
	Succeeded,
	PartialSuccess,
	Failed,
};

enum class ESourceKind : uint8
{
	None,
	File,
	Url,
};

enum class EMeshImportType : uint8
{
	Static,
	Skeletal,
};

struct FDiagnostic
{
	FString Severity;
	FString Code;
	FString Message;
	FString Path;
};

struct FTextureOptions
{
	TOptional<TextureCompressionSettings> CompressionSettings;
	TOptional<TextureGroup> LODGroup;
	TOptional<bool> bSRGB;
	TOptional<bool> bVirtualTextureStreaming;
	TOptional<bool> bFlipGreenChannel;
};

struct FMeshOptions
{
	EMeshImportType MeshType = EMeshImportType::Static;
	TOptional<bool> bImportMaterials;
	TOptional<bool> bImportTextures;
	TOptional<bool> bImportAnimations;
	TOptional<bool> bCombineMeshes;
	TOptional<bool> bGenerateCollision;
	FString SkeletonPath;
};

struct FItemRequest
{
	int32 Index = INDEX_NONE;
	ESourceKind SourceKind = ESourceKind::None;
	FString FilePath;
	FString Url;
	TMap<FString, FString> Headers;
	FString Filename;
	FString DestinationPath;
	FString DestinationName;
	FString AssetPath;
	bool bReplaceExisting = false;
	bool bReplaceExistingSettings = false;
	TOptional<FTextureOptions> TextureOptions;
	TOptional<FMeshOptions> MeshOptions;
};

struct FItemRecord
{
	FItemRequest Request;
	EImportItemState State = EImportItemState::Failed;
	bool bAccepted = false;
	TArray<FDiagnostic> Diagnostics;
	FString ResolvedSourcePath;
	FString StagedFilePath;
	TSet<FString> KnownDestinationObjects;
	TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> PendingRequest;
	TStrongObjectPtr<UAssetImportTask> ImportTask;
	UE::Interchange::FAssetImportResultPtr ReimportResult;
	TWeakObjectPtr<UObject> ReimportTarget;
	TArray<FString> ImportedObjects;
	TSet<FString> DirtyPackages;
	int32 CompletionChecks = 0;
	bool bCompletionProcessed = false;
};

struct FJobRecord
{
	FString JobId;
	FString Operation;
	EImportJobKind Kind = EImportJobKind::Generic;
	bool bValidateOnly = false;
	EImportJobState Status = EImportJobState::Queued;
	FDateTime CreatedAt = FDateTime::UtcNow();
	TOptional<FDateTime> StartedAt;
	TOptional<FDateTime> CompletedAt;
	TArray<FDiagnostic> Diagnostics;
	TArray<FItemRecord> Items;
	TSet<FString> ImportedObjects;
	TSet<FString> DirtyPackages;
};

static void AddDiagnostic(TArray<FDiagnostic>& Diagnostics, const FString& Severity, const FString& Code, const FString& Message, const FString& Path = FString())
{
	Diagnostics.Add({Severity, Code, Message, Path});
}

static void AddError(TArray<FDiagnostic>& Diagnostics, const FString& Code, const FString& Message, const FString& Path = FString())
{
	AddDiagnostic(Diagnostics, TEXT("error"), Code, Message, Path);
}

static FString StripSensitiveUrlParts(const FString& Url)
{
	int32 CutIndex = INDEX_NONE;
	int32 QueryIndex = INDEX_NONE;
	int32 FragmentIndex = INDEX_NONE;
	Url.FindChar(TEXT('?'), QueryIndex);
	Url.FindChar(TEXT('#'), FragmentIndex);
	if (QueryIndex != INDEX_NONE && FragmentIndex != INDEX_NONE)
	{
		CutIndex = FMath::Min(QueryIndex, FragmentIndex);
	}
	else
	{
		CutIndex = QueryIndex != INDEX_NONE ? QueryIndex : FragmentIndex;
	}
	return CutIndex == INDEX_NONE ? Url : Url.Left(CutIndex);
}

static FString ResolveFilePath(const FString& FilePath)
{
	return FPaths::IsRelative(FilePath)
		? FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), FilePath)
		: FPaths::ConvertRelativePathToFull(FilePath);
}

static FString JobKindToString(const EImportJobKind Kind)
{
	switch (Kind)
	{
	case EImportJobKind::Generic: return TEXT("import");
	case EImportJobKind::Reimport: return TEXT("reimport");
	case EImportJobKind::Texture: return TEXT("texture");
	case EImportJobKind::Mesh: return TEXT("mesh");
	default: return TEXT("import");
	}
}

static FString JobStateToString(const EImportJobState State)
{
	switch (State)
	{
	case EImportJobState::Queued: return TEXT("queued");
	case EImportJobState::Running: return TEXT("running");
	case EImportJobState::Succeeded: return TEXT("succeeded");
	case EImportJobState::PartialSuccess: return TEXT("partial_success");
	case EImportJobState::Failed: default: return TEXT("failed");
	}
}

static FString ItemStateToString(const EImportItemState State)
{
	switch (State)
	{
	case EImportItemState::Queued: return TEXT("queued");
	case EImportItemState::Downloading: return TEXT("downloading");
	case EImportItemState::Staged: return TEXT("staged");
	case EImportItemState::Importing: return TEXT("importing");
	case EImportItemState::Succeeded: return TEXT("succeeded");
	case EImportItemState::Failed: default: return TEXT("failed");
	}
}

static TArray<TSharedPtr<FJsonValue>> ToJsonStrings(const TSet<FString>& Values)
{
	TArray<FString> Sorted = Values.Array();
	Sorted.Sort();
	TArray<TSharedPtr<FJsonValue>> Json;
	for (const FString& Value : Sorted)
	{
		Json.Add(MakeShared<FJsonValueString>(Value));
	}
	return Json;
}

static TArray<TSharedPtr<FJsonValue>> ToJsonStrings(const TArray<FString>& Values)
{
	TSet<FString> Unique;
	for (const FString& Value : Values)
	{
		if (!Value.IsEmpty())
		{
			Unique.Add(Value);
		}
	}
	return ToJsonStrings(Unique);
}

static TArray<TSharedPtr<FJsonValue>> ToJsonDiagnostics(const TArray<FDiagnostic>& Diagnostics)
{
	TArray<TSharedPtr<FJsonValue>> Json;
	for (const FDiagnostic& Diagnostic : Diagnostics)
	{
		TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();
		Obj->SetStringField(TEXT("severity"), Diagnostic.Severity);
		Obj->SetStringField(TEXT("code"), Diagnostic.Code);
		Obj->SetStringField(TEXT("message"), Diagnostic.Message);
		if (!Diagnostic.Path.IsEmpty())
		{
			Obj->SetStringField(TEXT("path"), Diagnostic.Path);
		}
		Json.Add(MakeShared<FJsonValueObject>(Obj));
	}
	return Json;
}

static void TrackImportedObjectPath(FItemRecord& Item, FJobRecord& Job, const FString& ObjectPath)
{
	if (ObjectPath.IsEmpty())
	{
		return;
	}

	Item.ImportedObjects.AddUnique(ObjectPath);
	Job.ImportedObjects.Add(ObjectPath);
	if (FPackageName::IsValidObjectPath(ObjectPath))
	{
		const FString PackageName = FPackageName::ObjectPathToPackageName(ObjectPath);
		if (!PackageName.IsEmpty())
		{
			Item.DirtyPackages.Add(PackageName);
			Job.DirtyPackages.Add(PackageName);
		}
	}
}

static void TrackImportedObjects(FItemRecord& Item, FJobRecord& Job, const TArray<UObject*>& Objects)
{
	for (UObject* Object : Objects)
	{
		if (!Object)
		{
			continue;
		}
		TrackImportedObjectPath(Item, Job, Object->GetPathName());
	}
}

static TSet<FString> CollectDestinationObjectPaths(const FString& DestinationPath)
{
	TSet<FString> ObjectPaths;
	if (!FPackageName::IsValidLongPackageName(DestinationPath))
	{
		return ObjectPaths;
	}

	TArray<FAssetData> AssetDatas;
	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
	AssetRegistryModule.Get().GetAssetsByPath(FName(*DestinationPath), AssetDatas, false, false);
	for (const FAssetData& AssetData : AssetDatas)
	{
		ObjectPaths.Add(AssetData.GetObjectPathString());
	}
	return ObjectPaths;
}

static FString GetDefaultImportedAssetName(const FItemRequest& Request)
{
	if (!Request.DestinationName.IsEmpty())
	{
		return Request.DestinationName;
	}

	if (Request.SourceKind == ESourceKind::Url)
	{
		const FString UrlFilename = !Request.Filename.IsEmpty()
			? Request.Filename
			: FPaths::GetCleanFilename(StripSensitiveUrlParts(Request.Url));
		return FPaths::GetBaseFilename(UrlFilename);
	}

	return FPaths::GetBaseFilename(Request.FilePath);
}

static FString GetExpectedImportedObjectPath(const FItemRequest& Request)
{
	if (Request.DestinationPath.IsEmpty())
	{
		return FString();
	}

	const FString AssetName = GetDefaultImportedAssetName(Request);
	return AssetName.IsEmpty()
		? FString()
		: NormalizeAssetObjectPath(FString::Printf(TEXT("%s/%s"), *Request.DestinationPath, *AssetName));
}

static UAssetImportData* GetAssetImportData(UObject* Object)
{
	if (UTexture* Texture = Cast<UTexture>(Object))
	{
		return Texture->AssetImportData;
	}
	if (UStaticMesh* StaticMesh = Cast<UStaticMesh>(Object))
	{
		return StaticMesh->GetAssetImportData();
	}
	if (USkeletalMesh* SkeletalMesh = Cast<USkeletalMesh>(Object))
	{
		return SkeletalMesh->GetAssetImportData();
	}
	return nullptr;
}

static bool HasMatchingImportSource(UObject* Object, const TSet<FString>& CandidateSources)
{
	if (CandidateSources.Num() == 0)
	{
		return false;
	}

	UAssetImportData* ImportData = GetAssetImportData(Object);
	if (!ImportData)
	{
		return false;
	}

	TArray<FString> SourceFiles;
	ImportData->ExtractFilenames(SourceFiles);
	for (const FString& SourceFile : SourceFiles)
	{
		if (CandidateSources.Contains(ResolveFilePath(SourceFile)))
		{
			return true;
		}
	}

	return false;
}

static void ApplyTextureOverrides(FItemRecord& Item, FJobRecord& Job)
{
	if (!Item.Request.TextureOptions.IsSet())
	{
		return;
	}

	const FTextureOptions& Options = Item.Request.TextureOptions.GetValue();
	const TArray<FString> ImportedObjectPaths = Item.ImportedObjects;
	for (const FString& ObjectPath : ImportedObjectPaths)
	{
		UTexture* Texture = Cast<UTexture>(ResolveAssetByPath(ObjectPath));
		if (!Texture)
		{
			continue;
		}

		if (Options.bSRGB.IsSet()) Texture->SRGB = Options.bSRGB.GetValue();
		if (Options.CompressionSettings.IsSet()) Texture->CompressionSettings = Options.CompressionSettings.GetValue();
		if (Options.LODGroup.IsSet()) Texture->LODGroup = Options.LODGroup.GetValue();
		if (Options.bFlipGreenChannel.IsSet()) Texture->bFlipGreenChannel = Options.bFlipGreenChannel.GetValue();
		if (Options.bVirtualTextureStreaming.IsSet()) Texture->VirtualTextureStreaming = Options.bVirtualTextureStreaming.GetValue();
		Texture->MarkPackageDirty();
		Texture->PostEditChange();
		TrackImportedObjectPath(Item, Job, Texture->GetPathName());
	}
}

static void FinalizeJob(FJobRecord& Job)
{
	int32 SuccessCount = 0;
	int32 FailureCount = 0;
	int32 ActiveCount = 0;
	for (const FItemRecord& Item : Job.Items)
	{
		switch (Item.State)
		{
		case EImportItemState::Succeeded: ++SuccessCount; break;
		case EImportItemState::Failed: ++FailureCount; break;
		default: ++ActiveCount; break;
		}
	}

	if (ActiveCount > 0)
	{
		Job.Status = Job.StartedAt.IsSet() ? EImportJobState::Running : EImportJobState::Queued;
		return;
	}

	Job.Status = SuccessCount > 0
		? (FailureCount > 0 ? EImportJobState::PartialSuccess : EImportJobState::Succeeded)
		: EImportJobState::Failed;
	if (!Job.CompletedAt.IsSet())
	{
		Job.CompletedAt = FDateTime::UtcNow();
	}
}

static TSharedPtr<FJsonObject> BuildItemJson(const FItemRecord& Item)
{
	TSharedPtr<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetNumberField(TEXT("index"), Item.Request.Index);
	Json->SetStringField(TEXT("status"), ItemStateToString(Item.State));
	if (!Item.Request.AssetPath.IsEmpty())
	{
		Json->SetStringField(TEXT("assetPath"), Item.Request.AssetPath);
	}
	if (!Item.Request.DestinationPath.IsEmpty())
	{
		Json->SetStringField(TEXT("destinationPath"), Item.Request.DestinationPath);
	}
	if (!Item.Request.DestinationName.IsEmpty())
	{
		Json->SetStringField(TEXT("destinationName"), Item.Request.DestinationName);
	}
	if (Item.Request.SourceKind == ESourceKind::File && !Item.Request.FilePath.IsEmpty())
	{
		Json->SetStringField(TEXT("filePath"), Item.ResolvedSourcePath.IsEmpty() ? Item.Request.FilePath : Item.ResolvedSourcePath);
	}
	else if (Item.Request.SourceKind == ESourceKind::Url && !Item.Request.Url.IsEmpty())
	{
		Json->SetStringField(TEXT("url"), StripSensitiveUrlParts(Item.Request.Url));
	}
	if (!Item.StagedFilePath.IsEmpty())
	{
		Json->SetStringField(TEXT("stagedFilePath"), Item.StagedFilePath);
	}
	Json->SetArrayField(TEXT("importedObjects"), ToJsonStrings(Item.ImportedObjects));
	Json->SetArrayField(TEXT("dirtyPackages"), ToJsonStrings(Item.DirtyPackages));
	Json->SetArrayField(TEXT("diagnostics"), ToJsonDiagnostics(Item.Diagnostics));
	return Json;
}

static TSharedPtr<FJsonObject> BuildJobJson(const FJobRecord& Job)
{
	TSharedPtr<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetBoolField(TEXT("success"), !Job.CompletedAt.IsSet() || Job.Status != EImportJobState::Failed);
	Json->SetStringField(TEXT("operation"), Job.Operation);
	Json->SetStringField(TEXT("kind"), JobKindToString(Job.Kind));
	Json->SetStringField(TEXT("status"), JobStateToString(Job.Status));
	Json->SetBoolField(TEXT("terminal"), Job.CompletedAt.IsSet());
	Json->SetBoolField(TEXT("validateOnly"), Job.bValidateOnly);
	Json->SetStringField(TEXT("jobId"), Job.JobId);
	Json->SetStringField(TEXT("createdAt"), Job.CreatedAt.ToIso8601());
	if (Job.StartedAt.IsSet())
	{
		Json->SetStringField(TEXT("startedAt"), Job.StartedAt.GetValue().ToIso8601());
	}
	if (Job.CompletedAt.IsSet())
	{
		Json->SetStringField(TEXT("completedAt"), Job.CompletedAt.GetValue().ToIso8601());
	}

	int32 AcceptedCount = 0;
	int32 FailedCount = 0;
	TArray<TSharedPtr<FJsonValue>> ItemsJson;
	for (const FItemRecord& Item : Job.Items)
	{
		AcceptedCount += Item.bAccepted ? 1 : 0;
		FailedCount += Item.State == EImportItemState::Failed ? 1 : 0;
		ItemsJson.Add(MakeShared<FJsonValueObject>(BuildItemJson(Item)));
	}
	Json->SetNumberField(TEXT("itemCount"), Job.Items.Num());
	Json->SetNumberField(TEXT("acceptedItemCount"), AcceptedCount);
	Json->SetNumberField(TEXT("failedItemCount"), FailedCount);
	Json->SetArrayField(TEXT("items"), ItemsJson);
	Json->SetArrayField(TEXT("importedObjects"), ToJsonStrings(Job.ImportedObjects));
	Json->SetArrayField(TEXT("dirtyPackages"), ToJsonStrings(Job.DirtyPackages));
	Json->SetArrayField(TEXT("diagnostics"), ToJsonDiagnostics(Job.Diagnostics));
	return Json;
}

static TSharedPtr<FJsonObject> BuildMissingJobJson(const FString& Operation, const FString& JobId)
{
	TSharedPtr<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetBoolField(TEXT("success"), false);
	Json->SetStringField(TEXT("operation"), Operation);
	Json->SetStringField(TEXT("jobId"), JobId);
	Json->SetStringField(TEXT("error"), FString::Printf(TEXT("Import job not found: %s"), *JobId));
	return Json;
}

static TOptional<int32> ParseItemIndex(const FString& Path)
{
	if (!Path.StartsWith(TEXT("items[")))
	{
		return {};
	}

	int32 EndIndex = INDEX_NONE;
	if (!Path.FindChar(TEXT(']'), EndIndex) || EndIndex <= 6)
	{
		return {};
	}

	int32 Index = INDEX_NONE;
	return LexTryParseString(Index, *Path.Mid(6, EndIndex - 6)) ? TOptional<int32>(Index) : TOptional<int32>();
}

static TOptional<TextureCompressionSettings> ParseCompressionSetting(const FString& Value)
{
	if (const UEnum* Enum = StaticEnum<TextureCompressionSettings>())
	{
		const int64 Parsed = Enum->GetValueByNameString(Value, EGetByNameFlags::None);
		if (Parsed != INDEX_NONE)
		{
			return static_cast<TextureCompressionSettings>(Parsed);
		}
	}
	return {};
}

static TOptional<TextureGroup> ParseTextureGroup(const FString& Value)
{
	if (const UEnum* Enum = StaticEnum<TextureGroup>())
	{
		const int64 Parsed = Enum->GetValueByNameString(Value, EGetByNameFlags::None);
		if (Parsed != INDEX_NONE)
		{
			return static_cast<TextureGroup>(Parsed);
		}
	}
	return {};
}

static bool ParsePayload(const FString& PayloadJson,
                         const EImportJobKind Kind,
                         int32& OutItemCount,
                         TArray<FItemRequest>& OutRequests,
                         TArray<FDiagnostic>& OutDiagnostics)
{
	OutItemCount = 0;
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PayloadJson);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		AddError(OutDiagnostics, TEXT("invalid_payload"), TEXT("Payload must be a JSON object."));
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
	if (!Root->TryGetArrayField(TEXT("items"), Items) || Items == nullptr)
	{
		AddError(OutDiagnostics, TEXT("invalid_payload"), TEXT("Payload must include an items array."));
		return false;
	}

	OutItemCount = Items->Num();
	for (int32 Index = 0; Index < Items->Num(); ++Index)
	{
		TSharedPtr<FJsonObject> ItemObject = (*Items)[Index].IsValid() ? (*Items)[Index]->AsObject() : nullptr;
		const FString Path = FString::Printf(TEXT("items[%d]"), Index);
		if (!ItemObject.IsValid())
		{
			AddError(OutDiagnostics, TEXT("invalid_item"), TEXT("Each item must be a JSON object."), Path);
			continue;
		}

		FItemRequest Request;
		Request.Index = Index;
		ItemObject->TryGetStringField(TEXT("file_path"), Request.FilePath);
		ItemObject->TryGetStringField(TEXT("url"), Request.Url);
		ItemObject->TryGetStringField(TEXT("filename"), Request.Filename);
		ItemObject->TryGetStringField(TEXT("destination_path"), Request.DestinationPath);
		ItemObject->TryGetStringField(TEXT("destination_name"), Request.DestinationName);
		ItemObject->TryGetStringField(TEXT("asset_path"), Request.AssetPath);
		ItemObject->TryGetBoolField(TEXT("replace_existing"), Request.bReplaceExisting);
		ItemObject->TryGetBoolField(TEXT("replace_existing_settings"), Request.bReplaceExistingSettings);

		const TSharedPtr<FJsonObject>* HeadersObject = nullptr;
		if (ItemObject->TryGetObjectField(TEXT("headers"), HeadersObject) && HeadersObject && HeadersObject->IsValid())
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*HeadersObject)->Values)
			{
				if (!Pair.Value.IsValid() || Pair.Value->Type != EJson::String)
				{
					AddError(OutDiagnostics, TEXT("invalid_header_value"), TEXT("headers values must be strings."), Path);
					continue;
				}
				Request.Headers.Add(Pair.Key, Pair.Value->AsString());
			}
		}

		if (Kind == EImportJobKind::Texture)
		{
			const TSharedPtr<FJsonObject>* OptionsObject = nullptr;
			if (ItemObject->TryGetObjectField(TEXT("options"), OptionsObject) && OptionsObject && OptionsObject->IsValid())
			{
				FTextureOptions Options;
				FString EnumValue;
				bool BoolValue = false;
				if ((*OptionsObject)->TryGetStringField(TEXT("compression_settings"), EnumValue))
				{
					const TOptional<TextureCompressionSettings> Parsed = ParseCompressionSetting(EnumValue);
					if (!Parsed.IsSet())
					{
						AddError(OutDiagnostics, TEXT("invalid_compression_settings"), EnumValue, Path);
						continue;
					}
					Options.CompressionSettings = Parsed;
				}
				if ((*OptionsObject)->TryGetStringField(TEXT("lod_group"), EnumValue))
				{
					const TOptional<TextureGroup> Parsed = ParseTextureGroup(EnumValue);
					if (!Parsed.IsSet())
					{
						AddError(OutDiagnostics, TEXT("invalid_lod_group"), EnumValue, Path);
						continue;
					}
					Options.LODGroup = Parsed;
				}
				if ((*OptionsObject)->TryGetBoolField(TEXT("srgb"), BoolValue) || (*OptionsObject)->TryGetBoolField(TEXT("s_rgb"), BoolValue))
				{
					Options.bSRGB = BoolValue;
				}
				if ((*OptionsObject)->TryGetBoolField(TEXT("virtual_texture_streaming"), BoolValue))
				{
					Options.bVirtualTextureStreaming = BoolValue;
				}
				if ((*OptionsObject)->TryGetBoolField(TEXT("flip_green_channel"), BoolValue))
				{
					Options.bFlipGreenChannel = BoolValue;
				}
				Request.TextureOptions = Options;
			}
		}
		else if (Kind == EImportJobKind::Mesh)
		{
			const TSharedPtr<FJsonObject>* OptionsObject = nullptr;
			if (ItemObject->TryGetObjectField(TEXT("options"), OptionsObject) && OptionsObject && OptionsObject->IsValid())
			{
				FMeshOptions Options;
				FString MeshType;
				if ((*OptionsObject)->TryGetStringField(TEXT("mesh_type"), MeshType))
				{
					if (MeshType.Equals(TEXT("skeletal"), ESearchCase::IgnoreCase) || MeshType.Equals(TEXT("skeletal_mesh"), ESearchCase::IgnoreCase))
					{
						Options.MeshType = EMeshImportType::Skeletal;
					}
					else if (!MeshType.Equals(TEXT("static"), ESearchCase::IgnoreCase) && !MeshType.Equals(TEXT("static_mesh"), ESearchCase::IgnoreCase))
					{
						AddError(OutDiagnostics, TEXT("invalid_mesh_type"), MeshType, Path);
						continue;
					}
				}
				bool BoolValue = false;
				if ((*OptionsObject)->TryGetBoolField(TEXT("import_materials"), BoolValue)) Options.bImportMaterials = BoolValue;
				if ((*OptionsObject)->TryGetBoolField(TEXT("import_textures"), BoolValue)) Options.bImportTextures = BoolValue;
				if ((*OptionsObject)->TryGetBoolField(TEXT("import_animations"), BoolValue)) Options.bImportAnimations = BoolValue;
				if ((*OptionsObject)->TryGetBoolField(TEXT("combine_meshes"), BoolValue)) Options.bCombineMeshes = BoolValue;
				if ((*OptionsObject)->TryGetBoolField(TEXT("generate_collision"), BoolValue)) Options.bGenerateCollision = BoolValue;
				(*OptionsObject)->TryGetStringField(TEXT("skeleton_path"), Options.SkeletonPath);
				Request.MeshOptions = Options;
			}
		}

		OutRequests.Add(MoveTemp(Request));
	}

	return true;
}

static bool ValidateSource(FItemRequest& Request, const bool bAllowEmpty, TArray<FDiagnostic>& Diagnostics, const FString& Path)
{
	const bool bHasFile = !Request.FilePath.IsEmpty();
	const bool bHasUrl = !Request.Url.IsEmpty();
	if (bHasFile && bHasUrl)
	{
		AddError(Diagnostics, TEXT("invalid_source"), TEXT("Specify only one of file_path or url."), Path);
		return false;
	}
	if (!bHasFile && !bHasUrl)
	{
		if (bAllowEmpty)
		{
			Request.SourceKind = ESourceKind::None;
			return true;
		}
		AddError(Diagnostics, TEXT("invalid_source"), TEXT("Specify one of file_path or url."), Path);
		return false;
	}

	if (bHasFile)
	{
		Request.SourceKind = ESourceKind::File;
		Request.FilePath = ResolveFilePath(Request.FilePath);
		if (!FPaths::FileExists(Request.FilePath))
		{
			AddError(Diagnostics, TEXT("source_not_found"), FString::Printf(TEXT("Source file not found: %s"), *Request.FilePath), Path);
			return false;
		}
		return true;
	}

	Request.SourceKind = ESourceKind::Url;
	if (!Request.Url.StartsWith(TEXT("http://"), ESearchCase::IgnoreCase) && !Request.Url.StartsWith(TEXT("https://"), ESearchCase::IgnoreCase))
	{
		AddError(Diagnostics, TEXT("unsupported_url_scheme"), TEXT("Only http and https URLs are supported."), Path);
		return false;
	}
	const FString CandidateFilename = !Request.Filename.IsEmpty() ? Request.Filename : FPaths::GetCleanFilename(StripSensitiveUrlParts(Request.Url));
	if (CandidateFilename.IsEmpty() || FPaths::GetExtension(CandidateFilename, true).IsEmpty())
	{
		AddError(Diagnostics, TEXT("filename_required"), TEXT("URL imports require filename or a URL path with extension."), Path);
		return false;
	}
	Request.Filename = CandidateFilename;
	return true;
}

static bool ValidateImportTarget(const FItemRequest& Request, TArray<FDiagnostic>& Diagnostics, const FString& Path)
{
	if (Request.DestinationPath.IsEmpty())
	{
		AddError(Diagnostics, TEXT("destination_required"), TEXT("destination_path is required."), Path);
		return false;
	}
	if (!FPackageName::IsValidLongPackageName(Request.DestinationPath))
	{
		AddError(Diagnostics, TEXT("invalid_destination_path"), Request.DestinationPath, Path);
		return false;
	}
	return true;
}

static bool ValidateReimportTarget(FItemRequest& Request, TArray<FDiagnostic>& Diagnostics, const FString& Path)
{
	Request.AssetPath = NormalizeAssetObjectPath(Request.AssetPath);
	UObject* Asset = ResolveAssetByPath(Request.AssetPath);
	if (!Asset)
	{
		AddError(Diagnostics, TEXT("asset_not_found"), FString::Printf(TEXT("Asset not found: %s"), *Request.AssetPath), Path);
		return false;
	}
	Request.AssetPath = Asset->GetPathName();
	TArray<FString> ExistingSources;
	if (!FReimportManager::Instance()->CanReimport(Asset, &ExistingSources))
	{
		AddError(Diagnostics, TEXT("reimport_not_supported"), FString::Printf(TEXT("Asset cannot be reimported: %s"), *Request.AssetPath), Path);
		return false;
	}
	if (Request.SourceKind == ESourceKind::None)
	{
		if (ExistingSources.Num() == 0)
		{
			AddError(Diagnostics, TEXT("source_not_found"), TEXT("Asset has no recorded import source."), Path);
			return false;
		}
		const FString SourceFile = ResolveFilePath(ExistingSources[0]);
		if (!FPaths::FileExists(SourceFile))
		{
			AddError(Diagnostics, TEXT("source_not_found"), FString::Printf(TEXT("Recorded source file not found: %s"), *SourceFile), Path);
			return false;
		}
	}
	return true;
}

} // namespace BlueprintExtractorImport

struct FBlueprintExtractorImportJobManager::FImpl
{
	TMap<FString, BlueprintExtractorImport::FJobRecord> Jobs;

	~FImpl()
	{
		for (TPair<FString, BlueprintExtractorImport::FJobRecord>& Pair : Jobs)
		{
			for (BlueprintExtractorImport::FItemRecord& Item : Pair.Value.Items)
			{
				if (Item.PendingRequest.IsValid())
				{
					Item.PendingRequest->OnProcessRequestComplete().Unbind();
					Item.PendingRequest->CancelRequest();
					Item.PendingRequest.Reset();
				}
			}
		}
	}

	BlueprintExtractorImport::FJobRecord* FindJob(const FString& JobId)
	{
		return Jobs.Find(JobId);
	}

	void TrackFallbackImportedObjects(BlueprintExtractorImport::FItemRecord& Item, BlueprintExtractorImport::FJobRecord& Job)
	{
		using namespace BlueprintExtractorImport;

		if (Item.Request.DestinationPath.IsEmpty())
		{
			return;
		}

		const FString ExpectedObjectPath = GetExpectedImportedObjectPath(Item.Request);
		if (!ExpectedObjectPath.IsEmpty())
		{
			if (UObject* ImportedObject = ResolveAssetByPath(ExpectedObjectPath))
			{
				TrackImportedObjectPath(Item, Job, ImportedObject->GetPathName());
			}
		}

		const TSet<FString> CurrentDestinationObjects = CollectDestinationObjectPaths(Item.Request.DestinationPath);
		for (const FString& ObjectPath : CurrentDestinationObjects)
		{
			if (!Item.KnownDestinationObjects.Contains(ObjectPath))
			{
				TrackImportedObjectPath(Item, Job, ObjectPath);
			}
		}

		TSet<FString> CandidateSources;
		if (!Item.Request.FilePath.IsEmpty())
		{
			CandidateSources.Add(ResolveFilePath(Item.Request.FilePath));
		}
		if (!Item.ResolvedSourcePath.IsEmpty())
		{
			CandidateSources.Add(ResolveFilePath(Item.ResolvedSourcePath));
		}
		if (!Item.StagedFilePath.IsEmpty())
		{
			CandidateSources.Add(ResolveFilePath(Item.StagedFilePath));
		}

		for (const FString& ObjectPath : CurrentDestinationObjects)
		{
			if (Item.ImportedObjects.Contains(ObjectPath))
			{
				continue;
			}

			UObject* Asset = ResolveAssetByPath(ObjectPath);
			if (!Asset)
			{
				continue;
			}

			if (HasMatchingImportSource(Asset, CandidateSources))
			{
				TrackImportedObjectPath(Item, Job, Asset->GetPathName());
			}
		}
	}

	void FinishImport(BlueprintExtractorImport::FJobRecord& Job, BlueprintExtractorImport::FItemRecord& Item)
	{
		using namespace BlueprintExtractorImport;

		if (Item.bCompletionProcessed || !Item.ImportTask.IsValid())
		{
			return;
		}

		if (Item.ImportTask->AsyncResults.IsValid())
		{
			Item.ImportTask->AsyncResults->WaitUntilDone();
		}
		else if (!Item.ImportTask->IsAsyncImportComplete())
		{
			return;
		}

		const TArray<UObject*>& Imported = Item.ImportTask->GetObjects();
		TrackImportedObjects(Item, Job, Imported);
		for (const FString& ImportedPath : Item.ImportTask->ImportedObjectPaths)
		{
			TrackImportedObjectPath(Item, Job, NormalizeAssetObjectPath(ImportedPath));
		}
		TrackFallbackImportedObjects(Item, Job);
		if (Item.ImportedObjects.Num() == 0 && ++Item.CompletionChecks < 30)
		{
			return;
		}

		Item.bCompletionProcessed = true;
		ApplyTextureOverrides(Item, Job);
		Item.State = Item.ImportedObjects.Num() > 0 ? EImportItemState::Succeeded : EImportItemState::Failed;
		if (Item.State == EImportItemState::Failed)
		{
			AddError(Item.Diagnostics, TEXT("import_failed"), TEXT("Import produced no assets."), FString::Printf(TEXT("items[%d]"), Item.Request.Index));
		}
		Item.ImportTask.Reset();
	}

	void FinishReimport(BlueprintExtractorImport::FJobRecord& Job, BlueprintExtractorImport::FItemRecord& Item)
	{
		using namespace BlueprintExtractorImport;

		if (Item.bCompletionProcessed || !Item.ReimportResult.IsValid())
		{
			return;
		}
		Item.ReimportResult->WaitUntilDone();

		TrackImportedObjects(Item, Job, Item.ReimportResult->GetImportedObjects());
		if (Item.ImportedObjects.Num() == 0)
		{
			if (Item.ReimportTarget.IsValid())
			{
				TrackImportedObjectPath(Item, Job, Item.ReimportTarget->GetPathName());
			}
			else if (UObject* ReimportedObject = ResolveAssetByPath(Item.Request.AssetPath))
			{
				TrackImportedObjectPath(Item, Job, ReimportedObject->GetPathName());
			}
		}
		if (Item.ImportedObjects.Num() == 0 && ++Item.CompletionChecks < 30)
		{
			return;
		}

		Item.bCompletionProcessed = true;
		Item.State = Item.ImportedObjects.Num() > 0 ? EImportItemState::Succeeded : EImportItemState::Failed;
		if (Item.State == EImportItemState::Failed)
		{
			AddError(Item.Diagnostics, TEXT("reimport_failed"), TEXT("Reimport produced no assets."), FString::Printf(TEXT("items[%d]"), Item.Request.Index));
		}
		Item.ReimportResult.Reset();
	}

	bool StartDownload(BlueprintExtractorImport::FJobRecord& Job, BlueprintExtractorImport::FItemRecord& Item)
	{
		using namespace BlueprintExtractorImport;

		if (Item.PendingRequest.IsValid())
		{
			return true;
		}

		const FString StagingDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("BlueprintExtractor"), TEXT("ImportStaging"), Job.JobId);
		IFileManager::Get().MakeDirectory(*StagingDir, true);
		const FString Filename = !Item.Request.Filename.IsEmpty() ? Item.Request.Filename : FPaths::GetCleanFilename(StripSensitiveUrlParts(Item.Request.Url));
		Item.StagedFilePath = FPaths::Combine(StagingDir, FString::Printf(TEXT("%02d_%s"), Item.Request.Index, *Filename));
		Item.State = EImportItemState::Downloading;
		if (!Job.StartedAt.IsSet())
		{
			Job.StartedAt = FDateTime::UtcNow();
		}

		const FString JobId = Job.JobId;
		const int32 ItemIndex = Item.Request.Index;
		TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
		Request->SetURL(Item.Request.Url);
		Request->SetVerb(TEXT("GET"));
		for (const TPair<FString, FString>& Header : Item.Request.Headers)
		{
			Request->SetHeader(Header.Key, Header.Value);
		}

		Request->OnProcessRequestComplete().BindLambda([this, JobId, ItemIndex](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded)
		{
			AsyncTask(ENamedThreads::GameThread, [this, JobId, ItemIndex, Response, bSucceeded]()
			{
				using namespace BlueprintExtractorImport;

				FJobRecord* JobRecord = FindJob(JobId);
				if (!JobRecord || !JobRecord->Items.IsValidIndex(ItemIndex))
				{
					return;
				}

				FItemRecord& Runtime = JobRecord->Items[ItemIndex];
				Runtime.PendingRequest.Reset();
				if (!bSucceeded || !Response.IsValid() || Response->GetResponseCode() < 200 || Response->GetResponseCode() >= 300)
				{
					AddError(Runtime.Diagnostics, TEXT("download_failed"), FString::Printf(TEXT("Failed to download: %s"), *StripSensitiveUrlParts(Runtime.Request.Url)), FString::Printf(TEXT("items[%d]"), Runtime.Request.Index));
					Runtime.State = EImportItemState::Failed;
					FinalizeJob(*JobRecord);
					return;
				}
				if (!FFileHelper::SaveArrayToFile(Response->GetContent(), *Runtime.StagedFilePath))
				{
					AddError(Runtime.Diagnostics, TEXT("stage_failed"), TEXT("Failed to write staged import file."), FString::Printf(TEXT("items[%d]"), Runtime.Request.Index));
					Runtime.State = EImportItemState::Failed;
					FinalizeJob(*JobRecord);
					return;
				}
				Runtime.ResolvedSourcePath = Runtime.StagedFilePath;
				Runtime.State = EImportItemState::Staged;
				FinalizeJob(*JobRecord);
			});
		});

		if (!Request->ProcessRequest())
		{
			AddError(Item.Diagnostics, TEXT("download_failed"), TEXT("Failed to start download request."), FString::Printf(TEXT("items[%d]"), Item.Request.Index));
			Item.State = EImportItemState::Failed;
			return false;
		}

		Item.PendingRequest = Request;
		return true;
	}

	bool StartImport(BlueprintExtractorImport::FJobRecord& Job, BlueprintExtractorImport::FItemRecord& Item)
	{
		using namespace BlueprintExtractorImport;

		const FString SourceFile = Item.Request.SourceKind == ESourceKind::Url ? Item.StagedFilePath : Item.Request.FilePath;
		if (!FPaths::FileExists(SourceFile))
		{
			AddError(Item.Diagnostics, TEXT("source_not_found"), FString::Printf(TEXT("Source file not found: %s"), *SourceFile), FString::Printf(TEXT("items[%d]"), Item.Request.Index));
			Item.State = EImportItemState::Failed;
			return false;
		}

		Item.KnownDestinationObjects = CollectDestinationObjectPaths(Item.Request.DestinationPath);

		UAssetImportTask* Task = NewObject<UAssetImportTask>(GetTransientPackage());
		if (!Task)
		{
			AddError(Item.Diagnostics, TEXT("import_task_failed"), TEXT("Failed to allocate import task."), FString::Printf(TEXT("items[%d]"), Item.Request.Index));
			Item.State = EImportItemState::Failed;
			return false;
		}

		Task->Filename = SourceFile;
		Task->DestinationPath = Item.Request.DestinationPath;
		Task->DestinationName = Item.Request.DestinationName;
		Task->bReplaceExisting = Item.Request.bReplaceExisting;
		Task->bReplaceExistingSettings = Item.Request.bReplaceExistingSettings;
		Task->bAutomated = true;
		Task->bSave = false;
		Task->bAsync = true;

		if (Job.Kind == EImportJobKind::Texture && Item.Request.TextureOptions.IsSet())
		{
			UTextureFactory* Factory = NewObject<UTextureFactory>(GetTransientPackage());
			const BlueprintExtractorImport::FTextureOptions& Options = Item.Request.TextureOptions.GetValue();
			if (Options.CompressionSettings.IsSet()) Factory->CompressionSettings = Options.CompressionSettings.GetValue();
			if (Options.LODGroup.IsSet()) Factory->LODGroup = Options.LODGroup.GetValue();
			if (Options.bFlipGreenChannel.IsSet()) Factory->bFlipNormalMapGreenChannel = Options.bFlipGreenChannel.GetValue();
			Task->Factory = Factory;
		}
		else if (Job.Kind == EImportJobKind::Mesh && Item.Request.MeshOptions.IsSet())
		{
			UFbxImportUI* Options = NewObject<UFbxImportUI>(GetTransientPackage());
			Options->bAutomatedImportShouldDetectType = false;
			Options->bImportAsSkeletal = Item.Request.MeshOptions->MeshType == EMeshImportType::Skeletal;
			Options->bImportMesh = true;
			Options->SetMeshTypeToImport();
			if (Options->StaticMeshImportData && Item.Request.MeshOptions->bCombineMeshes.IsSet()) Options->StaticMeshImportData->bCombineMeshes = Item.Request.MeshOptions->bCombineMeshes.GetValue();
			if (Options->StaticMeshImportData && Item.Request.MeshOptions->bGenerateCollision.IsSet()) Options->StaticMeshImportData->bAutoGenerateCollision = Item.Request.MeshOptions->bGenerateCollision.GetValue();
			if (Item.Request.MeshOptions->bImportMaterials.IsSet()) Options->bImportMaterials = Item.Request.MeshOptions->bImportMaterials.GetValue();
			if (Item.Request.MeshOptions->bImportTextures.IsSet()) Options->bImportTextures = Item.Request.MeshOptions->bImportTextures.GetValue();
			if (Item.Request.MeshOptions->bImportAnimations.IsSet()) Options->bImportAnimations = Item.Request.MeshOptions->bImportAnimations.GetValue();
			if (Item.Request.MeshOptions->MeshType == EMeshImportType::Skeletal)
			{
				Options->Skeleton = Cast<USkeleton>(ResolveAssetByPath(Item.Request.MeshOptions->SkeletonPath));
				if (!Options->Skeleton)
				{
					AddError(Item.Diagnostics, TEXT("skeleton_not_found"), TEXT("mesh_options.skeleton_path must resolve to a Skeleton asset."), FString::Printf(TEXT("items[%d].options"), Item.Request.Index));
					Item.State = EImportItemState::Failed;
					return false;
				}
			}
			Task->Options = Options;
		}

		Item.ImportTask = TStrongObjectPtr<UAssetImportTask>(Task);
		Item.ResolvedSourcePath = SourceFile;
		Item.State = EImportItemState::Importing;
		if (!Job.StartedAt.IsSet())
		{
			Job.StartedAt = FDateTime::UtcNow();
		}

		TArray<UAssetImportTask*> Tasks;
		Tasks.Add(Task);
		FAssetToolsModule& AssetToolsModule = FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools"));
		AssetToolsModule.Get().ImportAssetTasks(Tasks);
		return true;
	}

	void StartReimport(BlueprintExtractorImport::FJobRecord& Job, BlueprintExtractorImport::FItemRecord& Item)
	{
		using namespace BlueprintExtractorImport;

		UObject* Target = ResolveAssetByPath(Item.Request.AssetPath);
		if (!Target)
		{
			AddError(Item.Diagnostics, TEXT("asset_not_found"), FString::Printf(TEXT("Asset not found: %s"), *Item.Request.AssetPath), FString::Printf(TEXT("items[%d]"), Item.Request.Index));
			Item.State = EImportItemState::Failed;
			return;
		}

		FString PreferredSource;
		if (Item.Request.SourceKind == ESourceKind::File)
		{
			PreferredSource = Item.Request.FilePath;
			FReimportManager::Instance()->UpdateReimportPath(Target, PreferredSource, INDEX_NONE);
		}
		else if (Item.Request.SourceKind == ESourceKind::Url)
		{
			PreferredSource = Item.StagedFilePath;
			FReimportManager::Instance()->UpdateReimportPath(Target, PreferredSource, INDEX_NONE);
		}

		Item.ReimportTarget = Target;
		Item.State = EImportItemState::Importing;
		if (!Job.StartedAt.IsSet())
		{
			Job.StartedAt = FDateTime::UtcNow();
		}
		Item.ReimportResult = FReimportManager::Instance()->ReimportAsync(Target, false, false, PreferredSource, nullptr, INDEX_NONE, false, true, false);
	}

	void UpdateJob(BlueprintExtractorImport::FJobRecord& Job)
	{
		using namespace BlueprintExtractorImport;

		for (FItemRecord& Item : Job.Items)
		{
			switch (Item.State)
			{
			case EImportItemState::Queued:
				if (Job.Kind == EImportJobKind::Reimport)
				{
					if (Item.Request.SourceKind == ESourceKind::Url) StartDownload(Job, Item); else StartReimport(Job, Item);
				}
				else
				{
					if (Item.Request.SourceKind == ESourceKind::Url) StartDownload(Job, Item); else StartImport(Job, Item);
				}
				break;
			case EImportItemState::Staged:
				if (Job.Kind == EImportJobKind::Reimport) StartReimport(Job, Item); else StartImport(Job, Item);
				break;
			case EImportItemState::Importing:
				if (Job.Kind == EImportJobKind::Reimport) FinishReimport(Job, Item); else FinishImport(Job, Item);
				break;
			default:
				break;
			}
		}
		FinalizeJob(Job);
	}

	TSharedPtr<FJsonObject> Enqueue(const BlueprintExtractorImport::EImportJobKind Kind, const FString& Operation, const FString& PayloadJson, const bool bValidateOnly)
	{
		using namespace BlueprintExtractorImport;

		int32 ItemCount = 0;
		TArray<FItemRequest> Requests;
		TArray<FDiagnostic> ParseDiagnostics;
		ParsePayload(PayloadJson, Kind, ItemCount, Requests, ParseDiagnostics);

		FJobRecord Job;
		Job.JobId = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens);
		Job.Operation = Operation;
		Job.Kind = Kind;
		Job.bValidateOnly = bValidateOnly;
		Job.Items.SetNum(ItemCount);
		for (int32 Index = 0; Index < ItemCount; ++Index)
		{
			Job.Items[Index].Request.Index = Index;
		}
		for (const FDiagnostic& Diagnostic : ParseDiagnostics)
		{
			const TOptional<int32> Index = ParseItemIndex(Diagnostic.Path);
			if (Index.IsSet() && Job.Items.IsValidIndex(Index.GetValue()))
			{
				Job.Items[Index.GetValue()].Diagnostics.Add(Diagnostic);
			}
			else
			{
				Job.Diagnostics.Add(Diagnostic);
			}
		}

		for (FItemRequest& Request : Requests)
		{
			FItemRecord& Item = Job.Items[Request.Index];
			Item.Request = Request;
			const FString Path = FString::Printf(TEXT("items[%d]"), Request.Index);
			const bool bSourceValid = ValidateSource(Item.Request, Kind == EImportJobKind::Reimport, Item.Diagnostics, Path);
			const bool bTargetValid = Kind == EImportJobKind::Reimport
				? ValidateReimportTarget(Item.Request, Item.Diagnostics, Path)
				: ValidateImportTarget(Item.Request, Item.Diagnostics, Path);
			if (Kind == EImportJobKind::Mesh && Item.Request.MeshOptions.IsSet())
			{
				const FString MeshFilename = Item.Request.SourceKind == ESourceKind::Url ? Item.Request.Filename : Item.Request.FilePath;
				const FString Extension = FPaths::GetExtension(MeshFilename, true).ToLower();
				const bool bStaticOk = Item.Request.MeshOptions->MeshType == EMeshImportType::Static && (Extension == TEXT(".fbx") || Extension == TEXT(".obj"));
				const bool bSkeletalOk = Item.Request.MeshOptions->MeshType == EMeshImportType::Skeletal && Extension == TEXT(".fbx");
				if (!(bStaticOk || bSkeletalOk))
				{
					AddError(Item.Diagnostics, TEXT("unsupported_extension"), TEXT("Mesh helper supports .fbx for skeletal meshes and .fbx/.obj for static meshes."), Path);
				}
			}
			Item.bAccepted = Item.Diagnostics.Num() == 0 && bSourceValid && bTargetValid;
			Item.State = (Item.Diagnostics.Num() == 0 && bSourceValid && bTargetValid)
				? (bValidateOnly ? EImportItemState::Succeeded : EImportItemState::Queued)
				: EImportItemState::Failed;
		}

		FinalizeJob(Job);
		const FString StoredJobId = Job.JobId;
		Jobs.Add(StoredJobId, MoveTemp(Job));
		BlueprintExtractorImport::FJobRecord* Stored = FindJob(StoredJobId);
		if (Stored && !bValidateOnly && !Stored->CompletedAt.IsSet())
		{
			UpdateJob(*Stored);
		}
		return Stored ? BuildJobJson(*Stored) : BuildMissingJobJson(Operation, TEXT("<generated>"));
	}
};

FBlueprintExtractorImportJobManager::FBlueprintExtractorImportJobManager()
	: Impl(MakeUnique<FImpl>())
{
}

FBlueprintExtractorImportJobManager::~FBlueprintExtractorImportJobManager() = default;

TSharedPtr<FJsonObject> FBlueprintExtractorImportJobManager::EnqueueImportJob(const FString& Operation,
                                                                              const FString& PayloadJson,
                                                                              const bool bValidateOnly)
{
	return Impl->Enqueue(BlueprintExtractorImport::EImportJobKind::Generic, Operation, PayloadJson, bValidateOnly);
}

TSharedPtr<FJsonObject> FBlueprintExtractorImportJobManager::EnqueueReimportJob(const FString& Operation,
                                                                                const FString& PayloadJson,
                                                                                const bool bValidateOnly)
{
	return Impl->Enqueue(BlueprintExtractorImport::EImportJobKind::Reimport, Operation, PayloadJson, bValidateOnly);
}

TSharedPtr<FJsonObject> FBlueprintExtractorImportJobManager::EnqueueTextureImportJob(const FString& Operation,
                                                                                     const FString& PayloadJson,
                                                                                     const bool bValidateOnly)
{
	return Impl->Enqueue(BlueprintExtractorImport::EImportJobKind::Texture, Operation, PayloadJson, bValidateOnly);
}

TSharedPtr<FJsonObject> FBlueprintExtractorImportJobManager::EnqueueMeshImportJob(const FString& Operation,
                                                                                  const FString& PayloadJson,
                                                                                  const bool bValidateOnly)
{
	return Impl->Enqueue(BlueprintExtractorImport::EImportJobKind::Mesh, Operation, PayloadJson, bValidateOnly);
}

TSharedPtr<FJsonObject> FBlueprintExtractorImportJobManager::GetImportJob(const FString& JobId)
{
	for (TPair<FString, BlueprintExtractorImport::FJobRecord>& Pair : Impl->Jobs)
	{
		if (!Pair.Value.CompletedAt.IsSet())
		{
			Impl->UpdateJob(Pair.Value);
		}
	}

	if (const BlueprintExtractorImport::FJobRecord* Job = Impl->Jobs.Find(JobId))
	{
		return BlueprintExtractorImport::BuildJobJson(*Job);
	}

	return BlueprintExtractorImport::BuildMissingJobJson(TEXT("get_import_job"), JobId);
}

TSharedPtr<FJsonObject> FBlueprintExtractorImportJobManager::ListImportJobs(const bool bIncludeCompleted)
{
	for (TPair<FString, BlueprintExtractorImport::FJobRecord>& Pair : Impl->Jobs)
	{
		if (!Pair.Value.CompletedAt.IsSet())
		{
			Impl->UpdateJob(Pair.Value);
		}
	}

	TArray<FString> JobIds;
	Impl->Jobs.GetKeys(JobIds);
	JobIds.Sort();

	TArray<TSharedPtr<FJsonValue>> JobsJson;
	for (const FString& JobId : JobIds)
	{
		const BlueprintExtractorImport::FJobRecord* Job = Impl->Jobs.Find(JobId);
		if (!Job || (!bIncludeCompleted && Job->CompletedAt.IsSet()))
		{
			continue;
		}
		JobsJson.Add(MakeShared<FJsonValueObject>(BlueprintExtractorImport::BuildJobJson(*Job)));
	}

	TSharedPtr<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetBoolField(TEXT("success"), true);
	Json->SetStringField(TEXT("operation"), TEXT("list_import_jobs"));
	Json->SetBoolField(TEXT("includeCompleted"), bIncludeCompleted);
	Json->SetNumberField(TEXT("jobCount"), JobsJson.Num());
	Json->SetArrayField(TEXT("jobs"), JobsJson);
	return Json;
}
