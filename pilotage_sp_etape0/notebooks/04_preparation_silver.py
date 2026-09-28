# Databricks notebook source
# MAGIC %md
# MAGIC # 04 Preparation silver
# MAGIC Applique les actions du catalogue qualite (rejet, quarantaine, correction), normalise, enrichit les sinistres
# MAGIC des garanties de reference, puis reconcilie les flux nettoyes avec la balance comptable (tolerance 0,10 %,
# MAGIC BLOQUANT). Chaque correction est tracee dans la colonne _corrections.

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
from pyspark.sql.window import Window
from pilotage_sp.schemas import TRANSCODAGE_POSTES
from pilotage_sp.qualite import reconcilier

anom = spark.table(ctx.table("ops", "dq_anomalies")).where(f"exercice = {N}")
def cles(regles):
    return anom.where(F.col("regle_id").isin(regles)).select(F.col("cle")).distinct()
def bronze(nom):
    return spark.table(ctx.table("bronze", nom)).where(f"exercice = {N}").drop("_fichier_source", "_horodatage_ingestion")
def corriger(df, condition, regle):
    return df.withColumn("_corrections", F.when(condition, F.concat_ws(",", F.col("_corrections"), F.lit(regle))).otherwise(F.col("_corrections")))

# ---------------------------------------------------------------- prestations sante
s = bronze("flx_prestations_sante").dropDuplicates().withColumn("_corrections", F.lit(""))          # S01
s = s.join(cles(["S02", "S06", "S08", "S09"]), s.id_ligne == F.col("cle"), "left_anti")              # S02 rejet, S06 S08 quarantaine, S09
s = corriger(s, F.col("date_soins") > F.col("date_paiement"), "S04")
s = (s.withColumn("_d", F.col("date_soins"))
       .withColumn("date_soins", F.when(F.col("_d") > F.col("date_paiement"), F.col("date_paiement")).otherwise(F.col("_d")))
       .withColumn("date_paiement", F.when(F.col("_d") > F.col("date_paiement"), F.col("_d")).otherwise(F.col("date_paiement"))).drop("_d"))
s = corriger(s, F.col("date_soins").isNull(), "S03")
s = s.withColumn("date_soins", F.coalesce(F.col("date_soins"), F.date_sub(F.col("date_paiement"), 15)))
transco = F.create_map(*[F.lit(x) for kv in TRANSCODAGE_POSTES.items() for x in kv])
s = corriger(s, F.col("poste").isin(list(TRANSCODAGE_POSTES)), "S05")
s = s.withColumn("poste", F.coalesce(transco[F.col("poste")], F.col("poste")))
ctx.ecrire(s, "silver", "prestations_sante")

# ---------------------------------------------------------------- referentiels et cotisations
ctx.ecrire(bronze("ref_contrats"), "silver", "contrats")
ctx.ecrire(bronze("ref_assures"), "silver", "assures")
c = bronze("flx_cotisations").dropDuplicates(["id_quittance"])                                       # C01
ctx.ecrire(c, "silver", "cotisations")

# ---------------------------------------------------------------- paiements et sinistres prevoyance
p = bronze("flx_prestations_prevoyance").dropDuplicates(["id_paiement"])                               # V01
p = p.join(cles(["V02"]), p.id_paiement == F.col("cle"), "left_anti")                                 # V02
ctx.ecrire(p, "silver", "paiements_prevoyance")

sin = bronze("snp_sinistres_prevoyance").withColumn("_corrections", F.lit(""))
sin = sin.join(cles(["P03", "P04", "P05"]), sin.id_sinistre == F.col("cle"), "left_anti")            # quarantaine / rejet
# P02 : indemnite journaliere deduite du dernier paiement connu (montant / jours de la periode)
tous_paiements = spark.table(ctx.table("silver", "paiements_prevoyance")).where(f"exercice <= {N}")
dernier = (tous_paiements.where("type_paiement = 'IJ'")
           .withColumn("ij_deduite", F.round(F.col("montant") / (F.datediff("date_fin_periode", "date_debut_periode") + 1), 2))
           .withColumn("rg", F.row_number().over(Window.partitionBy("id_sinistre").orderBy(F.col("date_fin_periode").desc())))
           .where("rg = 1").select("id_sinistre", "ij_deduite"))
