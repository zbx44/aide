from __future__ import annotations
"""知识库系统 - 创建、上传、解析、分块、检索、RAG

设计：
1. 知识库：用户可创建多个知识库，每个包含多个文档
2. 文件解析：支持 docx/xlsx/pdf/md/txt/csv/json
3. 文本分块：按段落/固定长度分块，保留元数据
4. 检索：关键词+BM25混合检索（离线无需向量模型）
5. RAG：对话时选择知识库，先检索再回答
"""
import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """知识库管理"""

    def __init__(self):
        self.db_path = settings.DATA_DIR / "knowledge.db"
        self.storage_dir = settings.DATA_DIR / "knowledge_files"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_knowledge_bases (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    doc_count INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_documents (
                    id TEXT PRIMARY KEY,
                    kb_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    error TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (kb_id) REFERENCES kb_knowledge_bases(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_kb ON kb_documents(kb_id)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_chunks (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    kb_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    chunk_index INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES kb_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (kb_id) REFERENCES kb_knowledge_bases(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunk_kb ON kb_chunks(kb_id)
            """)
            conn.commit()

    # ===== 知识库管理 =====

    def create_kb(self, name: str, description: str = "") -> dict:
        kb_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    "INSERT INTO kb_knowledge_bases (id, name, description, created_at, updated_at) VALUES (?,?,?,?,?)",
                    (kb_id, name, description, now, now)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                raise ValueError(f"知识库 '{name}' 已存在")
        return {"id": kb_id, "name": name, "description": description}

    def list_kbs(self) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM kb_knowledge_bases ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_kb(self, kb_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM kb_knowledge_bases WHERE id = ?", (kb_id,)
            ).fetchone()
            return dict(row) if row else None

    def delete_kb(self, kb_id: str):
        # 删除文件
        kb_dir = self.storage_dir / kb_id
        if kb_dir.exists():
            import shutil
            shutil.rmtree(kb_dir)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM kb_chunks WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM kb_documents WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM kb_knowledge_bases WHERE id = ?", (kb_id,))
            conn.commit()

    # ===== 文档上传与解析 =====

    def upload_document(self, kb_id: str, file_path: str, filename: str) -> dict:
        doc_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # 存储文件
        kb_dir = self.storage_dir / kb_id
        kb_dir.mkdir(parents=True, exist_ok=True)
        save_path = kb_dir / f"{doc_id}_{filename}"
        import shutil
        shutil.copy2(file_path, save_path)

        file_type = Path(filename).suffix.lower().lstrip(".")
        file_size = os.path.getsize(save_path)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO kb_documents (id, kb_id, filename, file_path, file_type, file_size, status, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (doc_id, kb_id, filename, str(save_path), file_type, file_size, "pending", now)
            )
            conn.commit()

        # 异步解析
        try:
            chunks = self._parse_and_chunk(str(save_path), file_type)
            self._save_chunks(doc_id, kb_id, chunks)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE kb_documents SET status='ready', chunk_count=? WHERE id=?",
                    (len(chunks), doc_id)
                )
                conn.execute(
                    "UPDATE kb_knowledge_bases SET doc_count=doc_count+1, "
                    "chunk_count=chunk_count+?, updated_at=? WHERE id=?",
                    (len(chunks), now, kb_id)
                )
                conn.commit()

            return {"doc_id": doc_id, "chunks": len(chunks), "status": "ready"}
        except Exception as e:
            logger.error(f"文档解析失败 {filename}: {e}")
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE kb_documents SET status='error', error=? WHERE id=?",
                    (str(e), doc_id)
                )
                conn.commit()
            return {"doc_id": doc_id, "status": "error", "error": str(e)}

    def _parse_and_chunk(self, file_path: str, file_type: str) -> List[dict]:
        """解析文件并分块"""
        text = self._extract_text(file_path, file_type)
        chunks = self._chunk_text(text, chunk_size=800, overlap=100)
        return chunks

    def _extract_text(self, file_path: str, file_type: str) -> str:
        """提取文本内容"""
        if file_type in ("md", "txt", "csv", "json", "yaml", "yml"):
            # Windows记事本默认GBK编码，必须尝试多种编码
            for enc in ("utf-8", "gbk", "gb2312", "gb18030", "latin-1"):
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        text = f.read()
                    # 检查是否成功解码出中文内容
                    if len(text.strip()) > 0 and any('\u4e00' <= c <= '\u9fff' for c in text):
                        return text
                except (UnicodeDecodeError, UnicodeError):
                    continue
            # 兜底：强制utf-8+ignore
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif file_type == "docx":
            from docx import Document
            doc = Document(file_path)
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

        elif file_type == "xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(file_path, read_only=True)
            texts = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c) for c in row if c is not None]
                    if cells:
                        texts.append(" | ".join(cells))
            wb.close()
            return "\n".join(texts)

        elif file_type == "pptx":
            from pptx import Presentation
            prs = Presentation(file_path)
            texts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        texts.append(shape.text_frame.text)
            return "\n\n".join(texts)

        elif file_type == "pdf":
            return self._extract_pdf(file_path)

        else:
            # 尝试作为纯文本读取
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                raise ValueError(f"不支持的文件类型: {file_type}")

    def _extract_pdf(self, file_path: str) -> str:
        """提取PDF文本"""
        # 方式1: PyMuPDF
        try:
            import fitz
            doc = fitz.open(file_path)
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            pass

        # 方式2: pdfplumber
        try:
            import pdfplumber
            texts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        texts.append(t)
            return "\n\n".join(texts)
        except ImportError:
            pass

        # 方式3: PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            texts = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texts.append(t)
            return "\n\n".join(texts)
        except ImportError:
            pass

        raise ValueError(
            "PDF解析需要安装依赖：pip install PyMuPDF 或 pdfplumber 或 PyPDF2"
        )

    def _chunk_text(self, text: str, chunk_size: int = 800,
                    overlap: int = 100) -> List[dict]:
        """文本分块"""
        if not text.strip():
            return []

        # 按段落先切
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append({"content": current_chunk, "index": len(chunks)})
                # 如果单段太长，按固定长度切
                if len(para) > chunk_size:
                    for i in range(0, len(para), chunk_size - overlap):
                        chunk = para[i:i + chunk_size]
                        if chunk.strip():
                            chunks.append({"content": chunk, "index": len(chunks)})
                    current_chunk = ""
                else:
                    current_chunk = para

        if current_chunk.strip():
            chunks.append({"content": current_chunk, "index": len(chunks)})

        return chunks

    def _save_chunks(self, doc_id: str, kb_id: str, chunks: List[dict]):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            for chunk in chunks:
                chunk_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO kb_chunks (id, doc_id, kb_id, content, chunk_index, metadata, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (chunk_id, doc_id, kb_id, chunk["content"], chunk["index"],
                     json.dumps({"keywords": self._extract_keywords(chunk["content"])}, ensure_ascii=False), now)
                )
            conn.commit()

    # ===== 检索 =====

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """从文本中提取关键词（用于中文检索）
        策略：按标点分句，提取2-4字ngram + 英文单词
        """
        keywords = set()
        # 按标点分句
        sentences = re.split(r'[，。！？；：、""\'\'[\]()<>《》【】\s\n\r]+', text)
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            # 先提取英文单词（2字母以上）
            en_words = re.findall(r'[a-zA-Z][a-zA-Z0-9_]{1,}', s)
            for w in en_words:
                keywords.add(w.lower())
            # 提取中文ngram（2-4字）
            cn_chars = re.findall(r'[\u4e00-\u9fff]+', s)
            for seg in cn_chars:
                for n in [2, 3, 4]:
                    for i in range(len(seg) - n + 1):
                        gram = seg[i:i+n]
                        if gram:
                            keywords.add(gram)
                # 单字也加入（用于短查询如"放羊"拆成"放"+"羊"也能部分匹配）
                for c in seg:
                    if len(seg) <= 10:  # 短句才加单字，避免噪音
                        keywords.add(c)
        # 限制数量
        return list(keywords)[:500]

    def search(self, kb_id: str, query: str, top_k: int = 5) -> List[dict]:
        """检索知识库（多策略混合检索）
        策略: keywords ngram交集 + LIKE全文匹配 + 单字匹配
        """
        results = []
        seen_ids = set()
        score_map = {}  # id -> score

        # 提取查询关键词
        query_ngrams = set()
        for n in [2, 3, 4]:
            for i in range(len(query) - n + 1):
                gram = query[i:i+n]
                if gram and not gram.isascii():
                    query_ngrams.add(gram)

        # 单字也加入（用于短查询匹配）
        single_chars = set()
        for c in query:
            if '\u4e00' <= c <= '\u9fff':
                single_chars.add(c)

        # 英文词
        en_words = set(w.lower() for w in re.findall(r'[a-zA-Z]{2,}', query))

        # 一次性加载所有 chunks
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            all_rows = conn.execute(
                "SELECT * FROM kb_chunks WHERE kb_id = ?", (kb_id,)
            ).fetchall()

        if not all_rows:
            return []

        for row in all_rows:
            r = dict(row)
            score = 0.0

            # 策略1: ngram关键词交集
            meta = {}
            try:
                meta = json.loads(r.get("metadata", "{}"))
            except Exception:
                pass
            chunk_keywords = set(meta.get("keywords", []))
            ngram_overlap = len(query_ngrams & chunk_keywords)
            if ngram_overlap > 0:
                score += ngram_overlap * 3.0  # ngram匹配置信度高

            # 策略2: 单字匹配（对短查询很关键）
            if single_chars:
                chunk_single = set(c for c in r["content"] if '\u4e00' <= c <= '\u9fff')
                char_overlap = len(single_chars & chunk_single)
                if char_overlap > 0:
                    score += char_overlap * 0.5  # 单字匹配权重低一些

            # 策略3: LIKE全文匹配（用查询原文）
            content = r.get("content", "")
            if query in content:
                score += 10.0  # 完全出现在文本中，最高分

            # 策略4: 对查询中的2字片段做LIKE
            for ng in query_ngrams:
                if ng in content:
                    score += 2.0

            # 策略5: 英文词匹配
            if en_words:
                content_lower = content.lower()
                for w in en_words:
                    if w in content_lower:
                        score += 2.0

            if score > 0:
                r["_score"] = score
                results.append(r)
                score_map[r["id"]] = score

        # 按分数排序
        results.sort(key=lambda x: x.get("_score", 0), reverse=True)

        # 截取内容预览
        for r in results:
            content = r.get("content", "")
            # 高亮匹配部分
            r["preview"] = content[:200] + "..." if len(content) > 200 else content

        return results[:top_k]

    def get_documents(self, kb_id: str) -> List[dict]:
        """获取知识库下的文档列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM kb_documents WHERE kb_id = ? ORDER BY created_at DESC",
                (kb_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_document(self, doc_id: str):
        """删除文档及其分块"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            doc = conn.execute(
                "SELECT * FROM kb_documents WHERE id = ?", (doc_id,)
            ).fetchone()
            if doc:
                kb_id = doc["kb_id"]
                chunk_count = doc["chunk_count"]
                # 删除文件
                file_path = doc["file_path"]
                if os.path.exists(file_path):
                    os.unlink(file_path)
                conn.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
                conn.execute("DELETE FROM kb_documents WHERE id = ?", (doc_id,))
                conn.execute(
                    "UPDATE kb_knowledge_bases SET doc_count=doc_count-1, "
                    "chunk_count=chunk_count-?, updated_at=? WHERE id=?",
                    (chunk_count, datetime.now().isoformat(), kb_id)
                )
                conn.commit()

    def build_rag_context(self, kb_ids: List[str], query: str,
                          top_k_per_kb: int = 3) -> str:
        """为RAG构建检索上下文"""
        all_chunks = []
        for kb_id in kb_ids:
            chunks = self.search(kb_id, query, top_k=top_k_per_kb)
            all_chunks.extend(chunks)

        if not all_chunks:
            return ""

        # 去重
        seen = set()
        unique = []
        for c in all_chunks:
            if c["id"] not in seen:
                seen.add(c["id"])
                unique.append(c)

        context_parts = []
        for c in unique:
            context_parts.append(c["content"])

        return "\n\n---\n\n".join(context_parts)


# 全局单例
knowledge_base = KnowledgeBase()
