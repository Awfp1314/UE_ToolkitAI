#include "Authoring/WidgetAnimationAuthoring.h"

#include "Authoring/AssetMutationHelpers.h"
#include "Authoring/AuthoringHelpers.h"

#include "Animation/WidgetAnimation.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Widget.h"
#include "Dom/JsonValue.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Misc/FrameRate.h"
#include "MovieScene.h"
#include "MovieSceneBinding.h"
#include "MovieSceneMarkedFrame.h"
#include "MovieScenePossessable.h"
#include "Animation/MovieScene2DTransformTrack.h"
#include "Animation/MovieScene2DTransformSection.h"
#include "Sections/MovieSceneColorSection.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Tracks/MovieSceneColorTrack.h"
#include "Tracks/MovieSceneFloatTrack.h"
#include "Tracks/MovieScenePropertyTrack.h"
#include "UObject/UObjectGlobals.h"
#include "WidgetBlueprint.h"

namespace WidgetAnimationAuthoringInternal
{

static const FString TrackKindRenderOpacity = TEXT("render_opacity");
static const FString TrackKindRenderTransformTranslation = TEXT("render_transform_translation");
static const FString TrackKindRenderTransformScale = TEXT("render_transform_scale");
static const FString TrackKindRenderTransformAngle = TEXT("render_transform_angle");
static const FString TrackKindColorAndOpacity = TEXT("color_and_opacity");

static TArray<FString> BuildSupportedTrackKinds()
{
	return {
		TrackKindRenderOpacity,
		TrackKindRenderTransformTranslation,
		TrackKindRenderTransformScale,
		TrackKindRenderTransformAngle,
		TrackKindColorAndOpacity,
	};
}

static TArray<TSharedPtr<FJsonValue>> SupportedTracksJson()
{
	TArray<TSharedPtr<FJsonValue>> Result;
	for (const FString& TrackKind : BuildSupportedTrackKinds())
	{
		Result.Add(MakeShared<FJsonValueString>(TrackKind));
	}
	return Result;
}

static TSharedPtr<FJsonValueObject> MakeDiagnosticValue(const FString& Severity,
                                                        const FString& Code,
                                                        const FString& Message,
                                                        const FString& Path = FString())
{
	const TSharedPtr<FJsonObject> Diagnostic = MakeShared<FJsonObject>();
	Diagnostic->SetStringField(TEXT("severity"), Severity);
	Diagnostic->SetStringField(TEXT("code"), Code);
	Diagnostic->SetStringField(TEXT("message"), Message);
	if (!Path.IsEmpty())
	{
		Diagnostic->SetStringField(TEXT("path"), Path);
	}
	return MakeShared<FJsonValueObject>(Diagnostic);
}

static TSharedPtr<FJsonObject> MakeExtractError(const FString& AssetPath, const FString& Message)
{
	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), false);
	Result->SetStringField(TEXT("operation"), TEXT("extract_widget_animation"));
	Result->SetStringField(TEXT("assetPath"), AssetPath);
	Result->SetArrayField(TEXT("supportedTracks"), SupportedTracksJson());
	Result->SetArrayField(TEXT("diagnostics"), {
		MakeDiagnosticValue(TEXT("error"), TEXT("extract_failed"), Message, AssetPath),
	});
	return Result;
}

static FString BuildWidgetPathFromLiveWidget(const UWidget* Widget)
{
	if (!Widget)
	{
		return FString();
	}

	TArray<FString> Segments;
	const UWidget* CurrentWidget = Widget;
	while (CurrentWidget)
	{
		Segments.Insert(CurrentWidget->GetName(), 0);
		CurrentWidget = CurrentWidget->GetParent();
	}

	return FString::Join(Segments, TEXT("/"));
}

static void BuildWidgetPathMap(const UWidgetBlueprint* WidgetBlueprint, TMap<FName, FString>& OutPaths)
{
	OutPaths.Reset();
	if (!WidgetBlueprint || !WidgetBlueprint->WidgetTree)
	{
		return;
	}

	WidgetBlueprint->WidgetTree->ForEachWidget([&OutPaths](UWidget* Widget)
	{
		if (Widget)
		{
			OutPaths.Add(Widget->GetFName(), BuildWidgetPathFromLiveWidget(Widget));
		}
	});
}

static UWidgetAnimation* FindAnimationByName(UWidgetBlueprint* WidgetBlueprint, const FString& AnimationName)
{
	if (!WidgetBlueprint)
	{
		return nullptr;
	}

	for (UWidgetAnimation* Animation : WidgetBlueprint->Animations)
	{
		if (!Animation)
		{
			continue;
		}

		if (Animation->GetName() == AnimationName || Animation->GetFName().ToString() == AnimationName)
		{
			return Animation;
		}

#if WITH_EDITOR
		if (Animation->GetDisplayLabel() == AnimationName)
		{
			return Animation;
		}
#endif
	}

	return nullptr;
}

static FString BuildUniqueAnimationName(UWidgetBlueprint* WidgetBlueprint, const FString& RequestedName)
{
	const FString BaseName = RequestedName.IsEmpty() ? TEXT("WidgetAnimation") : RequestedName;
	FString Candidate = BaseName;
	int32 Suffix = 1;
	while (FindAnimationByName(WidgetBlueprint, Candidate))
	{
		Candidate = FString::Printf(TEXT("%s_%d"), *BaseName, Suffix++);
	}
	return Candidate;
}

static UWidget* ResolveWidgetByPath(const UWidgetBlueprint* WidgetBlueprint, const FString& WidgetPath)
{
	if (!WidgetBlueprint || !WidgetBlueprint->WidgetTree || WidgetPath.IsEmpty())
	{
		return nullptr;
	}

	TArray<FString> Segments;
	WidgetPath.ParseIntoArray(Segments, TEXT("/"), true);
	if (Segments.Num() == 0)
	{
		return nullptr;
	}

	UWidget* Current = WidgetBlueprint->WidgetTree->RootWidget;
	if (!Current || Current->GetName() != Segments[0])
	{
		return nullptr;
	}

	for (int32 SegmentIndex = 1; SegmentIndex < Segments.Num(); ++SegmentIndex)
	{
		const FString& Segment = Segments[SegmentIndex];
		UWidget* Next = nullptr;
		WidgetBlueprint->WidgetTree->ForEachWidget([&Current, &Segment, &Next](UWidget* Candidate)
		{
			if (!Next && Candidate && Candidate->GetParent() == Current && Candidate->GetName() == Segment)
			{
				Next = Candidate;
			}
		});
		if (!Next)
		{
			return nullptr;
		}
		Current = Next;
	}

	return Current;
}

