"""
测试运行器 - 可视化测试界面
让测试变得简单易懂！
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QTextEdit,
    QPushButton, QLabel, QSplitter, QProgressBar, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestStatus(Enum):
    """测试状态"""
    NOT_RUN = "未运行"
    RUNNING = "运行中"
    PASSED = "通过"
    FAILED = "失败"
    SKIPPED = "跳过"


@dataclass
class TestResult:
    """测试结果"""
    name: str
    status: TestStatus
    duration: float = 0.0
    error_message: str = ""
    traceback: str = ""


class TestCategory:
    """测试分类"""
    THREAD_MANAGEMENT = "🧵 线程管理测试"
    INTEGRATION = "🔗 集成测试"
    OTHER = "⚙️ 功能测试"


# 测试名称映射 - 把文件名翻译成友好的中文描述
TEST_NAME_MAP = {
    # Thread Management 测试
    'test_thread_manager': '线程管理器 - 核心功能测试',
    'test_worker': '工作线程 - Worker 测试',
    'test_thread_monitor': '线程监控器 - 监控功能测试',
    'test_thread_configuration': '线程配置 - 配置管理测试',
    'test_thread_cleanup': '线程清理 - 资源清理测试',
    'test_thread_pool_backpressure': '线程池背压 - 流量控制测试',
    'test_timeout_mechanism': '超时机制 - 超时处理测试',
    'test_cancellation_token_injection': '取消令牌 - 任务取消测试',
    'test_thread_service': '线程服务 - ThreadService 测试',
    'test_cleanup_contract': '清理契约 - 清理接口测试',
    'test_shutdown_orchestrator': '关闭编排器 - 优雅关闭测试',
    'test_shutdown_sequence': '关闭序列 - 关闭顺序测试',
    'test_app_manager_shutdown': '应用管理器 - 关闭流程测试',

    # 集成测试
    'test_config_service': '配置服务 - ConfigService 集成测试',
    'test_service_singleton': '服务单例 - 单例模式测试',
    'test_thread_service': '线程服务 - ThreadService 集成测试',

    # 其他功能测试
    'test_migration_validator': '迁移验证器 - QThread 违规检测',
    'test_feature_flags': '功能开关 - Feature Flags 测试',
    'test_module_interface': '模块接口 - 模块接口测试',
    'test_asset_manager_lazy_loading': '资产管理器 - 懒加载测试',
    'test_lazy_asset_loader': '懒加载器 - 资产懒加载测试',
    'test_lru_cache': 'LRU 缓存 - 缓存功能测试',
    'test_memory_retrieval_accuracy': '记忆检索 - AI 记忆准确性测试',
    'test_function_calling_coordinator': '函数调用协调器 - 协调器测试',
    'test_streaming_buffer_manager': '流式缓冲 - 缓冲管理器测试',
    'test_tool_status_display': '工具状态显示 - UI 状态测试',
    'test_error_handler': '错误处理器 - 错误处理测试',
    'test_file_operations': '文件操作 - 文件处理测试',
    'test_log_analyzer': '日志分析器 - 日志分析测试',
    'test_safe_print': '安全打印 - 打印功能测试',
    'test_pytest_setup': 'Pytest 设置 - 测试环境测试',
    'test_performance_regression': '性能回归 - 性能测试',
    'test_performance_validation': '性能验证 - 性能验证测试',
}


def get_friendly_test_name(test_file_name: str) -> str:
    """获取友好的测试名称"""
    return TEST_NAME_MAP.get(test_file_name, test_file_name)


class TestCollector:
    """测试收集器 - 扫描并分类所有测试"""
    
    def __init__(self, tests_dir: Path):
        self.tests_dir = tests_dir
        self.tests: Dict[str, List[Path]] = {
            TestCategory.THREAD_MANAGEMENT: [],
            TestCategory.INTEGRATION: [],
            TestCategory.OTHER: []
        }
    
    def collect(self):
        """收集所有测试文件"""
        # Thread Management 测试
        thread_patterns = [
            'test_thread_*.py', 'test_worker.py', 'test_cancellation_*.py',
            'test_cleanup_*.py', 'test_shutdown_*.py', 'test_app_manager_shutdown.py'
        ]
        
        for pattern in thread_patterns:
            for test_file in self.tests_dir.glob(pattern):
                if test_file.is_file():
                    self.tests[TestCategory.THREAD_MANAGEMENT].append(test_file)
        
        # 集成测试
        integration_dir = self.tests_dir / 'integration'
        if integration_dir.exists():
            for test_file in integration_dir.glob('test_*.py'):
                self.tests[TestCategory.INTEGRATION].append(test_file)
        
        # 其他测试
        for test_file in self.tests_dir.glob('test_*.py'):
            if test_file.is_file():
                # 排除已经分类的测试
                if (test_file not in self.tests[TestCategory.THREAD_MANAGEMENT] and
                    test_file not in self.tests[TestCategory.INTEGRATION]):
                    self.tests[TestCategory.OTHER].append(test_file)
        
        return self.tests


class TestRunner(QThread):
    """测试运行器 - 在后台运行测试"""
    
    # 信号
    test_started = pyqtSignal(str)  # 测试开始
    test_finished = pyqtSignal(str, TestResult)  # 测试完成
    all_finished = pyqtSignal(dict)  # 所有测试完成
    
    def __init__(self, test_files: List[Path]):
        super().__init__()
        self.test_files = test_files
        self.results: Dict[str, TestResult] = {}
    
    def run(self):
        """运行测试"""
        import pytest
        import time

        for test_file in self.test_files:
            test_name = test_file.stem
            self.test_started.emit(test_name)

            start_time = time.time()

            try:
                # 运行单个测试文件
                # 使用 pytest.main 运行测试
                result_code = pytest.main([
                    str(test_file),
                    '-v',  # 详细输出
                    '--tb=short',  # 简短的错误信息
                    '-p', 'no:warnings',  # 不显示警告
                    '--capture=no'  # 不捕获输出
                ])

                duration = time.time() - start_time

                # 解析结果
                if result_code == 0:
                    # 所有测试通过
                    status = TestStatus.PASSED
                    error_msg = ""
                elif result_code == 1:
                    # 有测试失败
                    status = TestStatus.FAILED
                    error_msg = "部分测试失败，请查看详细日志"
                elif result_code == 2:
                    # 测试执行被中断
                    status = TestStatus.FAILED
                    error_msg = "测试执行被中断"
                elif result_code == 3:
                    # 内部错误
                    status = TestStatus.FAILED
                    error_msg = "pytest 内部错误"
                elif result_code == 4:
                    # 命令行使用错误
                    status = TestStatus.FAILED
                    error_msg = "pytest 命令行参数错误"
                elif result_code == 5:
                    # 没有收集到测试
                    status = TestStatus.SKIPPED
                    error_msg = "没有找到测试用例"
                else:
                    status = TestStatus.FAILED
                    error_msg = f"未知错误，退出码: {result_code}"

                test_result = TestResult(
                    name=test_name,
                    status=status,
                    duration=duration,
                    error_message=error_msg
                )

            except Exception as e:
                duration = time.time() - start_time
                import traceback
                test_result = TestResult(
                    name=test_name,
                    status=TestStatus.FAILED,
                    duration=duration,
                    error_message=str(e),
                    traceback=traceback.format_exc()
                )

            self.results[test_name] = test_result
            self.test_finished.emit(test_name, test_result)

        self.all_finished.emit(self.results)


class TestRunnerUI(QMainWindow):
    """测试运行器主界面"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧪 测试运行器 - UE Toolkit AI")
        self.setGeometry(100, 100, 1400, 900)

        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: #2196F3;
            }
        """)

        # 收集测试
        self.tests_dir = PROJECT_ROOT / 'tests'
        self.collector = TestCollector(self.tests_dir)
        self.all_tests = self.collector.collect()

        # 测试结果
        self.test_results: Dict[str, TestResult] = {}

        # 初始化界面
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # 顶部工具栏
        toolbar = self.create_toolbar()
        main_layout.addLayout(toolbar)

        # 主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：测试树
        left_panel = self.create_test_tree()
        splitter.addWidget(left_panel)

        # 右侧：结果显示
        right_panel = self.create_result_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # 底部状态栏
        status_bar = self.create_status_bar()
        main_layout.addLayout(status_bar)

    def create_toolbar(self) -> QHBoxLayout:
        """创建工具栏"""
        toolbar = QHBoxLayout()

        # 运行所有测试按钮
        self.run_all_btn = QPushButton("▶ 运行所有测试")
        self.run_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.run_all_btn.clicked.connect(self.run_all_tests)
        toolbar.addWidget(self.run_all_btn)

        # 运行选中测试按钮
        self.run_selected_btn = QPushButton("▶ 运行选中测试")
        self.run_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.run_selected_btn.clicked.connect(self.run_selected_tests)
        toolbar.addWidget(self.run_selected_btn)

        # 清除结果按钮
        clear_btn = QPushButton("🗑 清除结果")
        clear_btn.clicked.connect(self.clear_results)
        toolbar.addWidget(clear_btn)

        toolbar.addStretch()

        # 统计标签
        self.stats_label = QLabel("总计: 0 | 通过: 0 | 失败: 0 | 未运行: 0")
        self.stats_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        toolbar.addWidget(self.stats_label)

        return toolbar

    def create_test_tree(self) -> QGroupBox:
        """创建测试树"""
        group = QGroupBox("📋 测试列表")
        layout = QVBoxLayout()

        self.test_tree = QTreeWidget()
        self.test_tree.setHeaderLabels(["测试名称", "状态", "耗时"])
        self.test_tree.setColumnWidth(0, 500)
        self.test_tree.setColumnWidth(1, 120)
        self.test_tree.setColumnWidth(2, 80)
        self.test_tree.itemClicked.connect(self.on_test_selected)

        # 设置树的样式
        self.test_tree.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                font-family: 'Microsoft YaHei UI', Arial;
                font-size: 12px;
                padding: 5px;
            }
            QTreeWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:hover {
                background-color: #e3f2fd;
            }
            QTreeWidget::item:selected {
                background-color: #bbdefb;
                color: black;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #2196F3;
                font-weight: bold;
                font-size: 13px;
            }
        """)

        # 添加测试项
        self.populate_test_tree()

        layout.addWidget(self.test_tree)
        group.setLayout(layout)

        return group

    def create_result_panel(self) -> QGroupBox:
        """创建结果显示面板"""
        group = QGroupBox("📊 测试结果")
        layout = QVBoxLayout()

        # 结果文本框
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: #333;
                font-family: 'Microsoft YaHei UI', Arial;
                font-size: 13px;
                padding: 10px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)

        # 显示欢迎信息
        self.show_welcome_message()

        layout.addWidget(self.result_text)

        group.setLayout(layout)
        return group

    def show_welcome_message(self):
        """显示欢迎信息"""
        total_tests = sum(len(files) for files in self.all_tests.values())

        html = f"""
            <div style="padding: 30px; font-family: 'Microsoft YaHei UI', Arial; text-align: center;">
                <h1 style="color: #2196F3; margin-bottom: 20px;">🧪 欢迎使用测试运行器</h1>

                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin: 20px 0;">
                    <h2 style="margin: 0 0 15px 0;">📊 测试统计</h2>
                    <p style="font-size: 18px; margin: 10px 0;">
                        共有 <strong style="font-size: 24px;">{total_tests}</strong> 个测试
                    </p>
                    <div style="display: flex; justify-content: space-around; margin-top: 20px; text-align: center;">
                        <div>
                            <p style="font-size: 16px; margin: 5px 0;">🧵 线程管理</p>
                            <p style="font-size: 20px; font-weight: bold; margin: 5px 0;">{len(self.all_tests.get(TestCategory.THREAD_MANAGEMENT, []))}</p>
                        </div>
                        <div>
                            <p style="font-size: 16px; margin: 5px 0;">🔗 集成测试</p>
                            <p style="font-size: 20px; font-weight: bold; margin: 5px 0;">{len(self.all_tests.get(TestCategory.INTEGRATION, []))}</p>
                        </div>
                        <div>
                            <p style="font-size: 16px; margin: 5px 0;">⚙️ 功能测试</p>
                            <p style="font-size: 20px; font-weight: bold; margin: 5px 0;">{len(self.all_tests.get(TestCategory.OTHER, []))}</p>
                        </div>
                    </div>
                </div>

                <div style="background-color: #e3f2fd; padding: 25px; border-radius: 8px; margin: 20px 0; text-align: left;">
                    <h3 style="color: #1976d2; margin-top: 0;">🚀 快速开始</h3>
                    <ol style="color: #666; line-height: 2; font-size: 14px;">
                        <li>点击左侧的测试项，查看测试详情</li>
                        <li>点击 <strong style="color: #4CAF50;">"▶ 运行所有测试"</strong> 运行全部测试</li>
                        <li>或者选择特定的测试，点击 <strong style="color: #2196F3;">"▶ 运行选中测试"</strong></li>
                        <li>查看右侧的测试结果和错误信息</li>
                    </ol>
                </div>

                <div style="background-color: #fff3e0; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: left;">
                    <h3 style="color: #F57C00; margin-top: 0;">💡 使用技巧</h3>
                    <ul style="color: #666; line-height: 2; font-size: 14px; list-style-type: none; padding-left: 0;">
                        <li>✨ <strong>分类运行：</strong>选择整个分类（如"线程管理测试"），一次运行该分类下的所有测试</li>
                        <li>✨ <strong>查看详情：</strong>点击任意测试项，右侧会显示详细说明</li>
                        <li>✨ <strong>错误提示：</strong>测试失败时，会显示详细的错误信息和修复建议</li>
                        <li>✨ <strong>实时进度：</strong>底部进度条显示测试运行进度</li>
                    </ul>
                </div>

                <p style="color: #999; font-size: 12px; margin-top: 30px;">
                    💫 让测试变得简单有趣！
                </p>
            </div>
        """

        self.result_text.setHtml(html)

    def create_status_bar(self) -> QHBoxLayout:
        """创建状态栏"""
        status_layout = QHBoxLayout()

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("font-size: 12px;")
        status_layout.addWidget(self.status_label)

        return status_layout

    def populate_test_tree(self):
        """填充测试树"""
        self.test_tree.clear()

        # 按分类添加测试
        for category, test_files in self.all_tests.items():
            if not test_files:
                continue

            # 创建分类节点
            category_item = QTreeWidgetItem(self.test_tree)
            category_item.setText(0, f"{category} ({len(test_files)} 个测试)")
            category_item.setFont(0, QFont("Microsoft YaHei UI", 11, QFont.Weight.Bold))
            category_item.setForeground(0, QColor("#2196F3"))

            # 添加测试文件
            for test_file in sorted(test_files):
                test_item = QTreeWidgetItem(category_item)
                test_name = test_file.stem

                # 使用友好的名称
                friendly_name = get_friendly_test_name(test_name)
                test_item.setText(0, friendly_name)
                test_item.setText(1, "⚪ 未运行")
                test_item.setText(2, "-")
                test_item.setData(0, Qt.ItemDataRole.UserRole, test_file)
                test_item.setFont(0, QFont("Microsoft YaHei UI", 10))

        self.test_tree.expandAll()

    def on_test_selected(self, item: QTreeWidgetItem, column: int):
        """测试项被选中"""
        test_file = item.data(0, Qt.ItemDataRole.UserRole)
        if not test_file:
            return

        test_name = test_file.stem
        friendly_name = get_friendly_test_name(test_name)

        # 显示测试信息
        if test_name in self.test_results:
            result = self.test_results[test_name]
            self.display_test_result(result, friendly_name)
        else:
            self.result_text.setHtml(f"""
                <div style="padding: 20px;">
                    <h2 style="color: #2196F3; font-family: 'Microsoft YaHei UI';">📝 {friendly_name}</h2>
                    <hr style="border: none; border-top: 2px solid #e0e0e0; margin: 15px 0;">
                    <p style="color: #666; font-size: 14px; line-height: 1.6;">
                        <strong>状态：</strong>⚪ 尚未运行
                    </p>
                    <p style="color: #666; font-size: 14px; line-height: 1.6;">
                        <strong>说明：</strong>点击上方的 <span style="color: #2196F3; font-weight: bold;">"▶ 运行选中测试"</span> 按钮来运行此测试
                    </p>
                    <div style="background-color: #e3f2fd; padding: 15px; border-radius: 8px; margin-top: 20px;">
                        <p style="color: #1976d2; font-size: 13px; margin: 0;">
                            💡 <strong>提示：</strong>你也可以选择整个分类（如"线程管理测试"），然后点击运行按钮，一次运行该分类下的所有测试。
                        </p>
                    </div>
                </div>
            """)

    def display_test_result(self, result: TestResult, friendly_name: str = None):
        """显示测试结果"""
        if result.status == TestStatus.PASSED:
            color = "#4CAF50"
            bg_color = "#e8f5e9"
            icon = "✅"
            status_text = "测试通过"
        elif result.status == TestStatus.FAILED:
            color = "#f44336"
            bg_color = "#ffebee"
            icon = "❌"
            status_text = "测试失败"
        else:
            color = "#FFC107"
            bg_color = "#fff3e0"
            icon = "⚠️"
            status_text = "测试跳过"

        display_name = friendly_name or get_friendly_test_name(result.name)

        html = f"""
            <div style="padding: 20px; font-family: 'Microsoft YaHei UI', Arial;">
                <div style="background-color: {bg_color}; padding: 20px; border-radius: 8px; border-left: 5px solid {color};">
                    <h2 style="color: {color}; margin: 0 0 10px 0;">{icon} {display_name}</h2>
                    <p style="color: #666; margin: 5px 0; font-size: 14px;">
                        <strong>文件名：</strong><code style="background-color: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 3px;">{result.name}.py</code>
                    </p>
                </div>

                <div style="margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 8px;">
                    <p style="margin: 8px 0; font-size: 14px;">
                        <strong>状态：</strong><span style="color: {color}; font-weight: bold;">{icon} {status_text}</span>
                    </p>
                    <p style="margin: 8px 0; font-size: 14px;">
                        <strong>耗时：</strong><span style="color: #666;">{result.duration:.2f} 秒</span>
                    </p>
                </div>
        """

        if result.error_message:
            html += f"""
                <div style="margin-top: 20px;">
                    <h3 style="color: #f44336; margin-bottom: 10px;">❌ 错误信息</h3>
                    <div style="background-color: #2d2d2d; padding: 15px; border-radius: 8px; overflow-x: auto;">
                        <pre style="color: #ff6b6b; margin: 0; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; line-height: 1.5;">{result.error_message}</pre>
                    </div>
                </div>

                <div style="margin-top: 20px; background-color: #fff3e0; padding: 15px; border-radius: 8px; border-left: 4px solid #FFC107;">
                    <h3 style="color: #F57C00; margin: 0 0 10px 0;">💡 修复建议</h3>
                    <ul style="color: #666; margin: 0; padding-left: 20px; line-height: 1.8;">
                        <li><strong>AttributeError / TypeError：</strong>代码接口可能发生了变化，需要更新测试脚本</li>
                        <li><strong>AssertionError：</strong>检查代码逻辑是否正确，或者测试的预期值是否需要更新</li>
                        <li><strong>ImportError：</strong>检查依赖是否安装，运行 <code>pip install -r requirements.txt</code></li>
                        <li><strong>FileNotFoundError：</strong>测试依赖的文件不存在，可能需要删除或更新此测试</li>
                    </ul>
                </div>
            """
        else:
            html += """
                <div style="margin-top: 20px; background-color: #e8f5e9; padding: 15px; border-radius: 8px; border-left: 4px solid #4CAF50;">
                    <p style="color: #2e7d32; margin: 0; font-size: 14px;">
                        🎉 <strong>太棒了！</strong>所有测试都通过了，代码运行正常！
                    </p>
                </div>
            """

        html += "</div>"
        self.result_text.setHtml(html)

    def run_all_tests(self):
        """运行所有测试"""
        all_test_files = []
        for test_files in self.all_tests.values():
            all_test_files.extend(test_files)

        if not all_test_files:
            QMessageBox.warning(self, "警告", "没有找到测试文件！")
            return

        self.run_tests(all_test_files)

    def run_selected_tests(self):
        """运行选中的测试"""
        selected_items = self.test_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要运行的测试！")
            return

        test_files = []
        for item in selected_items:
            test_file = item.data(0, Qt.ItemDataRole.UserRole)
            if test_file:
                test_files.append(test_file)
            else:
                # 如果选中的是分类节点，运行该分类下的所有测试
                for i in range(item.childCount()):
                    child = item.child(i)
                    child_file = child.data(0, Qt.ItemDataRole.UserRole)
                    if child_file:
                        test_files.append(child_file)

        if not test_files:
            QMessageBox.warning(self, "警告", "没有找到可运行的测试！")
            return

        self.run_tests(test_files)

    def run_tests(self, test_files: List[Path]):
        """运行测试"""
        # 禁用按钮
        self.run_all_btn.setEnabled(False)
        self.run_selected_btn.setEnabled(False)

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(test_files))
        self.progress_bar.setValue(0)

        # 更新状态
        self.status_label.setText(f"正在运行 {len(test_files)} 个测试...")

        # 创建测试运行器
        self.test_runner = TestRunner(test_files)
        self.test_runner.test_started.connect(self.on_test_started)
        self.test_runner.test_finished.connect(self.on_test_finished)
        self.test_runner.all_finished.connect(self.on_all_finished)

        # 启动测试
        self.test_runner.start()

    def on_test_started(self, test_name: str):
        """测试开始"""
        self.status_label.setText(f"正在运行: {test_name}")

        # 更新树中的状态
        self.update_tree_item_status(test_name, "🔄 运行中", "-")

    def on_test_finished(self, test_name: str, result: TestResult):
        """测试完成"""
        self.test_results[test_name] = result

        # 更新进度条
        current = self.progress_bar.value()
        self.progress_bar.setValue(current + 1)

        # 更新树中的状态
        if result.status == TestStatus.PASSED:
            status_text = "✅ 通过"
        elif result.status == TestStatus.FAILED:
            status_text = "❌ 失败"
        else:
            status_text = "⚠️ 跳过"

        self.update_tree_item_status(test_name, status_text, f"{result.duration:.2f}s")

    def on_all_finished(self, results: Dict[str, TestResult]):
        """所有测试完成"""
        # 启用按钮
        self.run_all_btn.setEnabled(True)
        self.run_selected_btn.setEnabled(True)

        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 统计结果
        total = len(results)
        passed = sum(1 for r in results.values() if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results.values() if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in results.values() if r.status == TestStatus.SKIPPED)

        # 更新统计
        self.stats_label.setText(f"总计: {total} | 通过: {passed} | 失败: {failed} | 跳过: {skipped}")

        # 更新状态
        if failed > 0:
            self.status_label.setText(f"❌ 测试完成 - {failed} 个失败")

            # 显示失败提示
            QMessageBox.warning(
                self,
                "测试失败",
                f"有 {failed} 个测试失败！\n\n"
                "请查看右侧的错误信息，可能需要更新测试脚本。\n\n"
                "常见原因：\n"
                "• 代码接口发生了变化\n"
                "• 代码逻辑有 bug\n"
                "• 测试环境配置问题"
            )
        else:
            self.status_label.setText(f"✅ 测试完成 - 全部通过！")
            QMessageBox.information(self, "测试通过", f"所有 {total} 个测试都通过了！🎉")

    def update_tree_item_status(self, test_name: str, status: str, duration: str):
        """更新树中测试项的状态"""
        friendly_name = get_friendly_test_name(test_name)
        iterator = QTreeWidgetItemIterator(self.test_tree)
        while iterator.value():
            item = iterator.value()
            # 通过友好名称或原始名称匹配
            if item.text(0) == friendly_name or item.text(0) == test_name:
                item.setText(1, status)
                item.setText(2, duration)

                # 根据状态设置颜色
                if "通过" in status:
                    item.setForeground(1, QColor("#4CAF50"))
                elif "失败" in status:
                    item.setForeground(1, QColor("#f44336"))
                elif "运行中" in status:
                    item.setForeground(1, QColor("#2196F3"))
                else:
                    item.setForeground(1, QColor("#9E9E9E"))
                break
            iterator += 1

    def clear_results(self):
        """清除结果"""
        self.test_results.clear()
        self.result_text.clear()
        self.stats_label.setText("总计: 0 | 通过: 0 | 失败: 0 | 未运行: 0")
        self.status_label.setText("就绪")

        # 重置树中的状态
        iterator = QTreeWidgetItemIterator(self.test_tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.ItemDataRole.UserRole):  # 只重置测试项
                item.setText(1, "⚪ 未运行")
                item.setText(2, "-")
            iterator += 1


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    window = TestRunnerUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()

