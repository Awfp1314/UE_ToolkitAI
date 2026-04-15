#include "Capture/CaptureTypes.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Editor.h"
#include "Engine/GameViewportClient.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "ImageUtils.h"
#include "Misc/App.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Slate/WidgetRenderer.h"
#include "UnrealClient.h"
#include "Blueprint/UserWidget.h"
#include "Animation/WidgetAnimation.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "MovieScene.h"
#include "WidgetBlueprint.h"
#include "Slate/SceneViewport.h"

namespace BlueprintExtractorCapture
{
namespace
{
	static constexpr TCHAR CaptureArtifactName[] = TEXT("capture.png");
	static constexpr TCHAR CaptureMetadataName[] = TEXT("metadata.json");

	FString GetCaptureRootDirectory()
	{
		return FPaths::ConvertRelativePathToFull(
			FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("BlueprintExtractor"), TEXT("Captures")));
	}

	FString BuildCaptureDirectory(const FString& CaptureId)
	{
		return FPaths::Combine(GetCaptureRootDirectory(), CaptureId);
	}

	FString BuildCaptureArtifactPath(const FString& CaptureId)
	{
		return FPaths::Combine(BuildCaptureDirectory(CaptureId), CaptureArtifactName);
	}

	FString BuildCaptureMetadataPath(const FString& CaptureId)
	{
		return FPaths::Combine(BuildCaptureDirectory(CaptureId), CaptureMetadataName);
	}

	FString MakeCaptureId(const FString& SourceName, const FString& Suffix)
	{
		const FString SafeSource = FPaths::MakeValidFileName(SourceName.IsEmpty() ? TEXT("capture") : SourceName);
		return FString::Printf(
			TEXT("%s_%s_%s"),
			*SafeSource,
			*Suffix,
			*FGuid::NewGuid().ToString(EGuidFormats::Digits));
	}

	bool EnsureDirectory(const FString& DirectoryPath, FString& OutError)
	{
		if (IFileManager::Get().MakeDirectory(*DirectoryPath, true))
		{
			return true;
		}

		OutError = FString::Printf(TEXT("Failed to create directory: %s"), *DirectoryPath);
		return false;
	}

	TSharedPtr<FJsonObject> ParseJsonFile(const FString& FilePath)
	{
		FString RawJson;
		if (!FFileHelper::LoadFileToString(RawJson, *FilePath))
		{
			return nullptr;
		}

		TSharedPtr<FJsonObject> Parsed;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RawJson);
		if (!FJsonSerializer::Deserialize(Reader, Parsed) || !Parsed.IsValid())
		{
			return nullptr;
		}

