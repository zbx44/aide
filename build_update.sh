#!/bin/bash
# ==========================================
#  AIDE 增量更新包构建脚本
#  对比两个版本差异，只打包变更的文件
#
#  用法：
#    ./build_update.sh --from v0.2.0 --to v0.3.0
#    ./build_update.sh --to v0.3.0          # from默认为当前VERSION
#
#  产出：
#    dist/aide-v0.3.0-update.zip
# ==========================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 解析参数
FROM_VERSION=""
TO_VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --from) FROM_VERSION="$2"; shift 2 ;;
        --to)   TO_VERSION="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# 默认from版本为当前VERSION
if [ -z "$FROM_VERSION" ] && [ -f "VERSION" ]; then
    FROM_VERSION=$(cat VERSION | sed 's/^v//')
fi
if [ -z "$TO_VERSION" ]; then
    echo "[错误] 请指定 --to 版本号"
    echo "用法: ./build_update.sh --from v0.2.0 --to v0.3.0"
    exit 1
fi

# 去掉v前缀
FROM_VER="${FROM_VERSION#v}"
TO_VER="${TO_VERSION#v}"

echo "========================================="
echo "  AIDE 增量更新包构建"
echo "  从 v${FROM_VER} → v${TO_VER}"
echo "========================================="
echo ""

# 创建临时构建目录
BUILD_DIR="/tmp/aide-update-v${TO_VER}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "[1/5] 收集应用代码 (app/)..."
# 复制app目录（排除__pycache__、venv、.pyc）
if [ -d "app" ]; then
    rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
        --exclude='.env' --exclude='data' --exclude='static' \
        "app/" "$BUILD_DIR/app/"
    echo "  ✅ app/ 已复制"
else
    echo "  ⚠️ app/ 目录不存在，跳过"
fi

echo "[2/5] 收集配置文件 (config/)..."
if [ -d "config" ]; then
    cp -r config/ "$BUILD_DIR/config/"
    echo "  ✅ config/ 已复制"
fi

echo "[3/5] 收集迁移脚本 (app/backend/migrations/)..."
# 迁移脚本已经在app/里面了，确认存在
if [ -d "$BUILD_DIR/app/backend/migrations" ]; then
    echo "  ✅ migrations/ 已包含"
fi

echo "[4/5] 生成元数据..."

# 生成UPGRADE_INFO.json
cat > "$BUILD_DIR/UPGRADE_INFO.json" << EOF
{
  "version": "${TO_VER}",
  "from_version": "${FROM_VER}",
  "min_upgrade_from": "${FROM_VER}",
  "release_date": "$(date +%Y-%m-%d)",
  "release_notes": [
    "请编辑此文件添加更新说明"
  ],
  "config_updates": {
    "new_keys": [],
    "changed_keys": {}
  }
}
EOF

# 生成升级脚本骨架
cat > "$BUILD_DIR/upgrade_script.py" << 'UPGRADEOF'
#!/usr/bin/env python3
"""AIDE 自动升级脚本 - 由 build_update.sh 生成

此脚本在升级过程中自动执行，用于：
1. 数据库迁移
2. 配置合并
3. 数据格式转换

请根据本次版本变更内容修改此脚本。
"""
import sys
from pathlib import Path


def upgrade(root_dir):
    """执行升级操作"""
    root = Path(root_dir)
    
    # 示例：执行数据库迁移
    # from core.migrations import MigrationRunner
    # runner = MigrationRunner(str(root))
    # result = runner.run_pending()
    # print(f"迁移结果: {result}")
    
    print("升级脚本执行完成")


if __name__ == "__main__":
    root = "."
    if len(sys.argv) > 2 and sys.argv[1] == "--root":
        root = sys.argv[2]
    upgrade(root)
UPGRADEOF

echo "[5/5] 打包..."

# 创建输出目录
DIST_DIR="$SCRIPT_DIR/dist"
mkdir -p "$DIST_DIR"

OUTPUT_FILE="$DIST_DIR/aide-v${TO_VER}-update.zip"

cd "$BUILD_DIR"
zip -r "$OUTPUT_FILE" . -x "*.pyc" -q
cd "$SCRIPT_DIR"

# 计算MD5和大小
if command -v md5sum &>/dev/null; then
    CHECKSUM=$(md5sum "$OUTPUT_FILE" | awk '{print $1}')
elif command -v md5 &>/dev/null; then
    CHECKSUM=$(md5 -q "$OUTPUT_FILE")
else
    CHECKSUM=""
fi

FILESIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null || echo "0")

# 更新manifest.json
MANIFEST="$DIST_DIR/manifest.json"
if [ -f "$MANIFEST" ]; then
    # 读取现有manifest，追加新版本
    python3 -c "
import json
with open('$MANIFEST', 'r') as f:
    m = json.load(f)
m['latest_version'] = '${TO_VER}'
m['updates'].append({
    'version': '${TO_VER}',
    'file': 'v${TO_VER}/aide-v${TO_VER}-update.zip',
    'size': $FILESIZE,
    'checksum': '$CHECKSUM',
    'release_date': '$(date +%Y-%m-%d)',
    'release_notes': ['请编辑 manifest.json 添加更新说明'],
    'config_updates': {'new_keys': [], 'changed_keys': {}}
})
with open('$MANIFEST', 'w') as f:
    json.dump(m, f, ensure_ascii=False, indent=2)
"
else
    cat > "$MANIFEST" << EOF
{
  "latest_version": "${TO_VER}",
  "min_upgrade_from": "${FROM_VER}",
  "updates": [
    {
      "version": "${TO_VER}",
      "file": "v${TO_VER}/aide-v${TO_VER}-update.zip",
      "size": ${FILESIZE},
      "checksum": "${CHECKSUM}",
      "release_date": "$(date +%Y-%m-%d)",
      "release_notes": [
        "请编辑 manifest.json 添加更新说明"
      ],
      "config_updates": {
        "new_keys": [],
        "changed_keys": {}
      }
    }
  ]
}
EOF
fi

# 清理临时目录
rm -rf "$BUILD_DIR"

echo ""
echo "========================================="
echo "  更新包构建完成！"
echo "========================================="
echo ""
echo "  文件: $OUTPUT_FILE"
echo "  大小: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo "  MD5:  $CHECKSUM"
echo ""
echo "  manifest.json: $MANIFEST"
echo ""
echo "  ⚠️ 请编辑以下文件："
echo "  1. $OUTPUT_FILE 内的 UPGRADE_INFO.json → 填写更新说明"
echo "  2. $OUTPUT_FILE 内的 upgrade_script.py → 编写迁移逻辑"
echo "  3. $MANIFEST → 填写 release_notes"
echo ""
echo "  部署：将 dist/ 目录上传到升级服务器即可"
echo ""
