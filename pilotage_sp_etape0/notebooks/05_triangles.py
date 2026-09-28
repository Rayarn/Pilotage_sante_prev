# Databricks notebook source
# MAGIC %md
# MAGIC # 05 Triangles et agregats
# MAGIC Agrege en Spark les increments de paiements sante (segment, mois de soins, mois de paiement), les cotisations
# MAGIC acquises mensuelles et les triangles de nombres de sinistres prevoyance (annee de survenance, delai de
# MAGIC declaration) : ce sont les seules entrees des moteurs de calcul.

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
from pyspark.sql import functions as F
from pilotage_sp.prevoyance import triangle_nombres

arrete = f"{N}-12-31"
inc = (spark.table(ctx.table("silver", "prestations_sante")).where(f"exercice <= {N}").where(F.col("date_paiement") <= arrete)
       .groupBy("segment", F.date_format("date_soins", "yyyy-MM").alias("mois_soins"), F.date_format("date_paiement", "yyyy-MM").alias("mois_paiement"))
       .agg(F.sum("montant_rembourse").alias("montant"), F.count("*").alias("nb_lignes")).withColumn("exercice", F.lit(N)))
ctx.ecrire(inc, "gold", "increments_sante")

cot = (spark.table(ctx.table("silver", "cotisations")).where(f"exercice <= {N}").where(F.col("date_debut_periode") <= arrete)
       .dropDuplicates(["id_quittance"])
       .groupBy("branche", "segment", "garantie", F.date_format("date_debut_periode", "yyyy-MM").alias("mois"))
       .agg(F.sum("montant_cotisation_ht").alias("montant")).withColumn("exercice", F.lit(N)))
ctx.ecrire(cot, "gold", "cotisations_mensuelles")

sin = spark.table(ctx.table("silver", "sinistres_prevoyance")).where(f"exercice = {N}").toPandas()
lignes = []
for g in ("INCAPACITE", "INVALIDITE", "DECES"):
    for seg in ("COL", "IND"):
        cum, age = triangle_nombres(sin, g, seg, N)
        t = cum.stack().rename("nb_cumule").reset_index()
        t.columns = ["annee_survenance", "delai_declaration", "nb_cumule"]
        lignes.append(t.assign(garantie=g, segment=seg))
tri = pd.concat(lignes, ignore_index=True).assign(exercice=N)
ctx.ecrire_pandas(tri, "gold", "triangles_nombres_prevoyance")
ctx.journaliser("05_triangles", "OK", f"{inc.count()} cellules sante")
