# 个人AI助手 - 系统设计文档

> 项目代号：AIDE (AI Desktop Engine)
> 版本：v0.1 设计稿
> 日期：2026-05-19

---

## 一、项目概述

一个运行在Windows 10上的个人AI助手，通过自然语言交互，实现文档生成、定时数据分析、OA流程集成、智能工具四大能力。

### 核心原则

- **本地优先**：所有数据不出本机，LLM调用走内网vLLM
- **配置驱动**：任务模板化，SQL/Prompt/输出模板可配置复用
- **渐进式**：模块解耦，可独立开发部署

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                        客户端层                               │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │  桌面客户端       │  │  Web UI (Vue3 + Element Plus)   │   │
│  │  (PySide6/Qt)   │  │  同一套API，浏览器访问             │   │
│  └────────┬────────┘  └───────────────┬─────────────────┘   │
└───────────┼───────────────────────────┼──────────────────────┘
            │                           │
┌───────────▼───────────────────────────▼──────────────────────┐
│                    FastAPI 后端服务                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ 文档引擎  │ │ 分析引擎  │ │ OA/IM    │ │ 智能工具集    │   │
│  │ DocEngine │ │ AnaEngine│ │ Notifier │ │ ToolBox      │   │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘ └──────┬───────┘   │
│        │            │            │              │            │
│  ┌─────▼────────────▼────────────▼──────────────▼───────┐   │
│  │              LLM Client (OpenAI兼容)                  │   │
│  │         vLLM: 192.168.1.100:8004/v1                  │   │
│  │         Model: qwen3.6-27B                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │ Scheduler │ │ DM DB    │ │ 文件存储  │                    │
│  │(APScheduler)│ │(dmPython)│ │(本地磁盘)│                    │
│  └──────────┘ └──────────┘ └──────────┘                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、模块详细设计

### 3.1 文档生成引擎 (DocEngine)

#### 核心思路

LLM不直接生成文件，而是生成**结构化文档描述(JSON)**，由渲染器转换为最终文件。

```
用户自然语言 → LLM → 文档JSON → 渲染器 → Word/Excel/PPT
                    ↑                          ↓
                    └── 多轮修改 ← 读取当前状态 ←─┘
```

#### 文档状态模型

每个文档维护一个JSON状态，支持增量修改：

```json
{
  "doc_id": "uuid",
  "type": "docx",  // docx | xlsx | pptx
  "title": "设备运行月报",
  "created_at": "2026-05-19T00:00:00",
  "updated_at": "2026-05-19T00:10:00",
  "content": {
    "sections": [
      {
        "type": "heading",
        "level": 1,
        "text": "一、设备运行概况"
      },
      {
        "type": "paragraph",
        "text": "本月共监测设备XX台..."
      },
      {
        "type": "table",
        "headers": ["设备名称", "运行时长", "故障次数"],
        "rows": [["发动机A", "720h", "2"]]
      },
      {
        "type": "chart",
        "chart_type": "bar",  // bar | line | pie | scatter
        "title": "设备故障趋势",
        "x_axis": "月份",
        "y_axis": "故障次数",
        "data": {
          "labels": ["1月", "2月", "3月"],
          "datasets": [{"label": "故障数", "values": [5, 3, 7]}]
        },
        "width": 500,
        "height": 300
      }
    ]
  }
}
```

#### 图表生成

- 数据分析结果中的图表：用matplotlib生成图片 → 嵌入Word/PPT
- Excel图表：openpyxl原生图表
- PPT图表：python-pptx原生图表

#### 多轮修改流程

1. 用户说"把第二段的XX改成YY" / "加一个饼图"
2. 读取当前文档JSON状态
3. 将{当前状态 + 用户指令}发给LLM
4. LLM返回修改后的完整JSON（或diff）
5. 渲染器重新生成文件
6. 用户可下载最新版本

#### 技术选型

| 文件类型 | 库 | 说明 |
|---------|-----|------|
| Word | python-docx | 段落、表格、图片、样式 |
| Excel | openpyxl | 数据、公式、图表、样式 |
| PPT | python-pptx | 幻灯片、图表、布局 |
| 图表 | matplotlib | 生成图片嵌入文档 |

---

### 3.2 定时数据分析引擎 (AnaEngine)