		return Parsed;
	}

	bool WriteJsonFile(const FString& FilePath, const TSharedPtr<FJsonObject>& JsonObject, FString& OutError)
	{
		if (!JsonObject.IsValid())
		{
			OutError = TEXT("Missing JSON object to write.");
			return false;
		}

		FString RawJson;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&RawJson);
		if (!FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer))
		{
			OutError = FString::Printf(TEXT("Failed to serialize JSON file: %s"), *FilePath);
			return false;
		}

		if (!FFileHelper::SaveStringToFile(RawJson, *FilePath))
		{
			OutError = FString::Printf(TEXT("Failed to write JSON file: %s"), *FilePath);
			return false;
		}

		return true;
	}

	TArray<FString> JsonArrayToStringArray(const TArray<TSharedPtr<FJsonValue>>& Values)
	{
		TArray<FString> Result;
		Result.Reserve(Values.Num());
		for (const TSharedPtr<FJsonValue>& Value : Values)
		{
			FString StringValue;
			if (Value.IsValid() && Value->TryGetString(StringValue) && !StringValue.IsEmpty())
			{
				Result.Add(StringValue);
			}
		}
		return Result;
	}

	TArray<TSharedPtr<FJsonValue>> StringArrayToJsonArray(const TArray<FString>& Values)
	{
		TArray<TSharedPtr<FJsonValue>> Result;
		Result.Reserve(Values.Num());
		for (const FString& Value : Values)
		{
			Result.Add(MakeShared<FJsonValueString>(Value));
		}
		return Result;
	}

	FString InferVerificationSurface(const FString& CaptureType)
	{
		if (CaptureType == TEXT("widget_motion_checkpoint"))
		{
			return TEXT("widget_motion_checkpoint");
		}
		if (CaptureType == TEXT("editor_screenshot"))
		{
			return TEXT("editor_tool_viewport");
		}
		if (CaptureType == TEXT("runtime_screenshot"))
		{
			return TEXT("pie_runtime");
		}
		if (CaptureType == TEXT("widget_preview") || CaptureType == TEXT("comparison_diff"))
		{
			return TEXT("editor_offscreen");
		}

		return TEXT("editor_offscreen");
	}

	FString BuildScenarioId(const FBlueprintExtractorCaptureMetadata& Metadata)
	{
		const FString Source = !Metadata.AssetPath.IsEmpty()
			? Metadata.AssetPath
			: (!Metadata.CaptureId.IsEmpty() ? Metadata.CaptureId : TEXT("capture"));
		const FString Prefix = !Metadata.CaptureType.IsEmpty() ? Metadata.CaptureType : TEXT("capture");
		return FString::Printf(TEXT("%s:%s"), *Prefix, *Source);
	}

	TSharedPtr<FJsonObject> BuildDefaultWorldContext(const FBlueprintExtractorCaptureMetadata& Metadata)
	{
		const TSharedPtr<FJsonObject> Context = MakeShared<FJsonObject>();
		if (!Metadata.AssetPath.IsEmpty())
		{
			Context->SetStringField(TEXT("assetPath"), Metadata.AssetPath);
		}
		if (!Metadata.WidgetClass.IsEmpty())
		{
			Context->SetStringField(TEXT("widgetClass"), Metadata.WidgetClass);
		}
		if (Metadata.Surface == TEXT("editor_offscreen"))
		{
			Context->SetStringField(TEXT("contextType"), TEXT("widget_blueprint"));
			Context->SetStringField(TEXT("renderLane"), TEXT("offscreen"));
		}
		else if (Metadata.Surface == TEXT("editor_tool_viewport"))
		{
			Context->SetStringField(TEXT("contextType"), TEXT("editor_viewport"));
			Context->SetStringField(TEXT("renderLane"), TEXT("viewport"));
			Context->SetBoolField(TEXT("isPlayingInEditor"), false);
		}
		else if (Metadata.Surface == TEXT("pie_runtime"))
		{
			Context->SetStringField(TEXT("contextType"), TEXT("runtime_viewport"));
			Context->SetStringField(TEXT("renderLane"), TEXT("viewport"));
			Context->SetBoolField(TEXT("isPlayingInEditor"), true);
		}
		else
		{
			Context->SetStringField(TEXT("contextType"), TEXT("capture"));
		}

		return Context;
	}

	TSharedPtr<FJsonObject> BuildDefaultCameraContext(const FBlueprintExtractorCaptureMetadata& Metadata)
	{
		const TSharedPtr<FJsonObject> Context = MakeShared<FJsonObject>();
		if (Metadata.Surface == TEXT("editor_offscreen"))
		{
			Context->SetStringField(TEXT("contextType"), TEXT("offscreen_widget"));
		}
		else if (Metadata.Surface == TEXT("editor_tool_viewport"))
		{
			Context->SetStringField(TEXT("contextType"), TEXT("editor_viewport"));
		}
		else if (Metadata.Surface == TEXT("pie_runtime"))
		{
			Context->SetStringField(TEXT("contextType"), TEXT("runtime_viewport"));
		}
		else
		{
			Context->SetStringField(TEXT("contextType"), TEXT("capture_frame"));
		}
		if (Metadata.Width > 0)
		{
			Context->SetNumberField(TEXT("width"), Metadata.Width);
		}
		if (Metadata.Height > 0)
		{
			Context->SetNumberField(TEXT("height"), Metadata.Height);
		}
		return Context;
	}

	void EnsureVerificationArtifactDefaults(FBlueprintExtractorCaptureMetadata& Metadata)
	{
		if (Metadata.AssetPaths.Num() == 0 && !Metadata.AssetPath.IsEmpty())
		{
			Metadata.AssetPaths.Add(Metadata.AssetPath);
		}
		if (Metadata.AssetPath.IsEmpty() && Metadata.AssetPaths.Num() > 0)
		{
			Metadata.AssetPath = Metadata.AssetPaths[0];
		}
		if (Metadata.Surface.IsEmpty())
		{
			Metadata.Surface = InferVerificationSurface(Metadata.CaptureType);
		}
		if (Metadata.ScenarioId.IsEmpty())
		{
			Metadata.ScenarioId = BuildScenarioId(Metadata);
		}
		if (!Metadata.WorldContext.IsValid())
		{
			Metadata.WorldContext = BuildDefaultWorldContext(Metadata);
		}
		if (!Metadata.CameraContext.IsValid())
		{
			Metadata.CameraContext = BuildDefaultCameraContext(Metadata);
		}
	}

	bool ReadCaptureMetadata(const FString& MetadataPath, FBlueprintExtractorCaptureMetadata& OutMetadata)
	{
		const TSharedPtr<FJsonObject> Parsed = ParseJsonFile(MetadataPath);
		if (!Parsed.IsValid())
		{
			return false;
		}

		double FileSize = 0.0;
		double Width = 0.0;
		double Height = 0.0;

		if (!Parsed->TryGetStringField(TEXT("captureId"), OutMetadata.CaptureId))
		{
			return false;
		}

		Parsed->TryGetStringField(TEXT("captureType"), OutMetadata.CaptureType);
		Parsed->TryGetStringField(TEXT("surface"), OutMetadata.Surface);
		Parsed->TryGetStringField(TEXT("scenarioId"), OutMetadata.ScenarioId);
		Parsed->TryGetStringField(TEXT("assetPath"), OutMetadata.AssetPath);
		Parsed->TryGetStringField(TEXT("widgetClass"), OutMetadata.WidgetClass);
		Parsed->TryGetStringField(TEXT("captureDirectory"), OutMetadata.CaptureDirectory);
		Parsed->TryGetStringField(TEXT("artifactPath"), OutMetadata.ArtifactPath);
		Parsed->TryGetStringField(TEXT("metadataPath"), OutMetadata.MetadataPath);
		Parsed->TryGetStringField(TEXT("createdAt"), OutMetadata.CreatedAt);
		Parsed->TryGetStringField(TEXT("projectDir"), OutMetadata.ProjectDir);
		Parsed->TryGetStringField(TEXT("motionCaptureId"), OutMetadata.MotionCaptureId);
		Parsed->TryGetStringField(TEXT("checkpointName"), OutMetadata.CheckpointName);
		Parsed->TryGetStringField(TEXT("playbackSource"), OutMetadata.PlaybackSource);
		Parsed->TryGetStringField(TEXT("triggerMode"), OutMetadata.TriggerMode);
		Parsed->TryGetNumberField(TEXT("width"), Width);
		Parsed->TryGetNumberField(TEXT("height"), Height);
		Parsed->TryGetNumberField(TEXT("fileSizeBytes"), FileSize);
		Parsed->TryGetNumberField(TEXT("checkpointMs"), OutMetadata.CheckpointMs);
		const TArray<TSharedPtr<FJsonValue>>* AssetPathArray = nullptr;
		if (Parsed->TryGetArrayField(TEXT("assetPaths"), AssetPathArray) && AssetPathArray)
		{
			OutMetadata.AssetPaths = JsonArrayToStringArray(*AssetPathArray);
		}
		const TSharedPtr<FJsonObject>* WorldContext = nullptr;
		if (Parsed->TryGetObjectField(TEXT("worldContext"), WorldContext) && WorldContext)
		{
			OutMetadata.WorldContext = *WorldContext;
		}
		const TSharedPtr<FJsonObject>* CameraContext = nullptr;
		if (Parsed->TryGetObjectField(TEXT("cameraContext"), CameraContext) && CameraContext)
		{
			OutMetadata.CameraContext = *CameraContext;
		}
		const TSharedPtr<FJsonObject>* Comparison = nullptr;
		if (Parsed->TryGetObjectField(TEXT("comparison"), Comparison) && Comparison)
		{
			OutMetadata.Comparison = *Comparison;
		}
		OutMetadata.Width = FMath::Max(0, FMath::RoundToInt(Width));
		OutMetadata.Height = FMath::Max(0, FMath::RoundToInt(Height));
		OutMetadata.FileSizeBytes = FMath::Max<int64>(0, FMath::RoundToInt64(FileSize));

		if (OutMetadata.MetadataPath.IsEmpty())
		{
			OutMetadata.MetadataPath = MetadataPath;
		}

		if (OutMetadata.CaptureDirectory.IsEmpty())
		{
			OutMetadata.CaptureDirectory = FPaths::GetPath(MetadataPath);
		}

		EnsureVerificationArtifactDefaults(OutMetadata);

		return true;
	}

	bool WriteCaptureMetadata(const FBlueprintExtractorCaptureMetadata& Metadata, FString& OutError)
	{
		return WriteJsonFile(Metadata.MetadataPath, CaptureMetadataToJson(Metadata), OutError);
	}

	bool ResolveCaptureInput(const FString& CaptureIdOrPath, FString& OutPath, FBlueprintExtractorCaptureMetadata* OutMetadata = nullptr)
	{
		if (CaptureIdOrPath.IsEmpty())
		{
			return false;
		}

		const FString AbsoluteInput = FPaths::ConvertRelativePathToFull(CaptureIdOrPath);
		if (FPaths::FileExists(AbsoluteInput))
		{
			OutPath = AbsoluteInput;
			return true;
		}

		const FString CaptureDirectory = BuildCaptureDirectory(CaptureIdOrPath);
		const FString ArtifactPath = FPaths::Combine(CaptureDirectory, CaptureArtifactName);
		const FString MetadataPath = FPaths::Combine(CaptureDirectory, CaptureMetadataName);
		if (!FPaths::FileExists(ArtifactPath))
		{
			return false;
		}

		OutPath = ArtifactPath;
		if (OutMetadata)
		{
			ReadCaptureMetadata(MetadataPath, *OutMetadata);
		}
		return true;
	}

	int64 CalculateDirectorySize(const FString& DirectoryPath)
	{
		class FDirectorySizeVisitor final : public IPlatformFile::FDirectoryVisitor
		{
		public:
			int64 TotalBytes = 0;

			virtual bool Visit(const TCHAR* FilenameOrDirectory, bool bIsDirectory) override
			{
				if (!bIsDirectory)
				{
					TotalBytes += IFileManager::Get().FileSize(FilenameOrDirectory);
				}
				return true;
			}
		};

		FDirectorySizeVisitor Visitor;
		FPlatformFileManager::Get().GetPlatformFile().IterateDirectoryRecursively(*DirectoryPath, Visitor);
		return Visitor.TotalBytes;
	}

	bool LoadComparableImage(const FString& FilePath, FImage& OutImage, FString& OutError)
	{
		if (!FImageUtils::LoadImage(*FilePath, OutImage))
		{
			OutError = FString::Printf(TEXT("Failed to load image: %s"), *FilePath);
			return false;
		}

		OutImage.ChangeFormat(ERawImageFormat::BGRA8, EGammaSpace::sRGB);
		return true;
	}

	bool SaveImageAsPng(const FString& FilePath, const FImage& Image, FString& OutError)
	{
		if (!FImageUtils::SaveImageByExtension(*FilePath, Image))
		{
			OutError = FString::Printf(TEXT("Failed to write PNG file: %s"), *FilePath);
			return false;
		}

		return true;
	}

	struct FMotionCheckpointRequest
	{
		FString Name;
		double TimeMs = -1.0;
	};

	UWidgetAnimation* FindRuntimeAnimationByName(UWidgetBlueprint* WidgetBlueprint, const FString& AnimationName)
	{
		if (!WidgetBlueprint)
		{
			return nullptr;
		}

		const UWidgetBlueprintGeneratedClass* GeneratedClass = Cast<UWidgetBlueprintGeneratedClass>(WidgetBlueprint->GeneratedClass);
		if (!GeneratedClass)
		{
			return nullptr;
		}

		for (UWidgetAnimation* Animation : GeneratedClass->Animations)
		{
			if (Animation && (Animation->GetName() == AnimationName || Animation->GetFName().ToString() == AnimationName))
			{
				return Animation;
			}
		}

		return nullptr;
	}

	UWidgetAnimation* FindAuthoredAnimationByName(UWidgetBlueprint* WidgetBlueprint, const FString& AnimationName)
	{
		if (!WidgetBlueprint)
		{
			return nullptr;
		}

		for (UWidgetAnimation* Animation : WidgetBlueprint->Animations)
		{
			if (Animation && (Animation->GetName() == AnimationName || Animation->GetFName().ToString() == AnimationName))
			{
				return Animation;
			}
		}

		return nullptr;
	}

	bool ParseMotionCheckpointRequests(const TSharedPtr<FJsonObject>& Payload,
	                                  UWidgetAnimation* AuthoredAnimation,
	                                  TArray<FMotionCheckpointRequest>& OutCheckpoints,
	                                  bool& bOutPartialVerification)
	{
		OutCheckpoints.Reset();
		bOutPartialVerification = false;

		const TArray<TSharedPtr<FJsonValue>>* Checkpoints = nullptr;
		if (Payload.IsValid() && Payload->TryGetArrayField(TEXT("checkpoints"), Checkpoints) && Checkpoints)
		{
			for (const TSharedPtr<FJsonValue>& CheckpointValue : *Checkpoints)
			{
				const TSharedPtr<FJsonObject> Checkpoint = CheckpointValue.IsValid() ? CheckpointValue->AsObject() : nullptr;
				if (!Checkpoint.IsValid())
				{
					continue;
				}

				FMotionCheckpointRequest Request;
				Checkpoint->TryGetStringField(TEXT("name"), Request.Name);
				Checkpoint->TryGetNumberField(TEXT("time_ms"), Request.TimeMs);
				if (Request.TimeMs < 0.0)
				{
					Checkpoint->TryGetNumberField(TEXT("timeMs"), Request.TimeMs);
				}
				if (!Request.Name.IsEmpty())
				{
					OutCheckpoints.Add(Request);
				}
			}
		}

		if (OutCheckpoints.Num() == 0 && AuthoredAnimation && AuthoredAnimation->MovieScene)
		{
			for (const FMovieSceneMarkedFrame& MarkedFrame : AuthoredAnimation->MovieScene->GetMarkedFrames())
			{
				OutCheckpoints.Add({ MarkedFrame.Label, AuthoredAnimation->MovieScene->GetTickResolution().AsSeconds(MarkedFrame.FrameNumber) * 1000.0 });
			}
		}

		if (OutCheckpoints.Num() == 0 && AuthoredAnimation)
		{
			const double EndTimeMs = AuthoredAnimation->GetEndTime() * 1000.0;
			OutCheckpoints.Add({ TEXT("closed"), 0.0 });
			OutCheckpoints.Add({ TEXT("opening_peak"), EndTimeMs * 0.5 });
			OutCheckpoints.Add({ TEXT("open"), EndTimeMs });
			bOutPartialVerification = true;
		}

		if (AuthoredAnimation && AuthoredAnimation->MovieScene)
		{
			for (FMotionCheckpointRequest& Request : OutCheckpoints)
			{
				if (Request.TimeMs >= 0.0)
				{
					continue;
				}

				const int32 MarkedFrameIndex = AuthoredAnimation->MovieScene->FindMarkedFrameByLabel(Request.Name);
				if (MarkedFrameIndex >= 0)
				{
					Request.TimeMs = AuthoredAnimation->MovieScene->GetTickResolution().AsSeconds(
						AuthoredAnimation->MovieScene->GetMarkedFrames()[MarkedFrameIndex].FrameNumber) * 1000.0;
				}
			}
		}

		OutCheckpoints.RemoveAll([](const FMotionCheckpointRequest& Request)
		{
			return Request.Name.IsEmpty() || Request.TimeMs < 0.0;
		});
		return OutCheckpoints.Num() > 0;
	}

	bool CaptureWidgetInstance(UUserWidget* WidgetInstance,
	                          const FString& SourceName,
	                          const FString& CaptureSuffix,
	                          FBlueprintExtractorCaptureMetadata& OutMetadata,
	                          FString& OutError,
	                          const int32 RequestedWidth,
	                          const int32 RequestedHeight)
	{
		if (!WidgetInstance)
		{
			OutError = TEXT("Widget instance is null.");
			return false;
		}

		const int32 Width = FMath::Clamp(RequestedWidth, 64, 2048);
		const int32 Height = FMath::Clamp(RequestedHeight, 64, 2048);
		const TSharedRef<SWidget> SlateWidget = WidgetInstance->TakeWidget();
		WidgetInstance->ForceLayoutPrepass();

		UTextureRenderTarget2D* RenderTarget = FWidgetRenderer::CreateTargetFor(FVector2D(Width, Height), TF_Bilinear, true);
		if (!RenderTarget)
		{
			OutError = TEXT("Failed to allocate a render target for widget capture.");
			return false;
		}

		{
			FWidgetRenderer Renderer(true, true);
			Renderer.DrawWidget(RenderTarget, SlateWidget, FVector2D(Width, Height), 0.0f);
		}

		FlushRenderingCommands();

		FImage CapturedImage;
		if (!FImageUtils::GetRenderTargetImage(RenderTarget, CapturedImage))
		{
			OutError = TEXT("Failed to read pixels from the widget capture render target.");
			return false;
		}

		OutMetadata.CaptureId = MakeCaptureId(SourceName, CaptureSuffix);
		OutMetadata.CaptureDirectory = BuildCaptureDirectory(OutMetadata.CaptureId);
		OutMetadata.ArtifactPath = BuildCaptureArtifactPath(OutMetadata.CaptureId);
		OutMetadata.MetadataPath = BuildCaptureMetadataPath(OutMetadata.CaptureId);
		OutMetadata.Width = CapturedImage.SizeX;
		OutMetadata.Height = CapturedImage.SizeY;
		OutMetadata.CreatedAt = FDateTime::UtcNow().ToIso8601();
		OutMetadata.ProjectDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
		OutMetadata.WorldContext = BuildDefaultWorldContext(OutMetadata);
		OutMetadata.CameraContext = BuildDefaultCameraContext(OutMetadata);

		if (!EnsureDirectory(OutMetadata.CaptureDirectory, OutError))
		{
			return false;
		}
		if (!SaveImageAsPng(OutMetadata.ArtifactPath, CapturedImage, OutError))
		{
			return false;
		}

		OutMetadata.FileSizeBytes = FMath::Max<int64>(0, IFileManager::Get().FileSize(*OutMetadata.ArtifactPath));
		return WriteCaptureMetadata(OutMetadata, OutError);
	}
}

