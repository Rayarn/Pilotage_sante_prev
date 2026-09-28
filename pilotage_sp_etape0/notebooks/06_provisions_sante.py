# Databricks notebook source
# MAGIC %md
# MAGIC # 06 Provisions sante
# MAGIC PSAP par segment et mois de soins : Chain Ladder (facteurs ponderes sur 24 mois calendaires), Bornhuetter-Ferguson
# MAGIC sur les derniers mois, S/P a priori si l'hypothese l'impose, erreur de Mack, PFGS. Calcul avec les hypotheses de
# MAGIC l'exercice (jeu N) et celles de l'exercice precedent (jeu N-1) pour isoler l'effet des hypotheses.

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
from pilotage_sp.sante import provisions_sante, facteurs_table

hyp = charger_hypotheses(spark.table(ctx.table("ref", "hypotheses_arrete")).toPandas(), spark.table(ctx.table("ref", "tme_mensuel")).toPandas())
inc = spark.table(ctx.table("gold", "increments_sante")).where(f"exercice = {N}").toPandas()
cot = (spark.table(ctx.table("gold", "cotisations_mensuelles")).where(f"exercice = {N} AND branche = 'SANTE'").toPandas()
       .groupby(["segment", "mois"], as_index=False).montant.sum())
arrete = pd.Timestamp(f"{N}-12-31")
jeux = {"N": hyp[N]} | ({"N-1": hyp[N - 1]} if N - 1 in hyp else {})
details, resumes = [], []
for jeu, h in jeux.items():
    d, r = provisions_sante(inc, cot, h, arrete)
    details.append(d.assign(jeu_hypotheses=jeu, exercice=N))
    resumes.append(r.assign(jeu_hypotheses=jeu, exercice=N, facteurs=r.facteurs.astype(str)))
detail = pd.concat(details, ignore_index=True)
ctx.ecrire_pandas(detail, "gold", "provisions_sante_detail")
ctx.ecrire_pandas(pd.concat(resumes, ignore_index=True), "gold", "provisions_sante_resume")
ctx.ecrire_pandas(facteurs_table(inc, hyp[N], arrete).assign(exercice=N), "gold", "facteurs_sante")
display(pd.concat(resumes)[["jeu_hypotheses", "segment", "psap", "psap_chain_ladder", "ecart_type_mack"]])
ctx.journaliser("06_provisions_sante", "OK", f"PSAP {detail[detail.jeu_hypotheses == 'N'].psap.sum():,.0f}")
