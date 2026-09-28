# Databricks notebook source
# MAGIC %md
# MAGIC # 09 Controles de coherence et livraison
# MAGIC Controles de second niveau (bouclage, signes, variations, conformite des hypotheses, qualite a valider),
# MAGIC exports vers le volume de livraison (CSV, XLSX, JSON de reporting), manifeste d'empreintes et journal d'arrete.

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
import json
import datetime as dt
import pandas as pd
import pilotage_sp
from pilotage_sp.hypotheses import charger_hypotheses

def lire(schema, nom, n=N):
    return spark.table(ctx.table(schema, nom)).where(f"exercice = {n}").toPandas()
def lire_jusqua(schema, nom):
    return spark.table(ctx.table(schema, nom)).where(f"exercice <= {N}").toPandas()
def existe(schema, nom, n):
    return spark.catalog.tableExists(ctx.table(schema, nom)) and spark.table(ctx.table(schema, nom)).where(f"exercice = {n}").limit(1).count() > 0

hyp = charger_hypotheses(spark.table(ctx.table("ref", "hypotheses_arrete")).toPandas(), spark.table(ctx.table("ref", "tme_mensuel")).toPandas())
h = hyp[N]
detail, synthese = lire("gold", "provisions_detail"), lire("gold", "provisions_synthese")
dq, rec = lire("ops", "dq_resultats"), lire("ops", "reconciliation")
pont = lire("gold", "pont_provisions") if existe("gold", "pont_provisions", N) else pd.DataFrame()
controles = []
def controle(code, libelle, ok, severite, valeur=""):
    controles.append({"exercice": N, "code": code, "libelle": libelle, "statut": "OK" if ok else "KO", "severite": severite, "valeur": str(valeur)})

controle("L01", "Synthese egale a la somme du detail", abs(detail[detail.jeu_hypotheses == "N"].montant.sum() - synthese.montant.sum()) < 1, "BLOQUANT")
neg = synthese.groupby(["branche", "segment", "type_provision"]).montant.sum()
controle("L02", "Aucune provision agregee negative", (neg >= -1e-6).all(), "BLOQUANT", neg[neg < 0].to_dict())
controle("L03", "Bouclage du pont N-1 vers N (1 euro)", pont.empty or pont.controle_bouclage.abs().max() < 1, "BLOQUANT",
         "" if pont.empty else round(pont.controle_bouclage.abs().max(), 4))
controle("L04", "Taux technique conforme au plafond A331-22", h.taux_technique <= max(h.plafond_reglementaire, 0) + 1e-9, "BLOQUANT",
         f"{h.taux_technique:.2%} / {h.plafond_reglementaire:.2%}")
controle("L05", "Reconciliation comptable dans la tolerance", (rec.statut == "CONFORME").all(), "BLOQUANT")
majeurs = dq[(dq.statut == "HORS_SEUIL") & (dq.severite == "MAJEUR")]
controle("L06", "Regles qualite majeures hors seuil (validation requise)", majeurs.empty, "A_VALIDER", ", ".join(majeurs.regle_id))
if existe("gold", "provisions_synthese", N - 1):
    prec = lire("gold", "provisions_synthese", N - 1).groupby("branche").montant.sum()
    var = synthese.groupby("branche").montant.sum() / prec - 1
    controle("L07", "Variation des provisions par branche inferieure a 25 %", (var.abs() <= 0.25).all(), "ALERTE", var.round(4).to_dict())
ctrl = pd.DataFrame(controles)
ctx.ecrire_pandas(ctrl, "ops", "controles_livraison")
display(ctrl)
if ((ctrl.statut == "KO") & (ctrl.severite == "BLOQUANT")).any():
    ctx.journaliser("09_controles_livraison", "BLOQUANT", ctrl[ctrl.statut == "KO"].code.tolist())
    raise RuntimeError("Controle de livraison bloquant en echec")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exports et JSON de reporting

# COMMAND ----------

