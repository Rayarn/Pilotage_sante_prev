"""Provisions de prevoyance : incapacite, invalidite (dont rentes en attente), deces, IBNR, PMGD.

Cadre : article A331-22 du Code des assurances (lois BCAC, taux plafonne a 75 % du TME moyen 24 mois).
Conventions (detaillees et illustrees dans la note technique) :
- anciennete s en mois entiers ecoules depuis la survenance de l'arret ; premier mois certain ;
- PM incapacite  = IJ_m * somme_{k=0}^{K} L(s+k)/L(s) * v^(k/12) ;
- PM passage     = somme_{k=0}^{K} N(s+k)/L(s) * v^((k+1)/12) * R * a_inv(x_passage, n_k) ;
- PM invalidite  = R/12 * somme_{m=0}^{n-1} l(t+m)/l(t) * v^(m/12) ;
  K et n bornes par la date de retraite du bareme de l'arrete (fin de service des prestations) ;
- PMGD           = C * somme_m p(maintien) * q_m * v^((m+1)/12), mortalite TH/TF 00-02 x coefficient ;
- IBNR           = (Chain Ladder sur triangles de nombres annee de survenance x delai de declaration) x cout moyen.
"""

import numpy as np
import pandas as pd

from .retraite import age_legal_mois

MOIS_MAX_INVALIDITE = 540
GARANTIES_IBNR = ("INCAPACITE", "DECES")


def _age_entier(naissance, date):
    n = pd.to_datetime(naissance)
    d = pd.to_datetime(date)
    return ((d - n).dt.days / 365.25).astype(float)


def _mois_ecoules(debut, fin):
    debut = pd.to_datetime(debut)
    fin = pd.Timestamp(fin)
    m = (fin.year - debut.dt.year) * 12 + (fin.month - debut.dt.month) - (fin.day < debut.dt.day).astype(int)
    return m.clip(lower=0).astype(int)


def mois_avant_retraite(naissance, date_arrete, bareme):
    """Nombre de mois entiers entre l'arrete et l'age legal du bareme (0 si deja atteint)."""
    naissance = pd.to_datetime(pd.Series(naissance)).reset_index(drop=True)
    age_mois = age_legal_mois(naissance, bareme)
    arrete = pd.Timestamp(date_arrete)
    ecoules = (arrete.year - naissance.dt.year) * 12 + (arrete.month - naissance.dt.month) - (arrete.day < naissance.dt.day).astype(int)
    return np.maximum(age_mois - ecoules.to_numpy(), 0)


