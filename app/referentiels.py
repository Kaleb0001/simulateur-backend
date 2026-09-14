"""Les listes fermées de ce système : agences, professions, tranches de
revenus, sources des fonds, motifs de retrait, types de compte.

Chaque valeur a un code stable et un libellé. Le code est ce qui est stocké et
échangé : un consommateur (IMF SHIELD) peut raisonner dessus, par exemple repérer
un client « etudiant » déclaré avec une tranche de revenus élevée. Les
libellés ne servent qu'à l'affichage.

Les agences et les professions vivent en base (tables `agences`,
`categories_profession` et `professions`) : les valeurs ci-dessous n'en sont
que les données initiales, insérées au démarrage si elles manquent. Les autres
listes restent définies ici.

Exposé par GET /api/v1/referentiels.
"""

import unicodedata


def _code(libelle: str) -> str:
    sans_accents = unicodedata.normalize("NFD", libelle).encode("ascii", "ignore").decode()
    garde = "".join(c if c.isalnum() else "_" for c in sans_accents.lower())
    return "_".join(part for part in garde.split("_") if part)


# (catégorie, libellé de la catégorie, professions). La catégorie
# « sans_activite » regroupe les professions sans employeur.
_PROFESSIONS = [
    ("sans_activite", "Sans activité professionnelle", [
        "Élève", "Étudiant", "Sans emploi", "Retraité", "Personne au foyer"]),
    ("agriculture", "Agriculture, élevage et pêche", [
        "Agriculteur", "Maraîcher", "Éleveur", "Pêcheur", "Mareyeur",
        "Producteur de café-cacao", "Technicien agricole"]),
    ("commerce", "Commerce", [
        "Commerçant", "Revendeuse de marché", "Grossiste", "Importateur", "Exportateur",
        "Boutiquier", "Gérant de commerce", "Représentant commercial",
        "Agent de transfert d'argent"]),
    ("artisanat", "Artisanat et métiers", [
        "Couturier", "Coiffeur", "Menuisier", "Maçon", "Soudeur", "Mécanicien",
        "Électricien", "Plombier", "Forgeron", "Cordonnier", "Tisserand", "Bijoutier",
        "Boulanger", "Pâtissier", "Photographe", "Réparateur de téléphones",
        "Vulcanisateur", "Peintre en bâtiment"]),
    ("transport", "Transport et logistique", [
        "Conducteur de taxi-moto", "Chauffeur de taxi", "Chauffeur", "Transporteur",
        "Transitaire", "Docker", "Magasinier"]),
    ("btp", "Bâtiment et travaux publics", [
        "Ingénieur en génie civil", "Architecte", "Chef de chantier", "Géomètre",
        "Entrepreneur en BTP"]),
    ("sante", "Santé", [
        "Médecin", "Infirmier", "Sage-femme", "Pharmacien", "Aide-soignant",
        "Technicien de laboratoire", "Dentiste", "Tradipraticien"]),
    ("education", "Éducation et recherche", [
        "Enseignant", "Enseignant-chercheur", "Directeur d'école", "Formateur"]),
    ("administration", "Administration et fonction publique", [
        "Fonctionnaire", "Cadre de l'administration", "Agent administratif", "Secrétaire",
        "Magistrat", "Douanier", "Agent des impôts", "Élu local", "Député", "Diplomate"]),
    ("securite", "Sécurité et défense", [
        "Militaire", "Policier", "Agent de sécurité", "Sapeur-pompier"]),
    ("finance", "Banque, finance et assurance", [
        "Banquier", "Agent de microfinance", "Comptable", "Expert-comptable", "Caissier",
        "Agent d'assurance", "Auditeur"]),
    ("services", "Services et professions libérales", [
        "Avocat", "Notaire", "Huissier de justice", "Consultant", "Chef d'entreprise",
        "Cadre du secteur privé", "Employé de bureau", "Restaurateur", "Cuisinier",
        "Serveur", "Hôtelier", "Agent immobilier", "Employé de maison"]),
    ("technologie_culture", "Technologie, médias et culture", [
        "Informaticien", "Technicien en télécommunications", "Journaliste",
        "Animateur radio", "Artiste", "Graphiste"]),
    ("religion_associatif", "Religion et vie associative", [
        "Ministre du culte", "Responsable d'ONG"]),
    ("autre", "Autre", ["Autre"]),
]

CATEGORIES_PROFESSION: dict[str, str] = {code: libelle for code, libelle, _ in _PROFESSIONS}

# code -> (libellé, catégorie)
PROFESSIONS: dict[str, tuple[str, str]] = {
    _code(libelle): (libelle, categorie)
    for categorie, _, libelles in _PROFESSIONS
    for libelle in libelles
}

# Catégories dont les professions n'ont pas d'employeur.
CATEGORIES_SANS_EMPLOYEUR = {"sans_activite"}

