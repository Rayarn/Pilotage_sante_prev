"""Generateur du portefeuille fictif « Mutuelle Orsane » (sante et prevoyance, individuel et collectif).

Principe : on simule un monde complet (entreprises, salaries, familles, travailleurs
non salaries, soins, arrets de travail, invalidites, deces, cotisations) puis on en
tire, pour chaque exercice 2021 a 2025, les extractions que le systeme de gestion
livre a l'actuariat au 31 decembre : seules les informations connues a cette date y
figurent (declarations, paiements et clotures anterieurs a l'arrete). Les sinistres
survenus mais non declares n'y sont pas : c'est ce qui donne un sens aux IBNR.

Recit porte par les donnees (verifiable dans les extractions) :
- 2021 : rattrapage post-crise sanitaire, montee en charge du 100 % Sante (audiologie) ;
- 2022 : hausse des arrets de travail, remontee des taux, lot d'affiliations sans date de naissance ;
- 2023 : bascule du systeme de gestion sante (retard de liquidation en fin d'annee, doublons),
         baisse du remboursement dentaire du regime obligatoire au 1er octobre ;
- 2024 : annee de consolidation, rattrapage des stocks ;
- 2025 : entree d'un grand compte (logistique) en sante et prevoyance collectives.

Module « monde » : entites et populations. Point d'entree : generer_donnees.py
"""

from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))
from pilotage_sp.referentiels import charger_tables  # noqa: E402
from pilotage_sp.retraite import age_legal_reel_mois  # noqa: E402

SEED = 20260927
EXERCICES = [2020, 2021, 2022, 2023, 2024, 2025]  # 2020 : arrete de reprise (bilan d'ouverture)
DEBUT_PREV = np.datetime64("2010-01-01")
DEBUT_SANTE = np.datetime64("2019-01-01")
FIN = np.datetime64("2025-12-31")
HORIZON_FLUX = np.datetime64("2026-12-31")
SORTIE = RACINE / "data" / "raw"

J = np.timedelta64(1, "D")

# ----------------------------------------------------------------------------- parametres sante
POSTES = {
    #                 freq/an  frais  part RC  pente age  delai fixe  gamma(k, theta)   part tardive  tardif (min, max)
    "PHARMACIE":      (2.2,    85.0,  0.20,    0.020,     2,          (2.0, 3.0),       0.03,         (30, 120)),
    "SOINS_COURANTS": (1.9,    135.0, 0.30,    0.012,     4,          (2.0, 6.0),       0.05,         (30, 150)),
    "BIOLOGIE":       (0.6,    80.0,  0.33,    0.015,     4,          (2.0, 6.0),       0.04,         (30, 120)),
    "DENTAIRE":       (0.50,   420.0, 0.42,    0.006,     10,         (2.0, 12.0),      0.10,         (40, 200)),
    "OPTIQUE":        (0.26,   360.0, 0.55,    0.004,     7,          (2.0, 8.0),       0.06,         (30, 150)),
    "AUDIOLOGIE":     (0.030,  1600.0, 0.45,   0.050,     15,         (2.0, 15.0),      0.10,         (40, 200)),
    "HOSPITALISATION": (0.13,  1450.0, 0.22,   0.025,     15,         (1.5, 25.0),      0.15,         (60, 330)),
}
FACTEUR_FORMULE = {"ESSENTIEL": 0.75, "CONFORT": 1.00, "RENFORCE": 1.35}
INFLATION_FRAIS = {2019: 0.985, 2020: 1.000, 2021: 1.035, 2022: 1.075, 2023: 1.128, 2024: 1.182, 2025: 1.236}
SAISON = np.array([1.05, 1.00, 1.05, 0.98, 0.95, 1.00, 0.88, 0.75, 1.02, 1.08, 1.08, 1.06])
SAISON = SAISON / SAISON.mean()
INDICE_TARIF_SANTE = {
    "IND": {2019: 0.980, 2020: 1.000, 2021: 1.020, 2022: 1.056, 2023: 1.109, 2024: 1.192, 2025: 1.270},
    "COL": {2019: 0.990, 2020: 1.000, 2021: 1.010, 2022: 1.035, 2023: 1.076, 2024: 1.141, 2025: 1.209},
}
SP_CIBLE_2021 = {"IND": 0.79, "COL": 0.855}

