# -*- coding: utf-8 -*-

"""
工具注册表
定义只读工具的接口和调度逻辑
"""

import json
from typing import Dict, Any, List, Callable, Optional
from core.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# 内置工具箱功能文档（打包为 exe 后 README.md 不可用时的 fallback）
# 更新 README.md 后请同步更新此常量
# ============================================================
_BUILTIN_TOOLKIT_DOC = """\
# UE Toolkit — 虚幻引擎工具箱

面向虚幻引擎开发者的 Windows 桌面工具箱，集工程管理、资产管理、AI 助手、配置工具和资源推荐于一体。

## 功能模块

### 1. 我的工程

管理本地所有虚幻引擎工程项目。

- 自动扫描本机已安装的 UE 引擎版本
- 发现并列出本地所有 .uproject 工程
- 支持按分类管理工程（自定义分类）
- 支持从引擎模板创建新工程（空白、第三人称、第一人称、载具等多种模板）
- 支持创建 C++ 工程或蓝图工程
- 工程卡片展示缩略图、引擎版本、最后修改时间等信息
- 右键菜单可快速打开工程、打开工程目录、编辑工程信息

### 2. 资产库

管理和浏览虚幻引擎资产资源。

- 支持添加、编辑、删除资产
- 支持拖放添加资产
- 资产卡片展示缩略图、名称、大小、时间等信息
- 支持搜索资产（包括拼音搜索）
- 支持按分类筛选资产
- 支持切换卡片视图模式（标准/紧凑）
- 资产详情弹窗查看完整信息
- 支持分类管理（新增、编辑、删除分类）

### 3. AI 助手

内置的 AI 聊天助手，支持与大语言模型对话。

- ChatGPT 风格的聊天界面
- 支持两种 LLM 供应商：
  - API 模式：兼容 OpenAI 格式的在线 API
  - Ollama 模式：连接本地 Ollama 服务，使用本地模型
- 支持流式输出，实时显示 AI 回复
- 支持多轮对话，保持上下文
- 支持 Markdown 渲染
- 内置工具调用系统，AI 可以读取资产信息、配置信息等

### 4. 工程配置

管理虚幻引擎工程的配置文件。

- 支持创建和管理配置模板
- 可将常用配置保存为模板，方便复用
- 支持快速打开配置文件所在目录
- 配置自动保存

### 5. 作者推荐

精选的虚幻引擎相关资源站点推荐。

- 按分类展示推荐站点（资源网站、工具、论坛、学习等）
- 点击卡片直接在浏览器中打开对应网站

## 通用功能

### 主题切换
- 支持深色主题和浅色主题，点击右上角太阳/月亮图标切换
- 主题设置自动保存

### 设置中心
- 点击右上角齿轮图标进入，可配置 AI 助手的 LLM 供应商、API Key、模型等

### 自动更新
- 启动时自动检查更新，标题栏可手动检查
- 发现新版本时弹出更新对话框

### 系统托盘
- 程序运行时在系统托盘显示图标
- 关闭窗口时可选择最小化到托盘或退出程序

### 问题反馈
- 左侧导航栏底部提供问题反馈按钮

## 操作注意事项

1. 本程序仅支持 Windows 系统。
2. 程序采用单实例运行机制，同一时间只能运行一个实例。
3. 用户数据存储在 %APPDATA%\\ue_toolkit\\user_data\\ 目录下。
4. AI 助手需要配置 LLM 供应商：API 模式需填写 API Key 和 URL；Ollama 模式需先安装并启动 Ollama 服务。
5. 资产库的资产路径请确保指向有效的本地目录。
6. 我的工程模块首次使用时扫描可能需要一些时间。
7. 关闭窗口时可选择最小化到托盘或退出程序，可记住选择。
"""


class ToolDefinition:
    """工具定义"""
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        function: Callable,
        requires_confirmation: bool = False
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema 格式
        self.function = function
        self.requires_confirmation = requires_confirmation  # v0.2: 权限声明


