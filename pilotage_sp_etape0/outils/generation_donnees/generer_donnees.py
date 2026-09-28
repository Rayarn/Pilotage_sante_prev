"""Point d'entree : genere le monde fictif « Mutuelle Orsane » et les extractions annuelles 2020 (reprise) a 2025.

Usage : python outils/generation_donnees/generer_donnees.py
Deterministe (graine fixe) : deux executions produisent des fichiers identiques (empreintes sha256 dans _TEMOIN).
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monde import (RACINE, SEED, EXERCICES, SORTIE, generer_entreprises, generer_contrats_collectifs, generer_salaries,  # noqa: E402
                   generer_sante_individuelle, generer_tns, construire_affiliations)
import sante_gen  # noqa: E402
import prevoyance_gen  # noqa: E402
import extractions as ex  # noqa: E402
from pilotage_sp.referentiels import charger_tables  # noqa: E402

VERITE = Path(__file__).resolve().parent / "verite"


def contrats_complets(cc, si_c, tns):
    t = pd.DataFrame({"id_contrat": tns.id_contrat, "branche": "PREVOYANCE", "segment": "IND",
                      "code_produit": "PREV_IND_" + tns.formule, "formule": tns.formule, "date_effet": tns.date_adhesion,
                      "date_resiliation": tns.date_radiation, "departement": tns.departement})
    c = pd.concat([cc, si_c, t], ignore_index=True)
    for col in ("date_effet", "date_resiliation"):
        c[col] = pd.to_datetime(c[col])
    return c


def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    tables = charger_tables(RACINE / "data" / "referentiels")
    ent = generer_entreprises(rng)
    cc = generer_contrats_collectifs(rng, ent)
    sal = generer_salaries(rng, ent)
    si_c, si_m = generer_sante_individuelle(rng)
    tns = generer_tns(rng)
    aff = construire_affiliations(rng, cc, sal, si_m, tns)
    contrats = contrats_complets(cc, si_c, tns)
    print(f"monde : {len(aff):,} affiliations, {len(contrats):,} contrats ({time.time() - t0:.0f}s)")

    sante_gen.enregistrer_formules(contrats[["id_contrat", "formule"]])
    soins = sante_gen.simuler_soins(rng, aff)
    cot_s = sante_gen.simuler_cotisations_sante(rng, aff, contrats[contrats.branche == "SANTE"], soins)
    cot_s["branche"] = "SANTE"
    print(f"sante : {len(soins):,} lignes de prestations ({time.time() - t0:.0f}s)")

    p, sin, pay, primes = prevoyance_gen.simuler_prevoyance(rng, aff, cc, tables)
    # garanties du contrat portees par le dossier sinistre (rente d'invalidite et capital deces de reference)
    g = p.drop_duplicates("id_assure").set_index("id_assure")
    col = (sin.segment == "COL").values
    multiple = np.where(sin.cadre.values, sin.id_assure.map(g.multiple_capital_cadre).values,
                        sin.id_assure.map(g.multiple_capital_non_cadre).values)
    sin["rente_invalidite_garantie"] = np.where(col, np.round(sin.id_assure.map(g.taux_rente_invalidite).values * sin.salaire_reference.values, 2),
                                                sin.id_assure.map(g.rente_invalidite_garantie_annuelle).values)
    sin["capital_deces_garanti"] = np.where(col, np.round(multiple * sin.salaire_reference.values, 2),
                                            sin.id_assure.map(g.capital_deces_garanti).values)
    cot_p = prevoyance_gen.etaler_cotisations(primes, contrats[["id_contrat", "segment"]])
    cot_p["branche"] = "PREVOYANCE"
    print(f"prevoyance : {len(sin):,} sinistres, {len(pay):,} paiements ({time.time() - t0:.0f}s)")

    cot = pd.concat([cot_s, cot_p], ignore_index=True)
    cot["segment"] = cot.id_contrat.map(contrats.set_index("id_contrat").segment)
    cot = cot.sort_values(["date_debut_periode", "id_contrat", "garantie"]).reset_index(drop=True)
    cot["id_quittance"] = ex.ids("Q", len(cot), 9)
    cot = cot[["id_quittance", "id_contrat", "branche", "segment", "garantie", "date_debut_periode", "date_fin_periode",
               "date_emission", "montant_cotisation_ht"]]

    # ---------------------------------------------------------------- verite (hors chaine de production, sert au backtesting)
    VERITE.mkdir(parents=True, exist_ok=True)
    v = soins.assign(mois_soins=soins.date_soins.dt.to_period("M").astype(str)).groupby(["segment", "mois_soins"]).montant_rembourse.sum()
    v.round(2).reset_index().to_csv(VERITE / "sante_ultime_par_mois_soins.csv", sep=";", index=False)
    s = sin.copy()
    s["cout_ultime_non_actualise"] = prevoyance_gen.cout_total(s)
    s["annee_survenance"] = s.date_survenance.dt.year
    s.groupby(["segment", "garantie", "annee_survenance"]).agg(nb=("id_sinistre", "size"), cout=("cout_ultime_non_actualise", "sum")) \
        .round(2).reset_index().to_csv(VERITE / "prevoyance_ultime_par_survenance.csv", sep=";", index=False)

    # ---------------------------------------------------------------- extractions annuelles
    colonnes_sante = ["id_ligne", "id_decompte", "id_assure", "id_contrat", "segment", "poste", "date_soins", "date_paiement",
                      "frais_reels", "base_remboursement", "montant_ro", "montant_rembourse", "nb_actes", "canal", "type_ligne"]
    colonnes_pay = ["id_paiement", "id_sinistre", "garantie", "type_paiement", "date_debut_periode", "date_fin_periode",
                    "date_paiement", "montant"]
    journal_anomalies = []
    for n in EXERCICES:
        arrete = pd.Timestamp(f"{n}-12-31")
        fen = ex.fenetres(n)
        rep = SORTIE / f"exercice={n}"
        rng_n = np.random.default_rng(SEED + n)
        fichiers = {}
        fichiers["REF_CONTRATS"] = ex.ref_contrats(contrats, arrete)
        a, j = ex.bruit_assures(rng_n, ex.ref_assures(aff, arrete), n)
        fichiers["REF_ASSURES"] = a
        journal_anomalies += [(n, *x) for x in j]
        cs = cot[((cot.branche == "SANTE") & ex._entre(cot.date_debut_periode, *fen["sante"]))
                 | ((cot.branche == "PREVOYANCE") & ex._entre(cot.date_debut_periode, *fen["prev_cotisations"]))]
        fichiers["FLX_COTISATIONS"] = cs.reset_index(drop=True)
        ss = soins[ex._entre(soins.date_paiement, *fen["sante"])][colonnes_sante]
        ss, j = ex.bruit_sante(rng_n, ss, n, None)
        fichiers["FLX_PRESTATIONS_SANTE"] = ss
        journal_anomalies += [(n, *x) for x in j]
        snp = ex.snapshot_sinistres(sin, pay, arrete)
        pp = pay[ex._entre(pay.date_paiement, *fen["prev_paiements"])][colonnes_pay].reset_index(drop=True)
        snp, pp, j = ex.bruit_sinistres(rng_n, snp, pp, n, aff)
        fichiers["SNP_SINISTRES_PREVOYANCE"] = snp
        fichiers["FLX_PRESTATIONS_PREVOYANCE"] = pp
        journal_anomalies += [(n, *x) for x in j]
        fichiers["CPT_BALANCE"] = ex.balance(n, cot, soins, pay, sin, contrats)
        temoin = []
        for nom, df in fichiers.items():
            chemin = rep / f"{nom}_{n}.csv"
            h = ex.ecrire(df, chemin)
            col = ex.COLONNE_CONTROLE[nom]
            temoin.append({"fichier": chemin.name, "type_extraction": fen["type"],
                           "periode_debut": fen["sante"][0] if nom == "FLX_PRESTATIONS_SANTE" else
                           (fen["prev_paiements"][0] if nom == "FLX_PRESTATIONS_PREVOYANCE" else f"{n}-01-01"),
                           "periode_fin": f"{n}-12-31", "date_extraction": f"{n + 1}-01-08", "nb_lignes": len(df),
                           "somme_controle": round(float(pd.to_numeric(df[col], errors="coerce").sum()), 2) if col else None,
                           "sha256": h})
        pd.DataFrame(temoin).to_csv(rep / f"_TEMOIN_{n}.csv", sep=";", index=False)
        print(f"  exercice {n} : " + ", ".join(f"{k}={len(v):,}" for k, v in fichiers.items()) + f" ({time.time() - t0:.0f}s)")
    pd.DataFrame(journal_anomalies, columns=["exercice", "domaine", "anomalie_injectee", "nb"]).to_csv(
        VERITE / "anomalies_injectees.csv", sep=";", index=False)
    (VERITE / "README.md").write_text(
        "Donnees de verite du generateur (hors chaine de production).\n\n"
        "- sante_ultime_par_mois_soins.csv : charge ultime simulee par mois de soins (paiements jusqu'au 31/12/2026).\n"
        "- prevoyance_ultime_par_survenance.csv : cout ultime non actualise (duree complete simulee).\n"
        "- anomalies_injectees.csv : anomalies volontairement introduites dans les extractions.\n\n"
        "Usage : backtesting des methodes et recette des regles de qualite. Ne jamais brancher sur le pipeline.\n", encoding="utf-8")
    print(f"termine en {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