# ----------------------------------------------------------------------------- parametres prevoyance
TENDANCE_ARRETS = {2010: 0.94, 2011: 0.95, 2012: 0.95, 2013: 0.96, 2014: 0.97, 2015: 0.97, 2016: 0.98,
                   2017: 0.99, 2018: 1.00, 2019: 1.00, 2020: 1.06, 2021: 1.05, 2022: 1.13, 2023: 1.16,
                   2024: 1.19, 2025: 1.21}
INDICE_TARIF_PREV = {y: 1.0 for y in range(2010, 2023)} | {2023: 1.03, 2024: 1.0815, 2025: 1.1248}
SP_CIBLE_PREV = {"COL": 0.84, "IND": 0.78}
REPARTITION_COTISATION_PREV = {"INCAPACITE": 0.40, "INVALIDITE": 0.36, "DECES": 0.24}

NOMS_A = ["Arvel", "Brisac", "Calmet", "Dorian", "Estrel", "Faucon", "Garnier", "Hauteval", "Isard", "Jolivet",
          "Keran", "Lorient", "Maurel", "Norvel", "Orlac", "Pradel", "Quintal", "Roustan", "Sorel", "Tavel",
          "Valcour", "Verdal", "Aubrac", "Belcaire", "Corvel", "Durance", "Escande", "Fenouil", "Gaillac", "Lunel"]
NOMS_B = ["Industrie", "Services", "Logistique", "Conseil", "Batiment", "Distribution", "Transports", "Ingenierie",
          "Restauration", "Sante", "Numerique", "Mecanique", "Energie", "Agroalimentaire", "Imprimerie"]
NAF = {"Industrie": "25.62A", "Services": "82.11Z", "Logistique": "52.29A", "Conseil": "70.22Z", "Batiment": "43.21A",
       "Distribution": "47.11F", "Transports": "49.41A", "Ingenierie": "71.12B", "Restauration": "56.10A",
       "Sante": "86.90D", "Numerique": "62.01Z", "Mecanique": "28.29B", "Energie": "35.14Z",
       "Agroalimentaire": "10.71C", "Imprimerie": "18.12Z"}
DEPARTEMENTS = ["75", "92", "93", "94", "95", "78", "91", "77", "69", "13", "33", "59", "31", "44", "67", "06", "34", "35"]


# ============================================================================= utilitaires
def d64(x):
    """Conversion robuste vers numpy datetime64[D] (NaT conserve)."""
    if x is None or (not isinstance(x, np.datetime64) and pd.isna(x)):
        return np.datetime64("NaT")
    return np.datetime64(pd.Timestamp(x).date())


def jours(x):
    return (np.asarray(x, dtype="datetime64[D]") - np.datetime64("1970-01-01")).astype(np.int64)


def date_de(j):
    return np.datetime64("1970-01-01") + np.asarray(j, dtype=np.int64) * J


def ajouter_mois(dates, mois):
    """Decalage calendaire en mois, vectorise, jour tronque a la fin du mois."""
    d = np.asarray(dates, dtype="datetime64[D]")
    m = d.astype("datetime64[M]")
    jour = (d - m.astype("datetime64[D]")).astype(int)
    cible = m + np.asarray(mois, dtype=int).astype("timedelta64[M]")
    nb_jours = ((cible + np.timedelta64(1, "M")).astype("datetime64[D]") - cible.astype("datetime64[D]")).astype(int)
    return cible.astype("datetime64[D]") + np.minimum(jour, nb_jours - 1) * J


def age_a(naissance, date):
    return (np.asarray(date, dtype="datetime64[D]") - np.asarray(naissance, dtype="datetime64[D]")).astype(int) / 365.25


