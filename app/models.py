from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    type: Mapped[str] = mapped_column(String(16))  # "physique" | "morale"
    statut: Mapped[str] = mapped_column(String(16), default="actif", server_default="actif")

    # Identite
    nom: Mapped[str] = mapped_column(String(255))
    prenoms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_naissance: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_creation_entite: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationalite: Mapped[str] = mapped_column(String(120))
    # Personne physique : piece d'identite. Personne morale : RCCM + CUCE
    # (la piece d'identite est alors collectee sur chaque beneficiaire effectif).
    type_piece_identite: Mapped[str | None] = mapped_column(String(64), nullable=True)
    numero_piece_identite: Mapped[str | None] = mapped_column(String(64), nullable=True)
    numero_rccm: Mapped[str | None] = mapped_column(String(64), nullable=True)
    numero_cuce: Mapped[str | None] = mapped_column(String(64), nullable=True)
    adresse: Mapped[str] = mapped_column(String(500))
    telephone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agence: Mapped[str] = mapped_column(String(120))

    # Situation familiale
    situation_matrimoniale: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nom_conjoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nom_pere: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profession_pere: Mapped[str | None] = mapped_column(String(120), nullable=True)
    nom_mere: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profession_mere: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Coordonnees GPS
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Secteur et activite professionnelle
    secteur_activite: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profession: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employeur: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revenus_mensuels_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenus_mensuels_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    devise_revenus: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source_revenus: Mapped[str | None] = mapped_column(String(120), nullable=True)
    autres_sources_revenus: Mapped[str | None] = mapped_column(String(255), nullable=True)
    objet_relation: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Entree en relation
    canal_entree_relation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_entree_relation: Mapped[date | None] = mapped_column(Date, nullable=True)
    agent_traitant: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Auto-declaration PPE
    ppe_est_ppe_ou_proche: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    ppe_precisions: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    comptes: Mapped[list["Compte"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", order_by="Compte.id"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", order_by="Document.id"
    )
    beneficiaires_effectifs: Mapped[list["BeneficiaireEffectif"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", order_by="BeneficiaireEffectif.id"
    )
    autres_activites: Mapped[list["AutreActivite"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", order_by="AutreActivite.id"
    )


class AutreActivite(Base):
    """Activites supplementaires d'un client (une personne morale peut en
    exercer plusieurs). L'activite principale reste portee par les colonnes
    secteur_activite / profession de Client.
    """

    __tablename__ = "autres_activites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    secteur_activite: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    client: Mapped["Client"] = relationship(back_populates="autres_activites")


class BeneficiaireEffectif(Base):
    __tablename__ = "beneficiaires_effectifs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    nom_complet: Mapped[str] = mapped_column(String(255))
    date_naissance: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationalite: Mapped[str | None] = mapped_column(String(120), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pourcentage_detention: Mapped[float | None] = mapped_column(Float, nullable=True)
    type_piece_identite: Mapped[str | None] = mapped_column(String(64), nullable=True)
    numero_piece_identite: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fonction: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="beneficiaires_effectifs")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    type_document: Mapped[str] = mapped_column(String(64))
    numero: Mapped[str | None] = mapped_column(String(64), nullable=True)
    date_delivrance: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    autorite_emettrice: Mapped[str | None] = mapped_column(String(120), nullable=True)
    statut: Mapped[str] = mapped_column(String(32), default="valide", server_default="valide")
    reference_fichier: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="documents")


class Compte(Base):
    __tablename__ = "comptes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    numero_compte: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    type_compte: Mapped[str] = mapped_column(String(64))
    devise: Mapped[str] = mapped_column(String(8))
    solde: Mapped[float] = mapped_column(Float, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="comptes")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="compte",
        cascade="all, delete-orphan",
        order_by="Transaction.id",
        foreign_keys="Transaction.compte_id",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    compte_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), index=True)
    compte_destination_id: Mapped[int | None] = mapped_column(
        ForeignKey("comptes.id"), nullable=True, index=True
    )

    type_operation: Mapped[str] = mapped_column(String(16))  # depot | retrait | virement
    montant: Mapped[float] = mapped_column(Float)
    devise: Mapped[str] = mapped_column(String(8))
    canal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_operation: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    compte: Mapped["Compte"] = relationship(
        back_populates="transactions", foreign_keys=[compte_id]
    )
    compte_destination: Mapped["Compte | None"] = relationship(
        foreign_keys=[compte_destination_id]
    )


class JournalAcces(Base):
    __tablename__ = "journal_acces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    methode: Mapped[str] = mapped_column(String(8))
    chemin: Mapped[str] = mapped_column(String(255))
    statut_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consommateur: Mapped[str | None] = mapped_column(String(120), nullable=True)
