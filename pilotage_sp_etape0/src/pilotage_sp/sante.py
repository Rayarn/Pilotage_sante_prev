"""Provisions pour sinistres a payer (PSAP) sante : triangles mensuels, Chain Ladder, Mack, Bornhuetter-Ferguson.

Entree : increments de paiements agreges (segment, mois de soins, mois de paiement, montant), cotisations
acquises mensuelles par segment, hypotheses de l'arrete. Tout est deterministe et en pandas : le volume
est celui d'un triangle (quelques milliers de cellules), l'agregation amont est faite en Spark.
"""

import numpy as np
import pandas as pd

NB_LAGS = 24  # au-dela de 24 mois de developpement, la sante est consideree comme liquidee (facteur 1)


def _mois(x):
    return pd.PeriodIndex(pd.to_datetime(x), freq="M") if not isinstance(x, pd.PeriodIndex) else x


def triangle(increments, date_arrete, segment):
    """Triangle cumule : lignes = mois de soins, colonnes = anciennete 0..NB_LAGS-1 (NaN hors diagonale)."""
    fin = pd.Timestamp(date_arrete).to_period("M")
    d = increments[increments.segment == segment].copy()
    d["ms"] = _mois(d.mois_soins)
    d["mp"] = _mois(d.mois_paiement)
    d = d[(d.mp <= fin) & (d.ms <= fin)]
    d["lag"] = (d.mp - d.ms).apply(lambda x: x.n).clip(lower=0)
    d.loc[d.lag >= NB_LAGS, "lag"] = NB_LAGS - 1
    origines = pd.period_range(d.ms.min(), fin, freq="M")
    inc = d.pivot_table(index="ms", columns="lag", values="montant", aggfunc="sum").reindex(index=origines, columns=range(NB_LAGS))
    inc = inc.fillna(0.0)
    cum = inc.cumsum(axis=1)
    age = np.array([(fin - o).n for o in origines])
    masque = np.arange(NB_LAGS)[None, :] > age[:, None]
    return cum.mask(masque), age


def facteurs_chain_ladder(cum, age, profondeur):
    """Facteurs ponderes par les volumes, estimes sur les `profondeur` derniers mois calendaires."""
    c = cum.to_numpy()
    n = c.shape[0]
    f = np.ones(NB_LAGS - 1)
    poids = np.zeros(NB_LAGS - 1)
    sigma2 = np.full(NB_LAGS - 1, np.nan)
    for j in range(NB_LAGS - 1):
        # cellule (i, j+1) observee et situee dans la fenetre calendaire : age_i - (j+1) < profondeur
        i = np.nonzero((age >= j + 1) & (age - (j + 1) < profondeur))[0]
        i = i[np.isfinite(c[i, j]) & np.isfinite(c[i, j + 1]) & (c[i, j] > 0)]
        if len(i) == 0:
            continue
        f[j] = c[i, j + 1].sum() / c[i, j].sum()
        poids[j] = c[i, j].sum()
        if len(i) > 1:
            sigma2[j] = (c[i, j] * (c[i, j + 1] / c[i, j] - f[j]) ** 2).sum() / (len(i) - 1)
    # extrapolation de Mack pour les derniers sigma2 non estimables
    for j in range(NB_LAGS - 1):
        if poids[j] == 0:
            sigma2[j] = 0.0
        elif np.isnan(sigma2[j]):
            prec = sigma2[:j][~np.isnan(sigma2[:j]) & (sigma2[:j] > 0)]
            sigma2[j] = min(prec[-1] ** 2 / prec[-2], prec[-2], prec[-1]) if len(prec) >= 2 else (prec[-1] if len(prec) else 0.0)
    return f, poids, sigma2