static UWidget* ResolveWidgetByName(const UWidgetBlueprint* WidgetBlueprint, const FString& WidgetName, FString& OutWidgetPath)
{
	OutWidgetPath.Reset();
	if (!WidgetBlueprint || !WidgetBlueprint->WidgetTree || WidgetName.IsEmpty())
	{
		return nullptr;
	}

	UWidget* Result = nullptr;
	WidgetBlueprint->WidgetTree->ForEachWidget([&Result, &WidgetName, &OutWidgetPath](UWidget* Widget)
	{
		if (!Result && Widget && Widget->GetName() == WidgetName)
		{
			Result = Widget;
			OutWidgetPath = BuildWidgetPathFromLiveWidget(Widget);
		}
	});
	return Result;
}

static UWidget* ResolveWidgetFromSelector(const UWidgetBlueprint* WidgetBlueprint,
                                          const TSharedPtr<FJsonObject>& TrackObject,
                                          FString& OutWidgetPath,
                                          TArray<FString>& OutErrors)
{
	OutWidgetPath.Reset();
	if (!TrackObject.IsValid())
	{
		OutErrors.Add(TEXT("Track payload must be an object."));
		return nullptr;
	}

	FString WidgetPath;
	if (TrackObject->TryGetStringField(TEXT("widget_path"), WidgetPath) && !WidgetPath.IsEmpty())
	{
		if (UWidget* ByPath = ResolveWidgetByPath(WidgetBlueprint, WidgetPath))
		{
			OutWidgetPath = WidgetPath;
			return ByPath;
		}
		OutErrors.Add(FString::Printf(TEXT("Widget path '%s' did not resolve to a widget."), *WidgetPath));
		return nullptr;
	}

	FString WidgetName;
	if (TrackObject->TryGetStringField(TEXT("widget_name"), WidgetName) && !WidgetName.IsEmpty())
	{
		if (UWidget* ByName = ResolveWidgetByName(WidgetBlueprint, WidgetName, OutWidgetPath))
		{
			return ByName;
		}
		OutErrors.Add(FString::Printf(TEXT("Widget name '%s' did not resolve to a widget."), *WidgetName));
		return nullptr;
	}

	OutErrors.Add(TEXT("Track payload requires widget_path or widget_name."));
	return nullptr;
}

static double FrameToMilliseconds(const UMovieScene* MovieScene, const FFrameNumber FrameNumber)
{
	return MovieScene ? MovieScene->GetTickResolution().AsSeconds(FrameNumber) * 1000.0 : 0.0;
}

static FFrameNumber MillisecondsToFrame(const UMovieScene* MovieScene, const double Milliseconds)
{
	return MovieScene ? MovieScene->GetTickResolution().AsFrameNumber(Milliseconds / 1000.0) : FFrameNumber(0);
}

static int32 ExtractFps(const UMovieScene* MovieScene)
{
	if (!MovieScene)
	{
		return 20;
	}

	const FFrameRate DisplayRate = MovieScene->GetDisplayRate();
	return DisplayRate.Numerator > 0 && DisplayRate.Denominator > 0
		? FMath::Max(1, FMath::RoundToInt(DisplayRate.AsDecimal()))
		: 20;
}

static bool ParseInterpolation(const FString& Interpolation, ERichCurveInterpMode& OutInterpMode)
{
	if (Interpolation.Equals(TEXT("constant"), ESearchCase::IgnoreCase))
	{
		OutInterpMode = RCIM_Constant;
		return true;
	}
	if (Interpolation.Equals(TEXT("linear"), ESearchCase::IgnoreCase))
	{
		OutInterpMode = RCIM_Linear;
		return true;
	}
	if (Interpolation.IsEmpty() || Interpolation.Equals(TEXT("cubic"), ESearchCase::IgnoreCase))
	{
		OutInterpMode = RCIM_Cubic;
		return true;
	}
	return false;
}

static void AddFloatKey(FMovieSceneFloatChannel& Channel,
                        const FFrameNumber Frame,
                        const float Value,
                        const FString& Interpolation)
{
	ERichCurveInterpMode InterpMode = RCIM_Cubic;
	ParseInterpolation(Interpolation, InterpMode);
	if (InterpMode == RCIM_Constant)
	{
		Channel.AddConstantKey(Frame, Value);
	}
	else if (InterpMode == RCIM_Linear)
	{
		Channel.AddLinearKey(Frame, Value);
	}
	else
	{
		Channel.AddCubicKey(Frame, Value);
	}
}

static FString PropertyPathToTrackKind(const UMovieSceneTrack* Track)
{
	const UMovieScenePropertyTrack* PropertyTrack = Cast<UMovieScenePropertyTrack>(Track);
	if (!PropertyTrack)
	{
		return FString();
	}

	const FString PropertyPath = PropertyTrack->GetPropertyPath().ToString();
	if (PropertyPath == TEXT("RenderOpacity"))
	{
		return TrackKindRenderOpacity;
	}
	if (PropertyPath == TEXT("ColorAndOpacity"))
	{
		return TrackKindColorAndOpacity;
	}
	if (PropertyPath == TEXT("RenderTransform") && Track->IsA<UMovieScene2DTransformTrack>())
	{
		return TEXT("render_transform");
	}
	return FString();
}

static void AppendScalarKeys(const UMovieScene* MovieScene,
                             const FMovieSceneFloatChannel& Channel,
                             TArray<TSharedPtr<FJsonValue>>& OutKeys)
{
	const TArrayView<const FFrameNumber> Times = Channel.GetTimes();
	const TArrayView<const FMovieSceneFloatValue> Values = Channel.GetValues();
	const int32 KeyCount = FMath::Min(Times.Num(), Values.Num());
	for (int32 Index = 0; Index < KeyCount; ++Index)
	{
		const TSharedPtr<FJsonObject> Key = MakeShared<FJsonObject>();
		Key->SetNumberField(TEXT("time_ms"), FrameToMilliseconds(MovieScene, Times[Index]));
		Key->SetNumberField(TEXT("value"), Values[Index].Value);
		Key->SetStringField(TEXT("interpolation"),
			Values[Index].InterpMode == RCIM_Constant ? TEXT("constant")
				: Values[Index].InterpMode == RCIM_Linear ? TEXT("linear")
					: TEXT("cubic"));
		OutKeys.Add(MakeShared<FJsonValueObject>(Key));
	}
}