class MoteurPrevoyance:
    def __init__(self, tables, h):
        self.t = tables
        self.h = h
        self.v = 1.0 / (1.0 + h.taux_technique)
        ages = range(tables.age_min_inv, tables.age_min_inv + tables.lx_inv_annuel.shape[0])
        self.lx_inv = {a: tables.lx_invalidite_mensuel(a, MOIS_MAX_INVALIDITE + 1) for a in ages}
        vm = self.v ** (np.arange(MOIS_MAX_INVALIDITE + 2) / 12.0)
        # rente mensuelle d'invalidite a terme a echoir, par age d'entree et duree : a_inv[x][n]
        self.a_inv = {}
        for a, lx in self.lx_inv.items():
            p = lx / lx[0] if lx[0] > 0 else np.zeros_like(lx)
            self.a_inv[a] = np.concatenate([[0.0], np.cumsum(p[:-1] * vm[:len(p) - 1]) / 12.0])
        # facteur PMGD d'un nouvel invalide d'age a, par sexe et duree restante n : G[sexe][a][n]
        self.g_inv = {}
        for sexe in ("H", "F"):
            self.g_inv[sexe] = {}
            for a, lx in self.lx_inv.items():
                p = lx / lx[0] if lx[0] > 0 else np.zeros_like(lx)
                q = self._q_mensuel(sexe, float(a), len(p) - 1)
                terme = p[:-1] * q * vm[1:len(p)]
                self.g_inv[sexe][a] = np.concatenate([[0.0], np.cumsum(terme)])

    # ------------------------------------------------------------------ utilitaires
    def _age_inv(self, age):
        return int(np.clip(age, self.t.age_min_inv, self.t.age_min_inv + self.t.lx_inv_annuel.shape[0] - 1))

    def rente_attente(self, age_passage, n_mois):
        a = self._age_inv(age_passage)
        n = int(np.clip(n_mois, 0, MOIS_MAX_INVALIDITE))
        return self.a_inv[a][n]

    def _q_mensuel(self, sexe, age_depart, nb):
        qx = self.t.qx["F" if sexe == "F" else "H"]
        ages = np.clip(np.floor(age_depart + np.arange(nb) / 12.0).astype(int), 0, 120)
        q = np.minimum(qx[ages] * self.h.coef_surmortalite_pmgd, 1.0)
        return 1 - (1 - q) ** (1 / 12)

    # ------------------------------------------------------------------ provisions par sinistre
    def incapacite(self, sin, arrete):
        """PM incapacite, PM passage (rentes en attente) et PMGD des arrets en cours."""
        out = []
        s_all = _mois_ecoules(sin.date_survenance, arrete).to_numpy()
        age_entree = np.floor(_age_entier(sin.date_naissance, sin.date_survenance)).astype(int).to_numpy()
        age_arrete = _age_entier(sin.date_naissance, pd.Series(arrete, index=sin.index)).to_numpy()
        r_all = mois_avant_retraite(sin.date_naissance, arrete, self.h.bareme_retraite)
        L_all = self.t.ligne_incapacite(age_entree)
        N_all = self.t.ligne_passage(age_entree)
        for j, x in enumerate(sin.itertuples(index=False)):
            s = min(int(s_all[j]), 35)
            L, N = L_all[j], N_all[j]
            K = min(35 - s, int(r_all[j]) - 1)
            if K < 0 or L[s] <= 0:
                out.append((0.0, 0.0, 0.0))
                continue
            k = np.arange(K + 1)
            maintien = L[s + k] / L[s]
            ij_m = float(x.ij_journaliere) * 365.25 / 12.0
            pm_inc = ij_m * (maintien * self.v ** (k / 12.0)).sum()
            passage = N[s + k] / L[s]
            a = np.array([self.rente_attente(np.floor(age_arrete[j] + (kk + 1) / 12.0), r_all[j] - kk - 1) for kk in k])
            pm_pas = float(x.rente_invalidite_potentielle) * (passage * self.v ** ((k + 1) / 12.0) * a).sum()
            q = self._q_mensuel(x.sexe, age_arrete[j], K + 1)
            pmgd = float(x.capital_deces_potentiel) * (maintien * q * self.v ** ((k + 1) / 12.0)).sum()
            # garantie deces maintenue apres un passage en invalidite futur
            sexe = "F" if x.sexe == "F" else "H"
            g = np.array([self.g_inv[sexe][self._age_inv(np.floor(age_arrete[j] + (kk + 1) / 12.0))]
                          [int(np.clip(r_all[j] - kk - 1, 0, MOIS_MAX_INVALIDITE))] for kk in k])
            pmgd += float(x.capital_deces_potentiel) * (passage * self.v ** ((k + 1) / 12.0) * g).sum()
            out.append((pm_inc, pm_pas, pmgd))
        r = np.array(out).reshape(-1, 3)
        return pd.DataFrame({"id_sinistre": sin.id_sinistre.values, "pm_incapacite": r[:, 0], "pm_passage": r[:, 1],
                             "pmgd": r[:, 2], "anciennete_mois": s_all, "mois_avant_retraite": r_all})

    def invalidite(self, sin, arrete):
        out = []
        t_all = _mois_ecoules(sin.date_survenance, arrete).to_numpy()
        age_entree = np.floor(_age_entier(sin.date_naissance, sin.date_survenance)).astype(int).to_numpy()
        age_arrete = _age_entier(sin.date_naissance, pd.Series(arrete, index=sin.index)).to_numpy()
        r_all = mois_avant_retraite(sin.date_naissance, arrete, self.h.bareme_retraite)
        for j, x in enumerate(sin.itertuples(index=False)):
            n = int(r_all[j])
            if n <= 0:
                out.append((0.0, 0.0))
                continue
            lx = self.lx_inv[self._age_inv(age_entree[j])]
            t = int(min(t_all[j], MOIS_MAX_INVALIDITE))
            m = np.arange(n)
            idx = np.minimum(t + m, MOIS_MAX_INVALIDITE)
            if lx[t] > 0:
                maintien = lx[idx] / lx[t]
            else:  # table epuisee a cette anciennete : table de l'age atteint
                lx2 = self.lx_inv[self._age_inv(age_arrete[j])]
                maintien = lx2[np.minimum(m, MOIS_MAX_INVALIDITE)] / lx2[0]
            pm = float(x.rente_annuelle) / 12.0 * (maintien * self.v ** (m / 12.0)).sum()
            q = self._q_mensuel(x.sexe, age_arrete[j], n)
            pmgd = float(x.capital_deces_potentiel) * (maintien * q * self.v ** ((m + 1) / 12.0)).sum()
            out.append((pm, pmgd))
        r = np.array(out).reshape(-1, 2)
        return pd.DataFrame({"id_sinistre": sin.id_sinistre.values, "pm_invalidite": r[:, 0], "pmgd": r[:, 1],
                             "anciennete_mois": t_all, "mois_avant_retraite": r_all})


