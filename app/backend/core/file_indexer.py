from __future__ import annotations
"""本地文件检索系统 - 向量语义检索 + FTS5全文检索 v2.0

升级要点：
1. 同时索引文件（按文件名）和目录（按目录名）
2. 名称清洗：去除冗余符号、标准化
3. 语义增强：结合父目录/子特征生成增强语义文本
4. TF-IDF向量 + 余弦相似度语义检索（纯Python，零外部依赖）
5. 首次建库后台进行，不阻塞用户
6. 增量更新：只重新索引变更的文件/目录
7. 筛选：按类型（文件/目录）、按扩展名
8. 结果格式化：图标 + 名称 + 路径 + 相似度 + 修改时间
"""
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from collections import Counter
from datetime import datetime
from typing import List, Optional, Tuple

from config.settings import settings

logger = logging.getLogger(__name__)

# 忽略的目录名
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".idea", ".vscode", "dist", "build", ".next", ".nuxt",
    "vendor", "target", ".tox", ".mypy_cache", ".pytest_cache",
    "site-packages", "Recycle", "$RECYCLE.BIN", "System Volume Information",
    "Windows", "ProgramData",
}

SKIP_DIR_PATTERNS = re.compile(
    r'(\$RECYCLE\.BIN|System Volume Information|\.git[/\\]|node_modules[/\\]|'
    r'__pycache__[/\\]|\.venv[/\\]|site-packages[/\\]|AppData[/\\]Local[/\\]Temp)',
    re.IGNORECASE
)

INDEXABLE_EXTENSIONS = {
    ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pdf",
    ".txt", ".md", ".rst", ".log", ".csv", ".tsv",
    ".json", ".yaml", ".yml", ".xml", ".ini", ".cfg", ".conf", ".toml",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php", ".cs", ".swift", ".kt", ".scala",
    ".sh", ".bat", ".ps1", ".sql", ".r", ".m", ".lua",
    ".html", ".htm", ".css", ".scss", ".less",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico",
    ".mp3", ".mp4", ".wav", ".avi", ".mkv", ".flac", ".wmv", ".mov",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".dwg", ".dxf", ".step", ".stp", ".igs",
    ".rtf", ".odt", ".ods", ".odp",
}

NOISE_PATTERNS = [
    re.compile(r'[_\-\s]*v?\d+(\.\d+)*$'),
    re.compile(r'[_\-\s]*(final|draft|copy|backup|bak|old|new|tmp|temp)$', re.IGNORECASE),
    re.compile(r'[【】\[\]{}（）()《》<>]'),
    re.compile(r'_{2,}'),
    re.compile(r'~+'),
    re.compile(r'^[\s_\-.#\d]+'),
]

CN_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "那",
    "他", "她", "它", "们", "什么", "怎么", "哪", "几", "多",
    "少", "些", "个", "下", "里", "中", "后", "前", "时", "年",
    "月", "日", "号", "第", "等", "之", "与", "及", "或", "但",
}

EN_STOPWORDS = {
    "the", "is", "at", "of", "and", "or", "in", "to", "for",
    "a", "an", "it", "this", "that", "with", "on", "by",
    "from", "as", "be", "was", "are", "been", "have", "has",
    "not", "but", "if", "so", "no", "all", "can", "will",
    "do", "did", "does", "would", "could", "should",
}