#### 任务模板配置

每个分析任务是一个YAML配置文件，存放在 `tasks/` 目录：

```yaml
# tasks/daily_device_report.yaml
name: "每日设备运行报告"
description: "从达梦数据库获取设备数据，AI分析后生成Word报告"
enabled: true

schedule:
  cron: "0 8 * * *"   # 每天8点
  # 或 interval: 3600  # 每小时

database:
  host: "192.168.1.10"   # 主库
  standby: "192.168.1.11"  # 备库（主库不可用时切换）
  port: 5236
  username: "dmdb"
  password: "ENC:xxx"  # 加密存储
  database: "lczx"

sql: |
  SELECT device_name, run_hours, fault_count, last_check_date
  FROM device_status
  WHERE record_date = CURRENT_DATE

prompt: |
  你是航空发动机维修工厂的设备分析专家。请根据以下设备运行数据：
  1. 总结整体运行状况
  2. 指出异常设备
  3. 给出维护建议
  
  数据：
  {{data}}

output:
  format: "docx"  # docx | xlsx | pptx | md
  template: "templates/daily_device_report.docx"  # 可选，有则按模板填充
  filename: "设备运行日报_{{date}}.docx"
  save_path: "output/reports/"

notify:
  enabled: false  # 后续对接IM后开启
  # channel: "qq"
  # target: "your-qq-number"
```

#### 执行流程

```
定时触发 → 连接DM数据库 → 执行SQL → 格式化数据
    → 拼装Prompt → 调用vLLM → 获取分析结果
    → 选择模板/格式 → 渲染文档 → 保存文件
    → 推送通知（可选）
```

#### 数据库高可用

- 主库优先连接，连接失败自动切换备库
- dmPython支持连接超时和重试配置

---

### 3.3 OA/IM集成引擎 (Notifier)

#### 致远OA流程发起

```python
# 致远OA API封装
class SeeyonClient:
    def __init__(self, base_url, token_getter):
        self.base_url = base_url
        self.token_getter = token_getter
    
    async def start_process(self, template_code: str, subject: str, 
                            form_data: dict, draft: bool = False,
                            attachments: list = None):
        """发起致远流程"""
        payload = {
            "appName": "collaboration",
            "data": {
                "templateCode": template_code,
                "draft": "1" if draft else "0",
                "subject": subject,
                "data": form_data,  # {"formmain_xxx": {"字段": "值"}}
                "attachments": attachments or []
            }
        }
        # POST /seeyon/rest/bpm/process/start
```

#### 统一通知接口

```python
class NotifyChannel(Protocol):
    async def send_message(self, target: str, content: str, 
                          attachments: list = None) -> bool: ...

class QQNotifier(NotifyChannel): ...       # 后续对接
class SeeyonNotifier(NotifyChannel): ...    # OA流程
class EmailNotifier(NotifyChannel): ...     # 邮件
```

#### 配置化

```yaml
# config/notifiers.yaml
channels:
  seeyon:
    enabled: true
    base_url: "http://OA地址:端口"
    token_api: "/seeyon/rest/token"
    username: "xxx"
    password: "ENC:xxx"
  
  qq:
    enabled: false
    # 后续配置
  
  email:
    enabled: true
    smtp: "smtp.qq.com:465"
    sender: "your-email@example.com"
    password: "ENC:xxx"
```

---

### 3.4 智能工具集 (ToolBox)

#### 直接对话

```python
# 与vLLM模型的直接对话，支持多轮
# 流式输出，Web端SSE推送
POST /api/chat
{
    "message": "帮我解释一下这个概念",
    "conversation_id": "uuid",  # 多轮对话
    "stream": true
}
```

#### OCR图文识别

- PaddleOCR：本地部署，离线可用
- 支持图片上传 → 文字提取 → 可直接送入LLM分析

#### 工具注册表

```yaml
# config/tools.yaml
tools:
  - name: "ocr"
    type: "paddleocr"
    enabled: true
  
  - name: "web_search"
    type: "web_search"
    enabled: false  # 离线环境暂不开启
  
  - name: "calculator"
    type: "builtin"
    enabled: true
```

---

## 四、数据存储

### SQLite 表结构

