# Databricks notebook source
# MAGIC %md
# MAGIC # 07 Provisions prevoyance
# MAGIC Provisions mathematiques d'incapacite, de rentes en attente et d'invalidite (lois BCAC, A331-22), PSAP deces,
# MAGIC PMGD, IBNR (nombres x cout moyen) et PFGS. Jeu d'hypotheses N et N-1.

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
from pilotage_sp.prevoyance import provisions_prevoyance, synthese_prevoyance

lire_ref = lambda t: spark.table(ctx.table("ref", t)).toPandas()
tables = charger_tables({"incapacite": lire_ref("bcac_maintien_incapacite"), "passage": lire_ref("bcac_passage_invalidite"),
                         "invalidite": lire_ref("bcac_maintien_invalidite"), "mortalite_H": lire_ref("mortalite_th0002"),
                         "mortalite_F": lire_ref("mortalite_tf0002")})
hyp = charger_hypotheses(lire_ref("hypotheses_arrete"), lire_ref("tme_mensuel"))
sin = spark.table(ctx.table("silver", "sinistres_prevoyance")).where(f"exercice = {N}").toPandas()
pay = spark.table(ctx.table("silver", "paiements_prevoyance")).where(f"exercice <= {N}").dropDuplicates(["id_paiement"]).toPandas()
from dataclasses import replace
jeux = {"N": hyp[N]}
if N - 1 in hyp:  # jeu intermediaire : hypotheses N-1 avec le seul taux N, pour separer effet taux et effet bareme
    jeux |= {"N-1": hyp[N - 1], "N-1_TAUX_N": replace(hyp[N - 1], taux_technique=hyp[N].taux_technique)}
details, ibnrs, syntheses, facteurs = [], [], [], []
for jeu, h in jeux.items():
    d, ib, f = provisions_prevoyance(sin, pay, tables, h, date_arrete=f"{N}-12-31")
    details.append(d.assign(jeu_hypotheses=jeu))
    ibnrs.append(ib.assign(jeu_hypotheses=jeu))
    syntheses.append(synthese_prevoyance(d, ib, h).assign(jeu_hypotheses=jeu))
    facteurs.append(f.assign(jeu_hypotheses=jeu, facteurs=f.facteurs.astype(str)))
colonnes = ["id_sinistre", "id_sinistre_origine", "segment", "garantie", "statut", "date_survenance", "annee_survenance_origine",
            "paye_cumule", "pm_incapacite", "pm_passage", "pm_invalidite", "pmgd", "psap_deces", "psap_echues", "provision", "charge",
            "anciennete_mois", "mois_avant_retraite", "jeu_hypotheses"]
detail = pd.concat(details, ignore_index=True)
detail = detail[(detail.statut == "EN_COURS") | (detail.provision > 0)][colonnes].assign(exercice=N)
ctx.ecrire_pandas(detail, "gold", "provisions_prevoyance_sinistres")
ctx.ecrire_pandas(pd.concat(ibnrs, ignore_index=True).assign(exercice=N), "gold", "ibnr_prevoyance")
ctx.ecrire_pandas(pd.concat(syntheses, ignore_index=True).assign(exercice=N), "gold", "provisions_prevoyance_synthese")
ctx.ecrire_pandas(pd.concat(facteurs, ignore_index=True).assign(exercice=N), "gold", "facteurs_declaration")
s = pd.concat(syntheses)
display(s[s.jeu_hypotheses == "N"].groupby(["segment", "type_provision"]).montant.sum().unstack(0).round(0))
ctx.journaliser("07_provisions_prevoyance", "OK", f"{s[s.jeu_hypotheses == 'N'].montant.sum():,.0f}")
