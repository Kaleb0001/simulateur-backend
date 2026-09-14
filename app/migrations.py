"""Mise à niveau automatique d'une base existante (PostgreSQL ou SQLite).

Le schéma est créé au démarrage par `create_all`, qui ne sait que créer les
tables manquantes : une base ouverte avec une version antérieure du modèle
garde son ancien schéma, et l'API plante dès la première requête
(« no such column: clients.numero_rccm »). Ce module rattrape l'écart au
démarrage, sans perdre les données.

Deux écarts sont traités :

- colonne présente dans le modèle mais absente de la base → ajoutée ;
- colonne NOT NULL en base alors que le modèle l'autorise vide, valeur par
  défaut manquante, ou clé étrangère déclarée par le modèle mais absente de
  la base → sous PostgreSQL, un ALTER TABLE suffit ; sous SQLite, qui ne
  sait modifier ni l'une ni l'autre, la table est reconstruite.

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


def adapter_schema(engine: Engine, cles_etrangeres: bool = True) -> list[str]:
    """Aligne les tables déjà présentes en base sur le modèle courant.

    Hors SQLite, une clé étrangère n'est posée que si les données existantes
    la respectent : `cles_etrangeres=False` la remet à un second appel, fait
    après la normalisation des référentiels (voir app/main.py). SQLite ne
    vérifiant pas les données à la reconstruction, l'option y est sans effet.

    Renvoie la liste des opérations effectuées, pour affichage au démarrage.
    """
    inspecteur = inspect(engine)
    tables_existantes = set(inspecteur.get_table_names())
    operations: list[str] = []

    for table in Base.metadata.sorted_tables:
        if table.name not in tables_existantes:
            continue  # create_all vient de la créer avec le schéma à jour

        colonnes_base = {
            colonne["name"]: colonne for colonne in inspecteur.get_columns(table.name)
        }

        if engine.dialect.name == "sqlite":
            if _reconstruction_necessaire(table, colonnes_base) or _cles_etrangeres_manquantes(
                table, inspecteur
            ):
                _reconstruire_table(engine, table, colonnes_base)
                operations.append(f"table « {table.name} » reconstruite")
                continue
        else:
            operations += _modifier_colonnes(engine, table, colonnes_base, cles_etrangeres)

        ajoutees = False
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
            ajoutees = True
            operations.append(f"colonne « {table.name}.{colonne.name} » ajoutée")

        if engine.dialect.name != "sqlite" and cles_etrangeres and ajoutees:
            operations += _ajouter_cles_etrangeres(engine, table, inspect(engine))

    for operation in operations:
        logger.info("Schéma mis à niveau : %s", operation)

    return operations


def _modifier_colonnes(
    engine: Engine, table: Table, colonnes_base: dict, cles_etrangeres: bool
) -> list[str]:
    """Équivalent PostgreSQL de la reconstruction SQLite : lève les NOT NULL
    que le modèle n'impose plus, pose les valeurs par défaut manquantes et
    ajoute les clés étrangères absentes, sans recopier la table."""
    operations: list[str] = []
    compilateur = engine.dialect.ddl_compiler(engine.dialect, None)
    with engine.begin() as connection:
        for colonne in table.columns:
            colonne_base = colonnes_base.get(colonne.name)
            if colonne_base is None:
                continue
            if colonne.nullable and not colonne_base["nullable"]:
                connection.execute(
                    text(f'ALTER TABLE "{table.name}" ALTER COLUMN "{colonne.name}" DROP NOT NULL')
                )
                operations.append(f"colonne « {table.name}.{colonne.name} » rendue facultative")
            if colonne.server_default is not None and colonne_base["default"] is None:
                defaut = compilateur.get_column_default_string(colonne)
                connection.execute(
                    text(
                        f'ALTER TABLE "{table.name}" ALTER COLUMN "{colonne.name}" '
                        f"SET DEFAULT {defaut}"
                    )
                )
                operations.append(
                    f"valeur par défaut de « {table.name}.{colonne.name} » restaurée"
                )
    if cles_etrangeres:
        operations += _ajouter_cles_etrangeres(engine, table, inspect(engine))
    return operations


def _ajouter_cles_etrangeres(engine: Engine, table: Table, inspecteur) -> list[str]:
    """Ajoute (hors SQLite) les clés étrangères du modèle absentes en base.
    Une clé que les données existantes violent est signalée, pas imposée."""
    en_base = {
        (tuple(cle["constrained_columns"]), cle["referred_table"])
        for cle in inspecteur.get_foreign_keys(table.name)
    }
    colonnes_base = {colonne["name"] for colonne in inspecteur.get_columns(table.name)}
    operations: list[str] = []
    for cle in table.foreign_key_constraints:
        colonnes = tuple(colonne.name for colonne in cle.columns)
        if (colonnes, cle.referred_table.name) in en_base or not set(colonnes) <= colonnes_base:
            continue
        locales = ", ".join(f'"{nom}"' for nom in colonnes)
        references = ", ".join(f'"{element.column.name}"' for element in cle.elements)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        f'ALTER TABLE "{table.name}" ADD FOREIGN KEY ({locales}) '
                        f'REFERENCES "{cle.referred_table.name}" ({references})'
                    )
                )
        except Exception as erreur:  # données existantes incompatibles
            logger.warning(
                "Clé étrangère %s.%s → %s non ajoutée : %s",
                table.name,
                ", ".join(colonnes),
                cle.referred_table.name,
                erreur,
            )
            continue
        operations.append(
            f"clé étrangère « {table.name}.{', '.join(colonnes)} » ajoutée"
        )
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


def _cles_etrangeres_manquantes(table: Table, inspecteur) -> bool:
    en_base = {
        (tuple(cle["constrained_columns"]), cle["referred_table"])
        for cle in inspecteur.get_foreign_keys(table.name)
    }
    for cle in table.foreign_key_constraints:
        colonnes = tuple(colonne.name for colonne in cle.columns)
        if (colonnes, cle.referred_table.name) not in en_base:
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


# Anciennes valeurs libres de `comptes.type_compte`, ramenées aux types fermés.
# « Dépôt à terme » est un compte immobilisé : il devient un compte bloqué.
_TYPES_COMPTE_HISTORIQUES = {
    "courant": "courant",
    "compte courant": "courant",
    "epargne": "epargne",
    "épargne": "epargne",
    "compte epargne": "epargne",
    "compte épargne": "epargne",
    "bloque": "bloque",
    "bloqué": "bloque",
    "compte bloque": "bloque",
    "compte bloqué": "bloque",
    "depot a terme": "bloque",
    "dépôt à terme": "bloque",
}


# Colonnes retirées du modèle, supprimées de la base au démarrage.
_COLONNES_RETIREES = {
    "clients": ["source_revenus"],
    # L'adresse et les événements d'une connexion vivent dans son abonnement.
    "connexions": ["url_reception", "evenements"],
}


def supprimer_colonnes_retirees(engine: Engine) -> list[str]:
    """Supprime les colonnes qu'un champ retiré du modèle a laissées en base
    (PostgreSQL, ou SQLite 3.35 ou plus récent)."""
    inspecteur = inspect(engine)
    operations: list[str] = []
    for table, colonnes in _COLONNES_RETIREES.items():
        if table not in inspecteur.get_table_names():
            continue
        existantes = {c["name"] for c in inspecteur.get_columns(table)}
        for colonne in colonnes:
            if colonne not in existantes:
                continue
            with engine.begin() as connection:
                connection.execute(text(f'ALTER TABLE "{table}" DROP COLUMN "{colonne}"'))
            operations.append(f"colonne « {table}.{colonne} » supprimée")
    for operation in operations:
        logger.info("Schéma mis à niveau : %s", operation)
    return operations


def peupler_referentiels(engine: Engine) -> list[str]:
    """Insère les agences, catégories et professions initiales qui manquent
    en base. Une ligne existante n'est jamais modifiée : les tables peuvent
    être enrichies ou corrigées à la main."""
    from . import referentiels

    lignes = {
        "agences": [
            {"code": code, "nom": nom, "ville": ville, "active": True, "ordre": ordre}
            for ordre, (code, (nom, ville)) in enumerate(referentiels.AGENCES.items())
        ],
        "categories_profession": [
            {"code": code, "libelle": libelle, "ordre": ordre}
            for ordre, (code, libelle) in enumerate(referentiels.CATEGORIES_PROFESSION.items())
        ],
        "professions": [
            {
                "code": code,
                "libelle": libelle,
                "categorie": categorie,
                "sans_employeur": categorie in referentiels.CATEGORIES_SANS_EMPLOYEUR,
                "ordre": ordre,
            }
            for ordre, (code, (libelle, categorie)) in enumerate(referentiels.PROFESSIONS.items())
        ],
    }
    operations: list[str] = []
    with engine.begin() as connection:
        for table, valeurs in lignes.items():
            existants = {ligne[0] for ligne in connection.execute(text(f'SELECT code FROM "{table}"'))}
            manquants = [valeur for valeur in valeurs if valeur["code"] not in existants]
            if not manquants:
                continue
            colonnes = list(manquants[0])
            connection.execute(
                text(
                    f'INSERT INTO "{table}" ({", ".join(colonnes)}) '
                    f'VALUES ({", ".join(":" + c for c in colonnes)})'
                ),
                manquants,
            )
            operations.append(f"{len(manquants)} ligne(s) ajoutée(s) à « {table} »")
    for operation in operations:
        logger.info("Référentiels : %s", operation)
    return operations


def normaliser_referentiels(engine: Engine) -> list[str]:
    """Ramène aux listes fermées les valeurs saisies librement avant elles :
    types de compte, agences, professions et revenus mensuels (tranche
    déduite des anciens montants)."""
    return (
        normaliser_types_compte(engine)
        + _normaliser_agences(engine)
        + _normaliser_activites(engine)
    )


# Anciens noms d'agence sans équivalent exact dans la table.
_AGENCES_HISTORIQUES = {"lome": "lome_centre"}


def _normaliser_agences(engine: Engine) -> list[str]:
    """Remplace le nom d'agence saisi librement par le code de l'agence. Un
    nom inconnu devient une nouvelle agence plutôt que d'être perdu."""
    from . import referentiels

    inspecteur = inspect(engine)
    if not {"clients", "agences"} <= set(inspecteur.get_table_names()):
        return []
    operations: list[str] = []
    with engine.begin() as connection:
        agences = {
            code: nom for code, nom in connection.execute(text("SELECT code, nom FROM agences"))
        }
        par_nom = {referentiels._code(nom): code for code, nom in agences.items()}
        valeurs = [ligne[0] for ligne in connection.execute(text("SELECT DISTINCT agence FROM clients"))]
        for valeur in valeurs:
            if valeur is None or valeur in agences:
                continue
            cle = referentiels._code(valeur)
            cible = par_nom.get(cle) or _AGENCES_HISTORIQUES.get(cle)
            if cible is None:
                cible = cle or "inconnue"
                connection.execute(
                    text(
                        "INSERT INTO agences (code, nom, active, ordre) "
                        "VALUES (:code, :nom, :active, 999)"
                    ),
                    {"code": cible, "nom": valeur.strip() or cible, "active": True},
                )
                agences[cible] = valeur
                par_nom[cle] = cible
                operations.append(f"agence « {valeur} » créée")
            connection.execute(
                text("UPDATE clients SET agence = :cible WHERE agence = :valeur"),
                {"cible": cible, "valeur": valeur},
            )
            operations.append(f"agence « {valeur} » convertie en « {cible} »")
    for operation in operations:
        logger.info("Données mises à niveau : %s", operation)
    return operations