sin = sin.join(dernier, "id_sinistre", "left")
sin = corriger(sin, (F.col("garantie") == "INCAPACITE") & F.col("ij_journaliere").isNull(), "P02")
sin = (sin.withColumn("ij_journaliere", F.coalesce(F.col("ij_journaliere"), F.col("ij_deduite"))).drop("ij_deduite")
          .withColumn("rente_invalidite_potentielle", F.coalesce(F.col("rente_invalidite_garantie"), F.lit(0.0)))
          .withColumn("capital_deces_potentiel", F.coalesce(F.col("capital_deces_garanti"), F.lit(0.0))))
ctx.ecrire(sin, "silver", "sinistres_prevoyance")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reconciliation comptable (flux de l'annee N nettoyes contre balance)
# MAGIC Les paiements des sinistres mis en quarantaine restent des decaissements reels : ils sont rattaches a leur
# MAGIC segment via le dossier bronze et conserves dans les flux (seul le calcul des provisions les exclut).

# COMMAND ----------

debut, fin = f"{N}-01-01", f"{N}-12-31"
def flux(df, date_col, montant, branche, garantie, poste):
    return (df.where(F.col(date_col).between(debut, fin)).groupBy(*[c for c in ("segment", garantie) if c])
              .agg(F.sum(montant).alias("montant")).toPandas())
fs = flux(spark.table(ctx.table("silver", "prestations_sante")).where(f"exercice = {N}"), "date_paiement", "montant_rembourse", None, None, None)
fs = fs.assign(branche="SANTE", garantie="FRAIS_DE_SANTE", poste_comptable="PRESTATIONS_PAYEES")
fp = flux(spark.table(ctx.table("silver", "paiements_prevoyance")).where(f"exercice = {N}")
          .join(spark.table(ctx.table("bronze", "snp_sinistres_prevoyance")).where(f"exercice = {N}").select("id_sinistre", "segment")
                .dropDuplicates(["id_sinistre"]),
                "id_sinistre", "left").fillna({"segment": "INCONNU"}), "date_paiement", "montant", None, "garantie", None)
fp = fp.assign(branche="PREVOYANCE", poste_comptable="PRESTATIONS_PAYEES")
fc = (spark.table(ctx.table("silver", "cotisations")).where(f"exercice = {N}").where(F.col("date_debut_periode").between(debut, fin))
      .groupBy("branche", "segment", "garantie").agg(F.sum("montant_cotisation_ht").alias("montant")).toPandas()
      .assign(poste_comptable="COTISATIONS_ACQUISES"))
import pandas as pd
donnees = pd.concat([fs, fp, fc], ignore_index=True)
balance = spark.table(ctx.table("bronze", "cpt_balance")).where(f"exercice = {N}").select(
    "branche", "segment", "garantie", "poste_comptable", "montant").toPandas()
brut = (spark.table(ctx.table("bronze", "flx_prestations_sante")).where(f"exercice = {N}").where(F.col("date_paiement").between(debut, fin))
        .groupBy("segment").agg(F.sum("montant_rembourse").alias("montant_brut")).toPandas())
rec = reconcilier(donnees, balance, N)
rec = rec.merge(brut.assign(branche="SANTE", garantie="FRAIS_DE_SANTE", poste_comptable="PRESTATIONS_PAYEES"),
                on=["branche", "segment", "garantie", "poste_comptable"], how="left")
rec["ecart_relatif_avant_nettoyage"] = (rec.montant_brut - rec.montant_comptable) / rec.montant_comptable
ctx.ecrire_pandas(rec, "ops", "reconciliation")
display(rec)
ko = rec[rec.statut == "HORS_SEUIL"]
if len(ko):
    ctx.journaliser("04_preparation_silver", "BLOQUANT", ko.to_string())
    raise RuntimeError("Ecart de reconciliation superieur a 0,10 % : voir ops.reconciliation")
ctx.journaliser("04_preparation_silver", "OK", f"ecart max {rec.ecart_relatif.abs().max():.4%}")
