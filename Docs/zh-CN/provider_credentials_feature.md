# AI 助手供应商凭据独立保存功能

## 功能说明

从此版本开始，每个 AI 供应商的密钥配置将独立保存，切换供应商时不会丢失之前配置的密钥。

## 配置结构

新的配置文件结构：

```json
{
  "_version": "1.0.0",
  "llm_provider": "api",
  "provider_type": "deepseek",
  "provider_credentials": {
    "openai": {
      "api_key": "sk-xxx",
      "api_url": "https://api.openai.com/v1/chat/completions"
    },
    "deepseek": {
      "api_key": "sk-yyy",
      "api_url": "https://api.deepseek.com/v1/chat/completions"
    },
    "gemini": {
      "api_key": "AIza-zzz",
      "api_url": "https://generativelanguage.googleapis.com/v1beta/chat/completions"
    }
  },
  "api_settings": {
    "api_key": "sk-yyy",
    "api_url": "https://api.deepseek.com/v1/chat/completions",
    "default_model": "deepseek-chat"
  }
}
```

## 工作原理

1. **保存配置时**：当前供应商的密钥和 URL 会同时保存到：
   - `provider_credentials[供应商名称]` - 供应商独立配置
   - `api_settings` - 当前活动配置（向后兼容）

2. **切换供应商时**：自动从 `provider_credentials` 中加载该供应商之前保存的密钥和 URL

3. **旧配置迁移**：首次加载时，如果检测到旧配置格式，会自动迁移到新格式

## 使用示例

### 场景：配置多个供应商

1. 打开设置 → AI 助手设置
2. 选择 "Deepseek" 供应商
3. 输入 Deepseek 的 API Key
4. 点击保存

5. 切换到 "OpenAI" 供应商
6. 输入 OpenAI 的 API Key
7. 点击保存

8. 再次切换回 "Deepseek"
   - ✅ Deepseek 的密钥会自动填充，无需重新输入

## 支持的供应商

- OpenAI
- Google Gemini
- Deepseek
- Anthropic Claude
- Ollama (本地)
- 自定义 (BYOK)

## 向后兼容

- 旧版本的配置文件会自动迁移到新格式
- `api_settings` 字段保留，确保旧代码仍能正常工作
- 不会影响现有的配置和使用

## 技术细节

### 修改的文件

1. `ui/settings_widget.py`
   - 添加 `_load_provider_credentials()` 方法
   - 修改 `_on_provider_changed()` 方法，切换时加载凭据
   - 修改 `_load_config()` 方法，支持旧配置迁移
   - 修改 `_save_config()` 方法，保存到 `provider_credentials`

2. `modules/ai_assistant/config_schema.py`
   - 添加 `provider_type` 和 `provider_credentials` 字段

3. `modules/ai_assistant/config_template.json`
   - 添加 `provider_credentials` 默认结构

### 配置字段说明

- `provider_type`: 当前选中的供应商（openai, deepseek, gemini, claude, byok, ollama）
- `provider_credentials`: 字典，键为供应商名称，值为该供应商的配置
  - `api_key`: API 密钥
  - `api_url`: API 服务地址
