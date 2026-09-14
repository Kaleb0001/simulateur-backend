"""Copie toutes les données d'une base SQLite du simulateur vers PostgreSQL.

Usage (depuis simulateur/backend) :

    ../.venv-backend/bin/python scripts/sqlite_vers_postgres.py \\
        [--source sqlite:///../simulateur_imf.db] \\
        [--cible postgresql://simulateur:<mot de passe>@localhost:5434/simulateur_imf] \\
        [--remplacer]

À défaut d'argument, la source vient de SOURCE_DATABASE_URL (sinon le
fichier simulateur/simulateur_imf.db) et la cible de CIBLE_DATABASE_URL, puis
de DATABASE_URL (environnement ou .env).

Le schéma cible est créé d'après le modèle (app/models.py). Chaque table est
recopiée avec ses clés primaires et ses identifiants externes, dans l'ordre
des clés étrangères, en une seule transaction : en cas d'erreur, rien n'est
écrit. Les séquences PostgreSQL repartent ensuite de max(id) + 1, et le
nombre de lignes est vérifié table par table.

Le script refuse d'écrire dans une base dont une table contient déjà des
lignes (une application démarrée sur la base y a par exemple inséré les
référentiels) ; --remplacer vide d'abord ces tables.
"""

import argparse
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from dotenv import dotenv_values  # noqa: E402
from sqlalchemy import Integer, create_engine, func, inspect, make_url, select, text  # noqa: E402

from app import models  # noqa: E402, F401  (enregistre les tables du modèle)
from app.config import normaliser_database_url  # noqa: E402
from app.database import Base  # noqa: E402

SOURCE_PAR_DEFAUT = f"sqlite:///{(RACINE.parent / 'simulateur_imf.db').as_posix()}"
TAILLE_LOT = 500


def _arguments() -> argparse.Namespace:
    parseur = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parseur.add_argument("--source", help="URL de la base SQLite à recopier")
    parseur.add_argument("--cible", help="URL de la base PostgreSQL de destination")
    parseur.add_argument(
        "--remplacer",
        action="store_true",
        help="vider les tables de la cible avant la copie si elles contiennent des lignes",
    )
    return parseur.parse_args()


def _url_cible(argument: str | None) -> str:
    url = (
        argument
        or os.environ.get("CIBLE_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or dotenv_values(RACINE / ".env").get("DATABASE_URL")
    )
    if not url:
        sys.exit("Cible introuvable : passer --cible ou définir DATABASE_URL.")
    return normaliser_database_url(url)


def _affichable(url: str) -> str:
    return make_url(url).render_as_string(hide_password=True)


def main() -> int:
    arguments = _arguments()
    url_source = arguments.source or os.environ.get("SOURCE_DATABASE_URL") or SOURCE_PAR_DEFAUT
    url_cible = _url_cible(arguments.cible)

    if not url_source.startswith("sqlite"):
        sys.exit(f"La source doit être une base SQLite : {_affichable(url_source)}")
    if not url_cible.startswith("postgresql"):
        sys.exit(f"La cible doit être une base PostgreSQL : {_affichable(url_cible)}")
    chemin_source = make_url(url_source).database
    if not chemin_source or not Path(chemin_source).is_file():
        sys.exit(f"Fichier SQLite introuvable : {chemin_source}")

    print(f"Source : {_affichable(url_source)}")
    print(f"Cible  : {_affichable(url_cible)}")

    source = create_engine(url_source)
    cible = create_engine(url_cible, connect_args={"options": "-c timezone=UTC"})
    tables = Base.metadata.sorted_tables

    inspecteur_source = inspect(source)
    tables_source = set(inspecteur_source.get_table_names())
    ignorees = sorted(tables_source - {table.name for table in tables})
    if ignorees:
        print(f"Tables de la source absentes du modèle, non copiées : {', '.join(ignorees)}")

    Base.metadata.create_all(bind=cible)

    with cible.connect() as connexion:
        occupees = {
            table.name: connexion.scalar(select(func.count()).select_from(table))
            for table in tables
        }
    occupees = {nom: total for nom, total in occupees.items() if total}
    if occupees and not arguments.remplacer:
        detail = ", ".join(f"{nom} ({total})" for nom, total in occupees.items())
        sys.exit(
            f"La cible contient déjà des données : {detail}.\n"
            "Relancer avec --remplacer pour les effacer avant la copie."
        )

    attendus: dict[str, int] = {}
    with source.connect() as lecture, cible.begin() as ecriture:
        if occupees:
            noms = ", ".join(f'"{table.name}"' for table in tables)
            ecriture.execute(text(f"TRUNCATE {noms} RESTART IDENTITY CASCADE"))
            print(f"Tables de la cible vidées : {', '.join(occupees)}")

        for table in tables:
            if table.name not in tables_source:
                print(f"  {table.name:<26} absente de la source, laissée vide")
                attendus[table.name] = 0
                continue
            en_source = {colonne["name"] for colonne in inspecteur_source.get_columns(table.name)}
            colonnes = [colonne for colonne in table.columns if colonne.name in en_source]
            retirees = sorted(en_source - {colonne.name for colonne in table.columns})
            if retirees:
                print(f"  {table.name}: colonnes retirées du modèle, non copiées : {', '.join(retirees)}")

            requete = select(*colonnes)
            cle_primaire = list(table.primary_key.columns)
            if cle_primaire and all(colonne.name in en_source for colonne in cle_primaire):
                requete = requete.order_by(*cle_primaire)
            resultat = lecture.execution_options(stream_results=True).execute(requete)

            copiees = 0
            while lot := resultat.fetchmany(TAILLE_LOT):
                ecriture.execute(table.insert(), [dict(ligne._mapping) for ligne in lot])
                copiees += len(lot)
            attendus[table.name] = lecture.scalar(text(f'SELECT COUNT(*) FROM "{table.name}"'))
            print(f"  {table.name:<26} {copiees} ligne(s)")

        for table in tables:
            cle_primaire = list(table.primary_key.columns)
            if len(cle_primaire) != 1 or not isinstance(cle_primaire[0].type, Integer):
                continue
            colonne = cle_primaire[0].name
            sequence = ecriture.scalar(
                text("SELECT pg_get_serial_sequence(:table, :colonne)"),
                {"table": table.name, "colonne": colonne},
            )
            if sequence is None:
                continue
            ecriture.execute(
                text(
                    f'SELECT setval(:sequence, COALESCE((SELECT MAX("{colonne}") '
                    f'FROM "{table.name}"), 0) + 1, false)'
                ),
                {"sequence": sequence},
            )

    ecarts = []
    with cible.connect() as connexion:
        for table in tables:
            total = connexion.scalar(select(func.count()).select_from(table))
            if total != attendus[table.name]:
                ecarts.append(f"{table.name} : {total} en cible, {attendus[table.name]} en source")
    if ecarts:
        print("Écarts de comptage :\n  " + "\n  ".join(ecarts))
        return 1

    print(f"Copie terminée : {sum(attendus.values())} ligne(s) dans {len(tables)} tables, comptes vérifiés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