bool CaptureEditorScreenshot(FBlueprintExtractorCaptureMetadata& OutMetadata, FString& OutError)
{
	return CaptureEditorScreenshot(TEXT("editor"), OutMetadata, OutError);
}

TSharedPtr<FJsonObject> CaptureMetadataToJson(const FBlueprintExtractorCaptureMetadata& Metadata)
{
	FBlueprintExtractorCaptureMetadata Normalized = Metadata;
	EnsureVerificationArtifactDefaults(Normalized);

	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("captureId"), Normalized.CaptureId);
	Result->SetStringField(TEXT("captureType"), Normalized.CaptureType);
	Result->SetStringField(TEXT("surface"), Normalized.Surface);
	Result->SetStringField(TEXT("scenarioId"), Normalized.ScenarioId);
	Result->SetStringField(TEXT("assetPath"), Normalized.AssetPath);
	Result->SetArrayField(TEXT("assetPaths"), StringArrayToJsonArray(Normalized.AssetPaths));
	if (!Normalized.WidgetClass.IsEmpty())
	{
		Result->SetStringField(TEXT("widgetClass"), Normalized.WidgetClass);
	}
	Result->SetStringField(TEXT("captureDirectory"), Normalized.CaptureDirectory);
	Result->SetStringField(TEXT("artifactPath"), Normalized.ArtifactPath);
	Result->SetStringField(TEXT("metadataPath"), Normalized.MetadataPath);
	Result->SetNumberField(TEXT("width"), Normalized.Width);
	Result->SetNumberField(TEXT("height"), Normalized.Height);
	Result->SetNumberField(TEXT("fileSizeBytes"), static_cast<double>(Normalized.FileSizeBytes));
	Result->SetStringField(TEXT("createdAt"), Normalized.CreatedAt);
	if (!Normalized.ProjectDir.IsEmpty())
	{
		Result->SetStringField(TEXT("projectDir"), Normalized.ProjectDir);
	}
	if (!Normalized.MotionCaptureId.IsEmpty())
	{
		Result->SetStringField(TEXT("motionCaptureId"), Normalized.MotionCaptureId);
	}
	if (!Normalized.CheckpointName.IsEmpty())
	{
		Result->SetStringField(TEXT("checkpointName"), Normalized.CheckpointName);
	}
	if (Normalized.CheckpointMs > 0.0 || !Normalized.CheckpointName.IsEmpty())
	{
		Result->SetNumberField(TEXT("checkpointMs"), Normalized.CheckpointMs);
	}
	if (!Normalized.PlaybackSource.IsEmpty())
	{
		Result->SetStringField(TEXT("playbackSource"), Normalized.PlaybackSource);
	}
	if (!Normalized.TriggerMode.IsEmpty())
	{
		Result->SetStringField(TEXT("triggerMode"), Normalized.TriggerMode);
	}
	if (Normalized.WorldContext.IsValid())
	{
		Result->SetObjectField(TEXT("worldContext"), Normalized.WorldContext);
	}
	if (Normalized.CameraContext.IsValid())
	{
		Result->SetObjectField(TEXT("cameraContext"), Normalized.CameraContext);
	}
	if (Normalized.Comparison.IsValid())
	{
		Result->SetObjectField(TEXT("comparison"), Normalized.Comparison);
	}
		return Result;
	}

	bool CaptureViewportImage(FViewport* Viewport, FImage& OutImage, FString& OutError)
	{
		if (!Viewport)
		{
			OutError = TEXT("Viewport is null.");
			return false;
		}

		const FIntPoint Size = Viewport->GetSizeXY();
		if (Size.X <= 0 || Size.Y <= 0)
		{
			OutError = TEXT("Viewport has no drawable size.");
			return false;
		}

		TArray<FColor> Pixels;
		const FIntRect CaptureRect(0, 0, Size.X, Size.Y);
		FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
		ReadFlags.SetLinearToGamma(true);
		if (!Viewport->ReadPixels(Pixels, ReadFlags, CaptureRect))
		{
			OutError = TEXT("Failed to read pixels from the viewport.");
			return false;
		}

		if (Pixels.Num() != Size.X * Size.Y)
		{
			OutError = TEXT("Viewport pixel count did not match the reported size.");
			return false;
		}

		OutImage = FImage(Size.X, Size.Y, ERawImageFormat::BGRA8, EGammaSpace::sRGB);
		TArrayView64<FColor> DestPixels = OutImage.AsBGRA8();
		for (int64 Index = 0; Index < Pixels.Num(); ++Index)
		{
			DestPixels[Index] = Pixels[Index];
		}

		return true;
	}

	bool CaptureViewportScreenshot(FViewport* Viewport,
	                               const FString& CaptureName,
	                               const FString& CaptureType,
	                               const FString& Surface,
	                               FBlueprintExtractorCaptureMetadata& OutMetadata,
	                               FString& OutError)
	{
		if (!FApp::CanEverRender() || !FSlateApplication::IsInitialized())
		{
			OutError = TEXT("Viewport screenshot capture requires rendering to be enabled. Avoid -NullRHI for visual verification runs.");
			return false;
		}

		FImage CapturedImage;
		if (!CaptureViewportImage(Viewport, CapturedImage, OutError))
		{
			return false;
		}

		OutMetadata.CaptureId = MakeCaptureId(CaptureName, CaptureType);
		OutMetadata.CaptureType = CaptureType;
		OutMetadata.Surface = Surface;
		OutMetadata.AssetPath = FString::Printf(TEXT("%s://%s"), *CaptureType, *FPaths::MakeValidFileName(CaptureName));
		OutMetadata.AssetPaths = { OutMetadata.AssetPath };
		OutMetadata.ScenarioId = FString::Printf(TEXT("%s:%s"), *CaptureType, *OutMetadata.AssetPath);
		OutMetadata.CaptureDirectory = BuildCaptureDirectory(OutMetadata.CaptureId);
		OutMetadata.ArtifactPath = BuildCaptureArtifactPath(OutMetadata.CaptureId);
		OutMetadata.MetadataPath = BuildCaptureMetadataPath(OutMetadata.CaptureId);
		OutMetadata.Width = CapturedImage.SizeX;
		OutMetadata.Height = CapturedImage.SizeY;
		OutMetadata.CreatedAt = FDateTime::UtcNow().ToIso8601();
		OutMetadata.ProjectDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
		OutMetadata.WorldContext = BuildDefaultWorldContext(OutMetadata);
		OutMetadata.CameraContext = BuildDefaultCameraContext(OutMetadata);

		if (!EnsureDirectory(OutMetadata.CaptureDirectory, OutError))
		{
			return false;
		}

		if (!SaveImageAsPng(OutMetadata.ArtifactPath, CapturedImage, OutError))
		{
			return false;
		}

		OutMetadata.FileSizeBytes = FMath::Max<int64>(0, IFileManager::Get().FileSize(*OutMetadata.ArtifactPath));
		return WriteCaptureMetadata(OutMetadata, OutError);
	}