# code -> (nom, ville)
AGENCES: dict[str, tuple[str, str]] = {
    "lome_centre": ("Lomé-Centre", "Lomé"),
    "lome_port": ("Lomé-Port", "Lomé"),
    "tsevie": ("Tsévié", "Tsévié"),
    "aneho": ("Aného", "Aného"),
    "kpalime": ("Kpalimé", "Kpalimé"),
    "atakpame": ("Atakpamé", "Atakpamé"),
    "sokode": ("Sokodé", "Sokodé"),
    "kara": ("Kara", "Kara"),
    "dapaong": ("Dapaong", "Dapaong"),
}

# code -> (libellé, minimum, maximum). Montants en XOF ; pas de maximum pour
# la dernière tranche.
TRANCHES_REVENUS: dict[str, tuple[str, int, int | None]] = {
    "de_1_a_200000": ("De 1 à 200 000", 1, 200_000),
    "de_200001_a_500000": ("De 200 001 à 500 000", 200_001, 500_000),
    "de_500001_a_1000000": ("De 500 001 à 1 000 000", 500_001, 1_000_000),
    "de_1000001_a_3000000": ("De 1 000 001 à 3 000 000", 1_000_001, 3_000_000),
    "de_3000001_a_5000000": ("De 3 000 001 à 5 000 000", 3_000_001, 5_000_000),
    "de_5000001_a_10000000": ("De 5 000 001 à 10 000 000", 5_000_001, 10_000_000),
    "de_10000001_a_15000000": ("De 10 000 001 à 15 000 000", 10_000_001, 15_000_000),
    "plus_de_15000000": ("Plus de 15 000 000", 15_000_001, None),
}

# D'où vient l'argent d'un dépôt.
SOURCES_FONDS: dict[str, str] = {
    "salaire": "Salaire",
    "activite_commerciale": "Recettes d'une activité commerciale",
    "activite_agricole": "Vente de récoltes ou d'élevage",
    "activite_artisanale": "Recettes d'une activité artisanale",
    "vente_de_biens": "Vente d'un bien (terrain, véhicule…)",
    "transfert_recu": "Transfert reçu (famille, diaspora)",
    "pension": "Pension ou retraite",
    "don": "Don ou aide",
    "pret": "Prêt reçu",
    "epargne_personnelle": "Épargne personnelle",
    "tontine": "Tontine",
    "heritage": "Héritage",
    "autre": "Autre",
}

# À quoi sert l'argent d'un retrait.
MOTIFS_RETRAIT: dict[str, str] = {
    "depenses_courantes": "Dépenses courantes du ménage",
    "achat_marchandises": "Achat de marchandises ou d'intrants",
    "frais_scolaires": "Frais scolaires",
    "frais_medicaux": "Frais médicaux",
    "construction": "Construction ou travaux",
    "achat_bien": "Achat d'un bien (terrain, véhicule…)",
    "investissement": "Investissement dans une activité",
    "remboursement_pret": "Remboursement d'un prêt",
    "evenement_familial": "Événement familial (mariage, funérailles…)",
    "transfert_envoye": "Envoi d'argent à un tiers",
    "voyage": "Voyage",
    "autre": "Autre",
}

TYPES_COMPTE: dict[str, str] = {
    "courant": "Compte courant",
    "epargne": "Compte épargne",
    "bloque": "Compte bloqué",
}


def tranche_pour_montant(montant: float | None) -> str | None:
    """La tranche qui contient un montant ; None sans montant."""
    if montant is None:
        return None
    for code, (_, _minimum, maximum) in TRANCHES_REVENUS.items():
        if maximum is None or montant <= maximum:
            return code
    return None


def profession_pour_texte(texte: str | None) -> str | None:
    """Le code d'une profession saisie librement avant la liste fermée.

    Essaie, dans l'ordre : le code ou le libellé exact ; la forme masculine
    d'un libellé féminin (« Coiffeuse » → coiffeur) ; un libellé qui commence
    par une profession connue (« Consultant en finances publiques » →
    consultant). Une valeur non reconnue devient « autre ».
    """
    if not texte or not texte.strip():
        return None
    cle = _code(texte)
    libelles = {_code(libelle): code for code, (libelle, _) in PROFESSIONS.items()}
    candidats = [cle]
    for feminin, masculin in (("euse", "eur"), ("rice", "eur"), ("ante", "ant"), ("iere", "ier"), ("enne", "en"), ("e", "")):
        premier = cle.split("_")[0]
        if premier.endswith(feminin):
            candidats.append("_".join([premier[: -len(feminin)] + masculin] + cle.split("_")[1:]))
    for candidat in candidats:
        if candidat in PROFESSIONS:
            return candidat
        if candidat in libelles:
            return libelles[candidat]
    for candidat in candidats:
        for libelle_code, code in sorted(libelles.items(), key=lambda kv: -len(kv[0])):
            if candidat.startswith(libelle_code + "_"):
                return code
    return "autre"
