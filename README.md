# AI 职场领航员

AI 职场领航员是一个面向校招和实习场景的企业级 AI 模拟面试平台。项目以 FastAPI + Vue 3 + PostgreSQL 为核心，结合 RAG 题库、简历解析、WebSocket 实时对话和结构化评估能力，形成“练习 - 追问 - 评分 - 回看”的完整闭环。

## 项目亮点

- 按岗位生成面试题目与追问，支持 Java 后端、Web 前端、Python 算法等岗位。
- 支持简历驱动、仓库驱动和题库驱动的个性化开场。
- 面试过程支持实时流式对话、倒计时控制、语音转写和代码实战侧栏。
- 面试结束后自动生成五维评分、改进建议和雷达图报告。
- 前端和后端均可本地运行，也支持 Docker Compose 一键部署。

## 技术栈

### 当前实现

- 后端：FastAPI、Uvicorn、Pydantic、PyJWT、psycopg2、python-dotenv
- 前端：Vue 3、Vue Router、Vite、Element Plus、Heroicons
- 数据库：PostgreSQL、pgvector
- 检索与题库：CSV 题库、VectorStore、RAG
- 部署：Docker、Docker Compose

## 核心功能

| 模块 | 说明 |
| --- | --- |
| 账号体系 | 注册、登录、刷新令牌、退出登录、个人信息维护 |
| 简历管理 | 文本编辑、文件上传、简历摘要与关键词提取 |
| 题库中心 | 按岗位浏览题目、收藏题目、查看标准答案与评分标准 |
| 模拟面试 | 基于岗位、简历和题库的实时追问与开场策略 |
| 代码实战 | Python 编程题生成、运行、提交与反馈 |
| 面试评估 | 五维评分、建议、报告存储与历史回看 |
| 数据总览 | 首页统计卡片、近期记录、雷达图展示 |

## 目录结构

```text
Project/
├── backend/                 # FastAPI 后端
├── frontend/                # Vue 3 前端
├── db/                      # 数据库结构与种子数据
├── data/                    # 题库和简历数据
├── scripts/                 # 构建题库索引等脚本
├── docker-compose.yml       # 本地一键部署
├── Dockerfile.backend       # 后端镜像构建
└── .env.llm.example         # LLM 环境变量模板
```

## 本地运行

### 1. 启动数据库和后端

```bash
docker-compose up --build
```

启动后可访问：

- 后端健康检查：`http://localhost:8000/health`
- 后端根地址：`http://localhost:8000/`

### 2. 启动前端开发环境

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：`http://localhost:5173`

## 配置说明

- `db/schema.sql` 定义完整表结构。
- `db/seed.sql` 提供初始化数据。
- `.env.llm` 用于配置大模型相关参数，未配置时系统会使用规则兜底。
- `backend/.cache/` 用于本地向量索引缓存。

## 已知边界

- 默认向量检索为本地实现，适合演示和课程项目，生产环境建议替换为持久化向量方案。
- 语音转写能力依赖模型和 API 配置，未配置时会禁用相关入口。
- 代码实战侧栏当前以 Python 为主，属于阶段性实现。

## 相关文档

- [项目需求文档](项目需求文档.md)
- [部署文档](部署文档.md)