TSharedPtr<FJsonObject> CaptureCompareResultToJson(const FBlueprintExtractorCaptureCompareResult& Result)
{
	const TSharedPtr<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetBoolField(TEXT("success"), true);
	Json->SetStringField(TEXT("capturePath"), Result.CapturePath);
	Json->SetStringField(TEXT("referencePath"), Result.ReferencePath);
	Json->SetNumberField(TEXT("tolerance"), Result.Tolerance);
	Json->SetBoolField(TEXT("pass"), Result.bPass);
	Json->SetNumberField(TEXT("rmse"), Result.Rmse);
	Json->SetNumberField(TEXT("maxPixelDelta"), Result.MaxPixelDelta);
	Json->SetNumberField(TEXT("mismatchPixelCount"), static_cast<double>(Result.MismatchPixelCount));
	Json->SetNumberField(TEXT("mismatchPercentage"), Result.MismatchPercentage);
	Json->SetStringField(TEXT("diffCaptureId"), Result.DiffCaptureId);
	Json->SetStringField(TEXT("diffArtifactPath"), Result.DiffArtifactPath);
	return Json;
}

TSharedPtr<FJsonObject> MotionCaptureResultToJson(const FBlueprintExtractorMotionCaptureResult& Result)
{
	const TSharedPtr<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetBoolField(TEXT("success"), true);
	Json->SetStringField(TEXT("motionCaptureId"), Result.MotionCaptureId);
	Json->SetStringField(TEXT("mode"), Result.Mode);
	Json->SetStringField(TEXT("triggerMode"), Result.TriggerMode);
	Json->SetStringField(TEXT("playbackSource"), Result.PlaybackSource);
	Json->SetStringField(TEXT("assetPath"), Result.AssetPath);
	Json->SetStringField(TEXT("animationName"), Result.AnimationName);
	Json->SetBoolField(TEXT("partialVerification"), Result.bPartialVerification);

	TArray<TSharedPtr<FJsonValue>> DiagnosticValues;
	for (const FString& Diagnostic : Result.Diagnostics)
	{
		DiagnosticValues.Add(MakeShared<FJsonValueString>(Diagnostic));
	}
	Json->SetArrayField(TEXT("diagnostics"), DiagnosticValues);

	TArray<TSharedPtr<FJsonValue>> ArtifactValues;
	for (const FBlueprintExtractorCaptureMetadata& Artifact : Result.VerificationArtifacts)
	{
		ArtifactValues.Add(MakeShared<FJsonValueObject>(CaptureMetadataToJson(Artifact)));
	}
	Json->SetArrayField(TEXT("verificationArtifacts"), ArtifactValues);
	Json->SetNumberField(TEXT("checkpointCount"), Result.VerificationArtifacts.Num());
	return Json;
}

