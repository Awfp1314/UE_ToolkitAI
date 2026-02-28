# -*- coding: utf-8 -*-
"""
AI回复消息气泡组件 - ChatGPT风格
支持Markdown渲染、代码高亮和流式输出
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QTextBrowser, QWidget, QPushButton, QSizePolicy, QApplication
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QIcon, QPixmap, QPainterPath


class _TransparentTextBrowser(QTextBrowser):
    """QTextBrowser 子类，不消费滚轮事件，让它传播到父级 QScrollArea"""
    
    def wheelEvent(self, event):
        event.ignore()

# Markdown库
try:
    import markdown
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.tables import TableExtension
    from markdown.extensions.codehilite import CodeHiliteExtension
    MARKDOWN_AVAILABLE = True
    # Markdown库已加载
    pass
except ImportError as e:
    MARKDOWN_AVAILABLE = False
    # Markdown库加载失败
    pass

# Pygments用于代码高亮
try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False


def markdown_to_html(text, theme="dark"):
    """将Markdown文本转换为HTML，带自定义样式"""
    if not text:
        return '<div></div>'
    
    if not MARKDOWN_AVAILABLE:
        # Markdown库不可用，使用纯文本显示
        pass
        # 转义HTML特殊字符，保留换行
        import html as html_module
        escaped_text = html_module.escape(text)
        escaped_text = escaped_text.replace('\n', '<br>')
        return f'<div style="white-space: pre-wrap;">{escaped_text}</div>'
    
    # 预处理：修复列表格式
    import re
    
    # 1. 在冒号后面如果直接跟列表，添加空行
    text = re.sub(r':\n(\*|-)(\s+)', r':\n\n\1\2', text)
    
    # 2. 处理内联列表：冒号后直接跟 - 或 * 项目（同一行）
    # 例如："场景类：- 项目1 - 项目2" -> "场景类：\n\n- 项目1\n- 项目2"
    def expand_inline_list(match):
        prefix = match.group(1)  # 冒号前的内容
        marker = match.group(2)  # - 或 *
        items_str = match.group(3)  # 后续内容
        
        # 根据标记符分割（支持 - 和 *）
        # 智能分割：只在 "- 大写字母" 或 "- 中文" 处分割，避免误分割描述中的 " - "
        if marker == '-':
            # 匹配 " - " 后跟大写字母或中文的位置
            items = re.split(r'\s+-\s+(?=[A-Z\u4e00-\u9fa5])', items_str)
        else:
            # 匹配 " * " 后跟大写字母或中文的位置
            items = re.split(r'\s+\*\s+(?=[A-Z\u4e00-\u9fa5])', items_str)
        
        # 过滤空项
        items = [item.strip() for item in items if item.strip()]
        if items:
            # 构建标准markdown列表
            list_items = '\n' + marker + ' ' + f'\n{marker} '.join(items)
            result = f'{prefix}:\n{list_items}'
            return result
        return match.group(0)
    
    # 匹配：冒号后直接跟 - 或 *（单行内的内联列表）
    # 只匹配当前行，不跨行
    text = re.sub(r'([\u4e00-\u9fa5a-zA-Z0-9\s()（）]+)：\s*([-\*])\s+(.+)$', 
                  expand_inline_list, text, flags=re.MULTILINE)
    
    try:
        # 配置扩展
        extensions = [
            'fenced_code',
            'tables',
            'sane_lists'
        ]
        
        # 如果Pygments可用，启用代码高亮
        if PYGMENTS_AVAILABLE:
            extensions.append(CodeHiliteExtension(
                linenums=False,
                guess_lang=True,
                css_class='highlight'
            ))
        
        # 转换Markdown
        html = markdown.markdown(text, extensions=extensions)
        return html
    except Exception as e:
        # Markdown转换失败
        pass
        import traceback
        traceback.print_exc()
        # 转义HTML特殊字符
        import html as html_module
        escaped_text = html_module.escape(text)
        escaped_text = escaped_text.replace('\n', '<br>')
        return f'<div style="white-space: pre-wrap;">{escaped_text}</div>'


class AIMessageBubble(QFrame):
    """AI回复消息气泡 - ChatGPT风格，无气泡，居中显示"""
    
    # 添加信号
    regenerate_clicked = pyqtSignal()  # 重新生成按钮点击信号
    
    def __init__(self, message="", theme="dark", show_regenerate=True, parent=None):
        super().__init__(parent)
        self.message = message
        self.theme = theme
        self.show_regenerate = show_regenerate  # 是否显示重新生成按钮
        self._streaming = False  # 是否处于流式输出模式
        self._last_render_time = 0  # 上次渲染时间
        self._render_throttle_ms = 20  # 渲染节流时间（毫秒）
        
        # 延迟渲染定时器
        self._render_timer = QTimer()
        self._render_timer.timeout.connect(self._do_render)
        self._render_timer.setSingleShot(True)
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        self.setObjectName("AIMessageBubble")
        
        # 设置固定宽度780px（和旧项目一致）
        self.setFixedWidth(780)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 12, 0, 12)
        main_layout.setSpacing(0)
        
        # Markdown渲染器（使用自定义子类，让滚轮事件传播到父级 QScrollArea）
        self.text_browser = _TransparentTextBrowser()
        self.text_browser.setObjectName("AIMessageContent")
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setReadOnly(True)
        self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 需要时显示横向滚动条
        
        # 设置大小策略：宽度填满，高度自适应内容
        self.text_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # 使用WidgetWidth模式，让普通文本自动换行
        self.text_browser.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        
        # 设置光标样式（需要在viewport上设置）
        self.text_browser.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        
        # 安装事件过滤器以保持光标状态
        self.text_browser.viewport().installEventFilter(self)
        
        # 设置文档边距
        self.text_browser.document().setDocumentMargin(0)
        
        # 自动调整高度
        self.text_browser.document().contentsChanged.connect(self.adjust_height)
        
        main_layout.addWidget(self.text_browser)
        
        # 添加操作按钮容器（初始隐藏）
        self.action_buttons_container = QWidget()
        self.action_buttons_container.setObjectName("AIActionButtonsContainer")
        buttons_layout = QHBoxLayout(self.action_buttons_container)
        buttons_layout.setContentsMargins(0, 8, 0, 0)  # 顶部间距
        buttons_layout.setSpacing(8)
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # 复制按钮
        self.copy_button = QPushButton()
        self.copy_button.setObjectName("action_button")
        self.copy_button.setProperty("theme", self.theme)
        self.copy_button.setFixedSize(28, 28)
        self.copy_button.setToolTip("复制内容")
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.setFlat(False)  # 确保QSS背景颜色生效
        self.copy_button.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # 启用样式背景
        self.copy_button.setIcon(self._create_copy_icon())
        self.copy_button.setIconSize(QSize(18, 18))
        self.copy_button.clicked.connect(self.on_copy_clicked)
        buttons_layout.addWidget(self.copy_button)
        
        # 重新生成按钮（根据参数决定是否创建）
        if self.show_regenerate:
            self.regenerate_button = QPushButton()
            self.regenerate_button.setObjectName("action_button")
            self.regenerate_button.setProperty("theme", self.theme)
            self.regenerate_button.setFixedSize(28, 28)
            self.regenerate_button.setToolTip("重新生成回答")
            self.regenerate_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.regenerate_button.setFlat(False)  # 确保QSS背景颜色生效
            self.regenerate_button.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # 启用样式背景
            self.regenerate_button.setIcon(self._create_regenerate_icon())
            self.regenerate_button.setIconSize(QSize(18, 18))
            self.regenerate_button.clicked.connect(self.on_regenerate_clicked)
            buttons_layout.addWidget(self.regenerate_button)
        
        buttons_layout.addStretch(1)
        
        main_layout.addWidget(self.action_buttons_container)
        self.action_buttons_container.hide()  # 初始隐藏
        
        # 初始化显示
        if self.message:
            self.update_content()
    
    def set_theme(self, theme: str):
        """切换主题"""
        if self.theme == theme:
            return
        
        self.theme = theme
        self.update_content()
        
        # 重新创建按钮图标
        if hasattr(self, 'copy_button'):
            self.copy_button.setIcon(self._create_copy_icon())
            self.copy_button.setProperty("theme", theme)
        
        if hasattr(self, 'regenerate_button'):
            self.regenerate_button.setIcon(self._create_regenerate_icon())
            self.regenerate_button.setProperty("theme", theme)
    
    def append_text(self, text: str):
        """追加文本（流式输出）"""
        self.message += text
        
        # 启用流式模式
        if not self._streaming:
            self._streaming = True
        
        # 使用20ms节流机制，平衡性能和实时性
        import time
        current_time = time.time() * 1000  # 转换为毫秒
        
        if current_time - self._last_render_time >= self._render_throttle_ms:
            # 距离上次渲染已超过节流时间，立即渲染
            self._do_render()
            self._last_render_time = current_time
        else:
            # 还在节流期内，启动定时器延迟渲染
            if not self._render_timer.isActive():
                remaining_time = self._render_throttle_ms - (current_time - self._last_render_time)
                self._render_timer.start(int(max(1, remaining_time)))
    
    def set_text(self, text: str):
        """设置完整文本"""
        self.message = text
        self.update_content()
    
    def get_text(self) -> str:
        """获取当前文本"""
        return self.message
    
    def _do_render(self):
        """执行实际的渲染（节流后）"""
        self.update_content()
    
    def finalize(self):
        """完成流式输出，重新渲染整个内容
        
        在流式输出过程中，markdown可能不完整（如只有半个**），
        在输出完成后重新渲染可以确保正确显示
        """
        self._streaming = False
        # 停止渲染定时器
        if self._render_timer.isActive():
            self._render_timer.stop()
        # 最终渲染一次
        self.update_content()
        # 显示操作按钮
        self.action_buttons_container.show()
    
    def eventFilter(self, obj, event):
        """事件过滤器：确保光标始终为IBeam"""
        if obj == self.text_browser.viewport():
            # 鼠标进入时确保光标是IBeam
            if event.type() == event.Type.Enter:
                obj.setCursor(Qt.CursorShape.IBeamCursor)
            # 鼠标移动时确保光标是IBeam
            elif event.type() == event.Type.MouseMove:
                if obj.cursor().shape() != Qt.CursorShape.IBeamCursor:
                    obj.setCursor(Qt.CursorShape.IBeamCursor)
        return super().eventFilter(obj, event)
    
    def update_content(self):
        """更新显示内容"""
        # 生成HTML内容
        html_body = markdown_to_html(self.message, self.theme)
        
        # 根据主题选择CSS
        if self.theme == "dark":
            css = self._get_dark_theme_css()
        else:
            css = self._get_light_theme_css()
        
        # 组合完整的HTML
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{css}</style>
        </head>
        <body>{html_body}</body>
        </html>
        """
        
        # setHtml + adjust_height — scrollContentsBy 已被 _ChatScrollArea 阻断，
        # 不需要额外的 save/restore 逻辑
        self.text_browser.setHtml(full_html)
        self.text_browser.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        self.adjust_height()
    
    def adjust_height(self):
        """自动调整高度（简化版，和旧项目一致）"""
        # 确保文档宽度正确（气泡刚加入布局时 viewport 宽度可能为 0）
        vp_width = self.text_browser.viewport().width()
        if vp_width <= 0:
            vp_width = 740  # 780(bubble) - ~40(margins) 的估算值
        self.text_browser.document().setTextWidth(vp_width)
        doc_height = self.text_browser.document().size().height()
        self.text_browser.setFixedHeight(max(int(doc_height) + 10, 40))
    
    def _get_dark_theme_css(self) -> str:
        """获取深色主题的CSS样式"""
        return """
            body {
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
                font-size: 18px;
                font-weight: 500;
                line-height: 2.2em;
                color: #EDEDED;
                margin: 0;
                padding: 16px 20px;
                width: 100%;
                max-width: 100%;
                word-wrap: break-word;
                overflow-wrap: break-word;
                letter-spacing: 1px;
                -webkit-font-smoothing: antialiased;
                box-sizing: border-box;
            }
        
            h1, h2, h3, h4, h5, h6 {
                font-weight: 600;
                margin-top: 1.5em;
                margin-bottom: 1.2em;
                color: #ececf1;
                line-height: 1.5;
            }
            
            h1 { font-size: 1.8em; }
            h2 { font-size: 1.5em; }
            h3 { font-size: 1.3em; }
            
            p {
                margin: 1.2em 0;
                line-height: 2.2em;
            }
            
            ul, ol {
                margin: 1.2em 0;
                padding-left: 30px;
            }
            
            li {
                margin: 0.6em 0;
                line-height: 2.2em;
            }
            
            code {
                background-color: #2d2d2d;
                color: #e6db74;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
                font-size: 14px;
                font-weight: 400;
                letter-spacing: 0;
            }
            
            pre {
                background-color: #1E1E1E;
                border: none;
                border-radius: 8px;
                padding: 16px 20px;
                overflow-x: auto !important;
                overflow-y: auto !important;
                margin: 0.8em 0;
                width: 100%;
                max-width: 100%;
                max-height: 500px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
                white-space: pre !important;
                word-wrap: normal;
                box-sizing: border-box;
            }
            
            /* 代码块滚动条样式 - WebKit浏览器 */
            pre::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            
            pre::-webkit-scrollbar-track {
                background: #2d2d2d;
                border-radius: 4px;
            }
            
            pre::-webkit-scrollbar-thumb {
                background: #555;
                border-radius: 4px;
            }
            
            pre::-webkit-scrollbar-thumb:hover {
                background: #666;
            }
            
            pre code {
                background-color: transparent;
                padding: 0;
                color: #d4d4d4;
                font-size: 13.5px;
                font-weight: 400;
                line-height: 1.6;
                letter-spacing: 0;
                font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
                display: inline;
                white-space: pre !important;
                word-wrap: normal;
            }
            
            .highlight { background: #1E1E1E; border-radius: 8px; }
            .highlight .c { color: #6A9955; font-style: italic }
            .highlight .k { color: #C586C0 }
            .highlight .n { color: #d4d4d4 }
            .highlight .o { color: #d4d4d4 }
            .highlight .kd { color: #569CD6 }
            .highlight .kt { color: #4EC9B0 }
            .highlight .s { color: #CE9178 }
            .highlight .na { color: #9CDCFE }
            .highlight .nb { color: #4EC9B0 }
            .highlight .nc { color: #4EC9B0; font-weight: bold }
            .highlight .nf { color: #DCDCAA }
            .highlight .nn { color: #4EC9B0 }
            .highlight .nt { color: #569CD6 }
            .highlight .nv { color: #9CDCFE }
            .highlight .m { color: #B5CEA8 }
            .highlight .mi { color: #B5CEA8 }
            .highlight .s1 { color: #CE9178 }
            .highlight .s2 { color: #CE9178 }
            
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1.2em 0;
            }
            
            th, td {
                border: 1px solid #444;
                padding: 8px 12px;
                text-align: left;
            }
            
            th {
                background-color: #2d2d2d;
                font-weight: 600;
            }
            
            blockquote {
                border-left: 4px solid #569CD6;
                margin: 1.2em 0;
                padding-left: 16px;
                color: #b0b0b0;
            }
        """
    
    def _get_light_theme_css(self) -> str:
        """获取浅色主题的CSS样式"""
        return """
            body {
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
                font-size: 18px;
                font-weight: 500;
                line-height: 2.2em;
                color: #0D0D0D;
                margin: 0;
                padding: 16px 20px;
                width: 100%;
                max-width: 100%;
                word-wrap: break-word;
                overflow-wrap: break-word;
                letter-spacing: 1px;
                box-sizing: border-box;
            }
        
            h1, h2, h3, h4, h5, h6 {
                font-weight: 600;
                margin-top: 1.5em;
                margin-bottom: 1.2em;
                color: #1a1a1a;
                line-height: 1.5;
            }
            
            h1 { font-size: 1.8em; }
            h2 { font-size: 1.5em; }
            h3 { font-size: 1.3em; }
            
            p {
                margin: 1.2em 0;
                line-height: 2.2em;
            }
            
            ul, ol {
                margin: 1.2em 0;
                padding-left: 30px;
            }
            
            li {
                margin: 0.6em 0;
                line-height: 2.2em;
            }
            
            code {
                background-color: #f5f5f5;
                color: #d63384;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
                font-size: 14px;
                font-weight: 400;
            }
            
            pre {
                background-color: #f6f8fa;
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                padding: 16px 20px;
                overflow-x: auto !important;
                overflow-y: auto !important;
                margin: 0.8em 0;
                width: 100%;
                max-width: 100%;
                max-height: 500px;
                white-space: pre !important;
                word-wrap: normal;
                box-sizing: border-box;
            }
            
            /* 代码块滚动条样式 - WebKit浏览器 */
            pre::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            
            pre::-webkit-scrollbar-track {
                background: #e1e4e8;
                border-radius: 4px;
            }
            
            pre::-webkit-scrollbar-thumb {
                background: #c1c4c8;
                border-radius: 4px;
            }
            
            pre::-webkit-scrollbar-thumb:hover {
                background: #a1a4a8;
            }
            
            pre code {
                background-color: transparent;
                padding: 0;
                color: #24292e;
                font-size: 13.5px;
                font-weight: 400;
                line-height: 1.6;
                font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
                display: inline;
                white-space: pre !important;
                word-wrap: normal;
            }
            
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1.2em 0;
            }
            
            th, td {
                border: 1px solid #ddd;
                padding: 8px 12px;
                text-align: left;
            }
            
            th {
                background-color: #f5f5f5;
                font-weight: 600;
            }
            
            blockquote {
                border-left: 4px solid #0969da;
                margin: 1.2em 0;
                padding-left: 16px;
                color: #57606a;
            }
        """
    
    def _create_copy_icon(self):
        """创建复制图标（两个重叠的圆角正方形）- 与用户消息气泡一致"""
        # 使用更大的画布以获得更清晰的渲染
        size = 48
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 设置颜色和画笔
        color = QColor("#ececf1") if self.theme == "dark" else QColor("#2c2c2c")
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # 方块大小和位置
        box_size = 20
        corner_radius = 3
        offset = 7  # 两个矩形的偏移量
        
        # 绘制后面的方块（右下）- 只绘制右边和下边的L形
        back_x = 9 + offset
        back_y = 9 + offset
        
        path = QPainterPath()
        # 从右边中间开始，向上到右上角
        path.moveTo(back_x + box_size, back_y + box_size / 2)
        path.lineTo(back_x + box_size, back_y + corner_radius)
        # 右上角圆角
        path.arcTo(back_x + box_size - corner_radius * 2, back_y, 
                   corner_radius * 2, corner_radius * 2, 0, 90)
        # 移动到右下角（不绘制上边）
        path.moveTo(back_x + box_size, back_y + box_size / 2)
        path.lineTo(back_x + box_size, back_y + box_size - corner_radius)
        # 右下角圆角
        path.arcTo(back_x + box_size - corner_radius * 2, back_y + box_size - corner_radius * 2,
                   corner_radius * 2, corner_radius * 2, 0, -90)
        # 下边
        path.lineTo(back_x + corner_radius, back_y + box_size)
        # 左下角圆角
        path.arcTo(back_x, back_y + box_size - corner_radius * 2,
                   corner_radius * 2, corner_radius * 2, -90, -90)
        painter.drawPath(path)
        
        # 绘制前面的方块（左上）- 完整绘制
        painter.drawRoundedRect(10, 10, box_size, box_size, corner_radius, corner_radius)
        
        painter.end()
        return QIcon(pixmap)
    
    def _create_regenerate_icon(self):
        """创建重新生成图标（标准循环箭头 SVG）"""
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF
        
        color = "#ececf1" if self.theme == "dark" else "#2c2c2c"
        
        # 标准的重试/刷新箭头 SVG
        svg_data = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" 
             fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="1 4 1 10 7 10"/>
          <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
        </svg>'''
        
        size = 48
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        renderer = QSvgRenderer(svg_data.encode())
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # 居中绘制，留一点边距
        margin = 8
        renderer.render(painter, QRectF(margin, margin, size - margin * 2, size - margin * 2))
        painter.end()
        
        return QIcon(pixmap)
    
    def on_copy_clicked(self):
        """复制按钮点击"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.message)
        print(f"已复制: {self.message[:20]}...")
        
        # 暂时修改按钮文字以提示已复制
        original_icon = self.copy_button.icon()
        self.copy_button.setText("OK")
        self.copy_button.setIcon(QIcon())
        QTimer.singleShot(1000, lambda: (self.copy_button.setText(""), self.copy_button.setIcon(original_icon)))
    
    def on_regenerate_clicked(self):
        """重新生成按钮点击"""
        self.regenerate_clicked.emit()
    
    def hide_regenerate_button(self):
        """隐藏重新生成按钮"""
        if hasattr(self, 'regenerate_button') and self.regenerate_button:
            self.regenerate_button.hide()
    
    def show_regenerate_button(self):
        """显示重新生成按钮"""
        if hasattr(self, 'regenerate_button') and self.regenerate_button:
            self.regenerate_button.show()
