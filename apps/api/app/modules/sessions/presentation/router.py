from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.ingestion.presentation.schemas import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    HttpErrorResponse,
    to_camel,
)
from app.modules.sessions.application.assign_session import AssignSession
from app.modules.sessions.application.list_assignment_units import ListAssignmentUnits
from app.modules.sessions.application.list_sessions import ListSessions
from app.modules.sessions.domain.errors import (
    AssignmentForbidden,
    InvalidJustification,
    InvalidPeriod,
    SessionNotFound,
    UnitNotFound,
)
from app.modules.sessions.presentation.dependencies import (
    get_assign_session,
    get_list_assignment_units,
    get_list_sessions,
    manager_scope,
)
from app.modules.sessions.presentation.schemas import (
    AssignmentUnitListResponse,
    AssignmentUnitResponse,
    SessionAssignmentRequest,
    SessionAssignmentResponse,
    SessionListResponse,
    SessionResponse,
)


class StructuredValidationRoute(APIRoute):
    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as error:
                location = error.errors()[0].get("loc", ())
                field = to_camel(str(location[-1])) if location else "request"
                return validation_error(
                    code="INVALID_REQUEST",
                    message="Request validation failed.",
                    field=field,
                )

        return route_handler


router = APIRouter(
    prefix="/v1",
    tags=["sessions"],
    route_class=StructuredValidationRoute,
)

AUTH_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {
        "model": HttpErrorResponse,
        "description": "Invalid or missing bearer token.",
    },
    403: {
        "model": HttpErrorResponse,
        "description": "Organization membership and manager role required.",
    },
}


def validation_error(
    *,
    code: str,
    message: str,
    field: str,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=[ErrorDetail(field=field)],
        )
    )
    return JSONResponse(
        status_code=422,
        content=body.model_dump(by_alias=True),
    )


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    response_model_by_alias=True,
    responses={
        **AUTH_ERROR_RESPONSES,
        422: {
            "model": ErrorResponse,
            "description": "Invalid session filter.",
        },
    },
)
async def list_sessions(
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[ListSessions, Depends(get_list_sessions)],
    period: str | None = None,
    status: str | None = None,
) -> SessionListResponse | JSONResponse:
    try:
        sessions = await use_case.execute(scope, period=period, status=status)
    except InvalidPeriod:
        return validation_error(
            code="INVALID_PERIOD",
            message="Period must use YYYY-MM format.",
            field="period",
        )
    return SessionListResponse(
        items=[SessionResponse.from_view(session) for session in sessions]
    )


@router.get(
    "/assignment-units",
    response_model=AssignmentUnitListResponse,
    response_model_by_alias=True,
    responses=AUTH_ERROR_RESPONSES,
)
async def list_assignment_units(
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[
        ListAssignmentUnits,
        Depends(get_list_assignment_units),
    ],
) -> AssignmentUnitListResponse:
    units = await use_case.execute(scope)
    return AssignmentUnitListResponse(
        items=[AssignmentUnitResponse.from_view(unit) for unit in units]
    )


@router.put(
    "/sessions/{session_id}/assignment",
    response_model=SessionAssignmentResponse,
    response_model_by_alias=True,
    responses={
        **AUTH_ERROR_RESPONSES,
        404: {
            "model": HttpErrorResponse,
            "description": "Session or assignment unit not found.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Invalid assignment request.",
        },
    },
)
async def assign_session(
    session_id: UUID,
    request: SessionAssignmentRequest,
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[AssignSession, Depends(get_assign_session)],
) -> SessionAssignmentResponse | JSONResponse:
    try:
        result = await use_case.execute(
            scope,
            session_id,
            request.unit_id,
            request.justification,
        )
    except AssignmentForbidden as error:
        raise HTTPException(status_code=403, detail="Manager role required.") from error
    except SessionNotFound as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error
    except UnitNotFound as error:
        raise HTTPException(status_code=404, detail="Unit not found.") from error
    except InvalidJustification as error:
        return validation_error(
            code="INVALID_JUSTIFICATION",
            message="Justification is required.",
            field=error.field,
        )
    return SessionAssignmentResponse.from_result(result)
