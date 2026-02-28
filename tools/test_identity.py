# -*- coding: utf-8 -*-
"""测试身份设定读取"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.ai_services import EmbeddingService
from modules.ai_assistant.logic.enhanced_memory_manager import EnhancedMemoryManager


def main():
    print("=" * 60)
    print("[测试] 身份设定读取")
    print("=" * 60)
    
    # 创建记忆管理器
    embedding_service = EmbeddingService()
    memory = EnhancedMemoryManager(
        user_id="default",
        embedding_service=embedding_service
    )
    
    print(f"\n[统计] 用户级记忆数量: {len(memory.user_memories)}")
    
    # 获取身份设定
    print("\n" + "=" * 60)
    print("[调用] get_user_identity()")
    print("=" * 60)
    
    identity = memory.get_user_identity()
    
    print(f"\n[结果] 返回内容长度: {len(identity)} 字符")
    print("\n[内容]:")
    print("-" * 40)
    print(identity if identity else "(空)")
    print("-" * 40)
    
    # 显示所有包含身份关键词的记忆
    print("\n" + "=" * 60)
    print("[分析] 所有包含身份关键词的记忆")
    print("=" * 60)
    
    ai_keywords = ['你是', '从现在开始', '猫娘', '胡桃', '薇尔莉特']
    user_keywords = ['我是', '我叫']
    
    ai_memories = []
    user_memories = []
    
    for m in memory.user_memories:
        content = m.content
        for kw in ai_keywords:
            if kw in content:
                ai_memories.append((m.timestamp, m.importance, content))
                break
        for kw in user_keywords:
            if kw in content:
                user_memories.append((m.timestamp, m.importance, content))
                break
    
    print(f"\n[AI身份设定] 找到 {len(ai_memories)} 条:")
    for ts, imp, content in sorted(ai_memories, key=lambda x: x[0])[-5:]:
        print(f"  [{ts[:19]}] 重要性:{imp:.1f} | {content[:60]}...")
    
    print(f"\n[用户身份] 找到 {len(user_memories)} 条:")
    for ts, imp, content in sorted(user_memories, key=lambda x: x[0])[-5:]:
        print(f"  [{ts[:19]}] 重要性:{imp:.1f} | {content[:60]}...")


if __name__ == "__main__":
    main()
