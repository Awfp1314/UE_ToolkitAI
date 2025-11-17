"""
调试导入问题
"""
import sys

print("=" * 60)
print("测试导入")
print("=" * 60)

print("\n[1] 测试导入 logging...")
try:
    import logging
    print("✅ logging 导入成功")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)

print("\n[2] 测试导入 threading...")
try:
    import threading
    print("✅ threading 导入成功")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)

print("\n[3] 测试导入 pathlib...")
try:
    from pathlib import Path
    print("✅ pathlib 导入成功")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)

print("\n[4] 测试导入 core...")
try:
    import core
    print("✅ core 导入成功")
except Exception as e:
    print(f"❌ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[5] 测试导入 core.logger...")
try:
    import core.logger
    print("✅ core.logger 导入成功")
except Exception as e:
    print(f"❌ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[6] 测试导入 core.utils.path_utils...")
try:
    import core.utils.path_utils
    print("✅ core.utils.path_utils 导入成功")
except Exception as e:
    print(f"❌ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ 所有导入测试通过!")

