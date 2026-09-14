from datetime import datetime
from enum import Enum

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import Settings
from ..utils import generer_external_id, maintenant_utc, paginer
from . import comptes as comptes_crud


def _existe_client_actif(db: Session, exclure_client_id: int | None, *conditions) -> bool:
    stmt = select(models.Client).where(
        models.Client.statut == schemas.StatutClient.actif.value, *conditions
    )
    if exclure_client_id is not None:
        stmt = stmt.where(models.Client.id != exclure_client_id)
    return db.scalar(stmt) is not None


def _verifier_unicite_identifiants(
    db: Session,
    type_client: str,
    type_piece: str | None,
    numero_piece: str | None,
    numero_rccm: str | None,
    numero_cuce: str | None,
    exclure_client_id: int | None = None,
) -> None:
    """Deux clients actifs ne peuvent pas partager le même identifiant légal
    (pièce d'identité pour une personne physique, RCCM ou CUCE pour une
    personne morale) — hygiène de données basique, pas une règle de conformité.
    """
    if type_client == schemas.TypeClient.physique.value:
        if (
            type_piece
            and numero_piece
            and _existe_client_actif(
                db,
                exclure_client_id,
                models.Client.type_piece_identite == type_piece,
                models.Client.numero_piece_identite == numero_piece,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Un client actif existe déjà avec ce type et ce numéro de "
                    "pièce d'identité."
                ),
            )
        return

    if numero_rccm and _existe_client_actif(
        db, exclure_client_id, models.Client.numero_rccm == numero_rccm
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un client actif existe déjà avec ce numéro RCCM.",
        )
    if numero_cuce and _existe_client_actif(
        db, exclure_client_id, models.Client.numero_cuce == numero_cuce
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un client actif existe déjà avec ce numéro CUCE.",
        )


def _toucher_client(client: models.Client) -> None:
    """Fait remonter la date de modification du client lorsqu'une de ses
    sous-ressources change. Sans cela, l'ajout d'un document ou d'un
    bénéficiaire effectif ne touche que la table enfant : le dossier
    n'apparaîtrait pas dans un `GET /clients?modifie_depuis=...`, et un
    consommateur qui synchronise de façon incrémentale manquerait la mise à
    jour.
    """
    client.updated_at = maintenant_utc()


def creer_client(
    db: Session, payload: schemas.ClientCreate, settings: Settings
) -> models.Client:
    _verifier_unicite_identifiants(
        db,
        type_client=payload.type.value,
        type_piece=payload.piece_identite.type if payload.piece_identite else None,
        numero_piece=payload.piece_identite.numero if payload.piece_identite else None,
        numero_rccm=payload.numero_rccm,
        numero_cuce=payload.numero_cuce,
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
        type_piece_identite=payload.piece_identite.type if payload.piece_identite else None,
        numero_piece_identite=payload.piece_identite.numero if payload.piece_identite else None,
        numero_rccm=payload.numero_rccm,
        numero_cuce=payload.numero_cuce,
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

    # external_id reçoit un espace réservé distinct par élément (et non "" pour
    # tous) : lorsque plusieurs documents/bénéficiaires sont créés dans le même
    # flush, SQLAlchemy regroupe leurs INSERT — une valeur "" partagée par au
    # moins deux lignes violerait la contrainte d'unicité avant même qu'on ait
    # pu leur attribuer leur véritable external_id.
    for index, doc_payload in enumerate(payload.documents):
        document = _construire_document(client, doc_payload)
        document.external_id = f"_tmp_doc_{index}"
    for index, ben_payload in enumerate(payload.beneficiaires_effectifs):
        beneficiaire = _construire_beneficiaire(client, ben_payload)
        beneficiaire.external_id = f"_tmp_ben_{index}"

    _remplacer_autres_activites(client, payload.activite_professionnelle.autres_activites)

    db.flush()  # attribue un id à chaque document/bénéficiaire nouvellement rattaché

    for document in client.documents:
        document.external_id = generer_external_id("DOC-EXT", document.id)
    for beneficiaire in client.beneficiaires_effectifs:
        beneficiaire.external_id = generer_external_id("BEN-EXT", beneficiaire.id)

    # Compte auto-créé (voir §2 du prompt) : un client n'existe jamais sans
    # compte. payload.compte_initial permet d'en choisir le type/la devise/le
    # solde initial ; les champs non fournis reprennent les valeurs par
    # défaut configurées via variables d'environnement.
    comptes_crud.creer_compte(db, client, settings, payload.compte_initial)

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
    recherche: str | None = None,
) -> tuple[int, list[models.Client]]:
    stmt = select(models.Client)

    if type is not None:
        stmt = stmt.where(models.Client.type == type.value)
    if agence is not None:
        stmt = stmt.where(models.Client.agence == agence)
    if modifie_depuis is not None:
        stmt = stmt.where(models.Client.updated_at >= modifie_depuis)
    if recherche:
        # Recherche partielle, insensible à la casse, sur les champs qu'un
        # agent a sous la main : nom, prénoms et numéro d'identifiant légal
        # (pièce d'identité pour une personne physique, RCCM/CUCE pour une
        # personne morale).
        motif = f"%{recherche}%"
        stmt = stmt.where(
            or_(
                models.Client.nom.ilike(motif),
                models.Client.prenoms.ilike(motif),
                models.Client.numero_piece_identite.ilike(motif),
                models.Client.numero_rccm.ilike(motif),
                models.Client.numero_cuce.ilike(motif),
            )
        )

    stmt = stmt.order_by(models.Client.updated_at.asc())

    return paginer(db, stmt, limite, decalage)


