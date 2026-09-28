"""Simulation des sinistres de prevoyance (incapacite, invalidite, deces), des paiements et des cotisations.

Les durees sont tirees dans les lois BCAC (maintien en incapacite, passage en invalidite,
maintien en invalidite), la mortalite des actifs dans TH/TF 00-02 abattues : le moteur de
provisionnement utilise les memes lois, l'ecart entre realise et provisionne vient donc
de l'aleatoire, des delais de declaration et des hypotheses (taux, bareme de retraite).
"""

import numpy as np
import pandas as pd

from monde import (TENDANCE_ARRETS, INDICE_TARIF_PREV, SP_CIBLE_PREV, DEBUT_PREV, FIN, HORIZON_FLUX, J,
                   jours, date_de, ajouter_mois, age_a, ids, salaire_a)
from pilotage_sp.retraite import age_legal_reel_mois

ABATTEMENT_MORTALITE_ACTIFS = 0.55
PART_DECES_SORTIES_INVALIDITE = 0.55
REPARTITION_CATEGORIES = ([1, 2, 3], [0.15, 0.75, 0.10])


def incidence_arrets(age, sexe):
    """Frequence annuelle d'arrets de travail (toutes durees, avant franchise)."""
    base = 0.028 + 0.0011 * (np.clip(age, 18, 67) - 20)
    return base * np.where(sexe == "F", 1.12, 0.92)


def _delai_gamma(rng, k, theta, n):
    return np.round(rng.gamma(k, theta, n)).astype(int) * J


# ============================================================================= exposition et evenements
def preparer_assures(aff, cc):
    p = aff[aff.branche == "PREVOYANCE"].copy().reset_index(drop=True)
    garanties = cc[cc.branche == "PREVOYANCE"][["id_contrat", "franchise_incap_jours", "taux_ij", "taux_rente_invalidite",
                                                  "multiple_capital_non_cadre", "multiple_capital_cadre", "ajustement_experience"]]
    p = p.merge(garanties, on="id_contrat", how="left")
    col = (p.segment == "COL").values
    p.loc[~col, "franchise_incap_jours"] = p.loc[~col, "franchise_jours"]
    p["ajustement_experience"] = p["ajustement_experience"].fillna(1.0)
    naiss = p.date_naissance.values.astype("datetime64[D]")
    p["date_retraite_reelle"] = ajouter_mois(naiss, age_legal_reel_mois(naiss))
    return p


