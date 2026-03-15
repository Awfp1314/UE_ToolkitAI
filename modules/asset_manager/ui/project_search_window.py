# -*- coding: utf-8 -*-
"""UE工程搜索窗口 - 资产管理器的二级窗口"""

import sys
import json
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QScrollArea, QLineEdit, QComboBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPoint, QTimer
from PyQt6.QtGui import (
    QFont, QKeySequence, QShortcut, QPixmap, QPainter, 
    QColor, QPainterPath, QLinearGradient
)

from core.logger import get_logger

logger = get_logger(__name__)


class ProgressButton(QPushButton):
    """带进度条的按钮组件"""
    progress_finished = pyqtSignal()
    progress_changed = pyqtSignal(float)
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._progress = 0.0
        self._is_loading = False
        self._auto_mode = False
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_progress)
    
    def start_progress(self, duration_ms=2000):
        """开始自动进度动画"""
        self._progress = 0.0
        self._is_loading = True
        self._auto_mode = True
        self._progress_step = 1.0 / (duration_ms / 33.33)  # 30fps
        self._timer.start(33)  # 30fps，视觉上足够流畅
        self.update()
    
    def set_progress(self, progress: float):
        """手动设置进度"""
        self._auto_mode = False
        self._timer.stop()
        self._progress = max(0.0, min(1.0, progress))
        self._is_loading = self._progress < 1.0
        
        if self._progress >= 1.0:
            self._progress = 1.0
            self._is_loading = False
            self.progress_finished.emit()
        
        self.progress_changed.emit(self._progress)
        self.update()
    
    def stop_progress(self):
        """停止进度动画"""
        self._timer.stop()
        self._is_loading = False
        self._progress = 0.0
        self._auto_mode = False
        self.update()
    
    def reset_progress(self):
        """重置进度"""
        self.stop_progress()
    
    def get_progress(self) -> float:
        """获取当前进度"""
        return self._progress
    
    def update_button_text(self, text: str):
        """更新按钮文本"""
        self.setText(text)
    
    def _update_progress(self):
        """更新进度"""
        if not self._auto_mode:
            return
        
        if self._progress < 1.0:
            self._progress += self._progress_step
            if self._progress >= 1.0:
                self._progress = 1.0
                self._timer.stop()
                self._is_loading = False
                self._auto_mode = False
                self.progress_finished.emit()
            self.progress_changed.emit(self._progress)
            self.update()
    
    def paintEvent(self, a0):
        """自定义绘制 - 绘制进度条"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        if self._progress > 0:
            radius = 10.0  # 与按钮的圆角半径一致
            progress_width = rect.width() * self._progress
            
            progress_rect = QRectF(0, 0, progress_width, rect.height())
            path = QPainterPath()
            path.addRoundedRect(progress_rect, radius, radius)
            
            gradient = QLinearGradient(0, 0, progress_width, 0)
            # 使用蓝色渐变，在深色和浅色主题下都清晰可见
            gradient.setColorAt(0, QColor(74, 158, 255, 80))
            gradient.setColorAt(1, QColor(74, 158, 255, 120))
            
            painter.fillPath(path, gradient)
        
        painter.end()
        super().paintEvent(a0)


class RoundedThumbnail(QWidget):
    """圆角缩略图控件"""
    def __init__(self, w=200, h=130, r=10, parent=None):
        super().__init__(parent)
        self.setFixedSize(w, h)
        self.r, self._pixmap = r, None
        self.bg, self.tc = "rgba(0,0,0,0.3)", "#606060"
    
    def setPixmap(self, p):
        self._pixmap = p if p and not p.isNull() else None
        self.update()
    
    def set_theme(self, is_dark):
        self.bg = "rgba(0,0,0,0.3)" if is_dark else "rgba(255,255,255,0.5)"
        self.tc = "#606060" if is_dark else "#a0a0a0"
        self.update()
    
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.r, self.r)
        p.setClipPath(path)
        
        if self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)
        else:
            p.fillRect(self.rect(), QColor(self.bg))
            p.setPen(QColor(self.tc))
            p.setFont(QFont("Segoe UI Emoji", 32))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "📁")
        p.end()


class ProjectCard(QFrame):
    """工程卡片"""
    open_req = pyqtSignal(str)
    import_req = pyqtSignal(str)  # 导入请求信号，传递工程路径
    
    def __init__(self, name, path, ver, mod, theme, thumb_path=None, category="默认", parent=None):
        super().__init__(parent)
        self.name, self.path, self.ver, self.mod, self.theme = name, path, ver, mod, theme
        self.thumb_path = thumb_path
        self.category = category
        self.setObjectName("ProjectCard")
        self.setFixedSize(180, 220)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        l = QVBoxLayout(self)
        l.setContentsMargins(0,0,0,0)
        l.setSpacing(0)
        
        # 缩略图区
        ts = QWidget()
        ts.setObjectName("ProjectCardThumb")
        ts.setFixedHeight(120)
        tl = QVBoxLayout(ts)
        tl.setContentsMargins(6,6,6,6)
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb = RoundedThumbnail(168,108,0,self)
        
        # 加载缩略图
        if thumb_path and Path(thumb_path).exists():
            try:
                pixmap = QPixmap(thumb_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(168, 108, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    if scaled.width() > 168 or scaled.height() > 108:
                        x = (scaled.width() - 168) // 2
                        y = (scaled.height() - 108) // 2
                        scaled = scaled.copy(x, y, 168, 108)
                    self.thumb.setPixmap(scaled)
            except:
                pass
        
        tl.addWidget(self.thumb)
        l.addWidget(ts)
        
        # 版本徽标 - 放在缩略图右上角（蓝色，类似资产卡片）
        self.version_badge = QLabel(f"UE {ver}")
        self.version_badge.setObjectName("VersionBadge")
        self.version_badge.setParent(self.thumb)
        self.version_badge.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                background-color: rgba(0, 122, 204, 0.85);
                border-radius: 3px;
                padding: 3px 6px;
            }
        """)
        self.version_badge.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.version_badge.setCursor(Qt.CursorShape.ArrowCursor)
        self.version_badge.setFixedSize(self.version_badge.sizeHint())
        # 定位到右上角
        self.version_badge.move(168 - 8 - self.version_badge.width(), 8)
        
        # 分类标签 - 放在缩略图左下角（替换原来的版本标签）
        self.category_label = QLabel(category)
        self.category_label.setObjectName("CategoryLabel")
        self.category_label.setParent(self.thumb)
        self.category_label.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                font-size: 11px;
                font-weight: 600;
                background-color: #000000;
                border-radius: 0px;
                padding: 4px 10px;
            }
        """)
        self.category_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.category_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.category_label.setFixedSize(self.category_label.sizeHint())
        self.category_label.move(8, 108 - 8 - self.category_label.height())
        
        # 信息区
        iw = QWidget()
        iw.setObjectName("ProjectCardInfo")
        il = QVBoxLayout(iw)
        il.setContentsMargins(10,8,10,10)
        il.setSpacing(6)
        
        nl = QLabel(name)
        nl.setObjectName("ProjectCardName")
        nl.setWordWrap(True)
        nl.setFixedHeight(32)
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        nl.setFont(f)
        il.addWidget(nl)
        
        # 修改时间
        if mod:
            ml = QHBoxLayout()
            ml.setSpacing(6)
            tl = QLabel(mod)
            tl.setObjectName("ProjectCardTime")
            f3 = QFont()
            f3.setPointSize(8)
            tl.setFont(f3)
            ml.addWidget(tl)
            ml.addStretch()
            il.addLayout(ml)
        
        # 导入按钮
        self.import_btn = ProgressButton("▶  导入工程")
        self.import_btn.setObjectName("ProjectCardImportButton")
        self.import_btn.setFixedHeight(32)
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.import_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.import_btn.clicked.connect(self._on_import_clicked)
        il.addWidget(self.import_btn)
        
        l.addWidget(iw)
        self.set_theme(theme)
    
    def _on_import_clicked(self):
        """导入按钮点击事件"""
        # 发射导入请求信号，传递工程路径
        self.import_req.emit(self.path)
    
    def _reset_import_button(self):
        """重置导入按钮"""
        self.import_btn.reset_progress()
        self.import_btn.update_button_text("▶  导入工程")
    
    def start_import_animation(self):
        """启动导入动画"""
        self.import_btn.set_progress(0.0)
        self.import_btn.update_button_text("0%")
    
    def update_import_progress(self, progress: float):
        """更新导入进度
        
        Args:
            progress: 进度值 0.0-1.0
        """
        self.import_btn.set_progress(progress)
        percentage = int(progress * 100)
        self.import_btn.update_button_text(f"{percentage}%")
    
    def finish_import_animation(self):
        """完成导入动画"""
        self.import_btn.set_progress(1.0)
        self.import_btn.update_button_text("✓ 导入成功")
    
    def set_theme(self, t):
        self.theme = t
        self.thumb.set_theme(t == "dark")


class ProjectScanner(QThread):
    """工程扫描器"""
    found = pyqtSignal(list)
    prog = pyqtSignal(str)
    
    def __init__(self, paths=None, exclude_paths=None):
        super().__init__()
        self.paths = paths or [
            Path.home()/"Documents",
            Path.home()/"Desktop", 
            Path.home()/"Downloads",
            Path("C:/Users")/Path.home().name/"Documents",
            Path("D:/"),
            Path("E:/"),
            Path("F:/"),
            Path("G:/"),
        ]
        self.exclude_paths = exclude_paths or []
        self.projs = []
        self.recent_projects_order = self._load_recent_projects_order()
    
    def _load_recent_projects_order(self):
        """从 UE 编辑器配置中加载最近打开的项目顺序
        
        Returns:
            dict: {项目路径: 修改时间戳}，时间戳越大表示越近修改
        """
        # 暂时使用修改时间作为排序依据
        # UE 的 RecentProjects.json 配置文件路径不确定，且格式可能因版本而异
        return {}
    
    def run(self):
        self.projs = []
        scanned_paths = set()
        
        for p in self.paths:
            if not p.exists():
                continue
            
            try:
                resolved = p.resolve()
                if resolved in scanned_paths:
                    continue
                scanned_paths.add(resolved)
            except:
                pass
            
            self.prog.emit(f"扫描: {p}")
            self._scan(p, maxd=4)
        
        self.prog.emit(f"完成，找到 {len(self.projs)} 个工程")
        self.found.emit(self.projs)
    
    def _is_excluded(self, path: Path) -> bool:
        """检查路径是否在排除列表中"""
        if not self.exclude_paths:
            return False
            
        try:
            resolved_path = path.resolve()
            for exclude_path in self.exclude_paths:
                try:
                    resolved_exclude = Path(exclude_path).resolve()
                    # 检查 path 是否在排除路径下（排除路径是 path 的父目录/祖先目录）
                    try:
                        # Python 3.9+ 方法
                        if resolved_path.is_relative_to(resolved_exclude):
                            logger.debug(f"路径 {path} 被排除（匹配规则: {exclude_path}）")
                            return True
                    except AttributeError:
                        # Python 3.8 兼容方法
                        if resolved_path == resolved_exclude or resolved_exclude in resolved_path.parents:
                            logger.debug(f"路径 {path} 被排除（匹配规则: {exclude_path}）")
                            return True
                except Exception as e:
                    logger.debug(f"解析排除路径失败: {exclude_path}, 错误: {e}")
                    continue
        except PermissionError:
            # 系统目录访问被拒绝是正常的，不需要警告
            logger.debug(f"无权限访问路径: {path}")
            pass
        except Exception as e:
            logger.debug(f"解析路径失败: {path}, 错误: {e}")
            pass
        return False
    
    def _scan(self, d, depth=0, maxd=4):
        if depth >= maxd:
            return
        try:
            for item in d.iterdir():
                if not item.is_dir():
                    continue
                
                # 检查是否在排除路径中 - 优先检查
                if self._is_excluded(item):
                    logger.debug(f"跳过排除路径: {item}")
                    continue
                
                # 跳过系统目录和隐藏目录
                if item.name.startswith('.') or item.name.startswith('$'):
                    continue
                name_lower = item.name.lower()
                if name_lower in [
                    'system volume information', 'windows', 'program files',
                    'program files (x86)', 'programdata', '$recycle.bin',
                    'recovery', 'msocache', 'boot', 'perflogs',
                    'appdata', 'node_modules', '.git', '__pycache__',
                    'venv', '.venv', 'env', '.env'
                ]:
                    continue
                
                # 跳过预览工程目录
                if name_lower in ['preview', 'samples', 'templates', 'engine', 'marketplace', 'plugins']:
                    continue
                
                # 检查是否为预览工程
                item_path_lower = str(item).lower()
                if any(keyword in item_path_lower for keyword in ['preview', 'sample', 'template', 'engine/content', 'marketplace']):
                    continue
                
                ups = list(item.glob("*.uproject"))
                if ups:
                    up = ups[0]
                    ver = self._ver(up)
                    stat = up.stat()
                    mt = datetime.fromtimestamp(stat.st_mtime)
                    thumb = self._get_thumbnail(item)
                    
                    # 获取最近打开时间（通过 Saved 目录下的文件判断）
                    recent_order = self._get_last_opened_time(item)
                    
                    # 读取工程分类（从 .UeToolkitconfig/project.json）
                    category = self._get_project_category(item)
                    
                    self.projs.append({
                        'name': item.name, 
                        'path': str(item), 
                        'version': ver, 
                        'modified': mt.strftime("%Y-%m-%d"),
                        'recent_order': recent_order,  # 最近打开时间戳（数字越大越近）
                        'thumbnail': thumb,
                        'category': category  # 工程分类
                    })
                    self.prog.emit(f"找到: {item.name}")
                else:
                    self._scan(item, depth+1, maxd)
        except:
            pass
    
    def _get_project_category(self, project_dir: Path) -> str:
        """读取工程分类
        
        从工程目录下的 .UeToolkitconfig/project.json 读取分类信息
        
        Args:
            project_dir: 工程目录路径
            
        Returns:
            str: 工程分类，默认为"默认"
        """
        try:
            config_file = project_dir / ".UeToolkitconfig" / "project.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('category', '默认')
        except Exception:
            pass
        return '默认'
    
    def _get_last_opened_time(self, project_dir: Path) -> int:
        """获取工程最近打开时间
        
        通过检查 Saved 目录下的文件来判断工程最近打开时间：
        1. 优先检查 Saved/Logs/*.log（每次启动都会更新）
        2. 其次检查 Saved/Config/Windows/EditorPerProjectUserSettings.ini
        3. 最后使用 .uproject 文件的修改时间作为后备
        
        Args:
            project_dir: 工程目录路径
            
        Returns:
            int: 时间戳（秒），越大表示越近打开
        """
        try:
            saved_dir = project_dir / "Saved"
            if not saved_dir.exists():
                # 没有 Saved 目录，使用 .uproject 文件时间
                uproject = list(project_dir.glob("*.uproject"))[0]
                return int(uproject.stat().st_mtime)
            
            # 1. 检查日志文件（最可靠）
            logs_dir = saved_dir / "Logs"
            if logs_dir.exists():
                log_files = list(logs_dir.glob("*.log"))
                if log_files:
                    # 找到最新的日志文件
                    latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                    return int(latest_log.stat().st_mtime)
            
            # 2. 检查编辑器配置文件
            config_file = saved_dir / "Config" / "Windows" / "EditorPerProjectUserSettings.ini"
            if config_file.exists():
                return int(config_file.stat().st_mtime)
            
            # 3. 后备方案：使用 .uproject 文件时间
            uproject = list(project_dir.glob("*.uproject"))[0]
            return int(uproject.stat().st_mtime)
            
        except Exception:
            # 出错时返回 0（排在最后）
            return 0
    
    def _get_thumbnail(self, proj_dir):
        """获取工程缩略图"""
        try:
            saved_dir = proj_dir / "Saved"
            if not saved_dir.exists():
                return None
            
            imgs = list(saved_dir.glob("*.png")) + list(saved_dir.glob("*.jpg")) + list(saved_dir.glob("*.jpeg"))
            if imgs:
                latest = max(imgs, key=lambda p: p.stat().st_mtime)
                return str(latest)
        except:
            pass
        return None
    
    def _ver(self, f):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                d = json.load(fp)
                v = d.get('EngineAssociation', '')
                if v:
                    p = v.split('.')
                    if len(p) >= 2:
                        return f"{p[0]}.{p[1]}"
                return "Unknown"
        except:
            return "Unknown"


class ProjectSearchWindow(QWidget):
    """工程搜索窗口"""
    
    # 新增：工程选择信号（用于选择模式）
    project_selected = pyqtSignal(str)
    
    def __init__(self, parent=None, asset_name: str = "", logic=None, mode: str = "import", 
                 package_type=None, engine_version: str = "", asset_path=None):
        """初始化工程搜索窗口
        
        Args:
            parent: 父窗口
            asset_name: 要导入的资产名称（导入模式使用）
            logic: 资产管理逻辑层引用（导入模式使用）
            mode: 窗口模式，"import"=导入资产模式，"select"=选择工程模式
            package_type: 资产包装类型（用于插件过滤）
            engine_version: 资产引擎版本（用于插件过滤）
            asset_path: 资产路径（用于提取插件原名）
        """
        super().__init__(parent)
        # 检测当前主题
        try:
            from core.utils.style_system import get_current_theme
            self.dark = get_current_theme() != "modern_light"
        except Exception:
            self.dark = True
        self.projs = []
        self.all = []
        self.cards = []
        self.drag_pos = QPoint()
        self.scanner = None  # 扫描线程引用
        self.asset_name = asset_name  # 要导入的资产名称
        self.logic = logic  # 资产管理逻辑层引用
        self.mode = mode  # 窗口模式
        self.package_type = package_type  # 资产包装类型
        self.engine_version = engine_version  # 资产引擎版本
        self.asset_path = asset_path  # 资产路径
        
        self.setWindowTitle("请选择工程")
        self.resize(820, 650)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 加载 QSS 样式
        self._apply_theme_style()
        
        # 主容器
        container = QWidget()
        container.setObjectName("ProjectSearchContainer")
        
        ml = QVBoxLayout(self)
        ml.setContentsMargins(0,0,0,0)
        ml.addWidget(container)
        
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0,0,0,0)
        cl.setSpacing(0)
        
        # 自定义标题栏
        tb = self._create_title_bar()
        cl.addWidget(tb)
        
        # 内容区
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20,15,20,20)
        content_layout.setSpacing(15)
        
        # 提示信息栏（根据资产类型显示不同提示）
        if self.package_type:
            from ..logic.asset_model import PackageType
            pkg_type_str = self.package_type.value if hasattr(self.package_type, 'value') else str(self.package_type)
            
            tip_widget = QWidget()
            tip_widget.setObjectName("ProjectSearchTipArea")
            tip_layout = QHBoxLayout(tip_widget)
            tip_layout.setContentsMargins(12, 10, 12, 10)
            tip_layout.setSpacing(10)
            
            # 图标
            icon_label = QLabel("ℹ️")
            icon_label.setStyleSheet("font-size: 16px;")
            tip_layout.addWidget(icon_label)
            
            # 提示文本
            tip_text = QLabel()
            tip_text.setWordWrap(True)
            tip_text.setObjectName("ProjectSearchTipText")
            
            if pkg_type_str.lower() == 'plugin':
                tip_text.setText("💡 提示：导入插件后需要重启项目才能在编辑器中看到插件")
            elif pkg_type_str.lower() == 'content':
                tip_text.setText("💡 提示：资产包将直接复制到项目的 Content 目录，无需重启项目")
            elif pkg_type_str.lower() == 'project':
                tip_text.setText("💡 提示：将导入工程资产 Content 文件夹下的资产到目标工程")
            
            tip_layout.addWidget(tip_text, 1)
            
            # 样式
            tip_widget.setStyleSheet("""
                QWidget#ProjectSearchTipArea {
                    background-color: rgba(74, 158, 255, 0.1);
                    border-left: 3px solid #4a9eff;
                    border-radius: 4px;
                }
                QLabel#ProjectSearchTipText {
                    color: #4a9eff;
                    font-size: 13px;
                }
            """)
            
            content_layout.addWidget(tip_widget)
        
        # 过滤栏
        fw = QWidget()
        fw.setObjectName("ProjectSearchFilterArea")
        fl = QHBoxLayout(fw)
        fl.setContentsMargins(20, 10, 20, 20)
        fl.setSpacing(15)
        
        # 搜索框
        self.si = QLineEdit()
        self.si.setPlaceholderText("搜索工程...")
        self.si.setFixedHeight(36)
        self.si.setMaximumWidth(200)
        self.si.setObjectName("ProjectSearchInput")
        self.si.textChanged.connect(self._filter)
        fl.addWidget(self.si)
        
        # 分类筛选下拉框
        self.category_filter = QComboBox()
        self.category_filter.setFixedHeight(36)
        self.category_filter.setMinimumWidth(120)
        self.category_filter.setMaximumWidth(180)
        self.category_filter.setObjectName("ProjectSearchVersionFilter")  # 使用与版本筛选相同的样式
        self.category_filter.addItem("全部分类")
        self.category_filter.currentTextChanged.connect(self._filter)
        fl.addWidget(self.category_filter)
        
        # 版本选择框（插件导入时隐藏）
        self.vc = QComboBox()
        self.vc.addItems(["所有版本","UE 5.4","UE 5.3","UE 5.2","UE 5.1"])
        self.vc.setFixedHeight(36)
        self.vc.setMinimumWidth(120)
        self.vc.setMaximumWidth(180)
        self.vc.setObjectName("ProjectSearchVersionFilter")
        self.vc.currentTextChanged.connect(self._filter)
        
        # 检测是否为插件、资产包或工程类型，如果是则隐藏版本选择框
        is_plugin_or_content_or_project = False
        if self.package_type:
            from ..logic.asset_model import PackageType
            pkg_type_str = self.package_type.value if hasattr(self.package_type, 'value') else str(self.package_type)
            is_plugin_or_content_or_project = pkg_type_str.lower() in ['plugin', 'content', 'project']
        
        if not is_plugin_or_content_or_project:
            fl.addWidget(self.vc)
        
        # 弹性空间
        fl.addStretch()
        
        # 刷新按钮
        rb = QPushButton("刷新")
        rb.setObjectName("ProjectSearchRefreshButton")
        rb.setFixedHeight(36)
        rb.setCursor(Qt.CursorShape.PointingHandCursor)
        rb.clicked.connect(self._scan)
        fl.addWidget(rb)
        content_layout.addWidget(fw)
        
        # 结果统计
        self.rl = QLabel("正在扫描...")
        self.rl.setObjectName("ProjectSearchResultLabel")
        content_layout.addWidget(self.rl)
        
        # 工程列表
        sa = QScrollArea()
        sa.setObjectName("ProjectSearchScrollArea")
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.lc = QWidget()
        self.lc.setObjectName("ProjectSearchList")
        self.ll = QGridLayout(self.lc)
        self.ll.setContentsMargins(0,0,0,0)
        self.ll.setHorizontalSpacing(12)
        self.ll.setVerticalSpacing(12)
        self.ll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        for i in range(4):
            self.ll.setColumnStretch(i, 0)
        self.ll.setColumnStretch(4, 1)
        
        sa.setWidget(self.lc)
        content_layout.addWidget(sa, 1)
        
        cl.addWidget(content)
        
        # 窗口居中显示
        self._center_window()
        
        self._scan()
    
    def _center_window(self):
        """将窗口居中显示 - 优先相对于主窗口居中"""
        import logging
        _logger = logging.getLogger(__name__)
        
        main_window = None
        try:
            app = QApplication.instance()
            if app:
                # 优先用 activeWindow
                active = app.activeWindow()
                _logger.info(f"[居中调试] activeWindow={active}, class={active.__class__.__name__ if active else 'None'}")
                if active and active is not self and active.isVisible():
                    main_window = active
                
                # 回退：遍历顶层窗口，找 UEMainWindow
                if not main_window:
                    for widget in app.topLevelWidgets():
                        _logger.info(f"[居中调试] topLevel: class={widget.__class__.__name__}, visible={widget.isVisible()}, isWindow={widget.isWindow()}, geo={widget.geometry()}")
                        if widget is self or not widget.isVisible() or not widget.isWindow():
                            continue
                        class_name = widget.__class__.__name__
                        if class_name == "UEMainWindow":
                            main_window = widget
                            break
                    
                    # 再回退：找最大的可见窗口
                    if not main_window:
                        for widget in app.topLevelWidgets():
                            if widget is self or not widget.isVisible() or not widget.isWindow():
                                continue
                            if main_window is None or widget.width() * widget.height() > main_window.width() * main_window.height():
                                main_window = widget
        except Exception as e:
            _logger.error(f"[居中调试] 异常: {e}")

        _logger.info(f"[居中调试] 最终 main_window={main_window}, class={main_window.__class__.__name__ if main_window else 'None'}")
        _logger.info(f"[居中调试] self.size=({self.width()}, {self.height()})")

        if main_window:
            mg = main_window.geometry()
            _logger.info(f"[居中调试] main geometry: x={mg.x()}, y={mg.y()}, w={mg.width()}, h={mg.height()}")
            x = mg.x() + (mg.width() - self.width()) // 2
            y = mg.y() + (mg.height() - self.height()) // 2
            _logger.info(f"[居中调试] 计算位置: x={x}, y={y}, move to ({max(0, x)}, {max(0, y)})")
            self.move(max(0, x), max(0, y))
        else:
            screen = self.screen()
            if screen:
                sg = screen.geometry()
                x = (sg.width() - self.width()) // 2
                y = (sg.height() - self.height()) // 2
                _logger.info(f"[居中调试] 屏幕居中: x={sg.x() + x}, y={sg.y() + y}")
                self.move(sg.x() + x, sg.y() + y)
    
    def _create_title_bar(self):
        """创建自定义标题栏"""
        tb = QWidget()
        tb.setObjectName("ProjectSearchTitleBar")
        tb.setFixedHeight(50)
        
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(20,0,10,0)
        
        # 标题
        title = QLabel("请选择工程")
        title.setObjectName("ProjectSearchTitleText")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        tl.addWidget(title)
        
        tl.addStretch()
        
        # 最小化按钮
        min_btn = QPushButton("−")
        min_btn.setObjectName("ProjectSearchMinButton")
        min_btn.setFixedSize(36,36)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.clicked.connect(self.showMinimized)
        tl.addWidget(min_btn)
        
        # 最大化/还原按钮
        max_btn = QPushButton("□")
        max_btn.setObjectName("ProjectSearchMaxButton")
        max_btn.setFixedSize(36,36)
        max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        max_btn.clicked.connect(self._toggle_maximize)
        tl.addWidget(max_btn)
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setObjectName("ProjectSearchCloseButton")
        close_btn.setFixedSize(36,36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        tl.addWidget(close_btn)
        
        return tb
    
    def _toggle_maximize(self):
        """切换最大化"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
    
    def mousePressEvent(self, e):
        """鼠标按下"""
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() <= 50:
            self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, e):
        """鼠标移动"""
        if e.buttons() == Qt.MouseButton.LeftButton and not self.drag_pos.isNull():
            self.move(e.globalPosition().toPoint() - self.drag_pos)
    
    def mouseDoubleClickEvent(self, e):
        """双击标题栏最大化"""
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() <= 50:
            self._toggle_maximize()
    
    def showEvent(self, event):
        """窗口显示事件 - 确保窗口显示后再居中"""
        super().showEvent(event)
        # 延迟执行居中，确保窗口几何信息已经就绪
        QTimer.singleShot(0, self._center_window)
    
    def _scan(self):
        self.rl.setText("正在扫描...")
        for c in self.cards:
            c.deleteLater()
        self.cards.clear()
        
        # 获取需要排除的路径
        exclude_paths = self._get_excluded_paths()
        
        s = ProjectScanner(exclude_paths=exclude_paths)
        s.found.connect(self._found)
        s.prog.connect(self._prog)
        s.start()
        self.scanner = s
    
    def _get_excluded_paths(self):
        """获取需要排除的路径列表"""
        exclude_paths = []
        
        try:
            from core.services import config_service
            asset_config = config_service.get_module_config("asset_manager") or {}
            
            # 1. 获取资产库路径（从 asset_libraries 数组读取）
            asset_libraries = asset_config.get("asset_libraries", [])
            for lib in asset_libraries:
                lib_path = lib.get("path", "")
                if lib_path:
                    exclude_paths.append(lib_path)
                    logger.debug(f"排除资产库: {lib_path}")
            
            # 2. 获取当前资产库路径（兼容旧配置）
            current_library = asset_config.get("current_asset_library", "")
            if current_library:
                exclude_paths.append(current_library)
                logger.debug(f"排除当前资产库: {current_library}")
            
            # 3. 获取预览工程路径
            preview_projects = asset_config.get("preview_projects", [])
            for proj in preview_projects:
                preview_path = proj.get("path", "")
                if preview_path:
                    exclude_paths.append(preview_path)
                    logger.debug(f"排除预览工程: {preview_path}")
            
            logger.info(f"工程扫描排除路径列表: {exclude_paths}")
            
        except Exception as e:
            logger.error(f"获取排除路径失败: {e}", exc_info=True)
        
        return exclude_paths
    
    def _found(self, ps):
        self.all = ps
        self.projs = ps
        
        # 加载分类列表到下拉框
        self._load_categories()
        
        # 如果是插件或资产包类型，自动过滤版本
        if self.package_type and self.engine_version:
            from ..logic.asset_model import PackageType
            pkg_type_str = self.package_type.value if hasattr(self.package_type, 'value') else str(self.package_type)
            
            if pkg_type_str.lower() == 'plugin':
                # 插件必须严格匹配版本
                filtered = []
                for p in ps:
                    project_version = p.get('version', '')
                    # 严格匹配版本（如 "5.4" 匹配 "5.4"）
                    if project_version and self.engine_version in project_version:
                        filtered.append(p)
                self.projs = filtered
                logger.info(f"插件版本筛选: 需要 UE {self.engine_version}，筛选后剩余 {len(filtered)} 个工程")
            
            elif pkg_type_str.lower() == 'content':
                # 资产包可以向上兼容（可以导入到相同或更高版本的工程）
                filtered = []
                try:
                    # 解析资产包的版本号（如 "5.4" -> [5, 4]）
                    asset_version_parts = [int(x) for x in self.engine_version.split('.')]
                    
                    for p in ps:
                        project_version = p.get('version', '')
                        if not project_version:
                            continue
                        
                        try:
                            # 解析工程版本号
                            project_version_parts = [int(x) for x in project_version.split('.')]
                            
                            # 比较版本号：工程版本 >= 资产包版本
                            if project_version_parts >= asset_version_parts:
                                filtered.append(p)
                        except (ValueError, AttributeError):
                            # 版本号解析失败，跳过
                            continue
                    
                    self.projs = filtered
                    logger.info(f"资产包版本筛选: 需要 UE {self.engine_version} 或更高版本，筛选后剩余 {len(filtered)} 个工程")
                except (ValueError, AttributeError) as e:
                    # 资产包版本号解析失败，不进行筛选
                    logger.warning(f"资产包版本号解析失败: {self.engine_version}, 错误: {e}")
            
            elif pkg_type_str.lower() == 'project':
                # 工程资产的 Content 可以向上兼容（类似资产包）
                filtered = []
                try:
                    # 解析工程资产的版本号（如 "5.4" -> [5, 4]）
                    asset_version_parts = [int(x) for x in self.engine_version.split('.')]
                    
                    for p in ps:
                        project_version = p.get('version', '')
                        if not project_version:
                            continue
                        
                        try:
                            # 解析目标工程版本号
                            project_version_parts = [int(x) for x in project_version.split('.')]
                            
                            # 比较版本号：目标工程版本 >= 工程资产版本
                            if project_version_parts >= asset_version_parts:
                                filtered.append(p)
                        except (ValueError, AttributeError):
                            # 版本号解析失败，跳过
                            continue
                    
                    self.projs = filtered
                    logger.info(f"工程资产版本筛选: 需要 UE {self.engine_version} 或更高版本，筛选后剩余 {len(filtered)} 个工程")
                except (ValueError, AttributeError) as e:
                    # 工程资产版本号解析失败，不进行筛选
                    logger.warning(f"工程资产版本号解析失败: {self.engine_version}, 错误: {e}")
        
        # 更新版本选择框 - 基于搜索到的工程版本
        self._update_version_filter()
        
        # 应用当前排序
        self._sort()
        self.rl.setText(f"找到 {len(self.projs)} 个工程")
    
    def _load_categories(self):
        """从工程列表中提取所有分类并加载到下拉框"""
        categories = set()
        for p in self.all:
            cat = p.get('category', '默认')
            if cat:
                categories.add(cat)
        
        # 保存当前选择
        current = self.category_filter.currentText()
        
        # 更新下拉框
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("全部分类")
        for cat in sorted(categories):
            self.category_filter.addItem(cat)
        
        # 恢复选择
        if current and current != "全部分类":
            idx = self.category_filter.findText(current)
            if idx >= 0:
                self.category_filter.setCurrentIndex(idx)
        
        self.category_filter.blockSignals(False)
    
    def _prog(self, m):
        self.rl.setText(m)
    
    def _refresh(self):
        for c in self.cards:
            c.deleteLater()
        self.cards.clear()
        
        while self.ll.count():
            i = self.ll.takeAt(0)
            if i.widget():
                i.widget().deleteLater()
        
        for index, project in enumerate(self.projs):
            c = ProjectCard(
                project['name'], 
                project['path'], 
                project.get('version','Unknown'), 
                project.get('modified',''), 
                "dark" if self.dark else "light",
                thumb_path=project.get('thumbnail'),
                category=project.get('category', '默认')
            )
            c.open_req.connect(self._open)
            
            # 根据模式设置不同的按钮文字和行为
            if self.mode == "select":
                c.import_btn.setText("▶  选择此工程")
                c.import_req.connect(self._on_select_project)  # 选择模式
            else:
                c.import_req.connect(self._on_import_project)  # 导入模式
            
            row = index // 4
            col = index % 4
            self.ll.addWidget(c, row, col)
            self.cards.append(c)
        
        self.rl.setText(f"找到 {len(self.projs)} 个工程")
    
    def _update_version_filter(self):
        """根据搜索到的工程版本更新版本选择框"""
        # 收集所有唯一的版本
        versions = set()
        for project in self.all:
            version = project.get('version', '')
            if version:
                versions.add(version)
        
        # 排序版本（按版本号降序）
        sorted_versions = sorted(versions, reverse=True)
        
        # 保存当前选择
        current_selection = self.vc.currentText()
        
        # 清空并重新填充版本选择框
        self.vc.blockSignals(True)  # 临时阻止信号，避免触发筛选
        self.vc.clear()
        self.vc.addItem("所有版本")
        for version in sorted_versions:
            self.vc.addItem(version)
        
        # 恢复之前的选择（如果还存在）
        index = self.vc.findText(current_selection)
        if index >= 0:
            self.vc.setCurrentIndex(index)
        else:
            self.vc.setCurrentIndex(0)  # 默认选择"所有版本"
        
        self.vc.blockSignals(False)  # 恢复信号
    
    def _filter(self):
        st = self.si.text().lower()
        vf = self.vc.currentText()
        cf = self.category_filter.currentText()
        
        f = []
        for p in self.all:
            if st and st not in p['name'].lower() and st not in p['path'].lower():
                continue
            if vf != "所有版本" and p.get('version','') not in vf:
                continue
            if cf != "全部分类" and p.get('category', '默认') != cf:
                continue
            f.append(p)
        
        self.projs = f
        self._refresh()
    
    def _sort(self):
        """按最近打开时间排序（降序）"""
        # 按 recent_order（最近打开时间戳）排序，数字越大越靠前（越近打开）
        self.projs.sort(key=lambda x: x.get('recent_order', 0), reverse=True)
        self._refresh()
    
    def _open(self, pp):
        pp = Path(pp)
        uf = list(pp.glob("*.uproject"))
        if uf:
            import subprocess
            import sys
            try:
                if sys.platform == "win32":
                    # Windows: 使用 os.startfile 打开 .uproject 文件
                    import os
                    os.startfile(str(uf[0]))
                    print(f"打开: {pp}")
                else:
                    # macOS/Linux: 使用 subprocess.Popen
                    subprocess.Popen([str(uf[0])], shell=False)
                    print(f"打开: {pp}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法打开: {e}")
    
    def _on_select_project(self, project_path: str):
        """处理工程选择请求（选择模式）"""
        # 发射选择信号
        self.project_selected.emit(project_path)
    
    def _on_import_project(self, project_path: str):
        """处理工程导入请求"""
        if not self.logic or not self.asset_name:
            return
        
        # 检查目标工程是否正在运行
        from pathlib import Path
        target_project = Path(project_path)
        
        # 检查是否有 .uproject 文件被占用（说明 UE 编辑器正在运行）
        uproject_files = list(target_project.glob("*.uproject"))
        if uproject_files:
            try:
                # 尝试以独占模式打开 .uproject 文件
                with open(uproject_files[0], 'r+') as f:
                    pass
            except PermissionError:
                # 文件被占用，提示用户
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "工程正在运行",
                    f"目标工程正在 UE 编辑器中打开。\n\n"
                    f"导入资产时需要覆盖同名文件，如果编辑器正在使用这些文件，可能会导致导入失败。\n\n"
                    f"建议：先关闭 UE 编辑器，再导入资产。\n\n"
                    f"工程路径：{project_path}",
                    QMessageBox.StandardButton.Ok
                )
                return
            except Exception:
                # 其他错误忽略，继续导入
                pass
        
        # 查找资产
        asset = None
        for a in self.logic.assets:
            if a.name == self.asset_name:
                asset = a
                break
        
        if not asset:
            return
        
        # 查找对应的卡片
        target_card = None
        for card in self.cards:
            if card.path == project_path:
                target_card = card
                break
        
        if not target_card:
            return
        
        # 启动导入动画
        target_card.start_import_animation()
        
        # 在线程中执行导入
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class ImportThread(QThread):
            finished = pyqtSignal(bool)
            progress_update = pyqtSignal(float)  # 进度更新信号 0.0-1.0
            
            def __init__(self, logic, asset, target_path, package_type, asset_path):
                super().__init__()
                self.logic = logic
                self.asset = asset
                self.target_path = target_path
                self.package_type = package_type
                self.asset_path = asset_path
            
            def run(self):
                try:
                    from pathlib import Path
                    from ..logic.asset_model import PackageType
                    target_project = Path(self.target_path)
                    
                    # 创建进度包装器，将文件级进度映射到0-90%范围
                    def copy_progress_wrapper(current, total, message):
                        if total > 0:
                            # 将复制进度映射到0-90%范围
                            progress = (current / total) * 0.9  # 90%的进度范围
                            self.progress_update.emit(progress)
                    
                    # 判断是否为插件类型
                    is_plugin = False
                    is_others = False
                    if self.package_type:
                        pkg_type_str = self.package_type.value if hasattr(self.package_type, 'value') else str(self.package_type)
                        is_plugin = pkg_type_str.lower() == 'plugin'
                        is_others = pkg_type_str.lower() == 'others'
                    
                    if is_plugin:
                        # 插件导入逻辑：复制到 Plugins 文件夹
                        plugins_folder = self.asset_path / "Plugins"
                        if plugins_folder.exists() and plugins_folder.is_dir():
                            # 获取插件原名（Plugins 文件夹下的第一个子文件夹）
                            plugin_folders = [f for f in plugins_folder.iterdir() if f.is_dir()]
                            if plugin_folders:
                                plugin_name = plugin_folders[0].name
                                source_plugin = plugins_folder / plugin_name
                                target_plugin = target_project / "Plugins" / plugin_name
                                
                                # 复制整个插件目录
                                success = self.logic._file_ops.safe_copytree(
                                    source_plugin,
                                    target_plugin,
                                    progress_callback=copy_progress_wrapper
                                )
                            else:
                                success = False
                        else:
                            success = False
                            
                    elif is_others:
                        # 其他资源导入逻辑：从 Others 文件夹递归复制所有内容直接到目标工程的 Content/ 下
                        # 结构：Others/原始文件名/Models|Textures/ → Content/原始文件名/Models|Textures/
                        others_folder = self.asset_path / "Others"
                        if others_folder.exists() and others_folder.is_dir():
                            target_base = target_project / "Content"
                            
                            logger.info(f"其他资源导入: 从 {others_folder} 复制所有内容到 {target_base}")
                            
                            # 确保目标目录存在
                            target_base.mkdir(parents=True, exist_ok=True)
                            
                            # 递归复制 Others 文件夹下的所有内容
                            success = True
                            items = list(others_folder.iterdir())
                            
                            if len(items) == 0:
                                logger.error("Others 文件夹为空")
                                success = False
                            else:
                                # 计算总大小（用于更准确的进度）
                                total_size = 0
                                for item in items:
                                    if item.is_file():
                                        total_size += item.stat().st_size
                                    elif item.is_dir():
                                        for subitem in item.rglob('*'):
                                            if subitem.is_file():
                                                total_size += subitem.stat().st_size
                                
                                copied_size = 0
                                
                                for item in items:
                                    target_path = target_base / item.name
                                    
                                    # 创建进度包装器（基于字节大小）
                                    def item_progress_wrapper(current, total, message):
                                        if total_size > 0:
                                            # 计算当前项目的进度贡献
                                            item_progress = (current / total) if total > 0 else 0
                                            # 计算总体进度
                                            overall_progress = (copied_size + item_progress * total) / total_size * 0.9
                                            self.progress_update.emit(overall_progress)
                                    
                                    if item.is_dir():
                                        item_success = self.logic._file_ops.safe_copytree(
                                            item, target_path, progress_callback=item_progress_wrapper
                                        )
                                        # 更新已复制大小
                                        if item_success:
                                            for subitem in item.rglob('*'):
                                                if subitem.is_file():
                                                    copied_size += subitem.stat().st_size
                                    else:
                                        item_success = self.logic._file_ops.safe_copy_file(
                                            item, target_path, progress_callback=item_progress_wrapper
                                        )
                                        # 更新已复制大小
                                        if item_success:
                                            copied_size += item.stat().st_size
                                    
                                    if not item_success:
                                        success = False
                                        logger.error(f"其他资源导入失败: {item} -> {target_path}")
                                        break
                        else:
                            logger.error(f"Others 文件夹不存在: {others_folder}")
                            success = False
                    
                    else:
                        # 资产包/工程资产导入逻辑：导入 Content 文件夹内的实际资产
                        # 判断是否为工程资产
                        is_project_asset = False
                        if self.package_type:
                            pkg_type_str = self.package_type.value if hasattr(self.package_type, 'value') else str(self.package_type)
                            is_project_asset = pkg_type_str.lower() == 'project'
                        
                        if is_project_asset:
                            # 工程资产：实际工程在 Project 子文件夹下的某个工程文件夹中
                            # 结构：资产路径/Project/工程文件夹/Content/
                            project_folder = self.asset.path / "Project"
                            
                            if project_folder.exists() and project_folder.is_dir():
                                # 查找 Project 文件夹下的第一个包含 .uproject 的子文件夹
                                ue_project_folder = None
                                for item in project_folder.iterdir():
                                    if item.is_dir():
                                        # 检查是否包含 .uproject 文件
                                        uproject_files = list(item.glob("*.uproject"))
                                        if uproject_files:
                                            ue_project_folder = item
                                            break
                                
                                if ue_project_folder:
                                    content_folder = ue_project_folder / "Content"
                                    
                                    if content_folder.exists() and content_folder.is_dir():
                                        # 复制 Content 文件夹内的所有内容到目标工程的 Content 文件夹
                                        success = True
                                        content_items = list(content_folder.iterdir())
                                        total_items = len(content_items)
                                        
                                        logger.info(f"工程资产导入: 从 {content_folder} 复制 {total_items} 个项目到 {target_project / 'Content'}")
                                        
                                        for idx, item in enumerate(content_items):
                                            target_path = target_project / "Content" / item.name
                                            
                                            # 创建进度包装器
                                            def item_progress_wrapper(current, total, message):
                                                if total > 0:
                                                    # 计算总体进度：(已完成项目 + 当前项目进度) / 总项目数
                                                    overall_progress = ((idx + current / total) / total_items) * 0.9
                                                    self.progress_update.emit(overall_progress)
                                            
                                            if item.is_dir():
                                                item_success = self.logic._file_ops.safe_copytree(
                                                    item, target_path, progress_callback=item_progress_wrapper
                                                )
                                            else:
                                                item_success = self.logic._file_ops.safe_copy_file(
                                                    item, target_path, progress_callback=item_progress_wrapper
                                                )
                                            
                                            if not item_success:
                                                success = False
                                                logger.error(f"工程资产导入失败: {item} -> {target_path}")
                                                break
                                    else:
                                        logger.error(f"工程资产 Content 文件夹不存在: {content_folder}")
                                        success = False
                                else:
                                    logger.error(f"在 {project_folder} 下未找到包含 .uproject 的工程文件夹")
                                    success = False
                            else:
                                logger.error(f"工程资产 Project 文件夹不存在: {project_folder}")
                                success = False
                        else:
                            # 资产包：Content 文件夹在资产根目录下
                            content_folder = self.asset.path / "Content"
                            
                            if content_folder.exists() and content_folder.is_dir():
                                # 新结构：复制 Content 文件夹内的所有内容到目标工程的 Content 文件夹
                                success = True
                                content_items = list(content_folder.iterdir())
                                total_items = len(content_items)
                                
                                for idx, item in enumerate(content_items):
                                    target_path = target_project / "Content" / item.name
                                    
                                    # 创建进度包装器
                                    def item_progress_wrapper(current, total, message):
                                        if total > 0:
                                            # 计算总体进度：(已完成项目 + 当前项目进度) / 总项目数
                                            overall_progress = ((idx + current / total) / total_items) * 0.9
                                            self.progress_update.emit(overall_progress)
                                    
                                    if item.is_dir():
                                        item_success = self.logic._file_ops.safe_copytree(
                                            item, target_path, progress_callback=item_progress_wrapper
                                        )
                                    else:
                                        item_success = self.logic._file_ops.safe_copy_file(
                                            item, target_path, progress_callback=item_progress_wrapper
                                        )
                                    
                                    if not item_success:
                                        success = False
                                        break
                            else:
                                # 兼容旧结构：直接复制整个资产文件夹（仅用于没有 Content 文件夹的旧资产包）
                                source_folder_name = self.asset.path.name
                                logger.warning(f"使用旧结构导入: {self.asset.path} -> {target_project / 'Content' / source_folder_name}")
                                success = self.logic._file_ops.safe_copytree(
                                    self.asset.path,
                                    target_project / "Content" / source_folder_name,
                                    progress_callback=copy_progress_wrapper
                                )
                    
                    # 复制完成，更新到90%（剩余10%留给finish_import_animation）
                    if success:
                        self.progress_update.emit(0.9)  # 90%
                    
                    self.finished.emit(success)
                except Exception as e:
                    self.finished.emit(False)
        
        # 创建并启动线程，传递 package_type 和 asset_path
        self.import_thread = ImportThread(self.logic, asset, project_path, self.package_type, self.asset_path)
        
        def on_progress(progress):
            # 更新卡片进度
            target_card.update_import_progress(progress)
        
        def on_finished(success):
            if success:
                # 完成导入动画
                target_card.finish_import_animation()
                # 1秒后重置按钮并关闭窗口
                QTimer.singleShot(1000, lambda: self._finish_import(target_card))
        
        self.import_thread.progress_update.connect(on_progress)
        self.import_thread.finished.connect(on_finished)
        self.import_thread.start()
    
    def _finish_import(self, card):
        """完成导入，重置按钮并关闭窗口"""
        card._reset_import_button()
        self.close()
    
    def set_theme(self, is_dark: bool):
        """设置主题"""
        self.dark = is_dark
        self._apply_theme_style()
        for c in self.cards:
            c.set_theme("dark" if self.dark else "light")
    
    def _apply_theme_style(self):
        """应用主题样式"""
        try:
            from core.utils.style_system import style_system
            theme_name = "modern_dark" if self.dark else "modern_light"
            style_system.apply_to_widget(self, theme_name)
        except Exception as e:
            # 如果样式系统不可用，使用备用样式
            pass
    
    def toggle(self):
        self.dark = not self.dark
        self._apply_theme_style()
        for c in self.cards:
            c.set_theme("dark" if self.dark else "light")
        print(f"✓ {'深色' if self.dark else '浅色'}主题")
    
    def closeEvent(self, event):
        """窗口关闭事件 - 清理扫描线程和导入线程"""
        # 停止扫描线程
        if self.scanner and self.scanner.isRunning():
            # 先尝试等待线程自然结束
            if not self.scanner.wait(500):
                # 如果500ms内没有结束，强制终止
                self.scanner.terminate()
                self.scanner.wait(1000)
        
        # 停止导入线程
        if hasattr(self, 'import_thread') and self.import_thread.isRunning():
            if not self.import_thread.wait(500):
                self.import_thread.terminate()
                self.import_thread.wait(1000)
        
        # 清理所有卡片
        for c in self.cards:
            c.deleteLater()
        self.cards.clear()
        
        # 接受关闭事件
        event.accept()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = ProjectSearchWindow()
    w.show()
    s = QShortcut(QKeySequence("Ctrl+T"), w)
    s.activated.connect(w.toggle)
    print("UE工程搜索窗口\n快捷键: Ctrl+T")
    sys.exit(app.exec())
