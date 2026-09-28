# Databricks notebook source
# MAGIC %md
# MAGIC # 01 Controle de disponibilite des extractions
# MAGIC Compare chaque fichier depose en zone d'atterrissage a son fichier temoin : presence, empreinte sha256,
# MAGIC structure (en-tete), nombre de lignes et somme de controle. Tout ecart est BLOQUANT : la chaine s'arrete
# MAGIC avant toute ingestion et la gestion est sollicitee pour une relivraison.

# COMMAND ----------

import sys
from pathlib import Path

RACINE = Path.cwd().parent
sys.path.insert(0, str(RACINE / "src"))
from pilotage_sp.plateforme import Contexte

dbutils.widgets.text("catalog", "sp_pilotage")
dbutils.widgets.text("exercice", "2025")
ctx = Contexte(spark, dbutils.widgets.get("catalog"), dbutils.widgets.get("exercice"), RACINE)
N = ctx.exercice
print(f"catalogue {ctx.catalog} | exercice {N} | {'Databricks' if ctx.databricks else 'local'}")

# COMMAND ----------

import hashlib
import pandas as pd
from pilotage_sp.schemas import FICHIERS, schema_spark
from pilotage_sp.schemas import lire_csv

landing = ctx.chemin_landing()
temoin = pd.read_csv(f"{landing}/_TEMOIN_{N}.csv", sep=";")
colonne_controle = {"REF_ASSURES": "salaire_annuel", "FLX_COTISATIONS": "montant_cotisation_ht", "FLX_PRESTATIONS_SANTE": "montant_rembourse",
                    "SNP_SINISTRES_PREVOYANCE": "capital", "FLX_PRESTATIONS_PREVOYANCE": "montant", "CPT_BALANCE": "montant"}
resultats = []
for nom in FICHIERS:
    fichier = f"{nom}_{N}.csv"
    chemin = f"{landing}/{fichier}"
    ligne = temoin[temoin.fichier == fichier]
    r = {"exercice": N, "fichier": fichier, "present": Path(chemin).exists(), "temoin_present": len(ligne) == 1}
    if r["present"] and r["temoin_present"]:
        t = ligne.iloc[0]
        with open(chemin, "rb") as f:
            r["sha256_ok"] = hashlib.sha256(f.read()).hexdigest() == t.sha256
        with open(chemin, encoding="utf-8") as f:
            r["structure_ok"] = f.readline().strip().split(";") == list(FICHIERS[nom])
        df = lire_csv(spark, chemin, nom)
        r["nb_lignes"] = df.count()
        r["nb_lignes_ok"] = r["nb_lignes"] == int(t.nb_lignes)
        col = colonne_controle.get(nom)
        if col:
            somme = df.agg({col: "sum"}).collect()[0][0] or 0.0
            r["somme_controle_ok"] = abs(somme - float(t.somme_controle)) <= 0.05 + 1e-9 * abs(float(t.somme_controle))
        else:
            r["somme_controle_ok"] = True
        r["periode_debut"], r["periode_fin"], r["type_extraction"] = t.periode_debut, t.periode_fin, t.type_extraction
    r["statut"] = "OK" if all(r.get(k, False) for k in ("present", "temoin_present", "sha256_ok", "structure_ok", "nb_lignes_ok",
                                                         "somme_controle_ok")) else "KO"
    resultats.append(r)
res = pd.DataFrame(resultats)
ctx.ecrire_pandas(res.astype({c: "string" for c in ("periode_debut", "periode_fin", "type_extraction") if c in res}), "ops",
                  "controle_disponibilite")
display(res)

# COMMAND ----------

ko = res[res.statut == "KO"]
if len(ko):
    ctx.journaliser("01_controle_disponibilite", "BLOQUANT", ", ".join(ko.fichier))
    raise RuntimeError(f"Extractions non conformes au temoin : {list(ko.fichier)}. Relivraison requise.")
ctx.journaliser("01_controle_disponibilite", "OK", f"{len(res)} fichiers conformes")