class TFIDFEncoder:
    """纯Python TF-IDF向量编码器，零外部依赖"""

    def __init__(self):
        self.vocab: dict = {}
        self.idf: list = []
        self._built = False
        self._doc_count = 0

    def tokenize(self, text: str) -> list:
        tokens = []
        for w in re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text.lower()):
            if w not in EN_STOPWORDS and len(w) >= 2:
                tokens.append(w)
        cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
        for i in range(len(cn_chars) - 1):
            bigram = cn_chars[i] + cn_chars[i + 1]
            if bigram not in CN_STOPWORDS:
                tokens.append(bigram)
        if 0 < len(cn_chars) <= 3:
            tokens.append("".join(cn_chars))
        return tokens

    def build(self, documents: list) -> None:
        self._doc_count = len(documents)
        if self._doc_count == 0:
            return
        doc_freq = Counter()
        for doc in documents:
            for t in set(self.tokenize(doc)):
                doc_freq[t] += 1
        min_df = max(1, self._doc_count // 100)
        self.vocab = {}
        self.idf = []
        idx = 0
        for token, df in doc_freq.items():
            if df >= min_df and df / self._doc_count <= 0.9:
                self.vocab[token] = idx
                self.idf.append(math.log(self._doc_count / (df + 1)) + 1)
                idx += 1
        if len(self.vocab) < 50 and self._doc_count > 0:
            self.vocab = {}
            self.idf = []
            idx = 0
            for token, df in doc_freq.items():
                self.vocab[token] = idx
                self.idf.append(math.log(self._doc_count / (df + 1)) + 1)
                idx += 1
        self._built = True
        logger.info(f"TF-IDF词汇表: {len(self.vocab)}词, {self._doc_count}文档")

    def encode(self, text: str) -> list:
        if not self._built:
            return []
        tokens = self.tokenize(text)
        tf = Counter(tokens)
        total = len(tokens) or 1
        sparse = {}
        for token, count in tf.items():
            if token in self.vocab:
                idx = self.vocab[token]
                sparse[idx] = round(count / total * self.idf[idx], 6)
        result = []
        for idx in sorted(sparse.keys()):
            result.append(float(idx))
            result.append(sparse[idx])
        return result

    @staticmethod
    def cosine_similarity(vec_a: list, vec_b: list) -> float:
        def to_dict(v):
            d = {}
            for i in range(0, len(v), 2):
                d[int(v[i])] = v[i + 1]
            return d
        a, b = to_dict(vec_a), to_dict(vec_b)
        dot = sum(a[k] * b.get(k, 0) for k in a)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def to_state(self) -> dict:
        return {"vocab": self.vocab, "idf": self.idf, "doc_count": self._doc_count}

    def from_state(self, state: dict) -> None:
        self.vocab = state.get("vocab", {})
        self.idf = state.get("idf", [])
        self._doc_count = state.get("doc_count", 0)
        self._built = bool(self.vocab)


class IndexProgress:
    """线程安全的索引进度追踪器"""

    def __init__(self):
        self._lock = threading.Lock()
        self._reset_unlocked()

    def _reset_unlocked(self):
        self.is_indexing = False
        self.phase = ""                # 当前阶段描述
        self.phase_index = 0           # 阶段序号 1/2/3
        self.phase_total = 3           # 总阶段数
        self.files_found = 0           # 已发现的文件数
        self.dirs_found = 0            # 已发现的目录数
        self.entries_indexed = 0        # 已索引条目数
        self.entries_total = 0          # 预估总条目数
        self.scan_dirs_done = 0         # 已扫描的配置目录数
        self.scan_dirs_total = 0        # 配置目录总数
        self.start_time = None         # 开始时间
        self.eta_seconds = None         # 预估剩余秒数
        self.error = None              # 错误信息

    def reset(self):
        with self._lock:
            self._reset_unlocked()

    def start(self, total_dirs: int = 0):
        with self._lock:
            self._reset_unlocked()
            self.is_indexing = True
            self.start_time = time.time()
            self.scan_dirs_total = total_dirs

    def finish(self, error: str = None):
        with self._lock:
            self.is_indexing = False
            self.error = error
            if not error:
                self.phase = "完成"
                self.phase_index = self.phase_total

    def update_phase(self, phase: str, phase_index: int = None):
        with self._lock:
            self.phase = phase
            if phase_index is not None:
                self.phase_index = phase_index
            self._update_eta()

    def add_files(self, count: int):
        with self._lock:
            self.files_found += count
            self._update_eta()

    def add_dirs(self, count: int):
        with self._lock:
            self.dirs_found += count
            self._update_eta()

    def set_scan_dir_done(self, count: int = 1):
        with self._lock:
            self.scan_dirs_done += count
            self._update_eta()

    def set_entries_total(self, total: int):
        with self._lock:
            self.entries_total = total
            self._update_eta()

    def add_entries_indexed(self, count: int):
        with self._lock:
            self.entries_indexed += count
            self._update_eta()

    def _update_eta(self):
        """内部估算剩余时间（调用者需已持有锁）"""
        if not self.start_time or not self.is_indexing:
            return
        elapsed = time.time() - self.start_time
        if elapsed < 1:
            return

        # 根据阶段计算进度
        if self.phase_index == 1 and self.scan_dirs_total > 0:
            # 阶段1: 按扫描目录进度
            progress = self.scan_dirs_done / self.scan_dirs_total
        elif self.phase_index == 2:
            # 阶段2: 构建词汇表，极快，固定80%
            progress = 0.8
        elif self.phase_index == 3 and self.entries_total > 0:
            # 阶段3: 按编码进度
            progress = 0.8 + 0.2 * (self.entries_indexed / self.entries_total)
        else:
            progress = self.phase_index / self.phase_total

        progress = max(progress, 0.01)
        if progress < 1.0:
            self.eta_seconds = int(elapsed / progress * (1 - progress))
        else:
            self.eta_seconds = 0

    def get_snapshot(self) -> dict:
        """获取当前进度快照"""
        with self._lock:
            elapsed = 0
            if self.start_time:
                elapsed = int(time.time() - self.start_time)

            # 计算总进度百分比
            if self.phase_index == 1 and self.scan_dirs_total > 0:
                pct = round(self.scan_dirs_done / self.scan_dirs_total * 33, 1)
            elif self.phase_index == 2:
                pct = 50.0
            elif self.phase_index == 3 and self.entries_total > 0:
                pct = round(50 + self.entries_indexed / self.entries_total * 50, 1)
            elif self.phase_index >= 3:
                pct = 100.0
            else:
                pct = round(self.phase_index / self.phase_total * 33, 1)

            # 进度条文本
            bar_len = 20
            filled = int(bar_len * pct / 100)
            bar = "█" * filled + "░" * (bar_len - filled)

            return {
                "is_indexing": self.is_indexing,
                "phase": self.phase,
                "phase_index": self.phase_index,
                "phase_total": self.phase_total,
                "progress_pct": pct,
                "progress_bar": f"[{bar}] {pct}%",
                "files_found": self.files_found,
                "dirs_found": self.dirs_found,
                "entries_indexed": self.entries_indexed,
                "entries_total": self.entries_total,
                "scan_dirs_done": self.scan_dirs_done,
                "scan_dirs_total": self.scan_dirs_total,
                "elapsed_seconds": elapsed,
                "eta_seconds": self.eta_seconds,
                "elapsed_human": self._fmt_duration(elapsed),
                "eta_human": self._fmt_duration(self.eta_seconds) if self.eta_seconds else "计算中...",
                "error": self.error,
            }

    def get_formatted(self) -> str:
        """获取格式化的进度文本，适合直接展示给用户"""
        s = self.get_snapshot()
        if not s["is_indexing"]:
            if s["error"]:
                return f"❌ 索引失败: {s['error']}"
            return "✅ 索引已完成，可以开始检索了"

        lines = [
            f"📂 正在构建文件索引库...",
            f"{s['progress_bar']}",
            f"📌 {s['phase']}",
            f"📄 已发现 {s['files_found']} 个文件 | 📁 {s['dirs_found']} 个文件夹",
        ]
        if s["entries_total"] > 0 and s["phase_index"] >= 3:
            lines.append(f"🔢 向量计算: {s['entries_indexed']}/{s['entries_total']}")
        if s["eta_human"] and s["eta_human"] != "计算中...":
            lines.append(f"⏱ 预计还需 {s['eta_human']}")
        lines.append(f"⏰ 已用时 {s['elapsed_human']}")
        return "\n".join(lines)

    @staticmethod
    def _fmt_duration(seconds) -> str:
        if seconds is None:
            return "计算中..."
        s = int(seconds)
        if s < 60:
            return f"{s}秒"
        elif s < 3600:
            m, sec = divmod(s, 60)
            return f"{m}分{sec}秒"
        else:
            h, m = divmod(s // 60, 60)
            return f"{h}小时{m}分"


class LocalFileIndexer:
    """本地文件索引与语义检索 v2.0"""

    def __init__(self):
        self.db_path = settings.DATA_DIR / "file_index_v2.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.encoder = TFIDFEncoder()
        self.progress = IndexProgress()
        self._init_db()
        self._load_encoder()
        self.default_roots = self._detect_default_roots()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS indexed_dirs (
                    id TEXT PRIMARY KEY,
                    dir_path TEXT NOT NULL,
                    recursive INTEGER DEFAULT 1,
                    last_scanned TEXT,
                    file_count INTEGER DEFAULT 0,
                    dir_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_entries (
                    id TEXT PRIMARY KEY,
                    dir_id TEXT NOT NULL,
                    entry_type TEXT NOT NULL DEFAULT 'file',
                    path TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    clean_name TEXT NOT NULL DEFAULT '',
                    enhanced_text TEXT NOT NULL DEFAULT '',
                    ext TEXT NOT NULL DEFAULT '',
                    parent_dir_name TEXT NOT NULL DEFAULT '',
                    size INTEGER DEFAULT 0,
                    created_time TEXT,
                    modified_time TEXT,
                    vector TEXT DEFAULT '[]',
                    indexed_at TEXT NOT NULL,
                    FOREIGN KEY (dir_id) REFERENCES indexed_dirs(id)
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS file_entries_fts
                USING fts5(name, clean_name, enhanced_text, parent_dir_name,
                           content='file_entries', content_rowid='rowid')
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_ai AFTER INSERT ON file_entries BEGIN
                    INSERT INTO file_entries_fts(rowid, name, clean_name, enhanced_text, parent_dir_name)
                    VALUES (new.rowid, new.name, new.clean_name, new.enhanced_text, new.parent_dir_name);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_ad AFTER DELETE ON file_entries BEGIN
                    INSERT INTO file_entries_fts(file_entries_fts, rowid, name, clean_name, enhanced_text, parent_dir_name)
                    VALUES ('delete', old.rowid, old.name, old.clean_name, old.enhanced_text, old.parent_dir_name);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_au AFTER UPDATE ON file_entries BEGIN
                    INSERT INTO file_entries_fts(file_entries_fts, rowid, name, clean_name, enhanced_text, parent_dir_name)
                    VALUES ('delete', old.rowid, old.name, old.clean_name, old.enhanced_text, old.parent_dir_name);
                    INSERT INTO file_entries_fts(rowid, name, clean_name, enhanced_text, parent_dir_name)
                    VALUES (new.rowid, new.name, new.clean_name, new.enhanced_text, new.parent_dir_name);
                END
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS encoder_state (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _load_encoder(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT state_json FROM encoder_state WHERE id = 1").fetchone()
                if row:
                    self.encoder.from_state(json.loads(row[0]))
        except Exception as e:
            logger.warning(f"加载编码器失败: {e}")

    def _save_encoder(self):
        try:
            now = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO encoder_state (id, state_json, updated_at) VALUES (1, ?, ?)",
                    (json.dumps(self.encoder.to_state(), ensure_ascii=False), now)
                )
        except Exception as e:
            logger.error(f"保存编码器失败: {e}")

    def _detect_default_roots(self) -> list:
        roots = []
        if os.name == 'nt':
            for letter in 'CDEFGH':
                drive = f"{letter}:\\"
                if os.path.isdir(drive):
                    roots.append(drive)
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if os.path.isdir(desktop):
                roots.append(desktop)
        else:
            home = os.path.expanduser("~")
            if os.path.isdir(home):
                roots.append(home)
        return roots

    # ===== 名称清洗 =====

    @staticmethod
    def clean_name(name: str) -> str:
        """清洗: "Q4销售报告_final_v3.xlsx" → "q4销售报告" """
        base = os.path.splitext(name)[0] if '.' in name else name
        for pat in NOISE_PATTERNS:
            base = pat.sub('', base)
        base = re.sub(r'[_\-\s]{2,}', ' ', base).strip(' _-.')
        return ''.join(c.lower() if c.isascii() and c.isalpha() else c for c in base).strip()

    # ===== 语义增强 =====

    @staticmethod
    def enhance_text(entry_type: str, clean_name: str, parent_dir_name: str,
                     ext: str = "", child_names: list = None) -> str:
        TYPE_MAP = {
            ".docx": "Word文档", ".doc": "Word文档",
            ".xlsx": "Excel表格", ".xls": "Excel表格",
            ".pptx": "PPT演示文稿", ".ppt": "PPT演示文稿",
            ".pdf": "PDF文档", ".txt": "文本文件", ".md": "Markdown文档",
            ".csv": "CSV数据表", ".json": "JSON数据文件",
            ".py": "Python源代码", ".js": "JavaScript源代码",
            ".html": "HTML网页", ".css": "CSS样式表",
            ".png": "PNG图片", ".jpg": "JPEG图片", ".jpeg": "JPEG图片",
            ".mp4": "MP4视频", ".mp3": "MP3音频",
            ".zip": "ZIP压缩包", ".rar": "RAR压缩包",
            ".dwg": "AutoCAD图纸", ".dxf": "DXF图纸",
        }
        if entry_type == 'dir':
            parts = []
            if parent_dir_name:
                parts.append(f"{parent_dir_name}下的")
            if child_names:
                child_desc = "、".join(child_names[:3])
                parts.append(f"包含{child_desc}的")
            parts.append(f"文件夹{clean_name}")
            text = "".join(parts)
        else:
            type_desc = TYPE_MAP.get(ext, f"{ext.replace('.', '').upper()}文件" if ext else "文件")
            prefix = f"{parent_dir_name}中的" if parent_dir_name else ""
            text = f"{prefix}{type_desc}{clean_name}"
        if clean_name not in text:
            text = f"{text}（{clean_name}）"
        return text

    # ===== 目录管理 =====

    def add_dir(self, dir_path: str, recursive: bool = True) -> dict:
        dir_path = os.path.abspath(dir_path)
        if not os.path.isdir(dir_path):
            return {"error": f"目录不存在: {dir_path}"}
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM indexed_dirs WHERE dir_path = ?", (dir_path,)
            ).fetchone()
            if existing:
                return {"status": "exists", "dir_id": existing[0], "dir_path": dir_path}
            dir_id = str(uuid.uuid4())[:8]
            conn.execute(
                "INSERT INTO indexed_dirs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (dir_id, dir_path, 1 if recursive else 0, None, 0, 0, now),
            )
        return {"status": "added", "dir_id": dir_id, "dir_path": dir_path}

    def remove_dir(self, dir_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            dir_info = conn.execute(
                "SELECT dir_path FROM indexed_dirs WHERE id = ?", (dir_id,)
            ).fetchone()
            if not dir_info:
                return {"error": f"目录ID不存在: {dir_id}"}
            conn.execute("DELETE FROM file_entries WHERE dir_id = ?", (dir_id,))
            conn.execute("DELETE FROM indexed_dirs WHERE id = ?", (dir_id,))
        return {"status": "removed", "dir_path": dir_info[0]}

    def list_dirs(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT id, dir_path, recursive, last_scanned,
                       file_count, dir_count, created_at
                FROM indexed_dirs
            """).fetchall()
        return [
            {
                "dir_id": r[0], "dir_path": r[1], "recursive": bool(r[2]),
                "last_scanned": r[3], "file_count": r[4], "dir_count": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]

    # ===== 索引构建 =====

    def scan_background(self, dir_id: str = None) -> dict:
        """后台扫描建库（非阻塞）"""
        if self.progress.is_indexing:
            snap = self.progress.get_snapshot()
            return {
                "status": "already_indexing",
                "message": "索引正在进行中",
                "progress": snap,
                "formatted": self.progress.get_formatted(),
            }

        def _run():
            try:
                self.scan(dir_id)
            except Exception as e:
                logger.error(f"后台索引失败: {e}")
                self.progress.finish(error=str(e))

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        snap = self.progress.get_snapshot()
        return {
            "status": "indexing_started",
            "message": "正在后台构建文件索引，您可以继续其他操作",
            "progress": snap,
            "formatted": self.progress.get_formatted(),
        }

    def scan(self, dir_id: str = None) -> dict:
        """同步扫描索引"""
        with sqlite3.connect(self.db_path) as conn:
            if dir_id:
                dirs = conn.execute(
                    "SELECT id, dir_path, recursive FROM indexed_dirs WHERE id = ?",
                    (dir_id,),
                ).fetchall()
            else:
                dirs = conn.execute(
                    "SELECT id, dir_path, recursive FROM indexed_dirs"
                ).fetchall()

        if not dirs:
            for root in self.default_roots:
                try:
                    self.add_dir(root)
                except Exception:
                    pass
            with sqlite3.connect(self.db_path) as conn:
                dirs = conn.execute(
                    "SELECT id, dir_path, recursive FROM indexed_dirs"
                ).fetchall()
            if not dirs:
                self.progress.finish(error="没有可扫描的索引目录，请先添加目录")
                return {"error": "没有可扫描的索引目录，请先添加目录"}

        # 初始化进度追踪
        self.progress.start(total_dirs=len(dirs))

        total_files = 0
        total_dirs = 0
        all_enhanced = []
        all_entries = []

        # 阶段1: 扫描文件系统
        self.progress.update_phase("阶段1/3: 扫描文件系统...", phase_index=1)
        for did, dir_path, recursive in dirs:
            f_count, d_count, entries = self._scan_dir(did, dir_path, bool(recursive))
            total_files += f_count
            total_dirs += d_count
            all_entries.extend(entries)
            self.progress.set_scan_dir_done()

        self._batch_write_entries(all_entries)
        all_enhanced.extend(e['enhanced_text'] for e in all_entries)

        # 阶段2: 构建TF-IDF
        self.progress.update_phase(
            f"阶段2/3: 构建语义向量 ({len(all_enhanced)}条目)...",
            phase_index=2,
        )
        self.encoder.build(all_enhanced)
        self._save_encoder()

        # 阶段3: 编码所有条目
        self.progress.set_entries_total(len(all_enhanced))
        self.progress.update_phase("阶段3/3: 计算向量并存储...", phase_index=3)
        self._encode_all_entries()

        # 更新目录统计
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            for did, _, _ in dirs:
                fc = conn.execute(
                    "SELECT COUNT(*) FROM file_entries WHERE dir_id=? AND entry_type='file'",
                    (did,)
                ).fetchone()[0]
                dc = conn.execute(
                    "SELECT COUNT(*) FROM file_entries WHERE dir_id=? AND entry_type='dir'",
                    (did,)
                ).fetchone()[0]
                conn.execute(
                    "UPDATE indexed_dirs SET last_scanned=?, file_count=?, dir_count=? WHERE id=?",
                    (now, fc, dc, did),
                )

        self.progress.finish()
        return {
            "status": "completed",
            "total_files": total_files,
            "total_dirs": total_dirs,
            "vocab_size": len(self.encoder.vocab),
            "formatted": self.progress.get_formatted(),
        }

    def _scan_dir(self, dir_id: str, dir_path: str, recursive: bool) -> tuple:
        """扫描单个目录，收集文件和子目录"""
        file_count = 0
        dir_count = 0
        entries = []
        now = datetime.now().isoformat()
        dir_info_map = {}

        try:
            for root, dirs, files in os.walk(dir_path):
                dirs[:] = [
                    d for d in dirs
                    if d not in SKIP_DIRS
                    and not d.startswith(".")
                    and not SKIP_DIR_PATTERNS.search(os.path.join(root, d))
                ]
                root_name = os.path.basename(root) or root
                parent_name = os.path.basename(os.path.dirname(root)) or ""
                child_file_names = []
                child_dir_names = []

                for d in dirs:
                    child_dir_names.append(d)
                    dpath = os.path.join(root, d)
                    dir_info_map[dpath] = {
                        'name': d, 'parent_name': root_name,
                        'children_files': [], 'children_dirs': [],
                    }

                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in INDEXABLE_EXTENSIONS:
                        continue
                    child_file_names.append(self.clean_name(f))
                    fpath = os.path.join(root, f)
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()
                        ctime = datetime.fromtimestamp(os.path.getctime(fpath)).isoformat()
                        fsize = os.path.getsize(fpath)
                    except OSError:
                        continue
                    clean = self.clean_name(f)
                    enhanced = self.enhance_text('file', clean, root_name, ext)
                    entries.append({
                        'id': str(uuid.uuid4())[:8], 'dir_id': dir_id,
                        'entry_type': 'file', 'path': fpath, 'name': f,
                        'clean_name': clean, 'enhanced_text': enhanced,
                        'ext': ext, 'parent_dir_name': root_name,
                        'size': fsize, 'created_time': ctime,
                        'modified_time': mtime, 'indexed_at': now,
                    })
                    file_count += 1
                    # 每发现100个文件更新一次进度
                    if file_count % 100 == 0:
                        self.progress.add_files(0)  # 触发ETA重算
                        self.progress.update_phase(
                            f"阶段1/3: 扫描文件系统... (已发现 {self.progress.files_found + file_count} 文件)",
                        )

                for d in dirs:
                    dpath = os.path.join(root, d)
                    if dpath in dir_info_map:
                        dir_info_map[dpath]['children_files'] = child_file_names[:5]
                        dir_info_map[dpath]['children_dirs'] = child_dir_names

                if not recursive:
                    break

        except Exception as e:
            logger.error(f"扫描目录失败 {dir_path}: {e}")
            return 0, 0, []

        # 更新进度中的文件/目录发现数
        self.progress.add_files(file_count)
        self.progress.add_dirs(len(dir_info_map))

        for dpath, info in dir_info_map.items():
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(dpath)).isoformat()
                ctime = datetime.fromtimestamp(os.path.getctime(dpath)).isoformat()
            except OSError:
                continue
            clean = self.clean_name(info['name'])
            child_names = info['children_files'] + info['children_dirs']
            enhanced = self.enhance_text('dir', clean, info['parent_name'], child_names=child_names)
            entries.append({
                'id': str(uuid.uuid4())[:8], 'dir_id': dir_id,
                'entry_type': 'dir', 'path': dpath, 'name': info['name'],
                'clean_name': clean, 'enhanced_text': enhanced,
                'ext': '', 'parent_dir_name': info['parent_name'],
                'size': 0, 'created_time': ctime,
                'modified_time': mtime, 'indexed_at': now,
            })
            dir_count += 1

        return file_count, dir_count, entries

    def _batch_write_entries(self, entries: list):
        if not entries:
            return
        with sqlite3.connect(self.db_path) as conn:
            dir_ids = set(e['dir_id'] for e in entries)
            for did in dir_ids:
                conn.execute("DELETE FROM file_entries WHERE dir_id = ?", (did,))
            for e in entries:
                conn.execute("""
                    INSERT OR REPLACE INTO file_entries
                    (id, dir_id, entry_type, path, name, clean_name, enhanced_text,
                     ext, parent_dir_name, size, created_time, modified_time, vector, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    e['id'], e['dir_id'], e['entry_type'], e['path'], e['name'],
                    e['clean_name'], e['enhanced_text'], e['ext'], e['parent_dir_name'],
                    e['size'], e['created_time'], e['modified_time'], '[]', e['indexed_at'],
                ))

    def _encode_all_entries(self):
        batch_size = 500
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM file_entries").fetchone()[0]
        offset = 0
        while offset < total:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT id, enhanced_text FROM file_entries ORDER BY id LIMIT ? OFFSET ?",
                    (batch_size, offset)
                ).fetchall()
            updates = []
            for entry_id, enhanced in rows:
                vec = self.encoder.encode(enhanced)
                updates.append((json.dumps(vec), entry_id))
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany("UPDATE file_entries SET vector = ? WHERE id = ?", updates)
            offset += batch_size
            self.progress.add_entries_indexed(len(rows))
            # 更新阶段进度文本
            done = min(offset, total)
            self.progress.update_phase(
                f"阶段3/3: 计算向量并存储... ({done}/{total})"
            )

    # ===== 查询解析 =====

    _TIME_KEYWORDS = {
        "今年": 0, "本年": 0, "当前年": 0,
        "去年": -1, "上一年": -1,
        "前年": -2, "大前年": -3,
    }

    _TYPE_KEYWORDS = {
        "excel": [".xlsx", ".xls"],  "表格": [".xlsx", ".xls", ".csv"],
        "word": [".docx", ".doc"],   "文档": [".docx", ".doc", ".pdf", ".txt"],
        "ppt": [".pptx", ".ppt"],    "演示": [".pptx", ".ppt"],
        "pdf": [".pdf"],             "图片": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"],
        "视频": [".mp4", ".avi", ".mkv", ".mov", ".wmv"],
        "音频": [".mp3", ".wav", ".flac"],
        "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "代码": [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go"],
        "cad": [".dwg", ".dxf"],     "图纸": [".dwg", ".dxf", ".step", ".stp"],
    }

    def _parse_query(self, query: str) -> dict:
        """解析自然语言查询，提取筛选条件"""
        now = datetime.now()
        entry_type = None
        time_filter = None
        ext_filters = None
        clean_q = query

        # 类型筛选：文件夹/目录/文件
        for kw, et in [("文件夹", "dir"), ("目录", "dir"), ("文件", "file")]:
            if kw in clean_q:
                entry_type = et
                clean_q = clean_q.replace(kw, " ")
                break

        # 时间筛选
        year_match = re.search(r'(\d{4})年', clean_q)
        month_match = re.search(r'(\d{1,2})月', clean_q)
        if year_match:
            time_filter = {
                "year": int(year_match.group(1)),
                "month": int(month_match.group(1)) if month_match else None,
            }
            clean_q = clean_q.replace(year_match.group(0), " ")
            if month_match:
                clean_q = clean_q.replace(month_match.group(0), " ")
        else:
            for kw, offset in self._TIME_KEYWORDS.items():
                if kw in clean_q:
                    time_filter = {"year": now.year + offset, "month": None}
                    clean_q = clean_q.replace(kw, " ")
                    break
            if not time_filter:
                if "上个月" in clean_q:
                    m = now.month - 1 or 12
                    y = now.year if now.month > 1 else now.year - 1
                    time_filter = {"year": y, "month": m}
                    clean_q = clean_q.replace("上个月", " ")
                elif "这个月" in clean_q:
                    time_filter = {"year": now.year, "month": now.month}
                    clean_q = clean_q.replace("这个月", " ")

        # 文件类型筛选
        for type_kw, exts in self._TYPE_KEYWORDS.items():
            if type_kw in clean_q.lower():
                ext_filters = exts
                clean_q = re.sub(type_kw, " ", clean_q, flags=re.IGNORECASE)
                break

        clean_q = re.sub(r'\s+', ' ', clean_q).strip()
        return {
            "clean_query": clean_q,
            "entry_type": entry_type,
            "time_filter": time_filter,
            "ext_filters": ext_filters,
        }

    def _check_time_filter(self, time_filter: dict, created_time: str, modified_time: str) -> bool:
        """检查条目是否符合时间筛选"""
        if not time_filter:
            return True
        target_year = time_filter.get("year")
        target_month = time_filter.get("month")
        for timestr in [modified_time, created_time]:
            if not timestr:
                continue
            try:
                date_part = timestr.split('T')[0] if 'T' in timestr else timestr[:10]
                parts = date_part.split('-')
                year = int(parts[0])
                if year != target_year:
                    continue
                if target_month and len(parts) >= 2:
                    if int(parts[1]) != target_month:
                        continue
                return True
            except (ValueError, IndexError):
                continue
        return False

    # ===== 检索 =====

    def search(self, query: str, limit: int = 20, entry_type: str = None,
               ext_filter: str = None) -> list:
        """语义检索文件和目录

        流程:
        1. 解析查询 → 提取类型/时间/扩展名筛选条件
        2. 向量召回 → 全量计算相似度
        3. 条件过滤 → 类型、时间、扩展名
        4. 排序 → 相似度降序 + 同分按修改时间降序

        Args:
            query: 自然语言查询
            limit: 返回数量（默认20，平衡精度与效率）
            entry_type: 筛选类型 'file'/'dir'/None(全部)
            ext_filter: 扩展名筛选 如 'xlsx'
        """
        parsed = self._parse_query(query)
        clean_query = parsed["clean_query"] or query
        # 若解析后语义查询过短（<2字），退回原始查询避免向量化为空
        if len(clean_query) < 2:
            clean_query = query

        # 合并接口参数与解析参数（接口参数优先）
        final_type = entry_type or parsed["entry_type"]
        final_exts = None
        if ext_filter:
            final_exts = [f".{ext_filter.lstrip('.')}"]
        elif parsed["ext_filters"]:
            final_exts = parsed["ext_filters"]

        query_vec = self.encoder.encode(clean_query) if self.encoder._built else []

        with sqlite3.connect(self.db_path) as conn:
            # 一次批量拉取所有向量，避免逐条查询
            rows = conn.execute("""
                SELECT id, entry_type, path, name, clean_name, enhanced_text,
                       ext, parent_dir_name, size, created_time, modified_time
                FROM file_entries
            """).fetchall()

            vec_map = {}
            if query_vec:
                vec_rows = conn.execute("SELECT id, vector FROM file_entries").fetchall()
                for vid, vjson in vec_rows:
                    vec_map[vid] = json.loads(vjson)

            scored = []
            for r in rows:
                (entry_id, etype, path, name, clean, enhanced,
                 ext, parent, size, ctime, mtime) = r

                # 类型过滤
                if final_type and etype != final_type:
                    continue
                # 扩展名过滤
                if final_exts and ext not in final_exts:
                    continue
                # 时间过滤
                if not self._check_time_filter(parsed["time_filter"], ctime, mtime):
                    continue

                # 打分
                vec = vec_map.get(entry_id, [])
                vec_score = TFIDFEncoder.cosine_similarity(query_vec, vec) if query_vec and vec else 0.0
                kw_score = self._keyword_match_score(clean_query, name, clean, enhanced)
                final_score = vec_score * 0.7 + kw_score * 0.3

                if final_score < 0.01:
                    continue

                scored.append({
                    "entry_type": etype,
                    "path": path,
                    "name": name,
                    "clean_name": clean,
                    "ext": ext,
                    "parent_dir_name": parent,
                    "size": size,
                    "modified_time": mtime,
                    "similarity": round(final_score * 100, 1),
                    "vec_score": round(vec_score * 100, 1),
                    "kw_score": round(kw_score * 100, 1),
                })

            # 排序: 相似度降序 → 同分按修改时间降序
            scored.sort(key=lambda x: (
                -x["similarity"],
                -(x["modified_time"] or "")
            ))
            results = scored[:limit]

        return results

    def _keyword_match_score(self, query: str, name: str, clean: str, enhanced: str) -> float:
        """关键词匹配加分"""
        q_lower = query.lower()
        score = 0.0
        if q_lower in name.lower() or q_lower in clean.lower():
            score += 0.8
        query_chars = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z0-9]+', q_lower)
        if query_chars:
            match_count = sum(1 for c in query_chars if c in enhanced.lower())
            score += match_count / len(query_chars) * 0.4
        eng_words = re.findall(r'[a-zA-Z]{2,}', q_lower)
        if eng_words:
            matched = sum(1 for w in eng_words if w in clean.lower() or w in enhanced.lower())
            score += matched / len(eng_words) * 0.3
        return min(score, 1.0)

    def search_fts(self, query: str, limit: int = 10, entry_type: str = None,
                   ext_filter: str = None) -> list:
        """FTS5全文检索（备用/补充）"""
        results = []
        conditions = []
        params = []
        if entry_type:
            conditions.append("f.entry_type = ?")
            params.append(entry_type)
        if ext_filter:
            conditions.append("f.ext = ?")
            params.append(f".{ext_filter.lstrip('.')}")

        where_extra = f"AND {' AND '.join(conditions)}" if conditions else ""
        fts_query = self._build_fts_query(query)

        with sqlite3.connect(self.db_path) as conn:
            try:
                rows = conn.execute(f"""
                    SELECT f.entry_type, f.path, f.name, f.clean_name, f.enhanced_text,
                           f.ext, f.parent_dir_name, f.size, f.modified_time,
                           bm25(file_entries_fts) as score
                    FROM file_entries_fts ft
                    JOIN file_entries f ON f.rowid = ft.rowid
                    WHERE file_entries_fts MATCH ?
                    {where_extra}
                    ORDER BY score
                    LIMIT ?
                """, (fts_query, *params, limit)).fetchall()

                for r in rows:
                    results.append({
                        "entry_type": r[0], "path": r[1], "name": r[2],
                        "clean_name": r[3], "enhanced_text": r[4],
                        "ext": r[5], "parent_dir_name": r[6],
                        "size": r[7], "modified_time": r[8],
                        "similarity": round(min(-r[9] * 10, 100), 1),
                        "match_type": "fts",
                    })
            except Exception as e:
                logger.warning(f"FTS5检索失败: {e}")

        return results

    def _build_fts_query(self, query: str) -> str:
        clean = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', query)
        words = clean.split()
        expanded = []
        for w in words:
            if re.match(r'^[\u4e00-\u9fff]+$', w) and len(w) > 2:
                for i in range(len(w) - 1):
                    expanded.append(w[i:i + 2])
                expanded.append(w)
            else:
                expanded.append(w)
        if not expanded:
            return query
        return " OR ".join(f'"{e}"*' for e in expanded)

    # ===== 格式化输出 =====

    @staticmethod
    def format_results(results: list) -> str:
        """格式化检索结果为可读文本

        示例:
        [📄] 2023财务报表 | D:/工作/财务/2023报表.xlsx | 相似度92% | 2023-12-30
        [📁] 财务资料 | D:/工作/财务 | 相似度88% | 2023-06-15
        """
        if not results:
            return "未找到匹配的文件或目录"

        lines = []
        for i, r in enumerate(results, 1):
            icon = "📁" if r.get('entry_type') == 'dir' else "📄"
            ext = r.get('ext', '')
            name = r.get('name', '')
            path = r.get('path', '')
            sim = r.get('similarity', 0)
            mtime = r.get('modified_time', '')
            # 格式化修改时间（只取日期）
            if mtime and 'T' in mtime:
                mtime = mtime.split('T')[0]
            elif mtime and len(mtime) > 10:
                mtime = mtime[:10]

            line = f"{i}. [{icon}] {name}"
            if ext and r.get('entry_type') != 'dir':
                line += f" ({ext})"
            line += f" | {path} | 相似度{sim}% | {mtime}"
            lines.append(line)

        return "\n".join(lines)

    # ===== 索引状态 =====

    def get_status(self) -> dict:
        """获取索引状态"""
        with sqlite3.connect(self.db_path) as conn:
            dir_count = conn.execute("SELECT COUNT(*) FROM indexed_dirs").fetchone()[0]
            file_count = conn.execute(
                "SELECT COUNT(*) FROM file_entries WHERE entry_type='file'"
            ).fetchone()[0]
            dir_entry_count = conn.execute(
                "SELECT COUNT(*) FROM file_entries WHERE entry_type='dir'"
            ).fetchone()[0]
            total_size = conn.execute(
                "SELECT SUM(size) FROM file_entries"
            ).fetchone()[0] or 0
            ext_stats = conn.execute("""
                SELECT ext, COUNT(*) as cnt
                FROM file_entries
                WHERE entry_type = 'file'
                GROUP BY ext
                ORDER BY cnt DESC
                LIMIT 15
            """).fetchall()

        status = {
            "indexed_dirs": dir_count,
            "file_count": file_count,
            "dir_entry_count": dir_entry_count,
            "total_size": self._human_size(total_size),
            "encoder_built": self.encoder._built,
            "vocab_size": len(self.encoder.vocab),
            "ext_distribution": [{"ext": r[0], "count": r[1]} for r in ext_stats],
        }
        # 加上进度信息
        status["progress"] = self.progress.get_snapshot()
        status["progress_formatted"] = self.progress.get_formatted()
        return status

    def get_stats(self) -> dict:
        """兼容旧接口"""
        return self.get_status()

    @staticmethod
    def _human_size(size: int) -> str:
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f}MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f}GB"


# 全局单例
file_indexer = LocalFileIndexer()
