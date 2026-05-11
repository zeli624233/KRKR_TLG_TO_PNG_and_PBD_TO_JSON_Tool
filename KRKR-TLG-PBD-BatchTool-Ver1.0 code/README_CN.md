# KRKR TLG/PBD 批处理工具 Ver1.0

这个工具把两个功能整合成一个软件：

1. **TLG → PNG**：参考 `tlg2png-1.0` 的 TLG0 / TLG5 / TLG6 解码逻辑，内置 Python 解码器，支持批量和多进程。
2. **PBD ↔ JSON**：参考 `PBDConverter-main` 的 README 和配置方式，内置 `PBDConverter.exe`、`PBDConverter.cf`、`data.xp3`，支持 PBD 转 JSON，也支持 JSON 转 PBD。

> `json.dll` 和 `PackinOne.dll` 属于游戏 plugin 文件，本工具包不内置。第一次使用 PBD/JSON 转换时，软件会让你选择游戏的 `plugin` 文件夹，然后自动复制这两个 DLL 到 `PBD文件解析配置`。

## 快速使用

1. 解压本工具包。
2. 双击 `install_requirements.bat` 安装依赖。
3. 双击 `run_gui.bat` 打开图形界面。
4. 进入对应页面：
   - `TLG 转 PNG`
   - `PBD / JSON 转换`

## GUI 功能

### TLG 转 PNG

- 支持输入单个 `.tlg` 文件或一个目录。
- 支持递归扫描子目录。
- 支持输出到源文件旁边，或输出到指定目录。
- 输出到指定目录时可以保留原目录结构。
- 支持覆盖已存在 PNG。
- 支持自定义线程/进程数，默认是 CPU 逻辑线程数的 50% + 1。
- 支持输出文件名追加后缀。

### PBD / JSON 转换

- 支持 `PBD → JSON`。
- 支持 `JSON → PBD`。
- 支持批量目录转换和递归扫描。
- 支持输出目录镜像结构。
- 支持并行启动多个 PBDConverter 进程。
- 支持保留临时目录，方便排错。
- 第一次使用会提示选择游戏 `plugin` 文件夹。

## 命令行用法

在工具目录打开命令行：

```bat
python -m krkr_batch_tool --help
```

### 1. 打开 GUI

```bat
python -m krkr_batch_tool gui
```

### 2. TLG 批量转 PNG

```bat
python -m krkr_batch_tool tlg2png "D:\input_tlg" -o "D:\output_png" -r -j 8 --overwrite
```

常用参数：

```text
-r, --recursive      递归扫描子目录
-j, --workers N      并行进程数
--full-workers       使用全部 CPU 逻辑线程
--overwrite          覆盖已有输出
--suffix _conv       输出文件名追加后缀
--no-mirror          输出到目录时不保留原目录结构
--dry-run            只预览，不实际转换
--optimize-png       PNG optimize，体积可能更小但更慢
```

### 3. PBD 批量转 JSON

```bat
python -m krkr_batch_tool pbd2json "D:\pbd" -o "D:\json" -r -j 4 --plugin-dir "D:\game\plugin"
```

### 4. JSON 批量转 PBD

```bat
python -m krkr_batch_tool json2pbd "D:\json" -o "D:\pbd" -r -j 4 --overwrite
```

### 5. 配置游戏 plugin 文件夹

```bat
python -m krkr_batch_tool config-plugin "D:\game\plugin"
```

### 6. 扫描可转换文件

```bat
python -m krkr_batch_tool scan "D:\game" --ext tlg --ext pbd -r
```

### 7. 自检 PBD 配置

```bat
python -m krkr_batch_tool doctor
```

### 8. 清理临时目录

```bat
python -m krkr_batch_tool clean-temp
```

## PBD 配置说明

工具首次运行会自动创建：

```text
PBD文件解析配置
```

里面会自动放入：

```text
PBDConverter.exe
PBDConverter.cf
data.xp3
```

还需要从游戏 `plugin` 文件夹复制：

```text
json.dll
PackinOne.dll
```

GUI 会自动弹窗让你选择 `plugin` 文件夹；命令行可以用 `--plugin-dir` 或 `config-plugin` 配置。

## 注意事项

- PBDConverter 是 Windows 程序，PBD/JSON 转换建议在 Windows 上运行。
- TLG 转 PNG 不依赖 PBDConverter，也不需要游戏 DLL。
- 批量 PBD/JSON 转换会给每个任务创建临时目录，默认转换完成后自动清理。
- 如果 PBD 转换失败，可以勾选/使用 `--keep-temp` 保留临时目录排查。

## 打包 EXE

安装 PyInstaller 后双击：

```text
build_windows_exe.bat
```

打包结果会在 `dist/KRKR_TLG_PBD_Tool`。
