"""Simulation de la consommation de soins, des remboursements et des cotisations sante."""

import numpy as np
import pandas as pd

from monde import (POSTES, FACTEUR_FORMULE, INFLATION_FRAIS, SAISON, INDICE_TARIF_SANTE, SP_CIBLE_2021,
                   DEBUT_SANTE, FIN, J, jours, date_de, age_a, ids, lognormale)

TAUX_RO = {"PHARMACIE": 0.55, "SOINS_COURANTS": 0.55, "BIOLOGIE": 0.60, "DENTAIRE": 0.35, "OPTIQUE": 0.04,
           "AUDIOLOGIE": 0.15, "HOSPITALISATION": 0.78}
TAUX_SS_THEORIQUE = {"PHARMACIE": 0.65, "SOINS_COURANTS": 0.70, "BIOLOGIE": 0.60, "DENTAIRE": 0.70, "OPTIQUE": 0.60,
                     "AUDIOLOGIE": 0.60, "HOSPITALISATION": 0.80}
SIGMA_FRAIS = {"PHARMACIE": 0.70, "SOINS_COURANTS": 0.65, "BIOLOGIE": 0.55, "DENTAIRE": 0.85, "OPTIQUE": 0.55,
               "AUDIOLOGIE": 0.45, "HOSPITALISATION": 1.00}
MOIS = np.arange(np.datetime64("2019-01"), np.datetime64("2026-01"), dtype="datetime64[M]")


def facteur_frequence(poste, annee, mois):
    f = 1.0
    if annee == 2020:
        f = {3: 0.62, 4: 0.50, 5: 0.66, 6: 0.88}.get(mois, 0.97)
    elif annee == 2021:
        f = 1.05
    if poste == "AUDIOLOGIE" and annee >= 2021:
        f *= 1.55  # montee en charge du 100 % Sante audiologie
    if poste == "OPTIQUE" and annee >= 2021:
        f *= 1.04
    return f


