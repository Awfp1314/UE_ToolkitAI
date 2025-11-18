"""
搜索引擎类

提供资产搜索和排序功能，支持拼音搜索。
"""

import os
from typing import List, Dict, Optional
from logging import Logger


class SearchEngine:
    """搜索引擎类
    
    提供资产搜索和排序功能：
    - 支持按名称、描述、分类搜索
    - 支持拼音搜索（如果 pypinyin 可用）
    - 支持多种排序方式
    - 拼音依赖降级策略
    """
    
    # 支持的排序方法
    SORT_METHODS = [
        "添加时间（最新）",
        "添加时间（最旧）",
        "名称（A-Z）",
        "名称（Z-A）",
        "分类（A-Z）",
        "分类（Z-A）"
    ]
    
    def __init__(self, logger: Logger):
        """初始化搜索引擎
        
        Args:
            logger: 日志记录器
        """
        self._logger = logger
        self._mock_mode = os.environ.get('ASSET_MANAGER_MOCK_MODE') == '1'
        self._pinyin_cache: Dict[str, Dict[str, str]] = {}
        
        # 尝试导入 pypinyin
        self._pypinyin_available = False
        try:
            import pypinyin
            self._pypinyin = pypinyin
            self._pypinyin_available = True
            self._logger.info("pypinyin is available, pinyin search enabled")
        except ImportError:
            self._logger.warning(
                "pypinyin not installed, pinyin search disabled. "
                "Install with: pip install pypinyin"
            )
        
        if self._mock_mode:
            self._logger.info("SearchEngine: Mock mode enabled")
    
    def get_pinyin(self, text: str) -> str:
        """获取文本的拼音（全拼）

        Args:
            text: 输入文本

        Returns:
            str: 拼音字符串（小写，无分隔符）
        """
        if not text:
            return ""

        if not self._pypinyin_available:
            return text.lower()

        try:
            # 使用 pypinyin 转换
            pinyin_list = self._pypinyin.lazy_pinyin(text)
            return ''.join(pinyin_list).lower()
        except Exception as e:
            self._logger.warning(f"Failed to convert to pinyin: {e}")
            return text.lower()

    def get_pinyin_initials(self, text: str) -> str:
        """获取文本的拼音首字母

        Args:
            text: 输入文本

        Returns:
            str: 拼音首字母字符串（小写）
        """
        if not text:
            return ""

        if not self._pypinyin_available:
            return text.lower()

        try:
            # 使用 pypinyin 转换，只取首字母
            pinyin_list = self._pypinyin.lazy_pinyin(text)
            return ''.join([p[0] for p in pinyin_list if p]).lower()
        except Exception as e:
            self._logger.warning(f"Failed to convert to pinyin initials: {e}")
            return text.lower()
    
    def build_pinyin_cache(self, assets: List) -> Dict[str, Dict[str, str]]:
        """构建拼音缓存（包含全拼和首字母）

        Args:
            assets: 资产列表

        Returns:
            Dict: 拼音缓存 {asset_id: {
                'name_pinyin': str,           # 全拼
                'name_initials': str,         # 首字母
                'desc_pinyin': str,
                'desc_initials': str,
                'category_pinyin': str,
                'category_initials': str
            }}
        """
        cache = {}
        for asset in assets:
            asset_id = getattr(asset, 'id', str(id(asset)))
            name = getattr(asset, 'name', '')
            desc = getattr(asset, 'description', '')
            category = getattr(asset, 'category', '')

            cache[asset_id] = {
                'name_pinyin': self.get_pinyin(name),
                'name_initials': self.get_pinyin_initials(name),
                'desc_pinyin': self.get_pinyin(desc),
                'desc_initials': self.get_pinyin_initials(desc),
                'category_pinyin': self.get_pinyin(category),
                'category_initials': self.get_pinyin_initials(category)
            }
        self._pinyin_cache = cache
        return cache
    
    def search(
        self,
        assets: List,
        search_text: str,
        category: Optional[str] = None
    ) -> List:
        """搜索资产

        Args:
            assets: 资产列表
            search_text: 搜索文本
            category: 可选的分类过滤

        Returns:
            List: 匹配的资产列表
        """
        try:
            if not assets:
                return []

            # 先按分类过滤
            filtered = assets
            if category:
                filtered = [a for a in assets if getattr(a, 'category', '') == category]

            # 如果没有搜索文本，返回过滤后的结果
            if not search_text:
                return filtered

            # 搜索文本转小写
            search_lower = search_text.lower()
            search_pinyin = self.get_pinyin(search_text)

            # 判断搜索文本是否包含中文字符
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in search_text)

            # 首字母匹配策略：
            # 1. 如果包含中文，不使用首字母匹配（中文直接匹配 + 拼音全拼匹配）
            # 2. 如果是纯字母且长度 <= 3，启用首字母匹配（如 ht, abc）
            # 3. 如果是纯字母且长度 > 3，不使用首字母匹配（如 wester, hutao）
            is_short_alpha = search_lower.isalpha() and len(search_lower) <= 3
            use_initials = not has_chinese and is_short_alpha
            search_initials = self.get_pinyin_initials(search_text) if use_initials else ""

            # 搜索匹配
            results = []
            for asset in filtered:
                name = getattr(asset, 'name', '')
                desc = getattr(asset, 'description', '')
                cat = getattr(asset, 'category', '')

                # 检查直接匹配
                if (search_lower in name.lower() or
                    search_lower in desc.lower() or
                    search_lower in cat.lower()):
                    results.append(asset)
                    continue

                # 检查拼音匹配（如果可用）
                if self._pypinyin_available:
                    asset_id = getattr(asset, 'id', str(id(asset)))
                    if asset_id in self._pinyin_cache:
                        cache = self._pinyin_cache[asset_id]

                        # 基础匹配：拼音全拼匹配
                        matched = (search_pinyin in cache.get('name_pinyin', '') or
                                  search_pinyin in cache.get('desc_pinyin', '') or
                                  search_pinyin in cache.get('category_pinyin', ''))

                        # 如果启用首字母匹配，则额外检查首字母
                        if not matched and use_initials and search_initials:
                            matched = (search_initials in cache.get('name_initials', '') or
                                      search_initials in cache.get('desc_initials', '') or
                                      search_initials in cache.get('category_initials', ''))

                        if matched:
                            results.append(asset)

            return results

        except Exception as e:
            self._logger.warning(f"Search failed: {e}, returning original list")
            return assets
    
    def sort(self, assets: List, sort_method: str) -> List:
        """排序资产

        Args:
            assets: 资产列表
            sort_method: 排序方法

        Returns:
            List: 排序后的资产列表
        """
        try:
            if not assets:
                return []

            if sort_method not in self.SORT_METHODS:
                self._logger.warning(f"Unknown sort method: {sort_method}, returning original list")
                return assets

            # 复制列表避免修改原列表
            sorted_assets = assets.copy()

            # 按添加时间排序
            if sort_method == "添加时间（最新）":
                sorted_assets.sort(
                    key=lambda a: getattr(a, 'added_time', ''),
                    reverse=True
                )
            elif sort_method == "添加时间（最旧）":
                sorted_assets.sort(
                    key=lambda a: getattr(a, 'added_time', '')
                )

            # 按名称排序
            elif sort_method == "名称（A-Z）":
                if self._pypinyin_available:
                    sorted_assets.sort(
                        key=lambda a: self.get_pinyin(getattr(a, 'name', ''))
                    )
                else:
                    sorted_assets.sort(
                        key=lambda a: getattr(a, 'name', '').lower()
                    )
            elif sort_method == "名称（Z-A）":
                if self._pypinyin_available:
                    sorted_assets.sort(
                        key=lambda a: self.get_pinyin(getattr(a, 'name', '')),
                        reverse=True
                    )
                else:
                    sorted_assets.sort(
                        key=lambda a: getattr(a, 'name', '').lower(),
                        reverse=True
                    )

            # 按分类排序
            elif sort_method == "分类（A-Z）":
                if self._pypinyin_available:
                    sorted_assets.sort(
                        key=lambda a: self.get_pinyin(getattr(a, 'category', ''))
                    )
                else:
                    sorted_assets.sort(
                        key=lambda a: getattr(a, 'category', '').lower()
                    )
            elif sort_method == "分类（Z-A）":
                if self._pypinyin_available:
                    sorted_assets.sort(
                        key=lambda a: self.get_pinyin(getattr(a, 'category', '')),
                        reverse=True
                    )
                else:
                    sorted_assets.sort(
                        key=lambda a: getattr(a, 'category', '').lower(),
                        reverse=True
                    )

            return sorted_assets

        except Exception as e:
            self._logger.warning(f"Sort failed: {e}, returning original list")
            return assets

