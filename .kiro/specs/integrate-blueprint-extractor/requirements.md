# Requirements Document

## Introduction

本文档定义了将开源项目 `blueprint-extractor` 集成到 UE Toolkit 的需求。该集成将替换现有的 `BlueprintToAI` 插件，并实现基于 License 的功能分级（免费版 vs 付费版）。

`blueprint-extractor` 是一个成熟的开源项目，支持 112 个工具，覆盖 Blueprint、UMG、Material、AI 资产等。所有权限控制在 Python 层实现，不修改插件源码以保持开源合规。

## Glossary

- **UE_Toolkit**: 虚幻引擎工具包，提供 AI 助手和资产操作能力的 Python 应用程序
- **Blueprint_Extractor**: 开源的虚幻引擎插件，提供资产提取和操作的 HTTP API
- **Tools_Registry**: 工具注册表，管理所有可用工具的注册和调度
- **Feature_Gate**: 功能门控系统，基于 License 控制工具访问权限
- **License_Manager**: 许可证管理器，处理激活和验证
- **UE_Tool_Client**: HTTP 客户端，与 Blueprint_Extractor 插件通信
- **Free_Tools**: 免费工具集，包含所有只读操作（18 个工具）
- **Pro_Tools**: 付费工具集，包含所有创建和修改操作（94 个工具）
- **Subsystem**: 虚幻引擎子系统，Blueprint_Extractor 的核心组件

## Requirements

### Requirement 1: 插件文件管理

**User Story:** 作为开发者，我希望正确部署 Blueprint_Extractor 插件，以便替换旧的 BlueprintToAI 插件

#### Acceptance Criteria

1. THE UE_Toolkit SHALL deploy Blueprint_Extractor plugin to `Plugins/BlueprintExtractor/` directory
2. THE UE_Toolkit SHALL remove the deprecated `Plugins/BlueprintToAI/` directory
3. THE UE_Toolkit SHALL remove the temporary `Plugins/temp_blueprint_extractor/` directory
4. THE UE_Toolkit SHALL preserve the original LICENSE file from Blueprint_Extractor

### Requirement 2: HTTP 客户端配置

**User Story:** 作为开发者，我希望 HTTP 客户端连接到正确的插件端点，以便与 Blueprint_Extractor 通信

#### Acceptance Criteria

1. THE UE_Tool_Client SHALL use subsystem path `/Script/BlueprintExtractor.Default__BlueprintExtractorSubsystem`
2. WHEN connection is established, THE UE_Tool_Client SHALL verify the Subsystem is accessible
3. IF connection fails, THEN THE UE_Tool_Client SHALL return a descriptive error message

### Requirement 3: 权限控制集成

**User Story:** 作为产品经理，我希望实现基于 License 的功能分级，以便区分免费用户和付费用户

#### Acceptance Criteria

1. THE Tools_Registry SHALL initialize a Feature_Gate instance with License_Manager
2. WHEN a tool is dispatched, THE Tools_Registry SHALL check permissions before execution
3. IF a tool is not allowed, THEN THE Tools_Registry SHALL return an error with `locked: true` and `tier: "pro"`
4. THE Feature_Gate SHALL skip permission checks for non-UE tools
5. THE error message SHALL be user-friendly and suggest activation

### Requirement 4: 免费工具定义

**User Story:** 作为免费用户，我希望使用只读功能，以便分析和查看 UE 资产

#### Acceptance Criteria

1. THE Feature_Gate SHALL define Free_Tools as a set containing all Extract\* tools
2. THE Free_Tools SHALL include `ExtractBlueprint` for reading blueprint structure
3. THE Free_Tools SHALL include `ExtractWidgetBlueprint` for reading UMG widgets
4. THE Free_Tools SHALL include `ExtractMaterial` for reading materials
5. THE Free_Tools SHALL include `SearchAssets` for searching assets
6. THE Free_Tools SHALL include `ListAssets` for listing assets
7. THE Free_Tools SHALL include `GetActiveBlueprint` for getting current active blueprint
8. THE Free_Tools SHALL include `ExtractActiveBlueprint` for extracting current active blueprint
9. THE Free_Tools SHALL include `GetEditorContext` for getting editor state
10. WHEN License is not activated, THE Feature_Gate SHALL allow access to all Free_Tools

