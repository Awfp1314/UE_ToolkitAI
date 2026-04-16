using UnrealBuildTool;

public class BlueprintToolsUE54 : ModuleRules
{
	public BlueprintToolsUE54(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"CoreUObject",
			"Engine",
			"EditorSubsystem",
			"DeveloperSettings",
			"RemoteControlCommon",
			"UnrealEd",
			"BlueprintGraph",
			"KismetCompiler",
			"Kismet",
			"AssetRegistry",
			"Json",
			"JsonUtilities",
			"HTTP"
		});
	}
}
