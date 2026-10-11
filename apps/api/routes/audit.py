import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import AuditEventDB

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Ledger"])


@router.get("/events")
async def list_audit_events(
    limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    query = select(AuditEventDB).order_by(desc(AuditEventDB.created_at)).limit(limit)
    res = await db.execute(query)
    events = res.scalars().all()
    return [
        {
            "event_id": e.event_id,
            "actor": e.actor,
            "event_type": e.event_type,
            "correlation_id": e.correlation_id,
            "entity_id": e.entity_id,
            "entity_type": e.entity_type,
            "payload": json.loads(e.payload_json) if e.payload_json else {},
            "timestamp": e.created_at,
        }
        for e in events
    ]
