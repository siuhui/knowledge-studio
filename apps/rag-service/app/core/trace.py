import uuid

from fastapi import Request


def attach_trace_id(request: Request) -> str:
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    return trace_id


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))
