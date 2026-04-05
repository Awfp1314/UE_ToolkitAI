# -*- coding: utf-8 -*-

"""
配置应用器

负责将配置模板应用到目标项目。
"""

import json
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple, Callable
from datetime import datetime

from core.logger import get_logger
from .config_model import ConfigTemplate, ConfigType
from .config_storage import ConfigStorage
from .version_matcher import VersionMatcher
from .performance_utils import copytree_with_progress, cleanup_temp_files
from .utils import validate_path, check_write_permission

logger = get_logger(__name__)


class ConfigApplier:
    """配置应用器

    负责将配置模板应用到目标项目。
    """

    def __init__(self, storage: ConfigStorage, version_matcher: VersionMatcher):
        """初始化配置应用器

        Args:
            storage: 配置存储管理器
            version_matcher: 版本匹配器
        """
        self.storage = storage
        self.version_matcher = version_matcher
        logger.info("配置应用器初始化完成")

    def apply_config(
        self,
        template: ConfigTemplate,
        target_project: Path,
        backup: bool,
        progress_callback: Optional[Callable[[int, str, str], None]] = None
    ) -> Tuple[bool, str]:
        """应用配置到目标项目

        Args:
            template: 配置模板
            target_project: 目标项目路径
            backup: 是否备份原配置
            progress_callback: 进度回调函数 (stage: int, title: str, detail: str)

        Returns:
            (是否成功, 消息)
        """
        try:
            # 阶段 1: 版本验证
            if progress_callback:
                progress_callback(1, "版本验证", "正在验证配置版本与目标项目版本...")
            
            # 获取目标项目版本
            project_version = self._get_project_version(target_project)
            if not project_version:
                return False, "无法获取目标项目版本"
            
            # 验证版本兼容性
            is_compatible, error_msg = self.version_matcher.validate_version(
                template.config_version, project_version
            )
            if not is_compatible:
                return False, error_msg
            
            # 阶段 2: 备份配置
            backup_path = None
            if backup:
                if progress_callback:
                    progress_callback(2, "备份配置", "正在备份原配置...")
                
                backup_path = self._backup_config(target_project, template.type)
                if not backup_path:
                    return False, "备份配置失败"
                
                logger.info(f"配置备份成功: {backup_path}")
                
                # 自动保存备份为配置模板
                project_name = target_project.name
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_template = self._create_backup_template(
                    backup_path, project_name, template.type, 
                    template.config_version, str(target_project), timestamp
                )
                if backup_template:
                    logger.info(f"备份配置已保存为模板: {backup_template.name}")
            
            # 阶段 3: 复制配置文件
            if progress_callback:
                progress_callback(3, "复制配置文件", "正在复制配置文件到目标项目...")
            
            if template.type == ConfigType.PROJECT_SETTINGS:
                success, error_msg = self._apply_project_settings(template, target_project)
                if not success:
                    return False, error_msg
            else:
                success, error_msg = self._apply_editor_preferences(template, target_project)
                if not success:
                    return False, error_msg
            
            # 阶段 4: 清理缓存
            if progress_callback:
                progress_callback(4, "清理缓存", "正在清理项目缓存...")
            
            if template.type == ConfigType.PROJECT_SETTINGS:
                self._clean_cache(target_project)
            
            # 阶段 5: 更新项目 ID
            if progress_callback:
                progress_callback(5, "更新项目ID", "正在更新项目ID...")
            
            if template.type == ConfigType.PROJECT_SETTINGS:
                self._update_project_id(target_project)
            
            logger.info(
                f"配置应用成功: name={template.name}, target={target_project}, "
                f"backup={backup}"
            )
            return True, "配置应用成功"
            
        except Exception as e:
            logger.error(f"应用配置时发生错误: {e}", exc_info=True)
            return False, f"应用配置时发生错误: {str(e)}"

    def _backup_config(self, project_path: Path, config_type: ConfigType) -> Optional[Path]:
        """备份原配置

        Args:
            project_path: 项目路径
            config_type: 配置类型

        Returns:
            备份路径，如果失败则返回 None
        """
        try:
            # 创建备份目录
            backup_root = project_path / "Saved" / "ConfigBackup"
            backup_root.mkdir(parents=True, exist_ok=True)
            
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if config_type == ConfigType.PROJECT_SETTINGS:
                # 备份 Config/ 目录
                source_dir = project_path / "Config"
                if not source_dir.exists():
                    logger.warning(f"源配置目录不存在，跳过备份: {source_dir}")
                    return None
                
                backup_dir = backup_root / f"Config_{timestamp}"
                shutil.copytree(source_dir, backup_dir)
                logger.info(f"备份项目设置配置: {source_dir} -> {backup_dir}")
                return backup_dir
                
            elif config_type == ConfigType.EDITOR_PREFERENCES:
                # 备份 EditorPerProjectUserSettings.ini 文件
                # 尝试 WindowsEditor 目录（UE5）
                source_file = project_path / "Saved" / "Config" / "WindowsEditor" / "EditorPerProjectUserSettings.ini"
                
                # 如果不存在，尝试 Windows 目录（UE4）
                if not source_file.exists():
                    source_file = project_path / "Saved" / "Config" / "Windows" / "EditorPerProjectUserSettings.ini"
                
                if not source_file.exists():
                    logger.warning(f"编辑器偏好文件不存在，跳过备份: {source_file}")
                    return None
                
                backup_file = backup_root / f"EditorPrefs_{timestamp}.ini"
                shutil.copy2(source_file, backup_file)
                logger.info(f"备份编辑器偏好配置: {source_file} -> {backup_file}")
                return backup_file
            
            return None
            
        except Exception as e:
            logger.error(f"备份配置失败: {e}", exc_info=True)
            return None

    def _apply_project_settings(self, template: ConfigTemplate, target_project: Path) -> Tuple[bool, str]:
        """应用项目设置配置

        Args:
            template: 配置模板
            target_project: 目标项目路径

        Returns:
            (是否成功, 错误消息)
        """
        try:
            # 源配置目录
            source_config_dir = template.template_path / "Config"
            if not source_config_dir.exists():
                return False, "模板配置目录不存在"
            
            # 目标配置目录
            target_config_dir = target_project / "Config"
            
            # 路径安全验证
            if not validate_path(target_config_dir, target_project):
                return False, "目标配置目录路径不安全"
            
            # 检查写入权限
            if not check_write_permission(target_config_dir):
                return False, f"没有写入权限: {target_config_dir}"
            
            # 删除目标配置目录（如果存在）
            if target_config_dir.exists():
                shutil.rmtree(target_config_dir)
                logger.info(f"删除目标配置目录: {target_config_dir}")
            
            # 使用带进度的复制（对于大型配置）
            success = copytree_with_progress(
                source_config_dir, 
                target_config_dir,
                progress_callback=None  # 可以添加进度回调
            )
            
            if not success:
                return False, "复制配置目录失败"
            
            logger.info(f"复制配置目录: {source_config_dir} -> {target_config_dir}")
            
            return True, ""
            
        except Exception as e:
            logger.error(f"应用项目设置配置失败: {e}", exc_info=True)
            return False, f"应用项目设置配置失败: {str(e)}"

    def _apply_editor_preferences(self, template: ConfigTemplate, target_project: Path) -> Tuple[bool, str]:
        """应用编辑器偏好配置

        Args:
            template: 配置模板
            target_project: 目标项目路径

        Returns:
            (是否成功, 错误消息)
        """
        try:
            # 源编辑器偏好文件
            source_file = template.template_path / "EditorPerProjectUserSettings.ini"
            if not source_file.exists():
                return False, "模板编辑器偏好文件不存在"
            
            # 目标编�器偏好文件
            # 尝试 WindowsEditor 目录（UE5）
            target_dir = target_project / "Saved" / "Config" / "WindowsEditor"
            
            # 如果 WindowsEditor 不存在，使用 Windows 目录（UE4）
            if not target_dir.exists():
                target_dir = target_project / "Saved" / "Config" / "Windows"
            
            # 确保目标目录存在
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 路径安全验证
            if not validate_path(target_dir, target_project):
                return False, "目标目录路径不安全"
            
            # 检查写入权限
            if not check_write_permission(target_dir):
                return False, f"没有写入权限: {target_dir}"
            
            target_file = target_dir / "EditorPerProjectUserSettings.ini"
            
            # 复制文件
            shutil.copy2(source_file, target_file)
            logger.info(f"复制编辑器偏好文件: {source_file} -> {target_file}")
            
            return True, ""
            
        except Exception as e:
            logger.error(f"应用编辑器偏好配置失败: {e}", exc_info=True)
            return False, f"应用编辑器偏好配置失败: {str(e)}"

    def _clean_cache(self, project_path: Path):
        """清理项目缓存

        Args:
            project_path: 项目路径
        """
        try:
            # 删除 Saved/Config/ 目录
            saved_config_dir = project_path / "Saved" / "Config"
            if saved_config_dir.exists():
                shutil.rmtree(saved_config_dir)
                logger.info(f"删除缓存目录: {saved_config_dir}")
            
        except Exception as e:
            logger.warning(f"清理缓存失败（非致命错误）: {e}")

    def _update_project_id(self, project_path: Path):
        """更新项目 ID

        Args:
            project_path: 项目路径
        """
        try:
            # 查找 .uproject 文件
            uproject_files = list(project_path.glob("*.uproject"))
            if not uproject_files:
                logger.warning(f"未找到 .uproject 文件: {project_path}")
                return
            
            uproject_file = uproject_files[0]
            
            # 读取 .uproject 文件
            with open(uproject_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 生成新的项目 ID（GUID 格式）
            new_id = str(uuid.uuid4()).upper()
            
            # 更新 EpicAccountID 字段
            data['EpicAccountID'] = new_id
            
            # 保存 .uproject 文件
            with open(uproject_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"更新项目ID: {uproject_file}, 新ID: {new_id}")
            
        except Exception as e:
            logger.warning(f"更新项目ID失败（非致命错误）: {e}")

    def _get_project_version(self, project_path: Path) -> str:
        """获取项目引擎版本

        Args:
            project_path: 项目路径

        Returns:
            引擎版本字符串（如 "4.27"），如果无法获取则返回空字符串
        """
        try:
            # 查找 .uproject 文件
            uproject_files = list(project_path.glob("*.uproject"))
            if not uproject_files:
                logger.warning(f"未找到 .uproject 文件: {project_path}")
                return ""
            
            uproject_file = uproject_files[0]
            with open(uproject_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            engine_association = data.get('EngineAssociation', '')
            
            # 解析版本号
            import re
            if re.match(r'^\d+\.\d+', engine_association):
                # 提取主版本号和次版本号
                match = re.match(r'^(\d+\.\d+)', engine_association)
                if match:
                    version = match.group(1)
                    logger.info(f"获取项目引擎版本: {version}")
                    return version
            
            logger.warning(f"无法解析引擎版本: {engine_association}")
            return ""
            
        except Exception as e:
            logger.error(f"获取项目版本时发生错误: {e}", exc_info=True)
            return ""

    def _create_backup_template(
        self,
        backup_path: Path,
        project_name: str,
        config_type: ConfigType,
        config_version: str,
        source_project: str,
        timestamp: str
    ) -> Optional[ConfigTemplate]:
        """创建备份模板

        Args:
            backup_path: 备份路径
            project_name: 项目名称
            config_type: 配置类型
            config_version: 配置版本
            source_project: 源项目路径
            timestamp: 时间戳

        Returns:
            配置模板对象，如果失败则返回 None
        """
        try:
            # 格式化备份模板名称
            template_name = f"{project_name}_备份配置_{timestamp}"
            
            # 格式化备份模板描述
            description = f"以防配置应用出错的恢复备份（原项目：{project_name}）"
            
            # 计算文件统计信息
            files = []
            total_size = 0
            
            if config_type == ConfigType.PROJECT_SETTINGS:
                # 备份是一个目录
                if backup_path.is_dir():
                    for file_path in backup_path.rglob("*"):
                        if file_path.is_file():
                            files.append(str(file_path.relative_to(backup_path.parent)))
                            total_size += file_path.stat().st_size
            else:
                # 备份是一个文件
                if backup_path.is_file():
                    files.append(backup_path.name)
                    total_size = backup_path.stat().st_size
            
            # 创建配置模板对象
            template = ConfigTemplate(
                name=template_name,
                description=description,
                type=config_type,
                config_version=config_version,
                source_project=source_project,
                created_at=datetime.now(),
                file_count=len(files),
                total_size=total_size,
                files=files,
                template_path=self.storage.get_template_path(template_name)
            )
            
            # 创建模板目录
            template_dir = template.template_path
            template_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制备份文件到模板目录
            if config_type == ConfigType.PROJECT_SETTINGS:
                # 复制 Config 目录
                target_config_dir = template_dir / "Config"
                if backup_path.is_dir():
                    shutil.copytree(backup_path, target_config_dir)
            else:
                # 复制编辑器偏好文件
                target_file = template_dir / "EditorPerProjectUserSettings.ini"
                if backup_path.is_file():
                    shutil.copy2(backup_path, target_file)
            
            # 保存元数据
            metadata_file = template_dir / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"创建备份模板成功: {template_name}")
            return template
            
        except Exception as e:
            logger.error(f"创建备份模板失败: {e}", exc_info=True)
            return None


def apply_config_with_rollback(
    applier: ConfigApplier,
    template: ConfigTemplate,
    target_project: Path,
    backup_path: Optional[Path],
    progress_callback: Optional[Callable[[int, str, str], None]] = None
) -> Tuple[bool, str]:
    """应用配置（带回滚）

    Args:
        applier: 配置应用器实例
        template: 配置模板
        target_project: 目标项目路径
        backup_path: 备份路径
        progress_callback: 进度回调函数

    Returns:
        (是否成功, 消息)
    """
    try:
        # 应用配置
        success, message = applier.apply_config(
            template, target_project, backup_path is not None, progress_callback
        )

        if not success and backup_path:
            # 回滚
            logger.warning(f"配置应用失败，正在回滚: {message}")
            rollback_success, rollback_msg = restore_from_backup(
                backup_path, target_project, template.type
            )
            
            if rollback_success:
                return False, f"配置应用失败已回滚: {message}"
            else:
                return False, f"配置应用失败且回滚失败: {message}。回滚错误: {rollback_msg}"

        return success, message
        
    except Exception as e:
        logger.error(f"配置应用异常: {e}", exc_info=True)
        
        if backup_path:
            try:
                rollback_success, rollback_msg = restore_from_backup(
                    backup_path, target_project, template.type
                )
                
                if rollback_success:
                    return False, "配置应用异常已回滚"
                else:
                    return False, f"配置应用失败且回滚失败，请手动恢复。回滚错误: {rollback_msg}"
                    
            except Exception as rollback_error:
                logger.error(f"回滚失败: {rollback_error}", exc_info=True)
                return False, "配置应用失败且回滚失败，请手动恢复"
        
        return False, "配置应用失败"


def restore_from_backup(
    backup_path: Path,
    target_project: Path,
    config_type: ConfigType
) -> Tuple[bool, str]:
    """从备份恢复配置

    Args:
        backup_path: 备份路径
        target_project: 目标项目路径
        config_type: 配置类型

    Returns:
        (是否成功, 错误消息)
    """
    try:
        if config_type == ConfigType.PROJECT_SETTINGS:
            # 恢复项目设置配置
            target_config_dir = target_project / "Config"
            
            # 删除当前配置目录
            if target_config_dir.exists():
                shutil.rmtree(target_config_dir)
            
            # 从备份恢复
            if backup_path.is_dir():
                shutil.copytree(backup_path, target_config_dir)
                logger.info(f"从备份恢复项目设置配置: {backup_path} -> {target_config_dir}")
            else:
                return False, "备份路径不是有效的目录"
                
        elif config_type == ConfigType.EDITOR_PREFERENCES:
            # 恢复编辑器偏好配置
            # 尝试 WindowsEditor 目录（UE5）
            target_dir = target_project / "Saved" / "Config" / "WindowsEditor"
            
            # 如果 WindowsEditor 不存在，使用 Windows 目录（UE4）
            if not target_dir.exists():
                target_dir = target_project / "Saved" / "Config" / "Windows"
            
            # 确保目标目录存在
            target_dir.mkdir(parents=True, exist_ok=True)
            
            target_file = target_dir / "EditorPerProjectUserSettings.ini"
            
            # 从备份恢复
            if backup_path.is_file():
                shutil.copy2(backup_path, target_file)
                logger.info(f"从备份恢复编辑器偏好配置: {backup_path} -> {target_file}")
            else:
                return False, "备份路径不是有效的文件"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"从备份恢复配置失败: {e}", exc_info=True)
        return False, f"从备份恢复配置失败: {str(e)}"
