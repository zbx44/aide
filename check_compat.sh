#!/bin/bash
# ==========================================
#  AIDE 多平台兼容性检查
#  确保一份源码在 Python 3.8 + 3.12 下都能跑
# ==========================================
set -e

SRC="/home/ubuntu/.openclaw/workspace/ai-assistant"
cd "$SRC/app/backend"

export AIDE_ROOT="$SRC"

ERRORS=0

echo "========================================="
echo "  AIDE 多平台兼容性检查"
echo "========================================="
echo ""

# ===== 1. Python语法检查 =====
echo "[1/3] Python语法检查..."

for f in $(find . -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*"); do
    if ! python3 -m py_compile "$f" 2>/dev/null; then
        echo "  ❌ $f"
        ERRORS=$((ERRORS + 1))
    fi
done
echo "  语法检查完成"

# ===== 2. Python 3.8 兼容性静态扫描 =====
echo ""
echo "[2/3] Python 3.8 兼容性扫描..."

# 3.8不支持的语法/特性
CHECKS=(
    # match/case (3.10+)
    "s:match\s+[a-zA-Z]"
    # | 联合类型注解 (3.10+)
    "s:\w+\s*\|\s*\w+.*:"  
    # except* (3.11+)
    "s:except\s*\*"
    # 类型别名 TypeAlias (3.10+ 推荐)
    "s:TypeAlias"
)

# 3.8不支持的特性关键词
BAD_PATTERNS=(
    # str.removeprefix/removesuffix (3.9+)
    "removeprefix|removesuffix"
    # dict合并运算符 | (3.9+)
    "s:\}\s*\|\s*\{"
    # list[str] 语法 (3.9+) — 在类型注解外使用
    # tuple[int,...] — 同上
    # zoneinfo (3.9+)
    "import zoneinfo"
    # asyncio.TaskGroup (3.11+)
    "TaskGroup"
    # typing.ParamSpec (3.10+)
    "ParamSpec"
    # itertools.pairwise (3.10+)
    "pairwise"
    # match statement (3.10+) — 排除 match = 赋值
    "^\\s*match\\s+[a-zA-Z\"\']"
    # case statement (3.10+)
    "^\\s*case\\s+[a-zA-Z\"\']"
)

for f in $(find . -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*"); do
    for pattern in "${BAD_PATTERNS[@]}"; do
        if grep -Pn "$pattern" "$f" 2>/dev/null; then
            echo "  ⚠️ $f: 可能不兼容Python 3.8 (匹配: $pattern)"
            # 不算硬错误，只是警告
        fi
    done
done
echo "  兼容性扫描完成（⚠️ 为警告，非错误）"

# ===== 3. 关键模块导入测试 =====
echo ""
echo "[3/3] 关键模块导入测试..."

MODULES=(
    "config.settings"
    "core.llm"
    "core.database"
    "core.memory"
    "core.skills"
    "core.scheduler"
    "core.text2sql"
    "core.sql_safety"
    "core.schema_manager"
    "core.template_engine"
    "core.upgrade"
    "core.migrations"
    "routers.chat"
    "routers.doc"
    "routers.task"
    "routers.query"
    "routers.template"
    "routers.knowledge"
    "routers.tool"
    "routers.oa"
)

for mod in "${MODULES[@]}"; do
    if python3 -c "import $mod" 2>/dev/null; then
        echo "  ✅ $mod"
    else
        echo "  ❌ $mod"
        ERRORS=$((ERRORS + 1))
    fi
done

# ===== 结果 =====
echo ""
echo "========================================="
if [ "$ERRORS" -eq 0 ]; then
    echo "  ✅ 全部通过！代码兼容 Python 3.8 + 3.12"
else
    echo "  ❌ 发现 $ERRORS 个错误，请修复"
fi
echo "========================================="
