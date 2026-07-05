"""Process Runtime — execution engine for Vela-generated processes."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UUID,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base


class ProcessInstance(Base):
    """A single execution of a Vela-generated process within a tenant."""

    __tablename__ = "process_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    service_instance_id = Column(UUID(as_uuid=True), ForeignKey("service_instances.id", ondelete="CASCADE"), nullable=True)

    # The process definition as JSON — blocks, connections, fields, pages
    # This is a snapshot taken at deployment time from Vela
    process_definition = Column(JSONB, nullable=False, default=dict)

    # Current state
    current_block_key = Column(String(100), nullable=True)  # which block is active
    state = Column(String(30), nullable=False, default="active")  # active, paused, completed, failed

    # Who started this
    started_by = Column(String(255), nullable=True)  # user identifier
    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Snapshot of all field values (filled during execution)
    field_values = Column(JSONB, nullable=False, default=dict)
    # { "block_key": { "field_key": value, ... }, ... }
    # e.g. { "b2": { "amount": 150000, "title": "Закупка столов" } }

    # Execution history (audit trail)
    execution_log = Column(JSONB, nullable=False, default=list)
    # [ { "block_key": "b1", "action": "enter", "timestamp": "...", "user": "..." }, ... ]


class ProcessTransition(Base):
    """A transition from one block to another during execution."""

    __tablename__ = "process_transitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id = Column(UUID(as_uuid=True), ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False)

    from_block = Column(String(100), nullable=False)
    to_block = Column(String(100), nullable=False)
    transition_label = Column(String(255), nullable=True)
    triggered_by = Column(String(255), nullable=True)  # user or "system"
    triggered_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # What field values were set/updated during this transition
    delta = Column(JSONB, nullable=True, default=dict)
