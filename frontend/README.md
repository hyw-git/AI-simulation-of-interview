# 前端骨架（Vite + Vue 3 + Element Plus）

快速开始：

1. 进入 `frontend` 目录

```bash
cd frontend
```

2. 安装依赖并启动开发服务器

```bash
cd frontend
npm install
npm run dev
```

3. 可通过环境变量覆盖后端地址：创建 `.env` 或在命令行中设置 `VITE_API_BASE`，默认 `http://localhost:8000`。

示例：

```bash
export VITE_API_BASE=http://localhost:8000
npm run dev
```

说明：该骨架包含基础路由和对后端 `/health`, `/interviews`, `/questions` 的调用封装。前端已迁移为 Vue 3 + Element Plus，路由文件在 `src/router`。
