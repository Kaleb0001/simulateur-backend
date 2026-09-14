"""Mise à niveau automatique d'une base SQLite existante.

Le schéma est créé au démarrage par `create_all`, qui ne sait que créer les
tables manquantes : une base ouverte avec une version antérieure du modèle
garde son ancien schéma, et l'API plante dès la première requête
(« no such column: clients.numero_rccm »). Ce module rattrape l'écart au
démarrage, sans perdre les données.

Deux écarts sont traités :

- colonne présente dans le modèle mais absente de la base → ajoutée ;
- colonne NOT NULL en base alors que le modèle l'autorise vide → la table
  est reconstruite, SQLite ne sachant pas lever une contrainte NOT NULL.

Ce n'est pas un remplaçant d'Alembic : une colonne retirée du modèle est
laissée en place, et une colonne obligatoire ajoutée sans valeur par défaut
est signalée plutôt qu'ajoutée (elle serait impossible à remplir pour les
lignes existantes). C'est le minimum pour qu'une base de démonstration
survive à l'évolution du modèle pendant le hackathon.
"""

import logging

from sqlalchemy import Column, Connection, Engine, Table, inspect, text
from sqlalchemy.schema import CreateColumn

from .database import Base

logger = logging.getLogger(__name__)


def adapter_schema(engine: Engine) -> list[str]:
    """Aligne les tables déjà présentes en base sur le modèle courant.

    Renvoie la liste des opérations effectuées, pour affichage au démarrage.
    """
    if engine.dialect.name != "sqlite":
        return []

    inspecteur = inspect(engine)
    tables_existantes = set(inspecteur.get_table_names())
    operations: list[str] = []

    for table in Base.metadata.sorted_tables:
        if table.name not in tables_existantes:
            continue  # create_all vient de la créer avec le schéma à jour

        colonnes_base = {
            colonne["name"]: colonne for colonne in inspecteur.get_columns(table.name)
        }

        if _reconstruction_necessaire(table, colonnes_base):
            _reconstruire_table(engine, table, colonnes_base)
            operations.append(f"table « {table.name} » reconstruite")
            continue

        for colonne in table.columns:
            if colonne.name in colonnes_base:
                continue
            if not colonne.nullable and colonne.server_default is None:
                logger.warning(
                    "Colonne « %s.%s » obligatoire et sans valeur par défaut : "
                    "impossible de l'ajouter automatiquement à une base existante.",
                    table.name,
                    colonne.name,
                )
                continue
            _ajouter_colonne(engine, table, colonne)
            operations.append(f"colonne « {table.name}.{colonne.name} » ajoutée")

    for operation in operations:
        logger.info("Schéma mis à niveau : %s", operation)

    return operations


def _reconstruction_necessaire(table: Table, colonnes_base: dict) -> bool:
    """SQLite ne sait ni lever une contrainte NOT NULL, ni poser une valeur
    par défaut sur une colonne existante : dans ces deux cas, seule une
    reconstruction de la table permet de rattraper l'écart.

    Une valeur par défaut manquante n'est pas anodine : la base laisserait la
    colonne vide à l'insertion alors que le modèle la déclare obligatoire, et
    la lecture échouerait ensuite à la sérialisation.
    """
    for colonne in table.columns:
        if colonne.name not in colonnes_base:
            continue
        colonne_base = colonnes_base[colonne.name]
        if colonne.nullable and not colonne_base["nullable"]:
            return True
        if colonne.server_default is not None and colonne_base["default"] is None:
            return True
    return False


def _ajouter_colonne(engine: Engine, table: Table, colonne: Column) -> None:
    definition = CreateColumn(colonne).compile(engine).string
    with engine.begin() as connection:
        connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {definition}'))


def _reconstruire_table(engine: Engine, table: Table, colonnes_base: dict) -> None:
    """Recrée la table au schéma courant et y recopie les données existantes.

    Les noms de tables et de colonnes proviennent du modèle SQLAlchemy, pas
    d'une entrée utilisateur.
    """
    communes = [colonne for colonne in table.columns if colonne.name in colonnes_base]
    cibles = ", ".join(f'"{colonne.name}"' for colonne in communes)
    sources = ", ".join(_expression_source(engine, colonne) for colonne in communes)
    ancienne = f"_ancienne_{table.name}"

    with engine.connect() as connection:
        # Sans ce mode, SQLite réécrit les clés étrangères des autres tables
        # pour les faire pointer vers la table renommée, qui va disparaître.
        connection.exec_driver_sql("PRAGMA legacy_alter_table=ON")
        try:
            for index in _index_de(connection, table.name):
                connection.execute(text(f'DROP INDEX "{index}"'))
            connection.execute(text(f'ALTER TABLE "{table.name}" RENAME TO "{ancienne}"'))
            table.create(bind=connection)
            connection.execute(
                text(f'INSERT INTO "{table.name}" ({cibles}) SELECT {sources} FROM "{ancienne}"')
            )
            connection.execute(text(f'DROP TABLE "{ancienne}"'))
            connection.commit()
        finally:
            connection.exec_driver_sql("PRAGMA legacy_alter_table=OFF")


def _expression_source(engine: Engine, colonne: Column) -> str:
    """Reprend la valeur existante, en lui substituant la valeur par défaut de
    la colonne lorsqu'elle est vide alors que le modèle ne l'autorise plus
    (colonne devenue obligatoire depuis la création de la base).
    """
    reference = f'"{colonne.name}"'
    if colonne.nullable or colonne.server_default is None:
        return reference

    compilateur = engine.dialect.ddl_compiler(engine.dialect, None)
    defaut = compilateur.get_column_default_string(colonne)
    return reference if defaut is None else f"COALESCE({reference}, {defaut})"


def _index_de(connection: Connection, nom_table: str) -> list[str]:
    resultat = connection.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = :table AND sql IS NOT NULL"
        ),
        {"table": nom_table},
    )
    return [ligne[0] for ligne in resultat]
