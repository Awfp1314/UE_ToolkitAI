# -*- coding: utf-8 -*-

"""
版本匹配器

负责验证配置版本与目标项目版本是否兼容。
"""

import re
from typing import Tuple

from core.logger import get_logger

logger = get_logger(__name__)


class VersionMatcher:
    """版本匹配器

    负责验证配置版本与目标项目版本是否兼容。
    """

    def validate_version(
        self,
        config_version: str,
        project_version: str
    ) -> Tuple[bool, str]:
        """验证版本兼容性

        Args:
            config_version: 配置版本（如 "4.27"）
            project_version: 项目版本（如 "4.27"）

        Returns:
            (是否兼容, 消息)
        """
        try:
            # 解析版本号
            config_major, config_minor = self._parse_version(config_version)
            project_major, project_minor = self._parse_version(project_version)

            # 比较主版本号和次版本号
            if config_major != project_major or config_minor != project_minor:
                error_msg = (
                    f"版本不兼容：配置版本为 {config_version}，"
                    f"目标项目版本为 {project_version}。"
                    f"只能应用到相同版本的项目。"
                )
                logger.warning(error_msg)
                return False, error_msg

            logger.info(f"版本验证通过: 配置版本 {config_version} 与项目版本 {project_version} 兼容")
            return True, ""

        except ValueError as e:
            error_msg = f"版本号格式错误: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _parse_version(self, version: str) -> Tuple[int, int]:
        """解析版本号

        支持格式:
        - "4.27" - 标准格式
        - "4.27.2" - 带补丁版本
        - "5.0" - UE5 格式
        - "5.3.1" - UE5 带补丁版本

        Args:
            version: 版本字符串（如 "4.27"）

        Returns:
            (主版本号, 次版本号)

        Raises:
            ValueError: 如果版本号格式不正确
        """
        if not version:
            raise ValueError("版本号不能为空")

        # 使用正则表达式提取主版本号和次版本号
        match = re.match(r'^(\d+)\.(\d+)', version)
        if not match:
            raise ValueError(f"无法解析版本号: {version}")

        major = int(match.group(1))
        minor = int(match.group(2))

        logger.debug(f"解析版本号: {version} -> 主版本={major}, 次版本={minor}")
        return major, minor
