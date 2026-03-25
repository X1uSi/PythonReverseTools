# Python Reverse Tools

一个面向 Windows 的 Python 逆向与打包辅助工具集，提供图形界面，方便对 PyInstaller、PYC、PYZ 等常见场景进行处理。

项目适合：

- 分析 PyInstaller 打包程序
- 反编译 .pyc 文件
- 识别打包程序对应的 Python 版本
- 修复 PYZ.pyz_extracted 中缺少魔术头的加密模块
- 在多个 Python 版本之间快速切换打包环境

## 功能特性

### 1. PyInstaller 解包

- 选择或拖入打包后的 EXE
- 调用 pyinstxtractor.py 进行解包
- 显示预期执行命令
- 使用主界面统一配置的 Python 解释器

### 2. PyInstaller 打包

- 图形化生成常用 PyInstaller 命令
- 默认勾选 -F、-w、--clean、-y
- 支持图标设置
- 支持自定义 dist 输出目录和 build 工作目录
- 显示预期命令
- 打包成功后自动打开输出目录
- 内置本地 PyInstaller 使用手册入口

### 3. PYC 反编译 / 反汇编

- pycdc：默认输出到同目录同名 .py
- pycdas：默认输出到同目录同名 .txt
- uncompyle6：默认输出到同目录同名 .py
- 提供在线反编译网站入口

### 4. 识别 EXE 打包 Python 版本

- 拖入 EXE 即可识别
- 自动扫描二进制中的 python311.dll、python3.11 等特征
- 可快速判断 PyInstaller 程序使用的 Python 主版本

### 5. 修复 PYZ 加密 pyc

- 独立功能，不影响原解包流程
- 选择或拖入 xxx.pyz
- 自动读取同目录 struct.pyc 前 8 字节作为正确魔术头
- 自动扫描 xxx.pyz_extracted 下的 *.pyc.encrypted
- 调用 pyi-archive_viewer 提取原始模块二进制
- 自动补全魔术头并生成标准 .pyc

### 6. 多解释器切换

- 主界面支持配置 Python 解释器路径
- 支持保存多个 Python 解释器
- 通过下拉框快速切换不同版本
- 所有依赖 Python 的功能统一使用当前选择的解释器

## 安装运行

1. 前往[Release页面](https://github.com/X1uSi/py_re_tools/releases)下载最新版的 Python Reverse Tools.zip
2. 解压zip文件
3. 安装依赖requirements.txt
4. 双击运行exe即可

## 适用场景

- PyInstaller 打包样本分析
- Python 程序逆向辅助
- .pyc / .pyz 文件恢复与处理
- 多 Python 版本打包测试

