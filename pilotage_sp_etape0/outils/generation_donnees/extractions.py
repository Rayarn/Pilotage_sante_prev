"""Extractions annuelles livrees par le systeme de gestion a l'actuariat (vision au 31/12/N).

Chaque exercice N produit, dans data/raw/exercice=N/ :
  REF_CONTRATS_N, REF_ASSURES_N, FLX_COTISATIONS_N, FLX_PRESTATIONS_SANTE_N,
  SNP_SINISTRES_PREVOYANCE_N, FLX_PRESTATIONS_PREVOYANCE_N, CPT_BALANCE_N et _TEMOIN_N.
L'exercice 2020 est la reprise de l'historique (bilan d'ouverture) : ses flux couvrent
2019-2020 en sante et 2010-2020 en prevoyance (paiements), 2016-2020 (cotisations prevoyance).

Les anomalies sont injectees ici, apres calcul de la balance comptable (propre) :
la reconciliation entre donnees nettoyees et balance est donc un vrai controle.
"""

import hashlib
import numpy as np
import pandas as pd

from monde import J, salaire_a, ids

SEP = ";"


def fenetres(exercice):
    if exercice == 2020:
        return {"sante": ("2019-01-01", "2020-12-31"), "prev_paiements": ("2010-01-01", "2020-12-31"),
                "prev_cotisations": ("2016-01-01", "2020-12-31"), "type": "REPRISE"}
    d = (f"{exercice}-01-01", f"{exercice}-12-31")
    return {"sante": d, "prev_paiements": d, "prev_cotisations": d, "type": "ANNUELLE"}


def _entre(s, a, b):
    return (s >= pd.Timestamp(a)) & (s <= pd.Timestamp(b))


def _masquer_futur(s, arrete):
    return s.where(s <= arrete)


# ============================================================================= referentiels
def ref_contrats(contrats, arrete):
    c = contrats[contrats.date_effet <= arrete].copy()
    c = c[c.date_resiliation.isna() | (c.date_resiliation >= arrete - pd.DateOffset(years=2))]
    c["date_resiliation"] = _masquer_futur(c.date_resiliation, arrete)
    cols = ["id_contrat", "branche", "segment", "code_produit", "formule", "id_entreprise", "raison_sociale", "code_naf",
            "departement", "date_effet", "date_resiliation", "franchise_incap_jours", "taux_ij", "taux_rente_invalidite",
            "multiple_capital_non_cadre", "multiple_capital_cadre"]
    return c.reindex(columns=cols).sort_values("id_contrat").reset_index(drop=True)


def ref_assures(aff, arrete):
    debut = pd.Timestamp(f"{arrete.year - 1}-01-01")
    a = aff[(aff.date_adhesion <= arrete) & (aff.date_radiation_brute.isna() | (aff.date_radiation_brute >= debut))].copy()
    a["date_radiation"] = _masquer_futur(a.date_radiation_brute, arrete)
    salarie = (a.segment == "COL") & (a.qualite == "ASSURE")
    ref = a.date_radiation.fillna(arrete).values.astype("datetime64[D]")
    a["salaire_annuel"] = np.where(salarie, salaire_a(a.salaire_embauche.values, a.date_embauche.values.astype("datetime64[D]"), ref),
                                   np.nan)
    a["csp"] = np.where(salarie, np.where(a.cadre, "CADRE", "NON_CADRE"),
                        np.where((a.branche == "PREVOYANCE") & (a.segment == "IND"), "TNS", None))
    cols = ["id_assure", "id_personne", "id_personne_principale", "id_contrat", "branche", "segment", "qualite", "sexe",
            "date_naissance", "date_adhesion", "date_radiation", "csp", "salaire_annuel", "ij_garantie_journaliere",
            "franchise_jours", "rente_invalidite_garantie_annuelle", "capital_deces_garanti", "departement"]
    return a[cols].sort_values("id_assure").reset_index(drop=True)