def _normaliser_activites(engine: Engine) -> list[str]:
    from . import referentiels

    inspecteur = inspect(engine)
    if "clients" not in inspecteur.get_table_names():
        return []
    colonnes = {c["name"] for c in inspecteur.get_columns("clients")}
    if "tranche_revenus_mensuels" not in colonnes:
        return []

    operations: list[str] = []
    with engine.begin() as connection:
        connues = {ligne[0] for ligne in connection.execute(text("SELECT code FROM professions"))}
        lignes = connection.execute(
            text(
                "SELECT id, profession, tranche_revenus_mensuels, revenus_mensuels_min, "
                "revenus_mensuels_max FROM clients"
            )
        ).all()
        for identifiant, profession, tranche, minimum, maximum in lignes:
            nouvelles: dict = {}
            if profession and profession not in connues:
                nouvelles["profession"] = referentiels.profession_pour_texte(profession)
            if tranche is None and (minimum is not None or maximum is not None):
                code = referentiels.tranche_pour_montant(maximum if maximum is not None else minimum)
                _, borne_min, borne_max = referentiels.TRANCHES_REVENUS[code]
                nouvelles.update(
                    tranche_revenus_mensuels=code,
                    revenus_mensuels_min=borne_min,
                    revenus_mensuels_max=borne_max,
                )
            if not nouvelles:
                continue
            affectations = ", ".join(f"{champ} = :{champ}" for champ in nouvelles)
            connection.execute(
                text(f"UPDATE clients SET {affectations} WHERE id = :id"), {**nouvelles, "id": identifiant}
            )
            operations.append(f"client {identifiant} : {', '.join(nouvelles)} normalisé")

    for operation in operations:
        logger.info("Données mises à niveau : %s", operation)
    return operations


def normaliser_types_compte(engine: Engine) -> list[str]:
    """Convertit les types de compte saisis librement avant que le type ne
    devienne un choix fermé (courant, epargne, bloque). Une valeur inconnue
    devient « courant », et chaque conversion est journalisée.
    """
    inspecteur = inspect(engine)
    if "comptes" not in inspecteur.get_table_names():
        return []

    operations: list[str] = []
    with engine.begin() as connection:
        valeurs = [
            ligne[0]
            for ligne in connection.execute(text("SELECT DISTINCT type_compte FROM comptes"))
        ]
        for valeur in valeurs:
            cible = _TYPES_COMPTE_HISTORIQUES.get((valeur or "").strip().lower(), "courant")
            if valeur == cible:
                continue
            connection.execute(
                text("UPDATE comptes SET type_compte = :cible WHERE type_compte = :valeur"),
                {"cible": cible, "valeur": valeur},
            )
            operations.append(f"type de compte « {valeur} » converti en « {cible} »")

    for operation in operations:
        logger.info("Données mises à niveau : %s", operation)
    return operations
