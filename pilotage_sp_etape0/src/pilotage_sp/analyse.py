"""Analyse de la variation des provisions (pont N-1 -> N) et de la liquidation.

Decomposition, hors PFGS, par branche, segment et garantie :
  provision N-1 (hypotheses N-1)
  - ecoulement              : paiements de N sur survenances <= N-1
  - ecart de liquidation    : provision N-1 - ecoulement - provision N des survenances <= N-1 (hypotheses N-1) ;
                              positif = boni
  + nouvelle survenance     : provision N des survenances N (hypotheses N-1)
  + effet des hypotheses    : provision N (hypotheses N) - provision N (hypotheses N-1), tout le stock
  = provision N (hypotheses N)
"""

import pandas as pd

CLE = ["branche", "segment", "garantie"]


def pont(prov_n, prov_n_hyp_prec, prov_prec, paiements_anciens, exercice):
    """Tables longues : `prov_*` (CLE + annee_survenance + montant, hors PFGS) ; `paiements_anciens` (CLE + montant)."""
    def tot(df, masque=None):
        d = df if masque is None else df[masque(df)]
        return d.groupby(CLE).montant.sum()
    ouverture = tot(prov_prec)
    ecoulement = tot(paiements_anciens)
    residuel = tot(prov_n_hyp_prec, lambda d: d.annee_survenance < exercice)
    nouvelle = tot(prov_n_hyp_prec, lambda d: d.annee_survenance >= exercice)
    cloture = tot(prov_n)
    effet = cloture.sub(tot(prov_n_hyp_prec), fill_value=0)
    x = pd.concat({"provision_ouverture": ouverture, "ecoulement": ecoulement, "provision_residuelle": residuel,
                   "nouvelle_survenance": nouvelle, "effet_hypotheses": effet, "provision_cloture": cloture}, axis=1).fillna(0.0)
    x["ecart_liquidation"] = x.provision_ouverture - x.ecoulement - x.provision_residuelle
    x["controle_bouclage"] = (x.provision_ouverture - x.ecoulement - x.ecart_liquidation + x.nouvelle_survenance
                              + x.effet_hypotheses - x.provision_cloture)
    x["taux_liquidation"] = x.ecart_liquidation / x.provision_ouverture.where(x.provision_ouverture != 0)
    x = x.reset_index()
    x["exercice"] = exercice
    return x[["exercice", *CLE, "provision_ouverture", "ecoulement", "ecart_liquidation", "provision_residuelle",
              "nouvelle_survenance", "effet_hypotheses", "provision_cloture", "taux_liquidation", "controle_bouclage"]]