# ============================================================================= sinistres prevoyance (etat connu a l'arrete)
def snapshot_sinistres(sin, pay, arrete):
    s = sin[sin.date_declaration <= arrete].copy()
    fin_connue = s.date_fin_reelle <= arrete
    deces = s.garantie == "DECES"
    regle = pay[(pay.garantie == "DECES") & (pay.date_paiement <= arrete)].groupby("id_sinistre").date_paiement.max()
    date_reglement = s.id_sinistre.map(regle)
    s["statut"] = np.where(deces, np.where(date_reglement.notna(), "CLOS", "EN_COURS"), np.where(fin_connue, "CLOS", "EN_COURS"))
    s["date_cloture"] = np.where(deces, date_reglement, s.date_fin_reelle.where(fin_connue))
    s["date_cloture"] = pd.to_datetime(s["date_cloture"])
    s["motif_cloture"] = np.where(s.statut == "CLOS", np.where(deces, "CAPITAL_REGLE", s.motif_fin_reel), None)
    s["csp"] = np.where(s.segment == "IND", "TNS", np.where(s.cadre, "CADRE", "NON_CADRE"))
    cols = ["id_sinistre", "id_sinistre_origine", "id_assure", "id_contrat", "segment", "garantie", "sexe", "date_naissance",
            "csp", "salaire_reference", "date_survenance", "date_declaration", "franchise_jours", "date_debut_indemnisation",
            "ij_journaliere", "categorie_invalidite", "rente_annuelle", "capital", "rente_invalidite_garantie", "capital_deces_garanti",
            "statut", "date_cloture", "motif_cloture"]
    s = s[cols].sort_values("id_sinistre").reset_index(drop=True)
    s.loc[s.garantie != "INCAPACITE", ["franchise_jours", "ij_journaliere"]] = np.nan
    s.loc[s.garantie == "DECES", "date_debut_indemnisation"] = pd.NaT
    s["categorie_invalidite"] = s.categorie_invalidite.astype("Int64")
    s["franchise_jours"] = s.franchise_jours.astype("Int64")
    return s


# ============================================================================= balance comptable (donnees propres)
def balance(exercice, cot, soins, pay_prev, sin, contrats):
    a, b = f"{exercice}-01-01", f"{exercice}-12-31"
    seg = contrats.set_index("id_contrat").segment
    lignes = []
    c = cot[_entre(cot.date_debut_periode, a, b)].copy()
    c["segment"] = c.id_contrat.map(seg)
    for (br, sg, g), v in c.groupby(["branche", "segment", "garantie"]).montant_cotisation_ht.sum().items():
        lignes.append((exercice, br, sg, g, "COTISATIONS_ACQUISES", round(v, 2)))
    s = soins[_entre(soins.date_paiement, a, b)]
    for sg, v in s.groupby("segment").montant_rembourse.sum().items():
        lignes.append((exercice, "SANTE", sg, "FRAIS_DE_SANTE", "PRESTATIONS_PAYEES", round(v, 2)))
    p = pay_prev[_entre(pay_prev.date_paiement, a, b)].merge(sin[["id_sinistre", "segment"]], on="id_sinistre")
    for (sg, g), v in p.groupby(["segment", "garantie"]).montant.sum().items():
        lignes.append((exercice, "PREVOYANCE", sg, g, "PRESTATIONS_PAYEES", round(v, 2)))
    return pd.DataFrame(lignes, columns=["exercice", "branche", "segment", "garantie", "poste_comptable", "montant"])


# ============================================================================= anomalies
def bruit_sante(rng, s, exercice, assures_connus):
    s = s.copy()
    n = len(s)
    journal = []
    # doublons exacts (double integration d'un flux)
    k = rng.choice(n, int(n * 0.0003), replace=False)
    s = pd.concat([s, s.iloc[k]], ignore_index=True)
    journal.append(("SANTE", "DOUBLON_EXACT", len(k)))
    # inversion des colonnes date de soins / date de paiement
    k = rng.choice(n, int(n * 0.0002), replace=False)
    ds, dp = s.loc[k, "date_soins"].copy(), s.loc[k, "date_paiement"].copy()
    s.loc[k, "date_soins"], s.loc[k, "date_paiement"] = dp.values, ds.values
    journal.append(("SANTE", "DATE_SOINS_POSTERIEURE_PAIEMENT", len(k)))
    # frais reels incoherents (remboursement total superieur aux frais)
    prest = np.nonzero((s.type_ligne == "PRESTATION").values)[0]
    k = rng.choice(prest, int(n * 0.0002), replace=False)
    s.loc[k, "frais_reels"] = np.round((s.loc[k, "montant_ro"] + s.loc[k, "montant_rembourse"]) * 0.8, 2).values
    journal.append(("SANTE", "REMBOURSEMENT_SUPERIEUR_FRAIS", len(k)))
    # beneficiaires inconnus du referentiel
    k = rng.choice(n, int(n * 0.0001), replace=False)
    s.loc[k, "id_assure"] = [f"A9{rng.integers(0, 10**7):07d}" for _ in k]
    journal.append(("SANTE", "ASSURE_INCONNU", len(k)))
    # codes poste mal saisis
    k = rng.choice(n, int(n * 0.0005), replace=False)
    variantes = {"PHARMACIE": "Pharmacie", "SOINS_COURANTS": "SOINS COURANTS", "DENTAIRE": "DENT", "OPTIQUE": "optique",
                 "BIOLOGIE": "BIO", "HOSPITALISATION": "HOSPI", "AUDIOLOGIE": "AUDIO"}
    s.loc[k, "poste"] = s.loc[k, "poste"].map(variantes).values
    journal.append(("SANTE", "POSTE_NON_NORMALISE", len(k)))
    # date de soins manquante
    k = rng.choice(n, int(n * 0.0002), replace=False)
    s.loc[k, "date_soins"] = pd.NaT
    journal.append(("SANTE", "DATE_SOINS_MANQUANTE", len(k)))
    if exercice == 2023:
        # bascule du systeme de gestion : re-emission d'une partie des decomptes de novembre-decembre sous de nouveaux identifiants
        fen = np.nonzero((s.date_paiement >= "2023-11-01").values & (s.type_ligne == "PRESTATION").values)[0]
        k = rng.choice(fen, int(len(fen) * 0.025), replace=False)
        d = s.iloc[k].copy()
        d["id_ligne"] = ids("M", len(d), 10)
        d["id_decompte"] = ids("MD", len(d), 9)
        d["date_paiement"] = d.date_paiement + pd.to_timedelta(rng.integers(0, 6, len(d)), unit="D")
        d.loc[d.date_paiement > "2023-12-31", "date_paiement"] = pd.Timestamp("2023-12-31")
        s = pd.concat([s, d], ignore_index=True)
        journal.append(("SANTE", "DOUBLON_FONCTIONNEL_MIGRATION", len(k)))
    return s.sample(frac=1, random_state=int(rng.integers(0, 2**31))).reset_index(drop=True), journal


