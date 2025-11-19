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
    THREAD_MANAGEMENT = "Thread Management 测试"
    INTEGRATION = "集成测试"
    OTHER = "其他功能测试"


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
        self.setGeometry(100, 100, 1200, 800)

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
        self.test_tree.setColumnWidth(0, 400)
        self.test_tree.setColumnWidth(1, 100)
        self.test_tree.itemClicked.connect(self.on_test_selected)

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
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.result_text)

        group.setLayout(layout)
        return group

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
            category_item.setText(0, f"{category} ({len(test_files)})")
            category_item.setFont(0, QFont("Arial", 11, QFont.Weight.Bold))

            # 添加测试文件
            for test_file in sorted(test_files):
                test_item = QTreeWidgetItem(category_item)
                test_name = test_file.stem
                test_item.setText(0, test_name)
                test_item.setText(1, "⚪ 未运行")
                test_item.setText(2, "-")
                test_item.setData(0, Qt.ItemDataRole.UserRole, test_file)

        self.test_tree.expandAll()

    def on_test_selected(self, item: QTreeWidgetItem, column: int):
        """测试项被选中"""
        test_file = item.data(0, Qt.ItemDataRole.UserRole)
        if not test_file:
            return

        test_name = test_file.stem

        # 显示测试信息
        if test_name in self.test_results:
            result = self.test_results[test_name]
            self.display_test_result(result)
        else:
            self.result_text.setHtml(f"""
                <h2 style="color: #4CAF50;">📝 {test_name}</h2>
                <p style="color: #888;">测试尚未运行</p>
                <p style="color: #888;">点击"运行选中测试"按钮来运行此测试</p>
            """)

    def display_test_result(self, result: TestResult):
        """显示测试结果"""
        if result.status == TestStatus.PASSED:
            color = "#4CAF50"
            icon = "✅"
            message = "测试通过！"
        elif result.status == TestStatus.FAILED:
            color = "#f44336"
            icon = "❌"
            message = "测试失败！"
        else:
            color = "#FFC107"
            icon = "⚠️"
            message = "测试跳过"

        html = f"""
            <h2 style="color: {color};">{icon} {result.name}</h2>
            <p><strong>状态:</strong> <span style="color: {color};">{result.status.value}</span></p>
            <p><strong>耗时:</strong> {result.duration:.2f}s</p>
        """

        if result.error_message:
            html += f"""
                <hr>
                <h3 style="color: #f44336;">错误信息:</h3>
                <pre style="background-color: #2d2d2d; padding: 10px; border-radius: 4px; color: #ff6b6b;">
{result.error_message}
                </pre>
            """

            # 添加建议
            html += """
                <hr>
                <h3 style="color: #FFC107;">💡 建议:</h3>
                <ul style="color: #d4d4d4;">
                    <li>如果错误是 <code>AttributeError</code> 或 <code>TypeError</code>，可能是代码接口发生了变化，需要更新测试</li>
                    <li>如果错误是 <code>AssertionError</code>，检查代码逻辑是否正确</li>
                    <li>如果错误是 <code>ImportError</code>，检查依赖是否安装</li>
                    <li>查看完整错误信息，定位问题所在</li>
                </ul>
            """

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
        iterator = QTreeWidgetItemIterator(self.test_tree)
        while iterator.value():
            item = iterator.value()
            if item.text(0) == test_name:
                item.setText(1, status)
                item.setText(2, duration)
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

