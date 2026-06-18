from fastapi import FastAPI

from app.core.trace import RequestIdMiddleware


def register_middlewares(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
