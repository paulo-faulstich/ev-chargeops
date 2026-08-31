"""Persistence and audit for the resident context."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.identity.domain.resident_context import (
    ResidentContextNotActive,
    ResidentContextUnitNotFound,
    ResidentContextView,
)
from app.modules.identity.infrastructure.models import ResidentContextModel
from app.modules.organizations.infrastructure.models import UnitModel


class SqlAlchemyResidentContextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _unit(self, organization_id: UUID, unit_id: UUID) -> UnitModel:
        unit = (
            await self.session.execute(
                select(UnitModel).where(
                    UnitModel.id == unit_id,
                    UnitModel.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if unit is None:
            raise ResidentContextUnitNotFound
        return unit

    def _view(
        self, context: ResidentContextModel, unit: UnitModel
    ) -> ResidentContextView:
        expires_at = context.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return ResidentContextView(
            id=context.id,
            organization_id=context.organization_id,
            unit_id=context.unit_id,
            unit_code=unit.code,
            unit_name=unit.display_name,
            expires_at=expires_at,
        )

    async def enter(
        self,
        organization_id: UUID,
        manager_profile_id: UUID,
        unit_id: UUID,
        ttl_seconds: int,
    ) -> ResidentContextView:
        """Open the context and audit the entrance, in one commit."""
        unit = await self._unit(organization_id, unit_id)
        now = datetime.now(UTC)
        context = ResidentContextModel(
            id=uuid4(),
            organization_id=organization_id,
            manager_profile_id=manager_profile_id,
            unit_id=unit.id,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self.session.add(context)
        self.session.add(
            AuditEventModel(
                organization_id=organization_id,
                actor_profile_id=manager_profile_id,
                occurred_at=now,
                event_type="resident_context_entered",
                entity_type="unit",
                entity_id=unit.id,
                metadata_json={
                    "resident_context_id": str(context.id),
                    "unit_code": unit.code,
                    "expires_at": context.expires_at.isoformat(),
                },
            )
        )
        await self.session.commit()
        return self._view(context, unit)

    async def resolve_active(
        self,
        context_id: UUID,
        organization_id: UUID,
        manager_profile_id: UUID,
    ) -> ResidentContextView:
        """The context as the authorization dependency sees it, or nothing.

        A context issued to another manager or organization resolves exactly
        like one that never existed.
        """
        context = (
            await self.session.execute(
                select(ResidentContextModel).where(
                    ResidentContextModel.id == context_id,
                    ResidentContextModel.organization_id == organization_id,
                    ResidentContextModel.manager_profile_id == manager_profile_id,
                )
            )
        ).scalar_one_or_none()
        if context is None or context.exited_at is not None:
            raise ResidentContextNotActive
        expires_at = context.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise ResidentContextNotActive
        unit = await self._unit(context.organization_id, context.unit_id)
        return self._view(context, unit)

    async def exit(
        self,
        context_id: UUID,
        organization_id: UUID,
        manager_profile_id: UUID,
    ) -> None:
        """Close the context and audit the exit. Idempotent for an exited one."""
        context = (
            await self.session.execute(
                select(ResidentContextModel).where(
                    ResidentContextModel.id == context_id,
                    ResidentContextModel.organization_id == organization_id,
                    ResidentContextModel.manager_profile_id == manager_profile_id,
                )
            )
        ).scalar_one_or_none()
        if context is None:
            raise ResidentContextNotActive
        if context.exited_at is not None:
            return
        now = datetime.now(UTC)
        context.exited_at = now
        self.session.add(
            AuditEventModel(
                organization_id=organization_id,
                actor_profile_id=manager_profile_id,
                occurred_at=now,
                event_type="resident_context_exited",
                entity_type="unit",
                entity_id=context.unit_id,
                metadata_json={"resident_context_id": str(context.id)},
            )
        )
        await self.session.commit()
