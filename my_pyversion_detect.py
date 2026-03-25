import os
import re
import sys
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class FileDropLineEdit(QLineEdit):
    """支持拖拽 EXE 文件的输入框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setReadOnly(True)
        self.setPlaceholderText("拖入 Python 打包的 EXE，或点击浏览选择")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        if files:
            self.setText(files[0])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.browse_file()
        super().mousePressEvent(event)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 EXE 文件",
            "",
            "可执行文件 (*.exe);;所有文件 (*)"
        )
        if file_path:
            self.setText(file_path)


def normalize_compact_version(compact_version):
    """将 311 这类版本号转成 3.11"""
    if len(compact_version) == 2:
        return f"{compact_version[0]}.{compact_version[1]}"
    if len(compact_version) == 3:
        return f"{compact_version[0]}.{compact_version[1:]}"
    return compact_version


def analyze_python_version(exe_path):
    """从 EXE 二进制中识别 Python 版本"""
    with open(exe_path, "rb") as exe_file:
        binary_data = exe_file.read()

    compact_matches = sorted(
        {
            match.decode("ascii")
            for match in re.findall(rb"python(\d{2,3})\.dll", binary_data, flags=re.IGNORECASE)
        }
    )
    dotted_matches = sorted(
        {
            f"{major.decode('ascii')}.{minor.decode('ascii')}"
            for major, minor in re.findall(
                rb"python(\d)\.(\d+)",
                binary_data,
                flags=re.IGNORECASE
            )
        }
    )

    detected_versions = sorted(
        set(normalize_compact_version(version) for version in compact_matches) | set(dotted_matches)
    )

    raw_hits = []
    for compact_version in compact_matches:
        raw_hits.append(f"python{compact_version}.dll")
    for dotted_version in dotted_matches:
        raw_hits.append(f"python{dotted_version}")

    return {
        "versions": detected_versions,
        "raw_hits": raw_hits,
    }


class PyVersionDetectGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python 打包版本识别")
        self.setGeometry(320, 320, 640, 420)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        title = QLabel("识别 PyInstaller EXE 对应的 Python 版本")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        input_group = QGroupBox("文件输入")
        input_layout = QVBoxLayout(input_group)

        self.file_input = FileDropLineEdit()
        input_layout.addWidget(self.file_input)

        self.detect_btn = QPushButton("识别版本")
        self.detect_btn.setFont(QFont("Arial", 12))
        self.detect_btn.clicked.connect(self.detect_version)
        input_layout.addWidget(self.detect_btn)

        layout.addWidget(input_group)

        result_group = QGroupBox("识别结果")
        result_layout = QVBoxLayout(result_group)

        self.result_label = QLabel("等待选择 EXE 文件")
        self.result_label.setFont(QFont("Arial", 11, QFont.Bold))
        result_layout.addWidget(self.result_label)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Courier New", 10))
        self.result_text.setPlaceholderText("这里会显示命中的 Python 版本特征")
        result_layout.addWidget(self.result_text)

        layout.addWidget(result_group)

    def detect_version(self):
        exe_path = self.file_input.text().strip()

        if not exe_path:
            QMessageBox.warning(self, "错误", "请先选择或拖入 EXE 文件")
            return

        if not os.path.isfile(exe_path):
            QMessageBox.warning(self, "错误", f"文件不存在:\n{exe_path}")
            return

        try:
            result = analyze_python_version(exe_path)
        except Exception as exc:
            QMessageBox.critical(self, "识别失败", f"读取文件时发生错误:\n{exc}")
            return

        versions = result["versions"]
        raw_hits = result["raw_hits"]

        if versions:
            self.result_label.setText(f"识别到 Python 打包版本: {', '.join(versions)}")
            self.result_text.setPlainText(
                f"文件: {exe_path}\n\n"
                f"推测版本: {', '.join(versions)}\n\n"
                "命中特征:\n"
                + ("\n".join(raw_hits) if raw_hits else "无")
            )
        else:
            self.result_label.setText("未识别到明确的 Python 版本")
            self.result_text.setPlainText(
                f"文件: {exe_path}\n\n"
                "未找到 python311.dll、python3.11 这类明显版本特征。\n"
                "可能原因:\n"
                "1. 该文件不是 PyInstaller 打包产物\n"
                "2. 版本特征被裁剪或混淆\n"
                "3. 需要结合 strings 工具进一步人工确认"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PyVersionDetectGUI()
    window.show()
    sys.exit(app.exec_())
