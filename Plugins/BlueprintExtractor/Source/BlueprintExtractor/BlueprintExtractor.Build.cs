using UnrealBuildTool;

public class BlueprintExtractor : ModuleRules
{
	public BlueprintExtractor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;
		ShortName = "BPE";

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"CoreUObject",
			"EditorSubsystem",
			"Engine",
			"DeveloperSettings",
			"RemoteControlCommon",
			"Slate",
			"SlateCore",
			"UnrealEd",
			"BlueprintGraph",
			"KismetCompiler",
			"Kismet",
			"GraphEditor",
			"ContentBrowser",
			"ContentBrowserData",
			"AssetTools",
			"AssetRegistry",
			"HTTP",
			"InterchangeEngine",
			"Json",
			"JsonUtilities",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"MaterialEditor",
			"PropertyBindingUtils",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"MessageLog",
			"GameplayTags",
			"UMG",
			"UMGEditor",
			"MovieScene",
			"MovieSceneTracks",
			"RenderCore",
			"RHI",
			"ImageCore",
			"SparseVolumeTexture"
		});

		if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.AddRange(new string[]
			{
				"AIGraph",
				"AnimGraph",
				"AnimationBlueprintLibrary",
				"BehaviorTreeEditor",
				"StateTreeEditorModule"
			});

			if (Target.Platform == UnrealTargetPlatform.Win64)
			{
				PrivateDependencyModuleNames.Add("LiveCoding");
			}
		}
	}
}