bool CaptureWidgetMotionCheckpoints(UWidgetBlueprint* WidgetBlueprint,
	const TSharedPtr<FJsonObject>& Payload,
	FBlueprintExtractorMotionCaptureResult& OutResult,
	FString& OutError)
{
	if (!WidgetBlueprint)
	{
		OutError = TEXT("WidgetBlueprint is null.");
		return false;
	}

	if (!FApp::CanEverRender() || !FSlateApplication::IsInitialized())
	{
		OutError = TEXT("Widget motion capture requires an editor session with rendering enabled. Avoid -NullRHI for visual verification runs.");
		return false;
	}

	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!World)
	{
		OutError = TEXT("No editor world is available for widget motion capture.");
		return false;
	}

	FString AnimationName;
	if (!Payload.IsValid() || !Payload->TryGetStringField(TEXT("animation_name"), AnimationName) || AnimationName.IsEmpty())
	{
		OutError = TEXT("Payload requires animation_name.");
		return false;
	}

	UWidgetAnimation* RuntimeAnimation = FindRuntimeAnimationByName(WidgetBlueprint, AnimationName);
	UWidgetAnimation* AuthoredAnimation = FindAuthoredAnimationByName(WidgetBlueprint, AnimationName);
	if (!RuntimeAnimation || !AuthoredAnimation)
	{
		OutError = FString::Printf(TEXT("Widget animation '%s' was not found on the compiled WidgetBlueprint. Compile the widget before motion capture."), *AnimationName);
		return false;
	}

	int32 Width = 512;
	int32 Height = 512;
	if (Payload.IsValid())
	{
		double WidthNumber = 512.0;
		double HeightNumber = 512.0;
		Payload->TryGetNumberField(TEXT("width"), WidthNumber);
		Payload->TryGetNumberField(TEXT("height"), HeightNumber);
		Width = FMath::RoundToInt(WidthNumber);
		Height = FMath::RoundToInt(HeightNumber);
	}

	TArray<FMotionCheckpointRequest> Checkpoints;
	bool bPartialVerification = false;
	if (!ParseMotionCheckpointRequests(Payload, AuthoredAnimation, Checkpoints, bPartialVerification))
	{
		OutError = FString::Printf(TEXT("No motion checkpoints could be resolved for animation '%s'."), *AnimationName);
		return false;
	}

	const UWidgetBlueprintGeneratedClass* GeneratedClass = Cast<UWidgetBlueprintGeneratedClass>(WidgetBlueprint->GeneratedClass);
	if (!GeneratedClass || GeneratedClass->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated))
	{
		OutError = FString::Printf(TEXT("WidgetBlueprint '%s' does not have a valid generated class. Compile it before motion capture."), *WidgetBlueprint->GetPathName());
		return false;
	}

	const FString AssetName = FPackageName::GetLongPackageAssetName(WidgetBlueprint->GetOutermost()->GetName());
	OutResult = {};
	OutResult.MotionCaptureId = MakeCaptureId(AssetName, TEXT("widget_motion"));
	OutResult.Mode = TEXT("editor_preview");
	OutResult.TriggerMode = TEXT("asset_animation");
	OutResult.PlaybackSource = AnimationName;
	OutResult.AssetPath = WidgetBlueprint->GetPathName();
	OutResult.AnimationName = AnimationName;
	OutResult.bPartialVerification = bPartialVerification;
	if (bPartialVerification)
	{
		OutResult.Diagnostics.Add(TEXT("No explicit checkpoints were supplied, so closed/opening_peak/open were inferred from the authored duration."));
	}

	for (const FMotionCheckpointRequest& Checkpoint : Checkpoints)
	{
		UUserWidget* WidgetInstance = NewObject<UUserWidget>(World, WidgetBlueprint->GeneratedClass, NAME_None, RF_Transient);
		if (!WidgetInstance)
		{
			OutError = FString::Printf(TEXT("Failed to instantiate widget class '%s'."), *WidgetBlueprint->GeneratedClass->GetPathName());
			return false;
		}

		WidgetInstance->SetDesignerFlags(EWidgetDesignFlags::Designing | EWidgetDesignFlags::ExecutePreConstruct);
		if (!WidgetInstance->Initialize())
		{
			OutError = FString::Printf(TEXT("Failed to initialize widget '%s'."), *WidgetBlueprint->GetPathName());
			return false;
		}

		WidgetInstance->PlayAnimation(RuntimeAnimation, 0.0f, 1, EUMGSequencePlayMode::Forward, 1.0f, false);
		WidgetInstance->SetAnimationCurrentTime(RuntimeAnimation, Checkpoint.TimeMs / 1000.0f);
		WidgetInstance->FlushAnimations();

		FBlueprintExtractorCaptureMetadata Metadata;
		Metadata.CaptureType = TEXT("widget_motion_checkpoint");
		Metadata.Surface = TEXT("widget_motion_checkpoint");
		Metadata.AssetPath = WidgetBlueprint->GetPathName();
		Metadata.AssetPaths = { Metadata.AssetPath };
		Metadata.WidgetClass = WidgetBlueprint->GeneratedClass->GetPathName();
		Metadata.ScenarioId = FString::Printf(TEXT("widget_motion:%s:%s:%s"), *Metadata.AssetPath, *AnimationName, *Checkpoint.Name);
		Metadata.MotionCaptureId = OutResult.MotionCaptureId;
		Metadata.CheckpointName = Checkpoint.Name;
		Metadata.CheckpointMs = Checkpoint.TimeMs;
		Metadata.PlaybackSource = AnimationName;
		Metadata.TriggerMode = TEXT("asset_animation");

		FString CaptureError;
		if (!CaptureWidgetInstance(WidgetInstance, AssetName, FString::Printf(TEXT("widget_motion_%s"), *FPaths::MakeValidFileName(Checkpoint.Name)), Metadata, CaptureError, Width, Height))
		{
			OutError = CaptureError;
			return false;
		}

		OutResult.VerificationArtifacts.Add(Metadata);
	}

	return true;
}

