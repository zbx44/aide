"""AIDE 配置编辑器 - 中文图形界面修改配置

使用PySide6，让用户以中文界面的方式修改常用配置，
而不是直接编辑.env文件。

修改的配置写入 user/user.env，不影响 config/default.env。
"""
import os
import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QFormLayout, QGroupBox, QLineEdit, QComboBox, QPushButton,
        QLabel, QMessageBox, QSpinBox, QTextEdit, QTabWidget
    )
    from PySide6.QtCore import Qt
except ImportError:
    print("[错误] 需要安装 PySide6: pip install PySide6")
    sys.exit(1)


class ConfigEditor(QMainWindow):
    """AIDE配置编辑器"""

    def __init__(self, root_dir: str = None):
        super().__init__()
        self.root_dir = Path(root_dir) if root_dir else self._find_root()
        self.config_env = self.root_dir / "config" / "default.env"
        self.user_env = self.root_dir / "user" / "user.env"

        self.setWindowTitle("AIDE 配置编辑器")
        self.setMinimumSize(500, 600)

        # 加载配置
        self.default_config = self._parse_env(self.config_env)
        self.user_config = self._parse_env(self.user_env)
        self.merged = {**self.default_config, **self.user_config}

        # 构建UI
        self._build_ui()

    def _find_root(self) -> Path:
        env_root = os.environ.get("AIDE_ROOT")
        if env_root:
            return Path(env_root)
        return Path(__file__).parent.parent

    @staticmethod
    def _parse_env(path: Path) -> dict:
        env = {}
        if not path.exists():
            return env
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    env[key.strip()] = value.strip()
        return env

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 标签页
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab 1: AI模型配置
        ai_widget = self._build_ai_tab()
        tabs.addTab(ai_widget, "🤖 AI模型")

        # Tab 2: 数据库配置
        db_widget = self._build_db_tab()
        tabs.addTab(db_widget, "🗄️ 数据库")

        # Tab 3: 通知配置
        notify_widget = self._build_notify_tab()
        tabs.addTab(notify_widget, "📧 通知")

        # 底部按钮
        btn_layout = QHBoxLayout()

        save_btn = QPushButton("💾 保存配置")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        reset_btn = QPushButton("🔄 恢复默认")
        reset_btn.clicked.connect(self._reset)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        status_label = QLabel()
        status_label.setText(
            f"配置文件：{self.user_env}\n"
            f"（修改只保存在user目录，升级时不会被覆盖）"
        )
        status_label.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(status_label)
        layout.addLayout(btn_layout)

    def _build_ai_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        # LLM Provider
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "公司内网 (vLLM)",
            "腾讯混元",
            "DeepSeek",
            "通义千问",
            "Moonshot (Kimi)",
            "自定义"
        ])
        self.provider_combo.setCurrentText(self._provider_display())
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("AI模型来源：", self.provider_combo)

        # 服务器地址
        self.llm_url = QLineEdit(self.merged.get("LLM_BASE_URL", ""))
        form.addRow("服务器地址：", self.llm_url)

        # 模型名称
        self.llm_model = QLineEdit(self.merged.get("LLM_MODEL", ""))
        form.addRow("模型名称：", self.llm_model)

        # API Key
        self.llm_api_key = QLineEdit(self.merged.get("LLM_TENCENT_API_KEY", "") or 
                                     self.merged.get("LLM_OPENAI_API_KEY", ""))
        self.llm_api_key.setEchoMode(QLineEdit.Password)
        form.addRow("API密钥：", self.llm_api_key)

        # 通用参数
        self.llm_max_tokens = QSpinBox()
        self.llm_max_tokens.setRange(1024, 65536)
        self.llm_max_tokens.setValue(int(self.merged.get("LLM_MAX_TOKENS", "4096")))
        form.addRow("最大生成长度：", self.llm_max_tokens)

        self.llm_temperature = QSpinBox()
        self.llm_temperature.setRange(0, 100)
        self.llm_temperature.setValue(int(float(self.merged.get("LLM_TEMPERATURE", "0.7")) * 100))
        form.addRow("创造性（0-100）：", self.llm_temperature)

        # 测试连接
        test_btn = QPushButton("🔍 测试连接")
        test_btn.clicked.connect(self._test_connection)
        form.addRow("", test_btn)

        return widget

    def _build_db_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self.dm_host = QLineEdit(self.merged.get("DM_HOST", ""))
        form.addRow("主库地址：", self.dm_host)

        self.dm_standby = QLineEdit(self.merged.get("DM_STANDBY_HOST", ""))
        form.addRow("备库地址：", self.dm_standby)

        self.dm_port = QLineEdit(self.merged.get("DM_PORT", "5236"))
        form.addRow("端口：", self.dm_port)

        self.dm_user = QLineEdit(self.merged.get("DM_USERNAME", "dmdb"))
        form.addRow("用户名：", self.dm_user)

        self.dm_password = QLineEdit(self.merged.get("DM_PASSWORD", ""))
        self.dm_password.setEchoMode(QLineEdit.Password)
        form.addRow("密码：", self.dm_password)

        self.dm_database = QLineEdit(self.merged.get("DM_DATABASE", "lczx"))
        form.addRow("数据库名：", self.dm_database)

        # 测试连接
        test_btn = QPushButton("🔍 测试数据库连接")
        test_btn.clicked.connect(self._test_db_connection)
        form.addRow("", test_btn)

        return widget

    def _build_notify_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self.email_sender = QLineEdit(self.merged.get("EMAIL_SENDER", ""))
        form.addRow("发件邮箱：", self.email_sender)

        self.email_password = QLineEdit(self.merged.get("EMAIL_PASSWORD", ""))
        self.email_password.setEchoMode(QLineEdit.Password)
        form.addRow("邮箱授权码：", self.email_password)

        self.oa_url = QLineEdit(self.merged.get("SEELYON_BASE_URL", ""))
        form.addRow("OA系统地址：", self.oa_url)

        self.oa_user = QLineEdit(self.merged.get("SEELYON_USERNAME", ""))
        form.addRow("OA用户名：", self.oa_user)

        self.oa_password = QLineEdit(self.merged.get("SEELYON_PASSWORD", ""))
        self.oa_password.setEchoMode(QLineEdit.Password)
        form.addRow("OA密码：", self.oa_password)

        return widget

    def _provider_display(self) -> str:
        provider = self.merged.get("LLM_PROVIDER", "vllm")
        mapping = {
            "vllm": "公司内网 (vLLM)",
            "tencent": "腾讯混元",
            "openai": "DeepSeek",
            "custom": "自定义",
        }
        return mapping.get(provider, provider)

    def _on_provider_changed(self, text):
        """切换Provider时自动填入默认值"""
        if "内网" in text or "vLLM" in text:
            self.llm_url.setText("http://192.168.1.100:8000/v1")
            self.llm_model.setText("qwen3.6-27B")
            self.llm_api_key.setText("")
        elif "腾讯" in text:
            self.llm_url.setText("https://api.hunyuan.cloud.tencent.com/v1")
            self.llm_model.setText("hunyuan-lite")
        elif "DeepSeek" in text:
            self.llm_url.setText("https://api.deepseek.com/v1")
            self.llm_model.setText("deepseek-chat")
        elif "通义" in text:
            self.llm_url.setText("https://dashscope.aliyuncs.com/compatible-mode/v1")
            self.llm_model.setText("qwen-plus")
        elif "Moonshot" in text or "Kimi" in text:
            self.llm_url.setText("https://api.moonshot.cn/v1")
            self.llm_model.setText("moonshot-v1-8k")

    def _test_connection(self):
        """测试LLM连接"""
        url = self.llm_url.text()
        if not url:
            QMessageBox.warning(self, "提示", "请填写服务器地址")
            return

        try:
            import urllib.request
            models_url = f"{url.rstrip('/')}/models" if not url.endswith("/models") else url
            req = urllib.request.Request(models_url, headers={"User-Agent": "AIDE"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    QMessageBox.information(self, "成功", "✅ 连接成功，AI模型可用！")
                else:
                    QMessageBox.warning(self, "失败", f"连接返回状态码：{resp.status}")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"❌ 连接失败：{e}")

    def _test_db_connection(self):
        """测试数据库连接"""
        host = self.dm_host.text()
        if not host:
            QMessageBox.warning(self, "提示", "请填写主库地址")
            return
        # 达梦数据库连接测试需要dmPython，简单检查网络连通性
        import socket
        port = int(self.dm_port.text() or "5236")
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            QMessageBox.information(self, "成功", f"✅ 网络连通 {host}:{port}")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"❌ 连接失败：{e}")

    def _save(self):
        """保存配置到user/user.env"""
        # 收集变更的配置项
        changes = {}

        # AI模型
        provider_text = self.provider_combo.currentText()
        if "内网" in provider_text:
            changes["LLM_PROVIDER"] = "vllm"
        elif "腾讯" in provider_text:
            changes["LLM_PROVIDER"] = "tencent"
        elif "DeepSeek" in provider_text:
            changes["LLM_PROVIDER"] = "openai"
        elif "通义" in provider_text:
            changes["LLM_PROVIDER"] = "openai"
        elif "Moonshot" in provider_text:
            changes["LLM_PROVIDER"] = "openai"
        else:
            changes["LLM_PROVIDER"] = "custom"

        provider = changes["LLM_PROVIDER"]
        if provider == "vllm":
            changes["LLM_BASE_URL"] = self.llm_url.text()
            changes["LLM_API_KEY"] = self.llm_api_key.text() or "not-needed"
            changes["LLM_MODEL"] = self.llm_model.text()
        elif provider == "tencent":
            changes["LLM_TENCENT_BASE_URL"] = self.llm_url.text()
            changes["LLM_TENCENT_API_KEY"] = self.llm_api_key.text()
            changes["LLM_TENCENT_MODEL"] = self.llm_model.text()
        elif provider == "openai":
            changes["LLM_OPENAI_BASE_URL"] = self.llm_url.text()
            changes["LLM_OPENAI_API_KEY"] = self.llm_api_key.text()
            changes["LLM_OPENAI_MODEL"] = self.llm_model.text()
        elif provider == "custom":
            changes["LLM_CUSTOM_BASE_URL"] = self.llm_url.text()
            changes["LLM_CUSTOM_API_KEY"] = self.llm_api_key.text()
            changes["LLM_CUSTOM_MODEL"] = self.llm_model.text()

        changes["LLM_MAX_TOKENS"] = str(self.llm_max_tokens.value())
        changes["LLM_TEMPERATURE"] = str(self.llm_temperature.value() / 100)

        # 数据库
        if self.dm_host.text():
            changes["DM_HOST"] = self.dm_host.text()
            changes["DM_STANDBY_HOST"] = self.dm_standby.text()
            changes["DM_PORT"] = self.dm_port.text()
            changes["DM_USERNAME"] = self.dm_user.text()
            changes["DM_PASSWORD"] = self.dm_password.text()
            changes["DM_DATABASE"] = self.dm_database.text()

        # 通知
        if self.email_sender.text():
            changes["EMAIL_SENDER"] = self.email_sender.text()
            changes["EMAIL_PASSWORD"] = self.email_password.text()
        if self.oa_url.text():
            changes["SEELYON_BASE_URL"] = self.oa_url.text()
            changes["SEELYON_USERNAME"] = self.oa_user.text()
            changes["SEELYON_PASSWORD"] = self.oa_password.text()

        # 与默认配置对比，只保存不同的
        custom = {}
        for k, v in changes.items():
            if v and v != self.default_config.get(k, ""):
                custom[k] = v

        # 写入user/user.env
        self.user_env.parent.mkdir(parents=True, exist_ok=True)
        with open(self.user_env, "w", encoding="utf-8") as f:
            f.write("# AIDE 用户自定义配置\n")
            f.write("# 此文件优先级高于 config/default.env\n")
            f.write("# 升级时不会被覆盖\n\n")
            for k, v in sorted(custom.items()):
                f.write(f"{k}={v}\n")

        QMessageBox.information(
            self, "保存成功",
            f"配置已保存到：{self.user_env}\n\n"
            f"修改了 {len(custom)} 项配置。\n"
            f"重启服务后生效。"
        )

    def _reset(self):
        """恢复默认配置"""
        reply = QMessageBox.question(
            self, "确认",
            "确定要恢复默认配置吗？\n你自定义的配置将被清除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 清空user.env
            with open(self.user_env, "w", encoding="utf-8") as f:
                f.write("# AIDE 用户自定义配置\n")
                f.write("# 此文件优先级高于 config/default.env\n")
                f.write("# 升级时不会被覆盖\n\n")
            QMessageBox.information(self, "已恢复", "已恢复默认配置，重启服务后生效。")
            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = ConfigEditor()
    editor.show()
    sys.exit(app.exec_())