# ============================================================================= IBNR
def triangle_nombres(sin, garantie, segment, annee_arrete, nb_annees=10):
    s = sin[(sin.garantie == garantie) & (sin.segment == segment)]
    ys = pd.to_datetime(s.date_survenance).dt.year
    yd = pd.to_datetime(s.date_declaration).dt.year
    s = pd.DataFrame({"ys": ys, "lag": (yd - ys).clip(lower=0)})
    origines = list(range(annee_arrete - nb_annees + 1, annee_arrete + 1))
    t = s[s.ys.isin(origines)].pivot_table(index="ys", columns="lag", aggfunc="size").reindex(index=origines,
                                                                                            columns=range(nb_annees))
    cum = t.fillna(0).cumsum(axis=1)
    age = np.array([annee_arrete - o for o in origines])
    return cum.mask(np.arange(nb_annees)[None, :] > age[:, None]), age


def ultimes_nombres(cum, age):
    c = cum.to_numpy(dtype=float)
    n = c.shape[1]
    f = np.ones(n - 1)
    for j in range(n - 1):
        i = np.nonzero(age >= j + 1)[0]
        den = c[i, j].sum()
        if den > 0:
            f[j] = c[i, j + 1].sum() / den
    fc = np.concatenate([np.cumprod(f[::-1])[::-1], [1.0]])
    diag = np.array([c[i, min(a, n - 1)] for i, a in enumerate(age)])
    return diag, diag * fc[np.minimum(age, n - 1)], f


