# AIDE 智能助手 - 系统设计文档

> 项目代号：AIDE (AI Desktop Engine)  
> 版本：v0.3.0  
> 日期：2026-05-24  
> 状态：已上线运行

---

## 一、项目概述

面向航空发动机维修工厂的本地化AI办公助手，通过自然语言交互实现文档生成、数据分析、文件检索、OA流程、自我进化五大能力。适配Win7/Win10离线环境，零外部依赖。

### 核心原则

- **本地优先**：所有数据不出本机，LLM调用走内网vLLM或腾讯TokenHub
- **离线可用**：Win7/Win10全部离线部署，自带Python运行时和所有依赖
- **配置驱动**：任务模板化，SQL/Prompt/输出模板可配置复用
- **渐进式**：模块解耦，技能可独立开关

### 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.8/3.12 + FastAPI + Uvicorn |
| 前端 | Vue3 + Element Plus + Vite |
| LLM | vLLM (Qwen3.6-27B) / 腾讯TokenHub (GLM-5.1) / OpenAI兼容 |
| 数据库 | SQLite (消息/记忆/索引) + 达梦 (业务数据) |
| 向量检索 | 纯Python TF-IDF + 余弦相似度 (零外部依赖) |
| 桌面客户端 | PySide6 (仅Win10) + 系统托盘 |
| 定时任务 | APScheduler |

---

## 二、系统架构

```
┌────────────────────────────────────────────────────────────────┐
│                          客户端层                               │
│  ┌─────────────────┐  ┌──────────────────────────────────┐    │
│  │  桌面客户端       │  │  Web UI (Vue3 + Element Plus)    │    │
│  │  (PySide6/Qt)   │  │  浏览器访问 http://127.0.0.1:8900 │    │
│  └────────┬────────┘  └───────────────┬──────────────────┘    │
└───────────┼───────────────────────────┼───────────────────────┘
            │                           │
┌───────────▼───────────────────────────▼───────────────────────┐
│                    FastAPI 后端服务 (:8900)                     │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │
│  │ 文档引擎  │ │ 分析引擎  │ │ OA/IM    │ │ 智能工具集    │     │
│  │ DocEngine │ │ AnaEngine│ │ Notifier │ │ Skills       │     │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘ └──────┬───────┘     │
│        │            │            │              │              │
│  ┌─────▼────────────▼────────────▼──────────────▼───────┐     │
│  │              LLM Client (OpenAI兼容)                  │     │
│  │  vLLM / 腾讯TokenHub / OpenAI兼容 / 自定义            │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐    │
│  │ 进化引擎  │ │ 记忆系统  │ │ 文件索引  │ │ 知识库RAG     │    │
│  │Evolution │ │ Memory   │ │Indexer   │ │ Knowledge     │    │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘    │
│                                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │ Scheduler │ │ DM DB    │ │ 文件存储  │                     │
│  │(APScheduler)│ │(dmPython)│ │(本地磁盘) │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└────────────────────────────────────────────────────────────────┘
```

---

## 三、模块详细设计

### 3.1 LLM客户端 (core/llm.py)

多Provider适配层，运行时切换：

| Provider | API格式 | 特殊处理 |
|----------|---------|---------|
| vLLM | OpenAI兼容 | Qwen3思考模型`<think>`标签解析 |
| 腾讯TokenHub | OpenAI兼容 | GLM-5的`reasoning_content`独立字段 |
| OpenAI兼容 | OpenAI标准 | 直通 |
| 自定义 | OpenAI兼容 | 直通 |

关键能力：
- 同步/异步双客户端（httpx）
- 消息截断（token估算 + 滑动窗口）
- 思考模型输出解析（Qwen3 `<think>` + GLM-5 `reasoning_content`）
- 工具调用（Function Calling）自动检测，400回退

### 3.2 技能系统 (core/skills.py)

三层架构：注册 → 发现 → 调度

**技能可见性分级：**