static TSharedPtr<FJsonObject> SerializeAnimation(UWidgetBlueprint* WidgetBlueprint, UWidgetAnimation* Animation)
{
	if (!WidgetBlueprint || !Animation || !Animation->MovieScene)
	{
		return nullptr;
	}

	TMap<FName, FString> WidgetPaths;
	BuildWidgetPathMap(WidgetBlueprint, WidgetPaths);

	const TSharedPtr<FJsonObject> AnimationObject = MakeShared<FJsonObject>();
	AnimationObject->SetStringField(TEXT("name"), Animation->GetName());
#if WITH_EDITOR
	if (!Animation->GetDisplayLabel().IsEmpty())
	{
		AnimationObject->SetStringField(TEXT("displayLabel"), Animation->GetDisplayLabel());
	}
#endif
	AnimationObject->SetNumberField(TEXT("durationMs"), Animation->GetEndTime() * 1000.0);

	const TSharedPtr<FJsonObject> Playback = MakeShared<FJsonObject>();
	Playback->SetNumberField(TEXT("fps"), ExtractFps(Animation->MovieScene));
	Playback->SetNumberField(TEXT("startTimeMs"), Animation->GetStartTime() * 1000.0);
	Playback->SetNumberField(TEXT("endTimeMs"), Animation->GetEndTime() * 1000.0);
	AnimationObject->SetObjectField(TEXT("playback"), Playback);
	AnimationObject->SetArrayField(TEXT("supportedTracks"), SupportedTracksJson());

	TArray<TSharedPtr<FJsonValue>> Bindings;
	for (const FWidgetAnimationBinding& Binding : Animation->AnimationBindings)
	{
		const TSharedPtr<FJsonObject> BindingObject = MakeShared<FJsonObject>();
		BindingObject->SetStringField(TEXT("widgetName"), Binding.WidgetName.ToString());
		BindingObject->SetStringField(TEXT("animationGuid"), Binding.AnimationGuid.ToString(EGuidFormats::DigitsWithHyphensLower));
		BindingObject->SetBoolField(TEXT("isRootWidget"), Binding.bIsRootWidget);
		if (const FString* WidgetPath = WidgetPaths.Find(Binding.WidgetName))
		{
			BindingObject->SetStringField(TEXT("widgetPath"), *WidgetPath);
		}
		Bindings.Add(MakeShared<FJsonValueObject>(BindingObject));
	}
	AnimationObject->SetArrayField(TEXT("bindings"), Bindings);

	TArray<TSharedPtr<FJsonValue>> Tracks;
	for (const FWidgetAnimationBinding& Binding : Animation->AnimationBindings)
	{
		const FString WidgetPath = WidgetPaths.FindRef(Binding.WidgetName);
		const FMovieSceneBinding* MovieSceneBinding = Animation->MovieScene->FindBinding(Binding.AnimationGuid);
		if (!MovieSceneBinding)
		{
			continue;
		}

		for (UMovieSceneTrack* Track : MovieSceneBinding->GetTracks())
		{
			if (!Track)
			{
				continue;
			}

			if (Track->IsA<UMovieSceneFloatTrack>() && PropertyPathToTrackKind(Track) == TrackKindRenderOpacity)
			{
				const TArray<UMovieSceneSection*> Sections = Track->GetAllSections();
				if (Sections.Num() > 0)
				{
					const TSharedPtr<FJsonObject> TrackObject = MakeShared<FJsonObject>();
					TrackObject->SetStringField(TEXT("widget_name"), Binding.WidgetName.ToString());
					if (!WidgetPath.IsEmpty())
					{
						TrackObject->SetStringField(TEXT("widget_path"), WidgetPath);
					}
					TrackObject->SetStringField(TEXT("property"), TrackKindRenderOpacity);
					TArray<TSharedPtr<FJsonValue>> Keys;
					AppendScalarKeys(Animation->MovieScene, CastChecked<UMovieSceneFloatSection>(Sections[0])->GetChannel(), Keys);
					TrackObject->SetArrayField(TEXT("keys"), Keys);
					Tracks.Add(MakeShared<FJsonValueObject>(TrackObject));
				}
				continue;
			}

			if (Track->IsA<UMovieScene2DTransformTrack>())
			{
				const TArray<UMovieSceneSection*> Sections = Track->GetAllSections();
				if (Sections.Num() == 0)
				{
					continue;
				}
				const UMovieScene2DTransformSection* Section = CastChecked<UMovieScene2DTransformSection>(Sections[0]);
				const auto AddVectorTrack = [&](const FString& Property, const FMovieSceneFloatChannel& XChannel, const FMovieSceneFloatChannel& YChannel)
				{
					const TArrayView<const FFrameNumber> XTimes = XChannel.GetTimes();
					const TArrayView<const FMovieSceneFloatValue> XValues = XChannel.GetValues();
					const TArrayView<const FFrameNumber> YTimes = YChannel.GetTimes();
					const TArrayView<const FMovieSceneFloatValue> YValues = YChannel.GetValues();
					const int32 KeyCount = FMath::Min(XTimes.Num(), FMath::Min(XValues.Num(), FMath::Min(YTimes.Num(), YValues.Num())));
					const TSharedPtr<FJsonObject> TrackObject = MakeShared<FJsonObject>();
					TrackObject->SetStringField(TEXT("widget_name"), Binding.WidgetName.ToString());
					if (!WidgetPath.IsEmpty())
					{
						TrackObject->SetStringField(TEXT("widget_path"), WidgetPath);
					}
					TrackObject->SetStringField(TEXT("property"), Property);
					TArray<TSharedPtr<FJsonValue>> Keys;
					for (int32 Index = 0; Index < KeyCount; ++Index)
					{
						const TSharedPtr<FJsonObject> ValueObject = MakeShared<FJsonObject>();
						ValueObject->SetNumberField(TEXT("x"), XValues[Index].Value);
						ValueObject->SetNumberField(TEXT("y"), YValues[Index].Value);
						const TSharedPtr<FJsonObject> Key = MakeShared<FJsonObject>();
						Key->SetNumberField(TEXT("time_ms"), FrameToMilliseconds(Animation->MovieScene, XTimes[Index]));
						Key->SetObjectField(TEXT("value"), ValueObject);
						Keys.Add(MakeShared<FJsonValueObject>(Key));
					}
					TrackObject->SetArrayField(TEXT("keys"), Keys);
					Tracks.Add(MakeShared<FJsonValueObject>(TrackObject));
				};

				AddVectorTrack(TrackKindRenderTransformTranslation, Section->Translation[0], Section->Translation[1]);
				AddVectorTrack(TrackKindRenderTransformScale, Section->Scale[0], Section->Scale[1]);

				const TSharedPtr<FJsonObject> AngleTrack = MakeShared<FJsonObject>();
				AngleTrack->SetStringField(TEXT("widget_name"), Binding.WidgetName.ToString());
				if (!WidgetPath.IsEmpty())
				{
					AngleTrack->SetStringField(TEXT("widget_path"), WidgetPath);
				}
				AngleTrack->SetStringField(TEXT("property"), TrackKindRenderTransformAngle);
				TArray<TSharedPtr<FJsonValue>> AngleKeys;
				AppendScalarKeys(Animation->MovieScene, Section->Rotation, AngleKeys);
				AngleTrack->SetArrayField(TEXT("keys"), AngleKeys);
				Tracks.Add(MakeShared<FJsonValueObject>(AngleTrack));
				continue;
			}

			if (Track->IsA<UMovieSceneColorTrack>() && PropertyPathToTrackKind(Track) == TrackKindColorAndOpacity)
			{
				const TArray<UMovieSceneSection*> Sections = Track->GetAllSections();
				if (Sections.Num() > 0)
				{
					const UMovieSceneColorSection* Section = CastChecked<UMovieSceneColorSection>(Sections[0]);
					const int32 KeyCount = FMath::Min(
						FMath::Min(Section->GetRedChannel().GetTimes().Num(), Section->GetRedChannel().GetValues().Num()),
						FMath::Min(
							FMath::Min(Section->GetGreenChannel().GetTimes().Num(), Section->GetGreenChannel().GetValues().Num()),
							FMath::Min(
								FMath::Min(Section->GetBlueChannel().GetTimes().Num(), Section->GetBlueChannel().GetValues().Num()),
								FMath::Min(Section->GetAlphaChannel().GetTimes().Num(), Section->GetAlphaChannel().GetValues().Num()))));
					const TSharedPtr<FJsonObject> TrackObject = MakeShared<FJsonObject>();
					TrackObject->SetStringField(TEXT("widget_name"), Binding.WidgetName.ToString());
					if (!WidgetPath.IsEmpty())
					{
						TrackObject->SetStringField(TEXT("widget_path"), WidgetPath);
					}
					TrackObject->SetStringField(TEXT("property"), TrackKindColorAndOpacity);
					TArray<TSharedPtr<FJsonValue>> Keys;
					for (int32 Index = 0; Index < KeyCount; ++Index)
					{
						const TSharedPtr<FJsonObject> ValueObject = MakeShared<FJsonObject>();
						ValueObject->SetNumberField(TEXT("r"), Section->GetRedChannel().GetValues()[Index].Value);
						ValueObject->SetNumberField(TEXT("g"), Section->GetGreenChannel().GetValues()[Index].Value);
						ValueObject->SetNumberField(TEXT("b"), Section->GetBlueChannel().GetValues()[Index].Value);
						ValueObject->SetNumberField(TEXT("a"), Section->GetAlphaChannel().GetValues()[Index].Value);
						const TSharedPtr<FJsonObject> Key = MakeShared<FJsonObject>();
						Key->SetNumberField(TEXT("time_ms"), FrameToMilliseconds(Animation->MovieScene, Section->GetRedChannel().GetTimes()[Index]));
						Key->SetObjectField(TEXT("value"), ValueObject);
						Keys.Add(MakeShared<FJsonValueObject>(Key));
					}
					TrackObject->SetArrayField(TEXT("keys"), Keys);
					Tracks.Add(MakeShared<FJsonValueObject>(TrackObject));
				}
			}
		}
	}
	AnimationObject->SetArrayField(TEXT("tracks"), Tracks);

	TArray<TSharedPtr<FJsonValue>> Checkpoints;
	for (const FMovieSceneMarkedFrame& MarkedFrame : Animation->MovieScene->GetMarkedFrames())
	{
		const TSharedPtr<FJsonObject> Checkpoint = MakeShared<FJsonObject>();
		Checkpoint->SetStringField(TEXT("name"), MarkedFrame.Label);
		Checkpoint->SetNumberField(TEXT("timeMs"), FrameToMilliseconds(Animation->MovieScene, MarkedFrame.FrameNumber));
		Checkpoints.Add(MakeShared<FJsonValueObject>(Checkpoint));
	}
	AnimationObject->SetArrayField(TEXT("checkpoints"), Checkpoints);
	return AnimationObject;
}