bool CaptureWidgetPreview(UWidgetBlueprint* WidgetBlueprint,
	int32 RequestedWidth,
	int32 RequestedHeight,
	FBlueprintExtractorCaptureMetadata& OutMetadata,
	FString& OutError)
{
	if (!WidgetBlueprint)
	{
		OutError = TEXT("WidgetBlueprint is null.");
		return false;
	}

	if (!FApp::CanEverRender() || !FSlateApplication::IsInitialized())
	{
		OutError = TEXT("Widget capture requires an editor session with rendering enabled. Avoid -NullRHI for visual verification runs.");
		return false;
	}

	UClass* WidgetClass = WidgetBlueprint->GeneratedClass;
	if (!WidgetClass || WidgetClass->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated))
	{
		OutError = FString::Printf(TEXT("WidgetBlueprint '%s' does not have a valid generated class. Compile it before capture."), *WidgetBlueprint->GetPathName());
		return false;
	}

	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!World)
	{
		OutError = TEXT("No editor world is available for widget preview capture.");
		return false;
	}

	const int32 Width = FMath::Clamp(RequestedWidth, 64, 2048);
	const int32 Height = FMath::Clamp(RequestedHeight, 64, 2048);
	UUserWidget* WidgetInstance = NewObject<UUserWidget>(World, WidgetClass, NAME_None, RF_Transient);
	if (!WidgetInstance)
	{
		OutError = FString::Printf(TEXT("Failed to instantiate widget class '%s'."), *WidgetClass->GetPathName());
		return false;
	}

	WidgetInstance->SetDesignerFlags(EWidgetDesignFlags::Designing | EWidgetDesignFlags::ExecutePreConstruct);
	if (!WidgetInstance->Initialize())
	{
		OutError = FString::Printf(TEXT("Failed to initialize widget '%s'."), *WidgetBlueprint->GetPathName());
		return false;
	}

	const TSharedRef<SWidget> SlateWidget = WidgetInstance->TakeWidget();
	WidgetInstance->ForceLayoutPrepass();

	UTextureRenderTarget2D* RenderTarget = FWidgetRenderer::CreateTargetFor(FVector2D(Width, Height), TF_Bilinear, true);
	if (!RenderTarget)
	{
		OutError = TEXT("Failed to allocate a render target for widget capture.");
		return false;
	}

	{
		FWidgetRenderer Renderer(true, true);
		Renderer.DrawWidget(RenderTarget, SlateWidget, FVector2D(Width, Height), 0.0f);
	}

	FlushRenderingCommands();

	FImage CapturedImage;
	if (!FImageUtils::GetRenderTargetImage(RenderTarget, CapturedImage))
	{
		OutError = TEXT("Failed to read pixels from the widget capture render target.");
		return false;
	}

	const FString AssetName = FPackageName::GetLongPackageAssetName(WidgetBlueprint->GetOutermost()->GetName());
	OutMetadata.CaptureId = MakeCaptureId(AssetName, TEXT("widget_preview"));
	OutMetadata.CaptureType = TEXT("widget_preview");
	OutMetadata.AssetPath = WidgetBlueprint->GetPathName();
	OutMetadata.AssetPaths = { OutMetadata.AssetPath };
	OutMetadata.WidgetClass = WidgetClass->GetPathName();
	OutMetadata.Surface = TEXT("editor_offscreen");
	OutMetadata.ScenarioId = FString::Printf(TEXT("widget_preview:%s"), *OutMetadata.AssetPath);
	OutMetadata.CaptureDirectory = BuildCaptureDirectory(OutMetadata.CaptureId);
	OutMetadata.ArtifactPath = BuildCaptureArtifactPath(OutMetadata.CaptureId);
	OutMetadata.MetadataPath = BuildCaptureMetadataPath(OutMetadata.CaptureId);
	OutMetadata.Width = CapturedImage.SizeX;
	OutMetadata.Height = CapturedImage.SizeY;
	OutMetadata.CreatedAt = FDateTime::UtcNow().ToIso8601();
	OutMetadata.ProjectDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
	OutMetadata.WorldContext = BuildDefaultWorldContext(OutMetadata);
	OutMetadata.CameraContext = BuildDefaultCameraContext(OutMetadata);

	if (!EnsureDirectory(OutMetadata.CaptureDirectory, OutError))
	{
		return false;
	}

	if (!SaveImageAsPng(OutMetadata.ArtifactPath, CapturedImage, OutError))
	{
		return false;
	}

	OutMetadata.FileSizeBytes = FMath::Max<int64>(0, IFileManager::Get().FileSize(*OutMetadata.ArtifactPath));
	return WriteCaptureMetadata(OutMetadata, OutError);
}

