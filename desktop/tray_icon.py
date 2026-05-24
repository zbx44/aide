"""AIDE 系统托盘 - 最小化到托盘运行，右键菜单操作

功能：
- 双击托盘图标：打开浏览器
- 右键菜单：打开界面、检查更新、修改配置、重启、查看日志、退出
- 状态指示：绿色=运行中，灰色=已停止
"""
import os
import signal
import subprocess
import sys
import webbrowser
from pathlib import Path

# PySide6 导入
try:
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
    from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
    from PySide6.QtCore import QTimer, QUrl
except ImportError:
    print("[错误] 需要安装 PySide6: pip install PySide6")
    sys.exit(1)


class AideTrayIcon:
    """AIDE系统托盘"""

    def __init__(self, root_dir: str = None):
        self.root_dir = Path(root_dir) if root_dir else self._find_root()
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # 状态
        self.service_running = False
        self.backend_process = None

        # 创建托盘
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self._create_icon("green"))
        self.tray.setToolTip("AIDE 智能助手 v0.3.0")
        self.tray.activated.connect(self._on_activated)

        # 创建菜单
        self._create_menu()

        # 定时检查服务状态
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_status)
        self.timer.start(10000)  # 每10秒检查

    def _find_root(self) -> Path:
        """自动查找项目根目录"""
        env_root = os.environ.get("AIDE_ROOT")
        if env_root:
            return Path(env_root)
        return Path(__file__).parent.parent

    def _create_icon(self, color: str) -> QIcon:
        """创建简单的彩色圆形图标"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        if color == "green":
            painter.setBrush(QColor(76, 175, 80))
        elif color == "red":
            painter.setBrush(QColor(244, 67, 54))
        else:
            painter.setBrush(QColor(158, 158, 158))
        painter.setPen(QColor(255, 255, 255))
        painter.drawEllipse(2, 2, 28, 28)
        painter.drawText(8, 22, "A")
        painter.end()
        return QIcon(pixmap)

    def _create_menu(self):
        """创建右键菜单"""
        menu = QMenu()

        # 版本显示
        version = "v0.3.0"
        version_file = self.root_dir / "VERSION"
        if version_file.exists():
            version = f"v{version_file.read_text().strip()}"

        menu.addAction(f"🧭 AIDE {version}").setEnabled(False)
        menu.addSeparator()

        # 打开界面
        open_action = QAction("🌐 打开界面", menu)
        open_action.triggered.connect(self._open_browser)
        menu.addAction(open_action)

        # 检查更新
        update_action = QAction("🆕 检查更新...", menu)
        update_action.triggered.connect(self._check_update)
        menu.addAction(update_action)

        menu.addSeparator()

        # 修改配置
        config_action = QAction("⚙️ 修改配置", menu)
        config_action.triggered.connect(self._edit_config)
        menu.addAction(config_action)

        # 重启服务
        restart_action = QAction("🔄 重启服务", menu)
        restart_action.triggered.connect(self._restart_service)
        menu.addAction(restart_action)

        # 查看日志
        log_action = QAction("📋 查看日志", menu)
        log_action.triggered.connect(self._view_logs)
        menu.addAction(log_action)

        menu.addSeparator()

        # 关于
        about_action = QAction("关于", menu)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

        # 退出
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

    def _on_activated(self, reason):
        """托盘图标激活（双击）"""
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_browser()

    def _open_browser(self):
        """打开浏览器"""
        port = 8900
        webbrowser.open(f"http://127.0.0.1:{port}")

    def _check_update(self):
        """检查更新"""
        try:
            from core.upgrade import UpgradeClient
            client = UpgradeClient(str(self.root_dir))
            update = client.check_update()
            if update:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("发现新版本")
                msg.setText(f"发现新版本 v{update['version']}")
                notes = "\n".join(f"• {n}" for n in update.get("release_notes", []))
                msg.setDetailedText(notes)
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setDefaultButton(QMessageBox.Yes)
                if msg.exec() == QMessageBox.Yes:
                    # TODO: 下载并执行升级
                    self.tray.showMessage("AIDE", "正在下载更新...", QSystemTrayIcon.Information, 3000)
            else:
                self.tray.showMessage("AIDE", "已是最新版本", QSystemTrayIcon.Information, 2000)
        except Exception as e:
            self.tray.showMessage("AIDE", f"检查更新失败: {e}", QSystemTrayIcon.Critical, 3000)

    def _edit_config(self):
        """打开配置编辑器"""
        user_env = self.root_dir / "user" / "user.env"
        config_env = self.root_dir / "config" / "default.env"

        # 尝试用系统默认编辑器打开
        target = user_env if user_env.exists() else config_env
        if sys.platform == "win32":
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)])
        else:
            subprocess.run(["xdg-open", str(target)])

    def _restart_service(self):
        """重启服务"""
        self._stop_backend()
        self._start_backend()
        self.tray.showMessage("AIDE", "服务已重启", QSystemTrayIcon.Information, 2000)

    def _view_logs(self):
        """查看日志"""
        log_dir = self.root_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(log_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(log_dir)])
        else:
            subprocess.run(["xdg-open", str(log_dir)])

    def _show_about(self):
        """关于对话框"""
        version = "0.3.0"
        version_file = self.root_dir / "VERSION"
        if version_file.exists():
            version = version_file.read_text().strip()

        QMessageBox.about(
            None, "关于 AIDE",
            f"<h3>🧭 AIDE 智能助手</h3>"
            f"<p>版本：v{version}</p>"
            f"<p>知行合一，说到做到</p>"
            f"<p>数据全部存储在本地，安全可靠</p>"
        )

    def _quit(self):
        """退出"""
        self._stop_backend()
        self.tray.hide()
        self.app.quit()

    def _is_port_in_use(self, port: int = 8900) -> bool:
        """检查端口是否已被占用"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("127.0.0.1", port))
                return True
            except (ConnectionRefusedError, OSError):
                return False

    def _start_backend(self):
        """启动后端服务"""
        # 先检查8900端口是否已有服务在跑
        if self._is_port_in_use(8900):
            print("[AIDE] 检测到8900端口已有服务运行，跳过启动后端")
            self.service_running = True
            self.tray.setIcon(self._create_icon("green"))
            return

        backend_dir = self.root_dir / "app" / "backend"
        if not backend_dir.exists():
            backend_dir = self.root_dir / "backend"

        python_exe = sys.executable
        try:
            self.backend_process = subprocess.Popen(
                [python_exe, "-m", "uvicorn", "main:app",
                 "--host", "127.0.0.1", "--port", "8900"],
                cwd=str(backend_dir),
                env={**os.environ, "AIDE_ROOT": str(self.root_dir)},
            )
            self.service_running = True
            self.tray.setIcon(self._create_icon("green"))
        except Exception as e:
            self.tray.showMessage("AIDE", f"启动失败: {e}", QSystemTrayIcon.Critical, 5000)

    def _stop_backend(self):
        """停止后端服务"""
        if self.backend_process:
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
            self.backend_process = None
        self.service_running = False
        self.tray.setIcon(self._create_icon("gray"))

    def _check_status(self):
        """定时检查服务状态"""
        if self.backend_process:
            ret = self.backend_process.poll()
            if ret is not None:
                # 服务已退出
                self.service_running = False
                self.tray.setIcon(self._create_icon("red"))
                self.tray.showMessage(
                    "AIDE", "服务意外停止，请右键重启",
                    QSystemTrayIcon.Critical, 5000
                )

    def run(self):
        """启动托盘"""
        # 先启动后端
        self._start_backend()

        # 显示托盘
        self.tray.show()
        self.tray.showMessage(
            "AIDE", "智能助手已启动\n双击图标打开界面",
            QSystemTrayIcon.Information, 3000
        )

        sys.exit(self.app.exec())


if __name__ == "__main__":
    tray = AideTrayIcon()
    tray.run()
