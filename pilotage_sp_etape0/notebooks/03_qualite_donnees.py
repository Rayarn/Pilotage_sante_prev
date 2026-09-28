# Databricks notebook source
# MAGIC %md
# MAGIC # 03 Qualite des donnees
# MAGIC Evalue le catalogue declaratif (ref.dq_regles) sur les tables bronze de l'exercice. Resultats dans
# MAGIC ops.dq_resultats, lignes en anomalie dans ops.dq_anomalies. Une regle BLOQUANTE hors seuil arrete la
# MAGIC chaine ; une regle MAJEURE hors seuil est tracee et doit etre validee au journal d'arrete.

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

from pilotage_sp.qualite import evaluer

temoin = spark.table(ctx.table("ops", "controle_disponibilite")).where(f"exercice = {N}").toPandas()
periode = temoin[temoin.fichier == f"FLX_PRESTATIONS_SANTE_{N}.csv"].iloc[0]
periodes = {"flx_prestations_sante": (periode.periode_debut, periode.periode_fin)}
resultats, anomalies = evaluer(spark, ctx, periodes)
ctx.ecrire_pandas(resultats, "ops", "dq_resultats")
ctx.ecrire(anomalies, "ops", "dq_anomalies")
display(resultats[["regle_id", "libelle", "severite", "action", "nb_anomalies", "taux_anomalies", "statut"]])

# COMMAND ----------

bloquants = resultats[resultats.bloquant]
majeurs = resultats[(resultats.statut == "HORS_SEUIL") & (resultats.severite == "MAJEUR")]
if len(bloquants):
    ctx.journaliser("03_qualite_donnees", "BLOQUANT", ", ".join(bloquants.regle_id))
    raise RuntimeError(f"Regles bloquantes hors seuil : {list(bloquants.regle_id)}")
ctx.journaliser("03_qualite_donnees", "A_VALIDER" if len(majeurs) else "OK", ", ".join(majeurs.regle_id))
print("Regles majeures hors seuil (validation requise) :", list(majeurs.regle_id) or "aucune")
