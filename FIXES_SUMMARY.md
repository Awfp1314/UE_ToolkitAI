# 修复总结

## 问题 1: 模型名称错误

### 问题描述

用户配置的模型名称 `deepseek-reasoner` 在 SiliconFlow API 中不存在，导致 API 返回错误：

```
Model does not exist. Please check it carefully.
```

### 解决方案

SiliconFlow 支持的 DeepSeek 模型名称应该是：

- `deepseek-ai/DeepSeek-V3` (最新版本)
- `deepseek-ai/DeepSeek-V2.5`

### 需要的操作

请在设置中将模型名称改为以上任意一个。

---

## 问题 2: 模型列表只显示一个模型

### 问题描述

当使用自定义 API（如 SiliconFlow）时，模型下拉框只显示配置文件中的 `default_model`，无法选择其他模型。

### 根本原因

代码逻辑错误：使用了硬编码的模型列表，而不是从 API 动态获取。

### 已实现的修复

#### 修改 `_load_api_models_for_combo` 方法

现在的逻辑：

1. **优先使用缓存**：如果有缓存且 URL 匹配，立即显示缓存的模型（快速响应）
2. **后台异步获取**：启动后台线程调用 `ApiLLMClient.fetch_available_models()` 从 API 的 `/v1/models` 端点获取最新模型列表
3. **更新缓存**：获取成功后保存到缓存文件
4. **失败回退**：如果获取失败且没有缓存，使用配置中的 `default_model`

```python
def _load_api_models_for_combo(self, config):
    """加载 API 模型列表到下拉框（从缓存或动态获取）"""
    # 1. 先从缓存加载（快速响应）
    # 2. 后台异步从 API 获取最新列表
    # 3. 更新 UI 和缓存
```

#### 工作流程

1. 用户在设置界面点击"保存配置"
2. 验证 API Key 成功后，保存配置
3. 调用 `main_win._load_ai_models()` 刷新主窗口的模型下拉框
4. `_load_ai_models()` 根据 provider 类型调用 `_load_api_models_for_combo()`
5. 从缓存或 API 动态获取模型列表并显示

---

## 下一步操作

### 方案：修复模型名称并重启

1. 重启 UE Toolkit 应用
2. 进入设置，将模型名称改为 `deepseek-ai/DeepSeek-V2.5` 或 `deepseek-ai/DeepSeek-V3`
3. 点击"保存配置"按钮
4. 系统会自动从 SiliconFlow API 获取可用模型列表
5. 返回 AI 助手，模型下拉框应该会显示从 API 获取的所有可用模型

### 如果模型列表还是只有一个

可能的原因：

1. API Key 无效或过期
2. SiliconFlow API 的 `/v1/models` 端点返回错误
3. 网络连接问题

解决方法：

- 检查日志文件 `logs/runtime/ue_toolkit.log` 查看详细错误信息
- 确认 API Key 是否有效
- 尝试手动访问 `https://api.siliconflow.cn/v1/models` 查看返回结果

---

## 关于 DSML 检测问题

从日志来看，DSML 检测代码已经正确实现，但由于模型名称错误，API 请求在第一步就失败了，所以没有机会测试 DSML 功能。

修复模型名称后，DSML 检测应该能正常工作。如果还有问题，请提供新的日志。

---

## 修改的文件

1. `ui/ue_main_window.py` - 修改 `_load_api_models_for_combo` 方法，从 API 动态获取模型列表
2. `modules/ai_assistant/config_template.json` - 移除不需要的 `available_models` 字段
