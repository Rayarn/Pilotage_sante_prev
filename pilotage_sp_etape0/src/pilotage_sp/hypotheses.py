"""Hypotheses actuarielles versionnees par arrete (note technique).

Toute hypothese susceptible de changer d'un arrete a l'autre (taux technique, bareme de retraite,
profondeur Bornhuetter-Ferguson, S/P a priori, chargements) vit dans la table de reference
`hypotheses_arrete`, jamais dans le code. Le plafond reglementaire du taux technique n'est pas saisi :
il est recalcule a partir de la serie officielle des TME mensuels (table `tme_mensuel`).
"""

from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd

from .retraite import BAREMES

PART_TME = 0.75
PLAFOND_ABSOLU = 0.045
NB_MOIS_TME = 24


def plafond_taux(tme, date_arrete):
    """Article A331-22 : taux <= 75 % du TME moyen des 24 derniers mois (mois de l'arrete inclus), 4,5 % maximum.

    `tme` : DataFrame (mois 'AAAA-MM', tme en decimal). Retourne (tme_moyen_24m, plafond).
    Si la moyenne est negative, le plafond est negatif et seul un taux <= 0 est admis (reglement ANC 2020-11).
    """
    t = tme.copy()
    t["mois"] = pd.PeriodIndex(t["mois"].astype(str), freq="M")
    fin = pd.Timestamp(date_arrete).to_period("M")
    fenetre = t[(t.mois > fin - NB_MOIS_TME) & (t.mois <= fin)]
    if len(fenetre) != NB_MOIS_TME:
        raise ValueError(f"Serie TME incomplete : {len(fenetre)} mois disponibles sur {NB_MOIS_TME} avant {fin}")
    moyenne = float(fenetre.tme.mean())
    return moyenne, min(PART_TME * moyenne, PLAFOND_ABSOLU)


@dataclass(frozen=True)
class Hypotheses:
    exercice: int
    date_arrete: pd.Timestamp
    version_note_technique: str
    taux_technique: float
    bareme_retraite: str
    nb_mois_bf: int
    nb_mois_sp_apriori: int
    profondeur_facteurs_mois: int
    sp_apriori_sante_ind: float
    sp_apriori_sante_col: float
    taux_pfgs_sante: float
    taux_pfgs_prevoyance: float
    coef_surmortalite_pmgd: float
    nb_annees_cout_moyen_ibnr: int
    commentaire: str = ""
    tme_moyen_24m: float = float("nan")
    plafond_reglementaire: float = float("nan")

    def sp_apriori(self, segment):
        return self.sp_apriori_sante_ind if segment == "IND" else self.sp_apriori_sante_col

    def controler(self):
        anomalies = []
        if self.taux_technique > max(self.plafond_reglementaire, 0.0) + 1e-9:
            anomalies.append("taux technique superieur au plafond reglementaire (75 % du TME moyen 24 mois, 4,5 % maximum)")
        if self.taux_technique < 0:
            anomalies.append("taux technique negatif")
        if self.bareme_retraite not in BAREMES:
            anomalies.append(f"bareme de retraite inconnu : {self.bareme_retraite}")
        if not 0 <= self.nb_mois_sp_apriori <= self.nb_mois_bf:
            anomalies.append("mois en S/P a priori hors de [0, nb_mois_bf]")
        if not 0 <= self.nb_mois_bf <= 12:
            anomalies.append("profondeur Bornhuetter-Ferguson hors de [0, 12] mois")
        return anomalies

    def en_dict(self):
        d = asdict(self)
        d["date_arrete"] = str(pd.Timestamp(self.date_arrete).date())
        return d


def charger_hypotheses(source, tme):
    """`source` : chemin du CSV ou DataFrame (ref.hypotheses_arrete) ; `tme` : chemin ou DataFrame (ref.tme_mensuel)."""
    df = source if isinstance(source, pd.DataFrame) else pd.read_csv(Path(source), sep=";")
    serie = tme if isinstance(tme, pd.DataFrame) else pd.read_csv(Path(tme), sep=";", dtype={"mois": str})
    resultat = {}
    for ligne in df.to_dict("records"):
        ligne["date_arrete"] = pd.Timestamp(ligne["date_arrete"])
        ligne["commentaire"] = "" if pd.isna(ligne.get("commentaire")) else str(ligne["commentaire"])
        for cle in ("exercice", "nb_mois_bf", "nb_mois_sp_apriori", "profondeur_facteurs_mois", "nb_annees_cout_moyen_ibnr"):
            ligne[cle] = int(ligne[cle])
        for cle in ("tme_moyen_24m", "plafond_reglementaire"):
            ligne.pop(cle, None)
        moyenne, plafond = plafond_taux(serie, ligne["date_arrete"])
        h = Hypotheses(**ligne, tme_moyen_24m=moyenne, plafond_reglementaire=plafond)
        anomalies = h.controler()
        if anomalies:
            raise ValueError(f"Hypotheses {h.exercice} non conformes : {anomalies}")
        resultat[h.exercice] = h
    return resultat
