# -*- coding: utf-8 -*-

"""
设置界面
现代化、简约的设计风格
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QRadioButton, QButtonGroup, QTabWidget,
    QScrollArea, QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from core.logger import get_logger

logger = get_logger(__name__)


# ==================== 设置界面组件 ====================

class SettingsSection(QWidget):
    """设置区块基类"""
    
    def __init__(self, title, icon="⚙️", parent=None):
        super().__init__(parent)
        self.title = title
        self.icon = icon
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.content_widget = QWidget()
        self.content_widget.setObjectName("SectionContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        layout.addWidget(self.content_widget)
    
    def add_setting_row(self, label_text, widget, description=""):
        row_container = QWidget()
        row_container.setObjectName("SettingRow")
        row_layout = QVBoxLayout(row_container)
        row_layout.setContentsMargins(0, 16, 0, 16)
        row_layout.setSpacing(8)
        
        setting_layout = QHBoxLayout()
        setting_layout.setSpacing(16)
        
        label = QLabel(label_text)
        label.setObjectName("SettingLabel")
        label.setFixedWidth(100)
        setting_layout.addWidget(label)
        
        setting_layout.addWidget(widget)
        setting_layout.addStretch()
        
        row_layout.addLayout(setting_layout)
        
        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("DescriptionLabel")
            desc_label.setWordWrap(True)
            desc_label.setContentsMargins(116, 0, 0, 0)
            row_layout.addWidget(desc_label)
        
        self.content_layout.addWidget(row_container)


class AIAssistantSection(SettingsSection):
    """AI助手设置区块"""
    
    # API Key 验证信号
    _api_key_validated = pyqtSignal(dict)  # 验证结果 {'valid': bool, 'error': str}
    
    def __init__(self, parent=None):
        super().__init__("AI助手设置", "🤖", parent)
        self._loading_config = False  # 加载配置标志
        
        # 连接 API Key 验证信号
        self._api_key_validated.connect(self._on_api_key_validation_result)
        
        self.setup_content()
        
        # 延迟加载配置
        QTimer.singleShot(100, self._load_config)
    
    def setup_content(self):
        # LLM供应商选择（改为具体的供应商）
        self.provider_combo = QComboBox()
        self.provider_combo.setObjectName("SettingComboBox")
        self.provider_combo.addItem("OpenAI", "openai")
        self.provider_combo.addItem("Google Gemini", "gemini")
        self.provider_combo.addItem("Deepseek", "deepseek")
        self.provider_combo.addItem("Anthropic Claude", "claude")
        self.provider_combo.addItem("Ollama (本地)", "ollama")
        self.provider_combo.addItem("自定义 (BYOK)", "byok")
        self.provider_combo.setFixedWidth(220)
        self.provider_combo.view().window().setWindowFlags(
            Qt.WindowType.Popup | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.provider_combo.view().window().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.add_setting_row("供应商", self.provider_combo, "选择 AI 服务供应商")
        
        # 添加间距
        spacer = QWidget()
        spacer.setFixedHeight(8)
        self.content_layout.addWidget(spacer)
        
        # API设置容器
        self.api_widget = QWidget()
        api_layout = QVBoxLayout(self.api_widget)
        api_layout.setContentsMargins(0, 0, 0, 0)
        api_layout.setSpacing(0)
        
        # API设置标题
        api_label = QLabel("API 设置")
        api_label.setObjectName("SubSectionLabel")
        api_layout.addWidget(api_label)
        
        # API Key (保存引用以便后续访问)
        self.api_key_row, self.api_key_input = self.create_password_row()
        self._add_row_to_layout(api_layout, "API Key", self.api_key_row, "输入你的API密钥")
        
        # API 状态标签（用于显示验证结果）
        self.api_model_status_label = QLabel("")
        self.api_model_status_label.setObjectName("DescriptionLabel")
        self.api_model_status_label.setWordWrap(True)
        self.api_model_status_label.setContentsMargins(116, 0, 0, 8)
        api_layout.addWidget(self.api_model_status_label)
        
        # API URL（仅 BYOK 时显示）
        self.api_url_row = QWidget()
        url_row_layout = QHBoxLayout(self.api_url_row)
        url_row_layout.setContentsMargins(0, 0, 0, 0)
        url_row_layout.setSpacing(0)
        
        self.api_url_input = QLineEdit()
        self.api_url_input.setObjectName("PathLineEdit")
        self.api_url_input.setPlaceholderText("https://api.example.com/v1/chat/completions")
        url_row_layout.addWidget(self.api_url_input)
        
        self._add_row_to_layout(api_layout, "API URL", self.api_url_row, "自定义 API 服务地址")
        
        self.content_layout.addWidget(self.api_widget)
        
        # 添加间距
        spacer2 = QWidget()
        spacer2.setFixedHeight(8)
        self.content_layout.addWidget(spacer2)
        
        # Ollama设置容器
        self.ollama_widget = QWidget()
        ollama_layout = QVBoxLayout(self.ollama_widget)
        ollama_layout.setContentsMargins(0, 0, 0, 0)
        ollama_layout.setSpacing(0)
        
        # Ollama设置标题
        ollama_label = QLabel("Ollama 设置")
        ollama_label.setObjectName("SubSectionLabel")
        ollama_layout.addWidget(ollama_label)
        
        # Ollama 服务地址（硬编码，只显示不可编辑）
        ollama_url_row = QWidget()
        url_row_layout = QHBoxLayout(ollama_url_row)
        url_row_layout.setContentsMargins(0, 0, 0, 0)
        url_row_layout.setSpacing(0)
        
        ollama_url_label = QLabel("http://localhost:11434")
        ollama_url_label.setObjectName("DescriptionLabel")
        ollama_url_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 13px;")
        url_row_layout.addWidget(ollama_url_label)
        url_row_layout.addStretch()
        
        self._add_row_to_layout(ollama_layout, "服务地址", ollama_url_row, "Ollama 本地服务地址（固定）")
        
        # Ollama状态标签
        self.ollama_status_label = QLabel("")
        self.ollama_status_label.setObjectName("DescriptionLabel")
        self.ollama_status_label.setWordWrap(True)
        self.ollama_status_label.setContentsMargins(116, 0, 0, 0)
        ollama_layout.addWidget(self.ollama_status_label)
        
        # 测试连接按钮行
        test_row = QWidget()
        test_layout = QHBoxLayout(test_row)
        test_layout.setContentsMargins(0, 0, 0, 0)
        test_layout.setSpacing(8)
        
        test_btn = QPushButton("测试连接")
        test_btn.setObjectName("BrowseButton")
        test_btn.setFixedWidth(80)
        test_btn.clicked.connect(self._test_ollama_connection)
        test_layout.addWidget(test_btn)
        test_layout.addStretch()
        
        self._add_row_to_layout(ollama_layout, "", test_row, "")
        
        # 启动 Ollama / 下载 Ollama 按钮行
        self.ollama_launch_row = self._create_ollama_launch_row()
        self._add_row_to_layout(ollama_layout, "Ollama 服务", self.ollama_launch_row, "启动本地 Ollama 服务，未安装则跳转官网下载")
        
        self.content_layout.addWidget(self.ollama_widget)
        
        # 添加间距
        spacer3 = QWidget()
        spacer3.setFixedHeight(8)
        self.content_layout.addWidget(spacer3)
        
        # AI资源管理部分已移除（不再使用语义模型功能）
        # ai_resource_label = QLabel("AI 资源管理")
        # ai_resource_label.setObjectName("SubSectionLabel")
        # self.content_layout.addWidget(ai_resource_label)
        
        # AI资源下载按钮行（已禁用 - 当前未使用语义模型功能）
        # download_row = self.create_ai_download_row()
        # self.add_setting_row("AI 模型", download_row, "下载或检查AI助手所需的语义搜索模型")
        
        # 初始状态：显示API设置，隐藏Ollama设置和URL输入
        self.api_widget.setVisible(True)
        self.ollama_widget.setVisible(False)
        self.api_url_row.setVisible(False)
        
        # 添加保存配置按钮（蓝色样式）
        save_btn = QPushButton("💾 保存配置")
        save_btn.setObjectName("PrimarySaveButton")
        save_btn.setFixedWidth(150)
        save_btn.clicked.connect(self._on_save_config_clicked)
        # 应用蓝色样式
        save_btn.setStyleSheet("""
            QPushButton#PrimarySaveButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#PrimarySaveButton:hover {
                background-color: #106ebe;
            }
            QPushButton#PrimarySaveButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.content_layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 不再自动扫描Ollama模型，只在用户切换到Ollama或点击测试连接时才扫描
        # QTimer.singleShot(200, self._auto_refresh_ollama_models)  # 已移除
    
    def _add_row_to_layout(self, layout, label_text, widget, description=""):
        """添加设置行到指定布局"""
        row_container = QWidget()
        row_container.setObjectName("SettingRow")
        row_layout = QVBoxLayout(row_container)
        row_layout.setContentsMargins(0, 16, 0, 16)
        row_layout.setSpacing(8)
        
        setting_layout = QHBoxLayout()
        setting_layout.setSpacing(16)
        
        label = QLabel(label_text)
        label.setObjectName("SettingLabel")
        label.setFixedWidth(100)
        setting_layout.addWidget(label)
        
        setting_layout.addWidget(widget)
        setting_layout.addStretch()
        
        row_layout.addLayout(setting_layout)
        
        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("DescriptionLabel")
            desc_label.setWordWrap(True)
            desc_label.setContentsMargins(116, 0, 0, 0)
            row_layout.addWidget(desc_label)
        
        layout.addWidget(row_container)
    
    def create_password_row(self):
        """创建密码输入行（带内嵌可见性切换按钮）"""
        from PyQt6.QtWidgets import QHBoxLayout, QWidget
        from PyQt6.QtCore import QSize
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 创建输入框容器（用于内嵌按钮）
        input_container = QWidget()
        input_container.setObjectName("PasswordInputContainer")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(0)
        
        # 密码输入框
        password_input = QLineEdit()
        password_input.setObjectName("PasswordLineEdit")
        password_input.setPlaceholderText("输入API Key...")
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        # 给右侧留出空间放按钮
        password_input.setStyleSheet("padding-right: 45px;")
        input_layout.addWidget(password_input)
        
        # 可见性切换按钮（内嵌在输入框右侧）
        show_btn = QPushButton("🙈")  # 初始状态：隐藏（闭眼）
        show_btn.setObjectName("PasswordToggleButtonInline")
        show_btn.setFixedSize(35, 35)
        show_btn.setCheckable(True)
        show_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 切换密码可见性和图标
        def toggle_password_visibility(checked):
            if checked:
                password_input.setEchoMode(QLineEdit.EchoMode.Normal)
                show_btn.setText("👁")  # 显示状态：睁眼
            else:
                password_input.setEchoMode(QLineEdit.EchoMode.Password)
                show_btn.setText("🙈")  # 隐藏状态：闭眼
        
        show_btn.clicked.connect(toggle_password_visibility)
        
        # 使用绝对定位将按钮放在输入框内部
        show_btn.setParent(input_container)
        show_btn.raise_()
        
        # 调整按钮位置（在输入框右侧内部）
        def update_button_position():
            show_btn.move(input_container.width() - show_btn.width() - 5, 
                         (input_container.height() - show_btn.height()) // 2)
        
        input_container.resizeEvent = lambda e: update_button_position()
        
        layout.addWidget(input_container, 1)
        
        # 获取API Key按钮
        get_key_btn = QPushButton("获取 API Key")
        get_key_btn.setObjectName("GetApiKeyButton")
        get_key_btn.setFixedHeight(40)
        get_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        get_key_btn.clicked.connect(self._open_apikey_url)
        layout.addWidget(get_key_btn)
        
        return container, password_input
    
    def _open_apikey_url(self):
        """打开获取API Key的网页"""
        import webbrowser
        webbrowser.open("https://openai-hk.com/?i=2789")
    
    def create_api_model_row(self):
        """创建API模型输入行（简单的输入框）"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 模型名称输入框
        model_input = QLineEdit()
        model_input.setObjectName("PathLineEdit")
        model_input.setPlaceholderText("例如: gpt-4o-mini")
        model_input.setMinimumWidth(300)
        layout.addWidget(model_input)
        
        # 状态标签（用于显示验证结果）
        self.api_model_status_label = QLabel("")
        self.api_model_status_label.setObjectName("DescriptionLabel")
        layout.addWidget(self.api_model_status_label)
        
        layout.addStretch()
        
        return container, model_input
    
    def _fetch_api_models(self):
        """获取API支持的模型列表（异步）"""
        api_url = self.api_url_input.text()
        api_key = self.api_key_input.text()
        
        if not api_key:
            self.api_model_status_label.setText("⚠ 请先填写 API Key")
            return
        if not api_url:
            self.api_model_status_label.setText("⚠ 请先填写 API URL")
            return
        
        self._fetch_models_btn.setEnabled(False)
        self.api_model_status_label.setText("正在获取模型列表...")
        
        from threading import Thread
        
        def fetch_in_background():
            try:
                from modules.ai_assistant.clients.api_llm_client import ApiLLMClient
                logger.info(f"[获取模型] 开始请求，URL: {api_url}")
                models = ApiLLMClient.fetch_available_models(api_url, api_key, timeout=10)
                logger.info(f"[获取模型] 成功，找到 {len(models)} 个模型")
                self._api_models_fetched.emit(models)
            except Exception as e:
                error_str = str(e)
                logger.error(f"[获取模型] 失败: {error_str}")
                self._api_models_error.emit(error_str)
        
        thread = Thread(target=fetch_in_background, daemon=True)
        thread.start()
    
    @staticmethod
    def _format_model_display_name(model_id: str) -> str:
        """将模型ID格式化为易读的显示名
        
        例如：
            deepseek-ai/DeepSeek-R1  →  DeepSeek-R1 (deepseek-ai)
            Pro/Qwen/Qwen2.5-72B    →  Qwen2.5-72B (Pro/Qwen)
            gpt-4o                   →  gpt-4o
        """
        if '/' not in model_id:
            return model_id
        parts = model_id.rsplit('/', 1)
        return f"{parts[1]}  ({parts[0]})"
    
    def _populate_model_combo(self, models, selected_model=None):
        """填充模型下拉框（统一逻辑）
        
        Args:
            models: 模型ID列表
            selected_model: 要选中的模型ID（可选）
        """
        self.api_model_combo.clear()
        for model_id in models:
            display_name = self._format_model_display_name(model_id)
            # displayText 是简化名，userData 存完整模型ID
            self.api_model_combo.addItem(display_name, model_id)
            idx = self.api_model_combo.count() - 1
            self.api_model_combo.setItemData(idx, model_id, Qt.ItemDataRole.ToolTipRole)
        
        # 选中指定模型
        if selected_model:
            for i in range(self.api_model_combo.count()):
                if self.api_model_combo.itemData(i) == selected_model:
                    self.api_model_combo.setCurrentIndex(i)
                    return
        # 没找到就选第一个
        if self.api_model_combo.count() > 0:
            self.api_model_combo.setCurrentIndex(0)
    
    def _get_selected_model_id(self) -> str:
        """获取当前配置的模型名称"""
        try:
            from core.config.config_manager import ConfigManager
            from pathlib import Path
            
            template_path = Path(__file__).parent.parent / "modules" / "ai_assistant" / "config_template.json"
            config_manager = ConfigManager("ai_assistant", template_path=template_path)
            config = config_manager.get_module_config()
            
            return config.get("api_settings", {}).get("default_model", "")
        except Exception as e:
            logger.error(f"获取模型名称失败: {e}")
            return ""
    
    def _update_api_models_ui(self, models):
        """更新API模型下拉框（主线程）"""
        try:
            self._refreshing_models = True
            current_model = self._get_selected_model_id()
            
            if models:
                self._populate_model_combo(models, current_model)
                self.api_model_status_label.setText(f"✓ 找到 {len(models)} 个模型")
                self._save_cached_models(models)
            else:
                self.api_model_combo.clear()
                self.api_model_status_label.setText("⚠ 未找到模型")
        finally:
            self._refreshing_models = False
            self._fetch_models_btn.setEnabled(True)
    
    def _save_cached_models(self, models):
        """缓存模型列表到配置文件"""
        try:
            from pathlib import Path
            import json
            cache_dir = Path.home() / "AppData" / "Roaming" / "ue_toolkit" / "user_data" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # 用 API URL 作为 key，不同服务商的列表分开缓存
            api_url = self.api_url_input.text()
            cache_data = {
                'api_url': api_url,
                'models': models
            }
            cache_file = cache_dir / "api_models_cache.json"
            cache_file.write_text(json.dumps(cache_data, ensure_ascii=False), encoding='utf-8')
            logger.info(f"[模型缓存] 已缓存 {len(models)} 个模型")
        except Exception as e:
            logger.error(f"[模型缓存] 保存失败: {e}")
    
    def _load_cached_models(self):
        """从缓存加载模型列表"""
        try:
            from pathlib import Path
            import json
            cache_file = Path.home() / "AppData" / "Roaming" / "ue_toolkit" / "user_data" / "cache" / "api_models_cache.json"
            if not cache_file.exists():
                return
            
            cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
            cached_url = cache_data.get('api_url', '')
            current_url = self.api_url_input.text()
            
            # 只有 URL 匹配时才加载缓存（换了服务商缓存就失效）
            if cached_url != current_url:
                return
            
            models = cache_data.get('models', [])
            if models:
                self._refreshing_models = True
                current_model = self._get_selected_model_id()
                self._populate_model_combo(models, current_model)
                self._refreshing_models = False
                self.api_model_status_label.setText(f"已加载缓存（{len(models)} 个模型）")
                logger.info(f"[模型缓存] 从缓存加载了 {len(models)} 个模型")
        except Exception as e:
            logger.error(f"[模型缓存] 加载失败: {e}")
    
    def _on_fetch_models_error(self, error_msg):
        """获取模型列表失败"""
        self.api_model_status_label.setText(f"✗ 获取失败: {error_msg}")
        self._fetch_models_btn.setEnabled(True)
    
    def _on_api_credentials_changed(self):
        """API URL 或 Key 变更时，清空模型列表提醒重新获取"""
        if self._loading_config or self._refreshing_models:
            return
        # 只在模型列表有多个选项时才清空（说明之前获取过）
        if self.api_model_combo.count() > 1:
            self._refreshing_models = True
            self.api_model_combo.clear()
            self._refreshing_models = False
            self.api_model_status_label.setText("⚠ API 已变更，请重新获取模型列表")
    
    def _validate_api_model(self):
        """验证当前选择的模型是否可用（异步）"""
        api_url = self.api_url_input.text()
        api_key = self.api_key_input.text()
        model = self._get_selected_model_id()
        
        if not api_key:
            self.api_model_status_label.setText("⚠ 请先填写 API Key")
            return
        if not api_url:
            self.api_model_status_label.setText("⚠ 请先填写 API URL")
            return
        if not model:
            self.api_model_status_label.setText("⚠ 请先选择模型")
            return
        
        self._validate_model_btn.setEnabled(False)
        self.api_model_status_label.setText(f"正在验证 {model} ...")
        
        from threading import Thread
        
        def validate_in_background():
            try:
                from modules.ai_assistant.clients.api_llm_client import ApiLLMClient
                result = ApiLLMClient.validate_model(api_url, api_key, model, timeout=15)
                result['model'] = model
                self._model_validated.emit(result)
            except Exception as e:
                self._model_validated.emit({'valid': False, 'error': str(e), 'model': model})
        
        thread = Thread(target=validate_in_background, daemon=True)
        thread.start()
    
    def _on_model_validated(self, result):
        """模型验证结果回调（主线程）"""
        self._validate_model_btn.setEnabled(True)
        model = result.get('model', '')
        if result['valid']:
            self.api_model_status_label.setText(f"✓ {model} 验证通过，可以使用")
        else:
            self.api_model_status_label.setText(f"✗ {model} 不可用: {result['error']}")
    
    def _create_ollama_launch_row(self):
        """创建 Ollama 启动/下载 按钮行"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self._ollama_launch_btn = QPushButton("启动 Ollama")
        self._ollama_launch_btn.setObjectName("BrowseButton")
        self._ollama_launch_btn.setFixedWidth(110)
        self._ollama_launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ollama_launch_btn.clicked.connect(self._on_launch_ollama)
        layout.addWidget(self._ollama_launch_btn)
        
        self._ollama_launch_status = QLabel("")
        self._ollama_launch_status.setObjectName("DescriptionLabel")
        layout.addWidget(self._ollama_launch_status)
        
        layout.addStretch()
        return container
    
    def _find_ollama_exe(self):
        """查找 Ollama 可执行文件路径，返回 (exe_path, is_gui_app)"""
        import os
        from pathlib import Path
        
        ollama_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
        
        # 1. 优先查找 GUI 托盘应用 "ollama app.exe"（不会弹黑窗口）
        gui_exe = ollama_dir / "ollama app.exe"
        if gui_exe.exists():
            return str(gui_exe), True
        
        # 2. 查找 CLI 版本 ollama.exe
        cli_exe = ollama_dir / "ollama.exe"
        if cli_exe.exists():
            return str(cli_exe), False
        
        # 3. 其他常见路径
        other_dirs = [
            Path(os.environ.get("PROGRAMFILES", "")) / "Ollama",
            Path.home() / "AppData" / "Local" / "Programs" / "Ollama",
        ]
        for d in other_dirs:
            gui = d / "ollama app.exe"
            if gui.exists():
                return str(gui), True
            cli = d / "ollama.exe"
            if cli.exists():
                return str(cli), False
        
        # 4. PATH 中查找
        import shutil
        which = shutil.which("ollama")
        if which:
            return which, False
        
        return None, False
    
    def _on_launch_ollama(self):
        """点击启动 Ollama 按钮"""
        exe, is_gui = self._find_ollama_exe()
        
        if not exe:
            # 未安装，跳转官网
            self._ollama_launch_status.setText("未检测到 Ollama，正在打开下载页面...")
            import webbrowser
            webbrowser.open("https://ollama.com/download")
            return
        
        # 已安装，先检查是否已在运行
        self._ollama_launch_btn.setEnabled(False)
        self._ollama_launch_status.setText("正在检查 Ollama 状态...")
        
        from threading import Thread
        
        def check_and_launch():
            try:
                import requests
                ollama_url = "http://localhost:11434"  # 硬编码地址
                session = requests.Session()
                session.trust_env = False
                session.proxies = {'http': None, 'https': None}
                
                # 先检查是否已在运行
                try:
                    resp = session.get(f"{ollama_url}/api/version", timeout=2)
                    if resp.status_code == 200:
                        if is_gui:
                            # 检查是否已经是通过 GUI 托盘应用运行的
                            # 如果不是，重启为 GUI 模式以避免 runner 弹黑窗口
                            import subprocess
                            result = subprocess.run(
                                ["tasklist", "/FI", "IMAGENAME eq ollama app.exe", "/NH"],
                                capture_output=True, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                timeout=5,
                            )
                            if "ollama app.exe" not in result.stdout.lower():
                                # 当前是 CLI 模式运行，重启为 GUI 模式
                                self._ollama_launch_status_signal("正在切换到 GUI 模式...")
                                try:
                                    startupinfo_kill = subprocess.STARTUPINFO()
                                    startupinfo_kill.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                                    startupinfo_kill.wShowWindow = 0
                                    subprocess.run(
                                        ["taskkill", "/F", "/IM", "ollama.exe"],
                                        startupinfo=startupinfo_kill,
                                        creationflags=subprocess.CREATE_NO_WINDOW,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                        timeout=5,
                                    )
                                    import time
                                    time.sleep(1)
                                except Exception:
                                    pass
                                # 不 return，继续走下面的启动逻辑
                            else:
                                self.ollama_status_label.setText("✓ Ollama 已在运行")
                                self._ollama_launch_status_signal("✓ Ollama 已在运行（GUI 模式）")
                                self._ollama_launch_btn_enable(True)
                                return
                        else:
                            self.ollama_status_label.setText("✓ Ollama 已在运行")
                            self._ollama_launch_status_signal("✓ Ollama 已在运行")
                            self._ollama_launch_btn_enable(True)
                            return
                except Exception:
                    pass
                
                # 未运行，启动它
                # 先清理可能残留的 ollama 进程（避免旧的 CLI 进程的 runner 弹黑窗口）
                self._ollama_launch_status_signal("正在启动 Ollama...")
                import subprocess
                try:
                    startupinfo_kill = subprocess.STARTUPINFO()
                    startupinfo_kill.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo_kill.wShowWindow = 0
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "ollama.exe"],
                        startupinfo=startupinfo_kill,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
                    import time
                    time.sleep(1)
                except Exception:
                    pass
                
                if is_gui:
                    # GUI 托盘应用：直接启动，不带 serve 参数，不会弹黑窗口
                    subprocess.Popen([exe], close_fds=True)
                else:
                    # CLI 版本：用 ollama serve，隐藏窗口
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0  # SW_HIDE
                    subprocess.Popen(
                        [exe, "serve"],
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        close_fds=True,
                    )
                
                # 等待启动（最多 10 秒）
                import time
                for i in range(20):
                    time.sleep(0.5)
                    try:
                        resp = session.get(f"{ollama_url}/api/version", timeout=2)
                        if resp.status_code == 200:
                            self._ollama_launch_status_signal(f"✓ Ollama 启动成功")
                            self._ollama_launch_btn_enable(True)
                            return
                    except Exception:
                        continue
                
                self._ollama_launch_status_signal("⚠ 启动超时，请手动检查")
                self._ollama_launch_btn_enable(True)
                
            except Exception as e:
                self._ollama_launch_status_signal(f"✗ 启动失败: {str(e)}")
                self._ollama_launch_btn_enable(True)
        
        thread = Thread(target=check_and_launch, daemon=True)
        thread.start()
    
    def _ollama_launch_status_signal(self, text):
        """线程安全地更新启动状态标签"""
        from PyQt6.QtCore import QMetaObject, Qt as QtCore_Qt, Q_ARG
        QMetaObject.invokeMethod(
            self._ollama_launch_status, "setText",
            QtCore_Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, text)
        )
    
    def _ollama_launch_btn_enable(self, enabled):
        """线程安全地启用/禁用按钮"""
        from PyQt6.QtCore import QMetaObject, Qt as QtCore_Qt, Q_ARG
        QMetaObject.invokeMethod(
            self._ollama_launch_btn, "setEnabled",
            QtCore_Qt.ConnectionType.QueuedConnection,
            Q_ARG(bool, enabled)
        )
    
    def create_ai_download_row(self):
        """创建AI资源下载行"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 状态标签
        self.ai_model_status_label = QLabel("检查中...")
        self.ai_model_status_label.setObjectName("DescriptionLabel")
        layout.addWidget(self.ai_model_status_label)
        
        layout.addStretch()
        
        # 下载按钮
        download_btn = QPushButton("下载 AI 资源")
        download_btn.setObjectName("BrowseButton")
        download_btn.setFixedWidth(120)
        download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_btn.clicked.connect(self._on_download_ai_model)
        layout.addWidget(download_btn)
        
        # 延迟检查模型状态
        QTimer.singleShot(200, self._check_ai_model_status)
        
        return container
    
    def _on_provider_changed(self, index):
        """供应商切换"""
        provider = self.provider_combo.currentData()
        print(f"[Provider] _on_provider_changed: provider={provider}")
        
        # 供应商到 URL 和默认模型的映射
        provider_configs = {
            "openai": {
                "url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4o-mini"
            },
            "gemini": {
                "url": "https://generativelanguage.googleapis.com/v1beta/chat/completions",
                "model": "gemini-2.0-flash-exp"
            },
            "deepseek": {
                "url": "https://api.deepseek.com/v1/chat/completions",
                "model": "deepseek-chat"
            },
            "claude": {
                "url": "https://api.anthropic.com/v1/messages",
                "model": "claude-3-5-sonnet-20241022"
            },
            "ollama": {
                "url": "http://localhost:11434/api/chat",
                "model": "llama3"
            },
            "byok": {
                "url": "",
                "model": "gpt-3.5-turbo"
            }
        }
        
        # 根据供应商显示/隐藏相应的设置区域
        is_ollama = (provider == "ollama")
        is_byok = (provider == "byok")
        is_api = not is_ollama
        
        self.api_widget.setVisible(is_api)
        self.ollama_widget.setVisible(is_ollama)
        self.api_url_row.setVisible(is_byok)
        
        # 先设置默认 URL（对于非 BYOK 供应商）
        config = provider_configs.get(provider, {})
        if not is_byok and not is_ollama:
            url = config.get("url", "")
            self.api_url_input.setText(url)
            
            # 同时设置默认模型（将在保存时使用）
            if not self._loading_config:
                model = config.get("model", "")
                if model:
                    logger.info(f"供应商切换：将使用默认模型 {model}")
        
        # 从配置中加载该供应商之前保存的密钥和 URL（可能会覆盖默认 URL）
        self._load_provider_credentials(provider)
        
        logger.info(f"供应商切换到: {provider}")
    
    def _load_provider_credentials(self, provider):
        """加载指定供应商的密钥配置
        
        Args:
            provider: 供应商标识（openai, deepseek, gemini, claude, byok, ollama）
        """
        try:
            from core.config.config_manager import ConfigManager
            from pathlib import Path
            from modules.ai_assistant.config_schema import get_ai_assistant_schema
            
            template_path = Path(__file__).parent.parent / "modules" / "ai_assistant" / "config_template.json"
            config_manager = ConfigManager(
                "ai_assistant", 
                template_path=template_path,
                config_schema=get_ai_assistant_schema()
            )
            config = config_manager.get_module_config()
            
            # 从 provider_credentials 中加载该供应商的配置
            provider_credentials = config.get("provider_credentials", {})
            provider_config = provider_credentials.get(provider, {})
            
            if provider == "ollama":
                # Ollama 不需要密钥，跳过
                logger.info(f"[加载凭据] Ollama 不需要密钥")
            else:
                # 加载 API Key
                api_key = provider_config.get("api_key", "")
                self.api_key_input.setText(api_key)
                
                # 加载 API URL
                # BYOK: 必须从配置加载（用户自定义）
                # 其他供应商: 如果配置中有保存的 URL，使用保存的；否则使用默认 URL（已在 _on_provider_changed 中设置）
                if provider == "byok":
                    api_url = provider_config.get("api_url", "")
                    self.api_url_input.setText(api_url)
                else:
                    # 非 BYOK 供应商：如果配置中有保存的 URL，使用保存的（可能用户修改过）
                    saved_url = provider_config.get("api_url", "")
                    if saved_url:
                        self.api_url_input.setText(saved_url)
                        logger.info(f"[加载凭据] 使用保存的 URL: {saved_url}")
                    # 否则保持 _on_provider_changed 中设置的默认 URL
                
                logger.info(f"[加载凭据] 已加载 {provider} 的配置，密钥长度: {len(api_key)}")
        except Exception as e:
            logger.error(f"加载供应商凭据失败: {e}", exc_info=True)
    
    def _load_config(self):
        """加载配置"""
        try:
            from core.config.config_manager import ConfigManager
            from pathlib import Path
            from modules.ai_assistant.config_schema import get_ai_assistant_schema
            
            self._loading_config = True
            
            template_path = Path(__file__).parent.parent / "modules" / "ai_assistant" / "config_template.json"
            config_manager = ConfigManager(
                "ai_assistant", 
                template_path=template_path,
                config_schema=get_ai_assistant_schema()
            )
            config = config_manager.get_module_config()
            
            # 优先使用 provider_type 字段（新版本保存的）
            provider = config.get("provider_type", "")
            
            # 如果没有 provider_type，则根据 llm_provider 和 URL 判断（兼容旧版本）
            if not provider:
                llm_provider = config.get("llm_provider", "api")
                
                # 加载API设置
                api_settings = config.get("api_settings", {})
                api_url = api_settings.get("api_url", "") or "https://api.openai.com/v1/chat/completions"
                
                # 根据 llm_provider 和 URL 判断供应商
                if llm_provider == "ollama":
                    provider = "ollama"
                else:
                    # API 供应商，根据 URL 判断具体类型
                    provider = "byok"  # 默认为自定义
                    if "openai.com" in api_url:
                        provider = "openai"
                    elif "generativelanguage.googleapis.com" in api_url or "gemini" in api_url.lower():
                        provider = "gemini"
                    elif "deepseek.com" in api_url:
                        provider = "deepseek"
                    elif "anthropic.com" in api_url or "claude" in api_url.lower():
                        provider = "claude"
                
                # 迁移旧配置：将当前的 api_settings 保存到 provider_credentials
                if not config.get("provider_credentials"):
                    logger.info(f"[配置迁移] 检测到旧配置格式，迁移到新格式")
                    config["provider_credentials"] = {}
                    if provider != "ollama":
                        config["provider_credentials"][provider] = {
                            "api_key": api_settings.get("api_key", ""),
                            "api_url": api_url
                        }
                        config_manager.save_user_config_fast(config)
                        logger.info(f"[配置迁移] 已迁移 {provider} 的配置")
            
            logger.info(f"[配置加载] provider_type={config.get('provider_type', '无')}, 最终供应商={provider}")
            
            # 设置供应商下拉框（这会触发 _on_provider_changed，自动加载该供应商的凭据）
            for i in range(self.provider_combo.count()):
                if self.provider_combo.itemData(i) == provider:
                    self.provider_combo.setCurrentIndex(i)
                    logger.info(f"[配置加载] 已设置供应商下拉框为: {provider}")
                    break
            
            logger.info("AI助手配置加载完成")
        except Exception as e:
            logger.error(f"加载AI助手配置失败: {e}", exc_info=True)
        finally:
            self._loading_config = False
    
    def _on_save_config_clicked(self):
        """保存配置按钮点击"""
        # 获取当前供应商
        provider = self.provider_combo.currentData()
        
        # 如果是 API 供应商（非 Ollama），先验证 API Key
        if provider != "ollama":
            api_key = self.api_key_input.text().strip()
            api_url = self.api_url_input.text().strip()
            
            if not api_key:
                self._show_api_key_error("请输入 API Key")
                return
            
            # 只有 BYOK 才需要用户输入 URL，其他供应商使用默认 URL
            if provider == "byok":
                if not api_url:
                    self._show_api_key_error("请输入 API URL")
                    return
            else:
                # 非 BYOK 供应商：如果 URL 为空，使用默认 URL
                if not api_url:
                    provider_configs = {
                        "openai": "https://api.openai.com/v1/chat/completions",
                        "gemini": "https://generativelanguage.googleapis.com/v1beta/chat/completions",
                        "deepseek": "https://api.deepseek.com/v1/chat/completions",
                        "claude": "https://api.anthropic.com/v1/messages",
                    }
                    api_url = provider_configs.get(provider, "")
                    if api_url:
                        self.api_url_input.setText(api_url)
                        logger.info(f"[配置保存] 使用默认 URL: {api_url}")
            
            # 异步验证 API Key 并获取模型列表
            self._validate_and_save_config(api_key, api_url)
        else:
            # Ollama：获取模型列表后保存
            self._fetch_ollama_models_and_save()
    
    def _fetch_ollama_models_and_save(self):
        """获取Ollama模型列表并保存配置"""
        from threading import Thread
        
        # 显示加载状态
        self.ollama_status_label.setText("🔄 正在获取模型列表...")
        self.ollama_status_label.setStyleSheet("color: #3498db;")
        
        def fetch_in_background():
            try:
                import requests
                ollama_url = "http://localhost:11434"
                
                logger.info(f"[配置保存] 开始获取 Ollama 模型列表")
                
                session = requests.Session()
                session.trust_env = False
                session.proxies = {'http': None, 'https': None}
                
                response = session.get(f"{ollama_url}/api/tags", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                    logger.info(f"[配置保存] 成功获取 {len(models)} 个 Ollama 模型")
                    
                    # 通过信号发送结果到主线程
                    from PyQt6.QtCore import QMetaObject, Qt
                    QMetaObject.invokeMethod(
                        self,
                        "_on_ollama_models_fetched",
                        Qt.ConnectionType.QueuedConnection,
                        models
                    )
                else:
                    logger.error(f"[配置保存] Ollama 请求失败，状态码: {response.status_code}")
                    QMetaObject.invokeMethod(
                        self,
                        "_on_ollama_fetch_error",
                        Qt.ConnectionType.QueuedConnection,
                        f"连接失败 (HTTP {response.status_code})"
                    )
            except requests.exceptions.ConnectionError as e:
                logger.error(f"[配置保存] Ollama 连接失败: {e}")
                from PyQt6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(
                    self,
                    "_on_ollama_fetch_error",
                    Qt.ConnectionType.QueuedConnection,
                    "无法连接到 Ollama 服务，请确保 Ollama 正在运行"
                )
            except Exception as e:
                logger.error(f"[配置保存] 获取 Ollama 模型失败: {e}")
                from PyQt6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(
                    self,
                    "_on_ollama_fetch_error",
                    Qt.ConnectionType.QueuedConnection,
                    str(e)
                )
        
        thread = Thread(target=fetch_in_background, daemon=True)
        thread.start()
    
    @pyqtSlot(list)
    def _on_ollama_models_fetched(self, models):
        """Ollama 模型获取成功（主线程）"""
        if models and len(models) > 0:
            logger.info(f"[配置保存] 收到 {len(models)} 个 Ollama 模型")
            self.ollama_status_label.setText(f"✅ 找到 {len(models)} 个模型")
            self.ollama_status_label.setStyleSheet("color: #27ae60;")
            
            # 保存配置（传入模型列表）
            success = self._save_config(models=models)
            
            if success:
                from modules.asset_manager.ui.message_dialog import MessageDialog
                MessageDialog("保存成功", f"Ollama 配置已保存\n找到 {len(models)} 个可用模型", "success", parent=self).exec()
            
            # 恢复状态
            QTimer.singleShot(2000, lambda: self.ollama_status_label.setText(""))
        else:
            self.ollama_status_label.setText("⚠ 未找到模型")
            self.ollama_status_label.setStyleSheet("color: #e67e22;")
    
    @pyqtSlot(str)
    def _on_ollama_fetch_error(self, error_msg):
        """Ollama 模型获取失败（主线程）"""
        self.ollama_status_label.setText(f"❌ {error_msg}")
        self.ollama_status_label.setStyleSheet("color: #e74c3c;")
        
        # 3秒后恢复
        QTimer.singleShot(3000, lambda: self.ollama_status_label.setText(""))
    
    def _show_api_key_error(self, message: str):
        """显示 API Key 错误提示"""
        # 设置输入框为红色边框（保持密码输入框的背景透明）
        self.api_key_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e74c3c;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        # 显示错误消息
        self.api_model_status_label.setText(f"❌ {message}")
        self.api_model_status_label.setStyleSheet("color: #e74c3c;")
        
        # 3秒后恢复正常样式
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, self._reset_api_key_style)
    
    def _reset_api_key_style(self):
        """恢复 API Key 输入框的正常样式"""
        self.api_key_input.setStyleSheet("")
        self.api_model_status_label.setText("")
        self.api_model_status_label.setStyleSheet("")
    
    def _validate_and_save_config(self, api_key: str, api_url: str):
        """验证 API Key 并保存配置"""
        from threading import Thread
        
        # 显示验证中状态
        self.api_model_status_label.setText("🔄 正在验证 API Key...")
        self.api_model_status_label.setStyleSheet("color: #3498db;")
        
        def validate_in_background():
            try:
                from modules.ai_assistant.clients.api_llm_client import ApiLLMClient
                
                # 获取模型列表来验证 API Key（同时获取可用模型）
                logger.info(f"[配置保存] 开始验证 API Key 并获取模型列表")
                models = ApiLLMClient.fetch_available_models(api_url, api_key, timeout=10)
                
                # 验证成功，返回模型列表
                result = {
                    'valid': True, 
                    'error': None,
                    'models': models
                }
                logger.info(f"[配置保存] 验证成功，获取到 {len(models)} 个模型")
                
                # 通过信号发送结果到主线程
                self._api_key_validated.emit(result)
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[配置保存] API Key 验证失败: {error_msg}")
                
                # 解析常见错误
                if '401' in error_msg or 'Unauthorized' in error_msg or 'Invalid' in error_msg:
                    error_msg = 'API Key 无效或已过期'
                elif '403' in error_msg or 'Forbidden' in error_msg:
                    error_msg = 'API Key 没有访问权限'
                elif 'timeout' in error_msg.lower():
                    error_msg = '连接超时，请检查网络或 API URL'
                
                self._api_key_validated.emit({'valid': False, 'error': f"验证失败: {error_msg}", 'models': []})
        
        thread = Thread(target=validate_in_background, daemon=True)
        thread.start()
    
    def _on_api_key_validation_result(self, result: dict):
        """处理 API Key 验证结果（主线程）"""
        if result.get("valid", False):
            # 验证成功
            models = result.get("models", [])
            logger.info(f"[配置保存] 验证成功，收到 {len(models)} 个模型")
            
            self.api_model_status_label.setText(f"✅ 验证成功，找到 {len(models)} 个模型")
            self.api_model_status_label.setStyleSheet("color: #27ae60;")
            
            # 保存配置（传入模型列表）
            success = self._save_config(models=models)
            
            if success:
                # 显示成功消息
                from modules.asset_manager.ui.message_dialog import MessageDialog
                MessageDialog("保存成功", f"API Key 验证通过，配置已保存\n找到 {len(models)} 个可用模型", "success", parent=self).exec()
            
            # 恢复状态
            QTimer.singleShot(2000, self._reset_api_key_style)
        else:
            # 验证失败
            error_msg = result.get("error", "API Key 无效")
            self._show_api_key_error(error_msg)
    
    def _save_config(self, models=None):
        """保存配置
        
        Args:
            models: 可用模型列表（从API获取），如果为None则使用配置中已有的模型
        """
        try:
            from core.config.config_manager import ConfigManager
            from pathlib import Path
            from modules.ai_assistant.config_schema import get_ai_assistant_schema
            
            template_path = Path(__file__).parent.parent / "modules" / "ai_assistant" / "config_template.json"
            config_manager = ConfigManager(
                "ai_assistant", 
                template_path=template_path,
                config_schema=get_ai_assistant_schema()
            )
            
            # 获取当前配置
            config = config_manager.get_module_config()
            
            # 更新配置
            provider = self.provider_combo.currentData()
            
            # 将供应商映射为 AI 助手识别的类型
            # 所有 API 供应商（openai, gemini, deepseek, claude, byok）都保存为 "api"
            # 只有 ollama 保存为 "ollama"
            if provider == "ollama":
                config["llm_provider"] = "ollama"
            else:
                config["llm_provider"] = "api"
            
            # 保存具体的供应商类型（用于加载时准确恢复）
            config["provider_type"] = provider
            
            # 初始化 provider_credentials（每个供应商单独保存密钥）
            if "provider_credentials" not in config:
                config["provider_credentials"] = {}
            
            # 保存当前供应商的凭据到 provider_credentials
            if provider != "ollama":
                config["provider_credentials"][provider] = {
                    "api_key": self.api_key_input.text().strip(),
                    "api_url": self.api_url_input.text().strip()
                }
                logger.info(f"[配置保存] 已保存 {provider} 的凭据到 provider_credentials")
            
            # API设置（保持向后兼容，同时保存到 api_settings）
            if "api_settings" not in config:
                config["api_settings"] = {}
            config["api_settings"]["api_key"] = self.api_key_input.text().strip()
            config["api_settings"]["api_url"] = self.api_url_input.text().strip()
            
            # 设置默认模型
            if models and len(models) > 0:
                # 使用从API/Ollama获取的第一个模型作为默认模型
                if provider == "ollama":
                    config["ollama_settings"]["default_model"] = models[0]
                    logger.info(f"[配置保存] 使用获取到的第一个 Ollama 模型: {models[0]}")
                else:
                    config["api_settings"]["default_model"] = models[0]
                    logger.info(f"[配置保存] 使用获取到的第一个 API 模型: {models[0]}")
            else:
                # 如果没有获取到模型，保留配置中已有的模型（或使用供应商默认模型）
                if provider == "ollama":
                    current_model = config.get("ollama_settings", {}).get("default_model", "")
                    if not current_model:
                        # Ollama 没有默认模型，保持为空或使用常见的默认值
                        config["ollama_settings"]["default_model"] = "llama3.2"
                        logger.info(f"[配置保存] 使用 Ollama 默认模型: llama3.2")
                    else:
                        logger.info(f"[配置保存] 保留已有 Ollama 模型: {current_model}")
                else:
                    current_model = config.get("api_settings", {}).get("default_model", "")
                    if not current_model:
                        # 使用供应商的默认模型作为后备
                        provider_default_models = {
                            "openai": "gpt-4o-mini",
                            "gemini": "gemini-2.0-flash-exp",
                            "deepseek": "deepseek-chat",
                            "claude": "claude-3-5-sonnet-20241022",
                            "byok": "gpt-3.5-turbo"
                        }
                        config["api_settings"]["default_model"] = provider_default_models.get(provider, "gpt-4o-mini")
                        logger.info(f"[配置保存] 使用供应商默认模型: {config['api_settings']['default_model']}")
                    else:
                        logger.info(f"[配置保存] 保留已有 API 模型: {current_model}")
            
            # Ollama设置
            if "ollama_settings" not in config:
                config["ollama_settings"] = {}
            # Ollama 地址硬编码
            config["ollama_settings"]["base_url"] = "http://localhost:11434"
            
            # Ollama 模型已在上面的"设置默认模型"部分处理
            
            # 打印调试信息
            saved_provider = config["llm_provider"]
            logger.info(f"[配置保存] 供应商: {saved_provider} (UI选择: {provider})")
            if saved_provider == "api":
                logger.info(f"[配置保存] API URL: {config['api_settings'].get('api_url')}")
                logger.info(f"[配置保存] API 模型: {config['api_settings'].get('default_model')}")
            elif saved_provider == "ollama":
                logger.info(f"[配置保存] Ollama URL: {config['ollama_settings'].get('base_url')}")
                logger.info(f"[配置保存] Ollama 模型: {config['ollama_settings'].get('default_model')}")
            
            # 保存配置
            success = config_manager.save_user_config_fast(config)
            if success:
                logger.info("✅ AI助手配置已保存成功")
                
                # 获取主窗口引用
                main_win = self.window()
                logger.info(f"[配置保存] 主窗口引用: {main_win}, 类型: {type(main_win).__name__}")
                
                # 清除主窗口的模型名称缓存，使标题栏同步更新
                if main_win and hasattr(main_win, '_cached_ai_model_name'):
                    del main_win._cached_ai_model_name
                    logger.info("[配置保存] 已清除模型名称缓存")
                
                # 刷新主窗口标题栏的模型下拉框
                if main_win and hasattr(main_win, '_load_ai_models'):
                    logger.info("[配置保存] 准备刷新主窗口模型列表")
                    # 使用 lambda 确保在正确的时机调用
                    QTimer.singleShot(100, lambda: main_win._load_ai_models())
                else:
                    if not main_win:
                        logger.warning("[配置保存] 无法获取主窗口引用")
                    else:
                        logger.warning(f"[配置保存] 主窗口没有 _load_ai_models 方法，可用方法: {[m for m in dir(main_win) if not m.startswith('_')][:10]}")
                
                return True
            else:
                logger.error("❌ AI助手配置保存失败")
                return False
        except Exception as e:
            logger.error(f"保存AI助手配置失败: {e}", exc_info=True)
            return False
    
    def _test_ollama_connection(self):
        """测试Ollama连接（异步）"""
        ollama_url = "http://localhost:11434"  # 硬编码地址
        
        self.ollama_status_label.setText("正在测试连接...")
        
        # 使用线程避免阻塞UI
        def test_connection():
            try:
                import requests
                session = requests.Session()
                session.trust_env = False
                session.proxies = {'http': None, 'https': None}
                response = session.get(f"{ollama_url}/api/version", timeout=5)
                return response.status_code == 200, response.status_code
            except Exception as e:
                return False, str(e)
        
        def on_result(result):
            success, info = result
            if success:
                self.ollama_status_label.setText("✓ 连接成功！Ollama 服务正常运行")
            else:
                if isinstance(info, int):
                    self.ollama_status_label.setText(f"✗ 连接失败 (HTTP {info})")
                else:
                    self.ollama_status_label.setText(f"✗ 连接失败: {info}")
        
        # 在后台线程执行
        from core.utils.thread_utils import get_thread_manager
        thread_manager = get_thread_manager()
        thread_manager.run_in_thread(test_connection, on_result=on_result)
    
    def _check_ai_model_status(self):
        """检查AI模型状态"""
        try:
            from modules.ai_assistant.logic.ai_model_manager import AIModelManager
            
            # 在后台线程检查
            def check_status():
                return AIModelManager.check_model_integrity()
            
            def on_result(available):
                if available:
                    self.ai_model_status_label.setText("✓ AI模型已就绪")
                    self.ai_model_status_label.setStyleSheet("color: #4CAF50;")
                else:
                    self.ai_model_status_label.setText("✗ AI模型未下载")
                    self.ai_model_status_label.setStyleSheet("color: #FF9800;")
            
            from core.utils.thread_utils import get_thread_manager
            thread_manager = get_thread_manager()
            thread_manager.run_in_thread(check_status, on_result=on_result)
        except Exception as e:
            logger.error(f"检查AI模型状态失败: {e}", exc_info=True)
            self.ai_model_status_label.setText("✗ 检查失败")
    
    def _on_download_ai_model(self):
        """下载AI模型"""
        try:
            from modules.ai_assistant.logic.ai_model_manager import AIModelManager
            
            # 先检查模型是否已存在
            if AIModelManager.check_model_integrity():
                from modules.asset_manager.ui.message_dialog import MessageDialog
                MessageDialog(
                    "AI资源已就绪",
                    "AI模型已经下载完成，无需重复下载。",
                    "info",
                    parent=self
                ).exec()
                return
            
            # 显示下载对话框
            from ui.dialogs.ai_model_download_dialog import AIModelDownloadDialog
            success = AIModelDownloadDialog.download_model(self.window())
            
            # 下载完成后更新状态
            if success:
                self.ai_model_status_label.setText("✓ AI模型已就绪")
                self.ai_model_status_label.setStyleSheet("color: #4CAF50;")
                logger.info("AI模型下载成功")
            else:
                self.ai_model_status_label.setText("✗ 下载失败或已取消")
                self.ai_model_status_label.setStyleSheet("color: #F44336;")
                logger.warning("AI模型下载失败或被取消")
        except Exception as e:
            logger.error(f"下载AI模型失败: {e}", exc_info=True)
            from modules.asset_manager.ui.message_dialog import MessageDialog
            MessageDialog(
                "下载失败",
                f"下载AI模型时发生错误：\n{str(e)}",
                "error",
                parent=self
            ).exec()


class GeneralSection(SettingsSection):
    """常规设置区块"""

    floating_widget_toggled = pyqtSignal(bool)  # 悬浮窗开关信号
    autostart_toggled = pyqtSignal(bool)         # 开机自启信号

    def __init__(self, parent=None):
        super().__init__("常规设置", "⚙️", parent)
        self._updating_close_behavior = False  # 标志位，防止循环触发
        self._updating_floating = False  # 标志位，防止循环触发
        self._updating_autostart = False  # 标志位，防止循环触发
        self.setup_content()
        self._init_close_behavior()  # 初始化关闭行为选择
        self._init_floating_toggle()  # 初始化悬浮窗开关
        self._init_autostart_toggle()  # 初始化开机自启开关
    
    def setup_content(self):
        # 关闭方式设置标题
        close_label = QLabel("关闭方式设置")
        close_label.setObjectName("SubSectionLabel")
        self.content_layout.addWidget(close_label)
        
        # 关闭行为选择
        close_radio_row = self.create_close_behavior_row()
        self.add_setting_row("关闭按钮行为", close_radio_row, "设置点击窗口关闭按钮时的默认行为")

        # 添加间距
        spacer2 = QWidget()
        spacer2.setFixedHeight(8)
        self.content_layout.addWidget(spacer2)

        # 悬浮窗与自启设置标题
        fw_label = QLabel("悬浮窗与自启设置")
        fw_label.setObjectName("SubSectionLabel")
        self.content_layout.addWidget(fw_label)

        # 桌面悬浮窗开关
        self.floating_toggle = QCheckBox("启用桌面悬浮窗")
        self.floating_toggle.stateChanged.connect(self._on_floating_toggled)
        self.add_setting_row("悬浮窗", self.floating_toggle, "在桌面显示悬浮窗，点击可快速打开主窗口")

        # 开机自启开关
        self.autostart_toggle = QCheckBox("开机自动启动")
        self.autostart_toggle.stateChanged.connect(self._on_autostart_toggled)
        self.add_setting_row("开机自启", self.autostart_toggle, "Windows 启动时自动运行 UE Toolkit")
    
    def create_close_behavior_row(self):
        """创建关闭行为选择行"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        self.close_button_group = QButtonGroup(container)
        
        self.close_radio = QRadioButton("直接关闭")
        self.close_radio.setObjectName("ThemeRadio")
        self.close_button_group.addButton(self.close_radio, 1)
        layout.addWidget(self.close_radio)
        
        self.minimize_radio = QRadioButton("最小化到托盘")
        self.minimize_radio.setObjectName("ThemeRadio")
        self.close_button_group.addButton(self.minimize_radio, 2)
        layout.addWidget(self.minimize_radio)
        
        self.ask_radio = QRadioButton("每次询问")
        self.ask_radio.setObjectName("ThemeRadio")
        self.ask_radio.setChecked(True)
        self.close_button_group.addButton(self.ask_radio, 0)
        layout.addWidget(self.ask_radio)
        
        # 连接信号
        self.close_button_group.buttonClicked.connect(self._on_close_behavior_changed)
        
        layout.addStretch()
        
        return container
    
    def _init_close_behavior(self):
        """初始化关闭行为选择"""
        try:
            from core.services import config_service
            app_config = config_service.get_module_config("app")
            
            if app_config:
                preference = app_config.get("close_action_preference")
                
                self._updating_close_behavior = True
                if preference == "close":
                    self.close_radio.setChecked(True)
                elif preference == "minimize":
                    self.minimize_radio.setChecked(True)
                else:
                    # 默认或 None 时选择"每次询问"
                    self.ask_radio.setChecked(True)
                self._updating_close_behavior = False
                
                logger.debug("[设置] 加载关闭偏好: %s", preference)
        except Exception as e:
            logger.warning("初始化关闭行为失败: %s", e)
    
    def _on_close_behavior_changed(self, button):
        """关闭行为改变时触发"""
        if self._updating_close_behavior:
            return
        
        try:
            from core.services import config_service
            
            # 获取选中的按钮ID
            button_id = self.close_button_group.id(button)
            
            # 映射到配置值
            if button_id == 1:  # 直接关闭
                preference = "close"
            elif button_id == 2:  # 最小化到托盘
                preference = "minimize"
            else:  # 每次询问
                preference = None
            
            # 保存配置
            app_config = config_service.get_module_config("app")
            if app_config:
                if preference is None:
                    # 删除配置项，表示每次询问
                    app_config.pop("close_action_preference", None)
                else:
                    app_config["close_action_preference"] = preference
                
                # immediate=False: 仅更新内存，退出时统一保存
                config_service.save_module_config("app", app_config, immediate=False)
                logger.debug("[设置] 关闭偏好已更新到内存: %s", preference)
        except Exception as e:
            logger.warning("保存关闭行为失败: %s", e)

    # ------------------------------------------------------------------
    # 悬浮窗开关 (Req 6.2, 6.4, 6.5, 6.8)
    # ------------------------------------------------------------------

    def _get_general_settings_path(self):
        """获取 general_settings.json 路径"""
        import os
        from pathlib import Path
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "ue_toolkit" / "user_data" / "general_settings.json"

    def _load_general_settings(self) -> dict:
        """加载通用设置"""
        import json
        path = self._get_general_settings_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_general_setting(self, key: str, value):
        """保存单个通用设置项"""
        import json
        settings = self._load_general_settings()
        settings[key] = value
        path = self._get_general_settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    def _init_floating_toggle(self):
        """初始化悬浮窗开关状态（从配置读取）"""
        try:
            self._updating_floating = True
            settings = self._load_general_settings()
            enabled = settings.get("floating_widget_enabled", False)
            self.floating_toggle.setChecked(enabled)
        except Exception as e:
            logger.warning("初始化悬浮窗开关失败: %s", e)
        finally:
            self._updating_floating = False

    def _on_floating_toggled(self, state):
        """悬浮窗开关改变时触发"""
        if self._updating_floating:
            return
        enabled = state == Qt.CheckState.Checked.value
        self._save_general_setting("floating_widget_enabled", enabled)
        self.floating_widget_toggled.emit(enabled)
        logger.info("[设置] 悬浮窗开关: %s", enabled)

    def update_floating_state(self, enabled: bool):
        """外部同步悬浮窗状态（悬浮窗右键菜单"关闭悬浮窗"调用）"""
        self._updating_floating = True
        self.floating_toggle.setChecked(enabled)
        self._save_general_setting("floating_widget_enabled", enabled)
        self._updating_floating = False

    # ------------------------------------------------------------------
    # 开机自启 (Req 6.3, 6.6, 6.9, 6.10)
    # ------------------------------------------------------------------

    AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    AUTOSTART_NAME = "UEToolkit"

    def _is_autostart_enabled(self) -> bool:
        """从 Windows 注册表读取开机自启状态"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self.AUTOSTART_KEY,
                0, winreg.KEY_READ,
            )
            winreg.QueryValueEx(key, self.AUTOSTART_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _set_autostart_registry(self, enabled: bool):
        """写入/删除 Windows 注册表开机自启项"""
        try:
            import sys
            import winreg
            from pathlib import Path
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self.AUTOSTART_KEY,
                0, winreg.KEY_SET_VALUE,
            )
            if enabled:
                if getattr(sys, 'frozen', False):
                    # 打包环境：直接使用 exe 路径
                    cmd = f'"{sys.executable}"'
                else:
                    # 开发环境：用 pythonw.exe 启动 main.py（隐藏命令行窗口）
                    pythonw = Path(sys.executable).parent / "pythonw.exe"
                    if not pythonw.exists():
                        pythonw = Path(sys.executable)
                    main_py = Path(__file__).resolve().parents[1] / "main.py"
                    cmd = f'"{pythonw}" "{main_py}"'
                winreg.SetValueEx(
                    key, self.AUTOSTART_NAME,
                    0, winreg.REG_SZ, cmd,
                )
            else:
                try:
                    winreg.DeleteValue(key, self.AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.error("设置开机自启失败: %s", e)

    def _init_autostart_toggle(self):
        """初始化开机自启开关（从注册表读取实际状态）"""
        try:
            self._updating_autostart = True
            enabled = self._is_autostart_enabled()
            self.autostart_toggle.setChecked(enabled)
        except Exception as e:
            logger.warning("初始化开机自启开关失败: %s", e)
        finally:
            self._updating_autostart = False

    def _on_autostart_toggled(self, state):
        """开机自启开关改变时触发"""
        if self._updating_autostart:
            return
        enabled = state == Qt.CheckState.Checked.value
        self._set_autostart_registry(enabled)
        self.autostart_toggled.emit(enabled)
        logger.info("[设置] 开机自启: %s", enabled)

    def update_autostart_state(self, enabled: bool):
        """外部同步开机自启状态（悬浮窗右键菜单调用）"""
        self._updating_autostart = True
        self.autostart_toggle.setChecked(enabled)
        self._updating_autostart = False


class PathCard(QWidget):
    """路径卡片组件"""
    
    def __init__(self, name, path, is_valid=True, on_browse=None, on_delete=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.path = path
        self.is_valid = is_valid
        self.on_browse_callback = on_browse
        self.on_delete_callback = on_delete
        self.init_ui()
    
    def init_ui(self):
        self.setObjectName("PathCard")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # 状态指示器
        self.status_icon = QLabel("✓" if self.is_valid else "✗")
        self.status_icon.setObjectName("StatusIcon")
        self.status_icon.setFixedWidth(20)
        layout.addWidget(self.status_icon)
        
        # 名称和路径容器
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        self.name_label = QLabel(self.name)
        self.name_label.setObjectName("CardNameLabel")
        info_layout.addWidget(self.name_label)
        
        self.path_label = QLabel(self.path)
        self.path_label.setObjectName("CardPathLabel")
        info_layout.addWidget(self.path_label)
        
        layout.addLayout(info_layout, 1)
        
        # 操作按钮
        browse_btn = QPushButton("浏览")
        browse_btn.setObjectName("CardButton")
        browse_btn.setFixedSize(60, 28)
        browse_btn.clicked.connect(self._on_browse_clicked)
        layout.addWidget(browse_btn)
        
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("CardDeleteButton")
        delete_btn.setFixedSize(60, 28)
        delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(delete_btn)
    
    def _on_browse_clicked(self):
        """浏览按钮点击"""
        if self.on_browse_callback:
            self.on_browse_callback(self)
    
    def _on_delete_clicked(self):
        """删除按钮点击"""
        if self.on_delete_callback:
            self.on_delete_callback(self)
    
    def update_path(self, new_path: str):
        """更新路径显示"""
        self.path = new_path
        self.path_label.setText(new_path)
        # 更新有效性
        from pathlib import Path
        self.is_valid = Path(new_path).exists() if new_path else False
        self.status_icon.setText("✓" if self.is_valid else "✗")


class AssetSection(SettingsSection):
    """资产设置区块"""
    
    def __init__(self, module_provider=None, parent=None):
        super().__init__("资产设置", "📦", parent)
        self.module_provider = module_provider
        self.asset_manager_logic = None
        self.setup_content()
        # 延迟加载资产管理器逻辑
        self._init_asset_manager_logic()
        # 加载当前配置
        self._load_current_paths()
    
    def _init_asset_manager_logic(self):
        """初始化资产管理器逻辑"""
        try:
            if not self.module_provider:
                return
            
            asset_module = self.module_provider.get_module("asset_manager")
            
            if asset_module:
                # ModuleAdapter 有 instance 属性，指向真正的模块实例
                if hasattr(asset_module, 'instance'):
                    module_instance = asset_module.instance
                    if hasattr(module_instance, 'logic'):
                        self.asset_manager_logic = module_instance.logic
                        logger.debug("成功获取资产管理器逻辑层")
                    else:
                        logger.warning("模块实例没有 logic 属性")
                else:
                    logger.warning("asset_module 没有 instance 属性")
            else:
                logger.warning("无法获取 asset_manager 模块")
        except Exception as e:
            logger.exception("初始化资产管理器逻辑失败: %s", e)
    
    def setup_content(self):
        # 资产库路径
        self.asset_lib_container = self.create_path_row("")
        self.asset_lib_input = self.asset_lib_container.findChild(QLineEdit)
        browse_btn = self.asset_lib_container.findChildren(QPushButton)[0]
        browse_btn.clicked.connect(self._browse_asset_library)
        self.add_setting_row("资产库路径", self.asset_lib_container, "存储所有资产文件的根目录")

        # 导入后删除源文件开关
        self.delete_source_toggle = QCheckBox("导入资产后自动删除源文件")
        self.delete_source_toggle.stateChanged.connect(self._on_delete_source_toggled)
        self.add_setting_row(
            "导入后删除源文件",
            self.delete_source_toggle,
            "开启后，资产导入成功后将自动删除原始压缩包或文件夹，无需每次手动确认。默认关闭（每次询问）。"
        )

        # 添加间距
        spacer = QWidget()
        spacer.setFixedHeight(8)
        self.content_layout.addWidget(spacer)
        
        # 预览工程标题
        preview_label = QLabel("预览工程")
        preview_label.setObjectName("SubSectionLabel")
        self.content_layout.addWidget(preview_label)
        
        # 预览工程卡片容器
        self.preview_cards_container = QWidget()
        self.preview_cards_layout = QVBoxLayout(self.preview_cards_container)
        self.preview_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_cards_layout.setSpacing(8)
        self.content_layout.addWidget(self.preview_cards_container)
        
        # 添加间距
        spacer_btn = QWidget()
        spacer_btn.setFixedHeight(8)
        self.content_layout.addWidget(spacer_btn)
        
        # 添加工程按钮
        add_btn = QPushButton("+ 添加预览工程")
        add_btn.setObjectName("AddProjectButton")
        add_btn.setFixedSize(140, 36)
        add_btn.clicked.connect(self._add_preview_project)
        self.content_layout.addWidget(add_btn)
    
    def _load_current_paths(self):
        """加载当前配置的路径"""
        try:
            if not self.asset_manager_logic:
                return
            
            # 加载资产库路径
            lib_path = self.asset_manager_logic.get_asset_library_path()
            if lib_path:
                self.asset_lib_input.setText(str(lib_path))

            # 加载删除源文件设置
            try:
                user_config = self.asset_manager_logic.config_manager.load_user_config()
                self.delete_source_toggle.blockSignals(True)
                self.delete_source_toggle.setChecked(
                    user_config.get("delete_source_after_import", False)
                )
                self.delete_source_toggle.blockSignals(False)
            except Exception as e:
                logger.warning("加载删除源文件设置失败: %s", e)
            
            # 加载预览工程列表
            self._load_preview_projects()
            
        except Exception as e:
            logger.warning("加载路径配置失败: %s", e)

    
    def _on_delete_source_toggled(self, state):
        """导入后删除源文件开关改变时触发"""
        if not self.asset_manager_logic:
            logger.warning("资产管理器未初始化，无法保存删除源文件设置")
            return
        
        enabled = state == Qt.CheckState.Checked.value
        try:
            config = self.asset_manager_logic.config_manager.load_user_config()
            config["delete_source_after_import"] = enabled
            self.asset_manager_logic.config_manager.save_user_config(
                config, backup_reason="update_delete_source"
            )
            mode_text = "自动删除" if enabled else "每次询问"
            logger.info("[资产设置] 导入后删除源文件: %s", mode_text)
        except Exception as e:
            logger.warning("保存删除源文件设置失败: %s", e)
            self.delete_source_toggle.blockSignals(True)
            self.delete_source_toggle.setChecked(not enabled)
            self.delete_source_toggle.blockSignals(False)
    
    def _load_preview_projects(self):
        """加载预览工程列表"""
        try:
            if not self.asset_manager_logic:
                return
            
            # 清空现有卡片
            while self.preview_cards_layout.count():
                item = self.preview_cards_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 从配置加载
            projects = self.asset_manager_logic.get_additional_preview_projects_with_names()
            
            for project in projects:
                name = project.get("name", "未命名工程")
                path = project.get("path", "")
                from pathlib import Path
                is_valid = Path(path).exists() if path else False
                
                # 创建卡片并连接回调函数
                card = PathCard(
                    name, 
                    path, 
                    is_valid,
                    on_browse=self._on_card_browse,
                    on_delete=self._on_card_delete
                )
                self.preview_cards_layout.addWidget(card)
                
        except Exception as e:
            logger.warning("加载预览工程失败: %s", e)
    
    def _browse_asset_library(self):
        """浏览并选择资产库路径"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择资产库文件夹",
            self.asset_lib_input.text() or "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self._save_asset_library_path(folder)
    
    def _save_asset_library_path(self, path_str: str):
        """保存资产库路径"""
        try:
            if not self.asset_manager_logic:
                logger.warning("资产管理器未初始化")
                return
            
            from pathlib import Path
            lib_path = Path(path_str.strip())
            
            if self.asset_manager_logic.set_asset_library_path(lib_path):
                self.asset_lib_input.setText(str(lib_path))
                logger.info("资产库路径已保存: %s", lib_path)
                
                # 刷新资产管理器UI
                self._refresh_asset_manager_ui()
            else:
                logger.warning("保存资产库路径失败")
                
        except Exception as e:
            logger.exception("保存资产库路径异常: %s", e)
    
    def _refresh_asset_manager_ui(self):
        """刷新资产管理器UI显示"""
        try:
            if not self.module_provider:
                return
            
            # 获取资产管理器模块
            asset_module = self.module_provider.get_module("asset_manager")
            if not asset_module:
                return
            
            # 获取UI实例
            if hasattr(asset_module, 'instance'):
                module_instance = asset_module.instance
                if hasattr(module_instance, 'ui') and module_instance.ui:
                    asset_ui = module_instance.ui
                    # 重置已加载标志，强制重新加载
                    if hasattr(asset_ui, '_assets_loaded'):
                        asset_ui._assets_loaded = False
                        logger.debug("已重置资产加载状态")
                    
                    # 刷新资产显示
                    if hasattr(asset_ui, 'load_assets_async'):
                        asset_ui.load_assets_async()
                        logger.debug("资产管理器UI已触发异步刷新")
                    elif hasattr(asset_ui, '_load_assets_async'):
                        asset_ui._load_assets_async()
                        logger.debug("资产管理器UI已直接刷新")
                    else:
                        logger.warning("资产管理器UI没有加载方法")
        except Exception as e:
            logger.exception("刷新资产管理器UI失败: %s", e)
    
    def _on_card_browse(self, card: 'PathCard'):
        """卡片浏览按钮回调"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择预览工程文件夹",
            card.path or "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            # 更新卡片显示
            card.update_path(folder)
            # 保存到配置
            self._update_preview_project(card.name, folder)
            logger.info("预览工程路径已更新: %s -> %s", card.name, folder)
    
    def _on_card_delete(self, card: 'PathCard'):
        """卡片删除按钮回调"""
        # 先从UI中删除卡片，避免重复点击
        self.preview_cards_layout.removeWidget(card)
        card.deleteLater()
        
        # 从配置中删除
        if self._delete_preview_project(card.name):
            logger.info("预览工程已删除: %s", card.name)
        else:
            logger.warning("删除预览工程失败: %s", card.name)
            # 即使失败也不恢复UI，因为可能是已经被删除了
    
    def _add_preview_project(self):
        """添加预览工程"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择预览工程文件夹",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            # TODO: 弹出命名对话框
            # 暂时使用文件夹名作为项目名
            from pathlib import Path
            name = Path(folder).name
            self._save_preview_project(folder, name)
    
    def _save_preview_project(self, path: str, name: str):
        """保存预览工程"""
        try:
            if not self.asset_manager_logic:
                return
            
            # 获取现有项目
            projects = self.asset_manager_logic.get_additional_preview_projects_with_names()
            
            # 添加新项目
            projects.append({"path": path, "name": name})
            
            # 保存配置
            if self.asset_manager_logic.set_additional_preview_projects_with_names(projects):
                logger.info("预览工程已添加: %s", name)
                # 重新加载显示
                self._load_preview_projects()
            else:
                logger.warning("保存预览工程失败")
                
        except Exception as e:
            logger.exception("保存预览工程异常: %s", e)
    
    def _update_preview_project(self, name: str, new_path: str) -> bool:
        """更新预览工程路径"""
        try:
            if not self.asset_manager_logic:
                return False
            
            # 获取现有项目
            projects = self.asset_manager_logic.get_additional_preview_projects_with_names()
            
            # 查找并更新
            updated = False
            for project in projects:
                if project.get("name") == name:
                    project["path"] = new_path
                    updated = True
                    break
            
            if not updated:
                return False
            
            # 保存配置
            return self.asset_manager_logic.set_additional_preview_projects_with_names(projects)
                
        except Exception as e:
            logger.exception("更新预览工程异常: %s", e)
            return False
    
    def _delete_preview_project(self, name: str) -> bool:
        """删除预览工程"""
        try:
            if not self.asset_manager_logic:
                return False
            
            # 获取现有项目
            projects = self.asset_manager_logic.get_additional_preview_projects_with_names()
            
            # 过滤掉要删除的项目
            new_projects = [p for p in projects if p.get("name") != name]
            
            if len(new_projects) == len(projects):
                # 没有找到要删除的项目
                return False
            
            # 保存配置
            return self.asset_manager_logic.set_additional_preview_projects_with_names(new_projects)
                
        except Exception as e:
            logger.exception("删除预览工程异常: %s", e)
            return False
    
    def create_path_row(self, default_path=""):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        path_edit = QLineEdit(default_path)
        path_edit.setObjectName("PathLineEdit")
        path_edit.setPlaceholderText("选择路径...")
        path_edit.setReadOnly(True)
        layout.addWidget(path_edit, 1)
        
        browse_btn = QPushButton("浏览")
        browse_btn.setObjectName("BrowseButton")
        browse_btn.setFixedWidth(80)
        layout.addWidget(browse_btn)
        
        return container


