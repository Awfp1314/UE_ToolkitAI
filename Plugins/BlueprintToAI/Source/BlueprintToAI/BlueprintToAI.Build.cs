// Copyright HUTAO. All Rights Reserved.

using UnrealBuildTool;

public class BlueprintToAI : ModuleRules
{
	public BlueprintToAI(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;
		
		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
			}
		);
			
		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"CoreUObject",
				"Engine",
				"Slate",
				"SlateCore",
				"UnrealEd",
				"EditorSubsystem",
				"AssetRegistry",
				"AssetTools",
				"BlueprintGraph",
				"KismetCompiler",
				"Kismet",
				"GraphEditor",
				"Json",
				"JsonUtilities",
				"RemoteControlCommon",
				"HTTP",
				"EnhancedInput",
			}
		);
	}
}
