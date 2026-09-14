from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..models import JournalAcces
from ..security import get_current_consumer
from ..utils import paginer

router = APIRouter(
    prefix="/api/v1",
    tags=["Journal des accès"],
    dependencies=[Depends(get_current_consumer)],
)


@router.get("/journal-acces", response_model=schemas.JournalAccesListResponse)
def lister_journal_acces(
    limite: int = Query(default=50, ge=1, le=500),
    decalage: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.JournalAccesListResponse:
    stmt = select(JournalAcces).order_by(JournalAcces.horodatage.desc(), JournalAcces.id.desc())
    total, resultats = paginer(db, stmt, limite, decalage)
    return schemas.JournalAccesListResponse(
        total=total,
        limite=limite,
        decalage=decalage,
        resultats=[schemas.JournalAccesEntree.model_validate(r) for r in resultats],
    )