def mettre_a_jour_client(
    db: Session, client: models.Client, payload: schemas.ClientUpdate
) -> models.Client:
    donnees = payload.model_dump(exclude_unset=True)

    if "piece_identite" in donnees:
        piece = donnees.pop("piece_identite")
        client.type_piece_identite = piece["type"] if piece else None
        client.numero_piece_identite = piece["numero"] if piece else None

    if "activite_professionnelle" in donnees and donnees["activite_professionnelle"] is not None:
        activite = donnees.pop("activite_professionnelle")
        autres_activites = activite.pop("autres_activites", None)
        for champ, valeur in activite.items():
            setattr(client, champ, valeur)
        if autres_activites is not None:
            _remplacer_autres_activites(
                client, [schemas.AutreActivite(**a) for a in autres_activites]
            )
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

    for champ, valeur in donnees.items():
        # Les champs de type Enum (type, statut, canal_entree_relation...)
        # doivent être stockés comme de simples chaînes en base.
        setattr(client, champ, valeur.value if isinstance(valeur, Enum) else valeur)

    _verifier_dossier_coherent(client)
    _verifier_unicite_identifiants(
        db,
        type_client=client.type,
        type_piece=client.type_piece_identite,
        numero_piece=client.numero_piece_identite,
        numero_rccm=client.numero_rccm,
        numero_cuce=client.numero_cuce,
        exclure_client_id=client.id,
    )

    db.commit()
    db.refresh(client)
    return client


def _verifier_dossier_coherent(client: models.Client) -> None:
    """Après une mise à jour partielle, le dossier doit rester cohérent :
    une personne physique garde sa pièce d'identité, une personne morale son
    RCCM et son CUCE.
    """
    piece_identite = (
        schemas.PieceIdentite(
            type=client.type_piece_identite, numero=client.numero_piece_identite
        )
        if client.type_piece_identite and client.numero_piece_identite
        else None
    )
    try:
        schemas.verifier_identifiants_selon_type(
            schemas.TypeClient(client.type),
            piece_identite,
            client.numero_rccm,
            client.numero_cuce,
        )
    except ValueError as erreur:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erreur)
        ) from erreur


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
    _toucher_client(client)
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
    _toucher_client(document.client)
    db.commit()
    db.refresh(document)
    return document


def supprimer_document(db: Session, document: models.Document) -> None:
    _toucher_client(document.client)
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
    _toucher_client(client)
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
    _toucher_client(beneficiaire.client)
    db.commit()
    db.refresh(beneficiaire)
    return beneficiaire


def supprimer_beneficiaire(db: Session, beneficiaire: models.BeneficiaireEffectif) -> None:
    _toucher_client(beneficiaire.client)
    db.delete(beneficiaire)
    db.commit()


# --------------------------------------------------------------------------
# Autres activités
# --------------------------------------------------------------------------


def _remplacer_autres_activites(
    client: models.Client, activites: list[schemas.AutreActivite]
) -> None:
    """Les activités supplémentaires sont de simples libellés sans cycle de
    vie propre (contrairement aux documents ou aux bénéficiaires effectifs) :
    elles sont remplacées en bloc, ce qui correspond au fonctionnement d'un
    formulaire à champs répétables.
    """
    client.autres_activites.clear()
    for activite in activites:
        client.autres_activites.append(
            models.AutreActivite(
                secteur_activite=activite.secteur_activite,
                description=activite.description,
            )
        )


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
        piece_identite=(
            schemas.PieceIdentite(
                type=client.type_piece_identite, numero=client.numero_piece_identite
            )
            if client.type_piece_identite and client.numero_piece_identite
            else None
        ),
        numero_rccm=client.numero_rccm,
        numero_cuce=client.numero_cuce,
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
            autres_activites=[
                schemas.AutreActivite(
                    secteur_activite=activite.secteur_activite,
                    description=activite.description,
                )
                for activite in client.autres_activites
            ],
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
