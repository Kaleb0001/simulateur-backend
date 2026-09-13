from datetime import datetime
from enum import Enum

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import Settings
from ..utils import generer_external_id, paginer
from . import comptes as comptes_crud


def piece_identite_en_conflit(
    db: Session,
    type_piece: str,
    numero_piece: str,
    exclure_client_id: int | None = None,
) -> bool:
    """Un même couple (type, numéro) de pièce d'identité ne peut pas être
    utilisé par deux clients actifs à la fois (hygiène de données basique,
    pas une règle de conformité).
    """
    stmt = select(models.Client).where(
        models.Client.type_piece_identite == type_piece,
        models.Client.numero_piece_identite == numero_piece,
        models.Client.statut == schemas.StatutClient.actif.value,
    )
    if exclure_client_id is not None:
        stmt = stmt.where(models.Client.id != exclure_client_id)
    return db.scalar(stmt) is not None


def _verifier_unicite_piece_identite(
    db: Session, type_piece: str, numero_piece: str, exclure_client_id: int | None = None
) -> None:
    if piece_identite_en_conflit(db, type_piece, numero_piece, exclure_client_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Un client actif existe déjà avec ce type et ce numéro de "
                "pièce d'identité."
            ),
        )


def creer_client(
    db: Session, payload: schemas.ClientCreate, settings: Settings
) -> models.Client:
    _verifier_unicite_piece_identite(
        db, payload.piece_identite.type, payload.piece_identite.numero
    )

    client = models.Client(
        external_id="",
        type=payload.type.value,
        statut=payload.statut.value,
        nom=payload.nom,
        prenoms=payload.prenoms,
        date_naissance=payload.date_naissance,
        date_creation_entite=payload.date_creation_entite,
        nationalite=payload.nationalite,
        type_piece_identite=payload.piece_identite.type,
        numero_piece_identite=payload.piece_identite.numero,
        adresse=payload.adresse,
        telephone=payload.telephone,
        email=payload.email,
        agence=payload.agence,
        situation_matrimoniale=(
            payload.situation_matrimoniale.value if payload.situation_matrimoniale else None
        ),
        nom_conjoint=payload.nom_conjoint,
        nom_pere=payload.nom_pere,
        profession_pere=payload.profession_pere,
        nom_mere=payload.nom_mere,
        profession_mere=payload.profession_mere,
        latitude=payload.coordonnees_gps.latitude if payload.coordonnees_gps else None,
        longitude=payload.coordonnees_gps.longitude if payload.coordonnees_gps else None,
        secteur_activite=payload.activite_professionnelle.secteur_activite,
        profession=payload.activite_professionnelle.profession,
        employeur=payload.activite_professionnelle.employeur,
        revenus_mensuels_min=payload.activite_professionnelle.revenus_mensuels_min,
        revenus_mensuels_max=payload.activite_professionnelle.revenus_mensuels_max,
        devise_revenus=payload.activite_professionnelle.devise_revenus,
        source_revenus=payload.activite_professionnelle.source_revenus,
        autres_sources_revenus=payload.activite_professionnelle.autres_sources_revenus,
        objet_relation=payload.activite_professionnelle.objet_relation,
        canal_entree_relation=(
            payload.canal_entree_relation.value if payload.canal_entree_relation else None
        ),
        date_entree_relation=payload.date_entree_relation,
        agent_traitant=payload.agent_traitant,
        ppe_est_ppe_ou_proche=payload.auto_declaration_ppe.est_ppe_ou_proche,
        ppe_precisions=payload.auto_declaration_ppe.precisions,
    )
    db.add(client)
    db.flush()  # attribue client.id

    client.external_id = generer_external_id("CL-EXT", client.id)

    for doc_payload in payload.documents:
        _construire_document(client, doc_payload)
    for ben_payload in payload.beneficiaires_effectifs:
        _construire_beneficiaire(client, ben_payload)

    db.flush()  # attribue un id à chaque document/bénéficiaire nouvellement rattaché

    for document in client.documents:
        document.external_id = generer_external_id("DOC-EXT", document.id)
    for beneficiaire in client.beneficiaires_effectifs:
        beneficiaire.external_id = generer_external_id("BEN-EXT", beneficiaire.id)

    # Compte auto-créé (voir §2 du prompt) : un client n'existe jamais sans compte.
    comptes_crud.creer_compte(db, client, settings)

    db.commit()
    db.refresh(client)
    return client


def get_client_by_external_id(db: Session, external_id: str) -> models.Client | None:
    return db.scalar(select(models.Client).where(models.Client.external_id == external_id))


