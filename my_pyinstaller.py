# my_pyinstaller.py - PyInstaller打包工具GUI
import os
import subprocess
import sys
import shlex
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QGroupBox, QCheckBox, QLineEdit, QPushButton, QLabel,
                             QTextEdit, QFileDialog, QMessageBox, QProgressBar, QDialog)
from PyQt5.QtCore import Qt, QUrl, QProcess, QMimeData
from PyQt5.QtGui import QFont, QDesktopServices, QTextCursor, QDragEnterEvent, QDropEvent
from app_config import get_python_executable, is_valid_python_executable


class DragDropLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """接受拖拽事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """处理文件拖放"""
        urls = event.mimeData().urls()
        if urls:
            # 获取第一个文件的本地路径
            file_path = urls[0].toLocalFile()
            self.setText(file_path)
            event.acceptProposedAction()


class PyInstallerGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PyInstaller打包工具")
        self.setMinimumSize(800, 600)
        self.process = None
        self.last_output_dir = None
        self.distpath_customized = False
        self.workpath_customized = False

        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 创建常用命令选项卡
        self.common_tab = QWidget()
        self.tab_widget.addTab(self.common_tab, "常用命令")
        self.setup_common_tab()

        # 创建自定义命令选项卡
        self.custom_tab = QWidget()
        self.tab_widget.addTab(self.custom_tab, "自定义命令")
        self.setup_custom_tab()

        # 添加执行按钮
        self.execute_btn = QPushButton("执行")
        self.execute_btn.setFont(QFont("Arial", 12))
        self.execute_btn.setFixedSize(120, 40)
        self.execute_btn.clicked.connect(self.execute_command)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.execute_btn)
        main_layout.addLayout(btn_layout)

    def open_pyinstaller_manual(self):
        """打开本地 PyInstaller 手册，缺失时回退到官网"""
        manual_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PyInstaller使用手册.md")
        if os.path.exists(manual_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(manual_path))
        else:
            QDesktopServices.openUrl(QUrl("https://pyinstaller.org/en/stable/usage.html"))

    def get_script_directory(self, file_path):
        """获取待打包脚本所在目录"""
        if not file_path:
            return ""
        return os.path.dirname(os.path.abspath(file_path))

    def get_default_distpath(self, file_path):
        """默认输出目录为脚本同目录"""
        return self.get_script_directory(file_path)

    def get_default_workpath(self, file_path):
        """默认工作目录为脚本同目录"""
        return self.get_script_directory(file_path)

    def on_distpath_changed(self, text):
        """记录 distpath 是否被用户手动修改"""
        default_path = self.get_default_distpath(self.file_input.text().strip())
        self.distpath_customized = bool(text.strip()) and text.strip() != default_path
        self.update_command_display()

    def on_workpath_changed(self, text):
        """记录 workpath 是否被用户手动修改"""
        default_path = self.get_default_workpath(self.file_input.text().strip())
        self.workpath_customized = bool(text.strip()) and text.strip() != default_path
        self.update_command_display()

    def select_distpath(self):
        """选择 dist 输出目录"""
        current_dir = self.distpath_input.text().strip() or self.get_default_distpath(self.file_input.text().strip())
        selected_dir = QFileDialog.getExistingDirectory(self, "选择 dist 输出目录", current_dir)
        if selected_dir:
            self.distpath_input.setText(selected_dir)

    def select_workpath(self):
        """选择 build 工作目录"""
        current_dir = self.workpath_input.text().strip() or self.get_default_workpath(self.file_input.text().strip())
        selected_dir = QFileDialog.getExistingDirectory(self, "选择 build 工作目录", current_dir)
        if selected_dir:
            self.workpath_input.setText(selected_dir)

    def setup_common_tab(self):
        """设置常用命令选项卡"""
        layout = QVBoxLayout(self.common_tab)
        layout.setSpacing(15)

        # 添加参数解释区域
        self.param_explanation = QTextEdit()
        self.param_explanation.setReadOnly(True)
        self.param_explanation.setFont(QFont("Arial", 9))
        self.param_explanation.setPlaceholderText("鼠标悬停在参数上查看详细解释...")
        self.param_explanation.setMaximumHeight(80)
        layout.addWidget(self.param_explanation)

        # 参数选择区
        param_layout = QHBoxLayout()

        # 基本选项
        basic_group = QGroupBox("基本选项")
        basic_layout = QVBoxLayout()

        self.clean_cb = QCheckBox("--clean")
        self.clean_cb.setChecked(True)
        self.clean_cb.setToolTip("构建前清理 PyInstaller 缓存和临时文件")
        self.clean_cb.enterEvent = lambda event: self.show_explanation("构建前清理 PyInstaller 缓存和临时文件")
        self.clean_cb.leaveEvent = lambda event: self.clear_explanation()
        basic_layout.addWidget(self.clean_cb)

        self.noconfirm_cb = QCheckBox("-y, --noconfirm")
        self.noconfirm_cb.setChecked(True)
        self.noconfirm_cb.setToolTip("覆盖已有输出目录时不再弹出确认")
        self.noconfirm_cb.enterEvent = lambda event: self.show_explanation("覆盖已有输出目录时不再弹出确认")
        self.noconfirm_cb.leaveEvent = lambda event: self.clear_explanation()
        basic_layout.addWidget(self.noconfirm_cb)

        basic_group.setLayout(basic_layout)
        param_layout.addWidget(basic_group)

        # 生成类型
        build_group = QGroupBox("生成类型")
        build_layout = QVBoxLayout()

        self.onefile_cb = QCheckBox("-F, --onefile")
        self.onefile_cb.setChecked(True)
        self.onefile_cb.setToolTip("创建一个单一的可执行文件包")
        # 添加悬停事件处理
        self.onefile_cb.enterEvent = lambda event: self.show_explanation("将所有文件打包成一个单独的可执行文件")
        self.onefile_cb.leaveEvent = lambda event: self.clear_explanation()
        build_layout.addWidget(self.onefile_cb)

        self.name_cb = QCheckBox("-n NAME, --name NAME")
        self.name_cb.setToolTip("指定打包应用和spec文件的名称")
        # 添加悬停事件处理
        self.name_cb.enterEvent = lambda event: self.show_explanation("为生成的可执行文件和spec文件指定名称")
        self.name_cb.leaveEvent = lambda event: self.clear_explanation()
        build_layout.addWidget(self.name_cb)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("输入应用名称")
        self.name_input.setEnabled(False)
        self.name_cb.stateChanged.connect(lambda state: self.name_input.setEnabled(state == Qt.Checked))
        build_layout.addWidget(self.name_input)

        build_group.setLayout(build_layout)
        param_layout.addWidget(build_group)

        # Windows与macOS特定选项
        os_group = QGroupBox("Windows与macOS特定选项")
        os_layout = QVBoxLayout()

        self.console_cb = QCheckBox("-c, --console, --nowindowed")
        self.console_cb.setToolTip("打开控制台窗口进行标准I/O")
        # 添加悬停事件处理
        self.console_cb.enterEvent = lambda event: self.show_explanation("为应用程序打开控制台窗口（Windows和macOS）")
        self.console_cb.leaveEvent = lambda event: self.clear_explanation()
        os_layout.addWidget(self.console_cb)

        self.windowed_cb = QCheckBox("-w, --windowed, --noconsole")
        self.windowed_cb.setChecked(True)
        self.windowed_cb.setToolTip("不提供控制台窗口进行标准I/O")
        # 添加悬停事件处理
        self.windowed_cb.enterEvent = lambda event: self.show_explanation("不显示控制台窗口（仅GUI应用程序）")
        self.windowed_cb.leaveEvent = lambda event: self.clear_explanation()
        os_layout.addWidget(self.windowed_cb)

        self.hide_console_cb = QCheckBox("--hide-console")
        self.hide_console_cb.setToolTip("自动隐藏或最小化控制台窗口")
        # 添加悬停事件处理
        self.hide_console_cb.enterEvent = lambda event: self.show_explanation("启动后自动隐藏或最小化控制台窗口")
        self.hide_console_cb.leaveEvent = lambda event: self.clear_explanation()
        os_layout.addWidget(self.hide_console_cb)

        self.icon_cb = QCheckBox("-i <FILE>, --icon <FILE>")
        self.icon_cb.setToolTip("指定应用的图标文件")
        # 添加悬停事件处理
        self.icon_cb.enterEvent = lambda event: self.show_explanation("为可执行文件设置自定义图标（.ico或.icns）")
        self.icon_cb.leaveEvent = lambda event: self.clear_explanation()
        os_layout.addWidget(self.icon_cb)

        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText("选择图标文件")
        self.icon_input.setEnabled(False)
        self.icon_cb.stateChanged.connect(lambda state: self.icon_input.setEnabled(state == Qt.Checked))

        icon_btn = QPushButton("浏览...")
        icon_btn.setFixedWidth(80)
        icon_btn.clicked.connect(self.select_icon_file)
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self.icon_input)
        icon_layout.addWidget(icon_btn)
        os_layout.addLayout(icon_layout)

        os_group.setLayout(os_layout)
        param_layout.addWidget(os_group)

        layout.addLayout(param_layout)

        # 文件选择区
        file_group = QGroupBox("选择Python文件")
        file_layout = QVBoxLayout()

        file_select_layout = QHBoxLayout()
        # 使用支持拖拽的输入框
        self.file_input = DragDropLineEdit()
        self.file_input.setPlaceholderText("拖放文件到此处或点击浏览按钮")
        self.file_input.textChanged.connect(self.update_command_display)
        file_select_layout.addWidget(self.file_input)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self.select_python_file)
        file_select_layout.addWidget(browse_btn)

        file_layout.addLayout(file_select_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        path_group = QGroupBox("输出路径")
        path_layout = QVBoxLayout()

        self.distpath_label = QLabel("dist 输出目录")
        path_layout.addWidget(self.distpath_label)
        distpath_row = QHBoxLayout()
        self.distpath_input = QLineEdit()
        self.distpath_input.setPlaceholderText("默认与待打包 Python 文件同目录")
        self.distpath_input.textChanged.connect(self.on_distpath_changed)
        distpath_row.addWidget(self.distpath_input)
        self.distpath_browse_btn = QPushButton("浏览...")
        self.distpath_browse_btn.setFixedWidth(80)
        self.distpath_browse_btn.clicked.connect(self.select_distpath)
        distpath_row.addWidget(self.distpath_browse_btn)
        path_layout.addLayout(distpath_row)

        self.workpath_label = QLabel("build 工作目录")
        path_layout.addWidget(self.workpath_label)
        workpath_row = QHBoxLayout()
        self.workpath_input = QLineEdit()
        self.workpath_input.setPlaceholderText("默认与待打包 Python 文件同目录")
        self.workpath_input.textChanged.connect(self.on_workpath_changed)
        workpath_row.addWidget(self.workpath_input)
        self.workpath_browse_btn = QPushButton("浏览...")
        self.workpath_browse_btn.setFixedWidth(80)
        self.workpath_browse_btn.clicked.connect(self.select_workpath)
        workpath_row.addWidget(self.workpath_browse_btn)
        path_layout.addLayout(workpath_row)

        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # 预期命令框
        command_group = QGroupBox("预期命令")
        command_layout = QVBoxLayout()

        self.command_display = QTextEdit()
        self.command_display.setReadOnly(True)
        self.command_display.setFont(QFont("Courier New", 10))
        self.command_display.setPlaceholderText("生成的命令将显示在这里")
        command_layout.addWidget(self.command_display)

        command_group.setLayout(command_layout)
        layout.addWidget(command_group)

        # 连接信号以更新命令显示
        self.connect_signals()
        self.update_command_display()

    def setup_custom_tab(self):
        """设置自定义命令选项卡"""
        layout = QVBoxLayout(self.custom_tab)
        layout.setSpacing(15)

        # 自定义命令输入
        custom_group = QGroupBox("自定义命令")
        custom_layout = QVBoxLayout()

        self.custom_command_input = QTextEdit()
        self.custom_command_input.setPlaceholderText(
            "在此输入完整的PyInstaller命令...\n例如: pyinstaller --onefile --windowed --icon=app.ico myscript.py")
        self.custom_command_input.setFont(QFont("Courier New", 10))
        custom_layout.addWidget(self.custom_command_input)

        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)

        # 添加帮助链接
        help_layout = QHBoxLayout()
        help_layout.addStretch()

        help_label = QLabel("需要帮助? 查看")
        help_layout.addWidget(help_label)

        help_btn = QPushButton("PyInstaller文档")
        help_btn.setStyleSheet("color: blue; text-decoration: underline;")
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.clicked.connect(self.open_pyinstaller_manual)
        help_layout.addWidget(help_btn)

        layout.addLayout(help_layout)

    def show_explanation(self, text):
        """显示参数解释"""
        self.param_explanation.setText(text)
        self.param_explanation.setStyleSheet("background-color: #f0f0f0; border: 1px solid #d0d0d0;")

    def clear_explanation(self):
        """清除参数解释"""
        self.param_explanation.clear()
        self.param_explanation.setStyleSheet("")

    def connect_signals(self):
        """连接所有信号以更新命令显示"""
        # 连接所有复选框
        for checkbox in self.common_tab.findChildren(QCheckBox):
            checkbox.stateChanged.connect(self.update_command_display)

        # 连接文本输入框
        self.name_input.textChanged.connect(self.update_command_display)
        self.icon_input.textChanged.connect(self.update_command_display)

    def get_python_executable(self):
        """获取当前应使用的 Python 解释器路径"""
        return get_python_executable()

    def get_pyinstaller_prefix_args(self):
        """始终使用当前解释器执行 PyInstaller，避免命中 PATH 中其他版本"""
        return [self.get_python_executable(), "-m", "PyInstaller"]

    def format_command_for_display(self, args):
        """将参数列表格式化为可展示的命令字符串"""
        if sys.platform == "win32":
            return subprocess.list2cmdline(args)
        return shlex.join(args)

    def normalize_custom_command(self, command):
        """将自定义命令中的裸 pyinstaller 改写为当前解释器执行"""
        if not command:
            return command

        try:
            args = shlex.split(command, posix=(sys.platform != "win32"))
        except ValueError:
            return command

        if not args:
            return command

        first_arg = args[0].lower()
        if first_arg in {"pyinstaller", "pyinstaller.exe"}:
            args = self.get_pyinstaller_prefix_args() + args[1:]
            return self.format_command_for_display(args)

        if first_arg in {"python", "python.exe", "python3", "python3.exe"}:
            args[0] = self.get_python_executable()
            return self.format_command_for_display(args)

        return command

    def build_common_command_args(self):
        """构建常用命令页的 PyInstaller 参数"""
        args = self.get_pyinstaller_prefix_args()
        file_path = self.file_input.text().strip()
        distpath = self.distpath_input.text().strip() or self.get_default_distpath(file_path)
        workpath = self.workpath_input.text().strip() or self.get_default_workpath(file_path)

        # 添加基本选项
        if self.clean_cb.isChecked():
            args.append("--clean")
        if self.noconfirm_cb.isChecked():
            args.append("-y")
        if distpath:
            args.extend(["--distpath", distpath])
        if workpath:
            args.extend(["--workpath", workpath])

        # 添加生成类型选项
        if self.onefile_cb.isChecked():
            args.append("-F")
        if self.name_cb.isChecked() and self.name_input.text():
            args.extend(["-n", self.name_input.text()])

        # 添加操作系统特定选项
        if self.console_cb.isChecked():
            args.append("-c")
        if self.windowed_cb.isChecked():
            args.append("-w")
        if self.hide_console_cb.isChecked():
            args.append("--hide-console")
        if self.icon_cb.isChecked() and self.icon_input.text():
            args.extend(["-i", self.icon_input.text()])

        args.append(file_path)
        return args

    def update_output_path_display(self):
        """更新 dist/workpath 展示"""
        file_path = self.file_input.text().strip()
        default_distpath = self.get_default_distpath(file_path)
        default_workpath = self.get_default_workpath(file_path)

        if not self.distpath_customized:
            self.distpath_input.blockSignals(True)
            self.distpath_input.setText(default_distpath)
            self.distpath_input.blockSignals(False)

        if not self.workpath_customized:
            self.workpath_input.blockSignals(True)
            self.workpath_input.setText(default_workpath)
            self.workpath_input.blockSignals(False)

    def parse_output_dir_from_command(self, command):
        """从命令中解析输出目录"""
        if not command:
            return None

        try:
            args = shlex.split(command, posix=(sys.platform != "win32"))
        except ValueError:
            return None

        for index, arg in enumerate(args):
            if arg == "--distpath" and index + 1 < len(args):
                return args[index + 1]
            if arg.startswith("--distpath="):
                return arg.split("=", 1)[1]

        script_path = None
        for arg in reversed(args):
            if arg.lower().endswith(".py") or arg.lower().endswith(".spec"):
                script_path = arg
                break

        if script_path:
            return self.get_default_distpath(script_path)
        return None

    def update_command_display(self):
        """更新预期命令框的内容"""
        self.update_output_path_display()

        if not self.file_input.text():
            self.command_display.setText("请先选择Python文件")
            return

        command_args = self.build_common_command_args()
        self.command_display.setText(self.format_command_for_display(command_args))

    def select_python_file(self):
        """选择Python文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Python文件", "",
            "Python文件 (*.py);;所有文件 (*)"
        )
        if file_path:
            self.file_input.setText(file_path)

    def select_icon_file(self):
        """选择图标文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图标文件", "",
            "图标文件 (*.ico);;所有文件 (*)"
        )
        if file_path:
            self.icon_input.setText(file_path)

    def execute_command(self):
        """执行命令"""
        current_tab = self.tab_widget.currentIndex()

        if current_tab == 0:  # 常用命令
            if not self.file_input.text().strip():
                QMessageBox.warning(self, "无效命令", "请先生成有效的打包命令")
                return
            python_executable = self.get_python_executable()
            if not is_valid_python_executable(python_executable):
                QMessageBox.warning(self, "无效解释器", "请先在主界面配置有效的 Python 解释器")
                return
            command_args = self.build_common_command_args()
            command = self.format_command_for_display(command_args)
            self.last_output_dir = self.distpath_input.text().strip() or self.get_default_distpath(self.file_input.text().strip())
        else:  # 自定义命令
            command = self.custom_command_input.toPlainText().strip()
            if not command:
                QMessageBox.warning(self, "无效命令", "请输入有效的打包命令")
                return

            python_executable = self.get_python_executable()
            if not is_valid_python_executable(python_executable):
                QMessageBox.warning(self, "无效解释器", "请先在主界面配置有效的 Python 解释器")
                return

            command = self.normalize_custom_command(command)
            self.last_output_dir = self.parse_output_dir_from_command(command)

        # 创建输出窗口
        self.output_dialog = QDialog(self)
        self.output_dialog.setWindowTitle("命令执行中...")
        self.output_dialog.setMinimumSize(700, 500)

        layout = QVBoxLayout(self.output_dialog)

        # 命令显示
        command_label = QLabel(f"执行命令: {command}")
        command_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(command_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度模式
        layout.addWidget(self.progress_bar)

        # 输出区域
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Courier New", 9))
        self.output_text.setPlaceholderText("命令输出将显示在这里...")
        layout.addWidget(self.output_text)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close_output_dialog)
        layout.addWidget(close_btn)

        self.output_dialog.show()

        # 清空输出区域
        self.output_text.clear()

        # 执行命令
        self.execute_command_with_qprocess(command)

    def execute_command_with_qprocess(self, command):
        """使用QProcess执行命令"""
        # 如果已有进程在运行，先停止
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
            self.process = None

        # 创建新进程
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        # 连接信号
        self.process.readyReadStandardOutput.connect(self.read_process_output)
        self.process.finished.connect(self.process_finished)

        # 关键修复：正确处理命令参数
        if sys.platform == "win32":
            # 在Windows上，我们直接执行命令字符串
            self.process.start("cmd.exe", ["/c", command])
        else:
            # 在Unix系统上，使用shlex正确分割参数
            args = shlex.split(command)
            if args:
                executable = args[0]
                arguments = args[1:]
                self.process.start(executable, arguments)
            else:
                QMessageBox.warning(self, "错误", "无效的命令")
                return

    def read_process_output(self):
        """读取进程输出"""
        if self.process:
            output = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            self.append_output(output)

    def append_output(self, text):
        """追加输出到文本区域"""
        self.output_text.append(text)
        # 滚动到底部
        self.output_text.moveCursor(QTextCursor.End)

    def process_finished(self, exit_code, exit_status):
        """进程执行完成处理"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 添加执行结果信息
        if exit_code == 0:
            self.append_output("\n✅ 命令执行成功!")
            if self.last_output_dir and os.path.isdir(self.last_output_dir):
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output_dir))
        else:
            self.append_output(f"\n❌ 命令执行失败! 退出码: {exit_code}")

    def close_output_dialog(self):
        """关闭输出对话框"""
        # 如果进程仍在运行，终止它
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()

        self.output_dialog.close()


if __name__ == "__main__":
    # 独立运行测试
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle("Fusion")

    # 创建并显示窗口
    window = PyInstallerGUI()
    window.show()

    sys.exit(app.exec_())