def ids(prefixe, n, largeur, depart=0):
    return np.array([f"{prefixe}{i:0{largeur}d}" for i in range(depart + 1, depart + n + 1)], dtype=object)


def lognormale(rng, moyenne, sigma, n):
    mu = np.log(np.maximum(moyenne, 1e-9)) - 0.5 * sigma ** 2
    return rng.lognormal(mu, sigma, n)


def dates_uniformes(rng, debut, fin):
    debut = jours(debut)
    fin = jours(fin)
    return date_de(debut + np.floor(rng.random(len(debut)) * np.maximum(fin - debut + 1, 1)).astype(np.int64))


# ============================================================================= entreprises et contrats collectifs
def generer_entreprises(rng):
    n_anciennes, n_nouvelles = 125, 75
    n = n_anciennes + n_nouvelles
    entree = np.concatenate([
        dates_uniformes(rng, np.full(n_anciennes, np.datetime64("2001-01-01")), np.full(n_anciennes, np.datetime64("2009-12-31"))),
        dates_uniformes(rng, np.full(n_nouvelles, np.datetime64("2010-01-01")), np.full(n_nouvelles, np.datetime64("2024-06-30"))),
    ])
    entree = entree.astype("datetime64[M]").astype("datetime64[D]")  # effet au 1er du mois
    duree = rng.exponential(1 / 0.035, n)
    sortie = entree + (duree * 365.25).astype(int) * J
    sortie = np.array([np.datetime64(f"{str(d)[:4]}-12-31") for d in sortie])  # resiliation au 31/12
    sortie = np.where(sortie <= FIN, sortie, np.datetime64("NaT"))
    secteurs = rng.choice(NOMS_B, n)
    effectif = np.clip(lognormale(rng, 72, 1.05, n), 6, 1100).astype(int)
    df = pd.DataFrame({
        "id_entreprise": ids("E", n, 5),
        "raison_sociale": [f"{rng.choice(NOMS_A)} {s}" for s in secteurs],
        "secteur": secteurs,
        "code_naf": [NAF[s] for s in secteurs],
        "departement": rng.choice(DEPARTEMENTS, n),
        "date_entree": entree,
        "date_sortie": sortie,
        "effectif_initial": effectif,
        "facteur_arrets": np.exp(rng.normal(0, 0.12, n)),
        "grand_compte": False,
    })
    # Grand compte 2025
    gc = pd.DataFrame([{
        "id_entreprise": f"E{n + 1:05d}", "raison_sociale": "Veltane Logistique", "secteur": "Logistique",
        "code_naf": "52.29A", "departement": "95", "date_entree": np.datetime64("2025-01-01"),
        "date_sortie": np.datetime64("NaT"), "effectif_initial": 2300, "facteur_arrets": 1.35, "grand_compte": True}])
    df = pd.concat([df, gc], ignore_index=True)
    df["couvre_prev"] = rng.random(len(df)) < 0.80
    df["couvre_sante"] = rng.random(len(df)) < 0.75
    df.loc[~df.couvre_prev & ~df.couvre_sante, "couvre_prev"] = True
    df.loc[df.grand_compte, ["couvre_prev", "couvre_sante"]] = True
    # Second portefeuille d'entreprises assurees en prevoyance seule (courtage) : double la population
    # prevoyance collective sans modifier la sante, pour stabiliser IBNR et provisions d'invalidite.
    m = 200
    entree2 = np.concatenate([
        dates_uniformes(rng, np.full(125, np.datetime64("2001-01-01")), np.full(125, np.datetime64("2009-12-31"))),
        dates_uniformes(rng, np.full(75, np.datetime64("2010-01-01")), np.full(75, np.datetime64("2024-06-30")))])
    entree2 = entree2.astype("datetime64[M]").astype("datetime64[D]")
    sortie2 = entree2 + (rng.exponential(1 / 0.035, m) * 365.25).astype(int) * J
    sortie2 = np.array([np.datetime64(f"{str(d)[:4]}-12-31") for d in sortie2])
    sortie2 = np.where(sortie2 <= FIN, sortie2, np.datetime64("NaT"))
    secteurs2 = rng.choice(NOMS_B, m)
    df2 = pd.DataFrame({
        "id_entreprise": ids("E", m, 5, depart=len(df)), "raison_sociale": [f"{rng.choice(NOMS_A)} {s}" for s in secteurs2],
        "secteur": secteurs2, "code_naf": [NAF[s] for s in secteurs2], "departement": rng.choice(DEPARTEMENTS, m),
        "date_entree": entree2, "date_sortie": sortie2, "effectif_initial": np.clip(lognormale(rng, 72, 1.05, m), 6, 1100).astype(int),
        "facteur_arrets": np.exp(rng.normal(0, 0.12, m)), "grand_compte": False, "couvre_prev": True, "couvre_sante": False})
    return pd.concat([df, df2], ignore_index=True)


