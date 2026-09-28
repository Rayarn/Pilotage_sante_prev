"""Tests unitaires des moteurs (pytest -q depuis la racine du depot)."""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))
from pilotage_sp.hypotheses import charger_hypotheses, plafond_taux  # noqa: E402
from pilotage_sp.referentiels import charger_tables  # noqa: E402
from pilotage_sp.retraite import age_legal_mois  # noqa: E402
from pilotage_sp import sante, prevoyance, analyse  # noqa: E402

REF = RACINE / "data" / "referentiels"


@pytest.fixture(scope="module")
def tables():
    return charger_tables(REF)


@pytest.fixture(scope="module")
def hyp():
    return charger_hypotheses(REF / "hypotheses_arrete.csv", REF / "tme_mensuel.csv")


def test_plafond_tme_publie(hyp):
    # valeurs publiees (75 % du TME moyen 24 mois) : 0,66 % fin 2022, 1,79 % fin 2023, 2,41 % fin 2025
    assert hyp[2022].plafond_reglementaire == pytest.approx(0.0066, abs=5e-5)
    assert hyp[2023].plafond_reglementaire == pytest.approx(0.0179, abs=5e-5)
    assert hyp[2025].plafond_reglementaire == pytest.approx(0.0241, abs=5e-5)
    assert hyp[2021].plafond_reglementaire < 0 and hyp[2021].taux_technique == 0


def test_serie_tme_incomplete():
    tme = pd.read_csv(REF / "tme_mensuel.csv", sep=";", dtype={"mois": str})
    with pytest.raises(ValueError):
        plafond_taux(tme[tme.mois >= "2025-01"], "2025-12-31")


def test_baremes_retraite():
    n = pd.Series(pd.to_datetime(["1960-06-15", "1965-06-15", "1970-06-15"]))
    assert list(age_legal_mois(n, "LOI_2010")) == [744, 744, 744]
    assert list(age_legal_mois(n, "REFORME_2023")) == [744, 759, 768]
    assert list(age_legal_mois(n, "LFSS_2026")) == [744, 756, 768]


def test_chain_ladder_triangle_deterministe(hyp):
    # triangle ou chaque mois de soins paie 60 % au mois 0, 30 % au mois 1, 10 % au mois 2
    mois = pd.period_range("2024-01", "2025-12", freq="M")
    lignes = []
    for m in mois:
        for lag, part in enumerate((0.6, 0.3, 0.1)):
            if m + lag <= pd.Period("2025-12", "M"):
                lignes.append(("COL", str(m), str(m + lag), 1000 * part))
    inc = pd.DataFrame(lignes, columns=["segment", "mois_soins", "mois_paiement", "montant"])
    cot = pd.DataFrame({"segment": "COL", "mois": [str(m) for m in mois], "montant": 1000.0})
    h = replace(hyp[2025], nb_mois_bf=0, nb_mois_sp_apriori=0)
    detail, resume = sante.provisions_sante(inc, cot, h, "2025-12-31")
    assert resume.psap.iloc[0] == pytest.approx(400 + 100, rel=1e-9)   # dec : 400, nov : 100
    assert resume.ecart_type_mack.iloc[0] == pytest.approx(0, abs=1e-6)


def test_pm_incapacite_premier_mois_certain(tables, hyp):
    h = replace(hyp[2021], taux_technique=0.0)
    moteur = prevoyance.MoteurPrevoyance(tables, h)
    sin = pd.DataFrame({"id_sinistre": ["S1"], "date_survenance": [pd.Timestamp("2021-12-20")],
                        "date_naissance": [pd.Timestamp("1981-06-01")], "ij_journaliere": [30.0], "sexe": ["H"],
                        "rente_invalidite_potentielle": [0.0], "capital_deces_potentiel": [0.0]})
    r = moteur.incapacite(sin, pd.Timestamp("2021-12-31"))
    L = tables.ligne_incapacite([40])[0]
    attendu = 30 * 365.25 / 12 * L[:36].sum() / L[0]
    assert r.pm_incapacite.iloc[0] == pytest.approx(attendu, rel=1e-9)


def test_pm_invalidite_bornee_par_la_retraite(tables, hyp):
    moteur = prevoyance.MoteurPrevoyance(tables, hyp[2025])
    base = dict(id_sinistre=["I1"], date_survenance=[pd.Timestamp("2020-01-10")], rente_annuelle=[12000.0], sexe=["F"],
                capital_deces_potentiel=[0.0])
    jeune = moteur.invalidite(pd.DataFrame(base | {"date_naissance": [pd.Timestamp("1975-01-01")]}), pd.Timestamp("2025-12-31"))
    proche = moteur.invalidite(pd.DataFrame(base | {"date_naissance": [pd.Timestamp("1963-06-01")]}), pd.Timestamp("2025-12-31"))
    assert jeune.pm_invalidite.iloc[0] > proche.pm_invalidite.iloc[0] > 0
    assert proche.mois_avant_retraite.iloc[0] < 12


def test_pont_boucle():
    k = dict(branche="SANTE", segment="COL", garantie="FRAIS_DE_SANTE")
    prec = pd.DataFrame([k | {"annee_survenance": 2024, "montant": 100.0}])
    n = pd.DataFrame([k | {"annee_survenance": 2024, "montant": 15.0}, k | {"annee_survenance": 2025, "montant": 120.0}])
    n_prec = pd.DataFrame([k | {"annee_survenance": 2024, "montant": 14.0}, k | {"annee_survenance": 2025, "montant": 118.0}])
    pay = pd.DataFrame([k | {"montant": 80.0}])
    p = analyse.pont(n, n_prec, prec, pay, 2025)
    assert p.ecart_liquidation.iloc[0] == pytest.approx(6.0)
    assert p.effet_hypotheses.iloc[0] == pytest.approx(3.0)
    assert abs(p.controle_bouclage.iloc[0]) < 1e-9


@pytest.mark.parametrize("n", [2020, 2021, 2022, 2023, 2024, 2025])
def test_non_regression(n):
    """Compare la derniere livraison locale aux resultats de reference (au centime pres)."""
    liv = RACINE / "livraison" / f"exercice={n}" / f"provisions_synthese_{n}.csv"
    if not liv.exists():
        pytest.skip("pas de livraison locale : lancer outils/execution_locale/run_local.py")
    ref = pd.read_csv(RACINE / "resultats_reference" / f"exercice={n}" / f"provisions_synthese_{n}.csv", sep=";")
    cur = pd.read_csv(liv, sep=";")
    cle = ["branche", "segment", "garantie", "type_provision"]
    x = ref.merge(cur, on=cle, suffixes=("_ref", "_cur"), how="outer").fillna(0)
    assert (x.montant_ref - x.montant_cur).abs().max() < 0.01