bool CaptureEditorScreenshot(const FString& CaptureName,
	FBlueprintExtractorCaptureMetadata& OutMetadata,
	FString& OutError)
{
	if (!GEditor)
	{
		OutError = TEXT("Editor is not available.");
		return false;
	}

	if (GEditor->PlayWorld)
	{
		OutError = TEXT("Editor screenshot capture requires PIE to be inactive.");
		return false;
	}

	return CaptureViewportScreenshot(
		GEditor->GetActiveViewport(),
		CaptureName,
		TEXT("editor_screenshot"),
		TEXT("editor_tool_viewport"),
		OutMetadata,
		OutError);
}

bool CaptureRuntimeScreenshot(const FString& CaptureName,
	FBlueprintExtractorCaptureMetadata& OutMetadata,
	FString& OutError)
{
	if (!GEditor || !GEditor->PlayWorld)
	{
		OutError = TEXT("Runtime screenshot capture requires an active PIE session.");
		return false;
	}

	UGameViewportClient* GameViewportClient = GEditor->PlayWorld->GetGameViewport();
	FSceneViewport* Viewport = GameViewportClient ? GameViewportClient->GetGameViewport() : nullptr;
	return CaptureViewportScreenshot(
		Viewport,
		CaptureName,
		TEXT("runtime_screenshot"),
		TEXT("pie_runtime"),
		OutMetadata,
		OutError);
}

bool CompareCaptureToReference(const FString& CaptureIdOrPath,
	const FString& ReferenceIdOrPath,
	double Tolerance,
	FBlueprintExtractorCaptureCompareResult& OutResult,
	FString& OutError)
{
	FBlueprintExtractorCaptureMetadata ActualMetadata;
	FString CapturePath;
	if (!ResolveCaptureInput(CaptureIdOrPath, CapturePath, &ActualMetadata))
	{
		OutError = FString::Printf(TEXT("Unable to resolve capture '%s' to a PNG file."), *CaptureIdOrPath);
		return false;
	}

	FString ReferencePath;
	if (!ResolveCaptureInput(ReferenceIdOrPath, ReferencePath))
	{
		OutError = FString::Printf(TEXT("Unable to resolve reference '%s' to a PNG file."), *ReferenceIdOrPath);
		return false;
	}

	FImage ActualImage;
	if (!LoadComparableImage(CapturePath, ActualImage, OutError))
	{
		return false;
	}

	FImage ReferenceImage;
	if (!LoadComparableImage(ReferencePath, ReferenceImage, OutError))
	{
		return false;
	}

	if (ActualImage.SizeX != ReferenceImage.SizeX || ActualImage.SizeY != ReferenceImage.SizeY)
	{
		FImage ResizedReference;
		ReferenceImage.ResizeTo(ResizedReference, ActualImage.SizeX, ActualImage.SizeY, ERawImageFormat::BGRA8, EGammaSpace::sRGB);
		ReferenceImage = MoveTemp(ResizedReference);
	}

	const TArrayView64<const FColor> ActualPixels = ActualImage.AsBGRA8();
	const TArrayView64<const FColor> ReferencePixels = ReferenceImage.AsBGRA8();
	if (ActualPixels.Num() != ReferencePixels.Num())
	{
		OutError = TEXT("Loaded images do not have a matching pixel count after normalization.");
		return false;
	}

	FImage DiffImage(ActualImage.SizeX, ActualImage.SizeY, ERawImageFormat::BGRA8, EGammaSpace::sRGB);
	TArrayView64<FColor> DiffPixels = DiffImage.AsBGRA8();

	double SumSquaredError = 0.0;
	int32 MaxPixelDelta = 0;
	int64 MismatchPixelCount = 0;

	for (int64 PixelIndex = 0; PixelIndex < ActualPixels.Num(); ++PixelIndex)
	{
		const FColor& ActualPixel = ActualPixels[PixelIndex];
		const FColor& ReferencePixel = ReferencePixels[PixelIndex];
		const int32 DeltaR = FMath::Abs(static_cast<int32>(ActualPixel.R) - static_cast<int32>(ReferencePixel.R));
		const int32 DeltaG = FMath::Abs(static_cast<int32>(ActualPixel.G) - static_cast<int32>(ReferencePixel.G));
		const int32 DeltaB = FMath::Abs(static_cast<int32>(ActualPixel.B) - static_cast<int32>(ReferencePixel.B));
		const int32 DeltaA = FMath::Abs(static_cast<int32>(ActualPixel.A) - static_cast<int32>(ReferencePixel.A));
		const int32 PixelMaxDelta = FMath::Max(FMath::Max(DeltaR, DeltaG), FMath::Max(DeltaB, DeltaA));

		SumSquaredError += static_cast<double>(DeltaR * DeltaR + DeltaG * DeltaG + DeltaB * DeltaB + DeltaA * DeltaA);
		MaxPixelDelta = FMath::Max(MaxPixelDelta, PixelMaxDelta);
		if (PixelMaxDelta > 0)
		{
			++MismatchPixelCount;
		}

		DiffPixels[PixelIndex] = FColor(DeltaR, DeltaG, DeltaB, 255);
	}

	const double ChannelCount = FMath::Max<double>(1.0, static_cast<double>(ActualPixels.Num()) * 4.0);
	const double Rmse = FMath::Sqrt(SumSquaredError / ChannelCount) / 255.0;
	const double MismatchPercentage = ActualPixels.Num() > 0
		? (static_cast<double>(MismatchPixelCount) * 100.0 / static_cast<double>(ActualPixels.Num()))
		: 0.0;

	const FString DiffSource = !ActualMetadata.AssetPath.IsEmpty()
		? FPackageName::GetLongPackageAssetName(ActualMetadata.AssetPath)
		: FPaths::GetBaseFilename(CapturePath);
	const FString DiffCaptureId = MakeCaptureId(DiffSource, TEXT("comparison_diff"));
	const FString DiffDirectory = BuildCaptureDirectory(DiffCaptureId);
	const FString DiffArtifactPath = BuildCaptureArtifactPath(DiffCaptureId);
	const FString DiffMetadataPath = BuildCaptureMetadataPath(DiffCaptureId);
	if (!EnsureDirectory(DiffDirectory, OutError))
	{
		return false;
	}

	if (!SaveImageAsPng(DiffArtifactPath, DiffImage, OutError))
	{
		return false;
	}

	OutResult.CapturePath = CapturePath;
	OutResult.ReferencePath = ReferencePath;
	OutResult.Tolerance = FMath::Max(0.0, Tolerance);
	OutResult.bPass = Rmse <= OutResult.Tolerance;
	OutResult.Rmse = Rmse;
	OutResult.MaxPixelDelta = MaxPixelDelta;
	OutResult.MismatchPixelCount = MismatchPixelCount;
	OutResult.MismatchPercentage = MismatchPercentage;
	OutResult.DiffCaptureId = DiffCaptureId;
	OutResult.DiffArtifactPath = DiffArtifactPath;

	FBlueprintExtractorCaptureMetadata DiffMetadata;
	DiffMetadata.CaptureId = DiffCaptureId;
	DiffMetadata.CaptureType = TEXT("comparison_diff");
	DiffMetadata.AssetPath = !ActualMetadata.AssetPath.IsEmpty() ? ActualMetadata.AssetPath : CapturePath;
	DiffMetadata.AssetPaths = ActualMetadata.AssetPaths;
	DiffMetadata.WidgetClass = ActualMetadata.WidgetClass;
	DiffMetadata.Surface = !ActualMetadata.Surface.IsEmpty() ? ActualMetadata.Surface : TEXT("editor_offscreen");
	DiffMetadata.ScenarioId = ActualMetadata.ScenarioId;
	DiffMetadata.CaptureDirectory = DiffDirectory;
	DiffMetadata.ArtifactPath = DiffArtifactPath;
	DiffMetadata.MetadataPath = DiffMetadataPath;
	DiffMetadata.Width = DiffImage.SizeX;
	DiffMetadata.Height = DiffImage.SizeY;
	DiffMetadata.FileSizeBytes = FMath::Max<int64>(0, IFileManager::Get().FileSize(*DiffArtifactPath));
	DiffMetadata.CreatedAt = FDateTime::UtcNow().ToIso8601();
	DiffMetadata.ProjectDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
	DiffMetadata.WorldContext = ActualMetadata.WorldContext;
	DiffMetadata.CameraContext = ActualMetadata.CameraContext;
	DiffMetadata.Comparison = MakeShared<FJsonObject>();
	DiffMetadata.Comparison->SetStringField(TEXT("capturePath"), OutResult.CapturePath);
	DiffMetadata.Comparison->SetStringField(TEXT("referencePath"), OutResult.ReferencePath);
	DiffMetadata.Comparison->SetNumberField(TEXT("tolerance"), OutResult.Tolerance);
	DiffMetadata.Comparison->SetBoolField(TEXT("pass"), OutResult.bPass);
	DiffMetadata.Comparison->SetNumberField(TEXT("rmse"), OutResult.Rmse);
	DiffMetadata.Comparison->SetNumberField(TEXT("maxPixelDelta"), OutResult.MaxPixelDelta);
	DiffMetadata.Comparison->SetNumberField(TEXT("mismatchPixelCount"), static_cast<double>(OutResult.MismatchPixelCount));
	DiffMetadata.Comparison->SetNumberField(TEXT("mismatchPercentage"), OutResult.MismatchPercentage);
	DiffMetadata.Comparison->SetStringField(TEXT("diffCaptureId"), OutResult.DiffCaptureId);
	DiffMetadata.Comparison->SetStringField(TEXT("diffArtifactPath"), OutResult.DiffArtifactPath);
	if (!WriteCaptureMetadata(DiffMetadata, OutError))
	{
		return false;
	}
	return true;
}