| 级别 | 说明 | 用户可关闭？ | 示例 |
|------|------|------------|------|
| visible | 面向用户 | ✅ | local_file_search, query_database |
| hidden | 辅助功能 | ✅ | ocr_recognize, analyze_data |
| internal | 系统工具 | ❌ | read_file, write_file, run_shell |

**Function Calling 流程：**
1. 前端发消息 → 后端构造messages + tools schema
2. LLM返回tool_calls → skill_manager.execute_skill()
3. 工具结果注入messages → 二次LLM调用生成回复
4. 流式SSE输出最终结果

**技能开关持久化**：`data/skill_config.json`

### 3.3 本地文件检索 (core/file_indexer.py)

**v2.0 核心升级：**

| 特性 | 实现 |
|------|------|
| 索引对象 | 同时索引文件（按文件名）和目录（按目录名） |
| 名称清洗 | NOISE_PATTERNS去除冗余符号、版本号等 |
| 语义增强 | 结合父目录名/扩展名描述生成enhanced_text |
| 向量编码 | 纯Python TF-IDF（零依赖），稀疏向量存为[idx1,val1,...] |
| 混合检索 | `vec_score * 0.7 + kw_score * 0.3` |
| 后台索引 | threading.Daemon线程，不阻塞用户交互 |
| 进度追踪 | IndexProgress三阶段实时计数 + 进度条 + ETA |
| 查询解析 | `_parse_query()`自动提取类型/时间/扩展名筛选 |
| 双重排序 | 相似度降序 → 同分按修改时间降序 |

**查询解析示例：**
```
"2023年产品会议的PPT文件" → 
  语义查询: "产品会议的"
  类型筛选: file
  时间筛选: {year: 2023}
  扩展名: [.pptx, .ppt]
```

**时间关键词支持：** 今年/去年/前年/大前年/2023年/6月/这个月/上个月

**文件类型关键词：** Excel/表格/Word/文档/PPT/图纸/CAD/代码/压缩包/图片/视频/音频

### 3.4 记忆系统 (core/memory.py)

三层记忆架构：

```
┌─────────────────────────────────────┐
│  工作记忆 (build_context)            │
│  - 最近20条消息                      │
│  - 相关长期记忆检索注入               │
│  - 对话摘要（如有）                   │
├─────────────────────────────────────┤
│  长期记忆 (long_term_memory)         │
│  - 每轮对话后LLM自动提取              │
│  - 分类: fact/preference/rule/lesson │
│  - 关键词检索 + 重要性排序            │
├─────────────────────────────────────┤
│  对话摘要 (conversation_summaries)   │
│  - 6条消息后首次生成                  │
│  - 每20条消息更新                     │
│  - 永久存入SQLite                    │
└─────────────────────────────────────┘
```

**v0.3.0 关键修复：**
- 记忆注入提示改为"仅供与当前问题相关时参考"，防止LLM从记忆抄答案不调工具
- 对话摘要从"每20条才生成"改为"6条后即生成+每20条更新"
- GET /summarize 改为只读缓存，不再触发LLM（修复切换对话卡顿）

### 3.5 进化引擎 (core/evolution.py)

自我反思 + 规则积累：
- 每N轮对话触发反思
- LLM分析对话找出不足 → 提取改进规则
- 规则写入system_prompt的learned_rules
- 支持手动触发进化

### 3.6 知识库RAG (core/knowledge.py)

- 支持多知识库管理
- 文档分块 + 入库
- 查询时检索相关片段注入上下文
- 前端支持对话时选择知识库

### 3.7 FastAGI智能体广场 (core/fastagi.py)

对接滴普FastAGI大模型工作流平台（类似Dify）：
- 配置APP_ID + SECRET_KEY
- HMAC-SHA256签名鉴权
- 支持在线对话和文件上传

### 3.8 文档引擎 (engines/doc_engine.py + renderers/)

