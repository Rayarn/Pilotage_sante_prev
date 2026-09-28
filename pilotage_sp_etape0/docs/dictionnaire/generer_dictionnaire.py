"""Genere le dictionnaire de donnees (Markdown) a partir des contrats d'interface, du catalogue qualite et du metastore local."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))
from pilotage_sp.schemas import FICHIERS  # noqa: E402
from pilotage_sp.qualite import REGLES  # noqa: E402

DESCRIPTIONS = {
    "ref": {"bcac_maintien_incapacite": "Loi BCAC de maintien en incapacite (age d'entree x anciennete en mois)",
            "bcac_passage_invalidite": "Loi BCAC de passage en invalidite (nombres de passages par mois)",
            "bcac_maintien_invalidite": "Loi BCAC de maintien en invalidite (annuelle)",
            "mortalite_th0002": "Table de mortalite TH 00-02", "mortalite_tf0002": "Table de mortalite TF 00-02",
            "hypotheses_arrete": "Hypotheses versionnees, une ligne par arrete", "tme_mensuel": "Serie mensuelle des TME",
            "dq_regles": "Catalogue des regles de qualite"},
    "bronze": {k.lower(): f"Extraction {k} telle que livree, typee, partitionnee par exercice" for k in FICHIERS},
    "silver": {"prestations_sante": "Prestations sante nettoyees (colonne _corrections)", "cotisations": "Quittances dedoublonnees",
               "assures": "Affiliations de l'extraction", "contrats": "Contrats de l'extraction",
               "sinistres_prevoyance": "Dossiers de prevoyance a l'arrete, hors quarantaine, enrichis des garanties",
               "paiements_prevoyance": "Paiements de prevoyance dedoublonnes"},
    "gold": {"increments_sante": "Increments de paiements (segment, mois de soins, mois de paiement)",
             "cotisations_mensuelles": "Cotisations acquises par mois", "triangles_nombres_prevoyance": "Triangles de nombres",
             "provisions_sante_detail": "PSAP par segment et mois de soins, jeux N et N-1",
             "provisions_sante_resume": "PSAP et ecart-type de Mack par segment", "facteurs_sante": "Facteurs de developpement",
             "provisions_prevoyance_sinistres": "Provisions par dossier (PM, PMGD, echues), jeux d'hypotheses",
             "ibnr_prevoyance": "IBNR par garantie, segment et annee de survenance",
             "provisions_prevoyance_synthese": "Provisions de prevoyance par type et annee de survenance",
             "facteurs_declaration": "Facteurs de declaration IBNR",
             "provisions_detail": "Table longue de toutes les provisions (branche, segment, garantie, type, survenance, jeu)",
             "provisions_synthese": "Synthese de l'arrete (jeu N)", "pont_provisions": "Pont N-1 vers N",
             "charge_survenance": "Charge et S/P par annee de survenance", "kpi_exercice": "Indicateurs de pilotage (table longue)"},
    "ops": {"journal_etapes": "Trace d'execution des taches", "controle_disponibilite": "Controles du temoin",
            "dq_resultats": "Resultats des regles de qualite", "dq_anomalies": "Cles des lignes en anomalie",
            "reconciliation": "Ecarts flux contre balance", "controles_livraison": "Controles de livraison",
            "journal_arrete": "Journal d'arrete et validation"},
}

lignes = ["# Dictionnaire de donnees", "",
          "Genere par `docs/dictionnaire/generer_dictionnaire.py`. Catalogue Unity Catalog parametrable (`catalog`), "
          "schemas `landing`, `bronze`, `silver`, `gold`, `ops`, `ref`. Toutes les tables operationnelles sont partitionnees par `exercice`.", "",
          "## 1. Extractions (zone landing, CSV `;`, UTF-8, dates ISO)", ""]
for nom, cols in FICHIERS.items():
    lignes += [f"### {nom}_N", "", "| Colonne | Type |", "|---|---|"] + [f"| `{c}` | {t} |" for c, t in cols.items()] + [""]
lignes += ["## 2. Tables de la plateforme", ""]
try:
    from pilotage_sp.plateforme import session_locale
    spark = session_locale(RACINE)
    spark.sparkContext.setLogLevel("ERROR")
    for schema, tables in DESCRIPTIONS.items():
        lignes += [f"### Schema `{schema}`", ""]
        for t, desc in tables.items():
            nom = f"spark_catalog.{schema}.{t}"
            cols = ", ".join(f"`{f.name}` ({f.dataType.simpleString()})" for f in spark.table(nom).schema.fields) \
                if spark.catalog.tableExists(nom) else "(table non materialisee localement)"
            lignes += [f"- `{schema}.{t}` : {desc}.", f"  Colonnes : {cols}.", ""]
except Exception as e:  # sans Spark : descriptions seules
    for schema, tables in DESCRIPTIONS.items():
        lignes += [f"### Schema `{schema}`", ""] + [f"- `{schema}.{t}` : {d}." for t, d in tables.items()] + [""]
lignes += ["## 3. Catalogue des regles de qualite", "", "| Id | Table | Dimension | Severite | Seuil | Action | Libelle |", "|---|---|---|---|---|---|---|"]
lignes += [f"| {r['id']} | {r['table']} | {r['dimension']} | {r['severite']} | {r['seuil']:.2%} | {r['action']} | {r['libelle']} |" for r in REGLES]
(Path(__file__).parent / "dictionnaire_donnees.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
print("ok")