### Requirement 5: 付费工具定义

**User Story:** 作为付费用户，我希望使用完整功能，以便创建和修改 UE 资产

#### Acceptance Criteria

1. THE Feature_Gate SHALL define Pro_Tools as a set containing all Create* and Modify* tools
2. THE Pro_Tools SHALL include `CreateBlueprint` for creating new blueprints
3. THE Pro_Tools SHALL include `ModifyBlueprintMembers` for modifying blueprint members
4. THE Pro_Tools SHALL include `CreateWidgetBlueprint` for creating UMG widgets
5. THE Pro_Tools SHALL include `ModifyWidget` for modifying UMG widgets
6. THE Pro_Tools SHALL include `SaveAssets` for saving assets
7. THE Pro_Tools SHALL include all Import\* tools for importing external resources
8. THE Pro_Tools SHALL include all Capture\* tools for validation
9. THE Pro_Tools SHALL include PIE control and LiveCoding tools
10. WHEN License is not activated, THE Feature_Gate SHALL block access to all Pro_Tools
11. WHEN License is activated, THE Feature_Gate SHALL allow access to all Pro_Tools

### Requirement 6: 工具注册

**User Story:** 作为开发者，我希望注册 Blueprint_Extractor 的工具到 Tools_Registry，以便 AI 助手可以使用这些工具

#### Acceptance Criteria

1. THE Tools_Registry SHALL provide a method `_register_blueprint_extractor_tools()`
2. THE Tools_Registry SHALL register at least 20 core tools from Blueprint_Extractor
3. WHEN registering a tool, THE Tools_Registry SHALL include tool name, description, and parameters schema
4. WHEN registering a tool, THE Tools_Registry SHALL specify whether confirmation is required
5. THE tool description SHALL be clear and in Chinese
6. THE tool parameters SHALL follow JSON Schema format
7. THE tool function SHALL delegate to `_execute_ue_python_tool()` method
8. THE Tools_Registry SHALL register both Free_Tools and Pro_Tools

### Requirement 7: 工具执行

**User Story:** 作为用户，我希望工具执行结果准确，以便完成资产操作任务

#### Acceptance Criteria

1. WHEN a Free_Tool is called, THE Tools_Registry SHALL execute it via UE_Tool_Client
2. WHEN a Pro_Tool is called with valid license, THE Tools_Registry SHALL execute it via UE_Tool_Client
3. WHEN a Pro_Tool is called without valid license, THE Tools_Registry SHALL return permission error
4. WHEN tool execution succeeds, THE Tools_Registry SHALL return `success: true` with result data
5. WHEN tool execution fails, THE Tools_Registry SHALL return `success: false` with error message
6. THE result data SHALL be in JSON format
7. THE result data SHALL match Blueprint_Extractor's output schema

### Requirement 8: 旧代码清理

**User Story:** 作为开发者，我希望删除旧的 BlueprintToAI 相关代码，以便保持代码库整洁

#### Acceptance Criteria

1. THE Tools_Registry SHALL remove or replace the `_register_ue_tools()` method
2. THE codebase SHALL have no references to "BlueprintToAI"
3. THE old plugin directory `Plugins/BlueprintToAI/` SHALL be deleted
4. THE old design documents SHALL be removed

### Requirement 9: 免费功能测试

**User Story:** 作为 QA 工程师，我希望验证免费功能正常工作，以便确保用户体验

#### Acceptance Criteria

1. WHEN License is not activated, THE UE_Toolkit SHALL allow ExtractBlueprint execution
2. WHEN License is not activated, THE UE_Toolkit SHALL allow SearchAssets execution
3. WHEN License is not activated, THE UE_Toolkit SHALL allow GetActiveBlueprint execution
4. WHEN ExtractBlueprint is called with valid asset path, THE UE_Toolkit SHALL return complete JSON structure
5. THE extracted JSON SHALL include blueprint nodes, variables, and functions
6. THE extracted JSON SHALL be parseable and valid

