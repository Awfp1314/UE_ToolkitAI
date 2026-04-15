# -*- mode: python ; coding: utf-8 -*-
"""
UE Toolkit PyInstaller 打包配置
用于将Python项目打包成独立的Windows可执行文件
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 获取spec文件所在目录的父目录（项目根目录）
spec_dir = os.path.dirname(os.path.abspath(SPEC))
# spec_dir = scripts/package/config
# 项目根目录应该是spec_dir的父目录的父目录的父目录
spec_root = os.path.dirname(os.path.dirname(os.path.dirname(spec_dir)))

# 收集所有需要的数据文件
datas = [
    (os.path.join(spec_root, 'resources'), 'resources'),
    (os.path.join(spec_root, 'modules'), 'modules'),
    (os.path.join(spec_root, 'core'), 'core'),
    (os.path.join(spec_root, 'ui'), 'ui'),
    (os.path.join(spec_root, 'scripts/mcp_servers'), 'scripts/mcp_servers'),  # MCP 服务器脚本
    (os.path.join(spec_root, 'config/mcp_config.json'), 'config'),  # MCP 配置文件
    (os.path.join(spec_root, 'version.py'), '.'),  # 打包版本文件
    (os.path.join(spec_dir, 'License.txt'), '.'),  # 打包许可协议文件
]

# 显式添加所有 config_template.json 文件（确保打包后能找到）
config_templates = [
    'modules/ai_assistant/config_template.json',
    'modules/asset_manager/config_template.json',
    'modules/my_projects/config_template.json',
    'modules/config_tool/config_template.json',
    'modules/site_recommendations/config_template.json',
    'core/config_templates/app_config_template.json',
]

for template in config_templates:
    template_path = os.path.join(spec_root, template)
    if os.path.exists(template_path):
        # 保持原始目录结构
        target_dir = os.path.dirname(template)
        datas.append((template_path, target_dir))
    else:
        print(f"警告: 配置模板文件不存在: {template_path}")

# ========== 优化说明 ==========
# 已移除 AI 模型和库的数据文件收集，因为：
# 1. EmbeddingService 功能当前未被使用
# 2. Ollama 和 API Key 聊天不需要这些依赖
# 3. 可减少打包体积约 230MB
# 如需恢复，请参考 ue_toolkit.spec.backup
# ==============================

# 隐藏导入（PyInstaller可能无法自动检测的模块）
# 优化说明：只包含实际使用的模块，移除未使用的 AI 库
hiddenimports = [
    # PyQt6核心模块
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    
    # 标准库
    'uuid',
    'json',
    'sqlite3',
    'threading',
    'queue',
    
    # 图像处理（缩略图功能）
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageQt',
    
    # 系统工具
    'psutil',           # 进程管理
    'pypinyin',         # 拼音转换
    'watchdog',         # 配置热重载
    'yaml',             # YAML 配置
    
    # Word 文档生成
    'docx',             # python-docx
    'docx.shared',
    'docx.enum.text',
    'lxml',             # python-docx 依赖
    
    # HTTP 客户端（AI 聊天）
    'requests',         # API Key 客户端
    'httpx',            # Ollama 客户端
    
    # GitHub集成
    'github',
    
    # 项目模块
    'core.logger',
    'core.config_manager',
    'core.module_manager',
    'core.app_manager',
    'core.update_checker',
    'core.services',
    'version',
    
    # AI 助手模块（确保所有子模块都被包含）
    'modules.ai_assistant.logic.runtime_context',
    'modules.ai_assistant.logic.tools_registry',
    'modules.ai_assistant.logic.api_client',
    'modules.ai_assistant.logic.context_manager',
    'modules.ai_assistant.logic.config',
    'modules.ai_assistant.logic.memory_compressor',
    'modules.ai_assistant.clients.base_llm_client',
    'modules.ai_assistant.clients.ollama_llm_client',
    'modules.ai_assistant.clients.api_llm_client',
    'modules.ai_assistant.clients.llm_client_factory',
]

# 排除不需要的模块（减小打包体积）
# 优化说明：明确排除所有未使用的大型库
excludes = [
    # AI/ML 库（未使用的语义分析功能）
    'torch',
    'transformers',
    'sentence_transformers',
    'scipy',
    'sklearn',
    'scikit-learn',
    'faiss',
    'faiss-cpu',
    # numpy 保留 - AI 助手的记忆管理需要
    
    # 媒体处理（未使用）
    'moviepy',
    'imageio',
    'imageio_ffmpeg',
    
    # AI 推理（未使用）
    'onnxruntime',
    'tensorboard',
    'tensorflow',
    
    # 数据分析（未使用）
    'pandas',
    'matplotlib',
    
    # 开发工具
    'jupyter',
    'notebook',
    'IPython',
    
    # GUI 框架（未使用）
    'tkinter',
    '_tkinter',
    
    # 测试框架
    'test',
    'tests',
    'pytest',
    'unittest',
]

a = Analysis(
    [os.path.join(spec_root, 'main.py')],
    pathex=[spec_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(spec_dir, 'runtime_hook_encoding.py')],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,      # 包含所有二进制文件到单个EXE
    a.zipfiles,      # 包含所有zip文件到单个EXE
    a.datas,         # 包含所有数据文件到单个EXE
    [],
    name='UE_Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,        # 启用UPX压缩（如果安装了UPX）
    upx_exclude=[],
    runtime_tmpdir='_UE_Toolkit',  # 使用固定临时目录名，避免退出时删除失败的警告
    console=False,   # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(spec_root, 'resources', 'tubiao.ico'),
    version_file=None,
)

# 单文件模式不需要COLLECT
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='UE_Toolkit',
# )