def mack(cum, age, f, poids, sigma2):
    """Erreur quadratique de prediction de Mack (1993) par origine et totale."""
    c = cum.to_numpy()
    n = c.shape[0]
    proj = c.copy()
    for j in range(NB_LAGS - 1):
        manque = np.isnan(proj[:, j + 1])
        proj[manque, j + 1] = proj[manque, j] * f[j]
    ult = proj[:, -1]
    mse = np.zeros(n)
    terme_param = np.zeros(NB_LAGS - 1)
    for j in range(NB_LAGS - 1):
        if poids[j] > 0 and f[j] > 0:
            terme_param[j] = sigma2[j] / f[j] ** 2 / poids[j]
    for i in range(n):
        k0 = min(age[i], NB_LAGS - 1)
        s = 0.0
        for k in range(k0, NB_LAGS - 1):
            if f[k] > 0 and proj[i, k] > 0:
                s += sigma2[k] / f[k] ** 2 * (1.0 / proj[i, k] + (1.0 / poids[k] if poids[k] > 0 else 0.0))
        mse[i] = ult[i] ** 2 * s
    total = mse.sum()
    for i in range(n):
        for l in range(i + 1, n):
            k0 = min(age[i], NB_LAGS - 1)
            total += 2 * ult[i] * ult[l] * terme_param[k0:].sum()
    return np.sqrt(np.maximum(mse, 0)), float(np.sqrt(max(total, 0.0)))


def provisions_sante(increments, cotisations, h, date_arrete):
    """PSAP par segment et mois de soins. `cotisations` : segment, mois, montant (acquises)."""
    fin = pd.Timestamp(date_arrete).to_period("M")
    lignes, resume = [], []
    for segment in sorted(increments.segment.unique()):
        cum, age = triangle(increments, date_arrete, segment)
        f, poids, sigma2 = facteurs_chain_ladder(cum, age, h.profondeur_facteurs_mois)
        f_cum = np.concatenate([np.cumprod(f[::-1])[::-1], [1.0]])  # facteur de l'anciennete j a l'ultime
        se_i, se_total = mack(cum, age, f, poids, sigma2)
        diag = np.array([cum.iloc[i, min(a, NB_LAGS - 1)] for i, a in enumerate(age)])
        fc = f_cum[np.minimum(age, NB_LAGS - 1)]
        ult_cl = diag * fc
        cot = cotisations[cotisations.segment == segment].copy()
        cot["m"] = _mois(cot.mois)
        prime = cot.groupby("m").montant.sum().reindex(cum.index).fillna(0.0).to_numpy()
        sp = h.sp_apriori(segment)
        ult_bf = diag + (1 - 1 / fc) * sp * prime
        ult_elr = np.maximum(sp * prime, diag)
        elr = age < h.nb_mois_sp_apriori
        bf = (age < h.nb_mois_bf) & ~elr
        ult = np.where(elr, ult_elr, np.where(bf, ult_bf, ult_cl))
        df = pd.DataFrame({"segment": segment, "mois_soins": cum.index.astype(str), "anciennete_mois": age,
                           "paye_cumule": diag, "facteur_cumule": fc, "cotisation_acquise": prime,
                           "ultime_chain_ladder": ult_cl, "ultime_bornhuetter_ferguson": np.where(bf, ult_bf, np.nan),
                           "ultime_sp_a_priori": np.where(elr, ult_elr, np.nan),
                           "methode": np.where(elr, "SP_A_PRIORI", np.where(bf, "BORNHUETTER_FERGUSON", "CHAIN_LADDER")),
                           "ultime_retenu": ult,
                           "psap": ult - diag, "ecart_type_mack": se_i})
        lignes.append(df)
        resume.append({"segment": segment, "psap": float((ult - diag).sum()),
                       "psap_chain_ladder": float((ult_cl - diag).sum()), "ecart_type_mack": se_total,
                       "facteurs": f.tolist()})
    detail = pd.concat(lignes, ignore_index=True)
    detail["annee_soins"] = detail.mois_soins.str[:4].astype(int)
    detail["pfgs"] = detail.psap * h.taux_pfgs_sante
    return detail, pd.DataFrame(resume)


def facteurs_table(increments, h, date_arrete):
    """Restitution des facteurs de developpement (note technique, annexes)."""
    out = []
    for segment in sorted(increments.segment.unique()):
        cum, age = triangle(increments, date_arrete, segment)
        f, _, sigma2 = facteurs_chain_ladder(cum, age, h.profondeur_facteurs_mois)
        out.append(pd.DataFrame({"segment": segment, "anciennete": range(NB_LAGS - 1), "facteur": f, "sigma2": sigma2}))
    return pd.concat(out, ignore_index=True)
