# my_uncompyle6.py - uncompyle6反编译工具GUI
import sys
import os
import subprocess
import locale
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QMessageBox,
                             QHBoxLayout, QDialog, QLabel, QDialogButtonBox,
                             QTextEdit, QGroupBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from app_config import get_python_executable


class FileDropEdit(QLineEdit):
    """支持文件拖拽的输入框"""

    def __init__(self, parent=None, is_directory=False):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.is_directory = is_directory
        self.setPlaceholderText("拖拽文件或目录到此处 或 点击浏览")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            path = files[0]
            if self.is_directory and not os.path.isdir(path):
                QMessageBox.warning(self, "错误", "请拖拽目录而不是文件")
                return
            self.setText(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.browse()
        super().mousePressEvent(event)

    def browse(self):
        if self.is_directory:
            dir_path = QFileDialog.getExistingDirectory(
                self, "选择目录", ""
            )
            if dir_path:
                self.setText(dir_path)
        else:
            # 允许选择文件或目录
            file_path = QFileDialog.getExistingDirectory(
                self, "选择文件或目录", ""
            )
            if file_path:
                self.setText(file_path)


class Uncompyle6GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("uncompyle6反编译工具")
        self.setGeometry(300, 300, 600, 400)

        # 创建主部件和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 输入组
        input_group = QGroupBox("输入设置")
        input_layout = QVBoxLayout(input_group)

        # 输入文件/目录
        input_layout.addWidget(QLabel("PYC文件或目录:"))
        self.input_path_edit = FileDropEdit()
        input_layout.addWidget(self.input_path_edit)

        # 输出说明
        self.output_hint_label = QLabel("输出规则: 单个 PYC 反编译到同目录同名 .py；目录批量反编译到原目录")
        input_layout.addWidget(self.output_hint_label)

        layout.addWidget(input_group)

        # 执行按钮
        self.decompile_btn = QPushButton("执行反编译")
        self.decompile_btn.setFont(QFont("Arial", 12))
        self.decompile_btn.clicked.connect(self.execute_decompile)
        layout.addWidget(self.decompile_btn)

        # 添加弹性空间
        layout.addStretch()

    def execute_decompile(self):
        """执行反编译命令"""
        input_path = self.input_path_edit.text().strip()

        # 验证输入路径
        if not input_path:
            QMessageBox.warning(self, "错误", "请指定PYC文件或目录")
            return

        if not os.path.exists(input_path):
            QMessageBox.critical(self, "错误", f"路径不存在:\n{input_path}")
            return

        if os.path.isfile(input_path):
            output_dir = os.path.dirname(input_path)
            output_path = os.path.splitext(input_path)[0] + ".py"
        else:
            output_dir = input_path
            output_path = output_dir

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建输出目录:\n{str(e)}")
                return

        try:
            # 获取系统编码
            system_encoding = locale.getpreferredencoding()

            # 修复命令执行方式
            # 使用正确的模块路径调用uncompyle6
            command = [
                get_python_executable(),
                "-m", "uncompyle6.bin.uncompyle6",
                "-o", output_dir,
                input_path
            ]

            # 执行命令
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding=system_encoding,
                errors='replace'
            )

            # 显示结果对话框
            self.show_result_dialog(result, input_path, output_path)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生未知错误:\n{str(e)}")

    def show_result_dialog(self, result, input_path, output_path):
        """显示结果对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("反编译结果")
        dialog.setMinimumSize(700, 500)

        layout = QVBoxLayout(dialog)

        # 标题
        title = QLabel(f"输入路径: {input_path}\n输出位置: {output_path}")
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

        # 按钮框
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Uncompyle6GUI()
    window.show()
    sys.exit(app.exec_())