### Requirement 10: 付费功能阻止测试

**User Story:** 作为 QA 工程师，我希望验证未激活时付费功能被正确阻止，以便保护商业模式

#### Acceptance Criteria

1. WHEN License is not activated and CreateBlueprint is called, THE UE_Toolkit SHALL return error
2. WHEN License is not activated and ModifyBlueprintMembers is called, THE UE_Toolkit SHALL return error
3. WHEN License is not activated and SaveAssets is called, THE UE_Toolkit SHALL return error
4. THE error response SHALL include `success: false`
5. THE error response SHALL include `locked: true`
6. THE error response SHALL include `tier: "pro"`
7. THE error message SHALL suggest user to activate license
8. THE error message SHALL be in Chinese

### Requirement 11: 付费功能激活测试

**User Story:** 作为 QA 工程师，我希望验证激活后付费功能正常工作，以便确保付费用户体验

#### Acceptance Criteria

1. WHEN License is activated and CreateBlueprint is called, THE UE_Toolkit SHALL create the blueprint
2. WHEN License is activated and ModifyBlueprintMembers is called, THE UE_Toolkit SHALL modify the blueprint
3. WHEN License is activated and SaveAssets is called, THE UE_Toolkit SHALL save the assets
4. THE created blueprint SHALL be visible in UE Editor
5. THE modified blueprint SHALL reflect the changes in UE Editor
6. THE saved assets SHALL persist after editor restart

### Requirement 12: 插件编译和工具访问测试

**User Story:** 作为开发者，我希望验证插件编译成功且所有工具可访问，以便确保集成完整性

#### Acceptance Criteria

1. WHEN Blueprint_Extractor plugin is deployed, THE UE_Toolkit SHALL compile the plugin successfully
2. WHEN plugin compilation completes, THE UE_Toolkit SHALL verify all registered tools are accessible
3. THE UE_Toolkit SHALL provide a test script to verify tool accessibility
4. WHEN test script runs, THE test script SHALL call each registered tool with valid test parameters
5. WHEN test script runs, THE test script SHALL report success or failure for each tool
6. THE test script SHALL test at least 5 Free_Tools
7. THE test script SHALL test at least 5 Pro_Tools (with activated license)
8. IF any tool is not accessible, THEN THE test script SHALL report the tool name and error details
9. THE test results SHALL be logged to a file for review

### Requirement 13: 文档更新

**User Story:** 作为用户，我希望阅读更新的文档，以便了解新功能和限制

#### Acceptance Criteria

1. THE README.md SHALL include a "Third-Party Components" section
2. THE "Third-Party Components" section SHALL credit Blueprint_Extractor with author, license, and repository URL
3. THE README.md SHALL document Free_Tools capabilities
4. THE README.md SHALL document Pro_Tools capabilities
5. THE README.md SHALL explain the difference between free and paid tiers
6. THE integration guide `Plugins/BLUEPRINT_EXTRACTOR_INTEGRATION.md` SHALL be preserved
7. THE official documentation `Plugins/BlueprintExtractor/README.md` SHALL be preserved
8. THE LICENSE file SHALL be preserved

### Requirement 14: 临时文件清理

**User Story:** 作为开发者，我希望删除不再需要的临时文件，以便保持项目整洁

#### Acceptance Criteria

1. THE UE_Toolkit SHALL delete `Plugins/BlueprintToAI_Design.md`
2. THE UE_Toolkit SHALL delete `Plugins/BLUEPRINT_EXTRACTOR_ANALYSIS.md`
3. THE UE_Toolkit SHALL delete old test scripts: `test_blueprint_plugin.py`, `test_active_blueprint.py`, `test_add_variable_fixed.py`
4. THE UE_Toolkit SHALL preserve `Plugins/BLUEPRINT_EXTRACTOR_INTEGRATION.md`
5. THE UE_Toolkit SHALL preserve `Plugins/BlueprintExtractor/README.md`
6. THE UE_Toolkit SHALL preserve `Plugins/BlueprintExtractor/LICENSE`