class SettingsWidget(QWidget):
    """设置界面（选项卡形式）"""
    
    def __init__(self, module_provider=None, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsWidget")
        self.module_provider = module_provider
        self.scroll_areas = []  # 保存所有滚动区域的引用
        self.general_section = None  # 保存常规设置区块的引用
        self.ai_assistant_section = None  # 保存 AI 助手设置区块的引用
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        tab_widget.setObjectName("SettingsTabWidget")
        
        # 常规选项卡（放在最前面）
        self.general_section = GeneralSection()
        general_tab = self.create_tab_page(self.general_section)
        tab_widget.addTab(general_tab, "常规")

        # 资产设置选项卡
        asset_tab = self.create_tab_page(AssetSection(self.module_provider))
        tab_widget.addTab(asset_tab, "资产设置")
        
        # AI助手选项卡
        self.ai_assistant_section = AIAssistantSection()
        ai_tab = self.create_tab_page(self.ai_assistant_section)
        tab_widget.addTab(ai_tab, "AI助手")
        
        # 监听标签页切换事件，切换到 AI 助手时重新加载配置
        tab_widget.currentChanged.connect(lambda index: self._on_tab_changed(index, tab_widget))
        
        main_layout.addWidget(tab_widget)
    
    def create_tab_page(self, section_widget):
        """创建选项卡页面"""
        page = QWidget()
        page.setObjectName("TabPage")
        
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setObjectName("SettingsScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 启用自动隐藏滚动条
        from core.utils.auto_hide_scrollbar import enable_auto_hide_scrollbar
        enable_auto_hide_scrollbar(scroll_area)
        
        scroll_content = QWidget()
        scroll_content.setObjectName("SettingsScrollContent")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        content_layout.addWidget(section_widget)
        content_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # 保存滚动区域引用
        self.scroll_areas.append(scroll_area)
        
        return page
    
    def refresh_scrollbar_style(self):
        """强制刷新所有滚动条样式（主题切换后调用）"""
        try:
            from PyQt6.QtWidgets import QApplication
            
            # 获取当前应用的样式表
            app = QApplication.instance()
            if not app:
                return
            
            current_stylesheet = app.styleSheet()
            
            # 强制刷新每个滚动区域
            for scroll_area in self.scroll_areas:
                # 临时设置空样式表，然后恢复，触发重绘
                scroll_area.setStyleSheet("")
                scroll_area.setStyleSheet(current_stylesheet)
                scroll_area.verticalScrollBar().setStyleSheet("")
                scroll_area.verticalScrollBar().setStyleSheet(current_stylesheet)
        except Exception as e:
            logger.warning("刷新滚动条样式失败: %s", e)
    
    def _on_tab_changed(self, index, tab_widget):
        """标签页切换事件处理
        
        Args:
            index: 当前标签页索引
            tab_widget: QTabWidget 实例
        """
        # AI 助手标签页的索引是 2（常规=0, 资产设置=1, AI助手=2）
        if index == 2 and self.ai_assistant_section:
            # 切换到 AI 助手标签页时，重新加载配置（丢弃未保存的修改）
            logger.info("[设置界面] 切换到 AI 助手标签页，重新加载配置")
            self.ai_assistant_section._load_config()
