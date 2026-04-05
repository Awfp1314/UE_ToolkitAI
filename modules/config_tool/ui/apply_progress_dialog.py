# -*- coding: utf-8 -*-

"""
应用进度弹窗

参考 RenameProgressDialog 的实现：
- 显示配置名称和目标项目名称
- 列出所有应用阶段（版本验证、备份配置、复制配置文件、清理缓存、更新项目ID）
- 实现阶段状态图标（未开始、进行中、已完成）
- 实现旋转动画用于进行中状态
- 实现"后台执行"和"取消"按钮
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget
)
from PyQt6.QtCore import Qt, QTimer

from core.logger import get_logger

logger = get_logger(__name__)


class _SpinnerLabel(QLabel):
    """旋转加载图标（纯 CSS 动画占位，用定时器驱动文字旋转）"""
    _FRAMES = ["◐", "◓", "◑", "◒"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._idx = 0
        self.setText(self._FRAMES[0])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(120)

    def _tick(self):
        self._idx = (self._idx + 1) % len(self._FRAMES)
        self.setText(self._FRAMES[self._idx])

    def stop(self):
        self._timer.stop()


class ApplyProgressDialog(QDialog):
    """应用进度详情弹窗

    生命周期：
    - 应用开始前创建，可立即 show()
    - 应用过程中通过 set_stage_running/set_stage_done 驱动
    - 应用完成后通过 finish(success, message) 切换到结果状态
    """

    STAGE_NAMES = [
        "版本验证",
        "备份配置",
        "复制配置文件",
        "清理缓存",
        "更新项目ID"
    ]

    def __init__(self, config_name: str, target_project: str, parent=None):
        super().__init__(parent)
        self._config_name = config_name
        self._target_project = target_project
        self._total = len(self.STAGE_NAMES)
        self._spinners = {}   # stage_idx -> _SpinnerLabel
        self._status_icons = {}  # stage_idx -> QLabel
        self._finished = False
        self._cancelled = False

        self.setModal(False)
        self.setFixedWidth(400)
        self.setWindowTitle("应用进度")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._init_ui()

    def _init_ui(self):
        # 外层容器
        container = QWidget(self)
        container.setObjectName("ApplyProgressContainer")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(container)

        self._main = QVBoxLayout(container)
        self._main.setContentsMargins(28, 24, 28, 20)
        self._main.setSpacing(10)

        # ── 标题 ──
        title = QLabel("配置应用进行中")
        title.setObjectName("ApplyProgressTitle")
        self._main.addWidget(title)
        self._title_label = title

        summary = QLabel(f"{self._config_name}  →  {self._target_project}")
        summary.setObjectName("ApplyProgressSummary")
        self._main.addWidget(summary)

        self._main.addSpacing(6)

        # ── 阶段列表 ──
        for i in range(self._total):
            row = QHBoxLayout()
            row.setSpacing(10)

            # 状态图标（初始灰点）
            icon = QLabel("○")
            icon.setObjectName("ApplyStageIcon")
            icon.setFixedWidth(18)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("color: #555555; font-size: 14px;")
            self._status_icons[i] = icon
            row.addWidget(icon)

            stage_name = self.STAGE_NAMES[i]
            lbl = QLabel(f"阶段 {i+1}/{self._total} · {stage_name}")
            lbl.setObjectName("ApplyProgressStageLabel")
            lbl.setStyleSheet("color: #666666;")
            row.addWidget(lbl, 1)
            self._status_icons[i]._row_label = lbl  # 方便后续改色

            self._main.addLayout(row)

        self._main.addSpacing(8)

        # ── 结果区（初始隐藏）──
        self._result_widget = QWidget()
        result_layout = QVBoxLayout(self._result_widget)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(6)

        self._result_label = QLabel("")
        self._result_label.setObjectName("ApplyProgressResult")
        self._result_label.setWordWrap(True)
        result_layout.addWidget(self._result_label)

        self._result_widget.setVisible(False)
        self._main.addWidget(self._result_widget)

        # ── 按钮区 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        # 「后台执行」按钮：执行中显示，点击后隐藏弹窗
        self._btn_background = QPushButton("后台执行")
        self._btn_background.setObjectName("CancelButton")
        self._btn_background.setFixedSize(90, 32)
        self._btn_background.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_background.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_background.clicked.connect(self.hide)
        self._btn_background.setVisible(True)
        btn_layout.addWidget(self._btn_background)

        # 「取消」按钮：执行中显示
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setObjectName("CancelButton")
        self._btn_cancel.setFixedSize(80, 32)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        self._btn_cancel.setVisible(True)
        btn_layout.addWidget(self._btn_cancel)

        # 「关闭」按钮：完成后显示
        self._btn_close = QPushButton("关闭")
        self._btn_close.setObjectName("ApplyProgressBtnClose")
        self._btn_close.setFixedSize(80, 32)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.clicked.connect(self.accept)
        self._btn_close.setVisible(False)
        btn_layout.addWidget(self._btn_close)

        self._main.addLayout(btn_layout)

        self.adjustSize()

    def set_stage_running(self, stage_idx: int):
        """将指定阶段设置为运行中（旋转图标，文字高亮）"""
        icon_lbl = self._status_icons.get(stage_idx)
        if not icon_lbl:
            return
        # 替换为 spinner
        spinner = _SpinnerLabel()
        spinner.setObjectName("ApplyStageIcon")
        spinner.setFixedWidth(18)
        spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner.setStyleSheet("color: #4A9EFF; font-size: 14px;")
        self._spinners[stage_idx] = spinner

        # 在布局中替换旧图标
        for i in range(self._main.count()):
            item = self._main.itemAt(i)
            if item and item.layout():
                row_layout = item.layout()
                for j in range(row_layout.count()):
                    w = row_layout.itemAt(j).widget()
                    if w is icon_lbl:
                        row_layout.removeWidget(icon_lbl)
                        icon_lbl.hide()
                        row_layout.insertWidget(j, spinner)
                        break

        # 文字高亮
        if hasattr(icon_lbl, '_row_label'):
            icon_lbl._row_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")

        self._status_icons[stage_idx] = spinner  # 更新引用

    def set_stage_done(self, stage_idx: int):
        """将指定阶段设置为已完成（绿色对号）"""
        # 停止 spinner
        spinner = self._spinners.pop(stage_idx, None)
        if spinner:
            spinner.stop()
            # 替换回静态图标
            for i in range(self._main.count()):
                item = self._main.itemAt(i)
                if item and item.layout():
                    row_layout = item.layout()
                    for j in range(row_layout.count()):
                        w = row_layout.itemAt(j).widget()
                        if w is spinner:
                            row_layout.removeWidget(spinner)
                            spinner.hide()
                            done_icon = QLabel("✓")
                            done_icon.setObjectName("ApplyStageIcon")
                            done_icon.setFixedWidth(18)
                            done_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                            done_icon.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")
                            row_layout.insertWidget(j, done_icon)
                            # 更新行文字颜色
                            for k in range(row_layout.count()):
                                lw = row_layout.itemAt(k).widget()
                                if isinstance(lw, QLabel) and lw is not done_icon:
                                    lw.setStyleSheet("color: #4CAF50;")
                            break
        else:
            # 直接修改静态图标
            icon_lbl = self._status_icons.get(stage_idx)
            if icon_lbl and isinstance(icon_lbl, QLabel):
                icon_lbl.setText("✓")
                icon_lbl.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")
                if hasattr(icon_lbl, '_row_label'):
                    icon_lbl._row_label.setStyleSheet("color: #4CAF50;")

    def finish(self, success: bool, message: str = ""):
        """应用完成：显示结果区和操作按钮"""
        self._finished = True
        
        if success:
            self._title_label.setText("配置应用完成")
            self._result_label.setText(message or "配置已成功应用到目标项目")
            self._result_label.setStyleSheet("color: #4CAF50;")
        else:
            self._title_label.setText("配置应用失败")
            self._result_label.setText(message or "配置应用过程中发生错误")
            self._result_label.setStyleSheet("color: #F44336;")

        self._result_widget.setVisible(True)
        self._btn_background.setVisible(False)
        self._btn_cancel.setVisible(False)
        self._btn_close.setVisible(True)
        self.adjustSize()

        # 若弹窗不可见则强制弹出
        if not self.isVisible():
            self.show()
            self._center_on_parent()

    def _on_cancel_clicked(self):
        """取消按钮被点击"""
        self._cancelled = True
        self.reject()

    def is_cancelled(self) -> bool:
        """是否已取消"""
        return self._cancelled

    def _center_on_parent(self):
        """居中显示"""
        p = self.parent()
        if p:
            pg = p.geometry()
            x = pg.x() + (pg.width() - self.width()) // 2
            y = pg.y() + (pg.height() - self.height()) // 2
            self.move(x, y)