static bool ParseScalarKey(const TSharedPtr<FJsonObject>& KeyObject,
                           double& OutTimeMs,
                           float& OutValue,
                           FString& OutInterpolation,
                           TArray<FString>& OutErrors)
{
	double Value = 0.0;
	if (!KeyObject.IsValid()
		|| !KeyObject->TryGetNumberField(TEXT("time_ms"), OutTimeMs)
		|| !KeyObject->TryGetNumberField(TEXT("value"), Value))
	{
		OutErrors.Add(TEXT("Scalar key requires numeric time_ms and value fields."));
		return false;
	}

	OutValue = static_cast<float>(Value);
	KeyObject->TryGetStringField(TEXT("interpolation"), OutInterpolation);
	return true;
}

static bool ParseVectorKey(const TSharedPtr<FJsonObject>& KeyObject,
                           double& OutTimeMs,
                           FVector2D& OutValue,
                           FString& OutInterpolation,
                           TArray<FString>& OutErrors)
{
	const TSharedPtr<FJsonObject>* ValueObject = nullptr;
	double X = 0.0;
	double Y = 0.0;
	if (!KeyObject.IsValid()
		|| !KeyObject->TryGetNumberField(TEXT("time_ms"), OutTimeMs)
		|| !KeyObject->TryGetObjectField(TEXT("value"), ValueObject)
		|| !ValueObject
		|| !(*ValueObject)->TryGetNumberField(TEXT("x"), X)
		|| !(*ValueObject)->TryGetNumberField(TEXT("y"), Y))
	{
		OutErrors.Add(TEXT("Vector key requires time_ms and value.{x,y}."));
		return false;
	}

	OutValue = FVector2D(static_cast<float>(X), static_cast<float>(Y));
	KeyObject->TryGetStringField(TEXT("interpolation"), OutInterpolation);
	return true;
}

static bool ParseColorKey(const TSharedPtr<FJsonObject>& KeyObject,
                          double& OutTimeMs,
                          FLinearColor& OutValue,
                          FString& OutInterpolation,
                          TArray<FString>& OutErrors)
{
	const TSharedPtr<FJsonObject>* ValueObject = nullptr;
	double R = 0.0;
	double G = 0.0;
	double B = 0.0;
	double A = 1.0;
	if (!KeyObject.IsValid()
		|| !KeyObject->TryGetNumberField(TEXT("time_ms"), OutTimeMs)
		|| !KeyObject->TryGetObjectField(TEXT("value"), ValueObject)
		|| !ValueObject
		|| !(*ValueObject)->TryGetNumberField(TEXT("r"), R)
		|| !(*ValueObject)->TryGetNumberField(TEXT("g"), G)
		|| !(*ValueObject)->TryGetNumberField(TEXT("b"), B)
		|| !(*ValueObject)->TryGetNumberField(TEXT("a"), A))
	{
		OutErrors.Add(TEXT("Color key requires time_ms and value.{r,g,b,a}."));
		return false;
	}

	OutValue = FLinearColor(static_cast<float>(R), static_cast<float>(G), static_cast<float>(B), static_cast<float>(A));
	KeyObject->TryGetStringField(TEXT("interpolation"), OutInterpolation);
	return true;
}

