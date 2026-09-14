from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------


class TypeClient(str, Enum):
    physique = "physique"
    morale = "morale"


class StatutClient(str, Enum):
    actif = "actif"
    cloture = "cloture"


class CanalEntreeRelation(str, Enum):
    agence = "agence"
    agent = "agent"
    en_ligne = "en_ligne"


class StatutDocument(str, Enum):
    valide = "valide"
    expire = "expire"
    en_attente_renouvellement = "en_attente_renouvellement"


class TypeOperation(str, Enum):
    depot = "depot"
    retrait = "retrait"
    virement = "virement"


class SituationMatrimoniale(str, Enum):
    celibataire = "celibataire"
    marie = "marie"
    divorce = "divorce"
    veuf = "veuf"
    union_libre = "union_libre"


# --------------------------------------------------------------------------
# Blocs imbriques reutilisables
# --------------------------------------------------------------------------


class PieceIdentite(BaseModel):
    type: str
    numero: str


class CoordonneesGPS(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class AutreActivite(BaseModel):
    """Activité supplémentaire : une personne morale peut en exercer plusieurs
    (l'activité principale reste portée par `secteur_activite`/`profession`).
    """

    secteur_activite: str
    description: str | None = None


class ActiviteProfessionnelle(BaseModel):
    secteur_activite: str | None = None
    profession: str | None = None
    autres_activites: list[AutreActivite] = Field(default_factory=list)
    employeur: str | None = None
    revenus_mensuels_min: float | None = Field(default=None, ge=0)
    revenus_mensuels_max: float | None = Field(default=None, ge=0)
    devise_revenus: str | None = None
    source_revenus: str | None = None
    autres_sources_revenus: str | None = None
    objet_relation: str | None = None

    @model_validator(mode="after")
    def _verifier_plage_revenus(self) -> "ActiviteProfessionnelle":
        if (
            self.revenus_mensuels_min is not None
            and self.revenus_mensuels_max is not None
            and self.revenus_mensuels_min > self.revenus_mensuels_max
        ):
            raise ValueError(
                "revenus_mensuels_min ne peut pas être supérieur à revenus_mensuels_max."
            )
        return self


class AutoDeclarationPPE(BaseModel):
    est_ppe_ou_proche: bool = False
    precisions: str | None = None


def verifier_identifiants_selon_type(
    type_client: "TypeClient",
    piece_identite: PieceIdentite | None,
    numero_rccm: str | None,
    numero_cuce: str | None,
) -> None:
    """Une personne physique s'identifie par sa pièce d'identité ; une personne
    morale par son numéro RCCM et son numéro CUCE — sa pièce d'identité n'a pas
    de sens à ce niveau, ce sont ses bénéficiaires effectifs qui portent
    chacun la leur. Lève ValueError si la combinaison est incohérente.
    """
    if type_client == TypeClient.physique:
        if piece_identite is None:
            raise ValueError(
                "piece_identite est obligatoire pour un client de type physique."
            )
        if numero_rccm or numero_cuce:
            raise ValueError(
                "numero_rccm et numero_cuce ne s'appliquent qu'aux clients de type morale."
            )
    else:
        if not numero_rccm or not numero_cuce:
            raise ValueError(
                "numero_rccm et numero_cuce sont obligatoires pour un client de type morale."
            )
        if piece_identite is not None:
            raise ValueError(
                "piece_identite ne s'applique pas à un client de type morale : la pièce "
                "d'identité est collectée sur chaque bénéficiaire effectif."
            )


# --------------------------------------------------------------------------
# Bénéficiaires effectifs
# --------------------------------------------------------------------------


class BeneficiaireEffectifBase(BaseModel):
    nom_complet: str
    date_naissance: date | None = None
    nationalite: str | None = None
    adresse: str | None = None
    pourcentage_detention: float | None = Field(default=None, ge=0, le=100)
    type_piece_identite: str | None = None
    numero_piece_identite: str | None = None
    fonction: str | None = None


class BeneficiaireEffectifCreate(BeneficiaireEffectifBase):
    pass


class BeneficiaireEffectifUpdate(BaseModel):
    nom_complet: str | None = None
    date_naissance: date | None = None
    nationalite: str | None = None
    adresse: str | None = None
    pourcentage_detention: float | None = Field(default=None, ge=0, le=100)
    type_piece_identite: str | None = None
    numero_piece_identite: str | None = None
    fonction: str | None = None


class BeneficiaireEffectifRead(BeneficiaireEffectifBase):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


class DocumentBase(BaseModel):
    type_document: str
    numero: str | None = None
    date_delivrance: date | None = None
    date_expiration: date | None = None
    autorite_emettrice: str | None = None
    statut: StatutDocument = StatutDocument.valide
    reference_fichier: str | None = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    type_document: str | None = None
    numero: str | None = None
    date_delivrance: date | None = None
    date_expiration: date | None = None
    autorite_emettrice: str | None = None
    statut: StatutDocument | None = None
    reference_fichier: str | None = None


class DocumentRead(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Comptes
# --------------------------------------------------------------------------


class CompteCreate(BaseModel):
    """Utilisé pour l'ouverture d'un compte additionnel, ou pour personnaliser
    le compte auto-créé à la création d'un client (voir
    `ClientBase.compte_initial`).

    Les champs non fournis reprennent les valeurs par défaut configurées
    via variables d'environnement.
    """

    type_compte: str | None = None
    devise: str | None = None
    solde_initial: float | None = None


class CompteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    numero_compte: str
    type_compte: str
    devise: str
    solde: float
    client_external_id: str
    created_at: datetime
    updated_at: datetime


class ComptesListResponse(BaseModel):
    total: int
    limite: int
    decalage: int
    resultats: list[CompteRead]


# --------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------


class TransactionCreate(BaseModel):
    type_operation: TypeOperation
    montant: float = Field(gt=0)
    devise: str | None = None
    canal: str | None = None
    date_operation: datetime | None = None
    compte_destination_external_id: str | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    compte_external_id: str
    client_external_id: str
    compte_destination_external_id: str | None = None
    client_destination_external_id: str | None = None
    type_operation: TypeOperation
    montant: float
    devise: str
    canal: str | None = None
    date_operation: datetime
    created_at: datetime
    updated_at: datetime


class TransactionsListResponse(BaseModel):
    total: int
    limite: int
    decalage: int
    resultats: list[TransactionRead]


# --------------------------------------------------------------------------
# Clients
# --------------------------------------------------------------------------


class ClientBase(BaseModel):
    type: TypeClient
    nom: str
    prenoms: str | None = None
    date_naissance: date | None = None
    date_creation_entite: date | None = None
    nationalite: str
    piece_identite: PieceIdentite | None = None
    numero_rccm: str | None = None
    numero_cuce: str | None = None
    adresse: str
    telephone: str
    email: str | None = None
    agence: str

    situation_matrimoniale: SituationMatrimoniale | None = None
    nom_conjoint: str | None = None
    nom_pere: str | None = None
    profession_pere: str | None = None
    nom_mere: str | None = None
    profession_mere: str | None = None

    coordonnees_gps: CoordonneesGPS | None = None

    activite_professionnelle: ActiviteProfessionnelle = Field(
        default_factory=ActiviteProfessionnelle
    )
    beneficiaires_effectifs: list[BeneficiaireEffectifCreate] = Field(default_factory=list)
    documents: list[DocumentCreate] = Field(default_factory=list)

    canal_entree_relation: CanalEntreeRelation | None = None
    date_entree_relation: date | None = None
    agent_traitant: str | None = None

    auto_declaration_ppe: AutoDeclarationPPE = Field(default_factory=AutoDeclarationPPE)

    compte_initial: CompteCreate | None = Field(
        default=None,
        description=(
            "Permet de choisir le type/la devise/le solde initial du compte "
            "auto-créé pour ce client ; les champs non fournis reprennent "
            "les valeurs par défaut configurées via variables d'environnement."
        ),
    )

    @model_validator(mode="after")
    def _verifier_identifiants_selon_type(self) -> "ClientBase":
        verifier_identifiants_selon_type(
            self.type, self.piece_identite, self.numero_rccm, self.numero_cuce
        )
        return self


class ClientCreate(ClientBase):
    statut: StatutClient = StatutClient.actif


class ClientUpdate(BaseModel):
    """Mise a jour partielle : seuls les champs fournis sont modifies.

    Pour les documents et bénéficiaires effectifs, préférer les
    sous-ressources dédiées (POST/PUT/DELETE) qui permettent des mises à
    jour indépendantes du reste du dossier ; les inclure ici les
    remplacerait intégralement.
    """

    type: TypeClient | None = None
    statut: StatutClient | None = None
    nom: str | None = None
    prenoms: str | None = None
    date_naissance: date | None = None
    date_creation_entite: date | None = None
    nationalite: str | None = None
    piece_identite: PieceIdentite | None = None
    numero_rccm: str | None = None
    numero_cuce: str | None = None
    adresse: str | None = None
    telephone: str | None = None
    email: str | None = None
    agence: str | None = None

    situation_matrimoniale: SituationMatrimoniale | None = None
    nom_conjoint: str | None = None
    nom_pere: str | None = None
    profession_pere: str | None = None
    nom_mere: str | None = None
    profession_mere: str | None = None

    coordonnees_gps: CoordonneesGPS | None = None

    activite_professionnelle: ActiviteProfessionnelle | None = None

    canal_entree_relation: CanalEntreeRelation | None = None
    date_entree_relation: date | None = None
    agent_traitant: str | None = None

    auto_declaration_ppe: AutoDeclarationPPE | None = None


class ClientRead(BaseModel):
    external_id: str
    type: TypeClient
    statut: StatutClient
    nom: str
    prenoms: str | None = None
    date_naissance: date | None = None
    date_creation_entite: date | None = None
    nationalite: str
    piece_identite: PieceIdentite | None = None
    numero_rccm: str | None = None
    numero_cuce: str | None = None
    adresse: str
    telephone: str
    email: str | None = None
    agence: str

    situation_matrimoniale: SituationMatrimoniale | None = None
    nom_conjoint: str | None = None
    nom_pere: str | None = None
    profession_pere: str | None = None
    nom_mere: str | None = None
    profession_mere: str | None = None

    coordonnees_gps: CoordonneesGPS | None = None

    activite_professionnelle: ActiviteProfessionnelle
    beneficiaires_effectifs: list[BeneficiaireEffectifRead]
    documents: list[DocumentRead]

    canal_entree_relation: CanalEntreeRelation | None = None
    date_entree_relation: date | None = None
    agent_traitant: str | None = None

    auto_declaration_ppe: AutoDeclarationPPE

    comptes: list[CompteRead]

    created_at: datetime
    updated_at: datetime


class ClientSummary(BaseModel):
    external_id: str
    type: TypeClient
    statut: StatutClient
    nom: str
    prenoms: str | None = None
    nationalite: str
    agence: str
    created_at: datetime
    updated_at: datetime


class ClientsListResponse(BaseModel):
    total: int
    limite: int
    decalage: int
    resultats: list[ClientSummary]


# --------------------------------------------------------------------------
# Journal des acces
# --------------------------------------------------------------------------


class JournalAccesEntree(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horodatage: datetime
    methode: str
    chemin: str
    statut_code: int | None = None
    consommateur: str | None = None


class JournalAccesListResponse(BaseModel):
    total: int
    limite: int
    decalage: int
    resultats: list[JournalAccesEntree]