def bruit_assures(rng, a, exercice):
    a = a.copy()
    journal = []
    if exercice == 2022:
        col = np.nonzero(((a.segment == "COL") & (a.branche == "SANTE")).values)[0]
        k = rng.choice(col, int(len(col) * 0.025), replace=False)
        a.loc[k, "date_naissance"] = pd.NaT
        journal.append(("REFERENTIEL", "DATE_NAISSANCE_MANQUANTE", len(k)))
    if exercice == 2025:
        k = rng.choice(np.nonzero(((a.branche == "PREVOYANCE") & (a.segment == "COL") & a.date_radiation.isna()).values)[0], 45,
                       replace=False)
        a.loc[k, "salaire_annuel"] = 0.0
        journal.append(("REFERENTIEL", "SALAIRE_NUL", len(k)))
    return a, journal


def bruit_sinistres(rng, s, pay, exercice, aff):
    s, pay = s.copy(), pay.copy()
    journal = []
    k = rng.choice(len(pay), max(1, int(len(pay) * 0.0005)), replace=False)
    pay = pd.concat([pay, pay.iloc[k]], ignore_index=True)
    journal.append(("PREVOYANCE", "DOUBLON_EXACT_PAIEMENT", len(k)))
    if exercice == 2022:
        ouverts = np.nonzero(((s.garantie == "INCAPACITE") & (s.statut == "EN_COURS")).values)[0]
        k = rng.choice(ouverts, 3, replace=False)
        s.loc[k, "ij_journaliere"] = np.nan
        journal.append(("PREVOYANCE", "IJ_MANQUANTE", 3))
    if exercice == 2025:
        adh = aff.set_index("id_assure").date_adhesion
        ouverts = np.nonzero(((s.garantie == "INCAPACITE") & (s.statut == "EN_COURS") & (s.segment == "COL")).values)[0]
        k = rng.choice(ouverts, 2, replace=False)
        s.loc[k, "date_survenance"] = (s.loc[k, "id_assure"].map(adh) - pd.to_timedelta([45, 120], unit="D")).values
        journal.append(("PREVOYANCE", "SURVENANCE_ANTERIEURE_ADHESION", 2))
    return s, pay, journal


# ============================================================================= ecriture
def ecrire(df, chemin):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    out.to_csv(chemin, sep=SEP, index=False, encoding="utf-8", float_format="%.2f", lineterminator="\n")
    h = hashlib.sha256(chemin.read_bytes()).hexdigest()
    return h


COLONNE_CONTROLE = {"REF_CONTRATS": None, "REF_ASSURES": "salaire_annuel", "FLX_COTISATIONS": "montant_cotisation_ht",
                    "FLX_PRESTATIONS_SANTE": "montant_rembourse", "SNP_SINISTRES_PREVOYANCE": "capital",
                    "FLX_PRESTATIONS_PREVOYANCE": "montant", "CPT_BALANCE": "montant"}
