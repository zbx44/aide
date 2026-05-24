"""AI Assistant - Windows桌面客户端 (PySide6)"""
import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit, QTextEdit,
    QFileDialog, QMessageBox, QSystemTrayIcon, QMenu,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWebEngineWidgets import QWebEngineView


# 后端API地址
API_BASE = "http://127.0.0.1:8900"


class ChatWorker(QThread):
    """异步聊天线程"""
    response_ready = Signal(str)
    stream_chunk = Signal(str)
    error = Signal(str)

    def __init__(self, message: str, conversation_id: str = None):
        super().__init__()
        self.message = message
        self.conversation_id = conversation_id

    def run(self):
        import httpx
        try:
            with httpx.Client(timeout=60.0) as client:
                with client.stream(
                    "POST",
                    f"{API_BASE}/api/chat",
                    json={
                        "message": self.message,
                        "conversation_id": self.conversation_id,
                        "stream": True,
                    },
                ) as resp:
                    for line in resp.iter_lines():
                        if line.startswith("data:"):
                            chunk = line[5:].strip()
                            if chunk:
                                self.stream_chunk.emit(chunk)
                    self.response_ready.emit("")
        except Exception as e:
            self.error.emit(str(e))


class ChatPage(QWidget):
    """对话页面"""
    def __init__(self):
        super().__init__()
        self.conversation_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 对话显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                font-size: 14px;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        layout.addWidget(self.chat_display, stretch=1)

        # 输入区
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.returnPressed.connect(self.send_message)
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.input_field, stretch=1)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

    def send_message(self):
        msg = self.input_field.text().strip()
        if not msg:
            return

        self.chat_display.append(f"<b>我:</b> {msg}")
        self.input_field.clear()
        self.send_btn.setEnabled(False)

        self.worker = ChatWorker(msg, self.conversation_id)
        self.worker.stream_chunk.connect(self._on_chunk)
        self.worker.response_ready.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        self.chat_display.append("<b>知行:</b> ")

    def _on_chunk(self, chunk: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(chunk)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _on_done(self, _):
        self.send_btn.setEnabled(True)

    def _on_error(self, err: str):
        self.chat_display.append(f"<span style='color:red;'>错误: {err}</span>")
        self.send_btn.setEnabled(True)


class DocPage(QWidget):
    """文档生成页面"""
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("文档类型:"))
        self.doc_type_input = QLineEdit("docx")
        type_layout.addWidget(self.doc_type_input)
        layout.addLayout(type_layout)

        # 描述输入
        layout.addWidget(QLabel("描述文档内容:"))
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("例如：帮我生成一份设备运行月报，包含设备名称、运行时长、故障统计...")
        self.desc_input.setMaximumHeight(150)
        layout.addWidget(self.desc_input)

        # 生成按钮
        btn_layout = QHBoxLayout()
        self.create_btn = QPushButton("生成文档")
        self.create_btn.clicked.connect(self.create_doc)
        self.modify_input = QLineEdit()
        self.modify_input.setPlaceholderText("修改指令（如：加一个饼图）")
        self.modify_btn = QPushButton("修改文档")
        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.modify_input, stretch=1)
        btn_layout.addWidget(self.modify_btn)
        layout.addLayout(btn_layout)

        # 状态显示
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

    def create_doc(self):
        import httpx
        desc = self.desc_input.toPlainText().strip()
        doc_type = self.doc_type_input.text().strip() or "docx"
        if not desc:
            return

        self.status_label.setText("正在生成...")
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(f"{API_BASE}/api/doc/create", json={
                    "description": desc,
                    "doc_type": doc_type,
                })
                resp.raise_for_status()
                result = resp.json()
                self.status_label.setText(f"生成成功! ID: {result['doc_id']}")
                self.current_doc_id = result["doc_id"]
        except Exception as e:
            self.status_label.setText(f"生成失败: {e}")


class TaskPage(QWidget):
    """任务管理页面"""
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("定时分析任务管理（开发中...）"))


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI助手 - 知行")
        self.setMinimumSize(900, 700)

        # 中央widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # 侧边导航
        nav = QVBoxLayout()
        self.btn_chat = QPushButton("💬 对话")
        self.btn_doc = QPushButton("📄 文档")
        self.btn_task = QPushButton("📊 任务")
        self.btn_tool = QPushButton("🔧 工具")

        for btn in [self.btn_chat, self.btn_doc, self.btn_task, self.btn_tool]:
            btn.setMinimumHeight(50)
            btn.setMinimumWidth(100)
            nav.addWidget(btn)

        nav.addStretch()
        main_layout.addLayout(nav)

        # 页面容器
        self.stack = QStackedWidget()
        self.chat_page = ChatPage()
        self.doc_page = DocPage()
        self.task_page = TaskPage()
        self.stack.addWidget(self.chat_page)
        self.stack.addWidget(self.doc_page)
        self.stack.addWidget(self.task_page)
        main_layout.addWidget(self.stack, stretch=1)

        # 导航按钮事件
        self.btn_chat.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_doc.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_task.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.btn_tool.clicked.connect(lambda: self.stack.setCurrentIndex(2))

        # 系统托盘
        self._setup_tray()

    def _setup_tray(self):
        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示")
        quit_action = tray_menu.addAction("退出")

        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(QApplication.quit)

        self.tray = QSystemTrayIcon()
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(
            lambda reason: self.show() if reason == QSystemTrayIcon.DoubleClick else None
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 检查后端是否运行
    import httpx
    try:
        with httpx.Client(timeout=3.0) as client:
            client.get(f"{API_BASE}/api/health")
    except Exception:
        # 自动启动后端
        import subprocess
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", "8900"],
            cwd=backend_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