def ibnr(sin, charges, h, annee_arrete):
    """IBNR par garantie, segment et annee de survenance. `charges` : id_sinistre, charge (paye + provisions)."""
    lignes, facteurs = [], []
    for garantie in GARANTIES_IBNR:
        for segment in ("COL", "IND"):
            cum, age = triangle_nombres(sin, garantie, segment, annee_arrete)
            diag, ult, f = ultimes_nombres(cum, age)
            facteurs.append({"garantie": garantie, "segment": segment, "facteurs": [round(x, 4) for x in f]})
            ref = sin[(sin.garantie == garantie) & (sin.segment == segment)].copy()
            ref["ys"] = pd.to_datetime(ref.date_survenance).dt.year
            annees = range(annee_arrete - h.nb_annees_cout_moyen_ibnr, annee_arrete)
            ref = ref[ref.ys.isin(annees)].merge(charges, on="id_sinistre", how="left")
            cout_moyen = float(ref.charge.fillna(0).mean()) if len(ref) else 0.0
            # part du cout moyen d'un arret qui se realise en invalidite (rentes en attente, invalidite rattachee)
            cout_inv = float(ref.charge_invalidite.fillna(0).mean()) if len(ref) and garantie == "INCAPACITE" else 0.0
            for o, d, u in zip(cum.index, diag, ult):
                nb = max(u - d, 0.0)
                lignes.append({"garantie": garantie, "segment": segment, "annee_survenance": int(o), "nb_declares": d,
                               "nb_ultime": u, "nb_ibnr": nb, "cout_moyen": cout_moyen - cout_inv,
                               "ibnr": nb * (cout_moyen - cout_inv)})
                if garantie == "INCAPACITE":
                    lignes.append({"garantie": "INVALIDITE", "segment": segment, "annee_survenance": int(o), "nb_declares": d,
                                   "nb_ultime": u, "nb_ibnr": nb, "cout_moyen": cout_inv, "ibnr": nb * cout_inv})
    return pd.DataFrame(lignes), pd.DataFrame(facteurs)


# ============================================================================= prestations echues non reglees
def prestations_echues(detail, arrete, fenetre_mois=12):
    """IJ et arrerages de rente dus pour les periodes ecoulees a l'arrete mais non encore regles.

    Du = montant journalier x jours entre le debut d'indemnisation et min(arrete, cloture) ; provision = max(du - paye, 0).
    Concerne les sinistres en cours et ceux clos depuis moins de `fenetre_mois` mois (derniere echeance en cours de reglement).
    """
    debut = pd.to_datetime(detail.date_debut_indemnisation).fillna(pd.to_datetime(detail.date_survenance))
    fin = pd.to_datetime(detail.date_cloture).where(detail.statut == "CLOS", pd.NaT).fillna(arrete).clip(upper=arrete)
    jours = (fin - debut).dt.days.clip(lower=0) + 1
    journalier = np.where(detail.garantie == "INCAPACITE", detail.ij_journaliere.fillna(0.0),
                          np.where(detail.garantie == "INVALIDITE", detail.rente_annuelle.fillna(0.0) / 365.25, 0.0))
    recent = (detail.statut == "EN_COURS") | (fin >= arrete - pd.DateOffset(months=fenetre_mois))
    du = np.where(recent & detail.garantie.isin(["INCAPACITE", "INVALIDITE"]), journalier * jours, 0.0)
    return np.maximum(du - detail.paye_cumule.values, 0.0) * (du > 0)