class ToolsRegistry:
    """
    工具注册表
    
    v0.2: 注册和管理所有只读工具
    v0.3: 扩展支持受控写入工具
    """
    
    def __init__(self, asset_reader=None, config_reader=None, log_analyzer=None, document_reader=None, asset_importer=None):
        """
        初始化工具注册表
        
        Args:
            asset_reader: 资产读取器
            config_reader: 配置读取器
            log_analyzer: 日志分析器
            document_reader: 文档读取器
            asset_importer: 资产导入器（测试功能）
        """
        self.logger = logger
        self.asset_reader = asset_reader
        self.config_reader = config_reader
        self.log_analyzer = log_analyzer
        self.document_reader = document_reader
        self.asset_importer = asset_importer
        
        # 初始化UE工具HTTP客户端
        from modules.ai_assistant.clients.ue_tool_client import UEToolClient
        
        # 使用 Remote Control API (HTTP)
        ue_base_url = "http://127.0.0.1:30010"
        
        # TODO: 未来可以从配置管理器读取这些设置
        # if config_reader:
        #     ue_base_url = config_reader.get('ue_remote_control_url', 'http://127.0.0.1:30010')
        
        self.ue_client = UEToolClient(base_url=ue_base_url)
        self.logger.info(f"UE HTTP客户端已初始化 (目标: {ue_base_url})")
        
        # 初始化 Feature Gate 权限控制系统
        from core.security.license_manager import LicenseManager
        from core.security.feature_gate import FeatureGate
        
        self.license_manager = LicenseManager()
        self.feature_gate = FeatureGate(self.license_manager)
        self.logger.info("Feature Gate 权限控制系统已初始化")
        
        # 工具注册表
        self.tools: Dict[str, ToolDefinition] = {}
        
        # 注册所有只读工具
        self._register_readonly_tools()
        
        # 注册测试功能工具
        self._register_experimental_tools()
        
        # 注册 Blueprint Extractor 工具（免费 + 付费）
        self._register_blueprint_extractor_tools()
        
        self.logger.info(f"工具注册表初始化完成，共注册 {len(self.tools)} 个工具")
    
    def _register_readonly_tools(self):
        """注册所有只读工具"""
        
        # 1. 搜索资产
        self.register_tool(ToolDefinition(
            name="search_assets",
            description="""获取资产库中的资产列表。
            
重要规则：
- 当用户询问"有哪些资产"、"推荐资产"、"适合的资产"时，必须不带参数调用此工具获取完整资产列表
- 获取列表后，根据用户需求从列表中推荐合适的资产
- 只有当用户明确提供了具体的资产名称或关键词时，才传入 keyword 参数进行精确搜索
- 不要自己猜测关键词进行搜索，应该先获取完整列表再推荐""",
            parameters={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "精确搜索关键词（仅当用户明确提供资产名称时使用）。留空则返回所有资产列表"
                    }
                },
                "required": []  # keyword是可选的
            },
            function=self._tool_search_assets,
            requires_confirmation=False  # 只读，无需确认
        ))
        
        # 2. 查询资产详情
        self.register_tool(ToolDefinition(
            name="query_asset_detail",
            description="获取特定资产的详细信息（路径、文件列表、大小等）",
            parameters={
                "type": "object",
                "properties": {
                    "asset_name": {
                        "type": "string",
                        "description": "资产名称"
                    }
                },
                "required": ["asset_name"]
            },
            function=self._tool_query_asset_detail,
            requires_confirmation=False
        ))
        
        # 2.5. 推荐资产（在聊天中显示资产卡片）
        self.register_tool(ToolDefinition(
            name="recommend_assets",
            description="向用户推荐资产并在聊天界面中显示资产卡片。当用户询问意见（如'我想做个恐怖游戏'、'做个跑酷游戏'）时，AI 可以推荐合适的资产并调用此工具在聊天中展示资产卡片。资产卡片支持预览和导入功能。",
            parameters={
                "type": "object",
                "properties": {
                    "asset_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要推荐的资产名称列表（精确匹配资产库中的资产名称）"
                    },
                    "reason": {
                        "type": "string",
                        "description": "推荐理由（简短说明为什么推荐这些资产）"
                    }
                },
                "required": ["asset_names", "reason"]
            },
            function=self._tool_recommend_assets,
            requires_confirmation=False
        ))
        
        # 3. 搜索配置模板
        self.register_tool(ToolDefinition(
            name="search_configs",
            description="搜索UE项目配置模板",
            parameters={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["keyword"]
            },
            function=self._tool_search_configs,
            requires_confirmation=False
        ))
        
        # 4. 对比配置
        self.register_tool(ToolDefinition(
            name="diff_config",
            description="对比两个配置模板的差异",
            parameters={
                "type": "object",
                "properties": {
                    "config1": {"type": "string", "description": "第一个配置名称"},
                    "config2": {"type": "string", "description": "第二个配置名称"}
                },
                "required": ["config1", "config2"]
            },
            function=self._tool_diff_config,
            requires_confirmation=False
        ))
        
        # 5. 查询工具箱功能说明
        self.register_tool(ToolDefinition(
            name="query_toolkit_help",
            description="查询 UE Toolkit（虚幻引擎工具箱）的功能说明和操作指南。当用户询问工具箱有哪些功能、某个模块怎么用、操作注意事项等问题时调用此工具。支持按关键词搜索特定功能，也可以传入 section 获取指定章节内容。",
            parameters={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（可选），如 '资产库'、'AI助手'、'主题切换'、'注意事项' 等"
                    },
                    "section": {
                        "type": "string",
                        "description": "指定章节名（可选），如 '我的工程'、'资产库'、'AI 助手'、'工程配置'、'作者推荐'、'通用功能'、'操作注意事项'"
                    }
                },
                "required": []
            },
            function=self._tool_query_toolkit_help,
            requires_confirmation=False
        ))

        # 日志搜索和文档搜索功能已禁用
        # # 5. 搜索日志
        # self.register_tool(ToolDefinition(
        #     name="search_logs",
        #     description="搜索日志文件中的特定内容",
        #     parameters={
        #         "type": "object",
        #         "properties": {
        #             "keyword": {
        #                 "type": "string",
        #                 "description": "搜索关键词"
        #             }
        #         },
        #         "required": ["keyword"]
        #     },
        #     function=self._tool_search_logs,
        #     requires_confirmation=False
        # ))
        
        # # 6. 搜索文档
        # self.register_tool(ToolDefinition(
        #     name="search_docs",
        #     description="搜索项目文档和使用说明",
        #     parameters={
        #         "type": "object",
        #         "properties": {
        #             "keyword": {
        #                 "type": "string",
        #                 "description": "搜索关键词"
        #             }
        #         },
        #         "required": ["keyword"]
        #     },
        #     function=self._tool_search_docs,
        #     requires_confirmation=False
        # ))
    
    def register_tool(self, tool: ToolDefinition):
        """注册工具"""
        self.tools[tool.name] = tool
        self.logger.debug(f"注册工具: {tool.name} (需要确认: {tool.requires_confirmation})")
    
    def openai_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        返回 OpenAI tools 描述格式
        
        兼容 ChatGPT Function Calling 规范：
        tools=[{type:'function', function:{name, description, parameters}}]
        
        Returns:
            List[Dict]: OpenAI tools 格式的工具列表
        """
        schemas = []
        
        for tool_name, tool_def in self.tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters": tool_def.parameters
                }
            })
        
        return schemas
    
    def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调度工具执行
        
        增强功能：
        1. 参数验证（JSON Schema）
        2. 权限检查（通过工具的 requires_confirmation 标志）
        3. 错误处理和友好的错误消息
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            Dict: 工具执行结果 {success, result, error, locked, tier}
        """
        try:
            # 1. 检查工具是否存在
            if tool_name not in self.tools:
                return {
                    "success": False,
                    "error": f"未知工具: {tool_name}"
                }
            
            tool = self.tools[tool_name]
            
            # 2. 验证参数（JSON Schema）
            validation_error = self._validate_parameters(tool, arguments)
            if validation_error:
                return {
                    "success": False,
                    "error": validation_error
                }
            
            self.logger.info(f"执行工具: {tool_name}, 参数: {arguments}")
            
            # 3. 调用工具函数
            result = tool.function(**arguments)
            
            # 4. 处理返回结果
            # 如果工具返回的是 dict 且包含 status 字段（UE 工具的格式）
            if isinstance(result, dict) and "status" in result:
                # 转换为统一格式
                if result["status"] == "success":
                    return {
                        "success": True,
                        "result": result.get("data", result),
                        "tool_name": tool_name,
                        "requires_confirmation": tool.requires_confirmation
                    }
                elif result["status"] == "error":
                    # 检查是否是权限错误
                    if result.get("locked"):
                        return {
                            "success": False,
                            "error": result.get("message", "权限错误"),
                            "locked": result.get("locked", False),
                            "tier": result.get("tier", "unknown"),
                            "tool_name": tool_name
                        }
                    else:
                        # 普通执行错误，转发插件的错误消息
                        return {
                            "success": False,
                            "error": self._format_plugin_error(tool_name, result.get("message", "未知错误")),
                            "tool_name": tool_name
                        }
            
            # 5. 其他类型的返回值（字符串等）
            return {
                "success": True,
                "result": result,
                "tool_name": tool_name,
                "requires_confirmation": tool.requires_confirmation
            }
        
        except Exception as e:
            self.logger.error(f"工具执行失败 {tool_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"工具执行异常: {str(e)}",
                "tool_name": tool_name
            }
    
    def _validate_parameters(self, tool: ToolDefinition, arguments: Dict[str, Any]) -> Optional[str]:
        """
        验证工具参数是否符合 JSON Schema
        
        Args:
            tool: 工具定义
            arguments: 工具参数
            
        Returns:
            错误消息（如果验证失败），None（如果验证通过）
        """
        try:
            schema = tool.parameters
            
            # 检查必需参数
            required_params = schema.get("required", [])
            for param in required_params:
                if param not in arguments:
                    # 生成友好的错误消息，显示正确格式
                    example = self._generate_parameter_example(schema, param)
                    return (
                        f"参数错误：缺少必需参数 '{param}'。\n"
                        f"正确格式示例：{example}"
                    )
            
            # 检查参数类型（简单验证）
            properties = schema.get("properties", {})
            for param_name, param_value in arguments.items():
                if param_name in properties:
                    expected_type = properties[param_name].get("type")
                    if expected_type:
                        if not self._check_type(param_value, expected_type):
                            return (
                                f"参数错误：参数 '{param_name}' 的类型不正确。\n"
                                f"期望类型：{expected_type}，实际类型：{type(param_value).__name__}"
                            )
            
            return None  # 验证通过
            
        except Exception as e:
            self.logger.warning(f"参数验证异常: {e}")
            return None  # 验证异常时不阻止执行
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值的类型是否匹配"""
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # 未知类型，跳过检查
        
        return isinstance(value, expected_python_type)
    
    def _generate_parameter_example(self, schema: Dict[str, Any], param_name: str) -> str:
        """生成参数示例"""
        properties = schema.get("properties", {})
        if param_name not in properties:
            return f'{{"{param_name}": "..."}}'
        
        param_schema = properties[param_name]
        param_type = param_schema.get("type", "string")
        description = param_schema.get("description", "")
        
        # 生成示例值
        if param_type == "string":
            example_value = description.split("如 ")[-1].split("）")[0] if "如 " in description else "example_value"
            return f'{{"{param_name}": "{example_value}"}}'
        elif param_type == "number" or param_type == "integer":
            return f'{{"{param_name}": 0}}'
        elif param_type == "boolean":
            return f'{{"{param_name}": true}}'
        elif param_type == "array":
            return f'{{"{param_name}": []}}'
        elif param_type == "object":
            return f'{{"{param_name}": {{}}}}'
        else:
            return f'{{"{param_name}": "..."}}'
    
    def _format_plugin_error(self, tool_name: str, error_message: str) -> str:
        """
        格式化插件错误消息，使其更友好
        
        Args:
            tool_name: 工具名称
            error_message: 原始错误消息
            
        Returns:
            格式化后的错误消息
        """
        # 检查是否是连接错误
        if "无法连接" in error_message or "连接被拒绝" in error_message or "连接失败" in error_message:
            return (
                f"无法连接到虚幻引擎编辑器。\n\n"
                f"请确保：\n"
                f"1. UE 编辑器正在运行\n"
                f"2. Blueprint Extractor 插件已启用\n"
                f"3. HTTP 服务器正在监听端口\n\n"
                f"原始错误：{error_message}"
            )
        
        # 检查是否是资产未找到错误
        if "not found" in error_message.lower() or "未找到" in error_message:
            return (
                f"资产未找到。\n\n"
                f"请检查资产路径是否正确，确保资产存在于 UE 项目中。\n\n"
                f"原始错误：{error_message}"
            )
        
        # 其他错误，直接转发
        return f"工具 '{tool_name}' 执行失败：{error_message}"
    
    def cleanup(self):
        """清理资源，关闭连接"""
        try:
            if hasattr(self, 'ue_client') and self.ue_client:
                self.ue_client.close()
                self.logger.info("UE RPC客户端连接已关闭")
        except Exception as e:
            self.logger.warning(f"清理UE客户端时出错: {e}")
    
    # ========== 工具实现函数 ==========
    
    def _tool_search_assets(self, keyword: str = "") -> str:
        """搜索资产工具实现"""
        if self.asset_reader:
            # 如果没有关键词，返回所有资产列表
            if not keyword or not keyword.strip():
                return self.asset_reader.get_all_assets_summary()
            return self.asset_reader.search_assets(keyword)
        return "[错误] 资产读取器未初始化"
    
    def _tool_query_asset_detail(self, asset_name: str) -> str:
        """查询资产详情工具实现"""
        if self.asset_reader:
            return self.asset_reader.get_asset_details(asset_name)
        return "[错误] 资产读取器未初始化"
    
    def _tool_recommend_assets(self, asset_names: list, reason: str) -> str:
        """推荐资产工具实现
        
        返回特殊格式的字符串，包含资产 ID 列表，供 UI 层解析并渲染资产卡片
        """
        if not self.asset_reader:
            return "[错误] 资产读取器未初始化"
        
        # 调用 asset_reader 的 recommend_assets 方法
        result = self.asset_reader.recommend_assets(asset_names)
        
        if not result["success"]:
            return f"[推荐失败] {result['message']}"
        
        # 返回特殊格式的字符串，包含资产 ID 列表
        # 格式：[RECOMMEND_ASSETS]reason|asset_id1,asset_id2,asset_id3[/RECOMMEND_ASSETS]
        asset_ids_str = ",".join(result["asset_ids"])
        return f"[RECOMMEND_ASSETS]{reason}|{asset_ids_str}[/RECOMMEND_ASSETS]\n\n{result['message']}"
    
    def _tool_search_configs(self, keyword: str) -> str:
        """搜索配置工具实现"""
        if self.config_reader:
            return self.config_reader.search_configs(keyword)
        return "[错误] 配置读取器未初始化"
    
    def _tool_diff_config(self, config1: str, config2: str) -> str:
        """配置对比工具实现（暂时返回占位符）"""
        # TODO: 实现配置对比逻辑
        return f"[配置对比] {config1} vs {config2}\n（功能待实现）"
    
    def _tool_search_logs(self, keyword: str) -> str:
        """搜索日志工具实现"""
        if self.log_analyzer:
            return self.log_analyzer.search_in_logs(keyword)
        return "[错误] 日志分析器未初始化"
    
    def _tool_search_docs(self, keyword: str) -> str:
        """搜索文档工具实现"""
        if self.document_reader:
            return self.document_reader.search_in_documents(keyword)
        return "[错误] 文档读取器未初始化"

    def _tool_query_toolkit_help(self, keyword: str = "", section: str = "") -> str:
        """查询工具箱功能说明工具实现

        优先从 README.md 文件读取（开发环境），
        文件不存在时使用内置文档（打包后的 exe 环境）。
        """
        try:
            content = self._load_toolkit_doc()

            # 按章节提取
            if section:
                return self._extract_section(content, section)

            # 按关键词搜索
            if keyword:
                return self._search_in_readme(content, keyword)

            # 都没传，返回目录概览（不返回全文，节省 token）
            lines = content.split("\n")
            toc_lines = [line for line in lines if line.startswith("#")]
            return "📖 **UE Toolkit 功能文档目录**\n\n" + "\n".join(toc_lines) + \
                   "\n\n💡 提示：可以通过 section 参数获取具体章节内容，或通过 keyword 搜索。"

        except Exception as e:
            self.logger.error(f"查询工具箱帮助失败: {e}", exc_info=True)
            return f"[错误] 查询工具箱帮助时出错: {str(e)}"

    @staticmethod
    def _load_toolkit_doc() -> str:
        """加载工具箱功能文档

        优先读取 README.md 文件，不存在则使用内置文档。
        读取后过滤掉开发实现细节（技术栈、架构等），防止 AI 泄露。
        """
        from pathlib import Path
        readme_path = Path(__file__).parent.parent.parent.parent / "README.md"

        if readme_path.exists():
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()
            return ToolsRegistry._filter_dev_details(content)

        # 打包环境 fallback：内置精简文档（已预先去除开发细节）
        return _BUILTIN_TOOLKIT_DOC

    @staticmethod
    def _filter_dev_details(content: str) -> str:
        """过滤掉文档中的开发实现细节，防止 AI 泄露技术栈信息"""
        filtered_lines = []
        skip_section = False

        for line in content.split("\n"):
            # 跳过包含技术栈关键词的行
            line_lower = line.lower()
            if any(kw in line_lower for kw in [
                "技术栈", "python", "pyqt", "pyinstaller", "pip install",
                "从源码运行", "打包为安装包", "requirements.txt",
                "inno setup", "方式二"
            ]):
                continue

            # 跳过"安装与运行"整个章节（包含技术细节）
            if line.startswith("#") and "安装与运行" in line:
                skip_section = True
                continue
            if skip_section:
                if line.startswith("#") and "安装与运行" not in line:
                    skip_section = False
                else:
                    continue

            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    @staticmethod
    def _extract_section(content: str, section_name: str) -> str:
        """从 Markdown 内容中提取指定章节"""
        lines = content.split("\n")
        result = []
        capturing = False
        section_level = 0

        for line in lines:
            if line.startswith("#"):
                # 计算标题级别
                level = len(line) - len(line.lstrip("#"))
                title_text = line.lstrip("#").strip()

                if section_name.lower() in title_text.lower():
                    capturing = True
                    section_level = level
                    result.append(line)
                    continue
                elif capturing and level <= section_level:
                    # 遇到同级或更高级标题，停止
                    break

            if capturing:
                result.append(line)

        if not result:
            return f"[提示] 未找到章节「{section_name}」，请检查章节名是否正确。"

        return "\n".join(result)

    @staticmethod
    def _search_in_readme(content: str, keyword: str) -> str:
        """在 README 中搜索关键词，返回相关段落"""
        keyword_lower = keyword.lower()
        lines = content.split("\n")
        matched_sections = []
        current_section_title = ""
        current_section_lines = []

        for line in lines:
            if line.startswith("#"):
                # 保存上一个章节（如果匹配）
                if current_section_lines and any(
                    keyword_lower in l.lower() for l in current_section_lines
                ):
                    matched_sections.append(
                        current_section_title + "\n" + "\n".join(current_section_lines)
                    )
                current_section_title = line
                current_section_lines = []
            else:
                current_section_lines.append(line)

        # 检查最后一个章节
        if current_section_lines and any(
            keyword_lower in l.lower() for l in current_section_lines
        ):
            matched_sections.append(
                current_section_title + "\n" + "\n".join(current_section_lines)
            )

        if not matched_sections:
            return f"[提示] 在功能文档中未找到与「{keyword}」相关的内容。"

        return f"🔍 找到 {len(matched_sections)} 个相关章节：\n\n" + \
               "\n\n---\n\n".join(matched_sections[:3])  # 最多返回3个章节
    
    def _register_experimental_tools(self):
        """注册实验性功能工具（测试版）"""
        
        # 资产导入功能已禁用
        # # 1. 导入资产到UE项目
        # self.register_tool(ToolDefinition(
        #     name="import_asset_to_ue",
        #     description="将资产自动导入到当前正在运行的虚幻引擎项目（测试功能）。此工具会自动检测正在运行的UE项目，无需用户提供路径。",
        #     parameters={
        #         "type": "object",
        #         "properties": {
        #             "asset_name": {
        #                 "type": "string",
        #                 "description": "要导入的资产名称"
        #             }
        #         },
        #         "required": ["asset_name"]
        #     },
        #     function=self._tool_import_asset,
        #     requires_confirmation=False  # 测试功能，简化流程
        # ))
        
        # # 2. 列出可导入的资产
        # self.register_tool(ToolDefinition(
        #     name="list_importable_assets",
        #     description="列出所有可以导入到UE项目的资产",
        #     parameters={
        #         "type": "object",
        #         "properties": {}
        #     },
        #     function=self._tool_list_importable_assets,
        #     requires_confirmation=False
        # ))
        
        pass  # 占位符，保持方法结构
        
    
    def _tool_import_asset(self, asset_name: str) -> str:
        """导入资产工具实现（自动检测正在运行的UE项目）"""
        if self.asset_importer:
            result = self.asset_importer.import_asset_to_ue(asset_name)
            return result.get('message', '[错误] 导入失败')
        return "[错误] 资产导入器未初始化"
    
    def _tool_list_importable_assets(self) -> str:
        """列出可导入资产工具实现"""
        if self.asset_importer:
            return self.asset_importer.list_importable_assets()
        return "[错误] 资产导入器未初始化"
    
    def _tool_list_themes(self) -> str:
        """列出主题工具实现"""
        if self.theme_generator:
            return self.theme_generator.list_available_themes()
        return "[错误] 主题生成器未初始化"
    
    def _register_controlled_tools(self):
        """
        v0.3 新增：注册受控写入工具
        
        所有受控工具标记 requires_confirmation=True
        """
        # 1. 导出配置模板
        self.register_tool(ToolDefinition(
            name="export_config_template",
            description="导出UE配置模板到指定路径（需要确认）",
            parameters={
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "description": "配置模板名称"
                    },
                    "export_path": {
                        "type": "string",
                        "description": "导出路径"
                    }
                },
                "required": ["template_name", "export_path"]
            },
            function=self._tool_export_config_template,
            requires_confirmation=True  # 需要确认
        ))
        
        # 2. 批量重命名预览
        self.register_tool(ToolDefinition(
            name="batch_rename_preview",
            description="批量重命名资产（需要确认）",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "匹配模式"
                    },
                    "replacement": {
                        "type": "string",
                        "description": "替换文本"
                    },
                    "asset_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "资产ID列表"
                    }
                },
                "required": ["pattern", "replacement", "asset_ids"]
            },
            function=self._tool_batch_rename_preview,
            requires_confirmation=True  # 需要确认
        ))
    
    def _tool_export_config_template(self, template_name: str, export_path: str) -> str:
        """导出配置模板工具实现（返回预览）"""
        if self.controlled_tools:
            result = self.controlled_tools.export_config_template(template_name, export_path)
            return result.get('preview', '[错误] 无预览')
        return "[错误] 受控工具集未初始化"
    
    def _tool_batch_rename_preview(self, pattern: str, replacement: str, asset_ids: list) -> str:
        """批量重命名工具实现（返回预览）"""
        if self.controlled_tools:
            result = self.controlled_tools.batch_rename_preview(pattern, replacement, asset_ids)
            return result.get('preview', '[错误] 无预览')
        return "[错误] 受控工具集未初始化"
    
    def _register_blueprint_extractor_tools(self):
        """
        注册 Blueprint Extractor 工具到注册表
        
        包含：
        - 18 个免费工具（只读操作）
        - 10+ 个付费工具（创建/修改操作）
        
        所有工具委托给 _execute_ue_python_tool() 方法，
        该方法会通过 Feature Gate 检查权限。
        """
        
        # ========== 免费工具（18 个只读工具）==========
        
        # 1. ExtractBlueprint - 提取蓝图结构
        self.register_tool(ToolDefinition(
            name="ExtractBlueprint",
            description="提取指定路径蓝图的完整结构信息，包括节点、变量、函数、组件等。用于分析蓝图逻辑和结构。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "蓝图资产路径，如 /Game/Blueprints/BP_Character"
                    },
                    "Scope": {
                        "type": "string",
                        "description": "提取范围：Minimal（最小）| Compact（紧凑，默认）| Full（完整）",
                        "enum": ["Minimal", "Compact", "Full"]
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractBlueprint", **kwargs),
            requires_confirmation=False
        ))
        
        # 2. ExtractActiveBlueprint - 提取当前活动蓝图
        self.register_tool(ToolDefinition(
            name="ExtractActiveBlueprint",
            description="提取当前在 UE 编辑器中打开的蓝图的结构信息。这是 GetActiveBlueprint + ExtractBlueprint 的便捷组合。",
            parameters={
                "type": "object",
                "properties": {
                    "Scope": {
                        "type": "string",
                        "description": "提取范围：Minimal（最小）| Compact（紧凑，默认）| Full（完整）",
                        "enum": ["Minimal", "Compact", "Full"]
                    }
                },
                "required": []
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractActiveBlueprint", **kwargs),
            requires_confirmation=False
        ))
        
        # 3. GetActiveBlueprint - 获取当前活动蓝图路径
        self.register_tool(ToolDefinition(
            name="GetActiveBlueprint",
            description="获取当前在 UE 编辑器中激活（打开）的蓝图信息，返回蓝图的资产路径、名称、父类等。",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            function=lambda **kwargs: self._execute_ue_python_tool("GetActiveBlueprint", **kwargs),
            requires_confirmation=False
        ))
        
        # 4. ExtractWidgetBlueprint - 提取 UMG Widget
        self.register_tool(ToolDefinition(
            name="ExtractWidgetBlueprint",
            description="提取 UMG Widget 蓝图的结构信息，包括控件树、绑定、动画等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "Widget 蓝图资产路径，如 /Game/UI/WBP_MainMenu"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractWidgetBlueprint", **kwargs),
            requires_confirmation=False
        ))
        
        # 5. ExtractMaterial - 提取材质
        self.register_tool(ToolDefinition(
            name="ExtractMaterial",
            description="提取材质的结构信息，包括材质节点、参数、纹理等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "材质资产路径，如 /Game/Materials/M_Character"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractMaterial", **kwargs),
            requires_confirmation=False
        ))
        
        # 6. SearchAssets - 搜索资产
        self.register_tool(ToolDefinition(
            name="SearchAssets",
            description="在 UE 项目中搜索资产，支持按名称、类型、路径等条件搜索。",
            parameters={
                "type": "object",
                "properties": {
                    "Keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "AssetClass": {
                        "type": "string",
                        "description": "资产类型过滤，如 Blueprint、Material、Texture 等（可选）"
                    }
                },
                "required": ["Keyword"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("SearchAssets", **kwargs),
            requires_confirmation=False
        ))
        
        # 7. ListAssets - 列出资产
        self.register_tool(ToolDefinition(
            name="ListAssets",
            description="列出指定目录下的所有资产。",
            parameters={
                "type": "object",
                "properties": {
                    "Path": {
                        "type": "string",
                        "description": "资产目录路径，如 /Game/Blueprints"
                    },
                    "Recursive": {
                        "type": "boolean",
                        "description": "是否递归列出子目录（可选，默认 false）"
                    }
                },
                "required": ["Path"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ListAssets", **kwargs),
            requires_confirmation=False
        ))
        
        # 8. GetEditorContext - 获取编辑器上下文
        self.register_tool(ToolDefinition(
            name="GetEditorContext",
            description="获取当前 UE 编辑器的上下文信息，包括当前打开的关卡、选中的 Actor 等。",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            function=lambda **kwargs: self._execute_ue_python_tool("GetEditorContext", **kwargs),
            requires_confirmation=False
        ))
        
        # 9. ExtractDataTable - 提取数据表
        self.register_tool(ToolDefinition(
            name="ExtractDataTable",
            description="提取数据表的结构和内容，包括列定义和所有行数据。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "数据表资产路径，如 /Game/Data/DT_Items"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractDataTable", **kwargs),
            requires_confirmation=False
        ))
        
        # 10. ExtractEnum - 提取枚举
        self.register_tool(ToolDefinition(
            name="ExtractEnum",
            description="提取枚举类型的定义，包括所有枚举值。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "枚举资产路径，如 /Game/Enums/E_CharacterState"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractEnum", **kwargs),
            requires_confirmation=False
        ))
        
        # 11. ExtractStruct - 提取结构体
        self.register_tool(ToolDefinition(
            name="ExtractStruct",
            description="提取结构体的定义，包括所有成员变量和类型。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "结构体资产路径，如 /Game/Structs/S_PlayerData"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractStruct", **kwargs),
            requires_confirmation=False
        ))
        
        # 12. ExtractAnimBlueprint - 提取动画蓝图
        self.register_tool(ToolDefinition(
            name="ExtractAnimBlueprint",
            description="提取动画蓝图的结构信息，包括状态机、动画节点等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "动画蓝图资产路径，如 /Game/Characters/ABP_Character"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractAnimBlueprint", **kwargs),
            requires_confirmation=False
        ))
        
        # 13. ExtractBehaviorTree - 提取行为树
        self.register_tool(ToolDefinition(
            name="ExtractBehaviorTree",
            description="提取 AI 行为树的结构信息，包括任务节点、装饰器、服务等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "行为树资产路径，如 /Game/AI/BT_Enemy"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractBehaviorTree", **kwargs),
            requires_confirmation=False
        ))
        
        # 14. ExtractBlackboard - 提取黑板
        self.register_tool(ToolDefinition(
            name="ExtractBlackboard",
            description="提取 AI 黑板的结构信息，包括所有键值定义。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "黑板资产路径，如 /Game/AI/BB_Enemy"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractBlackboard", **kwargs),
            requires_confirmation=False
        ))
        
        # 15. ExtractStateMachine - 提取状态机
        self.register_tool(ToolDefinition(
            name="ExtractStateMachine",
            description="提取状态机的结构信息，包括状态、转换条件等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "状态机资产路径"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractStateMachine", **kwargs),
            requires_confirmation=False
        ))
        
        # 16. ExtractAnimMontage - 提取动画蒙太奇
        self.register_tool(ToolDefinition(
            name="ExtractAnimMontage",
            description="提取动画蒙太奇的结构信息，包括片段、通知等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "动画蒙太奇资产路径，如 /Game/Animations/AM_Attack"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractAnimMontage", **kwargs),
            requires_confirmation=False
        ))
        
        # 17. ExtractAnimSequence - 提取动画序列
        self.register_tool(ToolDefinition(
            name="ExtractAnimSequence",
            description="提取动画序列的信息，包括帧数、时长、通知等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "动画序列资产路径，如 /Game/Animations/AS_Walk"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractAnimSequence", **kwargs),
            requires_confirmation=False
        ))
        
        # 18. ExtractSoundCue - 提取声音提示
        self.register_tool(ToolDefinition(
            name="ExtractSoundCue",
            description="提取声音提示的结构信息，包括声音节点、衰减设置等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "声音提示资产路径，如 /Game/Audio/SC_Footstep"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractSoundCue", **kwargs),
            requires_confirmation=False
        ))
        
        self.logger.info("已注册 18 个免费 Blueprint Extractor 工具")
        
        # ========== 付费工具（10+ 个创建/修改工具）==========
        
        # 1. CreateBlueprint - 创建新蓝图
        self.register_tool(ToolDefinition(
            name="CreateBlueprint",
            description="创建新的蓝图资产。需要指定资产路径和父类。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "新蓝图的保存路径，如 /Game/Blueprints/BP_MyActor"
                    },
                    "ParentClass": {
                        "type": "string",
                        "description": "父类路径，如 /Script/Engine.Actor"
                    },
                    "GraphDSL": {
                        "type": "string",
                        "description": "图表 DSL（可选），用于快速定义节点"
                    }
                },
                "required": ["AssetPath", "ParentClass"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("CreateBlueprint", **kwargs),
            requires_confirmation=True  # 创建操作需要确认
        ))
        
        # 2. ModifyBlueprintMembers - 修改蓝图成员
        self.register_tool(ToolDefinition(
            name="ModifyBlueprintMembers",
            description="修改蓝图的成员（变量、函数等）。支持添加、删除、重命名等操作。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "蓝图资产路径"
                    },
                    "Operation": {
                        "type": "string",
                        "description": "操作类型：add_variable | remove_variable | rename_variable | add_function | remove_function",
                        "enum": ["add_variable", "remove_variable", "rename_variable", "add_function", "remove_function"]
                    },
                    "PayloadJson": {
                        "type": "string",
                        "description": "操作参数（JSON 字符串），如 {\"name\": \"Speed\", \"type\": \"float\"}"
                    }
                },
                "required": ["AssetPath", "Operation", "PayloadJson"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ModifyBlueprintMembers", **kwargs),
            requires_confirmation=True
        ))
        
        # 3. AddBlueprintVariable - 添加蓝图变量
        self.register_tool(ToolDefinition(
            name="AddBlueprintVariable",
            description="向蓝图添加新变量。支持的类型：bool, int, float, double, string, name, text, vector, rotator, transform, color 等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "蓝图资产路径"
                    },
                    "VariableName": {
                        "type": "string",
                        "description": "变量名称"
                    },
                    "VariableType": {
                        "type": "string",
                        "description": "变量类型：bool | int | float | double | string | name | text | vector | rotator | transform | color"
                    },
                    "DefaultValue": {
                        "type": "string",
                        "description": "默认值（可选）"
                    }
                },
                "required": ["AssetPath", "VariableName", "VariableType"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("AddBlueprintVariable", **kwargs),
            requires_confirmation=True
        ))
        
        # 4. AddBlueprintFunction - 添加蓝图函数
        self.register_tool(ToolDefinition(
            name="AddBlueprintFunction",
            description="向蓝图添加新函数。可以指定函数名称、输入参数、输出参数等。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "蓝图资产路径"
                    },
                    "FunctionName": {
                        "type": "string",
                        "description": "函数名称"
                    },
                    "Inputs": {
                        "type": "string",
                        "description": "输入参数（JSON 数组字符串，可选），如 '[{\"name\": \"Value\", \"type\": \"float\"}]'"
                    },
                    "Outputs": {
                        "type": "string",
                        "description": "输出参数（JSON 数组字符串，可选），如 '[{\"name\": \"Result\", \"type\": \"bool\"}]'"
                    }
                },
                "required": ["AssetPath", "FunctionName"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("AddBlueprintFunction", **kwargs),
            requires_confirmation=True
        ))
        
        # 5. CreateWidgetBlueprint - 创建 Widget 蓝图
        self.register_tool(ToolDefinition(
            name="CreateWidgetBlueprint",
            description="创建新的 UMG Widget 蓝图。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "Widget 蓝图的保存路径，如 /Game/UI/WBP_MyWidget"
                    },
                    "ParentClass": {
                        "type": "string",
                        "description": "父类路径（可选），默认为 UserWidget"
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("CreateWidgetBlueprint", **kwargs),
            requires_confirmation=True
        ))
        
        # 6. ModifyWidget - 修改 Widget
        self.register_tool(ToolDefinition(
            name="ModifyWidget",
            description="修改 UMG Widget 的结构，支持添加、删除、修改控件等操作。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "Widget 蓝图资产路径"
                    },
                    "Operation": {
                        "type": "string",
                        "description": "操作类型：add_widget | remove_widget | set_property",
                        "enum": ["add_widget", "remove_widget", "set_property"]
                    },
                    "PayloadJson": {
                        "type": "string",
                        "description": "操作参数（JSON 字符串）"
                    }
                },
                "required": ["AssetPath", "Operation", "PayloadJson"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ModifyWidget", **kwargs),
            requires_confirmation=True
        ))
        
        # 7. SaveAssets - 保存资产
        self.register_tool(ToolDefinition(
            name="SaveAssets",
            description="保存一个或多个资产到磁盘。所有修改操作不会自动保存，必须显式调用此工具。",
            parameters={
                "type": "object",
                "properties": {
                    "AssetPaths": {
                        "type": "string",
                        "description": "资产路径列表（JSON 数组字符串），如 '[\"/Game/BP1\", \"/Game/BP2\"]'"
                    }
                },
                "required": ["AssetPaths"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("SaveAssets", **kwargs),
            requires_confirmation=True
        ))
        
        # 8. ImportTexture - 导入纹理
        self.register_tool(ToolDefinition(
            name="ImportTexture",
            description="从本地文件系统导入纹理到 UE 项目。",
            parameters={
                "type": "object",
                "properties": {
                    "FilePath": {
                        "type": "string",
                        "description": "本地纹理文件路径"
                    },
                    "DestinationPath": {
                        "type": "string",
                        "description": "UE 项目中的目标路径，如 /Game/Textures/T_MyTexture"
                    }
                },
                "required": ["FilePath", "DestinationPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ImportTexture", **kwargs),
            requires_confirmation=True
        ))
        
        # 9. StartPIE - 启动 PIE（Play In Editor）
        self.register_tool(ToolDefinition(
            name="StartPIE",
            description="启动 Play In Editor（PIE）模式，用于测试游戏逻辑。",
            parameters={
                "type": "object",
                "properties": {
                    "Mode": {
                        "type": "string",
                        "description": "PIE 模式：Viewport | NewWindow | Standalone（可选，默认 Viewport）",
                        "enum": ["Viewport", "NewWindow", "Standalone"]
                    }
                },
                "required": []
            },
            function=lambda **kwargs: self._execute_ue_python_tool("StartPIE", **kwargs),
            requires_confirmation=False  # PIE 控制不需要确认
        ))
        
        # 10. StopPIE - 停止 PIE
        self.register_tool(ToolDefinition(
            name="StopPIE",
            description="停止当前运行的 Play In Editor（PIE）会话。",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            function=lambda **kwargs: self._execute_ue_python_tool("StopPIE", **kwargs),
            requires_confirmation=False
        ))
        
        self.logger.info("已注册 10 个付费 Blueprint Extractor 工具")
    
    def _execute_ue_python_tool(self, tool_name: str, **kwargs) -> dict:
        """
        通过HTTP客户端执行虚幻引擎编辑器内的函数。
        这是 Function Calling 调用虚幻引擎工具的桥梁。
        
        集成 Feature Gate 权限控制：
        1. 检查工具权限
        2. 如果被锁定，返回权限错误
        3. 如果允许，调用 UE Tool Client 执行工具
        4. 返回统一格式的结果
        
        Args:
            tool_name: UE工具名称（BlueprintExtractorSubsystem的函数名）
            **kwargs: 工具参数
            
        Returns:
            dict: 执行结果字典
                成功: {"status": "success", "data": {...}}
                权限错误: {"status": "error", "message": "...", "locked": true, "tier": "pro"}
                执行错误: {"status": "error", "message": "..."}
        """
        try:
            # 1. 检查工具权限（通过 Feature Gate）
            permission_result = self.feature_gate.check_tool_permission(tool_name)
            
            # 2. 如果权限被拒绝，返回权限错误
            if not permission_result["allowed"]:
                self.logger.warning(f"工具 '{tool_name}' 权限被拒绝: {permission_result['message']}")
                return {
                    "status": "error",
                    "message": permission_result["message"],
                    "locked": permission_result["locked"],
                    "tier": permission_result["tier"]
                }
            
            # 3. 权限通过，使用UE HTTP客户端执行工具
            result = self.ue_client.execute_tool_rpc(tool_name, **kwargs)
            
            # 4. 返回结果（保持原有格式）
            return result
            
        except Exception as e:
            self.logger.error(f"UE工具执行失败: {e}", exc_info=True)
            # 返回错误dict
            return {
                "status": "error", 
                "message": f"UE工具执行器捕获到错误: {str(e)}"
            }