模板驱动文档生成：
```
用户描述 → LLM解析 → 填充模板 → 渲染输出
                              ↓
                    docx_renderer / xlsx_renderer / pptx_renderer
```
支持：Word报告、Excel表格、PPT演示

### 3.9 分析引擎 (engines/analysis_engine.py)

自然语言 → SQL → 执行 → 图表：
```
用户问题 → LLM生成SQL → 安全检查 → 执行查询 → LLM分析 → 生成图表
```
支持：达梦/MySQL/PostgreSQL/SQLite

---

## 四、数据存储

| 数据库 | 用途 | 位置 |
|--------|------|------|
| memory.db | 对话消息/长期记忆/摘要 | data/memory.db |
| file_index_v2.db | 文件索引+TF-IDF向量 | data/file_index_v2.db |
| file_index.db | 旧版文件索引(兼容) | data/file_index.db |
| knowledge.db | 知识库文档/分块 | data/knowledge.db |
| 达梦数据库 | 业务数据（外部） | 网络连接 |

---

## 五、前端页面

| 路由 | 页面 | 功能 |
|------|------|------|
| /chat | 对话 | 多轮对话、流式SSE、附件上传、知识库选择 |
| /knowledge | 知识库 | 创建/上传文档/检索测试 |
| /doc | 文档 | 自然语言生成Word/Excel/PPT |
| /templates | 模板 | 报表模板管理 |
| /agents | 智能体 | FastAGI工作流 |
| /task | 任务 | 定时分析任务 |
| /query | 查数据 | 自然语言查数据库 |
| /skills | 技能 | 技能展示/开关 |
| /tool | 工具 | 文件索引/OCR |
| /help | 帮助 | 使用指南 |
| /settings | 设置 | LLM配置/数据源配置 |

**输入框布局（v0.3.0）：**
```
[技能] [记忆] [进化]                         [知识库选择 ▾]
┌──────────────────────────────────────────────────┐
│ 📎 附件1.xlsx ✕  📎 附件2.docx ✕              │ ← 附件预览
│ 输入消息...                                     │ ← 文本框(自适应高度)
│                                    [📎] [➤]     │ ← 附件+发送嵌在框内
└──────────────────────────────────────────────────┘
```

**图标方案（v0.3.0）：**
- 导航栏和关键按钮使用 `@element-plus/icons-vue` 矢量图标
- 解决Win7 Chrome emoji渲染为方框的问题

---

## 六、部署架构

### Win10离线包
```
aide-win10-offline/
├── aide/                   # 应用代码
├── python/python-3.12.9/   # Python 3.12运行时
├── packages/               # 所有pip whl包（含PySide6）
└── install.bat
```

### Win7离线包
```
aide-win7-offline/
├── aide/                   # 应用代码（无desktop/目录）
├── python/python-3.8.10/   # Python 3.8 embedded运行时
├── packages/               # 所有pip whl包（cp38）
└── install.bat
```

### 差异对比

| 项目 | Win10 | Win7 |
|------|-------|------|
| Python | 3.12.9 完整版 | 3.8.10 embedded |
| 桌面客户端 | PySide6 ✅ | ❌ 不支持 |
| 启动方式 | 桌面客户端 或 浏览器 | CMD + 浏览器 |
| pip包格式 | cp312 | cp38 |
| Uvicorn | Python启动 | python.exe -m uvicorn |

---

## 七、安全策略

- 所有密码字段在代码中为空字符串，运行时从user.env读取
- 前端设置页面密码字段显示`***`，API返回时脱敏
- 内网IP已从源码中移除，替换为示例地址（192.168.x.x）
- 个人邮箱已替换为 your-email@example.com
- `.gitignore`排除data/、logs/、user/、*.db等运行时数据
- 技能可见性分级防止用户误关系统工具

---

## 八、后续规划

详见 `docs/桌面伴侣方案.md` — 系统托盘+Chromium便携版方案