def lister_clients(
    db: Session,
    limite: int,
    decalage: int,
    type: schemas.TypeClient | None = None,
    agence: str | None = None,
    modifie_depuis: datetime | None = None,
) -> tuple[int, list[models.Client]]:
    stmt = select(models.Client)

    if type is not None:
        stmt = stmt.where(models.Client.type == type.value)
    if agence is not None:
        stmt = stmt.where(models.Client.agence == agence)
    if modifie_depuis is not None:
        stmt = stmt.where(models.Client.updated_at >= modifie_depuis)

    stmt = stmt.order_by(models.Client.updated_at.asc())

    return paginer(db, stmt, limite, decalage)


def mettre_a_jour_client(
    db: Session, client: models.Client, payload: schemas.ClientUpdate
) -> models.Client:
    donnees = payload.model_dump(exclude_unset=True)

    nouveau_type_piece = client.type_piece_identite
    nouveau_numero_piece = client.numero_piece_identite
    if "piece_identite" in donnees and donnees["piece_identite"] is not None:
        nouveau_type_piece = donnees["piece_identite"]["type"]
        nouveau_numero_piece = donnees["piece_identite"]["numero"]

    if (nouveau_type_piece, nouveau_numero_piece) != (
        client.type_piece_identite,
        client.numero_piece_identite,
    ):
        _verifier_unicite_piece_identite(
            db, nouveau_type_piece, nouveau_numero_piece, exclure_client_id=client.id
        )
    client.type_piece_identite = nouveau_type_piece
    client.numero_piece_identite = nouveau_numero_piece

    if "activite_professionnelle" in donnees and donnees["activite_professionnelle"] is not None:
        activite = donnees.pop("activite_professionnelle")
        for champ, valeur in activite.items():
            setattr(client, champ, valeur)
    else:
        donnees.pop("activite_professionnelle", None)

    if "auto_declaration_ppe" in donnees and donnees["auto_declaration_ppe"] is not None:
        ppe = donnees.pop("auto_declaration_ppe")
        client.ppe_est_ppe_ou_proche = ppe["est_ppe_ou_proche"]
        client.ppe_precisions = ppe["precisions"]
    else:
        donnees.pop("auto_declaration_ppe", None)

    if "coordonnees_gps" in donnees:
        coordonnees = donnees.pop("coordonnees_gps")
        client.latitude = coordonnees["latitude"] if coordonnees else None
        client.longitude = coordonnees["longitude"] if coordonnees else None

    donnees.pop("piece_identite", None)

    for champ, valeur in donnees.items():
        # Les champs de type Enum (type, statut, canal_entree_relation...)
        # doivent être stockés comme de simples chaînes en base.
        setattr(client, champ, valeur.value if isinstance(valeur, Enum) else valeur)

    db.commit()
    db.refresh(client)
    return client


# --------------------------------------------------------------------------
# Documents (sous-ressource)
# --------------------------------------------------------------------------


def _construire_document(client: models.Client, payload: schemas.DocumentCreate) -> models.Document:
    document = models.Document(
        client_id=client.id,
        external_id="",
        type_document=payload.type_document,
        numero=payload.numero,
        date_delivrance=payload.date_delivrance,
        date_expiration=payload.date_expiration,
        autorite_emettrice=payload.autorite_emettrice,
        statut=payload.statut.value,
        reference_fichier=payload.reference_fichier,
    )
    client.documents.append(document)
    return document


def ajouter_document(
    db: Session, client: models.Client, payload: schemas.DocumentCreate
) -> models.Document:
    document = _construire_document(client, payload)
    db.flush()
    document.external_id = generer_external_id("DOC-EXT", document.id)
    db.commit()
    db.refresh(document)
    return document


def get_document(db: Session, client: models.Client, document_external_id: str) -> models.Document | None:
    return db.scalar(
        select(models.Document).where(
            models.Document.client_id == client.id,
            models.Document.external_id == document_external_id,
        )
    )


def mettre_a_jour_document(
    db: Session, document: models.Document, payload: schemas.DocumentUpdate
) -> models.Document:
    donnees = payload.model_dump(exclude_unset=True)
    for champ, valeur in donnees.items():
        setattr(document, champ, valeur.value if isinstance(valeur, Enum) else valeur)
    db.commit()
    db.refresh(document)
    return document


def supprimer_document(db: Session, document: models.Document) -> None:
    db.delete(document)
    db.commit()


# --------------------------------------------------------------------------
# Bénéficiaires effectifs (sous-ressource)
# --------------------------------------------------------------------------


