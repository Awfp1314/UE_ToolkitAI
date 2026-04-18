using UnrealBuildTool;

public class BlueprintAnalyzer : ModuleRules
{
	public BlueprintAnalyzer(ReadOnlyTargetRules Target) : base(Target)
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
			"UnrealEd",
			"BlueprintGraph",
			"Kismet",
			"KismetCompiler",
			"AssetRegistry",
			"Json",
			"JsonUtilities",
			"UMG",
			"UMGEditor",
			"Slate",
			"SlateCore"
		});
	}
}
