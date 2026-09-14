"""Mise à niveau d'une base SQLite créée avec une version antérieure du modèle."""

import pytest
from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.migrations import adapter_schema

# Schéma « ancien » : sans les colonnes ajoutées depuis (RCCM/CUCE, situation
# familiale, coordonnées GPS, plage de revenus) et avec la pièce d'identité
# encore obligatoire.
ANCIEN_SCHEMA_CLIENTS = """
CREATE TABLE clients (
    id INTEGER NOT NULL PRIMARY KEY,
    external_id VARCHAR(32),
    type VARCHAR(16),
    statut VARCHAR(16) DEFAULT 'actif',
    nom VARCHAR(255),
    prenoms VARCHAR(255),
    nationalite VARCHAR(120),
    type_piece_identite VARCHAR(64) NOT NULL,
    numero_piece_identite VARCHAR(64) NOT NULL,
    adresse VARCHAR(500),
    telephone VARCHAR(32),
    email VARCHAR(255),
    agence VARCHAR(120),
    created_at DATETIME,
    updated_at DATETIME
)
"""


@pytest.fixture
def engine_ancienne_base(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'ancienne.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(ANCIEN_SCHEMA_CLIENTS))
        connection.execute(
            text("CREATE UNIQUE INDEX ix_clients_external_id ON clients (external_id)")
        )
        connection.execute(
            text(
                "INSERT INTO clients (id, external_id, type, statut, nom, prenoms, "
                "nationalite, type_piece_identite, numero_piece_identite, adresse, "
                "telephone, agence) VALUES (1, 'CL-EXT-0001', 'physique', 'actif', "
                "'Kodjo', 'Mensah', 'Togolaise', 'CNI', 'TG-0192837', 'Lomé', "
                "'+22890123456', 'Lomé-Centre')"
            )
        )
    return engine


def test_adaptation_ajoute_les_colonnes_manquantes(engine_ancienne_base):
    Base.metadata.create_all(bind=engine_ancienne_base)
    adapter_schema(engine_ancienne_base)

    colonnes = {c["name"] for c in inspect(engine_ancienne_base).get_columns("clients")}
    for attendue in (
        "numero_rccm",
        "numero_cuce",
        "situation_matrimoniale",
        "nom_pere",
        "latitude",
        "revenus_mensuels_min",
    ):
        assert attendue in colonnes


def test_adaptation_preserve_les_donnees(engine_ancienne_base):
    Base.metadata.create_all(bind=engine_ancienne_base)
    adapter_schema(engine_ancienne_base)

    with engine_ancienne_base.connect() as connection:
        ligne = connection.execute(
            text("SELECT external_id, nom, numero_piece_identite FROM clients")
        ).all()
    assert ligne == [("CL-EXT-0001", "Kodjo", "TG-0192837")]


def test_adaptation_leve_la_contrainte_not_null(engine_ancienne_base):
    """Une personne morale n'a pas de pièce d'identité : la colonne doit
    accepter NULL, ce que SQLite ne sait faire que via une reconstruction.
    """
    Base.metadata.create_all(bind=engine_ancienne_base)
    adapter_schema(engine_ancienne_base)

    with engine_ancienne_base.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clients (external_id, type, statut, nom, nationalite, "
                "numero_rccm, numero_cuce, adresse, telephone, agence) "
                "VALUES ('CL-EXT-0002', 'morale', 'actif', 'Sogex', 'Togolaise', "
                "'TG-2015-B-1', 'CUCE-1', 'Lomé', '+228', 'Lomé-Port')"
            )
        )


def test_adaptation_restaure_les_valeurs_par_defaut(engine_ancienne_base):
    """Sans valeur par défaut en base, une colonne obligatoire côté modèle
    resterait vide à l'insertion et la lecture échouerait ensuite.
    """
    Base.metadata.create_all(bind=engine_ancienne_base)
    adapter_schema(engine_ancienne_base)

    with engine_ancienne_base.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clients (external_id, type, nom, nationalite, "
                "type_piece_identite, numero_piece_identite, adresse, telephone, agence) "
                "VALUES ('CL-EXT-0003', 'physique', 'Ama', 'Togolaise', 'CNI', "
                "'TG-5555', 'Lomé', '+228', 'Lomé-Centre')"
            )
        )
        valeurs = connection.execute(
            text("SELECT created_at, statut FROM clients WHERE external_id = 'CL-EXT-0003'")
        ).one()

    assert valeurs[0] is not None
    assert valeurs[1] == "actif"


def test_adaptation_conserve_les_index(engine_ancienne_base):
    Base.metadata.create_all(bind=engine_ancienne_base)
    adapter_schema(engine_ancienne_base)

    index = {i["name"] for i in inspect(engine_ancienne_base).get_indexes("clients")}
    assert "ix_clients_external_id" in index


def test_adaptation_idempotente(engine_ancienne_base):
    Base.metadata.create_all(bind=engine_ancienne_base)
    adapter_schema(engine_ancienne_base)

    assert adapter_schema(engine_ancienne_base) == []


def test_adaptation_reajoute_une_colonne_supprimee(engine_ancienne_base):
    """Cas d'un simple ajout de colonne, sans reconstruction de table."""
    Base.metadata.create_all(bind=engine_ancienne_base)
    adapter_schema(engine_ancienne_base)

    with engine_ancienne_base.begin() as connection:
        connection.execute(text("ALTER TABLE clients DROP COLUMN numero_cuce"))

    operations = adapter_schema(engine_ancienne_base)

    assert operations == ["colonne « clients.numero_cuce » ajoutée"]
    colonnes = {c["name"] for c in inspect(engine_ancienne_base).get_columns("clients")}
    assert "numero_cuce" in colonnes