sortie = Path(ctx.chemin_livraison())
exports = {"provisions_synthese": synthese, "provisions_detail": detail, "pont_provisions": pont,
           "kpi_exercice": lire("gold", "kpi_exercice"), "charge_survenance": lire("gold", "charge_survenance"),
           "dq_resultats": dq, "reconciliation": rec, "controles_livraison": ctrl}
for nom, df in exports.items():
    df.to_csv(sortie / f"{nom}_{N}.csv", sep=";", index=False, encoding="utf-8")
with pd.ExcelWriter(sortie / f"synthese_arrete_{N}.xlsx") as xl:
    for nom in ("provisions_synthese", "pont_provisions", "kpi_exercice", "charge_survenance", "dq_resultats", "controles_livraison"):
        exports[nom].to_excel(xl, sheet_name=nom[:31], index=False)

def serie(df):
    return json.loads(df.to_json(orient="records", date_format="iso", double_precision=6))
hist_synth = lire_jusqua("gold", "provisions_synthese")
hist_kpi = lire_jusqua("gold", "kpi_exercice")
prev_sin = lire("gold", "provisions_prevoyance_synthese")
res_sante = lire("gold", "provisions_sante_resume")
sd = lire("gold", "provisions_sante_detail")
ib = lire("gold", "ibnr_prevoyance")
jeux = prev_sin.groupby(["jeu_hypotheses", "segment"]).montant.sum().unstack(0).fillna(0.0) if len(prev_sin) else pd.DataFrame()
rapport = {
    "entite": "Mutuelle Orsane (donnees fictives)", "exercice": N, "date_arrete": f"{N}-12-31",
    "version_code": pilotage_sp.__version__, "genere_le": dt.datetime.utcnow().isoformat(timespec="seconds"),
    "hypotheses": {k: v.en_dict() for k, v in hyp.items() if k in (N, N - 1)},
    "historique_provisions": serie(hist_synth.groupby(["exercice", "branche", "segment", "garantie", "type_provision"], as_index=False).montant.sum()),
    "historique_kpi": serie(hist_kpi),
    "charge_survenance": serie(lire("gold", "charge_survenance")),
    "pont": serie(pont),
    "sante_resume": serie(res_sante[["jeu_hypotheses", "segment", "psap", "psap_chain_ladder", "ecart_type_mack"]]),
    "sante_methodes": serie(sd[sd.jeu_hypotheses == "N"].groupby(["segment", "methode"], as_index=False).agg(psap=("psap", "sum"), nb_mois=("mois_soins", "count"))),
    "prevoyance_jeux": serie(jeux.reset_index()) if len(jeux) else [],
    "ibnr": serie(ib[(ib.jeu_hypotheses == "N") & (ib.annee_survenance >= N - 2)]),
    "qualite": serie(dq), "reconciliation": serie(rec), "controles": serie(ctrl),
}
(sortie / f"reporting_{N}.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")

# COMMAND ----------

manifeste = {"exercice": N, "version_code": pilotage_sp.__version__, "version_hypotheses": h.version_note_technique,
             "fichiers": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sortie.iterdir()) if p.name != "manifeste.json"}}
(sortie / "manifeste.json").write_text(json.dumps(manifeste, indent=1), encoding="utf-8")
statut = "LIVRE_AVEC_RESERVES" if (ctrl.statut == "KO").any() else "LIVRE"
journal = pd.DataFrame([{"exercice": N, "date_execution_utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
                         "version_code": pilotage_sp.__version__, "version_hypotheses": h.version_note_technique,
                         "provisions_totales": float(synthese.montant.sum()), "statut": statut,
                         "reserves": "; ".join(ctrl[ctrl.statut == "KO"].libelle), "validation_actuaire": "EN_ATTENTE"}])
ctx.ecrire_pandas(journal, "ops", "journal_arrete")
ctx.journaliser("09_controles_livraison", statut, str(sortie))
print(statut, f"{synthese.montant.sum():,.0f}", sortie)
