# BlueprintAITools for UE 5.6

## 版本信息

- 插件版本：1.0
- 支持引擎：Unreal Engine 5.6.0
- 基于：BlueprintAITools v3.0（只读版）

## 安装方法

1. 将整个 `BlueprintAITools_UE56` 文件夹复制到你的 UE 5.6 项目的 `Plugins/` 目录下
2. 重新生成项目文件（右键 .uproject → Generate Visual Studio project files）
3. 编译项目
4. 启动 UE 编辑器，在插件管理器中启用 "BlueprintAITools"

## 功能说明

这是一个只读版本的蓝图分析插件，提供以下功能：

- 导出当前打开的蓝图为 JSON 格式
- 查询可用节点字典
- 验证蓝图（检测 Pin 类型不匹配等错误）
- 获取选中节点信息
- 通过 TCP Socket (127.0.0.1:9998) 与桌面工具箱通信

## 与 UE 5.4 版本的区别

- 更新了 `EngineVersion` 为 5.6.0
- 其他代码保持不变（UE 5.4 到 5.6 的 API 兼容）

## 依赖

- PythonScriptPlugin（UE 内置插件，需要启用）

## 注意事项

- 本插件为只读模式，不支持修改蓝图
- 确保 PythonScriptPlugin 已启用
- 确保防火墙允许本地 9998 端口通信

## 技术支持

如有问题，请联系工具箱开发者。