def simuler_soins(rng, aff):
    """Un enregistrement par decompte (regroupement d'actes d'un meme beneficiaire, poste et mois)."""
    b = aff[aff.branche == "SANTE"].reset_index(drop=True)
    adh = b.date_adhesion.values.astype("datetime64[D]")
    rad = b.date_radiation_brute.values.astype("datetime64[D]")
    rad = np.where(np.isnat(rad), FIN, rad)
    milieu = MOIS.astype("datetime64[D]") + 14 * J
    couvert = (adh[:, None] <= milieu[None, :]) & (rad[:, None] >= milieu[None, :])
    age = age_a(b.date_naissance.values.astype("datetime64[D]")[:, None], milieu[None, :])
    formule = b.id_contrat.map(FORMULES).fillna("CONFORT").values
    fact_gc = np.where(b.grand_compte.values, 1.12, 1.0)
    blocs = []
    for poste, (freq, frais_moy, part_rc, pente, *_r) in POSTES.items():
        f_temps = np.array([facteur_frequence(poste, int(str(m)[:4]), int(str(m)[5:7])) * SAISON[int(str(m)[5:7]) - 1] for m in MOIS])
        f_form = np.where(formule == "RENFORCE", 1.06, np.where(formule == "ESSENTIEL", 0.95, 1.0)) if poste in ("DENTAIRE", "OPTIQUE") else 1.0
        lam = freq / 12 * np.exp(pente * (np.clip(age, 2, 95) - 40)) * f_temps[None, :] * (fact_gc * f_form)[:, None]
        lam = np.where(couvert, lam, 0.0)
        n = rng.poisson(lam)
        i, m = np.nonzero(n)
        rep = n[i, m]
        i, m = np.repeat(i, rep), np.repeat(m, rep)
        blocs.append(pd.DataFrame({"idx": i, "mois": m, "poste": poste}))
    d = pd.concat(blocs, ignore_index=True)
    d = d.sort_values(["idx", "mois", "poste"], kind="stable").reset_index(drop=True)
    n = len(d)
    debut_mois = MOIS[d.mois.values].astype("datetime64[D]")
    nb_jours = ((MOIS[d.mois.values] + np.timedelta64(1, "M")).astype("datetime64[D]") - debut_mois).astype(int)
    d["date_soins"] = debut_mois + np.floor(rng.random(n) * nb_jours).astype(int) * J
    annee = d.date_soins.values.astype("datetime64[Y]").astype(int) + 1970
    infl = pd.Series(annee).map(INFLATION_FRAIS).values
    poste = d.poste.values
    moy = pd.Series(poste).map({k: v[1] for k, v in POSTES.items()}).values * infl
    sig = pd.Series(poste).map(SIGMA_FRAIS).values
    frais = lognormale(rng, moy, sig, n)
    taux_ro = pd.Series(poste).map(TAUX_RO).values.copy()
    reforme_dentaire = (poste == "DENTAIRE") & (d.date_soins.values >= np.datetime64("2023-10-01"))
    taux_ro[reforme_dentaire] *= 60 / 70  # baisse du remboursement RO des soins dentaires au 1er octobre 2023
    ro = np.minimum(frais * taux_ro * rng.uniform(0.9, 1.1, n), frais * 0.95)
    f_form = pd.Series(formule[d.idx.values]).map(FACTEUR_FORMULE).values
    part = pd.Series(poste).map({k: v[2] for k, v in POSTES.items()}).values * f_form
    part = np.where(reforme_dentaire, part * 1.10, part)
    rc = np.minimum(frais - ro, frais * part * rng.uniform(0.85, 1.15, n))
    rc = np.maximum(rc, 0.0)
    base = ro / pd.Series(poste).map(TAUX_SS_THEORIQUE).values
    d["frais_reels"] = np.round(frais, 2)
    d["base_remboursement"] = np.round(base, 2)
    d["montant_ro"] = np.round(ro, 2)
    d["montant_rembourse"] = np.round(rc, 2)
    d["nb_actes"] = np.maximum(1, rng.poisson(pd.Series(poste).map({"PHARMACIE": 2.5, "SOINS_COURANTS": 1.8, "BIOLOGIE": 1.2}).fillna(0.2).values) + 0).astype(int)
    d["id_assure"] = b.id_assure.values[d.idx.values]
    d["id_contrat"] = b.id_contrat.values[d.idx.values]
    d["segment"] = b.segment.values[d.idx.values]
    # --------------------------------------------------------------- delais de paiement
    fixe = pd.Series(poste).map({k: v[4] for k, v in POSTES.items()}).values
    k = pd.Series(poste).map({k: v[5][0] for k, v in POSTES.items()}).values
    th = pd.Series(poste).map({k: v[5][1] for k, v in POSTES.items()}).values
    delai = fixe + rng.gamma(k, th)
    p_tard = pd.Series(poste).map({k: v[6] for k, v in POSTES.items()}).values
    tard = rng.random(n) < p_tard
    tmin = pd.Series(poste).map({k: v[7][0] for k, v in POSTES.items()}).values
    tmax = pd.Series(poste).map({k: v[7][1] for k, v in POSTES.items()}).values
    delai = delai + np.where(tard, rng.uniform(tmin, tmax), 0.0)
    papier = rng.random(n) < 0.05
    delai = delai + np.where(papier, rng.uniform(15, 60, n), 0.0)
    paiement = d.date_soins.values + np.round(delai).astype(int) * J
    # bascule du systeme de gestion : file d'attente du 16 octobre au 31 decembre 2023, rattrapage debut 2024
    fenetre = (paiement >= np.datetime64("2023-10-16")) & (paiement <= np.datetime64("2023-12-31"))
    retard = fenetre & (rng.random(n) < 0.55)
    paiement = paiement + np.where(retard, rng.uniform(20, 75, n).astype(int), 0) * J
    d["date_paiement"] = paiement
    canal = np.where(np.isin(poste, ["PHARMACIE"]) | ((poste == "HOSPITALISATION") & (rng.random(n) < 0.7)), "TIERS_PAYANT",
                     np.where(np.isin(poste, ["DENTAIRE", "OPTIQUE", "AUDIOLOGIE"]), "DEVIS_FACTURE", "NOEMIE"))
    d["canal"] = np.where(papier, "PAPIER", canal)
    d["type_ligne"] = "PRESTATION"
    d["id_decompte"] = ids("D", n, 9)
    # --------------------------------------------------------------- regularisations (indus recuperes)
    reg = rng.random(n) < 0.005
    r = d[reg].copy()
    frac = np.where(rng.random(len(r)) < 0.6, 1.0, 0.5)
    for col in ("frais_reels", "base_remboursement", "montant_ro", "montant_rembourse"):
        r[col] = -np.round(r[col].values * frac, 2)
    r["nb_actes"] = 0
    r["type_ligne"] = "REGULARISATION"
    r["date_paiement"] = r.date_paiement.values + rng.integers(20, 150, len(r)) * J
    d = pd.concat([d, r], ignore_index=True)
    d = d[d.date_paiement <= np.datetime64("2026-12-31")].copy()
    d = d.sort_values(["date_paiement", "id_decompte", "type_ligne"]).reset_index(drop=True)
    d["id_ligne"] = ids("L", len(d), 10)
    return d.drop(columns=["idx", "mois"])


