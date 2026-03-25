import sys
import os
import subprocess
import shutil
import locale
import configparser
import webbrowser
import threading
import tempfile
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QMessageBox,
                             QHBoxLayout, QDialog, QLabel, QDialogButtonBox,
                             QProgressDialog, QTextEdit, QGroupBox)
from PyQt5.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from app_config import get_python_executable, is_valid_python_executable

# 修复1: 使用sys.executable获取可执行文件路径
if getattr(sys, 'frozen', False):
    # 打包后使用可执行文件所在目录
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 开发环境使用脚本所在目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 修复2: 配置文件放在可执行文件目录
CONFIG_FILE = os.path.join(BASE_DIR, "unpacker_config.ini")


class FileDropEdit(QLineEdit):
    """支持文件拖拽的输入框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("拖拽文件到此处 或 点击浏览")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.setText(files[0])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.browse_file()
        super().mousePressEvent(event)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "可执行文件 (*.exe)"
        )
        if file_path:
            self.setText(file_path)


class FileDropLineEdit(FileDropEdit):
    """主界面文件拖拽输入框（只读）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("拖拽文件到此处 或 点击浏览")


class ConfigDialog(QDialog):
    """配置对话框"""

    def __init__(self, current_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置解包工具")
        self.setFixedSize(500, 200)  # 增加高度以适应新控件

        layout = QVBoxLayout(self)

        # 路径标签
        layout.addWidget(QLabel("pyinstxtractor.py 路径:"))

        # 路径输入框（支持拖拽）
        self.path_input = FileDropEdit()
        self.path_input.setText(current_path)
        layout.addWidget(self.path_input)

        # 浏览按钮
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_script)
        layout.addWidget(browse_btn)

        # GitHub链接
        github_layout = QHBoxLayout()
        github_layout.addWidget(QLabel("获取/更新 pyinstxtractor.py:"))

        github_btn = QPushButton("GitHub 项目页面")
        github_btn.setStyleSheet("color: blue; text-decoration: underline;")
        github_btn.setCursor(Qt.PointingHandCursor)
        github_btn.clicked.connect(self.open_github)
        github_layout.addWidget(github_btn)

        github_layout.addStretch()
        layout.addLayout(github_layout)

        # 按钮框
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def browse_script(self):
        """浏览选择pyinstxtractor.py文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择pyinstxtractor.py", "", "Python脚本 (*.py)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def open_github(self):
        """打开GitHub项目页面"""
        github_url = "https://github.com/extremecoders-re/pyinstxtractor"
        QDesktopServices.openUrl(QUrl(github_url))

    def get_path(self):
        """获取配置的路径"""
        return self.path_input.text().strip()


class UnpackThread(QThread):
    """解包线程，避免阻塞主线程"""
    finished = pyqtSignal(int, str, str, str, str)  # returncode, stdout, stderr, target_dir, extracted_dir
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, command, target_dir, extracted_dir, parent=None):
        super().__init__(parent)
        self.command = command
        self.target_dir = target_dir
        self.extracted_dir = extracted_dir
        self.cancelled = False

    def run(self):
        try:
            # 获取系统编码
            system_encoding = locale.getpreferredencoding()

            # 修复1: 使用临时文件捕获输出，避免内存溢出
            with tempfile.TemporaryFile(mode='w+', encoding=system_encoding) as stdout_file, \
                    tempfile.TemporaryFile(mode='w+', encoding=system_encoding) as stderr_file:

                self.progress.emit(f"执行命令: {' '.join(self.command)}")

                # 启动子进程
                process = subprocess.Popen(
                    self.command,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    encoding=system_encoding,
                    errors='replace',
                    cwd=BASE_DIR
                )

                # 定期检查进程状态
                while process.poll() is None:
                    if self.cancelled:
                        process.terminate()
                        self.error.emit("操作已取消")
                        return
                    time.sleep(0.1)  # 避免过度占用CPU

                # 读取输出
                stdout_file.seek(0)
                stdout = stdout_file.read()
                stderr_file.seek(0)
                stderr = stderr_file.read()

                self.finished.emit(process.returncode, stdout, stderr, self.target_dir, self.extracted_dir)

        except Exception as e:
            import traceback
            self.error.emit(f"解包过程中发生错误:\n{str(e)}\n\n{traceback.format_exc()}")


class PyInstxtractorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyInstaller解包工具")
        self.setGeometry(300, 300, 500, 200)
        self.unpack_thread = None
        self.progress_dialog = None

        # 加载配置
        self.config = self.load_config()

        # 创建主部件和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 顶部按钮布局
        top_layout = QHBoxLayout()

        # 配置按钮
        self.config_btn = QPushButton("配置")
        self.config_btn.clicked.connect(self.open_config_dialog)
        top_layout.addWidget(self.config_btn)

        # 状态标签
        self.status_label = QLabel(f"当前pyinstxtractor路径: {self.config['script_path']}")
        top_layout.addWidget(self.status_label)

        layout.addLayout(top_layout)

        self.python_status_label = QLabel(f"当前Python解释器: {get_python_executable()}")
        layout.addWidget(self.python_status_label)

        # 文件输入框
        self.file_input = FileDropLineEdit()
        self.file_input.textChanged.connect(self.update_command_display)
        layout.addWidget(self.file_input)

        command_group = QGroupBox("预期命令")
        command_layout = QVBoxLayout(command_group)

        self.command_display = QTextEdit()
        self.command_display.setReadOnly(True)
        self.command_display.setPlaceholderText("选择待解包 EXE 后，这里会显示实际执行的命令")
        command_layout.addWidget(self.command_display)

        layout.addWidget(command_group)

        # 解包按钮
        self.unpack_btn = QPushButton("解包")
        self.unpack_btn.clicked.connect(self.execute_unpack)
        layout.addWidget(self.unpack_btn)

        self.update_command_display()

    def load_config(self):
        """加载配置文件"""
        config = configparser.ConfigParser()

        # 修复3: 使用BASE_DIR获取默认路径
        default_script_path = os.path.join(BASE_DIR, "pyinstxtractor.py")

        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(CONFIG_FILE):
            try:
                config['DEFAULT'] = {
                    'script_path': default_script_path
                }
                with open(CONFIG_FILE, 'w') as configfile:
                    config.write(configfile)
                return {'script_path': default_script_path}
            except Exception as e:
                # 修复4: 处理配置文件创建失败的情况
                QMessageBox.warning(
                    self,
                    "配置文件创建失败",
                    f"无法创建配置文件:\n{str(e)}\n将使用默认路径: {default_script_path}"
                )
                return {'script_path': default_script_path}

        try:
            # 读取现有配置
            config.read(CONFIG_FILE)
            script_path = config.get('DEFAULT', 'script_path', fallback=default_script_path)

            # 如果配置的路径不存在，使用默认路径
            if not os.path.exists(script_path):
                script_path = default_script_path
                config.set('DEFAULT', 'script_path', script_path)
                with open(CONFIG_FILE, 'w') as configfile:
                    config.write(configfile)

            return {'script_path': script_path}
        except Exception as e:
            # 修复5: 处理配置文件读取失败的情况
            QMessageBox.warning(
                self,
                "配置文件读取失败",
                f"无法读取配置文件:\n{str(e)}\n将使用默认路径: {default_script_path}"
            )
            return {'script_path': default_script_path}

    def save_config(self, script_path):
        """保存配置到文件"""
        try:
            config = configparser.ConfigParser()
            config['DEFAULT'] = {
                'script_path': script_path
            }
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
            self.config['script_path'] = script_path
            self.status_label.setText(f"当前pyinstxtractor路径: {script_path}")
            self.update_command_display()
        except Exception as e:
            # 修复6: 处理配置文件保存失败的情况
            QMessageBox.warning(
                self,
                "配置文件保存失败",
                f"无法保存配置文件:\n{str(e)}\n当前路径: {script_path}"
            )

    def open_config_dialog(self):
        """打开配置对话框"""
        dialog = ConfigDialog(self.config['script_path'], self)
        if dialog.exec_() == QDialog.Accepted:
            new_path = dialog.get_path()
            if new_path:
                # 验证路径是否有效
                if os.path.exists(new_path) and new_path.endswith('.py'):
                    self.save_config(new_path)
                else:
                    QMessageBox.warning(
                        self,
                        "无效路径",
                        f"路径无效或不是Python脚本:\n{new_path}"
                    )

    def build_unpack_command(self):
        """构建解包命令"""
        python_exe = get_python_executable()
        script_path = self.config['script_path']
        file_path = self.file_input.text().strip()

        if not is_valid_python_executable(python_exe):
            return None
        if not script_path or not os.path.exists(script_path):
            return None
        if not file_path:
            return None

        return [python_exe, script_path, file_path]

    def update_command_display(self):
        """更新预期命令显示"""
        python_exe = get_python_executable()
        self.python_status_label.setText(f"当前Python解释器: {python_exe}")

        if not is_valid_python_executable(python_exe):
            self.command_display.setPlainText("请先在主界面配置有效的 Python 解释器")
            return

        script_path = self.config['script_path']
        if not script_path or not os.path.exists(script_path):
            self.command_display.setPlainText("请先配置有效的 pyinstxtractor.py 路径")
            return

        if not self.file_input.text().strip():
            self.command_display.setPlainText("请先选择待解包的 EXE 文件")
            return

        command = self.build_unpack_command()
        if command:
            self.command_display.setPlainText(subprocess.list2cmdline(command))
        else:
            self.command_display.setPlainText("无法生成解包命令，请检查输入")

    def execute_unpack(self):
        """执行解包命令并移动解包文件"""
        file_path = self.file_input.text().strip()

        # 验证文件路径
        if not file_path:
            QMessageBox.warning(self, "错误", "请先选择文件")
            return

        if not os.path.isfile(file_path):
            QMessageBox.critical(self, "错误", f"文件不存在:\n{file_path}")
            return

        # 检查pyinstxtractor.py是否存在
        script_path = self.config['script_path']
        if not os.path.exists(script_path):
            QMessageBox.critical(
                self,
                "缺少依赖",
                f"未找到pyinstxtractor.py:\n{script_path}\n请通过配置按钮设置正确路径"
            )
            return

        # 获取原文件所在目录和文件名
        original_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        # 构造目标目录路径（与原文件同目录）
        target_dir = os.path.join(original_dir, f"{file_name}_extracted")
        # 修复7: 使用BASE_DIR代替os.getcwd()
        extracted_dir = os.path.join(BASE_DIR, f"{file_name}_extracted")

        # 修复8: 创建进度对话框
        self.progress_dialog = QProgressDialog("正在解包，请稍候...", "取消", 0, 0, self)
        self.progress_dialog.setWindowTitle("解包中")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setCancelButton(None)  # 暂时禁用取消按钮
        self.progress_dialog.show()

        # # 修复9: 使用线程执行解包操作
        # command = [
        #     sys.executable,  # 使用当前Python解释器
        #     script_path,
        #     file_path
        # ]

        command = self.build_unpack_command()
        if not command:
            QMessageBox.critical(self, "错误", "未找到有效的 Python 解释器，请先在主界面配置并保存")
            return

        self.unpack_thread = UnpackThread(command, target_dir, extracted_dir)
        self.unpack_thread.finished.connect(self.handle_unpack_finished)
        self.unpack_thread.error.connect(self.handle_unpack_error)
        self.unpack_thread.progress.connect(self.update_progress)
        self.unpack_thread.start()

    def update_progress(self, message):
        """更新进度对话框消息"""
        if self.progress_dialog:
            self.progress_dialog.setLabelText(message)

    def handle_unpack_finished(self, returncode, stdout, stderr, target_dir, extracted_dir):
        """处理解包完成事件"""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        # 检查解包结果
        if returncode == 0:
            # 检查解包目录是否创建在程序运行目录下
            if os.path.exists(extracted_dir):
                # 如果目标目录已存在，先删除
                if os.path.exists(target_dir):
                    try:
                        shutil.rmtree(target_dir)
                    except Exception as e:
                        QMessageBox.critical(
                            self,
                            "删除目录失败",
                            f"无法删除现有目录:\n{target_dir}\n错误: {str(e)}"
                        )
                        return

                try:
                    # 移动解包目录到原文件所在目录
                    shutil.move(extracted_dir, target_dir)

                    QMessageBox.information(
                        self,
                        "完成",
                        f"解包成功完成!\n解包文件已移动到:\n{target_dir}"
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "移动文件失败",
                        f"无法移动解包文件:\n{str(e)}"
                    )
            else:
                # 尝试从输出中获取信息
                possible_dirs = [
                    extracted_dir,
                    os.path.join(os.path.dirname(self.config['script_path']),
                                 f"{os.path.basename(self.file_input.text())}_extracted"),
                    os.path.join(os.path.dirname(self.file_input.text()),
                                 f"{os.path.basename(self.file_input.text())}_extracted"),
                    os.path.join(BASE_DIR, f"{os.path.basename(self.file_input.text())}_extracted")
                ]

                found_dir = None
                for dir_path in possible_dirs:
                    if os.path.exists(dir_path):
                        found_dir = dir_path
                        break

                if found_dir:
                    QMessageBox.warning(
                        self,
                        "解包目录位置",
                        f"解包目录创建在:\n{found_dir}\n\n"
                        f"请手动移动到所需位置"
                    )
                else:
                    # 修复10: 显示更详细的错误信息
                    error_msg = "解包命令执行成功，但未找到解包目录\n\n"
                    error_msg += f"请检查以下位置:\n"
                    error_msg += "\n".join(possible_dirs)
                    error_msg += f"\n\n解包日志:\n{stdout}"

                    QMessageBox.warning(
                        self,
                        "警告",
                        error_msg
                    )
        else:
            error_msg = f"解包失败 (错误代码: {returncode})\n\n"
            error_msg += f"错误信息:\n{stderr if stderr else stdout}"
            QMessageBox.critical(self, "解包失败", error_msg)

    def handle_unpack_error(self, error_msg):
        """处理解包错误事件"""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        QMessageBox.critical(self, "错误", error_msg)

    def closeEvent(self, event):
        """窗口关闭时确保线程停止"""
        if self.unpack_thread and self.unpack_thread.isRunning():
            self.unpack_thread.cancelled = True
            self.unpack_thread.wait(2000)  # 等待2秒
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PyInstxtractorGUI()
    window.show()
    sys.exit(app.exec_())