### Requirement 15: 错误处理

**User Story:** 作为用户，我希望收到友好的错误提示，以便快速解决问题

#### Acceptance Criteria

1. WHEN License is not activated and Pro_Tool is called, THE UE_Toolkit SHALL return a message suggesting upgrade
2. WHEN UE Editor is not running, THE UE_Toolkit SHALL return a message suggesting to start UE Editor
3. WHEN tool parameters are invalid, THE UE_Toolkit SHALL return a message showing correct parameter format
4. WHEN Blueprint_Extractor returns an error, THE UE_Toolkit SHALL forward the error message to user
5. THE error messages SHALL be in Chinese
6. THE error messages SHALL be actionable and specific

### Requirement 16: 开源合规

**User Story:** 作为法务人员，我希望确保开源许可证合规，以便避免法律风险

#### Acceptance Criteria

1. THE UE_Toolkit SHALL NOT modify Blueprint_Extractor plugin source code
2. THE UE_Toolkit SHALL implement all permission control in Python layer
3. THE UE_Toolkit SHALL preserve the original MIT LICENSE file from Blueprint_Extractor
4. THE README.md SHALL include third-party component attribution
5. THE attribution SHALL include project name, author, license type, and repository URL

### Requirement 17: 版本兼容性

**User Story:** 作为用户，我希望了解支持的 UE 版本，以便确认兼容性

#### Acceptance Criteria

1. THE documentation SHALL state that Blueprint_Extractor supports UE 5.6 and 5.7
2. THE UE_Toolkit SHALL prioritize support for UE 5.6
3. WHERE user requests support for other UE versions, THE documentation SHALL explain version adaptation process
4. THE UE_Toolkit SHALL detect UE version and warn if unsupported

## Non-Functional Requirements

### Performance

1. WHEN a Free_Tool is called, THE UE_Toolkit SHALL return results within 5 seconds for typical assets
2. WHEN permission check is performed, THE Feature_Gate SHALL complete within 10 milliseconds

### Reliability

1. THE UE_Toolkit SHALL handle Blueprint_Extractor connection failures gracefully
2. THE UE_Toolkit SHALL retry failed HTTP requests up to 3 times with exponential backoff

### Maintainability

1. THE tool registration code SHALL be modular and easy to extend
2. THE Free_Tools and Pro_Tools lists SHALL be defined in a single location for easy updates
3. THE code SHALL include comments explaining the integration architecture

### Security

1. THE License_Manager SHALL validate license keys securely
2. THE UE_Tool_Client SHALL use HTTP (not HTTPS) only for localhost connections
3. THE Feature_Gate SHALL prevent privilege escalation attempts

## Success Criteria

- All 17 requirements are implemented and tested
- Free tools work without activation
- Pro tools are correctly blocked without activation
- Pro tools work after activation
- Documentation is complete with third-party attribution
- No compilation errors or runtime errors
- Code passes review

## Dependencies and Constraints

- Blueprint_Extractor plugin must be compatible with UE 5.6+
- License_Manager must be implemented and functional
- UE Editor must be running for tool execution
- HTTP server in Blueprint_Extractor must be enabled

## Risks

1. **Version Compatibility**: Blueprint_Extractor only supports UE 5.6 and 5.7
   - Mitigation: Document supported versions clearly, plan for future version support

2. **Open Source Compliance**: Must not modify plugin source code
   - Mitigation: Implement all permission control in Python layer

3. **Tool Naming**: Blueprint_Extractor uses PascalCase naming
   - Mitigation: Ensure consistent naming in Python code and Feature_Gate

4. **Error Handling**: Users need clear guidance when errors occur
   - Mitigation: Implement friendly error messages with actionable suggestions