static void ApplyCheckpointMarkedFrames(UMovieScene* MovieScene, const TSharedPtr<FJsonObject>& Payload)
{
	if (!MovieScene)
	{
		return;
	}

	MovieScene->DeleteMarkedFrames();
	const TArray<TSharedPtr<FJsonValue>>* Checkpoints = nullptr;
	if (!Payload.IsValid() || !Payload->TryGetArrayField(TEXT("checkpoints"), Checkpoints) || !Checkpoints)
	{
		return;
	}

	for (const TSharedPtr<FJsonValue>& CheckpointValue : *Checkpoints)
	{
		const TSharedPtr<FJsonObject> Checkpoint = CheckpointValue.IsValid() ? CheckpointValue->AsObject() : nullptr;
		double TimeMs = 0.0;
		FString Name;
		if (!Checkpoint.IsValid()
			|| !Checkpoint->TryGetStringField(TEXT("name"), Name)
			|| !Checkpoint->TryGetNumberField(TEXT("timeMs"), TimeMs))
		{
			continue;
		}

		FMovieSceneMarkedFrame MarkedFrame(MillisecondsToFrame(MovieScene, TimeMs));
		MarkedFrame.Label = Name;
		MovieScene->AddMarkedFrame(MarkedFrame);
	}
	MovieScene->SortMarkedFrames();
}

static void ResetAnimationTimeline(UWidgetAnimation* Animation)
{
	if (!Animation || !Animation->MovieScene)
	{
		return;
	}

	const TArray<FWidgetAnimationBinding> ExistingBindings = Animation->AnimationBindings;
	for (const FWidgetAnimationBinding& Binding : ExistingBindings)
	{
		if (FMovieSceneBinding* MovieSceneBinding = Animation->MovieScene->FindBinding(Binding.AnimationGuid))
		{
			const TArray<UMovieSceneTrack*> Tracks = MovieSceneBinding->GetTracks();
			for (UMovieSceneTrack* Track : Tracks)
			{
				if (Track)
				{
					Animation->MovieScene->RemoveTrack(*Track);
				}
			}
		}
		Animation->MovieScene->RemovePossessable(Binding.AnimationGuid);
	}

	Animation->AnimationBindings.Reset();
	Animation->MovieScene->DeleteMarkedFrames();
}

static FGuid EnsureWidgetBinding(UWidgetBlueprint* WidgetBlueprint, UWidgetAnimation* Animation, UWidget* Widget)
{
	const FName WidgetName = Widget->GetFName();
	FGuid WidgetGuid;
#if WITH_EDITORONLY_DATA
	if (FGuid* ExistingGuid = WidgetBlueprint->WidgetVariableNameToGuidMap.Find(WidgetName))
	{
		WidgetGuid = *ExistingGuid;
	}
	else
	{
		WidgetGuid = FGuid::NewDeterministicGuid(Widget->GetPathName());
		WidgetBlueprint->WidgetVariableNameToGuidMap.Add(WidgetName, WidgetGuid);
	}
#else
	WidgetGuid = FGuid::NewGuid();
#endif

	if (!Animation->MovieScene->FindBinding(WidgetGuid))
	{
		const FGuid AddedGuid = Animation->MovieScene->AddPossessable(Widget->GetName(), Widget->GetClass());
		if (AddedGuid != WidgetGuid)
		{
			if (FMovieScenePossessable* ExistingPossessable = Animation->MovieScene->FindPossessable(AddedGuid))
			{
				FMovieScenePossessable Replacement = *ExistingPossessable;
				Replacement.SetGuid(WidgetGuid);
				Replacement.SetName(Widget->GetName());
				Animation->MovieScene->ReplacePossessable(AddedGuid, Replacement);
			}
			Animation->MovieScene->ReplaceBinding(AddedGuid, WidgetGuid, Widget->GetName());
		}
	}

	if (!Animation->AnimationBindings.ContainsByPredicate([WidgetGuid](const FWidgetAnimationBinding& Binding)
	{
		return Binding.AnimationGuid == WidgetGuid;
	}))
	{
		FWidgetAnimationBinding Binding;
		Binding.AnimationGuid = WidgetGuid;
		Binding.WidgetName = WidgetName;
		Binding.bIsRootWidget = WidgetBlueprint && WidgetBlueprint->WidgetTree && WidgetBlueprint->WidgetTree->RootWidget == Widget;
		Animation->AnimationBindings.Add(Binding);
	}

	return WidgetGuid;
}

static bool ApplyPlaybackMetadata(UWidgetAnimation* Animation,
                                  const TSharedPtr<FJsonObject>& Payload,
                                  TArray<FString>& OutErrors)
{
	if (!Animation || !Animation->MovieScene)
	{
		OutErrors.Add(TEXT("Animation does not have a valid MovieScene."));
		return false;
	}

	double DurationMs = 5000.0;
	double Fps = 20.0;
	if (Payload.IsValid())
	{
		Payload->TryGetNumberField(TEXT("duration_ms"), DurationMs);
		Payload->TryGetNumberField(TEXT("fps"), Fps);
		if (const TSharedPtr<FJsonObject>* Timeline = nullptr; Payload->TryGetObjectField(TEXT("timeline"), Timeline) && Timeline && (*Timeline).IsValid())
		{
			(*Timeline)->TryGetNumberField(TEXT("duration_ms"), DurationMs);
			(*Timeline)->TryGetNumberField(TEXT("fps"), Fps);
		}
	}

	Animation->MovieScene->SetDisplayRate(FFrameRate(FMath::Max(1, FMath::RoundToInt(Fps)), 1));
	Animation->MovieScene->SetPlaybackRange(TRange<FFrameNumber>(0, MillisecondsToFrame(Animation->MovieScene, DurationMs) + 1));
	Animation->MovieScene->GetEditorData().WorkStart = 0.0;
	Animation->MovieScene->GetEditorData().WorkEnd = DurationMs / 1000.0;
	ApplyCheckpointMarkedFrames(Animation->MovieScene, Payload);
#if WITH_EDITOR
	FString DisplayLabel;
	if (Payload.IsValid() && Payload->TryGetStringField(TEXT("display_label"), DisplayLabel) && !DisplayLabel.IsEmpty())
	{
		Animation->SetDisplayLabel(DisplayLabel);
	}
#endif
	return true;
}