```sql
-- 文档状态表
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,        -- docx/xlsx/pptx
    title TEXT,
    content_json TEXT NOT NULL, -- 文档状态JSON
    file_path TEXT,            -- 最新生成的文件路径
    created_at DATETIME,
    updated_at DATETIME
);

-- 分析任务表
CREATE TABLE analysis_tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_yaml TEXT NOT NULL,  -- 任务配置
    enabled INTEGER DEFAULT 1,
    last_run DATETIME,
    last_status TEXT            -- success/failed/running
);

-- 分析执行记录
CREATE TABLE analysis_logs (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    started_at DATETIME,
    finished_at DATETIME,
    status TEXT,
    result_file TEXT,
    error_msg TEXT
);

-- 对话记录
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    role TEXT,          -- user/assistant
    content TEXT,
    created_at DATETIME
);

-- 通知记录
CREATE TABLE notify_logs (
    id TEXT PRIMARY KEY,
    channel TEXT,
    target TEXT,
    content TEXT,
    status TEXT,
    created_at DATETIME
);
```

---

## 五、API设计

### 文档相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/doc/create | 创建文档（自然语言描述） |
| POST | /api/doc/{id}/modify | 修改文档（自然语言指令） |
| GET | /api/doc/{id}/download | 下载文档文件 |
| GET | /api/doc/{id}/preview | 预览文档JSON状态 |
| GET | /api/doc/list | 文档列表 |
| DELETE | /api/doc/{id} | 删除文档 |

### 分析任务相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/task/list | 任务列表 |
| POST | /api/task/create | 创建任务 |
| PUT | /api/task/{id} | 修改任务配置 |
| POST | /api/task/{id}/run | 手动执行一次 |
| DELETE | /api/task/{id} | 删除任务 |
| GET | /api/task/{id}/logs | 执行记录 |

### 对话相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat | 发送消息（支持SSE流式） |
| GET | /api/conversation/list | 对话列表 |
| GET | /api/conversation/{id}/messages | 对话历史 |
| DELETE | /api/conversation/{id} | 删除对话 |

### OA/通知相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/oa/start-process | 发起OA流程 |
| POST | /api/notify/send | 发送通知 |

### 工具相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/tool/ocr | OCR识别 |
| GET | /api/tool/list | 可用工具列表 |

---

## 六、LLM调用设计

### vLLM对接

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://192.168.1.100:8004/v1",
    api_key="not-needed"  # vLLM默认不需要
)

# 模型名称
MODEL = "qwen3.6-27B"

# 流式调用
stream = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    stream=True,
    temperature=0.7,
    max_tokens=4096
)
```

### Prompt模板管理

不同场景使用不同的System Prompt：

```yaml
# config/prompts.yaml
prompts:
  doc_generation:
    system: |
      你是一个文档生成助手。用户用自然语言描述需求，你生成结构化的文档JSON。
      严格按以下格式输出，不要输出其他内容：
      {文档JSON schema}
  
  data_analysis:
    system: |
      你是数据分析专家。根据提供的数据库查询结果进行分析。
      输出格式：Markdown
  
  chat:
    system: |
      你是一个友善的个人AI助手，名叫知行。直接回答用户问题。
  
  oa_form:
    system: |
      你是OA流程助手。根据用户描述，提取表单字段数据。
      输出格式：JSON {"formmain_xxx": {"字段": "值"}}