bool ListCaptures(const FString& AssetPathFilter,
	TArray<FBlueprintExtractorCaptureMetadata>& OutCaptures,
	FString& OutError)
{
	OutCaptures.Reset();
	const FString RootDirectory = GetCaptureRootDirectory();
	if (!IFileManager::Get().DirectoryExists(*RootDirectory))
	{
		return true;
	}

	TArray<FString> CaptureDirectories;
	IFileManager::Get().FindFiles(CaptureDirectories, *(FPaths::Combine(RootDirectory, TEXT("*"))), false, true);
	for (const FString& CaptureDirectoryName : CaptureDirectories)
	{
		const FString MetadataPath = FPaths::Combine(RootDirectory, CaptureDirectoryName, CaptureMetadataName);
		FBlueprintExtractorCaptureMetadata Metadata;
		if (!ReadCaptureMetadata(MetadataPath, Metadata))
		{
			continue;
		}

		if (!AssetPathFilter.IsEmpty() && Metadata.AssetPath != AssetPathFilter)
		{
			continue;
		}

		OutCaptures.Add(MoveTemp(Metadata));
	}

	OutCaptures.Sort([](const FBlueprintExtractorCaptureMetadata& Left, const FBlueprintExtractorCaptureMetadata& Right)
	{
		return Left.CreatedAt > Right.CreatedAt;
	});

	return true;
}

bool CleanupCaptures(int32 MaxAgeDays,
	int32& OutDeletedCount,
	int64& OutFreedBytes,
	FString& OutError)
{
	OutDeletedCount = 0;
	OutFreedBytes = 0;

	const FString RootDirectory = GetCaptureRootDirectory();
	if (!IFileManager::Get().DirectoryExists(*RootDirectory))
	{
		return true;
	}

	const FDateTime Cutoff = FDateTime::UtcNow() - FTimespan::FromDays(FMath::Max(0, MaxAgeDays));
	TArray<FString> CaptureDirectories;
	IFileManager::Get().FindFiles(CaptureDirectories, *(FPaths::Combine(RootDirectory, TEXT("*"))), false, true);
	for (const FString& CaptureDirectoryName : CaptureDirectories)
	{
		const FString CaptureDirectory = FPaths::Combine(RootDirectory, CaptureDirectoryName);
		const FString MetadataPath = FPaths::Combine(CaptureDirectory, CaptureMetadataName);
		const FBlueprintExtractorCaptureMetadata Metadata = [&MetadataPath]()
		{
			FBlueprintExtractorCaptureMetadata Parsed;
			ReadCaptureMetadata(MetadataPath, Parsed);
			return Parsed;
		}();

		FDateTime CreatedAt = IFileManager::Get().GetTimeStamp(*CaptureDirectory);
		if (!Metadata.CreatedAt.IsEmpty())
		{
			FDateTime ParsedCreatedAt;
			if (FDateTime::ParseIso8601(*Metadata.CreatedAt, ParsedCreatedAt))
			{
				CreatedAt = ParsedCreatedAt;
			}
		}

		if (CreatedAt > Cutoff)
		{
			continue;
		}

		OutFreedBytes += CalculateDirectorySize(CaptureDirectory);
		if (!IFileManager::Get().DeleteDirectory(*CaptureDirectory, false, true))
		{
			OutError = FString::Printf(TEXT("Failed to delete capture directory: %s"), *CaptureDirectory);
			return false;
		}

		++OutDeletedCount;
	}

	return true;
}

} // namespace BlueprintExtractorCapture
