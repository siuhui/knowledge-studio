from fastapi import APIRouter, BackgroundTasks, Query
from starlette.responses import RedirectResponse

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationMeta
from app.schemas.studio import StudioTaskCreate, StudioTaskDetail, StudioTaskItem
from app.services.studio import StudioService, execute_studio_task

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{knowledge_base_id}/studio/tasks",
    tags=["studio"],
)


@router.post("", response_model=ApiResponse[StudioTaskItem], status_code=201)
def create_task(
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    knowledge_base_id: str,
    payload: StudioTaskCreate,
) -> ApiResponse[StudioTaskItem]:
    task = StudioService.create_task(db, kb_id=knowledge_base_id, user_id=current_user.id, payload=payload)
    background_tasks.add_task(execute_studio_task, task.id)

    return ApiResponse[StudioTaskItem](
        code=ResponseCode.OK,
        message="Task created",
        data=StudioTaskItem.model_validate(task),
    )


@router.get("", response_model=PaginatedResponse[StudioTaskItem])
def list_tasks(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[StudioTaskItem]:
    tasks, total = StudioService.list_tasks(
        db, kb_id=knowledge_base_id, user_id=current_user.id, page=page, page_size=page_size
    )

    items = [StudioTaskItem.model_validate(t) for t in tasks]
    return PaginatedResponse[StudioTaskItem](
        code=ResponseCode.OK,
        message="success",
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
        ),
    )


@router.get("/{task_id}", response_model=ApiResponse[StudioTaskDetail])
def get_task(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    task_id: str,
) -> ApiResponse[StudioTaskDetail]:
    task = StudioService.get_task(db, task_id=task_id, kb_id=knowledge_base_id, user_id=current_user.id)
    return ApiResponse[StudioTaskDetail](
        code=ResponseCode.OK,
        message="success",
        data=StudioTaskDetail.model_validate(task),
    )


@router.get("/{task_id}/download")
def download_task(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    task_id: str,
) -> RedirectResponse:
    task = StudioService.get_task(db, task_id=task_id, kb_id=knowledge_base_id, user_id=current_user.id)
    url = StudioService.get_download_url(task)
    return RedirectResponse(url=url, status_code=302)


@router.delete("/{task_id}", response_model=ApiResponse[None])
def delete_task(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    task_id: str,
) -> ApiResponse[None]:
    StudioService.delete_task(db, task_id=task_id, kb_id=knowledge_base_id, user_id=current_user.id)
    return ApiResponse[None](code=ResponseCode.OK, message="Task deleted", data=None)