static bool ApplyTimelinePayload(UWidgetBlueprint* WidgetBlueprint,
                                 UWidgetAnimation* Animation,
                                 const TSharedPtr<FJsonObject>& Payload,
                                 TArray<FString>& OutErrors)
{
	if (!WidgetBlueprint || !Animation || !Animation->MovieScene)
	{
		OutErrors.Add(TEXT("WidgetBlueprint or animation is invalid."));
		return false;
	}

	const TSharedPtr<FJsonObject>* TimelineObject = nullptr;
	const TSharedPtr<FJsonObject> Timeline = Payload.IsValid() && Payload->TryGetObjectField(TEXT("timeline"), TimelineObject) && TimelineObject
		? *TimelineObject
		: Payload;
	const TArray<TSharedPtr<FJsonValue>>* Tracks = nullptr;
	if (!Timeline.IsValid() || !Timeline->TryGetArrayField(TEXT("tracks"), Tracks) || !Tracks)
	{
		OutErrors.Add(TEXT("Timeline payload requires a tracks array."));
		return false;
	}

	ResetAnimationTimeline(Animation);
	ApplyPlaybackMetadata(Animation, Payload, OutErrors);

	for (const TSharedPtr<FJsonValue>& TrackValue : *Tracks)
	{
		const TSharedPtr<FJsonObject> TrackObject = TrackValue.IsValid() ? TrackValue->AsObject() : nullptr;
		FString WidgetPath;
		UWidget* Widget = ResolveWidgetFromSelector(WidgetBlueprint, TrackObject, WidgetPath, OutErrors);
		if (!Widget || !TrackObject.IsValid())
		{
			continue;
		}

		FString TrackKind;
		const TArray<TSharedPtr<FJsonValue>>* Keys = nullptr;
		if (!TrackObject->TryGetStringField(TEXT("property"), TrackKind) || !TrackObject->TryGetArrayField(TEXT("keys"), Keys) || !Keys)
		{
			OutErrors.Add(TEXT("Each track requires property and keys."));
			continue;
		}

		const FGuid BindingGuid = EnsureWidgetBinding(WidgetBlueprint, Animation, Widget);
		if (TrackKind == TrackKindRenderOpacity)
		{
			UMovieSceneFloatTrack* Track = Animation->MovieScene->AddTrack<UMovieSceneFloatTrack>(BindingGuid);
			Track->SetPropertyNameAndPath(TEXT("RenderOpacity"), TEXT("RenderOpacity"));
			UMovieSceneFloatSection* Section = CastChecked<UMovieSceneFloatSection>(Track->CreateNewSection());
			Track->AddSection(*Section);
			for (const TSharedPtr<FJsonValue>& KeyValue : *Keys)
			{
				double TimeMs = 0.0;
				float Value = 0.0f;
				FString Interpolation;
				if (ParseScalarKey(KeyValue.IsValid() ? KeyValue->AsObject() : nullptr, TimeMs, Value, Interpolation, OutErrors))
				{
					AddFloatKey(Section->GetChannel(), MillisecondsToFrame(Animation->MovieScene, TimeMs), Value, Interpolation);
				}
			}
			continue;
		}

		if (TrackKind == TrackKindRenderTransformTranslation || TrackKind == TrackKindRenderTransformScale || TrackKind == TrackKindRenderTransformAngle)
		{
			UMovieScene2DTransformTrack* Track = nullptr;
			if (FMovieSceneBinding* ExistingBinding = Animation->MovieScene->FindBinding(BindingGuid))
			{
				for (UMovieSceneTrack* ExistingTrack : ExistingBinding->GetTracks())
				{
					Track = Cast<UMovieScene2DTransformTrack>(ExistingTrack);
					if (Track)
					{
						break;
					}
				}
			}
			if (!Track)
			{
				Track = Animation->MovieScene->AddTrack<UMovieScene2DTransformTrack>(BindingGuid);
				Track->SetPropertyNameAndPath(TEXT("RenderTransform"), TEXT("RenderTransform"));
			}

			UMovieScene2DTransformSection* Section = nullptr;
			const TArray<UMovieSceneSection*> ExistingSections = Track->GetAllSections();
			if (ExistingSections.Num() > 0)
			{
				Section = Cast<UMovieScene2DTransformSection>(ExistingSections[0]);
			}
			if (!Section)
			{
				Section = CastChecked<UMovieScene2DTransformSection>(Track->CreateNewSection());
				Track->AddSection(*Section);
			}
			for (const TSharedPtr<FJsonValue>& KeyValue : *Keys)
			{
				if (TrackKind == TrackKindRenderTransformAngle)
				{
					double TimeMs = 0.0;
					float Value = 0.0f;
					FString Interpolation;
					if (ParseScalarKey(KeyValue.IsValid() ? KeyValue->AsObject() : nullptr, TimeMs, Value, Interpolation, OutErrors))
					{
						AddFloatKey(Section->Rotation, MillisecondsToFrame(Animation->MovieScene, TimeMs), Value, Interpolation);
					}
				}
				else
				{
					double TimeMs = 0.0;
					FVector2D Value;
					FString Interpolation;
					if (ParseVectorKey(KeyValue.IsValid() ? KeyValue->AsObject() : nullptr, TimeMs, Value, Interpolation, OutErrors))
					{
						FMovieSceneFloatChannel& XChannel = TrackKind == TrackKindRenderTransformTranslation ? Section->Translation[0] : Section->Scale[0];
						FMovieSceneFloatChannel& YChannel = TrackKind == TrackKindRenderTransformTranslation ? Section->Translation[1] : Section->Scale[1];
						const FFrameNumber Frame = MillisecondsToFrame(Animation->MovieScene, TimeMs);
						AddFloatKey(XChannel, Frame, Value.X, Interpolation);
						AddFloatKey(YChannel, Frame, Value.Y, Interpolation);
					}
				}
			}
			continue;
		}

		if (TrackKind == TrackKindColorAndOpacity)
		{
			if (!Widget->GetClass()->FindPropertyByName(TEXT("ColorAndOpacity")))
			{
				OutErrors.Add(FString::Printf(TEXT("Widget '%s' does not expose a ColorAndOpacity property."), *WidgetPath));
				continue;
			}

			UMovieSceneColorTrack* Track = Animation->MovieScene->AddTrack<UMovieSceneColorTrack>(BindingGuid);
			Track->SetPropertyNameAndPath(TEXT("ColorAndOpacity"), TEXT("ColorAndOpacity"));
			UMovieSceneColorSection* Section = CastChecked<UMovieSceneColorSection>(Track->CreateNewSection());
			Track->AddSection(*Section);
			for (const TSharedPtr<FJsonValue>& KeyValue : *Keys)
			{
				double TimeMs = 0.0;
				FLinearColor Value;
				FString Interpolation;
				if (ParseColorKey(KeyValue.IsValid() ? KeyValue->AsObject() : nullptr, TimeMs, Value, Interpolation, OutErrors))
				{
					const FFrameNumber Frame = MillisecondsToFrame(Animation->MovieScene, TimeMs);
					AddFloatKey(Section->GetRedChannel(), Frame, Value.R, Interpolation);
					AddFloatKey(Section->GetGreenChannel(), Frame, Value.G, Interpolation);
					AddFloatKey(Section->GetBlueChannel(), Frame, Value.B, Interpolation);
					AddFloatKey(Section->GetAlphaChannel(), Frame, Value.A, Interpolation);
				}
			}
			continue;
		}

		OutErrors.Add(FString::Printf(TEXT("Track '%s' is unsupported in v2."), *TrackKind));
	}

	return OutErrors.Num() == 0;
}