def generer_contrats_collectifs(rng, ent):
    lignes = []
    k_sc = k_pc = 0
    for e in ent.itertuples():
        if e.couvre_sante:
            k_sc += 1
            effet = max(d64(e.date_entree), np.datetime64("2016-01-01"))
            formule = "CONFORT" if e.grand_compte else rng.choice(["ESSENTIEL", "CONFORT", "RENFORCE"], p=[0.30, 0.50, 0.20])
            lignes.append({"id_contrat": f"SC{k_sc:05d}", "branche": "SANTE", "segment": "COL",
                           "code_produit": f"SANTE_COL_{formule}", "id_entreprise": e.id_entreprise,
                           "raison_sociale": e.raison_sociale, "code_naf": e.code_naf, "departement": e.departement,
                           "date_effet": effet, "date_resiliation": e.date_sortie, "formule": formule,
                           "part_familles": 0.60 if e.grand_compte else float(np.clip(rng.normal(0.42, 0.12), 0.1, 0.8)),
                           "franchise_incap_jours": np.nan, "taux_ij": np.nan, "taux_rente_invalidite": np.nan,
                           "multiple_capital_non_cadre": np.nan, "multiple_capital_cadre": np.nan,
                           "taux_cotisation_prevoyance": np.nan, "ajustement_experience": float(np.exp(rng.normal(0, 0.06)))})
        if e.couvre_prev:
            k_pc += 1
            formule = "STANDARD" if (e.grand_compte or rng.random() < 0.65) else "RENFORCE"
            renf = formule == "RENFORCE"
            lignes.append({"id_contrat": f"PC{k_pc:05d}", "branche": "PREVOYANCE", "segment": "COL",
                           "code_produit": f"PREV_COL_{formule}", "id_entreprise": e.id_entreprise,
                           "raison_sociale": e.raison_sociale, "code_naf": e.code_naf, "departement": e.departement,
                           "date_effet": e.date_entree, "date_resiliation": e.date_sortie, "formule": formule,
                           "part_familles": np.nan,
                           "franchise_incap_jours": 90 if (e.grand_compte or rng.random() < 0.80) else 30,
                           "taux_ij": 0.35 if renf else 0.28, "taux_rente_invalidite": 0.35 if renf else 0.28,
                           "multiple_capital_non_cadre": 2.0 if renf else 1.5, "multiple_capital_cadre": 3.0 if renf else 2.5,
                           "taux_cotisation_prevoyance": np.nan, "ajustement_experience": float(np.exp(rng.normal(0, 0.06)))})
    return pd.DataFrame(lignes)


