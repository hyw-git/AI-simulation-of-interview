from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# load .env if present
load_dotenv()
# load LLM-only secrets from .env.llm (overrides .env if both exist)
load_dotenv(dotenv_path=".env.llm", override=True)

app = FastAPI(title="AI 面试平台 - Backend (MVP)")

# CORS: 允许前端（Vite）访问后端
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include routers
from backend.app.api.health import router as health_router
from backend.app.api.auth import router as auth_router
from backend.app.api.questions import router as questions_router
from backend.app.api.interviews import router as interviews_router
from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.rag import router as rag_router

app.include_router(health_router)
app.include_router(auth_router, prefix="/auth")
app.include_router(questions_router, prefix="/questions")
app.include_router(interviews_router, prefix="/interviews")
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(rag_router, prefix="/rag")

@app.on_event("startup")
async def startup_event():
    # placeholder for startup tasks (DB connections, DI, etc.)
    print("Starting backend...")

@app.get("/")
async def root():
    return {"message": "AI 面试平台 Backend 已启动"}