```

---

## 七、项目结构

```
ai-assistant/
├── backend/
│   ├── main.py                    # FastAPI入口
│   ├── config/
│   │   ├── settings.py            # 全局配置
│   │   ├── database.yaml          # 数据库连接配置
│   │   ├── prompts.yaml           # Prompt模板
│   │   └── notifiers.yaml         # 通知渠道配置
│   ├── core/
│   │   ├── llm.py                 # vLLM客户端封装
│   │   ├── database.py            # 达梦数据库连接池
│   │   └── scheduler.py           # APScheduler封装
│   ├── engines/
│   │   ├── doc_engine.py          # 文档生成引擎
│   │   ├── analysis_engine.py     # 数据分析引擎
│   │   └── tool_engine.py         # 智能工具引擎
│   ├── notifiers/
│   │   ├── base.py                # 通知接口基类
│   │   ├── seeyon.py              # 致远OA
│   │   ├── email.py               # 邮件通知
│   │   └── qq.py                  # QQ通知（预留）
│   ├── renderers/
│   │   ├── docx_renderer.py       # Word渲染器
│   │   ├── xlsx_renderer.py       # Excel渲染器
│   │   ├── pptx_renderer.py       # PPT渲染器
│   │   └── chart_renderer.py      # 图表渲染器
│   ├── models/
│   │   ├── document.py            # 文档数据模型
│   │   ├── task.py                # 任务数据模型
│   │   └── conversation.py        # 对话数据模型
│   ├── routers/
│   │   ├── doc.py                 # 文档API
│   │   ├── task.py                # 任务API
│   │   ├── chat.py                # 对话API
│   │   ├── oa.py                  # OA API
│   │   └── tool.py                # 工具API
│   ├── tasks/                     # 分析任务配置目录
│   ├── templates/                 # 文档模板目录
│   ├── output/                    # 生成文件输出目录
│   └── data/                      # SQLite数据库目录
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Chat.vue           # 对话页面
│   │   │   ├── DocEditor.vue      # 文档生成/编辑
│   │   │   ├── TaskManager.vue    # 任务管理
│   │   │   └── Tools.vue          # 工具页面
│   │   ├── components/
│   │   └── api/
│   ├── package.json
│   └── vite.config.js
├── desktop/
│   ├── main.py                    # PySide6桌面客户端
│   └── resources/
├── requirements.txt
├── install.bat                    # Windows安装脚本
└── README.md
```

---

## 八、开发计划

### 第一期：核心框架 + 文档引擎 + 对话

**目标**：能对话、能生成文档

- [ ] FastAPI项目骨架 + SQLite
- [ ] vLLM客户端封装 + 流式输出
- [ ] 文档JSON状态模型设计
- [ ] Word渲染器（段落、表格、图片、样式）
- [ ] Excel渲染器（数据、公式、图表）
- [ ] PPT渲染器（幻灯片、布局）
- [ ] 图表渲染器（matplotlib → 图片嵌入）
- [ ] 多轮文档修改逻辑
- [ ] 对话页面（SSE流式）
- [ ] 文档编辑页面

### 第二期：定时分析引擎

**目标**：配置SQL+Prompt+模板，定时出报告

- [ ] dmPython达梦数据库连接 + 主备切换
- [ ] 分析任务YAML配置解析
- [ ] APScheduler定时调度
- [ ] 任务执行流水线（取数据→LLM分析→渲染文档）
- [ ] 任务管理页面（CRUD + 手动执行）
- [ ] 执行日志查看

### 第三期：OA/IM集成

**目标**：自动推送报告、发起OA流程

- [ ] 致远OA Token获取
- [ ] 致远OA流程发起API封装
- [ ] 附件上传接口
- [ ] 邮件通知通道
- [ ] IM通道预留接口
- [ ] 通知配置页面

### 第四期：智能工具集

**目标**：OCR、知识库等工具

- [ ] PaddleOCR集成
- [ ] RAG知识库（可选）
- [ ] 工具注册与管理
- [ ] 工具页面

### 第五期：桌面客户端 + 打包

**目标**：独立桌面程序

- [ ] PySide6客户端开发
- [ ] 系统托盘
- [ ] PyInstaller打包为exe
- [ ] 一键安装脚本

---

## 九、安全设计

- 数据库密码：AES加密存储，运行时解密
- API密钥：配置文件加密
- 本地服务：绑定127.0.0.1，不暴露网络
- OA Token：缓存 + 自动刷新
- 敏感操作：OA发起流程需二次确认

---

## 十、依赖清单

### Python后端

```
fastapi==0.115.*
uvicorn[standard]
pydantic>=2.0
sqlalchemy
aiosqlite
httpx
openai           # vLLM兼容API客户端
python-docx
openpyxl
python-pptx
matplotlib
dmPython         # 达梦数据库驱动
apscheduler
paddleocr        # OCR
paddlepaddle     # OCR引擎
pydantic-settings
python-multipart
sse-starlette    # SSE流式推送
cryptography     # 密码加密
jinja2           # 模板渲染
python-jose      # JWT（如需）
```

### 前端

```
vue@3
element-plus
axios
markdown-it
```

### 桌面客户端

```
PySide6
PyInstaller
```
