# my_pycdc.py - pycdc反编译工具GUI
import sys
import os
import subprocess
import configparser
import locale
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QMessageBox,
                             QHBoxLayout, QDialog, QLabel, QDialogButtonBox,
                             QTextEdit)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont

# 修复1: 使用sys.executable获取可执行文件路径
if getattr(sys, 'frozen', False):
    # 打包后使用可执行文件所在目录
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 开发环境使用脚本所在目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 修复2: 配置文件放在可执行文件目录
CONFIG_FILE = os.path.join(BASE_DIR, "pycdc_config.ini")


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
            self, "选择文件", "", "Python编译文件 (*.pyc)"
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
        self.setWindowTitle("配置pycdc工具")
        self.setFixedSize(500, 200)

        layout = QVBoxLayout(self)

        # 路径标签
        layout.addWidget(QLabel("pycdc.exe 路径:"))

        # 路径输入框（支持拖拽）
        self.path_input = FileDropEdit()
        self.path_input.setText(current_path)
        layout.addWidget(self.path_input)

        # 浏览按钮
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_exe)
        layout.addWidget(browse_btn)

        # GitHub链接
        github_layout = QHBoxLayout()
        github_layout.addWidget(QLabel("获取/更新 pycdc:"))

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

    def browse_exe(self):
        """浏览选择pycdc.exe文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择pycdc.exe", "", "可执行文件 (*.exe)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def open_github(self):
        """打开GitHub项目页面"""
        github_url = "https://github.com/zrax/pycdc"
        QDesktopServices.openUrl(QUrl(github_url))

    def get_path(self):
        """获取配置的路径"""
        return self.path_input.text().strip()


class PycdcGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pycdc反编译工具")
        self.setGeometry(300, 300, 500, 250)

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
        self.status_label = QLabel(f"当前pycdc路径: {self.config['exe_path']}")
        top_layout.addWidget(self.status_label)

        layout.addLayout(top_layout)

        # 文件输入框
        self.file_input = FileDropLineEdit()
        layout.addWidget(self.file_input)

        # 输出说明
        self.output_hint_label = QLabel("输出规则: 默认反编译到同目录同名 .py 文件")
        layout.addWidget(self.output_hint_label)

        # 反编译按钮
        self.decompile_btn = QPushButton("反编译")
        self.decompile_btn.clicked.connect(self.execute_decompile)
        layout.addWidget(self.decompile_btn)

    def load_config(self):
        """加载配置文件"""
        config = configparser.ConfigParser()

        # 修复3: 使用BASE_DIR获取默认路径
        default_exe_path = os.path.join(BASE_DIR, "pycdc.exe")

        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(CONFIG_FILE):
            try:
                config['DEFAULT'] = {
                    'exe_path': default_exe_path
                }
                with open(CONFIG_FILE, 'w') as configfile:
                    config.write(configfile)
                return {'exe_path': default_exe_path}
            except Exception as e:
                # 修复4: 处理配置文件创建失败的情况
                QMessageBox.warning(
                    None,
                    "配置文件创建失败",
                    f"无法创建配置文件:\n{str(e)}\n将使用默认路径: {default_exe_path}"
                )
                return {'exe_path': default_exe_path}

        try:
            # 读取现有配置
            config.read(CONFIG_FILE)
            exe_path = config.get('DEFAULT', 'exe_path', fallback=default_exe_path)

            # 如果配置的路径不存在，使用默认路径
            if not os.path.exists(exe_path):
                exe_path = default_exe_path
                config.set('DEFAULT', 'exe_path', exe_path)
                with open(CONFIG_FILE, 'w') as configfile:
                    config.write(configfile)

            return {'exe_path': exe_path}
        except Exception as e:
            # 修复5: 处理配置文件读取失败的情况
            QMessageBox.warning(
                None,
                "配置文件读取失败",
                f"无法读取配置文件:\n{str(e)}\n将使用默认路径: {default_exe_path}"
            )
            return {'exe_path': default_exe_path}

    def save_config(self, exe_path):
        """保存配置到文件"""
        try:
            config = configparser.ConfigParser()
            config['DEFAULT'] = {
                'exe_path': exe_path
            }
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
            self.config['exe_path'] = exe_path
            self.status_label.setText(f"当前pycdc路径: {exe_path}")
        except Exception as e:
            # 修复6: 处理配置文件保存失败的情况
            QMessageBox.warning(
                None,
                "配置文件保存失败",
                f"无法保存配置文件:\n{str(e)}\n当前路径: {exe_path}"
            )

    def open_config_dialog(self):
        """打开配置对话框"""
        dialog = ConfigDialog(self.config['exe_path'], self)
        if dialog.exec_() == QDialog.Accepted:
            new_path = dialog.get_path()
            if new_path:
                # 验证路径是否有效
                if os.path.exists(new_path) and new_path.endswith('.exe'):
                    self.save_config(new_path)
                else:
                    QMessageBox.warning(
                        self,
                        "无效路径",
                        f"路径无效或不是可执行文件:\n{new_path}"
                    )

    def execute_decompile(self):
        """执行反编译命令"""
        file_path = self.file_input.text().strip()

        # 验证文件路径
        if not file_path:
            QMessageBox.warning(self, "错误", "请先选择文件")
            return

        if not os.path.isfile(file_path):
            QMessageBox.critical(self, "错误", f"文件不存在:\n{file_path}")
            return

        # 检查pycdc.exe是否存在
        exe_path = self.config['exe_path']
        if not os.path.exists(exe_path):
            QMessageBox.critical(
                self,
                "缺少依赖",
                f"未找到pycdc.exe:\n{exe_path}\n请通过配置按钮设置正确路径"
            )
            return

        try:
            # 获取系统编码
            system_encoding = locale.getpreferredencoding()
            output_file = os.path.splitext(file_path)[0] + ".py"

            # 构造命令
            command = [exe_path, file_path]

            # 执行命令
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding=system_encoding,
                errors='replace'
            )

            if result.returncode == 0:
                with open(output_file, "w", encoding=system_encoding, errors="replace") as output_handle:
                    output_handle.write(result.stdout)

            # 显示结果对话框
            self.show_result_dialog(result, file_path, output_file)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生未知错误:\n{str(e)}")

    def show_result_dialog(self, result, file_path, output_file):
        """显示结果对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("反编译结果")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(dialog)

        # 标题
        title = QLabel(f"pyc文件: {os.path.basename(file_path)}\n输出文件: {output_file}")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(title)

        # 状态
        status = QLabel(f"退出代码: {result.returncode}")
        layout.addWidget(status)

        # 输出区域
        output_label = QLabel("输出内容:")
        layout.addWidget(output_label)

        output_text = QTextEdit()
        output_text.setReadOnly(True)
        output_text.setFont(QFont("Courier New", 9))

        # 添加输出内容
        if result.stdout:
            output_text.append("标准输出:\n" + result.stdout)
        if result.stderr:
            output_text.append("\n错误输出:\n" + result.stderr)

        layout.addWidget(output_text)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PycdcGUI()
    window.show()
    sys.exit(app.exec_())
