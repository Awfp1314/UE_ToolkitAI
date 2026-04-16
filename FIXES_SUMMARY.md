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

代码中对于自定义 API，只读取 `default_model` 字段：

```python
else:
    # 自定义 API，使用配置中的模型
    default_model = config.get("api_settings", {}).get("default_model", "gpt-3.5-turbo")
    models = [default_model]
```

### 已实现的修复

#### 1. 添加 SiliconFlow 支持

在 `ui/ue_main_window.py` 中添加了 SiliconFlow 的常用模型列表：

```python
elif "siliconflow.cn" in api_url:
    # SiliconFlow API 的常用模型
    models = [
        "deepseek-ai/DeepSeek-V3",
        "deepseek-ai/DeepSeek-V2.5",
        "Qwen/Qwen2.5-72B-Instruct",
        "Qwen/Qwen2.5-32B-Instruct",
        "Qwen/Qwen2.5-7B-Instruct",
        "Pro/Qwen/QwQ-32B-Preview",
        "THUDM/glm-4-9b-chat"
    ]
```

#### 2. 支持自定义模型列表

在配置模板中添加了 `available_models` 字段，允许用户为自定义 API 配置模型列表：

```json
{
  "api_settings": {
    "api_url": "https://api.siliconflow.cn/v1/chat/completions",
    "api_key": "your-key",
    "default_model": "deepseek-ai/DeepSeek-V2.5",
    "available_models": [
      "deepseek-ai/DeepSeek-V3",
      "deepseek-ai/DeepSeek-V2.5",
      "Qwen/Qwen2.5-72B-Instruct"
    ],
    ...
  }
}
```

#### 3. 更新加载逻辑

修改了模型加载逻辑，优先使用 `available_models`，如果没有配置则使用 `default_model`：

```python
else:
    # 自定义 API，尝试从配置读取 available_models 列表
    available_models = config.get("api_settings", {}).get("available_models", [])
    if available_models:
        models = available_models
    else:
        # 如果没有配置 available_models，使用 default_model
        default_model = config.get("api_settings", {}).get("default_model", "gpt-3.5-turbo")
        models = [default_model]
```

---

## 下一步操作

### 方案 1: 使用 SiliconFlow 内置支持（推荐）

1. 重启 UE Toolkit 应用
2. 进入设置，将模型名称改为 `deepseek-ai/DeepSeek-V2.5` 或 `deepseek-ai/DeepSeek-V3`
3. 保存设置
4. 返回 AI 助手，模型下拉框应该会显示多个 SiliconFlow 支持的模型

### 方案 2: 手动配置模型列表

1. 打开配置文件：`%APPDATA%\ue_toolkit\user_data\configs\ai_assistant\ai_assistant_config.json`
2. 在 `api_settings` 中添加 `available_models` 字段：

```json
{
  "api_settings": {
    "api_url": "https://api.siliconflow.cn/v1/chat/completions",
    "api_key": "your-key",
    "default_model": "deepseek-ai/DeepSeek-V2.5",
    "available_models": [
      "deepseek-ai/DeepSeek-V3",
      "deepseek-ai/DeepSeek-V2.5",
      "Qwen/Qwen2.5-72B-Instruct",
      "Qwen/Qwen2.5-32B-Instruct"
    ],
    ...
  }
}
```

3. 保存文件
4. 重启 UE Toolkit

---

## 关于 DSML 检测问题

从日志来看，DSML 检测代码已经正确实现，但由于模型名称错误，API 请求在第一步就失败了，所以没有机会测试 DSML 功能。

修复模型名称后，DSML 检测应该能正常工作。如果还有问题，请提供新的日志。

---

## 修改的文件

1. `ui/ue_main_window.py` - 添加 SiliconFlow 支持和自定义模型列表支持
2. `modules/ai_assistant/config_template.json` - 添加 `available_models` 字段说明
