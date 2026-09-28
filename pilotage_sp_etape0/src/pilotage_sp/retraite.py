"""Age legal de depart a la retraite, par generation et par bareme.

En prevoyance, le service des rentes d'invalidite (et, par construction, la
provision de rentes en attente) cesse a la liquidation de la pension de
vieillesse. L'age de fin de service est donc un attribut individuel, fonction
de la date de naissance et du bareme legal connu a la date d'arrete.

Trois baremes sont implementes :
- LOI_2010    : loi du 9 novembre 2010, age legal porte a 62 ans (generations 1955 et suivantes) ;
- REFORME_2023: loi du 14 avril 2023, relevement progressif de 62 a 64 ans
                (+3 mois par generation a partir des assures nes le 1er septembre 1961) ;
- LFSS_2026   : suspension introduite par la LFSS pour 2026 (fin decembre 2025),
                applicable aux pensions prenant effet a compter du 1er septembre 2026 ;
                gel a 62 ans et 9 mois pour la generation 1964 et le premier trimestre 1965,
                64 ans atteints a partir de la generation 1969.

Le bareme applicable a un arrete est un parametre versionne de la note
technique (table hypotheses_arrete), jamais une constante du code.
"""

import numpy as np
import pandas as pd

BAREMES = ("LOI_2010", "REFORME_2023", "LFSS_2026")


def _t(debut, fin, annees, mois):
    return (np.datetime64(debut), np.datetime64(fin), annees * 12 + mois)


_LOI_2010 = [
    _t("1900-01-01", "1951-06-30", 60, 0),
    _t("1951-07-01", "1951-12-31", 60, 4),
    _t("1952-01-01", "1952-12-31", 60, 9),
    _t("1953-01-01", "1953-12-31", 61, 2),
    _t("1954-01-01", "1954-12-31", 61, 7),
    _t("1955-01-01", "2100-12-31", 62, 0),
]

_REFORME_2023 = _LOI_2010[:5] + [
    _t("1955-01-01", "1961-08-31", 62, 0),
    _t("1961-09-01", "1961-12-31", 62, 3),
    _t("1962-01-01", "1962-12-31", 62, 6),
    _t("1963-01-01", "1963-12-31", 62, 9),
    _t("1964-01-01", "1964-12-31", 63, 0),
    _t("1965-01-01", "1965-12-31", 63, 3),
    _t("1966-01-01", "1966-12-31", 63, 6),
    _t("1967-01-01", "1967-12-31", 63, 9),
    _t("1968-01-01", "2100-12-31", 64, 0),
]

_LFSS_2026 = _LOI_2010[:5] + [
    _t("1955-01-01", "1961-08-31", 62, 0),
    _t("1961-09-01", "1961-12-31", 62, 3),
    _t("1962-01-01", "1962-12-31", 62, 6),
    _t("1963-01-01", "1963-12-31", 62, 9),
    _t("1964-01-01", "1965-03-31", 62, 9),
    _t("1965-04-01", "1965-12-31", 63, 0),
    _t("1966-01-01", "1966-12-31", 63, 3),
    _t("1967-01-01", "1967-12-31", 63, 6),
    _t("1968-01-01", "1968-12-31", 63, 9),
    _t("1969-01-01", "2100-12-31", 64, 0),
]

_TABLES = {"LOI_2010": _LOI_2010, "REFORME_2023": _REFORME_2023, "LFSS_2026": _LFSS_2026}


def age_legal_mois(dates_naissance, bareme):
    """Age legal de depart, en mois, pour un vecteur de dates de naissance."""
    if bareme not in _TABLES:
        raise ValueError(f"Bareme inconnu : {bareme}. Attendus : {BAREMES}")
    dates = pd.to_datetime(pd.Series(dates_naissance)).values.astype("datetime64[D]")
    resultat = np.full(len(dates), 62 * 12, dtype=int)
    for debut, fin, mois in _TABLES[bareme]:
        masque = (dates >= debut) & (dates <= fin)
        resultat[masque] = mois
    return resultat


def date_retraite(dates_naissance, bareme):
    """Date d'atteinte de l'age legal (fin de service des rentes)."""
    naissance = pd.to_datetime(pd.Series(dates_naissance)).reset_index(drop=True)
    mois = age_legal_mois(naissance, bareme)
    return pd.Series([n + pd.DateOffset(months=int(m)) for n, m in zip(naissance, mois)])


def age_legal_reel_mois(dates_naissance):
    """Age de depart effectivement applicable (vision a date, fin 2025).

    Sert uniquement au generateur de donnees pour determiner la date reelle
    de fin des rentes : bareme 2010 si l'age de 62 ans est atteint avant le
    1er septembre 2023, bareme 2023 si l'age 2023 est atteint avant le
    1er septembre 2026, bareme LFSS 2026 au-dela.
    """
    naissance = pd.to_datetime(pd.Series(dates_naissance)).values.astype("datetime64[D]")
    m2010 = age_legal_mois(naissance, "LOI_2010")
    m2023 = age_legal_mois(naissance, "REFORME_2023")
    m2026 = age_legal_mois(naissance, "LFSS_2026")
    atteinte_2010 = naissance.astype("datetime64[M]") + m2010.astype("timedelta64[M]")
    atteinte_2023 = naissance.astype("datetime64[M]") + m2023.astype("timedelta64[M]")
    return np.where(atteinte_2010 < np.datetime64("2023-09"), m2010,
                    np.where(atteinte_2023 < np.datetime64("2026-09"), m2023, m2026))


def table_bareme(bareme, generations=range(1955, 1972)):
    """Restitution lisible, destinee a la note technique."""
    lignes = []
    for g in generations:
        for mois in (1, 4, 7, 10):
            n = pd.Timestamp(year=g, month=mois, day=15)
            m = int(age_legal_mois([n], bareme)[0])
            lignes.append({"generation": g, "trimestre": (mois - 1) // 3 + 1, "age_mois": m,
                           "age_legal": f"{m // 12} ans" + (f" {m % 12} mois" if m % 12 else "")})
    return pd.DataFrame(lignes).drop_duplicates(["generation", "age_mois"]).reset_index(drop=True)
