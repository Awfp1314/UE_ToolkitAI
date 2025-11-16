# Resources 资源文件

本目录包含应用程序的静态资源文件，包括模板和图标等。

## 📁 目录结构

```
resources/
├── templates/                # 配置模板
│   └── global_settings.json  # 全局设置模板
└── tubiao.ico                # 应用图标
```

## 📄 配置模板

### `templates/global_settings.json`

全局设置模板文件，包含应用程序的默认配置。

## 🖼️ 图标

### `tubiao.ico`

应用程序图标，支持多尺寸：

- 16x16
- 32x32
- 48x48
- 256x256

## 📝 说明

本项目使用内联样式（inline QSS）而非外部 QSS 文件。
所有 UI 样式都直接在各个 UI 组件的代码中定义。

