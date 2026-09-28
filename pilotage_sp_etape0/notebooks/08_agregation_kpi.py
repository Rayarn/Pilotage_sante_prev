# Databricks notebook source
# MAGIC %md
# MAGIC # 08 Agregation, pont et indicateurs
# MAGIC Consolide les provisions sante et prevoyance (table longue gold.provisions_detail, synthese), calcule le pont
# MAGIC N-1 vers N (ecoulement, liquidation, nouvelle survenance, effet des hypotheses), la charge par annee de survenance
# MAGIC et les indicateurs de pilotage (gold.kpi_exercice) qui alimentent tableau de bord et reporting.

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
from pilotage_sp.analyse import pont

def lire(schema, nom, n=N):
    return spark.table(ctx.table(schema, nom)).where(f"exercice = {n}").toPandas()
def existe(schema, nom, n):
    return spark.catalog.tableExists(ctx.table(schema, nom)) and spark.table(ctx.table(schema, nom)).where(f"exercice = {n}").limit(1).count() > 0

sd = lire("gold", "provisions_sante_detail")
sante = pd.concat([sd.assign(type_provision="PSAP", montant=sd.psap), sd.assign(type_provision="PFGS", montant=sd.pfgs)])
sante = sante.assign(branche="SANTE", garantie="FRAIS_DE_SANTE", annee_survenance=sd.annee_soins.tolist() * 2)
prev = lire("gold", "provisions_prevoyance_synthese").assign(branche="PREVOYANCE")
cols = ["branche", "segment", "garantie", "type_provision", "annee_survenance", "montant", "jeu_hypotheses"]
detail = pd.concat([sante[cols], prev[cols]], ignore_index=True)
detail = detail.groupby(cols[:-2] + ["jeu_hypotheses"], as_index=False).montant.sum().assign(exercice=N)
ctx.ecrire_pandas(detail, "gold", "provisions_detail")
synthese = detail[detail.jeu_hypotheses == "N"].groupby(["branche", "segment", "garantie", "type_provision"], as_index=False).montant.sum()
ctx.ecrire_pandas(synthese.assign(exercice=N), "gold", "provisions_synthese")
display(synthese.pivot_table(index=["branche", "garantie", "type_provision"], columns="segment", values="montant", aggfunc="sum").round(0))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Paiements de l'exercice par annee de survenance d'origine

# COMMAND ----------

ps = lire("silver", "prestations_sante")
ps = ps[pd.to_datetime(ps.date_paiement).dt.year == N]
ps = ps.assign(branche="SANTE", garantie="FRAIS_DE_SANTE", annee_survenance=pd.to_datetime(ps.date_soins).dt.year, montant=ps.montant_rembourse)
sin = lire("silver", "sinistres_prevoyance")
origine = sin.set_index("id_sinistre").date_survenance
sin["annee_origine"] = pd.to_datetime(sin.id_sinistre_origine.map(origine)).fillna(pd.to_datetime(sin.date_survenance)).dt.year
pp_tout = spark.table(ctx.table("silver", "paiements_prevoyance")).where(f"exercice <= {N}").dropDuplicates(["id_paiement"]).toPandas()
pp_tout = pp_tout.merge(sin[["id_sinistre", "segment", "annee_origine"]], on="id_sinistre", how="inner")
pp = pp_tout[pd.to_datetime(pp_tout.date_paiement).dt.year == N].assign(branche="PREVOYANCE", annee_survenance=lambda d: d.annee_origine)
paiements_n = pd.concat([ps[["branche", "segment", "garantie", "annee_survenance", "montant"]],
                         pp[["branche", "segment", "garantie", "annee_survenance", "montant"]]], ignore_index=True)

# COMMAND ----------

# Pont N-1 -> N (hors PFGS)
hors_pfgs = detail[detail.type_provision != "PFGS"]
if existe("gold", "provisions_detail", N - 1):
    prec = lire("gold", "provisions_detail", N - 1)
    prec = prec[(prec.jeu_hypotheses == "N") & (prec.type_provision != "PFGS")]
    tab_pont = pont(hors_pfgs[hors_pfgs.jeu_hypotheses == "N"], hors_pfgs[hors_pfgs.jeu_hypotheses == "N-1"], prec,
                    paiements_n[paiements_n.annee_survenance < N], N)
    ctx.ecrire_pandas(tab_pont, "gold", "pont_provisions")
    display(tab_pont)