FORMULES = {}


def enregistrer_formules(contrats):
    FORMULES.update(dict(zip(contrats.id_contrat, contrats.formule)))


# ============================================================================= cotisations sante
def tarif_mensuel_brut(aff_sante, contrats, mois):
    """Cotisation mensuelle brute (avant calage) par affiliation et par mois."""
    b = aff_sante
    milieu = mois.astype("datetime64[D]") + 14 * J
    adh = b.date_adhesion.values.astype("datetime64[D]")
    rad = b.date_radiation_brute.values.astype("datetime64[D]")
    rad = np.where(np.isnat(rad), FIN, rad)
    couvert = (adh[:, None] <= milieu[None, :]) & (rad[:, None] >= milieu[None, :])
    age = age_a(b.date_naissance.values.astype("datetime64[D]")[:, None], milieu[None, :])
    formule = b.id_contrat.map(FORMULES).fillna("CONFORT").values
    f_form = pd.Series(formule).map({"ESSENTIEL": 0.80, "CONFORT": 1.00, "RENFORCE": 1.32}).values
    ind = (b.segment == "IND").values
    enfant = (b.qualite == "ENFANT").values
    t_ind = np.where(enfant[:, None], 22.0, 38.0 * np.exp(0.016 * (np.clip(age, 18, 95) - 40)))
    ajust = b.id_contrat.map(dict(zip(contrats.id_contrat, contrats.ajustement_experience))).fillna(1.0).values
    famille = b.option_famille.fillna(False).astype(bool).values
    t_col = np.where((b.qualite == "ASSURE").values, np.where(famille, 105.0, 45.0), 0.0) * ajust
    t_col = np.broadcast_to(t_col[:, None], couvert.shape)
    tarif = np.where(ind[:, None], t_ind, t_col) * f_form[:, None]
    return np.where(couvert, tarif, 0.0)


def simuler_cotisations_sante(rng, aff, contrats_sante, soins):
    b = aff[aff.branche == "SANTE"].reset_index(drop=True)
    mois = MOIS
    brut = tarif_mensuel_brut(b, contrats_sante, mois)
    annees = mois.astype("datetime64[Y]").astype(int) + 1970
    seg = b.segment.values
    indice = np.array([[INDICE_TARIF_SANTE[s][a] for a in annees] for s in ("IND", "COL")])
    brut = brut * np.where((seg == "IND")[:, None], indice[0][None, :], indice[1][None, :])  # indice par segment
    # calage : S/P 2021 cible par segment
    s21 = soins[(soins.date_soins.dt.year == 2021)].groupby("segment").montant_rembourse.sum()
    for k, s in enumerate(("IND", "COL")):
        m = seg == s
        p21 = brut[m][:, annees == 2021].sum()
        brut[m] *= s21[s] / (SP_CIBLE_2021[s] * p21)
    df = pd.DataFrame(brut, columns=[str(x) for x in mois])
    df["id_contrat"] = b.id_contrat.values
    agg = df.groupby("id_contrat").sum()
    long = agg.stack().reset_index()
    long.columns = ["id_contrat", "periode", "montant_cotisation_ht"]
    long = long[long.montant_cotisation_ht > 0].copy()
    long["montant_cotisation_ht"] = long.montant_cotisation_ht.round(2)
    long["garantie"] = "FRAIS_DE_SANTE"
    p = pd.to_datetime(long.periode)
    long["date_debut_periode"] = p
    long["date_fin_periode"] = p + pd.offsets.MonthEnd(0)
    long["date_emission"] = p - pd.Timedelta(days=5)
    return long.drop(columns=["periode"]).reset_index(drop=True)
