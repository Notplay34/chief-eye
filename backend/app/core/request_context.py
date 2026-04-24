"""Per-request context for audit and diagnostics."""
from contextvars import ContextVar
from typing import Optional


request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
client_ip_var: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)
user_agent_var: ContextVar[Optional[str]] = ContextVar("user_agent", default=None)


def current_request_context() -> dict:
    return {
        "request_id": request_id_var.get(),
        "client_ip": client_ip_var.get(),
        "user_agent": user_agent_var.get(),
    }