static TSharedPtr<FJsonObject> BuildMutationResult(FAssetMutationContext& Context,
                                                   const bool bSuccess,
                                                   UWidgetBlueprint* WidgetBlueprint,
                                                   UWidgetAnimation* Animation)
{
	const TSharedPtr<FJsonObject> Result = Context.BuildResult(bSuccess);
	Result->SetArrayField(TEXT("supportedTracks"), SupportedTracksJson());
	if (Animation)
	{
		Result->SetStringField(TEXT("animationName"), Animation->GetName());
		if (const TSharedPtr<FJsonObject> AnimationObject = SerializeAnimation(WidgetBlueprint, Animation))
		{
			Result->SetObjectField(TEXT("animation"), AnimationObject);
		}
	}
	return Result;
}

} // namespace WidgetAnimationAuthoringInternal

TArray<FString> FWidgetAnimationAuthoring::GetSupportedTrackKinds()
{
	return WidgetAnimationAuthoringInternal::BuildSupportedTrackKinds();
}

TSharedPtr<FJsonObject> FWidgetAnimationAuthoring::Extract(UWidgetBlueprint* WidgetBlueprint,
                                                           const FString& AnimationName)
{
	using namespace WidgetAnimationAuthoringInternal;

	if (!WidgetBlueprint)
	{
		return MakeExtractError(FString(), TEXT("WidgetBlueprint is null."));
	}

	UWidgetAnimation* Animation = FindAnimationByName(WidgetBlueprint, AnimationName);
	if (!Animation)
	{
		return MakeExtractError(WidgetBlueprint->GetPathName(), FString::Printf(TEXT("Widget animation '%s' was not found."), *AnimationName));
	}

	const TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("operation"), TEXT("extract_widget_animation"));
	Result->SetStringField(TEXT("assetPath"), WidgetBlueprint->GetPathName());
	Result->SetStringField(TEXT("animationName"), Animation->GetName());
	Result->SetArrayField(TEXT("supportedTracks"), SupportedTracksJson());
	Result->SetObjectField(TEXT("animation"), SerializeAnimation(WidgetBlueprint, Animation));
	return Result;
}

TSharedPtr<FJsonObject> FWidgetAnimationAuthoring::Create(UWidgetBlueprint* WidgetBlueprint,
                                                          const FString& AnimationName,
                                                          const TSharedPtr<FJsonObject>& PayloadJson,
                                                          const bool bValidateOnly)
{
	using namespace WidgetAnimationAuthoringInternal;

	FAssetMutationContext Context(
		TEXT("create_widget_animation"),
		WidgetBlueprint ? WidgetBlueprint->GetPathName() : FString(),
		TEXT("WidgetBlueprint"),
		bValidateOnly);

	if (!WidgetBlueprint)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("WidgetBlueprint is null."));
		return Context.BuildResult(false);
	}

	const FString RequestedName = AnimationName.IsEmpty() ? TEXT("WidgetAnimation") : AnimationName;
	if (FindAnimationByName(WidgetBlueprint, RequestedName))
	{
		Context.AddError(TEXT("animation_exists"), FString::Printf(TEXT("Widget animation '%s' already exists."), *RequestedName), WidgetBlueprint->GetPathName());
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	if (PayloadJson.IsValid())
	{
		if (const TSharedPtr<FJsonObject>* Timeline = nullptr; PayloadJson->TryGetObjectField(TEXT("timeline"), Timeline) && Timeline && (*Timeline).IsValid())
		{
			const TArray<TSharedPtr<FJsonValue>>* Tracks = nullptr;
			if (!(*Timeline)->TryGetArrayField(TEXT("tracks"), Tracks) || !Tracks)
			{
				ValidationErrors.Add(TEXT("timeline.tracks is required when a timeline object is supplied."));
			}
			else
			{
				for (const TSharedPtr<FJsonValue>& TrackValue : *Tracks)
				{
					FString WidgetPath;
					ResolveWidgetFromSelector(WidgetBlueprint, TrackValue.IsValid() ? TrackValue->AsObject() : nullptr, WidgetPath, ValidationErrors);
				}
			}
		}
	}

	Context.SetValidationSummary(ValidationErrors.Num() == 0,
		ValidationErrors.Num() == 0
			? TEXT("Widget animation payload validated.")
			: TEXT("Widget animation payload failed validation."),
		ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, WidgetBlueprint->GetPathName());
	}
	if (ValidationErrors.Num() > 0)
	{
		return Context.BuildResult(false);
	}

	const FString UniqueName = BuildUniqueAnimationName(WidgetBlueprint, RequestedName);
	if (bValidateOnly)
	{
		const TSharedPtr<FJsonObject> Result = Context.BuildResult(true);
		Result->SetStringField(TEXT("animationName"), UniqueName);
		Result->SetArrayField(TEXT("supportedTracks"), SupportedTracksJson());
		return Result;
	}

	Context.BeginTransaction(FText::FromString(TEXT("Create Widget Animation")));
	WidgetBlueprint->Modify();

	const FName UniqueFName(*UniqueName);
	UWidgetAnimation* NewAnimation = NewObject<UWidgetAnimation>(WidgetBlueprint, UniqueFName, RF_Transactional);
	NewAnimation->Rename(*UniqueName);
#if WITH_EDITOR
	NewAnimation->SetDisplayLabel(UniqueName);
#endif
	NewAnimation->MovieScene = NewObject<UMovieScene>(NewAnimation, UniqueFName, RF_Transactional);

	TArray<FString> ApplyErrors;
	ApplyPlaybackMetadata(NewAnimation, PayloadJson, ApplyErrors);
	if (PayloadJson.IsValid() && PayloadJson->HasField(TEXT("timeline")))
	{
		ApplyTimelinePayload(WidgetBlueprint, NewAnimation, PayloadJson, ApplyErrors);
	}
	for (const FString& Error : ApplyErrors)
	{
		Context.AddError(TEXT("apply_error"), Error, WidgetBlueprint->GetPathName());
	}
	if (ApplyErrors.Num() > 0)
	{
		return BuildMutationResult(Context, false, WidgetBlueprint, nullptr);
	}

	WidgetBlueprint->Animations.Add(NewAnimation);
	WidgetBlueprint->OnVariableAdded(NewAnimation->GetFName());
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBlueprint);
	WidgetBlueprint->MarkPackageDirty();
	Context.TrackDirtyObject(WidgetBlueprint);
	Context.TrackDirtyObject(NewAnimation);
	Context.TrackDirtyObject(NewAnimation->MovieScene);
	return BuildMutationResult(Context, true, WidgetBlueprint, NewAnimation);
}