# ============================================================================= salaries (processus de renouvellement)
def generer_salaries(rng, ent):
    """Periodes d'emploi des salaries : effectif initial, departs (turnover, retraite), remplacements, croissance."""
    blocs = []
    compteur = 0
    for e in ent.itertuples():
        w0 = max(d64(e.date_entree), DEBUT_PREV)
        w1 = FIN if pd.isna(e.date_sortie) else min(d64(e.date_sortie), FIN)
        if w1 <= w0:
            continue
        n0 = e.effectif_initial
        age0 = np.clip(rng.normal(43 if e.grand_compte else 41, 10.5, n0), 20, 61)
        naissance = w0 - (age0 * 365.25).astype(int) * J
        embauche = w0 - (rng.exponential(6, n0) * 365.25).astype(int) * J
        embauche = np.maximum(embauche, naissance + int(20 * 365.25) * J)
        debut = np.full(n0, w0)
        # croissance nette de 1 % par an
        annees = (w1 - w0).astype(int) / 365.25
        n_cr = rng.poisson(n0 * 0.01 * annees)
        age_cr = np.clip(rng.normal(34, 9, n_cr), 20, 58)
        deb_cr = dates_uniformes(rng, np.full(n_cr, w0), np.full(n_cr, w1))
        naissance = np.concatenate([naissance, deb_cr - (age_cr * 365.25).astype(int) * J])
        embauche = np.concatenate([embauche, deb_cr])
        debut = np.concatenate([debut, deb_cr])
        vague_n, vague_emb, vague_deb = naissance, embauche, debut
        while len(vague_n):
            retraite = ajouter_mois(vague_n, age_legal_reel_mois(vague_n))
            depart = vague_deb + (rng.exponential(1 / 0.11, len(vague_n)) * 365.25).astype(int) * J
            fin_theorique = np.minimum(depart, retraite)
            fin = np.minimum(fin_theorique, w1)
            m = len(vague_n)
            blocs.append(pd.DataFrame({
                "id_entreprise": e.id_entreprise, "date_naissance": vague_n, "date_embauche": vague_emb,
                "debut": vague_deb, "fin": fin,
                "motif_fin": np.where(fin_theorique > w1, "FIN_FENETRE", np.where(retraite <= depart, "RETRAITE", "DEPART")),
                "sexe": rng.choice(["F", "H"], m), "cadre": rng.random(m) < (0.18 if e.grand_compte else 0.26),
                "grand_compte": e.grand_compte, "facteur_arrets": e.facteur_arrets}))
            compteur += m
            remplacer = fin_theorique < w1
            nb = int(remplacer.sum())
            if nb == 0:
                break
            deb_r = fin_theorique[remplacer] + rng.integers(0, 60, nb) * J
            garder = deb_r < w1
            deb_r = deb_r[garder]
            age_r = np.clip(rng.normal(33, 9, len(deb_r)), 20, 58)
            vague_n = deb_r - (age_r * 365.25).astype(int) * J
            vague_emb = deb_r
            vague_deb = deb_r
    sal = pd.concat(blocs, ignore_index=True)
    sal["id_personne"] = ids("P", len(sal), 7)
    salaire_median = np.where(sal["cadre"], 54000.0, 31000.0)
    sal["salaire_embauche"] = np.round(lognormale(rng, salaire_median, 0.28, len(sal)), 0)
    return sal


def salaire_a(sal_embauche, date_embauche, date):
    anciennete = np.maximum(age_a(date_embauche, date), 0)
    return np.round(sal_embauche * 1.021 ** anciennete, 2)


