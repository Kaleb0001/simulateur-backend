from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, referentiels
from ..database import get_db
from ..security import get_current_consumer

router = APIRouter(
    prefix="/api/v1/referentiels",
    tags=["Référentiels"],
    dependencies=[Depends(get_current_consumer)],
)


@router.get("")
def lister_referentiels(db: Session = Depends(get_db)) -> dict:
    """Les listes fermées de ce système, avec le code à envoyer et le libellé
    à afficher : agences, professions (et leur catégorie), tranches de
    revenus mensuels, sources des fonds d'un dépôt, motifs d'un retrait,
    types de compte.

    Les agences et les professions sont lues en base : une ligne ajoutée aux
    tables `agences` ou `professions` apparaît ici sans redémarrage.
    """
    agences = db.scalars(select(models.Agence).order_by(models.Agence.ordre, models.Agence.nom))
    categories = db.scalars(
        select(models.CategorieProfession).order_by(models.CategorieProfession.ordre)
    )
    professions = db.scalars(
        select(models.Profession).order_by(models.Profession.ordre, models.Profession.libelle)
    )
    return {
        "agences": [
            {"code": a.code, "nom": a.nom, "ville": a.ville, "active": a.active} for a in agences
        ],
        "categories_profession": [{"code": c.code, "libelle": c.libelle} for c in categories],
        "professions": [
            {
                "code": p.code,
                "libelle": p.libelle,
                "categorie": p.categorie,
                "sans_employeur": p.sans_employeur,
            }
            for p in professions
        ],
        "tranches_revenus_mensuels": [
            {"code": code, "libelle": libelle, "minimum": minimum, "maximum": maximum}
            for code, (libelle, minimum, maximum) in referentiels.TRANCHES_REVENUS.items()
        ],
        "sources_fonds": [
            {"code": code, "libelle": libelle} for code, libelle in referentiels.SOURCES_FONDS.items()
        ],
        "motifs_retrait": [
            {"code": code, "libelle": libelle} for code, libelle in referentiels.MOTIFS_RETRAIT.items()
        ],
        "types_compte": [
            {"code": code, "libelle": libelle} for code, libelle in referentiels.TYPES_COMPTE.items()
        ],
    }
