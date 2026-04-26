# Task 1: 创建全局配置模板

## 目标

创建全局配置模板文件，为迁移旧的 `core/config_manager.py` 做准备。

## 背景

旧的 `core/config_manager.py` 管理全局配置（用户ID、跳过版本、待上报事件），现在需要通过配置模板的方式迁移到 `core/config/config_manager.py`。

## 任务清单

- [ ] 创建目录 `core/config_templates/`
- [ ] 创建全局配置模板文件 `core/config_templates/global_config_template.json`
- [ ] 定义模板结构（参考下方示例）
- [ ] 验证模板格式正确（JSON 格式）

## 全局配置模板内容

```json
{
  "_version": "1.0.0",
  "user_id": null,
  "skipped_versions": [],
  "pending_events": [],
  "last_check": null,
  "created_at": null,
  "updated_at": null
}
```

## 字段说明

- `_version`: 配置版本号
- `user_id`: 用户唯一标识（UUID 格式）
- `skipped_versions`: 跳过的版本列表
- `pending_events`: 待上报的事件队列
- `last_check`: 最后检查时间
- `created_at`: 配置创建时间
- `updated_at`: 配置更新时间

## 验收标准

1. 文件路径正确：`core/config_templates/global_config_template.json`
2. JSON 格式正确，可以被 `json.load()` 解析
3. 包含所有必需字段

## 依赖

无

## 预计时间

5 分钟

## 优先级

🔴 高优先级（阻塞后续任务）