# ============================================================================= sante individuelle et TNS
def generer_sante_individuelle(rng):
    n0, flux_annuel = 2900, 300
    sous0 = dates_uniformes(rng, np.full(n0, np.datetime64("2004-01-01")), np.full(n0, np.datetime64("2019-12-31")))
    n_new = rng.poisson(flux_annuel * 7)
    sous_new = dates_uniformes(rng, np.full(n_new, DEBUT_SANTE), np.full(n_new, np.datetime64("2025-11-30")))
    sous = np.concatenate([sous0, sous_new]).astype("datetime64[M]").astype("datetime64[D]")
    n = len(sous)
    depart_obs = np.maximum(sous, DEBUT_SANTE)
    fin = depart_obs + (rng.exponential(1 / 0.08, n) * 365.25).astype(int) * J
    fin = (fin.astype("datetime64[M]") + np.timedelta64(1, "M")).astype("datetime64[D]") - J
    fin = np.where(fin <= FIN, fin, np.datetime64("NaT"))
    ref_age = np.maximum(sous, DEBUT_SANTE)
    age_p = np.clip(rng.normal(57, 15, n), 18, 88)
    contrats = pd.DataFrame({
        "id_contrat": ids("SI", n, 6), "branche": "SANTE", "segment": "IND",
        "formule": rng.choice(["ESSENTIEL", "CONFORT", "RENFORCE"], n, p=[0.30, 0.45, 0.25]),
        "date_effet": sous, "date_resiliation": fin, "departement": rng.choice(DEPARTEMENTS, n)})
    contrats["code_produit"] = "SANTE_IND_" + contrats["formule"]
    membres = []
    naissance_p = ref_age - (age_p * 365.25).astype(int) * J
    sexe_p = rng.choice(["F", "H"], n)
    membres.append(pd.DataFrame({"id_contrat": contrats.id_contrat, "qualite": "ASSURE", "rang": 0,
                                 "date_naissance": naissance_p, "sexe": sexe_p}))
    conj = rng.random(n) < 0.55
    age_c = np.clip(age_p[conj] + rng.normal(-2, 4, conj.sum()), 18, 92)
    membres.append(pd.DataFrame({"id_contrat": contrats.id_contrat[conj].values, "qualite": "CONJOINT", "rang": 1,
                                 "date_naissance": ref_age[conj] - (age_c * 365.25).astype(int) * J,
                                 "sexe": np.where(sexe_p[conj] == "F", "H", "F")}))
    nb_enf = np.where(age_p < 55, rng.poisson(0.9, n), 0)
    idx = np.repeat(np.arange(n), nb_enf)
    age_e = rng.uniform(0, 23, len(idx))
    membres.append(pd.DataFrame({"id_contrat": contrats.id_contrat.values[idx], "qualite": "ENFANT",
                                 "rang": 2 + np.arange(len(idx)) % 5,
                                 "date_naissance": ref_age[idx] - (age_e * 365.25).astype(int) * J,
                                 "sexe": rng.choice(["F", "H"], len(idx))}))
    membres = pd.concat(membres, ignore_index=True).merge(
        contrats[["id_contrat", "date_effet", "date_resiliation", "departement"]], on="id_contrat")
    membres["date_adhesion"] = membres["date_effet"]
    fin_enf = ajouter_mois(membres["date_naissance"].values.astype("datetime64[D]"), np.full(len(membres), 26 * 12))
    rad = membres["date_resiliation"].values.astype("datetime64[D]")
    rad = np.where((membres.qualite == "ENFANT") & (fin_enf <= FIN) & (np.isnat(rad) | (fin_enf < rad)), fin_enf, rad)
    membres["date_radiation"] = rad
    membres = membres[(membres.date_radiation.isna()) | (membres.date_radiation > membres.date_adhesion)]
    return contrats, membres.drop(columns=["date_effet", "date_resiliation"]).reset_index(drop=True)