TSharedPtr<FJsonObject> FWidgetAnimationAuthoring::Modify(UWidgetBlueprint* WidgetBlueprint,
                                                          const FString& AnimationName,
                                                          const FString& Operation,
                                                          const TSharedPtr<FJsonObject>& PayloadJson,
                                                          const bool bValidateOnly)
{
	using namespace WidgetAnimationAuthoringInternal;

	FAssetMutationContext Context(
		TEXT("modify_widget_animation"),
		WidgetBlueprint ? WidgetBlueprint->GetPathName() : FString(),
		TEXT("WidgetBlueprint"),
		bValidateOnly);

	if (!WidgetBlueprint)
	{
		Context.AddError(TEXT("asset_not_found"), TEXT("WidgetBlueprint is null."));
		return Context.BuildResult(false);
	}

	if (Operation == TEXT("compile"))
	{
		FAuthoringHelpers::CompileBlueprint(WidgetBlueprint, Context, TEXT("WidgetBlueprint"));
		UWidgetAnimation* Animation = FindAnimationByName(WidgetBlueprint, AnimationName);
		return BuildMutationResult(Context, Context.CompileSummary.IsValid() ? Context.CompileSummary->GetBoolField(TEXT("success")) : true, WidgetBlueprint, Animation);
	}

	UWidgetAnimation* Animation = FindAnimationByName(WidgetBlueprint, AnimationName);
	if (!Animation)
	{
		Context.AddError(TEXT("animation_not_found"), FString::Printf(TEXT("Widget animation '%s' was not found."), *AnimationName), WidgetBlueprint->GetPathName());
		return Context.BuildResult(false);
	}

	TArray<FString> ValidationErrors;
	if (Operation == TEXT("replace_timeline"))
	{
		if (!PayloadJson.IsValid() || !PayloadJson->HasField(TEXT("timeline")))
		{
			ValidationErrors.Add(TEXT("replace_timeline requires payload.timeline."));
		}
	}
	else if (Operation == TEXT("patch_metadata"))
	{
		if (!PayloadJson.IsValid())
		{
			ValidationErrors.Add(TEXT("patch_metadata requires a payload."));
		}
	}
	else if (Operation == TEXT("rename_animation"))
	{
		FString NewName;
		if (!PayloadJson.IsValid() || !PayloadJson->TryGetStringField(TEXT("new_name"), NewName) || NewName.IsEmpty())
		{
			ValidationErrors.Add(TEXT("rename_animation requires payload.new_name."));
		}
		else if (NewName != AnimationName && FindAnimationByName(WidgetBlueprint, NewName))
		{
			ValidationErrors.Add(FString::Printf(TEXT("Widget animation '%s' already exists."), *NewName));
		}
	}
	else if (Operation != TEXT("remove_animation"))
	{
		ValidationErrors.Add(FString::Printf(TEXT("Unsupported modify_widget_animation operation '%s'."), *Operation));
	}

	Context.SetValidationSummary(ValidationErrors.Num() == 0,
		ValidationErrors.Num() == 0 ? TEXT("Widget animation payload validated.") : TEXT("Widget animation payload failed validation."),
		ValidationErrors);
	for (const FString& Error : ValidationErrors)
	{
		Context.AddError(TEXT("validation_error"), Error, WidgetBlueprint->GetPathName());
	}
	if (ValidationErrors.Num() > 0)
	{
		return BuildMutationResult(Context, false, WidgetBlueprint, Animation);
	}

	if (bValidateOnly)
	{
		return BuildMutationResult(Context, true, WidgetBlueprint, Animation);
	}

	Context.BeginTransaction(FText::FromString(TEXT("Modify Widget Animation")));
	WidgetBlueprint->Modify();
	Animation->Modify();
	if (Animation->MovieScene)
	{
		Animation->MovieScene->Modify();
	}

	if (Operation == TEXT("replace_timeline"))
	{
		TArray<FString> ApplyErrors;
		ApplyTimelinePayload(WidgetBlueprint, Animation, PayloadJson, ApplyErrors);
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, WidgetBlueprint->GetPathName());
		}
		if (ApplyErrors.Num() > 0)
		{
			return BuildMutationResult(Context, false, WidgetBlueprint, Animation);
		}
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBlueprint);
	}
	else if (Operation == TEXT("patch_metadata"))
	{
		TArray<FString> ApplyErrors;
		ApplyPlaybackMetadata(Animation, PayloadJson, ApplyErrors);
		for (const FString& Error : ApplyErrors)
		{
			Context.AddError(TEXT("apply_error"), Error, WidgetBlueprint->GetPathName());
		}
		if (ApplyErrors.Num() > 0)
		{
			return BuildMutationResult(Context, false, WidgetBlueprint, Animation);
		}
		FBlueprintEditorUtils::MarkBlueprintAsModified(WidgetBlueprint);
	}
	else if (Operation == TEXT("rename_animation"))
	{
		FString NewName;
		PayloadJson->TryGetStringField(TEXT("new_name"), NewName);
		const FName OldFName = Animation->GetFName();
		const FName NewFName(*NewName);
		Animation->Rename(*NewName);
		if (Animation->MovieScene)
		{
			Animation->MovieScene->Rename(*NewName);
		}
#if WITH_EDITOR
		Animation->SetDisplayLabel(NewName);
#endif
		WidgetBlueprint->OnVariableRenamed(OldFName, NewFName);
		FBlueprintEditorUtils::ReplaceVariableReferences(WidgetBlueprint, OldFName, NewFName);
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBlueprint);
	}
	else if (Operation == TEXT("remove_animation"))
	{
		const FName RemovedName = Animation->GetFName();
		Animation->Rename(nullptr, GetTransientPackage());
		WidgetBlueprint->Animations.Remove(Animation);
		WidgetBlueprint->OnVariableRemoved(RemovedName);
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(WidgetBlueprint);
		Animation = nullptr;
	}

	WidgetBlueprint->MarkPackageDirty();
	Context.TrackDirtyObject(WidgetBlueprint);
	if (Animation)
	{
		Context.TrackDirtyObject(Animation);
		if (Animation->MovieScene)
		{
			Context.TrackDirtyObject(Animation->MovieScene);
		}
	}
	return BuildMutationResult(Context, true, WidgetBlueprint, Animation);
}
