from __future__ import annotations
"""AIDE 升级客户端 - 检查更新、下载、执行升级、回滚

升级流程：
1. 检查更新（从内网服务器或本地文件）
2. 下载更新包 + 校验checksum
3. 停止后端服务
4. 备份当前 app/ 目录
5. 解压覆盖 app/ 和 config/
6. 不碰 data/、user/、output/、logs/
7. 合并新配置项（不覆盖用户自定义的）
8. 执行数据库迁移
9. 更新 VERSION 文件
10. 重启后端服务
11. 失败则自动回滚
"""
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class UpgradeClient:
    """AIDE升级客户端"""

    def __init__(self, root_dir: str = None):
        if root_dir:
            self.root_dir = Path(root_dir)
        else:
            # 自动检测
            env_root = os.environ.get("AIDE_ROOT")
            if env_root:
                self.root_dir = Path(env_root)
            else:
                self.root_dir = Path(__file__).parent.parent.parent

        self.app_dir = self.root_dir / "app"
        self.config_dir = self.root_dir / "config"
        self.data_dir = self.root_dir / "data"
        self.user_dir = self.root_dir / "user"
        self.version_file = self.root_dir / "VERSION"
        self.backup_dir = self.root_dir / "_upgrade_backups"

        # 升级服务器地址（从config读取或环境变量）
        self.update_server = os.environ.get(
            "AIDE_UPDATE_SERVER", 
            "http://your-update-server:9090/aide-updates"
        )

    def get_current_version(self) -> str:
        """获取当前版本号"""
        if self.version_file.exists():
            return self.version_file.read_text().strip()
        return "0.0.0"

    def check_update(self) -> Optional[dict]:
        """检查是否有新版本

        Returns:
            有新版本返回版本信息dict，没有返回None
        """
        try:
            import urllib.request
            manifest_url = f"{self.update_server}/manifest.json"
            logger.info(f"检查更新: {manifest_url}")

            req = urllib.request.Request(manifest_url, headers={"User-Agent": "AIDE-Updater"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                manifest = json.loads(resp.read().decode("utf-8"))

            latest = manifest.get("latest_version", "0.0.0")
            current = self.get_current_version()

            if self._compare_versions(latest, current) > 0:
                # 找到对应的更新信息
                for update in manifest.get("updates", []):
                    if update["version"] == latest:
                        update["current_version"] = current
                        update["manifest"] = manifest
                        return update

            return None  # 已是最新

        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return None

    def check_local_update(self, zip_path: str) -> Optional[dict]:
        """检查本地更新包

        Args:
            zip_path: 本地更新包路径

        Returns:
            更新信息dict
        """
        path = Path(zip_path)
        if not path.exists():
            return None

        # 尝试从zip中读取UPGRADE_INFO.json
        try:
            with zipfile.ZipFile(path, "r") as zf:
                if "UPGRADE_INFO.json" in zf.namelist():
                    info = json.loads(zf.read("UPGRADE_INFO.json"))
                    info["local_file"] = str(path)
                    info["current_version"] = self.get_current_version()
                    return info
        except Exception as e:
            logger.error(f"读取本地更新包失败: {e}")

        # 如果没有UPGRADE_INFO.json，用基本信息
        return {
            "version": "未知",
            "local_file": str(path),
            "current_version": self.get_current_version(),
            "release_notes": ["本地更新包"],
        }

    def download_update(self, update_info: dict, 
                        progress_callback: Callable = None) -> Optional[str]:
        """下载更新包

        Args:
            update_info: check_update()返回的版本信息
            progress_callback: 进度回调函数(downloaded, total)

        Returns:
            下载的临时文件路径，失败返回None
        """
        file_path = update_info.get("file")
        if not file_path:
            return None

        url = f"{self.update_server}/{file_path}"
        expected_size = update_info.get("size", 0)
        expected_checksum = update_info.get("checksum", "")

        logger.info(f"下载更新包: {url}")

        try:
            import urllib.request
            tmp_dir = tempfile.mkdtemp(prefix="aide_update_")
            tmp_file = os.path.join(tmp_dir, os.path.basename(file_path))

            req = urllib.request.Request(url, headers={"User-Agent": "AIDE-Updater"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", expected_size))
                downloaded = 0
                chunk_size = 65536

                with open(tmp_file, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)

            # 校验文件大小
            actual_size = os.path.getsize(tmp_file)
            if expected_size and actual_size != expected_size:
                logger.error(f"文件大小不匹配: 期望{expected_size}, 实际{actual_size}")
                os.remove(tmp_file)
                return None

            # 校验checksum
            if expected_checksum:
                actual_checksum = self._calc_md5(tmp_file)
                if actual_checksum != expected_checksum:
                    logger.error(f"校验和不匹配: 期望{expected_checksum}, 实际{actual_checksum}")
                    os.remove(tmp_file)
                    return None

            logger.info(f"下载完成: {tmp_file}")
            return tmp_file

        except Exception as e:
            logger.error(f"下载更新包失败: {e}")
            return None

    def execute_upgrade(self, zip_path: str, 
                        update_info: dict = None) -> dict:
        """执行升级

        Args:
            zip_path: 更新包zip文件路径
            update_info: 版本信息（可选）

        Returns:
            升级结果dict
        """
        result = {
            "success": False,
            "from_version": self.get_current_version(),
            "to_version": "?",
            "backup_path": None,
            "config_conflicts": [],
            "errors": [],
            "started_at": datetime.now().isoformat(),
        }

        try:
            # 1. 读取更新包信息
            target_version = "?"
            with zipfile.ZipFile(zip_path, "r") as zf:
                if "UPGRADE_INFO.json" in zf.namelist():
                    info = json.loads(zf.read("UPGRADE_INFO.json"))
                    target_version = info.get("version", "?")
                if "upgrade_script.py" in zf.namelist():
                    # 提取升级脚本
                    script_dir = self.root_dir / "_upgrade_temp"
                    script_dir.mkdir(exist_ok=True)
                    zf.extract("upgrade_script.py", script_dir)

            result["to_version"] = target_version
            logger.info(f"开始升级: {result['from_version']} → {target_version}")

            # 2. 停止后端服务
            logger.info("停止后端服务...")
            self._stop_service()

            # 3. 备份当前app/目录
            backup_name = f"app_backup_v{result['from_version']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path = self.backup_dir / backup_name
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            if self.app_dir.exists():
                logger.info(f"备份当前版本: {backup_path}")
                shutil.copytree(self.app_dir, backup_path)
                result["backup_path"] = str(backup_path)

            # 4. 解压覆盖 app/ 和 config/
            logger.info("解压更新包...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    # 只覆盖 app/ 和 config/ 目录
                    if member.startswith("app/") or member.startswith("config/"):
                        # 跳过目录条目
                        if member.endswith("/"):
                            continue
                        # 计算目标路径
                        dest = self.root_dir / member
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            # 5. 合并配置（不覆盖用户自定义的）
            logger.info("合并配置...")
            conflicts = self._merge_config(update_info)
            result["config_conflicts"] = conflicts

            # 6. 执行数据库迁移
            logger.info("执行数据库迁移...")
            script_path = self.root_dir / "_upgrade_temp" / "upgrade_script.py"
            if script_path.exists():
                self._run_migration_script(script_path)

            # 7. 更新VERSION文件
            self.version_file.write_text(target_version)
            logger.info(f"版本更新: {target_version}")

            # 8. 清理临时文件
            temp_dir = self.root_dir / "_upgrade_temp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

            result["success"] = True
            result["finished_at"] = datetime.now().isoformat()
            logger.info("升级完成！")

        except Exception as e:
            logger.error(f"升级失败: {e}")
            result["errors"].append(str(e))

            # 自动回滚
            if result["backup_path"]:
                logger.info("开始回滚...")
                try:
                    if self.app_dir.exists():
                        shutil.rmtree(self.app_dir)
                    shutil.copytree(Path(result["backup_path"]), self.app_dir)
                    logger.info("回滚完成")
                    result["rolled_back"] = True
                except Exception as re:
                    logger.error(f"回滚失败: {re}")
                    result["errors"].append(f"回滚失败: {re}")

        # 9. 重启服务
        try:
            self._start_service()
        except Exception as e:
            result["errors"].append(f"重启服务失败: {e}")

        return result

    def _merge_config(self, update_info: dict = None) -> list:
        """合并配置文件

        策略：
        - config/default.env 直接覆盖（开发者维护）
        - 如果用户在user/user.env中覆盖了某个配置项，保留用户的值
        - 新增的配置项自动追加到config/default.env

        Returns:
            有冲突的配置项列表（用户覆盖了但默认值也变了）
        """
        conflicts = []
        user_env = self.user_dir / "user.env"

        if not user_env.exists() or not update_info:
            return conflicts

        # 读取用户自定义的配置项
        user_vars = self._parse_env(user_env)
        if not user_vars:
            return conflicts

        # 检查更新中变更的配置项
        config_updates = update_info.get("config_updates", {})
        changed_keys = config_updates.get("changed_keys", {})

        for key, new_default in changed_keys.items():
            if key in user_vars:
                # 用户覆盖了这个配置项，且默认值变了，记为冲突
                conflicts.append({
                    "key": key,
                    "user_value": user_vars[key],
                    "new_default": new_default,
                })

        return conflicts

    def _run_migration_script(self, script_path: Path):
        """执行数据库迁移脚本"""
        try:
            result = subprocess.run(
                [sys.executable, str(script_path), "--root", str(self.root_dir)],
                capture_output=True, text=True, timeout=60, cwd=str(self.root_dir)
            )
            if result.returncode != 0:
                logger.error(f"迁移脚本执行失败: {result.stderr}")
            else:
                logger.info(f"迁移脚本执行完成: {result.stdout}")
        except Exception as e:
            logger.error(f"迁移脚本执行异常: {e}")

    def _stop_service(self):
        """停止后端服务"""
        # Linux
        try:
            subprocess.run(["pkill", "-f", "uvicorn main:app"], timeout=10)
            time.sleep(2)
        except Exception:
            pass

        # Windows
        try:
            subprocess.run(["taskkill", "/f", "/im", "uvicorn.exe"], timeout=10)
            time.sleep(2)
        except Exception:
            pass

    def _start_service(self):
        """重启后端服务"""
        start_sh = self.root_dir / "start.sh"
        start_bat = self.root_dir / "start.bat"

        if sys.platform == "win32" and start_bat.exists():
            subprocess.Popen([str(start_bat)], shell=True)
        elif start_sh.exists():
            subprocess.Popen([str(start_sh)], shell=True)

    @staticmethod
    def _parse_env(path: Path) -> dict:
        """解析.env文件"""
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

    @staticmethod
    def _calc_md5(file_path: str) -> str:
        """计算文件MD5"""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """比较版本号，v1>v2返回1，相等返回0，v1<v2返回-1"""
        def parse(v):
            parts = []
            for p in v.split("."):
                try:
                    parts.append(int(p))
                except ValueError:
                    parts.append(0)
            return parts

        p1, p2 = parse(v1), parse(v2)
        for a, b in zip(p1, p2):
            if a > b:
                return 1
            if a < b:
                return -1
        if len(p1) > len(p2):
            return 1
        if len(p1) < len(p2):
            return -1
        return 0

    def get_status(self) -> dict:
        """获取升级状态信息"""
        return {
            "current_version": self.get_current_version(),
            "root_dir": str(self.root_dir),
            "update_server": self.update_server,
            "app_dir_exists": self.app_dir.exists(),
            "data_dir_exists": self.data_dir.exists(),
            "backup_count": len(list(self.backup_dir.glob("app_backup_*"))) if self.backup_dir.exists() else 0,
        }

    def cleanup_backups(self, keep: int = 2):
        """清理旧备份，只保留最近N个"""
        if not self.backup_dir.exists():
            return
        backups = sorted(self.backup_dir.glob("app_backup_*"), key=lambda p: p.stat().st_mtime)
        for old_backup in backups[:-keep]:
            shutil.rmtree(old_backup, ignore_errors=True)
            logger.info(f"清理旧备份: {old_backup}")


# ===== 便捷函数 =====

def check_for_updates(root_dir: str = None) -> Optional[dict]:
    """检查是否有更新"""
    client = UpgradeClient(root_dir)
    return client.check_update()


def perform_upgrade(zip_path: str, root_dir: str = None, 
                    update_info: dict = None) -> dict:
    """执行升级"""
    client = UpgradeClient(root_dir)
    return client.execute_upgrade(zip_path, update_info)