def _construire_beneficiaire(
    client: models.Client, payload: schemas.BeneficiaireEffectifCreate
) -> models.BeneficiaireEffectif:
    beneficiaire = models.BeneficiaireEffectif(
        client_id=client.id,
        external_id="",
        nom_complet=payload.nom_complet,
        date_naissance=payload.date_naissance,
        nationalite=payload.nationalite,
        adresse=payload.adresse,
        pourcentage_detention=payload.pourcentage_detention,
        type_piece_identite=payload.type_piece_identite,
        numero_piece_identite=payload.numero_piece_identite,
        fonction=payload.fonction,
    )
    client.beneficiaires_effectifs.append(beneficiaire)
    return beneficiaire


def ajouter_beneficiaire(
    db: Session, client: models.Client, payload: schemas.BeneficiaireEffectifCreate
) -> models.BeneficiaireEffectif:
    beneficiaire = _construire_beneficiaire(client, payload)
    db.flush()
    beneficiaire.external_id = generer_external_id("BEN-EXT", beneficiaire.id)
    db.commit()
    db.refresh(beneficiaire)
    return beneficiaire


def get_beneficiaire(
    db: Session, client: models.Client, beneficiaire_external_id: str
) -> models.BeneficiaireEffectif | None:
    return db.scalar(
        select(models.BeneficiaireEffectif).where(
            models.BeneficiaireEffectif.client_id == client.id,
            models.BeneficiaireEffectif.external_id == beneficiaire_external_id,
        )
    )


def mettre_a_jour_beneficiaire(
    db: Session,
    beneficiaire: models.BeneficiaireEffectif,
    payload: schemas.BeneficiaireEffectifUpdate,
) -> models.BeneficiaireEffectif:
    donnees = payload.model_dump(exclude_unset=True)
    for champ, valeur in donnees.items():
        setattr(beneficiaire, champ, valeur)
    db.commit()
    db.refresh(beneficiaire)
    return beneficiaire


def supprimer_beneficiaire(db: Session, beneficiaire: models.BeneficiaireEffectif) -> None:
    db.delete(beneficiaire)
    db.commit()


# --------------------------------------------------------------------------
# Conversion vers les schémas de lecture
# --------------------------------------------------------------------------


def to_read(client: models.Client) -> schemas.ClientRead:
    return schemas.ClientRead(
        external_id=client.external_id,
        type=schemas.TypeClient(client.type),
        statut=schemas.StatutClient(client.statut),
        nom=client.nom,
        prenoms=client.prenoms,
        date_naissance=client.date_naissance,
        date_creation_entite=client.date_creation_entite,
        nationalite=client.nationalite,
        piece_identite=schemas.PieceIdentite(
            type=client.type_piece_identite, numero=client.numero_piece_identite
        ),
        adresse=client.adresse,
        telephone=client.telephone,
        email=client.email,
        agence=client.agence,
        situation_matrimoniale=(
            schemas.SituationMatrimoniale(client.situation_matrimoniale)
            if client.situation_matrimoniale
            else None
        ),
        nom_conjoint=client.nom_conjoint,
        nom_pere=client.nom_pere,
        profession_pere=client.profession_pere,
        nom_mere=client.nom_mere,
        profession_mere=client.profession_mere,
        coordonnees_gps=(
            schemas.CoordonneesGPS(latitude=client.latitude, longitude=client.longitude)
            if client.latitude is not None and client.longitude is not None
            else None
        ),
        activite_professionnelle=schemas.ActiviteProfessionnelle(
            secteur_activite=client.secteur_activite,
            profession=client.profession,
            employeur=client.employeur,
            revenus_mensuels_min=client.revenus_mensuels_min,
            revenus_mensuels_max=client.revenus_mensuels_max,
            devise_revenus=client.devise_revenus,
            source_revenus=client.source_revenus,
            autres_sources_revenus=client.autres_sources_revenus,
            objet_relation=client.objet_relation,
        ),
        beneficiaires_effectifs=[
            schemas.BeneficiaireEffectifRead.model_validate(b)
            for b in client.beneficiaires_effectifs
        ],
        documents=[schemas.DocumentRead.model_validate(d) for d in client.documents],
        canal_entree_relation=(
            schemas.CanalEntreeRelation(client.canal_entree_relation)
            if client.canal_entree_relation
            else None
        ),
        date_entree_relation=client.date_entree_relation,
        agent_traitant=client.agent_traitant,
        auto_declaration_ppe=schemas.AutoDeclarationPPE(
            est_ppe_ou_proche=client.ppe_est_ppe_ou_proche,
            precisions=client.ppe_precisions,
        ),
        comptes=[comptes_crud.to_read(c) for c in client.comptes],
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


def to_summary(client: models.Client) -> schemas.ClientSummary:
    return schemas.ClientSummary(
        external_id=client.external_id,
        type=schemas.TypeClient(client.type),
        statut=schemas.StatutClient(client.statut),
        nom=client.nom,
        prenoms=client.prenoms,
        nationalite=client.nationalite,
        agence=client.agence,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )
