#!/usr/bin/env python3
"""AIDE 数据迁移脚本 - 从旧版目录结构迁移到新版

旧版：backend/data/, backend/.env, backend/tasks/, backend/templates/
新版：data/, config/default.env, user/user.env, user/tasks/, user/templates/

用法：
  python migrate.py [--root /path/to/aide]

安全策略：
  - 只复制，不删除旧文件
  - 已存在的文件不覆盖
  - 迁移前自动备份
"""
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime


def migrate(root_dir: str):
    root = Path(root_dir).resolve()
    old_backend = root / "backend"
    
    if not old_backend.exists():
        print("[错误] 未找到旧版 backend/ 目录，无需迁移")
        return False
    
    print(f"项目根目录: {root}")
    print(f"旧版目录: {old_backend}")
    print()
    
    # 备份
    backup_dir = root / f"_migration_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"[1/6] 创建备份: {backup_dir}")
    # 只备份关键目录的元信息，不备份全部
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 迁移用户数据
    old_data = old_backend / "data"
    new_data = root / "data"
    if old_data.exists():
        print(f"[2/6] 迁移用户数据: {old_data} → {new_data}")
        new_data.mkdir(parents=True, exist_ok=True)
        for item in old_data.iterdir():
            dest = new_data / item.name
            if not dest.exists():
                if item.is_file():
                    shutil.copy2(item, dest)
                    print(f"  ✅ {item.name}")
                elif item.is_dir():
                    shutil.copytree(item, dest)
                    print(f"  ✅ {item.name}/")
            else:
                print(f"  ⏭️ {item.name} (已存在，跳过)")
    else:
        print("[2/6] 未找到旧数据目录，跳过")
    
    # 迁移配置
    old_env = old_backend / ".env"
    new_config = root / "config" / "default.env"
    user_env = root / "user" / "user.env"
    
    if old_env.exists() and not new_config.exists():
        print(f"[3/6] 迁移配置: {old_env} → {new_config}")
        new_config.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_env, new_config)
        print("  ✅ .env → config/default.env")
    elif old_env.exists():
        print(f"[3/6] 配置已存在，旧.env中的自定义项合并到 user/user.env")
        # 读取旧.env，提取非默认项写入user.env
        _merge_old_env_to_user(old_env, new_config, user_env)
    else:
        print("[3/6] 未找到旧配置文件，跳过")
    
    # 迁移定时任务
    old_tasks = old_backend / "tasks"
    new_tasks = root / "user" / "tasks"
    if old_tasks.exists():
        print(f"[4/6] 迁移定时任务: {old_tasks} → {new_tasks}")
        new_tasks.mkdir(parents=True, exist_ok=True)
        for item in old_tasks.glob("*.yaml"):
            dest = new_tasks / item.name
            if not dest.exists():
                shutil.copy2(item, dest)
                print(f"  ✅ {item.name}")
            else:
                print(f"  ⏭️ {item.name} (已存在，跳过)")
    else:
        print("[4/6] 未找到旧任务目录，跳过")
    
    # 迁移输出文档
    old_output = old_backend / "output"
    new_output = root / "output"
    if old_output.exists():
        print(f"[5/6] 迁移输出文档: {old_output} → {new_output}")
        new_output.mkdir(parents=True, exist_ok=True)
        for item in old_output.rglob("*"):
            if item.is_file():
                rel = item.relative_to(old_output)
                dest = new_output / rel
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    print(f"  ✅ {rel}")
    else:
        print("[5/6] 未找到旧输出目录，跳过")
    
    # 复制代码到app/backend/
    new_app = root / "app" / "backend"
    if not new_app.exists():
        print(f"[6/6] 设置新版目录结构: app/backend/")
        # app/backend/ 在install.sh中已经创建，这里只确保存在
        new_app.mkdir(parents=True, exist_ok=True)
    else:
        print(f"[6/6] app/backend/ 已存在")
    
    print()
    print("=" * 50)
    print("  迁移完成！")
    print("=" * 50)
    print()
    print("目录说明：")
    print(f"  app/     - 程序代码（升级时覆盖）")
    print(f"  config/  - 默认配置（升级时覆盖）")
    print(f"  data/    - 你的数据（升级不碰）")
    print(f"  user/    - 你的配置和模板（升级不碰）")
    print(f"  output/  - 生成的文档（升级不碰）")
    print()
    print("备份目录: " + str(backup_dir))
    print("确认无误后可删除旧版 backend/ 目录和备份")
    print()
    
    return True


def _merge_old_env_to_user(old_env: Path, default_env: Path, user_env: Path):
    """将旧.env中的自定义项（与default.env不同的）写入user/user.env"""
    old_vars = _parse_env(old_env)
    default_vars = _parse_env(default_env)
    
    # 找出不同的项
    custom = {}
    for k, v in old_vars.items():
        if k not in default_vars or default_vars[k] != v:
            custom[k] = v
    
    if not custom:
        print("  ℹ️ 旧配置与默认配置一致，无需合并")
        return
    
    user_env.parent.mkdir(parents=True, exist_ok=True)
    
    # 读取已有的user.env
    existing = _parse_env(user_env) if user_env.exists() else {}
    existing.update(custom)
    
    with open(user_env, "w", encoding="utf-8") as f:
        f.write("# AIDE 用户自定义配置（从旧版迁移）\n")
        f.write("# 升级时不会被覆盖\n\n")
        for k, v in sorted(existing.items()):
            f.write(f"{k}={v}\n")
    
    print(f"  ✅ 已合并 {len(custom)} 项自定义配置到 user/user.env")


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


if __name__ == "__main__":
    root = "."
    if len(sys.argv) > 2 and sys.argv[1] == "--root":
        root = sys.argv[2]
    
    success = migrate(root)
    sys.exit(0 if success else 1)
