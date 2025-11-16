# -*- coding: utf-8 -*-

"""
智能主题构建器 - 自动构建QSS主题文件

核心功能：
1. 自动检测 core/, widgets/, modules/ 目录下的QSS文件
2. 按固定顺序拼接（core → widgets → modules）
3. 从Python配置加载主题变量
4. 替换QSS中的 ${variable} 占位符
5. 生成完整主题文件到 themes/ 目录
6. 支持运行时动态变量更新（为实时主题编辑器准备）

使用示例:
    # 安静模式构建
    builder = ThemeBuilder(styles_root, verbose=False)
    builder.build_all_themes()
    
    # 详细日志模式
    builder = ThemeBuilder(styles_root, verbose=True)
    builder.build_theme("modern_dark")
    
    # 运行时更新变量
    builder.update_variables("modern_dark", {"primary": "#ff0000"})
    qss = builder.build_theme("modern_dark", save=False)
"""

import logging
import re
import importlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ThemeBuilder:
    """智能主题构建器"""
    
    def __init__(self, styles_root: Path, verbose: bool = True):
        """
        初始化主题构建器
        
        Args:
            styles_root: 样式系统根目录（resources/styles）
            verbose: 是否输出详细日志（默认True）
        """
        self.styles_root = Path(styles_root)
        self.verbose = verbose
        
        # 定义目录结构
        self.config_dir = self.styles_root / "config"
        self.themes_config_dir = self.config_dir / "themes"
        self.core_dir = self.styles_root / "core"
        self.widgets_dir = self.styles_root / "widgets"
        self.modules_dir = self.styles_root / "modules"
        self.output_dir = self.styles_root / "themes"
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 运行时变量覆盖（用于动态主题编辑）
        self._runtime_variables: Dict[str, Dict[str, str]] = {}
        
        self._log_info(f"✅ 主题构建器初始化完成")
        self._log_info(f"   样式根目录: {self.styles_root}")
    
    def _log_info(self, message: str):
        """输出信息日志（受verbose控制）"""
        if self.verbose:
            print(message)
        logger.info(message)
    
    def _log_debug(self, message: str):
        """输出调试日志（受verbose控制）"""
        if self.verbose:
            print(message)
        logger.debug(message)
    
    def _log_warning(self, message: str):
        """输出警告日志（始终显示）"""
        print(f"⚠️  {message}")
        logger.warning(message)
    
    def _log_error(self, message: str):
        """输出错误日志（始终显示）"""
        print(f"❌ {message}")
        logger.error(message)
    
    def discover_themes(self) -> List[str]:
        """
        发现所有可用的主题配置
        
        Returns:
            主题名称列表
        """
        if not self.themes_config_dir.exists():
            self._log_warning(f"主题配置目录不存在: {self.themes_config_dir}")
            return []
        
        themes = []
        for file in self.themes_config_dir.glob("*.py"):
            if file.name != "__init__.py":
                theme_name = file.stem
                themes.append(theme_name)
        
        self._log_info(f"🎨 发现 {len(themes)} 个主题配置:")
        for theme in themes:
            self._log_info(f"   - {theme}")
        
        return themes
    
    def _load_theme_variables(self, theme_name: str) -> Dict[str, str]:
        """
        从Python配置文件加载主题变量
        
        Args:
            theme_name: 主题名称
            
        Returns:
            变量字典
        """
        try:
            # 动态导入主题配置模块
            module_path = f"resources.styles.config.themes.{theme_name}"
            theme_module = importlib.import_module(module_path)
            
            # 加载全局变量
            from resources.styles.config import variables
            
            # 合并变量
            all_variables = {}
            
            # 1. 添加尺寸变量
            for key, value in variables.SPACING.items():
                all_variables[f'spacing_{key}'] = value
            
            for key, value in variables.BORDER_RADIUS.items():
                all_variables[f'radius_{key}'] = value
            
            for key, value in variables.FONT_SIZE.items():
                all_variables[f'font_{key}'] = value
            
            for key, value in variables.FONT_WEIGHT.items():
                all_variables[f'font_{key}'] = value
            
            # 2. 添加主题颜色变量
            if hasattr(theme_module, 'COLORS'):
                all_variables.update(theme_module.COLORS)
            
            # 3. 添加主题特定的圆角覆盖
            if hasattr(theme_module, 'BORDER_RADIUS_OVERRIDE'):
                for key, value in theme_module.BORDER_RADIUS_OVERRIDE.items():
                    all_variables[f'radius_{key}'] = value
            
            # 4. 应用运行时变量覆盖
            if theme_name in self._runtime_variables:
                all_variables.update(self._runtime_variables[theme_name])
                self._log_debug(f"   ✅ 应用了 {len(self._runtime_variables[theme_name])} 个运行时变量覆盖")
            
            self._log_debug(f"📦 加载主题变量: {theme_name}")
            self._log_debug(f"   ✅ 加载了 {len(all_variables)} 个变量")
            
            return all_variables
            
        except ImportError as e:
            self._log_error(f"无法导入主题配置: {theme_name}, 错误: {e}")
            return {}
        except Exception as e:
            self._log_error(f"加载主题变量失败: {theme_name}, 错误: {e}")
            return {}
    
    def _load_layer_qss(self, layer_dir: Path, layer_name: str) -> str:
        """
        加载某一层的所有QSS文件（递归加载子目录）
        
        Args:
            layer_dir: 层目录
            layer_name: 层名称（用于日志）
            
        Returns:
            合并后的QSS内容
        """
        if not layer_dir.exists():
            self._log_debug(f"   ⏭️  跳过不存在的目录: {layer_name}/")
            return ""
        
        # 递归查找所有.qss文件
        qss_files = sorted(layer_dir.rglob("*.qss"))
        
        if not qss_files:
            self._log_debug(f"   ⏭️  {layer_name}/ 目录为空")
            return ""
        
        self._log_debug(f"📂 加载 {layer_name}/ 目录...")
        
        combined_qss = []
        total_chars = 0
        
        for qss_file in qss_files:
            try:
                with open(qss_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 显示相对路径
                    relative_path = qss_file.relative_to(layer_dir)
                    combined_qss.append(f"\n/* ===== {relative_path} ===== */\n")
                    combined_qss.append(content)
                    total_chars += len(content)
                    self._log_debug(f"   📄 {relative_path}")
            except Exception as e:
                self._log_error(f"读取文件失败: {qss_file}, 错误: {e}")
        
        self._log_debug(f"   ✅ 加载了 {total_chars} 字符")
        
        return "\n".join(combined_qss)
    
    def _replace_variables(self, qss: str, variables: Dict[str, str]) -> str:
        """
        替换QSS中的变量占位符
        
        Args:
            qss: QSS内容
            variables: 变量字典
            
        Returns:
            替换后的QSS内容
        """
        # 使用正则表达式查找所有 ${variable} 占位符
        pattern = re.compile(r'\$\{(\w+)\}')
        
        def replace_func(match):
            var_name = match.group(1)
            if var_name in variables:
                return variables[var_name]
            else:
                self._log_warning(f"未找到变量: {var_name}")
                return match.group(0)  # 保留原始占位符
        
        result = pattern.sub(replace_func, qss)
        
        # 统计替换次数
        replaced_count = len(pattern.findall(qss))
        self._log_debug(f"🔄 替换了 {replaced_count} 个变量占位符")
        
        return result
    
    def build_theme(self, theme_name: str, save: bool = True) -> str:
        """
        构建单个主题
        
        Args:
            theme_name: 主题名称
            save: 是否保存到文件（默认True）
            
        Returns:
            完整的QSS内容
        """
        self._log_info(f"\n🎨 开始构建主题: {theme_name}")
        
        # 1. 加载主题变量
        variables = self._load_theme_variables(theme_name)
        if not variables:
            self._log_error(f"主题变量加载失败: {theme_name}")
            return ""
        
        # 2. 按顺序加载各层QSS
        qss_parts = []
        
        # Core层（基础样式 + 通用组件）
        core_qss = self._load_layer_qss(self.core_dir, "core")
        if core_qss:
            qss_parts.append(core_qss)
        
        # Widgets层（控件样式）
        widgets_qss = self._load_layer_qss(self.widgets_dir, "widgets")
        if widgets_qss:
            qss_parts.append(widgets_qss)
        
        # Modules层（模块样式）
        modules_qss = self._load_layer_qss(self.modules_dir, "modules")
        if modules_qss:
            qss_parts.append(modules_qss)
        
        # 3. 合并所有QSS
        combined_qss = "\n\n".join(qss_parts)
        
        # 4. 替换变量
        final_qss = self._replace_variables(combined_qss, variables)
        
        # 5. 保存到文件
        if save:
            output_file = self.output_dir / f"{theme_name}.qss"
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(final_qss)
                self._log_info(f"✅ 主题构建完成: {output_file.name}")
                self._log_info(f"   文件大小: {len(final_qss)} 字符")
            except Exception as e:
                self._log_error(f"保存主题文件失败: {output_file}, 错误: {e}")
        
        return final_qss

    def build_all_themes(self) -> List[Path]:
        """
        构建所有主题

        Returns:
            生成的主题文件路径列表
        """
        themes = self.discover_themes()

        if not themes:
            self._log_warning("未发现任何主题配置")
            return []

        output_files = []
        success_count = 0

        for theme_name in themes:
            try:
                self.build_theme(theme_name, save=True)
                output_file = self.output_dir / f"{theme_name}.qss"
                output_files.append(output_file)
                success_count += 1
            except Exception as e:
                self._log_error(f"构建主题失败: {theme_name}, 错误: {e}")

        self._log_info(f"\n✅ 成功构建 {success_count}/{len(themes)} 个主题")

        return output_files

    def update_variables(self, theme_name: str, variables: Dict[str, str]) -> None:
        """
        更新主题的运行时变量（用于动态主题编辑）

        Args:
            theme_name: 主题名称
            variables: 要更新的变量字典

        Example:
            builder.update_variables("modern_dark", {
                "primary": "#ff0000",
                "bg_primary": "#000000"
            })
            # 下次构建时会使用新的变量值
        """
        if theme_name not in self._runtime_variables:
            self._runtime_variables[theme_name] = {}

        self._runtime_variables[theme_name].update(variables)

        self._log_info(f"🔄 更新主题 '{theme_name}' 的运行时变量:")
        for key, value in variables.items():
            self._log_info(f"   {key} = {value}")

    def clear_runtime_variables(self, theme_name: Optional[str] = None) -> None:
        """
        清除运行时变量覆盖

        Args:
            theme_name: 主题名称，如果为None则清除所有主题的运行时变量
        """
        if theme_name is None:
            self._runtime_variables.clear()
            self._log_info("🧹 已清除所有运行时变量覆盖")
        elif theme_name in self._runtime_variables:
            del self._runtime_variables[theme_name]
            self._log_info(f"🧹 已清除主题 '{theme_name}' 的运行时变量覆盖")

    def get_runtime_variables(self, theme_name: str) -> Dict[str, str]:
        """
        获取主题的运行时变量覆盖

        Args:
            theme_name: 主题名称

        Returns:
            运行时变量字典
        """
        return self._runtime_variables.get(theme_name, {}).copy()

    def rebuild_theme_with_variables(
        self,
        theme_name: str,
        variables: Dict[str, str],
        save: bool = False
    ) -> str:
        """
        使用新变量重新构建主题（不保存到运行时变量）

        这个方法适用于实时预览，不会影响持久化的运行时变量

        Args:
            theme_name: 主题名称
            variables: 临时变量字典
            save: 是否保存到文件

        Returns:
            构建的QSS内容
        """
        # 临时保存当前的运行时变量
        original_vars = self._runtime_variables.get(theme_name, {}).copy()

        try:
            # 临时设置新变量
            self._runtime_variables[theme_name] = variables

            # 构建主题
            qss = self.build_theme(theme_name, save=save)

            return qss

        finally:
            # 恢复原始运行时变量
            if original_vars:
                self._runtime_variables[theme_name] = original_vars
            elif theme_name in self._runtime_variables:
                del self._runtime_variables[theme_name]

