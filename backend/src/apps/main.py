"""应用工厂；模块导入只定义应用，不打开数据库或启动后台任务。"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.api.errors import register_error_handlers
from apps.api.router import router
from apps.core.config import Settings
from apps.bootstrap.lifecycle import application_lifespan
from apps.middleware.request_id import RequestIdMiddleware
from apps.runtime.job_executor import Executor


def create_app(settings: Settings | None = None, executor: Executor | None = None) -> FastAPI:
    app = FastAPI(
        title="HarnessPRD API",
        description="对话式需求收集与文档生成",
        lifespan=application_lifespan(settings, executor),
    )
    register_error_handlers(app)
    app.add_middleware(RequestIdMiddleware, fastapi_app=app)
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "Vibe Coding API 运行中"}

    @app.get("/health", include_in_schema=False)
    @app.get("/api/health/live", tags=["health"])
    async def live():
        return {"status": "healthy"}

    @app.get("/api/health/ready", tags=["health"])
    def ready(request: Request):
        resources = getattr(request.app.state, "resources", None)
        if (
            resources
            and resources.ready
            and resources.job_manager.healthy
            and resources.database.is_ready()
        ):
            return {"status": "ready"}
        return JSONResponse(
            status_code=503,
            content={
                "code": "NOT_READY",
                "message": "服务未就绪",
                "request_id": getattr(request.state, "request_id", None),
                "retryable": True,
            },
        )

    @app.get("/api/metrics", tags=["health"])
    def metrics(request: Request):
        resources = getattr(request.app.state, "resources", None)
        if resources is None:
            return {"ready": False, "active_tasks": 0, "jobs": {}}
        return {
            "ready": resources.ready,
            "active_tasks": resources.job_manager.active_count,
            "jobs": resources.job_manager.jobs.counts(),
            "runtime": resources.job_manager.health,
        }

    return app


app = create_app()
