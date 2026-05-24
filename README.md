# AIDE - 个人AI助手

> 项目代号：AIDE (AI Desktop Engine) | 版本：v0.3.0

## 快速开始

### Windows
```
1. 双击 install.bat 安装
2. 双击桌面快捷方式或 start.bat 启动
3. 浏览器打开 http://127.0.0.1:8900
```

### Linux (Ubuntu 24.04)
```bash
bash install.sh        # 安装
./start.sh             # 启动
```

## 目录结构

```
aide/
  ├── app/           📦 程序代码（升级时覆盖）
  │   └── backend/
  ├── config/        ⚙️ 默认配置（升级时覆盖）
  │   └── default.env
  ├── data/          💾 用户数据（升级不碰！）
  ├── user/          👤 用户自定义（升级不碰！）
  │   ├── user.env        用户配置
  │   ├── tasks/          定时任务
  │   └── templates/      文档模板
  ├── output/        📄 生成的文档（升级不碰）
  ├── docs/          📖 文档
  └── logs/          📋 日志
```

## 配置

- 默认配置：`config/default.env`（开发者维护，升级时覆盖）
- 用户配置：`user/user.env`（优先级更高，升级不覆盖）

## 环境要求

- LLM: vLLM http://192.168.1.100:8004/v1 (qwen3.6-27B)
- 达梦数据库: 192.168.1.10:5236 / 192.168.1.11:5236 (dmdb/lczx)
- 致远OA: API对接
- 运行环境: Windows 10 / Ubuntu 24.04

## 文档

- [用户操作手册](docs/操作手册.md)
- [系统设计文档](docs/DESIGN.md)
- [P0改进方案](docs/P0改进方案.md)
- [项目反思](docs/项目反思_用户视角.md)
