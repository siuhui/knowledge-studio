from fastapi import Request

from .trace import attach_trace_id, get_trace_id


async def trace_id_middleware(request: Request, call_next):
    attach_trace_id(request)
    response = await call_next(request)
    response.headers["X-Trace-Id"] = get_trace_id(request)
    return response
