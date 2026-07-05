import uuid
from collections.abc import MutableMapping
from typing import Any

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestIdMiddleware:
    """Pure ASGI middleware — extracts / injects X-Request-ID.

    Uses raw ASGI (not ``BaseHTTPMiddleware``) so OpenTelemetry
    context is preserved across the request boundary.
    ``BaseHTTPMiddleware`` uses ``anyio.TaskGroup`` internally which
    loses OTel context.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate request ID from headers
        headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
        request_id = ""
        for key, value in headers:
            if key.lower() == b"x-request-id":
                request_id = value.decode("latin-1")
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        # Bind to structlog context for this request
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Inject X-Request-ID into the response headers
        async def send_with_request_id(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                header_list: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                # Avoid duplicates
                if not any(k.lower() == b"x-request-id" for k, _ in header_list):
                    header_list.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = header_list
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
