"""
Audit Service for logging data changes.

This service provides a simple interface for logging all data operations,
making it easy to add audit logging to any part of the application.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.audit.models import AuditLog


# Type aliases
EntityType = Literal[
    "client", "expense_bucket", "obligation", "schedule", "payment",
    "cash_event", "cash_account", "user", "integration_mapping"
]
ActionType = Literal[
    "create", "update", "delete", "sync_push", "sync_pull",
    "sync_error", "reconcile", "archive"
]
SourceType = Literal["api", "xero_sync", "quickbooks_sync", "system", "migration", "admin"]


class AuditService:
    """
    Service for logging audit events.

    Usage:
        audit = AuditService(db)
        await audit.log_create("client", client.id, {"name": "Acme"})
        await audit.log_update("client", client.id, {"name": ("Old", "New")})
        await audit.log_sync("client", client.id, "xero", "push", {"contact_id": "abc"})
    """

    def __init__(self, db: AsyncSession, user_id: Optional[str] = None, source: SourceType = "api"):
        self.db = db
        self.user_id = user_id
        self.source = source

    # ==========================================================================
    # Core Logging Methods
    # ==========================================================================

    async def log(
        self,
        entity_type: EntityType,
        entity_id: str,
        action: ActionType,
        field_name: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> AuditLog:
        """
        Log an audit event.

        Args:
            entity_type: Type of entity being changed
            entity_id: ID of the entity
            action: Type of action
            field_name: Optional specific field that changed
            old_value: Previous value (for updates/deletes)
            new_value: New value (for creates/updates)
            metadata: Additional context
            notes: Human-readable notes

        Returns:
            Created AuditLog
        """
        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            user_id=self.user_id,
            source=self.source,
            metadata=metadata,
            notes=notes,
        )

        self.db.add(log)
        # Don't commit here - let caller manage transaction
        return log

    # ==========================================================================
    # Convenience Methods
    # ==========================================================================

    async def log_create(
        self,
        entity_type: EntityType,
        entity_id: str,
        new_value: Dict[str, Any],
        notes: Optional[str] = None,
    ) -> AuditLog:
        """Log a create operation."""
        return await self.log(
            entity_type=entity_type,
            entity_id=entity_id,
            action="create",
            new_value=new_value,
            notes=notes,
        )

    async def log_update(
        self,
        entity_type: EntityType,
        entity_id: str,
        changes: Dict[str, tuple],
        notes: Optional[str] = None,
    ) -> List[AuditLog]:
        """
        Log an update operation.

        Args:
            changes: Dict mapping field names to (old_value, new_value) tuples

        Returns:
            List of AuditLogs (one per changed field)
        """
        logs = []
        for field_name, (old_value, new_value) in changes.items():
            if old_value != new_value:
                log = await self.log(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    action="update",
                    field_name=field_name,
                    old_value=old_value,
                    new_value=new_value,
                    notes=notes,
                )
                logs.append(log)
        return logs

    async def log_delete(
        self,
        entity_type: EntityType,
        entity_id: str,
        old_value: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> AuditLog:
        """Log a delete operation."""
        return await self.log(
            entity_type=entity_type,
            entity_id=entity_id,
            action="delete",
            old_value=old_value,
            notes=notes,
        )

    async def log_sync(
        self,
        entity_type: EntityType,
        entity_id: str,
        integration_type: str,
        direction: Literal["push", "pull"],
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Log a sync operation."""
        action = "sync_error" if error_message else f"sync_{direction}"
        return await self.log(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            metadata={
                "integration_type": integration_type,
                "direction": direction,
                **(details or {}),
            },
            notes=error_message,
        )

    async def log_archive(
        self,
        entity_type: EntityType,
        entity_id: str,
        notes: Optional[str] = None,
    ) -> AuditLog:
        """Log an archive operation."""
        return await self.log(
            entity_type=entity_type,
            entity_id=entity_id,
            action="archive",
            notes=notes,
        )

    # ==========================================================================
    # Query Methods
    # ==========================================================================

    async def get_entity_history(
        self,
        entity_type: EntityType,
        entity_id: str,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get audit history for an entity."""
        query = (
            select(AuditLog)
            .where(
                and_(
                    AuditLog.entity_type == entity_type,
                    AuditLog.entity_id == entity_id,
                )
            )
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_user_activity(
        self,
        user_id: str,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get recent activity for a user."""
        conditions = [AuditLog.user_id == user_id]
        if since:
            conditions.append(AuditLog.created_at >= since)

        query = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_sync_history(
        self,
        integration_type: str,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get sync history for an integration."""
        conditions = [
            AuditLog.action.in_(["sync_push", "sync_pull", "sync_error"])
        ]
        if since:
            conditions.append(AuditLog.created_at >= since)

        query = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        result = await self.db.execute(query)

        # Filter by integration_type in metadata
        logs = result.scalars().all()
        return [
            log for log in logs
            if log.metadata and log.metadata.get("integration_type") == integration_type
        ]


def create_audit_service(
    db: AsyncSession,
    user_id: Optional[str] = None,
    source: SourceType = "api"
) -> AuditService:
    """Factory function for creating AuditService instances."""
    return AuditService(db, user_id, source)
