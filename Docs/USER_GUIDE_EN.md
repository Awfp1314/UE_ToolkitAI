# UE Toolkit User Guide

**[中文](USER_GUIDE.md) | English**

---

# Quick Start

## Project Management

- **Centralized Scanning**: Automatically retrieves all Unreal Engine projects on local disk, enabling one-stop navigation and quick launch for multi-version projects.

- **Lossless Renaming**: Supports one-click renaming logic for Blueprint projects, ensuring that renaming does not affect packaging and deployment through automated path association handling (C++ project support in development).

## Asset Management

- **Multi-dimensional Asset Support**: Supports unified warehousing of four packaging structures: `CONTENT` (asset packages), `PLUGIN` (plugins), `PROJECT` (complete projects), and `OTHERS` (general multimedia).

- **Automatic Metadata Recognition**: Automatically analyzes asset structure during warehousing, identifies corresponding Unreal Engine version and asset type, reducing manual maintenance costs.

- **Resource Organization Optimization**: Built-in intelligent filtering mechanism, supports automatic decompression, deduplication, and ad file filtering to keep asset library clean.

## AI Assistant

- **Logic Audit**: Uses AI to deeply analyze assets in the library, supporting structured analysis of individual assets or entire asset libraries.
- **Blueprint Analysis (UE 5.4)**: Based on Socket communication and UE plugin linkage, supports read-only mode logic analysis and fault diagnosis for version 5.4 blueprints.

## Configuration Tool

- **Configuration Mirroring**: Supports snapshot saving of project User Preferences and Project Settings.
- **One-click Sync**: Enables quick application of configurations across different projects, currently perfectly adapted to UE4 environment development flow.

# 1. Project Management

> When opening the toolbox for the first time, it will scan projects, loading may be slow. After scanning is complete, it looks like this:

![Project Management Interface](images/image-20260405183418787.png)

> Right-click menu supports the following functions:

![Right-click Menu](images/image-20260405183556769.png)

# 2. Asset Management

## 2.1 Adding Assets

> Supports drag-and-drop adding and adding through toolbox. Adding assets supports two formats: compressed packages and folders. Both formats will automatically recognize asset types, including asset packages, plugins, projects, models, and other resources.

![Add Asset](images/image-20260405183932595.png)

> Whether it's a compressed package or folder, it will intelligently recognize the asset type, eliminating the trouble of manually decompressing and adjusting to the appropriate structure before importing.

![Asset Recognition 1](images/image-20260405184111444.png)

![Asset Recognition 2](images/image-20260405184131281.png)

> If you check "Create Description Document" when adding, a description document will be automatically created. Click the asset card with the left mouse button to open it. If not checked, you can create it later by clicking the asset card with the left mouse button.

![Description Document](images/image-20260405184439212.png)

> After successful addition, the added asset card will appear (Note: The asset does not have a thumbnail yet, we will introduce how to set thumbnails later)

![Asset Card](images/image-20260405184639373.png)

## 2.2 Previewing Assets

To preview assets, you first need to create and configure a preview project

> First create a preview project

![Create Preview Project](images/image-20260405185037657.png)

> After creating the preview project, open Toolbox Settings -> Asset Settings -> Add Preview Project

![Add Preview Project](images/image-20260405185303922.png)

> After setting up, return to the asset library interface and click Preview Asset on the asset card

![Preview Asset Button](images/image-20260405185414911.png)

> Select the preview project to use

![Select Preview Project](images/image-20260405185455110.png)

> You can see this is the previewed asset package

![Preview Asset Package](images/image-20260405185605775.png)

> The asset opens without damage or other issues and can be previewed normally

![Normal Preview](images/image-20260405185644719.png)

## 2.3 Setting Asset Thumbnails

Currently only supports thumbnail settings for asset packages and project assets

> First preview the asset you want to set a thumbnail for

There are two ways to set thumbnails:

- The first is to adjust to the appropriate position during preview and exit directly, which will automatically set the thumbnail. This method changes the thumbnail every time you preview the asset.
- The second is a permanent thumbnail. Next, we'll introduce how to set a permanent thumbnail.

> After previewing the asset, adjust it to the appropriate angle, take a high-resolution screenshot, then close the project to set a permanent thumbnail

![High Resolution Screenshot](images/image-20260405190122229.png)

> You can see the thumbnail has been set successfully

![Thumbnail Set Successfully](images/image-20260405190156001.png)

## 2.4 Importing Assets

> When importing assets, click the import icon on the asset card to open the project selection interface, which will automatically filter projects that can use the current asset

![Import Asset](images/image-20260405190359434.png)

> Click the Import to Project button to successfully import

# 3. AI Assistant

## 3.1 AI Assistant Configuration

AI Assistant supports mainstream model provider configurations, BYOK custom provider configuration, and Ollama. You only need to enter the key. Custom configuration requires entering the URL.

> Open Settings -> AI Assistant, enter the key, then save the configuration

![AI Assistant Configuration](images/image-20260405190819066.png)

> Let's do a simple test

![AI Test 1](images/image-20260405191539170.png)

![AI Test 2](images/image-20260405191605488.png)

> You can see a detailed analysis of the asset

## 3.2 Blueprint Analysis

Blueprint Analysis (currently only supports UE5.4)

> Blueprint analysis requires the use of a plugin. First, place the plugin in the project's Plugins folder. If it's a C++ project, compile it after placing the plugin. If it's a Blueprint project, after placing the plugin, right-click the project file and click the option shown in the image to compile the plugin.

![Plugin Compilation 1](images/image-20260301191908034.png)

![Plugin Compilation 2](images/image-20260301200121771.png)

![Plugin Compilation 3](images/image-20260301200136954.png)

# 4. Configuration Tool

The configuration tool can extract configurations from existing projects and apply them to other projects. Extractable configurations include two categories: project configuration and editor preference settings.

![Configuration Tool](images/image-20260405192235690.png)

> After adding the configuration, click with the left mouse button to select the project to apply to. Pay attention to the version when applying.

![Apply Configuration](images/image-20260405192342577.png)

> When applying, you can choose to backup the original configuration. If problems occur, you can roll back.

![Configuration Backup 1](images/image-20260405192432120.png)

![Configuration Backup 2](images/image-20260405192450877.png)

# 5. Feedback

If you have any issues, you can click the Feedback button in the lower left corner of the toolbox to provide feedback, or join the official communication group and @ the group owner.

QQ Group: 1048699469
