from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select


def paginer(db: Session, stmt: Select, limite: int, decalage: int) -> tuple[int, list]:
    """Applique offset/limit à une requête déjà filtrée/ordonnée et renvoie
    le total de résultats correspondant au filtre (hors pagination), pour
    construire les réponses de liste paginées de l'API.
    """
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    resultats = list(db.scalars(stmt.offset(decalage).limit(limite)).all())
    return total, resultats


def generer_external_id(prefixe: str, id_interne: int) -> str:
    """Construit un identifiant externe lisible, ex. CL-EXT-0001.

    S'appuie sur l'id auto-incrémenté attribué par la base après un flush,
    ce qui garantit l'unicité sans avoir besoin d'une table de compteurs
    dédiée (volume de démo, pas de forte concurrence en écriture).
    """
    return f"{prefixe}-{id_interne:04d}"


def generer_numero_compte(prefixe: str, id_interne: int) -> str:
    return f"{prefixe}-{id_interne:06d}"


def maintenant_utc() -> datetime:
    """Horodatage UTC naïf, cohérent avec les colonnes DateTime (elles-mêmes
    naïves) et avec func.now() côté SQLite.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
