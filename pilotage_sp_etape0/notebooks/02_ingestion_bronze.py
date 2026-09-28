# Databricks notebook source
# MAGIC %md
# MAGIC # 02 Ingestion en bronze
# MAGIC Lecture typee des extractions (contrats d'interface de pilotage_sp.schemas), sans aucune transformation
# MAGIC metier, ajout des colonnes techniques (exercice, fichier source, horodatage) et ecriture partitionnee
# MAGIC par exercice : un rejeu remplace la partition, il ne duplique pas.

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

from pyspark.sql import functions as F
from pilotage_sp.schemas import FICHIERS, TABLES_BRONZE
from pilotage_sp.schemas import lire_csv

for nom in FICHIERS:
    df = lire_csv(spark, f"{ctx.chemin_landing()}/{nom}_{N}.csv", nom)
    if "exercice" in df.columns:
        df = df.withColumnRenamed("exercice", "exercice_comptable")
    df = (df.withColumn("exercice", F.lit(N)).withColumn("_fichier_source", F.lit(f"{nom}_{N}.csv"))
            .withColumn("_horodatage_ingestion", F.current_timestamp()))
    ctx.ecrire(df, "bronze", TABLES_BRONZE[nom])
    print(f"{nom:<28} {df.count():>9,} lignes")
ctx.journaliser("02_ingestion_bronze", "OK")
