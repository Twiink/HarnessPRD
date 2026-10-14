import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api.jobs import router as jobs_router
from api.conversation import router as conversation_router
from api.config import router as config_router
from api.session import router as session_router
from api.documents import router as documents_router
from db.database import init_db
from middleware.request_id import RequestIdMiddleware

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(
    title="Vibe Coding API",
    description="对话式需求收集平台 API",
    version="1.0.0"
)

init_db()

app.add_middleware(RequestIdMiddleware)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(conversation_router)
app.include_router(jobs_router)
app.include_router(config_router)
app.include_router(session_router)
app.include_router(documents_router)


@app.get("/")
async def root():
    return {"message": "Vibe Coding API 运行中", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
