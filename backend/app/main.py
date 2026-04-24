from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.bootstrap.startup import run_startup_tasks, shutdown_resources
from app.core.logging_config import setup_logging, get_logger
from app.api.orders import router as orders_router
from app.api.employees import router as employees_router
from app.api.documents import router as documents_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.cash import router as cash_router
from app.api.price_list import router as price_list_router
from app.api.settings import router as settings_router
from app.api.warehouse import router as warehouse_router
from app.api.form_history import router as form_history_router
from app.api.audit import router as audit_router
from app.config import settings
from app.core.request_context import client_ip_var, request_id_var, user_agent_var

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_startup_tasks()
    yield
    await shutdown_resources()


app = FastAPI(title="Павильоны МРЭО", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    forwarded_for = request.headers.get("x-forwarded-for")
    client_ip = (forwarded_for.split(",")[0].strip() if forwarded_for else None) or (
        request.client.host if request.client else None
    )
    request_id = request.headers.get("x-request-id") or str(uuid4())
    tokens = [
        request_id_var.set(request_id),
        client_ip_var.set(client_ip),
        user_agent_var.set(request.headers.get("user-agent")),
    ]
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(tokens[0])
        client_ip_var.reset(tokens[1])
        user_agent_var.reset(tokens[2])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Необработанная ошибка: %s", exc)
    detail = "Внутренняя ошибка сервера"
    err_str = str(exc).lower()
    if "duplicate key" in err_str or "unique constraint" in err_str:
        detail = "Конфликт данных (дубликат). Обновите страницу и повторите."
    elif "foreign key" in err_str or "violates foreign key" in err_str:
        detail = "Ошибка связи с данными (например, сотрудник не найден). Выйдите и войдите снова."
    elif "column" in err_str and "does not exist" in err_str:
        detail = "Устаревшая схема БД. Перезапустите сервис: systemctl restart eye_w"
    return JSONResponse(
        status_code=500,
        content={"detail": detail},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(orders_router)
app.include_router(cash_router)
app.include_router(documents_router)
app.include_router(price_list_router)
app.include_router(settings_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(warehouse_router)
app.include_router(form_history_router)
app.include_router(audit_router)


@app.get("/health")
def health():
    return {"status": "ok"}