def generer_tns(rng):
    n0, flux_annuel = 5400, 580
    sous0 = dates_uniformes(rng, np.full(n0, np.datetime64("2000-01-01")), np.full(n0, np.datetime64("2009-12-31")))
    n_new = rng.poisson(flux_annuel * 16)
    sous_new = dates_uniformes(rng, np.full(n_new, DEBUT_PREV), np.full(n_new, np.datetime64("2025-11-30")))
    sous = np.concatenate([sous0, sous_new]).astype("datetime64[M]").astype("datetime64[D]")
    n = len(sous)
    age_s = np.concatenate([np.clip(rng.normal(40, 8, n0), 26, 55), np.clip(rng.normal(38, 8, n_new), 25, 55)])
    naissance = sous - (age_s * 365.25).astype(int) * J
    # anciens contrats : age a la souscription recale pour une population de 44 ans en moyenne en 2010
    retraite = ajouter_mois(naissance, age_legal_reel_mois(naissance))
    depart = np.maximum(sous, DEBUT_PREV) + (rng.exponential(1 / 0.065, n) * 365.25).astype(int) * J
    fin_theo = np.minimum(depart, retraite)
    fin = np.where(fin_theo <= FIN, (fin_theo.astype("datetime64[M]") + np.timedelta64(1, "M")).astype("datetime64[D]") - J,
                   np.datetime64("NaT"))
    garder = np.isnat(fin) | (fin > DEBUT_PREV)
    ij = rng.choice([30, 45, 60, 80, 100, 120, 150], n, p=[0.10, 0.18, 0.25, 0.20, 0.15, 0.08, 0.04]).astype(float)
    tns = pd.DataFrame({
        "date_naissance": naissance, "sexe": rng.choice(["F", "H"], n, p=[0.38, 0.62]), "date_adhesion": sous,
        "date_radiation": fin, "ij_garantie_journaliere": ij,
        "franchise_jours": rng.choice([30, 90], n, p=[0.75, 0.25]),
        "rente_invalidite_garantie_annuelle": np.round(ij * 365 * 0.5, 0),
        "capital_deces_garanti": rng.choice([50000, 75000, 100000, 150000, 200000], n, p=[0.25, 0.25, 0.25, 0.15, 0.10]).astype(float),
        "departement": rng.choice(DEPARTEMENTS, n), "facteur_arrets": 0.80})[garder].reset_index(drop=True)
    tns["id_contrat"] = ids("PI", len(tns), 6)
    tns["id_personne"] = ids("T", len(tns), 7)
    tns["formule"] = np.where(tns.ij_garantie_journaliere >= 100, "RENFORCE", "STANDARD")
    return tns


