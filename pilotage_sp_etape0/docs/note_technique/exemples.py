"""Calcule les exemples chiffres de la note technique avec le moteur de production et ecrit exemples.tex.

Usage : python docs/note_technique/exemples.py   (apres execution locale des arretes)
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))
from pilotage_sp.hypotheses import charger_hypotheses, plafond_taux  # noqa: E402
from pilotage_sp.referentiels import charger_tables  # noqa: E402
from pilotage_sp.retraite import age_legal_mois  # noqa: E402
from pilotage_sp import sante, prevoyance  # noqa: E402

REF = RACINE / "data" / "referentiels"
LIV = RACINE / "livraison"
T = charger_tables(REF)
H = charger_hypotheses(REF / "hypotheses_arrete.csv", REF / "tme_mensuel.csv")
out = []


def fr(x, d=2):
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s.replace(" ", "\\,")


def macro(nom, val):
    out.append(f"\\newcommand{{\\{nom}}}{{{val}}}")


# ------------------------------------------------------------------ 1. plafond du taux
tme = pd.read_csv(REF / "tme_mensuel.csv", sep=";", dtype={"mois": str})
lignes = []
for n in range(2020, 2026):
    m, p = plafond_taux(tme, f"{n}-12-31")
    lignes.append(f"{n} & {fr(100 * m)}\\,\\% & {fr(100 * p)}\\,\\% & {fr(100 * H[n].taux_technique)}\\,\\% \\\\")
macro("tabTaux", "\n".join(lignes))

# ------------------------------------------------------------------ 2. baremes de retraite
lignes = []
for date in ["1955-06-15", "1961-06-15", "1963-06-15", "1964-06-15", "1965-02-15", "1965-06-15", "1966-06-15", "1968-06-15", "1970-06-15"]:
    v = [age_legal_mois(pd.Series([pd.Timestamp(date)]), b)[0] for b in ("LOI_2010", "REFORME_2023", "LFSS_2026")]
    lignes.append(f"{date[:7]} & " + " & ".join(f"{a // 12} ans {a % 12} mois" if a % 12 else f"{a // 12} ans" for a in v) + " \\\\")
macro("tabRetraite", "\n".join(lignes))

# ------------------------------------------------------------------ 3. chain ladder jouet
C = np.array([[600.0, 900.0, 1000.0], [660.0, 990.0, np.nan], [720.0, np.nan, np.nan]])
f1 = (C[0, 1] + C[1, 1]) / (C[0, 0] + C[1, 0]); f2 = C[0, 2] / C[0, 1]
macro("cljF", fr(f1, 4)); macro("cljG", fr(f2, 4))
macro("cljUa", fr(C[1, 1] * f2)); macro("cljUb", fr(C[2, 0] * f1 * f2))
macro("cljR", fr(C[1, 1] * f2 - C[1, 1] + C[2, 0] * f1 * f2 - C[2, 0]))
# BF sur le dernier mois : prime 1 200, S/P a priori 85 %
fc = f1 * f2
macro("bfFc", fr(fc, 4)); macro("bfU", fr(720 + (1 - 1 / fc) * 0.85 * 1200)); macro("bfR", fr((1 - 1 / fc) * 0.85 * 1200))

# ------------------------------------------------------------------ 4. sante 2025 (production)
fs = pd.read_csv(LIV / "exercice=2025" / "provisions_detail_2025.csv", sep=";")
res = fs[(fs.branche == "SANTE") & (fs.jeu_hypotheses == "N")].groupby(["segment", "type_provision"]).montant.sum().unstack()
macro("santePsapCol", fr(res.loc["COL", "PSAP"], 0)); macro("santePsapInd", fr(res.loc["IND", "PSAP"], 0))

# backtesting sante : PSAP estimee a chaque arrete contre PSAP reelle (verite du generateur)
v = pd.read_csv(RACINE / "outils" / "generation_donnees" / "verite" / "sante_ultime_par_mois_soins.csv", sep=";")
lignes = []
for n in range(2020, 2026):
    det = pd.read_csv(LIV / f"exercice={n}" / f"provisions_detail_{n}.csv", sep=";")
    est = det[(det.branche == "SANTE") & (det.type_provision == "PSAP") & (det.jeu_hypotheses == "N")].groupby("segment").montant.sum()
    inc = []
    for y in range(2019, n + 1):
        p = LIV / f"exercice={n}" / f"charge_survenance_{n}.csv"
    cs = pd.read_csv(LIV / f"exercice={n}" / f"charge_survenance_{n}.csv", sep=";")
    paye = cs[cs.branche == "SANTE"].groupby("segment").paye.sum()
    vv = v[v.mois_soins <= f"{n}-12"].groupby("segment").montant_rembourse.sum()
    vrai = vv - paye
    lignes.append(f"{n} & " + " & ".join(f"{fr(est[s] / 1e3, 0)} & {fr(vrai[s] / 1e3, 0)} & {fr(100 * (est[s] / vrai[s] - 1), 1)}\\,\\%"
                                            for s in ("COL", "IND")) + " \\\\")
macro("tabBacktest", "\n".join(lignes))

# ------------------------------------------------------------------ 5. prevoyance : cas unitaires
h = H[2025]
arrete = pd.Timestamp("2025-12-31")
mot = prevoyance.MoteurPrevoyance(T, h)
cas = pd.DataFrame({"id_sinistre": ["EX1"], "date_survenance": [pd.Timestamp("2025-07-10")], "date_naissance": [pd.Timestamp("1980-03-01")],
                    "ij_journaliere": [60.0], "sexe": ["H"], "rente_invalidite_potentielle": [15000.0], "capital_deces_potentiel": [90000.0]})
r = mot.incapacite(cas, arrete).iloc[0]
L = T.ligne_incapacite([45])[0]
macro("exIncS", str(int(r.anciennete_mois))); macro("exIncL", fr(L[int(r.anciennete_mois)], 0)); macro("exIncLs", fr(L[35], 0))
macro("exIncPm", fr(r.pm_incapacite)); macro("exIncPas", fr(r.pm_passage)); macro("exIncGd", fr(r.pmgd))
macro("exIncR", str(int(r.mois_avant_retraite)))
cas2 = pd.DataFrame({"id_sinistre": ["EX2"], "date_survenance": [pd.Timestamp("2022-11-05")], "date_naissance": [pd.Timestamp("1972-09-20")],
                     "rente_annuelle": [14400.0], "sexe": ["F"], "capital_deces_potentiel": [80000.0]})
r2 = mot.invalidite(cas2, arrete).iloc[0]
macro("exInvT", str(int(r2.anciennete_mois))); macro("exInvR", str(int(r2.mois_avant_retraite)))
macro("exInvPm", fr(r2.pm_invalidite)); macro("exInvGd", fr(r2.pmgd))
for b in ("LOI_2010", "REFORME_2023"):
    rb = prevoyance.MoteurPrevoyance(T, replace(h, bareme_retraite=b)).invalidite(cas2, arrete).iloc[0]
    macro("exInvPm" + b.replace("_", "").replace("2010", "A").replace("2023", "B"), fr(rb.pm_invalidite))
for t in (0.0, 0.035):
    rt = prevoyance.MoteurPrevoyance(T, replace(h, taux_technique=t)).invalidite(cas2, arrete).iloc[0]
    macro("exInvPmTaux" + ("Zero" if t == 0 else "Haut"), fr(rt.pm_invalidite))

# ------------------------------------------------------------------ 6. IBNR 2025 incapacite collective
ib = pd.read_csv(LIV / "exercice=2025" / "provisions_detail_2025.csv", sep=";")
ibx = ib[(ib.type_provision.str.startswith("IBNR")) & (ib.segment == "COL") & (ib.jeu_hypotheses == "N") & (ib.annee_survenance == 2025)]
macro("ibnrIncCol", fr(ibx[ibx.type_provision == "IBNR_INCAPACITE"].montant.sum(), 0))
macro("ibnrInvCol", fr(ibx[ibx.type_provision == "IBNR_INVALIDITE"].montant.sum(), 0))

# ------------------------------------------------------------------ 7. synthese et pont 2025
LB = {"SANTE": "Santé", "PREVOYANCE": "Prévoyance"}
LG = {"FRAIS_DE_SANTE": "", "INCAPACITE": "incapacité", "INVALIDITE": "invalidité", "DECES": "décès"}
LT = {"PSAP": "PSAP frais de santé", "PFGS": "Frais de gestion (PFGS)", "PM_INCAPACITE": "PM incapacité",
      "PM_RENTES_EN_ATTENTE": "PM rentes en attente", "PM_INVALIDITE": "PM invalidité", "PMGD": "Maintien garantie décès",
      "IBNR_INCAPACITE": "IBNR incapacité", "IBNR_INVALIDITE": "IBNR invalidité", "IBNR_DECES": "IBNR décès",
      "PSAP_DECES_CONNUS": "Capitaux décès à régler", "PSAP_PRESTATIONS_ECHUES": "Prestations échues non réglées"}
syn = pd.read_csv(LIV / "exercice=2025" / "provisions_synthese_2025.csv", sep=";")
lignes = []
for (b, t), m in syn.groupby(["branche", "type_provision"]).montant.sum().items():
    lignes.append(f"{LB[b]} & {LT.get(t, t)} & {fr(m / 1e3, 0)} \\\\")
macro("tabSynthese", "\n".join(lignes)); macro("totalProv", fr(syn.montant.sum() / 1e6, 1))
pont = pd.read_csv(LIV / "exercice=2025" / "pont_provisions_2025.csv", sep=";")
lignes = []
for r in pont.itertuples():
    lignes.append(f"{LB[r.branche]} {r.segment.lower()} {LG[r.garantie]} & " + " & ".join(
        fr(x / 1e3, 0) for x in (r.provision_ouverture, r.ecoulement, r.ecart_liquidation, r.nouvelle_survenance, r.effet_hypotheses, r.provision_cloture)) + " \\\\")
macro("tabPont", "\n".join(lignes))

(Path(__file__).parent / "exemples.tex").write_text("% genere par exemples.py, ne pas modifier\n" + "\n".join(out) + "\n", encoding="utf-8")
print(len(out), "macros")