else:
    print("Pas d'arrete N-1 en gold : pont non calcule (arrete de reprise).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Charge par annee de survenance et indicateurs

# COMMAND ----------

cot = lire("gold", "cotisations_mensuelles")
cot["annee"] = cot.mois.str[:4].astype(int)
inc = lire("gold", "increments_sante")
paye_s = inc.assign(annee_survenance=inc.mois_soins.str[:4].astype(int)).groupby(["segment", "annee_survenance"]).montant.sum()
paye_p = pp_tout[pd.to_datetime(pp_tout.date_paiement) <= f"{N}-12-31"].groupby(["segment", "annee_origine"]).montant.sum()
paye_p.index.names = ["segment", "annee_survenance"]
lignes = []
for branche, paye in (("SANTE", paye_s), ("PREVOYANCE", paye_p)):
    prov = hors_pfgs[(hors_pfgs.jeu_hypotheses == "N") & (hors_pfgs.branche == branche)].groupby(["segment", "annee_survenance"]).montant.sum()
    c = cot[cot.branche == branche].groupby(["segment", "annee"]).montant.sum()
    c.index.names = ["segment", "annee_survenance"]
    x = pd.concat({"paye": paye, "provision": prov, "cotisations": c}, axis=1).fillna(0.0).reset_index()
    x["charge"] = x.paye + x.provision
    x["sp"] = x.charge / x.cotisations.where(x.cotisations > 0)
    lignes.append(x.assign(branche=branche))
charge = pd.concat(lignes, ignore_index=True)
charge = charge[(charge.annee_survenance >= N - 9) & (charge.annee_survenance <= N) & (charge.cotisations > 0)].assign(exercice=N)
ctx.ecrire_pandas(charge, "gold", "charge_survenance")

kpi = []
def ajouter(indicateur, df, valeur="montant", branche=None):
    for r in df.to_dict("records"):
        kpi.append({"indicateur": indicateur, "branche": r.get("branche", branche), "segment": r.get("segment", "TOUS"),
                    "garantie": r.get("garantie", "TOUTES"), "valeur": float(r[valeur])})
ajouter("cotisations_acquises", cot[cot.annee == N].groupby(["branche", "segment", "garantie"], as_index=False).montant.sum())
ajouter("prestations_payees", paiements_n.groupby(["branche", "segment", "garantie"], as_index=False).montant.sum())
ajouter("provisions_cloture", synthese.groupby(["branche", "segment", "garantie"], as_index=False).montant.sum())
if existe("gold", "provisions_synthese", N - 1):
    ouv = lire("gold", "provisions_synthese", N - 1).groupby(["branche", "segment", "garantie"], as_index=False).montant.sum()
    ajouter("provisions_ouverture", ouv)
k = pd.DataFrame(kpi)
bs = k.groupby(["indicateur", "branche", "segment"]).valeur.sum().unstack(0).fillna(0.0)
if "provisions_ouverture" in bs:
    bs["charge_comptable"] = bs.prestations_payees + bs.provisions_cloture - bs.provisions_ouverture
    bs["sp_comptable"] = bs.charge_comptable / bs.cotisations_acquises
for ind in [c for c in ("charge_comptable", "sp_comptable") if c in bs]:
    ajouter(ind, bs[ind].rename("montant").reset_index())
ajouter("sp_survenance_exercice", charge[charge.annee_survenance == N], valeur="sp")
sd_n = sd[sd.jeu_hypotheses == "N"]
res = lire("gold", "provisions_sante_resume")
ajouter("ecart_type_mack", res[res.jeu_hypotheses == "N"].assign(branche="SANTE", garantie="FRAIS_DE_SANTE"), valeur="ecart_type_mack")
assures = lire("silver", "assures")
actifs = assures[assures.date_radiation.isna() & (pd.to_datetime(assures.date_adhesion) <= f"{N}-12-31")]
ajouter("nb_personnes_couvertes", actifs.groupby(["branche", "segment"], as_index=False).size(), valeur="size")
ouverts = sin[sin.statut == "EN_COURS"].groupby(["segment", "garantie"], as_index=False).size().assign(branche="PREVOYANCE")
ajouter("nb_sinistres_en_cours", ouverts, valeur="size")
nouveaux = sin[pd.to_datetime(sin.date_declaration).dt.year == N].groupby(["segment", "garantie"], as_index=False).size().assign(branche="PREVOYANCE")
ajouter("nb_sinistres_declares_exercice", nouveaux, valeur="size")
kpi = pd.DataFrame(kpi).assign(exercice=N)
ctx.ecrire_pandas(kpi, "gold", "kpi_exercice")
display(kpi.head(40))
ctx.journaliser("08_agregation_kpi", "OK", f"provisions {synthese.montant.sum():,.0f}")
