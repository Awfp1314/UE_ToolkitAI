# 高性能文件操作工具

本目录包含用于加速文件操作的外部工具。

## 7-Zip 高速解压组件

### 文件说明

- `7z.exe` (549 KB) - 7-Zip 命令行工具
- `7z.dll` (1.8 MB) - 7-Zip 核心库
- 总大小：约 2.4 MB

### 功能

7-Zip 用于高速解压和压缩，可将解压速度提升 3-5 倍。

### 安装选项

在安装 UE Toolkit 时，可以选择是否安装 7-Zip 组件：

- **完整安装**：包含 7-Zip 组件（推荐）
- **精简安装**：不包含 7-Zip 组件
- **自定义安装**：手动选择是否安装

### 自动查找

程序会自动在以下位置查找 7z.exe（按优先级）：

1. `{安装目录}/resources/tools/7z.exe`（打包版本，优先）
2. `C:/Program Files/7-Zip/7z.exe`（系统安装）
3. PATH 环境变量

### 降级机制

如果未找到 7z.exe，程序会自动降级到 Python zipfile 实现（较慢但兼容）。

### 手动安装

如果安装时未选择 7-Zip 组件，可以：

**方法 1：安装系统版 7-Zip**

1. 下载：https://www.7-zip.org/
2. 安装到默认位置（`C:/Program Files/7-Zip/`）
3. 程序会自动检测

**方法 2：复制文件到安装目录**

1. 从已安装的 7-Zip 复制 `7z.exe` 和 `7z.dll`
2. 粘贴到 `{安装目录}/resources/tools/`

### 开发者：准备打包文件

运行 `download_7z.py` 脚本从系统 7-Zip 复制文件：

```bash
python Client/resources/tools/download_7z.py
```

### 许可证

7-Zip 是开源软件，采用 LGPL 许可证，可以自由分发。
官网：https://www.7-zip.org/

## robocopy

robocopy 是 Windows 内置工具，无需额外安装。
用于高速复制文件，可将复制速度提升 3-10 倍。

## 性能对比

| 操作             | Python 实现 | 高性能模式 | 提升 |
| ---------------- | ----------- | ---------- | ---- |
| 解压 10GB ZIP    | 5-8 分钟    | 1-2 分钟   | 3-5x |
| 复制 10GB 文件夹 | 3-5 分钟    | 30-60 秒   | 3-6x |
| 解压 100GB ZIP   | 50-80 分钟  | 10-15 分钟 | 5-8x |

## 技术细节

### 7z 多线程解压

```bash
7z x archive.zip -o{output_dir} -mmt=4 -y
```

- `-mmt=4`：使用 4 线程（可根据 CPU 调整）
- `-y`：自动确认覆盖

### robocopy 多线程复制

```bash
robocopy {src} {dst} /E /MT:8 /NFL /NDL /NJH /NJS /NP
```

- `/MT:8`：使用 8 线程
- `/E`：复制所有子目录（包括空目录）
- `/NFL /NDL /NJH /NJS /NP`：减少输出，提升性能
