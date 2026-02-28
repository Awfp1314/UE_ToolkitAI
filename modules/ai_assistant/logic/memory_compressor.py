# -*- coding: utf-8 -*-

"""
渐进式对话历史压缩模块

策略：
- 对话不超过阈值时，全部原样发送
- 超过阈值后，把最老的几轮追加压缩到已有摘要上（渐进式）
- 压缩调用用户已配置的 LLM API，不依赖本地语义模型
- 压缩在 AI 回复完成后异步执行，不阻塞用户输入
"""

from typing import List, Dict, Optional, Callable
from core.logger import get_logger

logger = get_logger(__name__)

# 默认配置
DEFAULT_MAX_ROUNDS = 10      # 超过此轮数触发压缩
DEFAULT_KEEP_RECENT = 5      # 保留最近 N 轮原始消息
DEFAULT_MODEL = "gemini-2.5-flash"


class MemoryCompressor:
    """渐进式对话压缩器

    每次只压缩最老的几轮到已有摘要上，token 消耗很小。
    发送时结构：[system] + [摘要] + [最近 keep_recent 轮]
    """

    def __init__(
        self,
        api_client_factory: Optional[Callable] = None,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        keep_recent: int = DEFAULT_KEEP_RECENT,
        compression_model: str = DEFAULT_MODEL,
    ):
        self.api_client_factory = api_client_factory
        self.max_rounds = max_rounds
        self.keep_recent = keep_recent
        self.compression_model = compression_model

        # 累积摘要（渐进式追加）
        self._summary: Optional[str] = None
        # 已压缩的消息数量（用于判断哪些是新的需要压缩的）
        self._compressed_count: int = 0

        logger.info(
            f"渐进式压缩器初始化（阈值: {max_rounds} 轮, 保留: {keep_recent} 轮, 模型: {compression_model}）"
        )

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    @property
    def summary(self) -> Optional[str]:
        return self._summary

    @summary.setter
    def summary(self, value: Optional[str]):
        self._summary = value

    @property
    def compressed_count(self) -> int:
        return self._compressed_count

    @compressed_count.setter
    def compressed_count(self, value: int):
        self._compressed_count = value

    def needs_compression(self, total_messages: int) -> bool:
        """判断是否需要压缩"""
        keep_count = self.keep_recent * 2  # 每轮 = user + assistant
        uncompressed = total_messages - self._compressed_count
        return uncompressed > keep_count + 4  # 留点余量再压缩

    def build_context_messages(
        self, all_messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """构建发送给 API 的消息列表（摘要 + 最近 N 轮）

        Returns:
            消息列表（不含 system 提示词，调用方自行添加）
        """
        keep_count = self.keep_recent * 2
        recent = all_messages[-keep_count:] if len(all_messages) > keep_count else all_messages

        result = []
        if self._summary:
            result.append({
                "role": "system",
                "content": f"[之前的对话摘要]\n{self._summary}",
            })
        result.extend(recent)
        return result

    def compress_oldest(self, all_messages: List[Dict[str, str]]) -> bool:
        """将最老的未压缩消息追加压缩到摘要中（渐进式）

        Args:
            all_messages: 全部 user/assistant 消息

        Returns:
            是否成功压缩
        """
        keep_count = self.keep_recent * 2
        if len(all_messages) <= keep_count:
            return False

        # 需要压缩的消息：从已压缩位置到保留区之前
        to_compress = all_messages[self._compressed_count : -keep_count]
        if not to_compress:
            return False

        logger.info(f"开始渐进式压缩 {len(to_compress)} 条消息...")

        new_summary = self._do_compress(to_compress, self._summary)
        if new_summary:
            self._summary = new_summary
            self._compressed_count = len(all_messages) - keep_count
            logger.info(f"压缩完成，摘要长度: {len(new_summary)} 字")
            return True

        return False

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _do_compress(
        self, messages: List[Dict[str, str]], existing_summary: Optional[str]
    ) -> Optional[str]:
        """调用 LLM 生成/追加摘要"""
        if self.api_client_factory:
            result = self._compress_via_api(messages, existing_summary)
            if result:
                return result

        # 兜底：纯文本摘要（不消耗 token）
        return self._simple_summary(messages, existing_summary)

    def _compress_via_api(
        self, messages: List[Dict[str, str]], existing_summary: Optional[str]
    ) -> Optional[str]:
        """通过 LLM API 压缩（同步 HTTP 请求，在后台线程中调用）"""
        try:
            import requests
            import json
            import os

            prompt = self._build_prompt(messages, existing_summary)

            # 读取 AI 助手配置获取 API 信息
            from core.config.config_manager import ConfigManager
            from pathlib import Path

            template_path = Path(__file__).parent.parent / "config_template.json"
            config_manager = ConfigManager("ai_assistant", template_path=template_path)
            config = config_manager.get_module_config()

            provider = config.get("llm_provider", "api")

            if provider == "api":
                api_settings = config.get("api_settings", {})
                api_url = api_settings.get("api_url", "")
                api_key = api_settings.get("api_key", "")
                model = api_settings.get("default_model", self.compression_model)

                if not api_url or not api_key:
                    logger.warning("压缩：API 未配置，使用纯文本兜底")
                    return None

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}" if not api_key.startswith("Bearer ") else api_key,
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                    "stream": False,
                }

                # 临时清除代理
                env_backup = {}
                proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
                for var in proxy_vars:
                    if var in os.environ:
                        env_backup[var] = os.environ[var]
                        del os.environ[var]

                try:
                    resp = requests.post(api_url, headers=headers, json=payload, timeout=20,
                                         proxies={"http": None, "https": None})
                finally:
                    for var, value in env_backup.items():
                        os.environ[var] = value

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()

                logger.warning(f"压缩 API 返回异常: {resp.status_code}")
                return None

            elif provider == "ollama":
                ollama_settings = config.get("ollama_settings", {})
                base_url = ollama_settings.get("base_url", "http://localhost:11434")
                model = ollama_settings.get("default_model", "")

                if not model:
                    logger.warning("压缩：Ollama 模型未配置，使用纯文本兜底")
                    return None

                import httpx
                resp = httpx.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                    timeout=20,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", "").strip()

                logger.warning(f"压缩 Ollama 返回异常: {resp.status_code}")
                return None

            return None

        except Exception as e:
            logger.error(f"API 压缩异常: {e}", exc_info=True)
            return None

    def _build_prompt(
        self, messages: List[Dict[str, str]], existing_summary: Optional[str]
    ) -> str:
        """构建压缩提示词"""
        conv_lines = []
        for msg in messages:
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    item.get("text", "") for item in content if item.get("type") == "text"
                )
            # 截断过长的单条消息
            if len(content) > 500:
                content = content[:500] + "..."
            conv_lines.append(f"{role}: {content}")

        conversation = "\n".join(conv_lines)

        if existing_summary:
            return (
                f"已有对话摘要：\n{existing_summary}\n\n"
                f"以下是新增的对话内容：\n{conversation}\n\n"
                f"请将已有摘要和新增内容合并，生成一份更新后的简洁摘要（150字以内）。"
                f"保留关键信息、用户意图和重要技术细节，忽略寒暄。"
            )
        else:
            return (
                f"以下是一段对话：\n{conversation}\n\n"
                f"请生成简洁摘要（100字以内），保留关键信息和用户意图。"
            )

    def generate_title(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """根据对话内容生成简短会话标题

        策略：先尝试 LLM 生成，失败则用本地关键词提取兜底。

        Args:
            messages: 对话消息列表

        Returns:
            生成的标题字符串，失败返回 None
        """
        if not messages:
            return None

        # 收集用户消息内容
        user_contents = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        item.get("text", "") for item in content if item.get("type") == "text"
                    )
                # 去掉附件信息
                content = content.split("\n\n[附加")[0].strip()
                if content:
                    user_contents.append(content)

        if not user_contents:
            return None

        # 尝试 LLM 生成标题
        title = self._generate_title_via_llm(messages)
        if title:
            return title

        # 兜底：本地关键词提取
        logger.info("LLM 标题生成失败，使用本地关键词提取")
        return self._generate_title_local(user_contents)

    def _generate_title_via_llm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """通过 LLM 生成标题"""
        sample = messages[:10]
        conv_lines = []
        for msg in sample:
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    item.get("text", "") for item in content if item.get("type") == "text"
                )
            if len(content) > 200:
                content = content[:200] + "..."
            conv_lines.append(f"{role}: {content}")

        conversation = "\n".join(conv_lines)
        prompt = (
            f"以下是一段对话：\n{conversation}\n\n"
            f"请用一个简短的标题（不超过15个字）概括这段对话的主题。"
            f"只返回标题本身，不要加引号、序号或其他任何内容。"
        )

        try:
            title = self._call_llm_for_text(prompt)
            if title:
                title = title.strip().strip('"\'""「」【】').strip()
                # 去掉可能的换行
                title = title.split("\n")[0].strip()
                if len(title) > 15:
                    title = title[:15] + "..."
                return title if title else None
        except Exception as e:
            logger.warning(f"LLM 生成标题失败: {e}")

        return None

    @staticmethod
    def _generate_title_local(user_contents: List[str]) -> Optional[str]:
        """本地关键词提取生成标题（不依赖网络）

        从用户消息中提取最有信息量的片段作为标题。
        """
        import re

        # 过滤掉太短或无意义的消息
        meaningful = []
        skip_patterns = [
            r'^(你好|hi|hello|嗨|hey|ok|好的|谢谢|嗯|哦|是的|对|行|可以)[\s!！。.？?]*$',
        ]
        for content in user_contents:
            content_clean = content.strip()
            if len(content_clean) < 3:
                continue
            if any(re.match(p, content_clean, re.IGNORECASE) for p in skip_patterns):
                continue
            meaningful.append(content_clean)

        if not meaningful:
            # 全是寒暄，用第一条有内容的消息
            meaningful = [c for c in user_contents if len(c.strip()) > 1]
            if not meaningful:
                return None

        # 取最有信息量的一条（最长的前几条中选第一条）
        # 优先选第一条有意义的消息（通常是用户的核心需求）
        best = meaningful[0]

        # 清理换行和多余空格
        best = best.replace("\n", " ").strip()
        best = re.sub(r'\s+', ' ', best)

        # 截取合适长度
        if len(best) > 15:
            # 尝试在标点处截断
            for i in range(15, min(len(best), 20)):
                if best[i] in '，。、！？,.!? ':
                    return best[:i]
            return best[:15] + "..."

        return best

    def _call_llm_for_text(self, prompt: str) -> Optional[str]:
        """通用 LLM 文本调用（同步，用于后台线程）"""
        try:
            import requests
            import os
            from core.config.config_manager import ConfigManager
            from pathlib import Path

            template_path = Path(__file__).parent.parent / "config_template.json"
            config_manager = ConfigManager("ai_assistant", template_path=template_path)
            config = config_manager.get_module_config()
            provider = config.get("llm_provider", "api")

            if provider == "api":
                api_settings = config.get("api_settings", {})
                api_url = api_settings.get("api_url", "")
                api_key = api_settings.get("api_key", "")
                model = api_settings.get("default_model", self.compression_model)

                if not api_url or not api_key:
                    return None

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}" if not api_key.startswith("Bearer ") else api_key,
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 50,
                    "stream": False,
                }

                env_backup = {}
                proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
                for var in proxy_vars:
                    if var in os.environ:
                        env_backup[var] = os.environ[var]
                        del os.environ[var]
                try:
                    resp = requests.post(api_url, headers=headers, json=payload, timeout=15,
                                         proxies={"http": None, "https": None})
                finally:
                    for var, value in env_backup.items():
                        os.environ[var] = value

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()

            elif provider == "ollama":
                ollama_settings = config.get("ollama_settings", {})
                base_url = ollama_settings.get("base_url", "http://localhost:11434")
                model = ollama_settings.get("default_model", "")
                if not model:
                    return None

                import httpx
                resp = httpx.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", "").strip()

        except Exception as e:
            logger.warning(f"LLM 调用失败: {e}")

        return None

    @staticmethod
    def _simple_summary(
        messages: List[Dict[str, str]], existing_summary: Optional[str]
    ) -> str:
        """纯文本兜底摘要（不消耗 token）"""
        topics = []
        for msg in messages:
            if msg["role"] == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        item.get("text", "") for item in content if item.get("type") == "text"
                    )
                if content:
                    topics.append(content[:40] + "..." if len(content) > 40 else content)

        new_part = "、".join(topics[:3])
        if len(topics) > 3:
            new_part += f" 等{len(topics)}个话题"

        if existing_summary:
            return f"{existing_summary}；后续又讨论了{new_part}"
        return f"用户讨论了{new_part}"
