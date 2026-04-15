# -*- coding: utf-8 -*-

"""
工具注册表
定义只读工具的接口和调度逻辑
"""

import json
from typing import Dict, Any, List, Callable
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
        
        # 工具注册表
        self.tools: Dict[str, ToolDefinition] = {}
        
        # 注册所有只读工具
        self._register_readonly_tools()
        
        # 注册测试功能工具
        self._register_experimental_tools()
        
        # 注册虚幻引擎蓝图操作工具
        self._register_ue_tools()
        
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
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            Dict: 工具执行结果 {success, result, error}
        """
        try:
            if tool_name not in self.tools:
                return {
                    "success": False,
                    "error": f"未知工具: {tool_name}"
                }
            
            tool = self.tools[tool_name]
            
            self.logger.info(f"执行工具: {tool_name}, 参数: {arguments}")
            
            # 调用工具函数
            result = tool.function(**arguments)
            
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
                "error": str(e),
                "tool_name": tool_name
            }
    
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
    
    def _execute_ue_python_tool(self, tool_name: str, **kwargs) -> dict:
        """
        通过HTTP客户端执行虚幻引擎编辑器内的函数。
        这是 Function Calling 调用虚幻引擎工具的桥梁。
        
        Args:
            tool_name: UE工具名称（BlueprintToAISubsystem的函数名）
            **kwargs: 工具参数
            
        Returns:
            dict: 执行结果字典
        """
        try:
            # 使用UE HTTP客户端执行工具
            result = self.ue_client.execute_tool_rpc(tool_name, **kwargs)
            
            # 直接返回dict，让dispatch方法统一处理
            return result
            
        except Exception as e:
            self.logger.error(f"UE工具执行失败: {e}", exc_info=True)
            # 返回错误dict
            return {
                "status": "error", 
                "message": f"UE工具执行器捕获到错误: {str(e)}"
            }
    
    def _register_ue_tools(self):
        """
        注册虚幻引擎蓝图操作工具到注册表中。

        使用 BlueprintToAI 插件的 Remote Control API。
        """
        # 1. 提取蓝图（读取）
        self.register_tool(ToolDefinition(
            name="extract_blueprint",
            description="""
提取蓝图的结构信息（节点、变量、组件等）。
用途：分析蓝图结构、理解蓝图逻辑、检测错误等。
参数：
- AssetPath: 蓝图资产路径（如 "/Game/Blueprints/BP_Character"）
- Scope: 提取范围（可选）
  - "Minimal": 只有节点类型和连接（最省token）
  - "Compact": 添加位置和基本属性（默认，平衡）
  - "Full": 包含所有信息（调试用）
            """.strip(),
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "蓝图资产路径（如 /Game/Blueprints/BP_Character）"
                    },
                    "Scope": {
                        "type": "string",
                        "description": "提取范围：Minimal | Compact | Full（默认 Compact）",
                        "enum": ["Minimal", "Compact", "Full"]
                    }
                },
                "required": ["AssetPath"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ExtractBlueprint", **kwargs),
            requires_confirmation=False  # 只读工具，无需确认
        ))

        # 2. 创建蓝图
        self.register_tool(ToolDefinition(
            name="create_blueprint",
            description="""
创建新的蓝图资产。
参数：
- AssetPath: 蓝图资产路径（如 "/Game/Blueprints/BP_MyActor"）
- ParentClass: 父类路径（如 "/Script/Engine.Actor"）
- GraphDSL: 图表DSL（可选，用于快速定义节点）
- PayloadJson: 额外配置（可选，JSON字符串）
            """.strip(),
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "蓝图资产路径"
                    },
                    "ParentClass": {
                        "type": "string",
                        "description": "父类路径（如 /Script/Engine.Actor）"
                    },
                    "GraphDSL": {
                        "type": "string",
                        "description": "图表DSL（可选）"
                    },
                    "PayloadJson": {
                        "type": "string",
                        "description": "额外配置JSON（可选）"
                    }
                },
                "required": ["AssetPath", "ParentClass"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("CreateBlueprint", **kwargs),
            requires_confirmation=True  # 创建操作需要确认
        ))

        # 3. 修改蓝图
        self.register_tool(ToolDefinition(
            name="modify_blueprint",
            description="""
修改现有蓝图。
参数：
- AssetPath: 蓝图资产路径
- Operation: 操作类型（add_variable | add_component | reparent | modify_graph）
- PayloadJson: 操作参数（JSON字符串）
            """.strip(),
            parameters={
                "type": "object",
                "properties": {
                    "AssetPath": {
                        "type": "string",
                        "description": "蓝图资产路径"
                    },
                    "Operation": {
                        "type": "string",
                        "description": "操作类型",
                        "enum": ["add_variable", "add_component", "reparent", "modify_graph"]
                    },
                    "PayloadJson": {
                        "type": "string",
                        "description": "操作参数JSON"
                    }
                },
                "required": ["AssetPath", "Operation", "PayloadJson"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("ModifyBlueprint", **kwargs),
            requires_confirmation=True  # 修改操作需要确认
        ))

        # 4. 保存蓝图
        self.register_tool(ToolDefinition(
            name="save_blueprints",
            description="""
保存蓝图到磁盘。
注意：所有修改操作不会自动保存，必须显式调用此工具。
参数：
- AssetPaths: 蓝图资产路径列表（JSON数组字符串）
            """.strip(),
            parameters={
                "type": "object",
                "properties": {
                    "AssetPaths": {
                        "type": "string",
                        "description": "蓝图资产路径列表（JSON数组字符串，如 '[\"/Game/BP1\", \"/Game/BP2\"]'）"
                    }
                },
                "required": ["AssetPaths"]
            },
            function=lambda **kwargs: self._execute_ue_python_tool("SaveBlueprints", **kwargs),
            requires_confirmation=True  # 保存操作需要确认
        ))

