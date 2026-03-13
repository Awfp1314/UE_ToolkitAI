#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复文档格式：将 .txt/.md 改为 .docx
"""

import re
from pathlib import Path

def fix_file(file_path):
    """修复单个文件"""
    print(f"处理文件: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 替换1: 检查文档是否存在的逻辑
    content = re.sub(
        r'# 检查 \.txt 或 \.md 文档是否存在\s+if hasattr\(self, \'asset_id\'\) and self\.asset_id:\s+doc_path_txt = logic\.documents_dir / f"\{self\.asset_id\}\.txt"\s+doc_path_md = logic\.documents_dir / f"\{self\.asset_id\}\.md"\s+return doc_path_txt\.exists\(\) or doc_path_md\.exists\(\)',
        '# 检查 .docx 文档是否存在\n                        if hasattr(self, \'asset_id\') and self.asset_id:\n                            doc_path = logic.documents_dir / f"{self.asset_id}.docx"\n                            return doc_path.exists()',
        content,
        flags=re.MULTILINE
    )
    
    # 替换2: 删除文档的逻辑
    content = re.sub(
        r'# 删除文档文件\s+doc_path_txt = logic\.documents_dir / f"\{self\.asset_id\}\.txt"\s+doc_path_md = logic\.documents_dir / f"\{self\.asset_id\}\.md"\s+\s+deleted = False\s+if doc_path_txt\.exists\(\):\s+doc_path_txt\.unlink\(\)\s+logger\.info\(f"已删除文档: \{doc_path_txt\}"\)\s+deleted = True\s+\s+if doc_path_md\.exists\(\):\s+doc_path_md\.unlink\(\)\s+logger\.info\(f"已删除文档: \{doc_path_md\}"\)\s+deleted = True\s+\s+if deleted:\s+QMessageBox\.information\(self, "删除成功", "文档已删除"\)\s+else:\s+QMessageBox\.warning\(self, "删除失败", "未找到文档文件"\)',
        '# 删除文档文件\n            doc_path = logic.documents_dir / f"{self.asset_id}.docx"\n            \n            if doc_path.exists():\n                doc_path.unlink()\n                logger.info(f"已删除文档: {doc_path}")\n                QMessageBox.information(self, "删除成功", "文档已删除")\n            else:\n                QMessageBox.warning(self, "删除失败", "未找到文档文件")',
        content,
        flags=re.MULTILINE
    )
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ 已修复: {file_path}")
        return True
    else:
        print(f"✗ 无需修改: {file_path}")
        return False

def main():
    """主函数"""
    # 修复 modern_asset_card.py
    file_path = Path(__file__).parent.parent / "modules" / "asset_manager" / "ui" / "modern_asset_card.py"
    
    if file_path.exists():
        fix_file(file_path)
    else:
        print(f"文件不存在: {file_path}")

if __name__ == "__main__":
    main()
