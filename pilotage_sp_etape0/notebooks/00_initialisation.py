# Databricks notebook source
# MAGIC %md
# MAGIC # 00 Initialisation de l'arrete
# MAGIC Cree les schemas (landing, bronze, silver, gold, ops, ref), charge les referentiels versionnes du depot
# MAGIC (tables BCAC, mortalite, TME, hypotheses, catalogue qualite) et verifie les hypotheses de l'exercice.
# MAGIC Idempotent : peut etre rejoue sans effet de bord.

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

import pandas as pd
from pilotage_sp.hypotheses import charger_hypotheses
from pilotage_sp.referentiels import charger_tables
from pilotage_sp.qualite import catalogue

ctx.creer_schemas()
ref = Path(ctx.chemin_referentiels())
REFERENTIELS = {"bcac_maintien_incapacite": "bcac_maintien_incapacite.csv", "bcac_passage_invalidite": "bcac_passage_invalidite.csv",
                "bcac_maintien_invalidite": "bcac_maintien_invalidite.csv", "mortalite_th0002": "mortalite_TH0002.csv",
                "mortalite_tf0002": "mortalite_TF0002.csv", "hypotheses_arrete": "hypotheses_arrete.csv", "tme_mensuel": "tme_mensuel.csv"}
for table, fichier in REFERENTIELS.items():
    pdf = pd.read_csv(ref / fichier, sep=";", dtype={"mois": str})
    ctx.ecrire_pandas(pdf, "ref", table, partition=None)
ctx.ecrire_pandas(catalogue(), "ref", "dq_regles", partition=None)

# COMMAND ----------

# Controle des referentiels et des hypotheses de l'exercice (bloquant)
tables = charger_tables(ref)
hyp = charger_hypotheses(ref / "hypotheses_arrete.csv", ref / "tme_mensuel.csv")
if N not in hyp:
    raise ValueError(f"Aucune hypothese versionnee pour l'exercice {N} : completer ref.hypotheses_arrete avant l'arrete")
h = hyp[N]
print(f"Hypotheses {h.version_note_technique} : taux {h.taux_technique:.2%} (plafond {h.plafond_reglementaire:.2%}, "
      f"TME moyen 24 mois {h.tme_moyen_24m:.2%}), bareme {h.bareme_retraite}")
ctx.journaliser("00_initialisation", "OK", h.version_note_technique)