def tirer_evenements(rng, p):
    """Arrets de travail et deces d'actifs, annee par annee (2010 a 2025)."""
    adh = p.date_adhesion.values.astype("datetime64[D]")
    rad = p.date_radiation_brute.values.astype("datetime64[D]")
    rad = np.where(np.isnat(rad), FIN, rad)
    naiss = p.date_naissance.values.astype("datetime64[D]")
    sexe = p.sexe.values
    ind = (p.segment == "IND").values
    arrets, deces, expo_lignes = [], [], []
    for annee in range(2010, 2026):
        a = np.maximum(adh, np.datetime64(f"{annee}-01-01"))
        b = np.minimum(rad, np.datetime64(f"{annee}-12-31"))
        ok = b >= a
        expo = np.where(ok, ((b - a).astype(int) + 1) / 365.25, 0.0)
        milieu = a + ((b - a).astype(int) // 2) * J
        age = np.where(ok, age_a(naiss, milieu), 40)
        facteur = TENDANCE_ARRETS[annee] * p.facteur_arrets.values * np.where(ind, 0.80, 1.0)
        lam = incidence_arrets(age, sexe) * facteur * expo
        n = rng.poisson(lam)
        i = np.repeat(np.nonzero(n)[0], n[n > 0])
        if len(i):
            arrets.append(pd.DataFrame({"idx": i, "date_survenance": dates_entre(rng, a[i], b[i])}))
        qx = np.where(sexe == "F", QX["F"][np.clip(age.astype(int), 0, 120)], QX["H"][np.clip(age.astype(int), 0, 120)])
        d = rng.random(len(p)) < 1 - (1 - qx * ABATTEMENT_MORTALITE_ACTIFS) ** expo
        i = np.nonzero(d & ok)[0]
        if len(i):
            deces.append(pd.DataFrame({"idx": i, "date_deces": dates_entre(rng, a[i], b[i])}))
        expo_lignes.append(pd.DataFrame({"idx": np.nonzero(ok)[0], "annee": annee, "exposition": expo[ok], "age": age[ok]}))
    return pd.concat(arrets, ignore_index=True), pd.concat(deces, ignore_index=True), pd.concat(expo_lignes, ignore_index=True)


def dates_entre(rng, a, b):
    ja, jb = jours(a), jours(b)
    return date_de(ja + np.floor(rng.random(len(ja)) * (jb - ja + 1)).astype(np.int64))


QX = {}


# ============================================================================= incapacite
def simuler_incapacites(rng, p, arrets, tables):
    x = arrets.merge(p, left_on="idx", right_index=True)
    surv = x.date_survenance.values.astype("datetime64[D]")
    naiss = x.date_naissance.values.astype("datetime64[D]")
    age_entree = np.floor(age_a(naiss, surv)).astype(int)
    franchise = x.franchise_incap_jours.values.astype(int)
    f_mois = np.where(franchise >= 90, 3, 1)
    L = tables.ligne_incapacite(age_entree)              # (n, 37)
    lf = L[np.arange(len(x)), f_mois]
    garder = rng.random(len(x)) < lf / 10000.0           # l'arret depasse la franchise
    x, surv, naiss, age_entree, franchise, f_mois, L, lf = (x[garder].reset_index(drop=True), surv[garder], naiss[garder],
                                                            age_entree[garder], franchise[garder], f_mois[garder],
                                                            L[garder], lf[garder])
    debut_ij = surv + franchise * J
    # le salarie deja parti a la retraite avant la fin de franchise n'est pas indemnise
    retraite = x.date_retraite_reelle.values.astype("datetime64[D]")
    ok = debut_ij < retraite
    x, surv, naiss, age_entree, franchise, f_mois, L, lf, debut_ij, retraite = (
        x[ok].reset_index(drop=True), surv[ok], naiss[ok], age_entree[ok], franchise[ok], f_mois[ok], L[ok], lf[ok],
        debut_ij[ok], retraite[ok])
    n = len(x)
    # mois de sortie K >= f : P(K = k) = (l_k - l_{k+1}) / l_f
    survie = L[:, 1:] / lf[:, None]                        # survie au-dela du mois k, k = 0..35
    k_idx = np.arange(36)[None, :]
    survie = np.where(k_idx < f_mois[:, None], np.inf, survie)
    u = rng.random(n)
    K = np.argmax(survie < u[:, None], axis=1)
    deb_k = ajouter_mois(surv, K)
    fin_k = ajouter_mois(surv, K + 1)
    sortie = deb_k + np.floor(rng.random(n) * (fin_k - deb_k).astype(int)).astype(int) * J
    sortie = np.maximum(sortie, debut_ij + J)
    # nature de la sortie
    P = tables.ligne_passage(age_entree)
    sorties_k = L[np.arange(n), K] - L[np.arange(n), K + 1]
    p_pass = np.clip(P[np.arange(n), K] / np.maximum(sorties_k, 1e-9), 0, 1)
    u2 = rng.random(n)
    p_deces = 0.010 + 0.0006 * (age_entree - 20)
    motif = np.where(u2 < p_pass, "PASSAGE_INVALIDITE",
                     np.where(u2 < p_pass + (1 - p_pass) * p_deces, "DECES",
                              np.where(K == 35, "FIN_DE_DROITS", "REPRISE_ACTIVITE")))
    en_retraite = retraite <= sortie
    sortie = np.where(en_retraite, retraite, sortie)
    motif = np.where(en_retraite, "RETRAITE", motif)
    salaire = np.where(x.segment == "COL", salaire_a(x.salaire_embauche.values,
                                                     x.date_embauche.values.astype("datetime64[D]"), surv), np.nan)
    ij = np.where(x.segment == "COL", np.round(x.taux_ij.values * salaire / 365.0, 2), x.ij_garantie_journaliere.values)
    decl = debut_ij + _delai_gamma(rng, 1.6, 12.0, n)
    tardive = rng.random(n) < 0.10
    decl = decl + np.where(tardive, rng.integers(60, 420, n), 0) * J
    return pd.DataFrame({
        "idx": x.idx.values, "garantie": "INCAPACITE", "date_survenance": surv, "date_declaration": decl,
        "franchise_jours": franchise, "date_debut_indemnisation": debut_ij, "ij_journaliere": ij,
        "salaire_reference": np.round(salaire, 2), "age_entree": age_entree, "date_fin_reelle": sortie, "motif_fin_reel": motif,
    })


def coherence_parcours(inc):
    """Un assure n'a qu'un arret indemnise a la fois et ne rechute plus en incapacite apres un passage en invalidite."""
    inc = inc.sort_values(["idx", "date_survenance"]).reset_index(drop=True)
    for _ in range(3):
        g = inc.groupby("idx")
        fin_prec = g.date_fin_reelle.transform(lambda s: s.cummax().shift())
        passage = (inc.motif_fin_reel == "PASSAGE_INVALIDITE").astype(int)
        passage_prec = passage.groupby(inc.idx).transform(lambda s: s.cumsum().shift(fill_value=0))
        ok = (fin_prec.isna() | (inc.date_survenance > fin_prec)) & (passage_prec == 0)
        if ok.all():
            break
        inc = inc[ok].reset_index(drop=True)
    return inc


# ============================================================================= invalidite
def simuler_invalidites(rng, p, inc, tables):
    passages = inc[inc.motif_fin_reel == "PASSAGE_INVALIDITE"].reset_index(drop=True)
    x = passages[["idx", "id_sinistre", "date_fin_reelle", "salaire_reference"]].merge(p, left_on="idx", right_index=True)
    n = len(x)
    surv = x.date_fin_reelle.values.astype("datetime64[D]")
    naiss = x.date_naissance.values.astype("datetime64[D]")
    age = np.floor(age_a(naiss, surv)).astype(int)
    retraite = x.date_retraite_reelle.values.astype("datetime64[D]")
    cat = rng.choice(REPARTITION_CATEGORIES[0], n, p=REPARTITION_CATEGORIES[1])
    rente_base = np.where(x.segment == "COL", x.taux_rente_invalidite.values * x.salaire_reference.values,
                          x.rente_invalidite_garantie_annuelle.values)
    rente = np.round(rente_base * np.where(cat == 1, 0.6, 1.0), 2)
    duree_mois = np.full(n, 10 ** 6)
    u = rng.random(n)
    for a in np.unique(age):
        m = age == a
        lx = tables.lx_invalidite_mensuel(a, 540)
        s = lx[1:] / lx[0]
        k = np.argmax(s[None, :] < u[m][:, None], axis=1)
        k = np.where((s[None, :] < u[m][:, None]).any(axis=1), k, 540)
        duree_mois[m] = k
    deb = ajouter_mois(surv, duree_mois)
    fin = ajouter_mois(surv, duree_mois + 1)
    sortie = deb + np.floor(rng.random(n) * (fin - deb).astype(int)).astype(int) * J
    motif = np.where(rng.random(n) < PART_DECES_SORTIES_INVALIDITE, "DECES", "REPRISE_ACTIVITE")
    en_retraite = retraite <= sortie
    sortie = np.where(en_retraite, retraite, sortie)
    motif = np.where(en_retraite, "RETRAITE", motif)
    return pd.DataFrame({
        "idx": x.idx.values, "garantie": "INVALIDITE", "id_sinistre_origine": x.id_sinistre.values, "date_survenance": surv,
        "date_declaration": surv + _delai_gamma(rng, 2.0, 10.0, n), "categorie_invalidite": cat, "rente_annuelle": rente,
        "salaire_reference": x.salaire_reference.values, "age_entree": age, "date_fin_reelle": sortie,
        "motif_fin_reel": motif, "date_debut_indemnisation": surv})


# ============================================================================= deces
def simuler_deces(rng, p, deces_actifs, inc, inv):
    morts = [deces_actifs.assign(id_sinistre_origine=None)]
    for s in (inc, inv):
        d = s[s.motif_fin_reel == "DECES"]
        morts.append(pd.DataFrame({"idx": d.idx.values, "date_deces": d.date_fin_reelle.values,
                                   "id_sinistre_origine": d.id_sinistre.values}))
    m = pd.concat(morts, ignore_index=True).sort_values("date_deces").drop_duplicates("idx")
    x = m.merge(p, left_on="idx", right_index=True)
    n = len(x)
    dd = x.date_deces.values.astype("datetime64[D]")
    salaire = np.where(x.segment == "COL", salaire_a(x.salaire_embauche.values, x.date_embauche.values.astype("datetime64[D]"),
                                                     dd), np.nan)
    multiple = np.where(x.cadre.values, x.multiple_capital_cadre.values, x.multiple_capital_non_cadre.values)
    capital = np.where(x.segment == "COL", np.round(multiple * salaire, 2), x.capital_deces_garanti.values)
    decl = dd + _delai_gamma(rng, 1.5, 20.0, n)
    tardive = rng.random(n) < 0.08
    decl = decl + np.where(tardive, rng.integers(90, 720, n), 0) * J
    return pd.DataFrame({"idx": x.idx.values, "garantie": "DECES", "id_sinistre_origine": x.id_sinistre_origine.values,
                         "date_survenance": dd, "date_declaration": decl, "capital": capital,
                         "salaire_reference": np.round(salaire, 2), "date_fin_reelle": dd, "motif_fin_reel": "DECES",
                         "date_debut_indemnisation": dd})


# ============================================================================= paiements
def paiements_periodiques(rng, sin, montant_jour):
    """Echeances mensuelles de debut d'indemnisation a la date de fin reelle (plafonnee a l'horizon)."""
    deb = sin.date_debut_indemnisation.values.astype("datetime64[D]")
    fin = np.minimum(sin.date_fin_reelle.values.astype("datetime64[D]"), HORIZON_FLUX)
    decl = sin.date_declaration.values.astype("datetime64[D]")
    nb = np.maximum(((fin.astype("datetime64[M]") - deb.astype("datetime64[M]")).astype(int)) + 2, 0)
    i = np.repeat(np.arange(len(sin)), nb)
    k = np.concatenate([np.arange(v) for v in nb]) if len(nb) else np.array([], int)
    p_deb = ajouter_mois(deb[i], k)
    p_fin = np.minimum(ajouter_mois(deb[i], k + 1) - J, fin[i])
    ok = p_fin >= p_deb
    i, p_deb, p_fin = i[ok], p_deb[ok], p_fin[ok]
    jours_p = (p_fin - p_deb).astype(int) + 1
    montant = np.round(montant_jour[i] * jours_p, 2)
    date_p = np.maximum(p_fin + np.round(rng.gamma(2.0, 3.0, len(i))).astype(int) * J, decl[i] + rng.integers(8, 25, len(i)) * J)
    return pd.DataFrame({"id_sinistre": sin.id_sinistre.values[i], "garantie": sin.garantie.values[i],
                         "date_debut_periode": p_deb, "date_fin_periode": p_fin, "date_paiement": date_p,
                         "montant": montant, "type_paiement": np.where(sin.garantie.values[i] == "INCAPACITE", "IJ", "RENTE")})


def simuler_paiements(rng, inc, inv, dec):
    p1 = paiements_periodiques(rng, inc, inc.ij_journaliere.values)
    p2 = paiements_periodiques(rng, inv, inv.rente_annuelle.values / 365.25)
    decl = dec.date_declaration.values.astype("datetime64[D]")
    date_p = decl + np.round(rng.gamma(2.0, 12.0, len(dec))).astype(int) * J
    p3 = pd.DataFrame({"id_sinistre": dec.id_sinistre.values, "garantie": "DECES", "date_debut_periode": dec.date_survenance.values,
                       "date_fin_periode": dec.date_survenance.values, "date_paiement": date_p, "montant": dec.capital.values,
                       "type_paiement": "CAPITAL"})
    pay = pd.concat([p1, p2, p3], ignore_index=True)
    pay = pay[pay.date_paiement <= HORIZON_FLUX].sort_values(["date_paiement", "id_sinistre"]).reset_index(drop=True)
    pay["id_paiement"] = ids("V", len(pay), 9)
    return pay


def cout_total(sin):
    """Cout ultime non actualise (duree complete simulee, au-dela de l'horizon), base du calage tarifaire."""
    duree = (sin.date_fin_reelle.values.astype("datetime64[D]") - sin.date_debut_indemnisation.values.astype("datetime64[D]")).astype(int)
    c = np.where(sin.garantie == "INCAPACITE", sin.ij_journaliere.fillna(0).values * np.maximum(duree, 0), 0.0)
    c = c + np.where(sin.garantie == "INVALIDITE", sin.rente_annuelle.fillna(0).values * np.maximum(duree, 0) / 365.25, 0.0)
    c = c + np.where(sin.garantie == "DECES", sin.capital.fillna(0).values, 0.0)
    return c


# ============================================================================= cotisations
def simuler_cotisations_prevoyance(rng, p, expo, sin):
    """Cotisations calees par garantie sur un S/P cible (survenances 2012-2019), puis indexees (hausses 2023-2025)."""
    e = expo.merge(p[["segment", "id_contrat", "salaire_embauche", "date_embauche", "ajustement_experience",
                      "ij_garantie_journaliere", "rente_invalidite_garantie_annuelle", "capital_deces_garanti", "sexe"]],
                   left_on="idx", right_index=True)
    milieu = pd.to_datetime(e.annee.astype(str) + "-07-01").values.astype("datetime64[D]")
    col = (e.segment == "COL").values
    sal = np.where(col, salaire_a(e.salaire_embauche.values, e.date_embauche.values.astype("datetime64[D]"), milieu), 0.0)
    age = e.age.values
    qx = np.where(e.sexe.values == "F", QX["F"][np.clip(age.astype(int), 0, 120)], QX["H"][np.clip(age.astype(int), 0, 120)])
    base = {
        "INCAPACITE": np.where(col, sal, e.ij_garantie_journaliere.fillna(0).values * 365 * incidence_arrets(age, "H") * 4),
        "INVALIDITE": np.where(col, sal, e.rente_invalidite_garantie_annuelle.fillna(0).values * np.exp(0.05 * (age - 40)) * 0.05),
        "DECES": np.where(col, sal, e.capital_deces_garanti.fillna(0).values * qx),
    }
    s = sin.copy()
    s["annee"] = s.date_survenance.dt.year
    orig = s.set_index("id_sinistre").date_survenance.dt.year
    s.loc[s.garantie == "INVALIDITE", "annee"] = s.loc[s.garantie == "INVALIDITE", "id_sinistre_origine"].map(orig).values
    s["cout"] = cout_total(s)
    lignes = []
    for seg in ("COL", "IND"):
        m_seg = e.segment.values == seg
        for g, b in base.items():
            fenetre = (e.annee.values >= 2012) & (e.annee.values <= 2019) & m_seg
            charge = s[(s.segment == seg) & (s.garantie == g) & s.annee.between(2012, 2019)].cout.sum()
            assiette = (b * e.exposition.values * e.ajustement_experience.values)[fenetre].sum()
            taux = charge / (SP_CIBLE_PREV[seg] * assiette)
            prime = b * e.exposition.values * e.ajustement_experience.values * taux * e.annee.map(INDICE_TARIF_PREV).values
            lignes.append(pd.DataFrame({"id_contrat": e.id_contrat.values[m_seg], "annee": e.annee.values[m_seg],
                                        "garantie": g, "prime": prime[m_seg]}))
    return pd.concat(lignes, ignore_index=True).groupby(["id_contrat", "annee", "garantie"], as_index=False).prime.sum()


def etaler_cotisations(prime_annuelle, segment_contrat):
    """COL : 12 echeances mensuelles ; IND : 4 echeances trimestrielles, emises en debut de periode."""
    x = prime_annuelle.merge(segment_contrat, on="id_contrat")
    blocs = []
    for seg, pas in (("COL", 1), ("IND", 3)):
        y = x[x.segment == seg]
        for debut in range(1, 13, pas):
            d = pd.to_datetime(y.annee.astype(str) + f"-{debut:02d}-01")
            blocs.append(pd.DataFrame({"id_contrat": y.id_contrat.values, "garantie": y.garantie.values,
                                       "date_debut_periode": d.values,
                                       "date_fin_periode": (d + pd.offsets.MonthEnd(pas)).values,
                                       "montant_cotisation_ht": np.round(y.prime.values * pas / 12, 2)}))
    c = pd.concat(blocs, ignore_index=True)
    c = c[c.montant_cotisation_ht > 0]
    c["date_emission"] = c.date_debut_periode - pd.Timedelta(days=5)
    return c.reset_index(drop=True)


# ============================================================================= orchestration
def simuler_prevoyance(rng, aff, cc, tables):
    QX["H"], QX["F"] = tables.qx["H"], tables.qx["F"]
    p = preparer_assures(aff, cc)
    arrets, deces_actifs, expo = tirer_evenements(rng, p)
    deces_actifs = deces_actifs.sort_values("date_deces").drop_duplicates("idx")
    # pas d'arret apres le deces
    d = arrets.merge(deces_actifs, on="idx", how="left")
    arrets = arrets[~(d.date_deces.notna() & (d.date_survenance >= d.date_deces)).values].reset_index(drop=True)
    inc = simuler_incapacites(rng, p, arrets, tables)
    inc = coherence_parcours(inc)
    inc["id_sinistre"] = ids("SIN", len(inc), 7)
    inv = simuler_invalidites(rng, p, inc, tables)
    inv["id_sinistre"] = ids("SIN", len(inv), 7, depart=len(inc))
    # un deces d'actif survenant pendant une incapacite ou une invalidite est porte par ces sinistres
    periodes = pd.concat([inc[["idx", "date_survenance", "date_fin_reelle"]], inv[["idx", "date_survenance", "date_fin_reelle"]]])
    m = deces_actifs.reset_index(drop=True).reset_index().merge(periodes, on="idx")
    couvert = m[(m.date_deces >= m.date_survenance) & (m.date_deces <= m.date_fin_reelle)]["index"].unique()
    deces_actifs = deces_actifs.reset_index(drop=True).drop(index=couvert)
    dec = simuler_deces(rng, p, deces_actifs, inc, inv)
    dec["id_sinistre"] = ids("SIN", len(dec), 7, depart=len(inc) + len(inv))
    sin = pd.concat([inc, inv, dec], ignore_index=True)
    ident = p[["id_assure", "id_personne", "id_contrat", "segment", "sexe", "date_naissance", "cadre", "date_adhesion"]]
    sin = sin.merge(ident, left_on="idx", right_index=True)
    for c in ("date_survenance", "date_declaration", "date_debut_indemnisation", "date_fin_reelle"):
        sin[c] = pd.to_datetime(sin[c])
    # un sinistre n'existe que s'il survient avant la fin de la fenetre (les arrets de fin 2025 peuvent ne pas etre declares)
    sin = sin[sin.date_survenance <= pd.Timestamp(FIN)].reset_index(drop=True)
    pay = simuler_paiements(rng, sin[sin.garantie == "INCAPACITE"], sin[sin.garantie == "INVALIDITE"], sin[sin.garantie == "DECES"])
    primes = simuler_cotisations_prevoyance(rng, p, expo, sin)
    return p, sin, pay, primes
