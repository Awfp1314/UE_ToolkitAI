# -*- coding: utf-8 -*-

"""
会话管理器 - 多会话 CRUD 和持久化

负责：
- 会话的创建、切换、删除、重命名
- 会话索引维护（session_index.json）
- 每个会话独立 JSON 文件存储
- 旧版 chat_history.json 自动迁移
"""

import json
import uuid
import time
from typing import List, Dict, Optional
from pathlib import Path


class SessionInfo:
    """会话元数据"""

    def __init__(self, session_id: str, title: str = "新对话",
                 created_at: float = None, updated_at: float = None,
                 message_count: int = 0, ai_titled: bool = False):
        self.session_id = session_id
        self.title = title
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or self.created_at
        self.message_count = message_count
        self.ai_titled = ai_titled  # 是否已被 AI 命名

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "ai_titled": self.ai_titled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionInfo":
        return cls(
            session_id=data["session_id"],
            title=data.get("title", "新对话"),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
            message_count=data.get("message_count", 0),
            ai_titled=data.get("ai_titled", False),
        )


class SessionManager:
    """多会话管理器"""

    def __init__(self):
        self._sessions: List[SessionInfo] = []
        self._current_session_id: Optional[str] = None
        self._base_dir: Optional[Path] = None
        self._sessions_dir: Optional[Path] = None
        self._index_file: Optional[Path] = None
        self._init_paths()
        self._migrate_legacy()
        self._load_index()

        # 如果没有任何会话，创建一个默认的
        if not self._sessions:
            self.create_session()

        # 默认选中最近更新的会话
        if self._current_session_id is None and self._sessions:
            self._current_session_id = self._sessions[0].session_id

    # ------------------------------------------------------------------
    # 路径初始化
    # ------------------------------------------------------------------

    def _init_paths(self):
        """初始化存储路径"""
        try:
            from core.utils.path_utils import PathUtils
            path_utils = PathUtils()
            self._base_dir = path_utils.get_user_data_dir() / "ai_chat_history"
            self._base_dir.mkdir(parents=True, exist_ok=True)
            self._sessions_dir = self._base_dir / "sessions"
            self._sessions_dir.mkdir(parents=True, exist_ok=True)
            self._index_file = self._base_dir / "session_index.json"
        except Exception as e:
            print(f"[WARNING] SessionManager 路径初始化失败: {e}")

    # ------------------------------------------------------------------
    # 旧版迁移
    # ------------------------------------------------------------------

    def _migrate_legacy(self):
        """将旧版 chat_history.json 迁移为第一个会话"""
        if self._base_dir is None:
            return

        legacy_file = self._base_dir / "chat_history.json"
        if not legacy_file.exists():
            return

        # 如果索引已存在，说明已经迁移过
        if self._index_file and self._index_file.exists():
            return

        try:
            with open(legacy_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            messages = data.get("messages", [])
            if not messages:
                return

            # 创建新会话文件
            session_id = str(uuid.uuid4())[:8]
            title = self._extract_title(messages)

            session_file = self._sessions_dir / f"{session_id}.json"
            session_data = {
                "version": 2,
                "session_id": session_id,
                "messages": messages,
                "summary": data.get("summary"),
                "compressed_count": data.get("compressed_count", 0),
            }

            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

            # 创建索引
            info = SessionInfo(
                session_id=session_id,
                title=title,
                message_count=len(messages),
            )
            self._sessions = [info]
            self._current_session_id = session_id
            self._save_index()

            # 重命名旧文件（备份）
            legacy_file.rename(legacy_file.with_suffix(".json.bak"))
            print(f"[INFO] 已迁移旧版聊天记录到会话 {session_id}")

        except Exception as e:
            print(f"[WARNING] 迁移旧版聊天记录失败: {e}")

    # ------------------------------------------------------------------
    # 索引管理
    # ------------------------------------------------------------------

    def _load_index(self):
        """加载会话索引"""
        if not self._index_file or not self._index_file.exists():
            return

        try:
            with open(self._index_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            sessions_data = data.get("sessions", [])
            self._sessions = [SessionInfo.from_dict(s) for s in sessions_data]
            self._current_session_id = data.get("current_session_id")

            # 按 updated_at 降序排列
            self._sessions.sort(key=lambda s: s.updated_at, reverse=True)

        except Exception as e:
            print(f"[WARNING] 加载会话索引失败: {e}")

    def _save_index(self):
        """保存会话索引"""
        if not self._index_file:
            return

        try:
            data = {
                "version": 1,
                "current_session_id": self._current_session_id,
                "sessions": [s.to_dict() for s in self._sessions],
            }
            tmp = self._index_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(self._index_file)
        except Exception as e:
            print(f"[WARNING] 保存会话索引失败: {e}")

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id

    def get_sessions(self) -> List[SessionInfo]:
        """获取所有会话（按更新时间降序）"""
        return list(self._sessions)

    def get_current_session(self) -> Optional[SessionInfo]:
        """获取当前会话信息"""
        for s in self._sessions:
            if s.session_id == self._current_session_id:
                return s
        return None

    def create_session(self, title: str = "新对话") -> SessionInfo:
        """创建新会话并切换到它"""
        session_id = str(uuid.uuid4())[:8]
        info = SessionInfo(session_id=session_id, title=title)
        self._sessions.insert(0, info)
        self._current_session_id = session_id

        # 创建空的会话文件
        self._save_session_file(session_id, [], None, 0)
        self._save_index()

        print(f"[INFO] 创建新会话: {session_id} ({title})")
        return info

    def switch_session(self, session_id: str) -> bool:
        """切换到指定会话"""
        for s in self._sessions:
            if s.session_id == session_id:
                self._current_session_id = session_id
                self._save_index()
                print(f"[INFO] 切换到会话: {session_id} ({s.title})")
                return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """删除指定会话"""
        target = None
        for s in self._sessions:
            if s.session_id == session_id:
                target = s
                break

        if not target:
            return False

        self._sessions.remove(target)

        # 删除会话文件
        if self._sessions_dir:
            session_file = self._sessions_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()

        # 如果删除的是当前会话，切换到第一个或创建新的
        if self._current_session_id == session_id:
            if self._sessions:
                self._current_session_id = self._sessions[0].session_id
            else:
                new_session = self.create_session()
                self._current_session_id = new_session.session_id

        self._save_index()
        print(f"[INFO] 删除会话: {session_id}")
        return True

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """重命名会话"""
        for s in self._sessions:
            if s.session_id == session_id:
                s.title = new_title.strip() or "新对话"
                self._save_index()
                return True
        return False

    def update_session_title_from_message(self, session_id: str, first_message: str):
        """从第一条用户消息自动生成会话标题"""
        for s in self._sessions:
            if s.session_id == session_id and s.title == "新对话":
                s.title = self._truncate_title(first_message)
                self._save_index()
                return

    def update_session_meta(self, session_id: str, message_count: int):
        """更新会话元数据（消息数、更新时间）"""
        for s in self._sessions:
            if s.session_id == session_id:
                s.message_count = message_count
                s.updated_at = time.time()
                # 重新排序
                self._sessions.sort(key=lambda x: x.updated_at, reverse=True)
                self._save_index()
                return

    # ------------------------------------------------------------------
    # 会话文件读写
    # ------------------------------------------------------------------

    def load_session_messages(self, session_id: str) -> dict:
        """加载指定会话的消息数据

        Returns:
            {"messages": [...], "summary": str|None, "compressed_count": int}
        """
        if not self._sessions_dir:
            return {"messages": [], "summary": None, "compressed_count": 0}

        session_file = self._sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return {"messages": [], "summary": None, "compressed_count": 0}

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "messages": data.get("messages", []),
                "summary": data.get("summary"),
                "compressed_count": data.get("compressed_count", 0),
            }
        except Exception as e:
            print(f"[WARNING] 加载会话 {session_id} 失败: {e}")
            return {"messages": [], "summary": None, "compressed_count": 0}

    def save_session_messages(self, session_id: str, messages: list,
                              summary: Optional[str] = None,
                              compressed_count: int = 0):
        """保存会话消息"""
        self._save_session_file(session_id, messages, summary, compressed_count)

        # 更新元数据
        msg_count = len([m for m in messages if m.get("role") in ("user", "assistant")])
        self.update_session_meta(session_id, msg_count)

    def _save_session_file(self, session_id: str, messages: list,
                           summary: Optional[str], compressed_count: int):
        """写入会话文件"""
        if not self._sessions_dir:
            return

        try:
            session_file = self._sessions_dir / f"{session_id}.json"
            data = {
                "version": 2,
                "session_id": session_id,
                "messages": messages,
            }
            if summary is not None:
                data["summary"] = summary
                data["compressed_count"] = compressed_count

            tmp = session_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(session_file)
        except Exception as e:
            print(f"[WARNING] 保存会话 {session_id} 失败: {e}")

    def get_session_file_path(self, session_id: str) -> Optional[Path]:
        """获取会话文件路径"""
        if self._sessions_dir:
            return self._sessions_dir / f"{session_id}.json"
        return None

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_title(messages: list) -> str:
        """从消息列表提取标题"""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                return SessionManager._truncate_title(content)
        return "新对话"

    @staticmethod
    def _truncate_title(text: str) -> str:
        """截取文本作为标题（最多15字符）"""
        # 去掉附件信息
        text = text.split("\n\n[附加")[0].strip()
        text = text.replace("\n", " ").strip()
        if len(text) > 15:
            return text[:15] + "..."
        return text or "新对话"
