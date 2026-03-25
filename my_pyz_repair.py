import locale
import os
import re
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_config import get_python_executable, is_valid_python_executable


class FileDropLineEdit(QLineEdit):
    """支持拖拽文件的输入框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setReadOnly(True)
        self.setPlaceholderText("拖入 PYZ.pyz 文件，或点击浏览选择")

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
            "选择 PYZ 文件",
            "",
            "PYZ文件 (*.pyz);;所有文件 (*)"
        )
        if file_path:
            self.setText(file_path)


class RepairThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, python_executable, pyz_path, parent=None):
        super().__init__(parent)
        self.python_executable = python_executable
        self.pyz_path = pyz_path

    def run(self):
        try:
            result = repair_encrypted_pyc_files(
                self.python_executable,
                self.pyz_path,
                self.progress.emit,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


def get_magic_header(struct_pyc_path):
    with open(struct_pyc_path, "rb") as file:
        header = file.read(8)
    if len(header) < 8:
        raise RuntimeError(f"struct.pyc 文件长度不足 8 字节: {struct_pyc_path}")
    return header


def list_encrypted_pyc_files(extracted_dir):
    encrypted_files = []
    for root, _, files in os.walk(extracted_dir):
        for file_name in files:
            if file_name.endswith(".pyc.encrypted"):
                encrypted_files.append(os.path.join(root, file_name))
    return sorted(encrypted_files)


def encrypted_file_to_module_name(extracted_dir, encrypted_file_path):
    relative_path = os.path.relpath(encrypted_file_path, extracted_dir)
    module_path = relative_path[:-len(".pyc.encrypted")]
    return module_path.replace("\\", ".").replace("/", ".")


def encrypted_file_to_output_pyc(encrypted_file_path):
    return encrypted_file_path[:-len(".encrypted")]


def run_archive_viewer_command(python_executable, pyz_path, interaction):
    system_encoding = locale.getpreferredencoding()
    command = [
        python_executable,
        "-m",
        "PyInstaller.utils.cliutils.archive_viewer",
        pyz_path,
    ]
    return subprocess.run(
        command,
        input=interaction,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding=system_encoding,
        errors="replace",
        cwd=os.path.dirname(pyz_path),
    )


def list_archive_entries(python_executable, pyz_path):
    result = run_archive_viewer_command(python_executable, pyz_path, "Q\n")
    output = f"{result.stdout}\n{result.stderr}"

    entry_pattern = re.compile(r"^\s*(\d+),\s*(\d+),\s*(\d+),\s*'([^']+)'", re.MULTILINE)
    entries = {}
    for match in entry_pattern.finditer(output):
        typecode, position, length, name = match.groups()
        entries[name] = {
            "typecode": int(typecode),
            "position": int(position),
            "length": int(length),
            "name": name,
        }

    if not entries:
        raise RuntimeError(
            "无法从 pyi-archive_viewer 输出中解析归档内容，请确认当前解释器已安装 PyInstaller，且输入的是有效的 PYZ 文件。"
        )

    return entries, output


def ensure_package_directories(extracted_dir, entries):
    for entry in entries.values():
        if entry["typecode"] == 3 and entry["length"] == 0:
            package_dir = os.path.join(extracted_dir, *entry["name"].split("."))
            os.makedirs(package_dir, exist_ok=True)


def prepend_magic_header_if_needed(magic_header, output_pyc_path):
    with open(output_pyc_path, "rb") as file:
        content = file.read()

    if content.startswith(magic_header):
        return False

    with open(output_pyc_path, "wb") as file:
        file.write(magic_header)
        file.write(content)
    return True


def extract_module_binary(python_executable, pyz_path, module_name, output_pyc_path):
    os.makedirs(os.path.dirname(output_pyc_path), exist_ok=True)
    if os.path.exists(output_pyc_path):
        os.remove(output_pyc_path)

    interaction = f"X {module_name}\n{output_pyc_path}\nQ\n"
    result = run_archive_viewer_command(python_executable, pyz_path, interaction)

    if result.returncode != 0 and not os.path.exists(output_pyc_path):
        raise RuntimeError(
            f"提取模块失败: {module_name}\n{result.stderr or result.stdout}"
        )

    if not os.path.exists(output_pyc_path):
        raise RuntimeError(f"提取后未生成输出文件: {output_pyc_path}")


def repair_encrypted_pyc_files(python_executable, pyz_path, progress_callback):
    pyz_dir = os.path.dirname(pyz_path)
    struct_pyc_path = os.path.join(pyz_dir, "struct.pyc")
    extracted_dir = f"{pyz_path}_extracted"

    if not os.path.isfile(pyz_path):
        raise RuntimeError(f"PYZ 文件不存在:\n{pyz_path}")
    if not os.path.isfile(struct_pyc_path):
        raise RuntimeError(f"未找到同目录 struct.pyc:\n{struct_pyc_path}")
    if not os.path.isdir(extracted_dir):
        raise RuntimeError(f"未找到解包目录:\n{extracted_dir}")

    progress_callback(f"读取魔术头: {struct_pyc_path}")
    magic_header = get_magic_header(struct_pyc_path)

    progress_callback("读取 PYZ 归档目录...")
    entries, _ = list_archive_entries(python_executable, pyz_path)
    ensure_package_directories(extracted_dir, entries)

    encrypted_files = list_encrypted_pyc_files(extracted_dir)
    if not encrypted_files:
        return {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "messages": ["未找到任何 .pyc.encrypted 文件。"],
        }

    success = 0
    failed = 0
    skipped = 0
    messages = []

    for encrypted_file in encrypted_files:
        module_name = encrypted_file_to_module_name(extracted_dir, encrypted_file)
        output_pyc_path = encrypted_file_to_output_pyc(encrypted_file)

        progress_callback(f"处理模块: {module_name}")

        entry = entries.get(module_name)
        if not entry:
            skipped += 1
            messages.append(f"[跳过] 归档中未找到模块: {module_name}")
            continue

        if entry["typecode"] != 0:
            skipped += 1
            messages.append(f"[跳过] 模块不是可提取文件项: {module_name} (typecode={entry['typecode']})")
            continue

        try:
            extract_module_binary(python_executable, pyz_path, module_name, output_pyc_path)
            header_added = prepend_magic_header_if_needed(magic_header, output_pyc_path)
            success += 1
            messages.append(
                f"[成功] {module_name} -> {output_pyc_path}"
                + ("，已补魔术头" if header_added else "，原文件已带魔术头")
            )
        except Exception as exc:
            failed += 1
            messages.append(f"[失败] {module_name}: {exc}")

    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "messages": messages,
    }


class PyzRepairGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PYZ 加密 pyc 修复工具")
        self.setGeometry(320, 320, 760, 560)
        self.worker = None

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        title = QLabel("修复 PYZ.pyz_extracted 中缺少魔术头的 .pyc.encrypted 模块")
        title.setFont(QFont("Arial", 13, QFont.Bold))
        layout.addWidget(title)

        self.python_status_label = QLabel(f"当前 Python 解释器: {get_python_executable()}")
        layout.addWidget(self.python_status_label)

        input_group = QGroupBox("输入 PYZ 文件")
        input_layout = QVBoxLayout(input_group)

        pyz_row = QHBoxLayout()
        self.pyz_input = FileDropLineEdit()
        self.pyz_input.textChanged.connect(self.update_context_display)
        pyz_row.addWidget(self.pyz_input)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.select_pyz_file)
        pyz_row.addWidget(browse_btn)
        input_layout.addLayout(pyz_row)

        self.context_label = QLabel("请先选择或拖入 PYZ.pyz 文件")
        input_layout.addWidget(self.context_label)

        layout.addWidget(input_group)

        self.run_btn = QPushButton("开始修复")
        self.run_btn.setFont(QFont("Arial", 12))
        self.run_btn.clicked.connect(self.start_repair)
        layout.addWidget(self.run_btn)

        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 9))
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

    def select_pyz_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 PYZ 文件",
            "",
            "PYZ文件 (*.pyz);;所有文件 (*)"
        )
        if file_path:
            self.pyz_input.setText(file_path)

    def update_context_display(self):
        pyz_path = self.pyz_input.text().strip()
        if not pyz_path:
            self.context_label.setText("请先选择或拖入 PYZ.pyz 文件")
            return

        pyz_dir = os.path.dirname(pyz_path)
        struct_pyc_path = os.path.join(pyz_dir, "struct.pyc")
        extracted_dir = f"{pyz_path}_extracted"

        self.context_label.setText(
            f"struct.pyc: {struct_pyc_path}\n"
            f"提取目录: {extracted_dir}"
        )

    def append_log(self, message):
        self.log_text.append(message)

    def start_repair(self):
        python_executable = get_python_executable()
        pyz_path = self.pyz_input.text().strip()

        self.python_status_label.setText(f"当前 Python 解释器: {python_executable}")

        if not is_valid_python_executable(python_executable):
            QMessageBox.warning(self, "无效解释器", "请先在主界面配置有效的 Python 解释器")
            return

        if not pyz_path:
            QMessageBox.warning(self, "错误", "请先选择或拖入 PYZ.pyz 文件")
            return

        self.log_text.clear()
        self.append_log(f"开始处理: {pyz_path}")
        self.run_btn.setEnabled(False)

        self.worker = RepairThread(python_executable, pyz_path, self)
        self.worker.progress.connect(self.append_log)
        self.worker.finished.connect(self.handle_finished)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def handle_finished(self, result):
        self.run_btn.setEnabled(True)
        for message in result["messages"]:
            self.append_log(message)

        summary = (
            f"\n处理完成\n"
            f"成功: {result['success']}\n"
            f"失败: {result['failed']}\n"
            f"跳过: {result['skipped']}"
        )
        self.append_log(summary)
        QMessageBox.information(self, "完成", summary)

    def handle_error(self, error_message):
        self.run_btn.setEnabled(True)
        self.append_log(f"[错误] {error_message}")
        QMessageBox.critical(self, "处理失败", error_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PyzRepairGUI()
    window.show()
    sys.exit(app.exec_())
