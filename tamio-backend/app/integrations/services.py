"""
Integration Mapping Service for centralized external system ID management.

This service provides a unified interface for managing relationships between
Tamio entities and external system identifiers (Xero, QuickBooks, etc.).
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.integrations.models import IntegrationMapping, IntegrationConnection


# Type aliases
EntityType = Literal["client", "expense_bucket", "obligation", "cash_account", "user"]
IntegrationType = Literal["xero", "quickbooks", "stripe"]
SyncStatus = Literal["synced", "pending_push", "pending_pull", "conflict", "error"]


class IntegrationMappingService:
    """
    Service for managing integration mappings.

    This service centralizes all external ID management, providing:
    - Create/update/delete mappings
    - Query by entity or external ID
    - Sync status management
    - Batch operations for efficiency
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # Create Operations
    # ==========================================================================

    async def create_mapping(
        self,
        entity_type: EntityType,
        entity_id: str,
        integration_type: IntegrationType,
        external_id: str,
        external_type: str,
        sync_status: SyncStatus = "synced",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IntegrationMapping:
        """
        Create a new integration mapping.

        Args:
            entity_type: Type of Tamio entity (client, expense_bucket, etc.)
            entity_id: ID of the Tamio entity
            integration_type: Type of integration (xero, quickbooks, etc.)
            external_id: ID in the external system
            external_type: Type in external system (contact, invoice, etc.)
            sync_status: Initial sync status
            metadata: Optional integration-specific metadata

        Returns:
            The created IntegrationMapping

        Raises:
            ValueError: If mapping already exists
        """
        # Check for existing mapping
        existing = await self.get_mapping_for_entity(
            entity_type, entity_id, integration_type
        )
        if existing:
            raise ValueError(
                f"Mapping already exists for {entity_type}/{entity_id} "
                f"to {integration_type}"
            )

        mapping = IntegrationMapping(
            entity_type=entity_type,
            entity_id=entity_id,
            integration_type=integration_type,
            external_id=external_id,
            external_type=external_type,
            sync_status=sync_status,
            last_synced_at=datetime.now(timezone.utc) if sync_status == "synced" else None,
            extra_data=metadata,
        )

        self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)

        return mapping

    async def create_or_update_mapping(
        self,
        entity_type: EntityType,
        entity_id: str,
        integration_type: IntegrationType,
        external_id: str,
        external_type: str,
        sync_status: SyncStatus = "synced",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IntegrationMapping:
        """
        Create a mapping or update if it already exists.

        This is useful for upsert scenarios during sync operations.
        """
        existing = await self.get_mapping_for_entity(
            entity_type, entity_id, integration_type
        )

        if existing:
            # Update existing mapping
            existing.external_id = external_id
            existing.external_type = external_type
            existing.sync_status = sync_status
            if sync_status == "synced":
                existing.last_synced_at = datetime.now(timezone.utc)
            if metadata:
                existing.extra_data = {**(existing.extra_data or {}), **metadata}

            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        return await self.create_mapping(
            entity_type=entity_type,
            entity_id=entity_id,
            integration_type=integration_type,
            external_id=external_id,
            external_type=external_type,
            sync_status=sync_status,
            metadata=metadata,
        )

    # ==========================================================================
    # Query Operations
    # ==========================================================================

    async def get_mapping_for_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
        integration_type: Optional[IntegrationType] = None,
    ) -> Optional[IntegrationMapping]:
        """
        Get mapping for a Tamio entity.

        Args:
            entity_type: Type of Tamio entity
            entity_id: ID of the Tamio entity
            integration_type: Optional filter by integration type

        Returns:
            IntegrationMapping or None
        """
        conditions = [
            IntegrationMapping.entity_type == entity_type,
            IntegrationMapping.entity_id == entity_id,
        ]
        if integration_type:
            conditions.append(IntegrationMapping.integration_type == integration_type)

        query = select(IntegrationMapping).where(and_(*conditions))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_mappings_for_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
    ) -> List[IntegrationMapping]:
        """
        Get all mappings for a Tamio entity (across all integrations).

        Args:
            entity_type: Type of Tamio entity
            entity_id: ID of the Tamio entity

        Returns:
            List of IntegrationMappings
        """
        query = select(IntegrationMapping).where(
            and_(
                IntegrationMapping.entity_type == entity_type,
                IntegrationMapping.entity_id == entity_id,
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_entity_for_external(
        self,
        integration_type: IntegrationType,
        external_id: str,
        external_type: Optional[str] = None,
    ) -> Optional[IntegrationMapping]:
        """
        Find Tamio entity by external system ID.

        Args:
            integration_type: Type of integration
            external_id: ID in the external system
            external_type: Optional filter by external type

        Returns:
            IntegrationMapping or None
        """
        conditions = [
            IntegrationMapping.integration_type == integration_type,
            IntegrationMapping.external_id == external_id,
        ]
        if external_type:
            conditions.append(IntegrationMapping.external_type == external_type)

        query = select(IntegrationMapping).where(and_(*conditions))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_mappings_by_status(
        self,
        integration_type: IntegrationType,
        sync_status: SyncStatus,
        limit: int = 100,
    ) -> List[IntegrationMapping]:
        """
        Get mappings by sync status (useful for finding pending syncs).

        Args:
            integration_type: Type of integration
            sync_status: Status to filter by
            limit: Maximum number of results

        Returns:
            List of IntegrationMappings
        """
        query = (
            select(IntegrationMapping)
            .where(
                and_(
                    IntegrationMapping.integration_type == integration_type,
                    IntegrationMapping.sync_status == sync_status,
                )
            )
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ==========================================================================
    # Update Operations
    # ==========================================================================

    async def update_sync_status(
        self,
        mapping_id: str,
        status: SyncStatus,
        error_message: Optional[str] = None,
    ) -> IntegrationMapping:
        """
        Update sync status for a mapping.

        Args:
            mapping_id: ID of the mapping
            status: New sync status
            error_message: Optional error message (for error status)

        Returns:
            Updated IntegrationMapping
        """
        query = select(IntegrationMapping).where(IntegrationMapping.id == mapping_id)
        result = await self.db.execute(query)
        mapping = result.scalar_one_or_none()

        if not mapping:
            raise ValueError(f"Mapping not found: {mapping_id}")

        mapping.sync_status = status
        if status == "synced":
            mapping.last_synced_at = datetime.now(timezone.utc)
            mapping.last_error = None
        elif status == "error":
            mapping.last_error = error_message

        await self.db.commit()
        await self.db.refresh(mapping)

        return mapping

    async def mark_synced(
        self,
        entity_type: EntityType,
        entity_id: str,
        integration_type: IntegrationType,
    ) -> Optional[IntegrationMapping]:
        """
        Mark a mapping as synced (convenience method).
        """
        mapping = await self.get_mapping_for_entity(
            entity_type, entity_id, integration_type
        )
        if mapping:
            return await self.update_sync_status(mapping.id, "synced")
        return None

    async def mark_pending_push(
        self,
        entity_type: EntityType,
        entity_id: str,
        integration_type: Optional[IntegrationType] = None,
    ) -> List[IntegrationMapping]:
        """
        Mark mapping(s) as pending push after entity changes.

        If integration_type is None, marks all integrations as pending.
        """
        mappings = await self.get_all_mappings_for_entity(entity_type, entity_id)

        updated = []
        for mapping in mappings:
            if integration_type is None or mapping.integration_type == integration_type:
                mapping.sync_status = "pending_push"
                updated.append(mapping)

        if updated:
            await self.db.commit()
            for m in updated:
                await self.db.refresh(m)

        return updated

    # ==========================================================================
    # Delete Operations
    # ==========================================================================

    async def delete_mapping(
        self,
        entity_type: EntityType,
        entity_id: str,
        integration_type: IntegrationType,
    ) -> bool:
        """
        Delete a mapping.

        Returns:
            True if deleted, False if not found
        """
        mapping = await self.get_mapping_for_entity(
            entity_type, entity_id, integration_type
        )
        if mapping:
            await self.db.delete(mapping)
            await self.db.commit()
            return True
        return False

    async def delete_all_mappings_for_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
    ) -> int:
        """
        Delete all mappings for an entity (when entity is deleted).

        Returns:
            Number of mappings deleted
        """
        mappings = await self.get_all_mappings_for_entity(entity_type, entity_id)
        count = len(mappings)

        for mapping in mappings:
            await self.db.delete(mapping)

        if count > 0:
            await self.db.commit()

        return count


class IntegrationConnectionService:
    """
    Service for managing integration connections (OAuth tokens, etc.).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_connection(
        self,
        user_id: str,
        integration_type: IntegrationType,
    ) -> Optional[IntegrationConnection]:
        """Get a user's connection to an integration."""
        query = select(IntegrationConnection).where(
            and_(
                IntegrationConnection.user_id == user_id,
                IntegrationConnection.integration_type == integration_type,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_active_connection(
        self,
        user_id: str,
        integration_type: IntegrationType,
    ) -> Optional[IntegrationConnection]:
        """Get active connection (non-expired, non-revoked)."""
        connection = await self.get_connection(user_id, integration_type)
        if connection and connection.is_active:
            return connection
        return None

    async def create_or_update_connection(
        self,
        user_id: str,
        integration_type: IntegrationType,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
        realm_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IntegrationConnection:
        """Create or update an integration connection."""
        existing = await self.get_connection(user_id, integration_type)

        if existing:
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.token_expires_at = token_expires_at
            existing.tenant_id = tenant_id
            existing.realm_id = realm_id
            existing.status = "active"
            if metadata:
                existing.extra_data = {**(existing.extra_data or {}), **metadata}

            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        connection = IntegrationConnection(
            user_id=user_id,
            integration_type=integration_type,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            tenant_id=tenant_id,
            realm_id=realm_id,
            status="active",
            metadata=metadata,
        )

        self.db.add(connection)
        await self.db.commit()
        await self.db.refresh(connection)

        return connection

    async def revoke_connection(
        self,
        user_id: str,
        integration_type: IntegrationType,
    ) -> bool:
        """Revoke a connection (user disconnected)."""
        connection = await self.get_connection(user_id, integration_type)
        if connection:
            connection.status = "revoked"
            connection.access_token = None
            connection.refresh_token = None
            await self.db.commit()
            return True
        return False

    async def update_tokens(
        self,
        user_id: str,
        integration_type: IntegrationType,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ) -> Optional[IntegrationConnection]:
        """Update tokens after refresh."""
        connection = await self.get_connection(user_id, integration_type)
        if connection:
            connection.access_token = access_token
            if refresh_token:
                connection.refresh_token = refresh_token
            if token_expires_at:
                connection.token_expires_at = token_expires_at
            connection.status = "active"
            await self.db.commit()
            await self.db.refresh(connection)
            return connection
        return None
