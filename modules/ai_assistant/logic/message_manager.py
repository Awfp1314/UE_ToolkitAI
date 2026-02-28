# -*- coding: utf-8 -*-

"""
消息管理器 - 从 ChatController 提取的消息数据层

负责：
- 消息历史存储与管理
- 消息格式化（附件拼接、显示文本构建）
- 消息验证
- 当前 AI 回复文本的累积
- 聊天记录持久化（JSON 文件）
"""

import json
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path


# 持久化保存的最大消息轮数（user+assistant 算一轮）
MAX_PERSISTED_ROUNDS = 50


class MessageManager:
    """消息数据管理器

    管理对话历史、消息格式化和验证逻辑。
    支持多会话：通过 SessionManager 按 session_id 加载/保存。
    """

    def __init__(self, session_manager=None):
        # 对话历史
        self._conversation_history: List[Dict[str, str]] = []
        # 当前 AI 回复的累积文本
        self._current_response_text: str = ""
        # 压缩摘要（由 MemoryCompressor 写入）
        self._compressed_summary: Optional[str] = None
        self._compressed_count: int = 0
        # 会话管理器
        self._session_manager = session_manager
        # 启动时自动加载当前会话
        self._load_history()

    # ------------------------------------------------------------------
    # 对话历史访问
    # ------------------------------------------------------------------

    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        """获取对话历史（只读引用）"""
        return self._conversation_history

    @property
    def current_response_text(self) -> str:
        """获取当前 AI 回复的累积文本"""
        return self._current_response_text

    # ------------------------------------------------------------------
    # 消息格式化
    # ------------------------------------------------------------------

    def build_full_message(
        self, message: str, attachments: Optional[list] = None
    ) -> Tuple[str, str]:
        """构建完整消息内容（包含附件信息）

        Args:
            message: 用户输入的原始消息文本
            attachments: 附件列表，每个附件为 dict，包含 type/name/path/data

        Returns:
            (display_message, full_message) 元组
            - display_message: 用于 UI 显示的简短文本
            - full_message: 包含附件详情的完整文本（发送给 API）
        """
        attachments = attachments or []

        if not message and not attachments:
            return ("", "")

        message = message.strip() if message else ""
        full_message = message

        if attachments:
            attachment_info = []
            for att in attachments:
                info = self._format_attachment(att)
                if info:
                    attachment_info.append(info)
            full_message = message + "".join(attachment_info)

        display_message = message if message else f"[已添加 {len(attachments)} 个附件]"
        return (display_message, full_message)

    @staticmethod
    def _format_attachment(att: Dict[str, Any]) -> str:
        """格式化单个附件为文本描述

        Args:
            att: 附件字典，包含 type, name, path, data 等字段

        Returns:
            格式化后的附件文本，若类型未知则返回空字符串
        """
        att_type = att.get("type", "")

        if att_type == "asset":
            asset_data = att.get("data", {})
            tree = asset_data.get("tree", "")
            files = asset_data.get("files", [])

            info = f"\n\n[附加资产: {att['name']}]\n"
            info += f"路径: {att['path']}\n"
            if tree:
                info += f"\n目录结构:\n```\n{tree}\n```\n"
            if files:
                info += f"\n文件列表 ({len(files)} 个文件):\n"
                for f in files[:20]:
                    info += f"  - {f}\n"
                if len(files) > 20:
                    info += f"  ... 还有 {len(files) - 20} 个文件\n"
            return info

        elif att_type == "config":
            info = f"\n\n[附加配置: {att['name']}]\n"
            info += f"路径: {att['path']}\n"
            return info

        return ""

    # ------------------------------------------------------------------
    # 消息验证
    # ------------------------------------------------------------------

    @staticmethod
    def validate_message(message: str, attachments: Optional[list] = None) -> bool:
        """验证消息是否有效（非空或有附件）

        Args:
            message: 用户输入的消息文本
            attachments: 附件列表

        Returns:
            True 表示消息有效，False 表示无效
        """
        attachments = attachments or []
        has_text = bool(message and message.strip())
        has_attachments = bool(attachments)
        return has_text or has_attachments

    # ------------------------------------------------------------------
    # 对话历史管理
    # ------------------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        """添加用户消息到对话历史

        Args:
            content: 用户消息内容（包含附件信息的完整文本）
        """
        self._conversation_history.append({
            "role": "user",
            "content": content,
        })

    def add_assistant_message(self, content: str) -> None:
        """添加助手回复到对话历史

        Args:
            content: 助手回复内容
        """
        self._conversation_history.append({
            "role": "assistant",
            "content": content,
        })

    def remove_last_assistant_message(self) -> bool:
        """移除最后一条助手回复（用于重新生成）

        Returns:
            True 表示成功移除，False 表示没有可移除的助手消息
        """
        if (
            self._conversation_history
            and self._conversation_history[-1].get("role") == "assistant"
        ):
            self._conversation_history.pop()
            return True
        return False

    def get_last_user_message(self) -> Optional[str]:
        """获取最后一条用户消息内容

        Returns:
            最后一条用户消息的文本，若不存在则返回 None
        """
        for msg in reversed(self._conversation_history):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return None

    def get_user_and_assistant_messages(self) -> List[Dict[str, str]]:
        """获取对话历史中的用户和助手消息（不含系统消息）

        Returns:
            仅包含 role 为 user/assistant 的消息列表
        """
        return [
            msg for msg in self._conversation_history
            if msg.get("role") in ("user", "assistant")
        ]

    def has_enough_history_for_regeneration(self) -> bool:
        """检查对话历史是否足够进行重新生成

        Returns:
            True 表示至少有 2 条消息（可以重新生成）
        """
        return len(self._conversation_history) >= 2

    # ------------------------------------------------------------------
    # 系统提示词管理
    # ------------------------------------------------------------------

    def update_system_prompt(self, system_prompt: str) -> None:
        """更新对话历史中的系统提示词

        如果历史中已有系统消息则更新，否则插入到开头。

        Args:
            system_prompt: 新的系统提示词内容
        """
        if (
            self._conversation_history
            and self._conversation_history[0].get("role") == "system"
        ):
            self._conversation_history[0]["content"] = system_prompt
        else:
            self._conversation_history.insert(0, {
                "role": "system",
                "content": system_prompt,
            })

    def has_system_prompt(self) -> bool:
        """检查对话历史中是否已有系统提示词"""
        return any(
            msg.get("role") == "system" for msg in self._conversation_history
        )

    # ------------------------------------------------------------------
    # 当前回复文本累积
    # ------------------------------------------------------------------

    def reset_current_response(self) -> None:
        """重置当前 AI 回复的累积文本"""
        self._current_response_text = ""

    def append_to_current_response(self, chunk: str) -> None:
        """追加数据块到当前 AI 回复

        Args:
            chunk: 流式接收到的文本片段
        """
        self._current_response_text += chunk

    def finalize_current_response(self) -> str:
        """完成当前 AI 回复：添加到历史并重置累积文本

        Returns:
            完整的 AI 回复文本
        """
        response_text = self._current_response_text
        if response_text:
            self.add_assistant_message(response_text)
        self._current_response_text = ""
        # 一轮对话结束，持久化保存
        self._save_history()
        return response_text

    # ------------------------------------------------------------------
    # 聊天记录持久化（通过 SessionManager）
    # ------------------------------------------------------------------

    def _save_history(self) -> None:
        """将对话历史持久化（防御式，不抛异常）"""
        try:
            if self._session_manager is None:
                return

            session_id = self._session_manager.current_session_id
            if not session_id:
                return

            # 只保存 user/assistant 消息，跳过 system
            messages_to_save = [
                msg for msg in self._conversation_history
                if msg.get("role") in ("user", "assistant")
            ]

            # 限制保存数量（最近 MAX_PERSISTED_ROUNDS 轮）
            max_messages = MAX_PERSISTED_ROUNDS * 2
            if len(messages_to_save) > max_messages:
                messages_to_save = messages_to_save[-max_messages:]

            self._session_manager.save_session_messages(
                session_id,
                messages_to_save,
                summary=self._compressed_summary,
                compressed_count=self._compressed_count,
            )
        except Exception as e:
            print(f"[WARNING] 保存聊天记录失败: {e}")

    def _load_history(self) -> None:
        """从当前会话加载对话历史（防御式，不抛异常）"""
        try:
            if self._session_manager is None:
                return

            session_id = self._session_manager.current_session_id
            if not session_id:
                return

            data = self._session_manager.load_session_messages(session_id)
            messages = data.get("messages", [])

            self._conversation_history.clear()
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    self._conversation_history.append(
                        {"role": role, "content": content}
                    )

            # 恢复压缩摘要
            self._compressed_summary = data.get("summary")
            self._compressed_count = data.get("compressed_count", 0)

            if self._conversation_history:
                print(f"[INFO] 已恢复 {len(self._conversation_history)} 条聊天记录 (session={session_id})")
            if self._compressed_summary:
                print(f"[INFO] 已恢复对话摘要（{len(self._compressed_summary)} 字）")
        except Exception as e:
            print(f"[WARNING] 加载聊天记录失败: {e}")

    def switch_session(self, session_id: str) -> None:
        """切换到指定会话（清空当前历史，加载新会话）"""
        self._conversation_history.clear()
        self._current_response_text = ""
        self._compressed_summary = None
        self._compressed_count = 0

        if self._session_manager:
            self._session_manager.switch_session(session_id)

        self._load_history()

    def get_persisted_messages(self) -> List[Dict[str, str]]:
        """获取已持久化的 user/assistant 消息（供 UI 恢复气泡用）

        Returns:
            仅包含 role 为 user/assistant 的消息列表副本
        """
        return [
            dict(msg) for msg in self._conversation_history
            if msg.get("role") in ("user", "assistant")
        ]

    def clear_history(self) -> None:
        """清空当前会话的对话历史"""
        self._conversation_history.clear()
        self._current_response_text = ""
        self._compressed_summary = None
        self._compressed_count = 0
        # 保存空历史到当前会话文件
        self._save_history()