# ============================================================================= orchestration
def provisions_prevoyance(sin, paiements, tables, h, date_arrete=None):
    """Calcule toutes les provisions de prevoyance a la date d'arrete de `h`.

    `sin` : sinistres connus a l'arrete (silver), enrichis de rente_invalidite_potentielle et capital_deces_potentiel.
    `paiements` : paiements cumules jusqu'a l'arrete (id_sinistre, montant, date_paiement).
    `date_arrete` : date de calcul (par defaut celle de `h`) ; permet d'appliquer les hypotheses N-1 au stock N.
    Retour : (detail par sinistre, IBNR, facteurs de declaration).
    """
    arrete = pd.Timestamp(date_arrete if date_arrete is not None else h.date_arrete)
    moteur = MoteurPrevoyance(tables, h)
    paye = paiements[pd.to_datetime(paiements.date_paiement) <= arrete].groupby("id_sinistre").montant.sum()
    sin = sin.copy()
    sin["paye_cumule"] = sin.id_sinistre.map(paye).fillna(0.0)
    origine = sin.set_index("id_sinistre").date_survenance
    sin["date_survenance_origine"] = pd.to_datetime(sin.id_sinistre_origine.map(origine)).fillna(pd.to_datetime(sin.date_survenance))
    ouverts = sin.statut == "EN_COURS"
    inc = sin[ouverts & (sin.garantie == "INCAPACITE")]
    inv = sin[ouverts & (sin.garantie == "INVALIDITE")]
    dec = sin[ouverts & (sin.garantie == "DECES")]
    r_inc = moteur.incapacite(inc, arrete) if len(inc) else pd.DataFrame(columns=["id_sinistre"])
    r_inv = moteur.invalidite(inv, arrete) if len(inv) else pd.DataFrame(columns=["id_sinistre"])
    r_dec = pd.DataFrame({"id_sinistre": dec.id_sinistre.values,
                          "psap_deces": np.maximum(dec.capital.fillna(0).values - dec.paye_cumule.values, 0.0)})
    detail = sin.merge(pd.concat([r_inc, r_inv, r_dec], ignore_index=True), on="id_sinistre", how="left",
                       suffixes=("", "_calc"))
    for c in ("pm_incapacite", "pm_passage", "pm_invalidite", "pmgd", "psap_deces"):
        detail[c] = detail[c].fillna(0.0) if c in detail else 0.0
    detail["psap_echues"] = prestations_echues(detail, arrete)
    types = ["pm_incapacite", "pm_passage", "pm_invalidite", "pmgd", "psap_deces", "psap_echues"]
    detail["provision"] = detail[types].sum(axis=1)
    # charge des sinistres (base du cout moyen IBNR) : incapacite + invalidite rattachee, deces
    detail["charge_propre"] = detail.paye_cumule + detail[[t for t in types if t != "pmgd"]].sum(axis=1)
    rattache = detail[detail.garantie == "INVALIDITE"].groupby("id_sinistre_origine").charge_propre.sum()
    detail["charge_invalidite"] = detail.id_sinistre.map(rattache).fillna(0.0) + detail.pm_passage
    detail["charge"] = detail.charge_propre + detail.id_sinistre.map(rattache).fillna(0.0)
    tab_ibnr, fact = ibnr(sin, detail[["id_sinistre", "charge", "charge_invalidite"]], h, arrete.year)
    detail["annee_survenance_origine"] = pd.to_datetime(detail.date_survenance_origine).dt.year
    return detail, tab_ibnr, fact


def synthese_prevoyance(detail, tab_ibnr, h):
    """Table longue : segment, garantie, type de provision, annee de survenance d'origine, montant."""
    d = detail
    blocs = [
        d[d.pm_incapacite != 0].assign(garantie="INCAPACITE", type_provision="PM_INCAPACITE", montant=d.pm_incapacite),
        d[d.pm_passage != 0].assign(garantie="INVALIDITE", type_provision="PM_RENTES_EN_ATTENTE", montant=d.pm_passage),
        d[d.pm_invalidite != 0].assign(garantie="INVALIDITE", type_provision="PM_INVALIDITE", montant=d.pm_invalidite),
        d[d.psap_deces != 0].assign(garantie="DECES", type_provision="PSAP_DECES_CONNUS", montant=d.psap_deces),
        d[d.pmgd != 0].assign(garantie="DECES", type_provision="PMGD", montant=d.pmgd),
        d[d.psap_echues != 0].assign(type_provision="PSAP_PRESTATIONS_ECHUES", montant=d.psap_echues),
    ]
    x = pd.concat([b[["segment", "garantie", "type_provision", "annee_survenance_origine", "montant"]] for b in blocs])
    x = x.rename(columns={"annee_survenance_origine": "annee_survenance"})
    i = tab_ibnr.assign(type_provision="IBNR_" + tab_ibnr.garantie, montant=tab_ibnr.ibnr)[
        ["segment", "garantie", "type_provision", "annee_survenance", "montant"]]
    x = pd.concat([x, i], ignore_index=True)
    x = x.groupby(["segment", "garantie", "type_provision", "annee_survenance"], as_index=False).montant.sum()
    pfgs = x.groupby(["segment", "garantie", "annee_survenance"], as_index=False).montant.sum()
    pfgs["montant"] *= h.taux_pfgs_prevoyance
    pfgs["type_provision"] = "PFGS"
    return pd.concat([x, pfgs], ignore_index=True)