# ============================================================================= affiliations
def construire_affiliations(rng, cc, sal, si_membres, tns):
    """Table maitre des affiliations (une ligne par personne et par contrat), historique complet."""
    blocs = []
    # --- prevoyance collective
    pc = cc[cc.branche == "PREVOYANCE"][["id_contrat", "id_entreprise", "date_effet", "date_resiliation", "departement"]]
    x = sal.merge(pc, on="id_entreprise")
    deb = np.maximum(x.debut.values.astype("datetime64[D]"), x.date_effet.values.astype("datetime64[D]"))
    fin_c = x.date_resiliation.values.astype("datetime64[D]")
    fin = np.where(np.isnat(fin_c), x.fin.values.astype("datetime64[D]"), np.minimum(x.fin.values.astype("datetime64[D]"), fin_c))
    ok = fin > deb
    x = x[ok].copy()
    x["date_adhesion"], x["date_radiation_brute"] = deb[ok], fin[ok]
    x["qualite"], x["id_personne_principale"] = "ASSURE", None
    x["segment"], x["branche"] = "COL", "PREVOYANCE"
    blocs.append(x)
    # --- sante collective (salaries + ayants droit)
    scn = cc[cc.branche == "SANTE"][["id_contrat", "id_entreprise", "date_effet", "date_resiliation", "departement", "part_familles"]]
    y = sal.merge(scn, on="id_entreprise")
    deb = np.maximum.reduce([y.debut.values.astype("datetime64[D]"), y.date_effet.values.astype("datetime64[D]"),
                             np.full(len(y), DEBUT_SANTE)])
    fin_c = y.date_resiliation.values.astype("datetime64[D]")
    fin = np.where(np.isnat(fin_c), y.fin.values.astype("datetime64[D]"), np.minimum(y.fin.values.astype("datetime64[D]"), fin_c))
    ok = fin > deb
    y = y[ok].copy()
    y["date_adhesion"], y["date_radiation_brute"] = deb[ok], fin[ok]
    y["qualite"], y["id_personne_principale"] = "ASSURE", None
    y["segment"], y["branche"] = "COL", "SANTE"
    famille = rng.random(len(y)) < y.part_familles.values
    y["option_famille"] = famille
    blocs.append(y)
    age_sal = age_a(y.date_naissance.values.astype("datetime64[D]"), y.date_adhesion.values.astype("datetime64[D]"))
    conj = famille & (rng.random(len(y)) < 0.72)
    c = y[conj].copy()
    c["date_naissance"] = c.date_naissance.values.astype("datetime64[D]") + (rng.normal(2, 4, len(c)) * 365.25).astype(int) * J
    c["sexe"] = np.where(c.sexe == "F", "H", "F")
    c["qualite"], c["id_personne_principale"], c["cadre"] = "CONJOINT", c.id_personne, False
    c["id_personne"] = None
    blocs.append(c)
    nb_enf = np.where(famille & (age_sal < 56), rng.poisson(1.35, len(y)), 0)
    idx = np.repeat(np.arange(len(y)), nb_enf)
    e = y.iloc[idx].copy()
    age_e = rng.uniform(0, 22, len(e))
    e["date_naissance"] = e.date_adhesion.values.astype("datetime64[D]") - (age_e * 365.25).astype(int) * J
    e["sexe"] = rng.choice(["F", "H"], len(e))
    e["qualite"], e["id_personne_principale"], e["cadre"] = "ENFANT", e.id_personne, False
    e["id_personne"] = None
    fin_enf = ajouter_mois(e.date_naissance.values.astype("datetime64[D]"), np.full(len(e), 26 * 12))
    e["date_radiation_brute"] = np.minimum(e.date_radiation_brute.values.astype("datetime64[D]"), fin_enf)
    e = e[e.date_radiation_brute > e.date_adhesion]
    blocs.append(e)
    # --- sante individuelle
    m = si_membres.copy()
    m["segment"], m["branche"] = "IND", "SANTE"
    m["date_adhesion"] = np.maximum(m.date_adhesion.values.astype("datetime64[D]"), DEBUT_SANTE)
    m["date_radiation_brute"] = m.date_radiation.values.astype("datetime64[D]")
    m["id_personne_principale"] = None
    m["cadre"] = False
    blocs.append(m)
    # --- prevoyance individuelle (TNS)
    t = tns.copy()
    t["segment"], t["branche"], t["qualite"], t["id_personne_principale"], t["cadre"] = "IND", "PREVOYANCE", "ASSURE", None, False
    t["date_radiation_brute"] = t.date_radiation.values.astype("datetime64[D]")
    blocs.append(t)

    colonnes = ["id_personne", "id_personne_principale", "id_contrat", "branche", "segment", "qualite", "sexe", "date_naissance",
                "date_adhesion", "date_radiation_brute", "cadre", "salaire_embauche", "date_embauche", "departement",
                "ij_garantie_journaliere", "franchise_jours", "rente_invalidite_garantie_annuelle", "capital_deces_garanti",
                "grand_compte", "facteur_arrets", "option_famille"]
    aff = pd.concat([b.reindex(columns=colonnes) for b in blocs], ignore_index=True)
    sans_id = aff.id_personne.isna()
    aff.loc[sans_id, "id_personne"] = ids("B", int(sans_id.sum()), 7)
    aff["id_assure"] = ids("A", len(aff), 8)
    si = ((aff.branche == "SANTE") & (aff.segment == "IND")).values
    principal = aff[si & (aff.qualite == "ASSURE").values].set_index("id_contrat").id_personne
    ayant_droit = si & (aff.qualite != "ASSURE").values
    aff.loc[ayant_droit, "id_personne_principale"] = aff.loc[ayant_droit, "id_contrat"].map(principal).values
    aff["date_radiation_brute"] = aff["date_radiation_brute"].where(aff["date_radiation_brute"] < FIN)
    for col in ("date_naissance", "date_adhesion", "date_radiation_brute", "date_embauche"):
        aff[col] = pd.to_datetime(aff[col])
    aff["grand_compte"] = aff["grand_compte"].fillna(False).astype(bool)
    aff["facteur_arrets"] = aff["facteur_arrets"].fillna(1.0).astype(float)
    aff["cadre"] = aff["cadre"].fillna(False).astype(bool)
    return aff
