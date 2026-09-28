"""Prepare les donnees d'une presentation d'arrete a partir du JSON de livraison (reporting_N.json).

Usage : python outils/reporting/preparer_deck.py 2025  ->  reporting/2025/deck_2025.json
Tous les chiffres viennent de la livraison ; les commentaires d'actuaire (faits marquants) sont saisis
dans FAITS_MARQUANTS et relus a chaque arrete, comme dans une note de synthese classique.
"""

import json
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[2]

FAITS_MARQUANTS = {
    2021: [("Premier arrêté sur la plateforme", "Bilan d'ouverture 2020 recalculé à partir de l'historique, puis arrêté 2021 produit de bout en bout."),
           ("Rattrapage des soins", "Retour des soins reportés pendant la crise sanitaire et montée en charge du 100 % Santé en audiologie."),
           ("Taux maintenu à 0 %", "La moyenne du TME sur 24 mois est négative : le taux d'actualisation reste nul.")],
    2022: [("Remontée des taux", "Le plafond réglementaire passe à 0,66 % : taux d'actualisation porté à 0,50 %."),
           ("Plus d'arrêts longs", "La fréquence des arrêts de travail indemnisés progresse nettement sur l'exercice."),
           ("Référentiel incomplet", "Dates de naissance manquantes ; trois indemnités journalières reconstituées à partir des paiements.")],
    2023: [("Bascule du système santé", "Paiements retardés en fin d'année et décomptes réémis en double sous de nouveaux identifiants."),
           ("Réforme des retraites", "Le recul de l'âge légal allonge la durée de service des rentes d'invalidité."),
           ("Taux à 1,25 %", "Hausse du taux d'actualisation ; baisse du remboursement obligatoire dentaire au 1er octobre.")],
    2024: [("Retour à la normale", "Fin des retards de gestion : la méthode santé standard est rétablie."),
           ("Mali santé collectif", "Reliquat des retards de la bascule 2023, constaté à la liquidation."),
           ("Taux à 1,50 %", "Hausse modérée du taux d'actualisation, sous un plafond de 2,28 %.")],
    2025: [("Grand compte", "Entrée de Veltane Logistique (2 300 salariés) en santé et prévoyance collectives."),
           ("Suspension de la réforme", "La LFSS 2026 raccourcit la durée de service des rentes d'invalidité."),
           ("Données à instruire", "Deux dossiers d'arrêt en quarantaine (survenance antérieure à l'adhésion), 45 salaires nuls.")],
}

RECOMMANDATIONS = {
    2021: [("Fiabiliser la reprise", "Faire valider par la direction financière le bilan d'ouverture recalculé et figer la version."),
           ("Documenter la chaîne", "Soumettre la note technique NT-2021.1 à la revue indépendante avant la clôture."),
           ("Suivre la santé individuelle", "Le boni de liquidation confirme la prudence du S/P a priori, à revoir en 2022.")],
    2022: [("Corriger à la source", "Obtenir de la gestion la complétude des dates de naissance : la correction aval ne suffit pas."),
           ("Anticiper les taux", "Le plafond réglementaire monte vite : fixer une règle écrite de passage du taux."),
           ("Surveiller les arrêts", "La fréquence des arrêts longs progresse : lancer une étude de sinistralité par entreprise.")],
    2023: [("Sécuriser la bascule", "Exiger de la gestion un état du stock de décomptes en attente à chaque clôture mensuelle."),
           ("Tracer le jugement", "Le recours au S/P a priori est un jugement d'expert : le documenter et le rétro-tester en 2024."),
           ("Mesurer la réforme", "L'effet retraite sur l'invalidité est durable : l'intégrer au tarif prévoyance 2024.")],
    2024: [("Clore l'incident", "Le mali santé 2024 solde la bascule : documenter l'écart résiduel dans le retour d'expérience."),
           ("Stabiliser les lois", "Engager une étude d'expérience incapacité : les écarts de liquidation restent sous 10 %."),
           ("Automatiser la revue", "Brancher l'agent de revue sur les tables gold pour préparer les commentaires d'écart.")],
    2025: [("Suivre le grand compte", "Isoler Veltane Logistique dans les indicateurs : sa sinistralité dépasse l'hypothèse tarifaire."),
           ("Instruire la quarantaine", "Trancher les deux dossiers antérieurs à l'adhésion avant l'arrêté semestriel."),
           ("Revoir le barème", "Suivre les textes d'application de la LFSS 2026 et mettre à jour le barème si besoin.")],
}


LIB_GARANTIE = {"INCAPACITE": "Incapacité", "INVALIDITE": "Invalidité", "DECES": "Décès", "FRAIS_DE_SANTE": "Frais de santé"}
LIB_TYPE = {"PM_INVALIDITE": "PM invalidité", "PM_RENTES_EN_ATTENTE": "Rentes en attente", "PMGD": "Maintien garantie décès",
            "PM_INCAPACITE": "PM incapacité", "IBNR_INCAPACITE": "IBNR incapacité", "IBNR_INVALIDITE": "IBNR invalidité",
            "IBNR_DECES": "IBNR décès", "PSAP_DECES_CONNUS": "Décès connus", "PSAP_PRESTATIONS_ECHUES": "Prestations échues",
            "PFGS": "Frais de gestion"}
LIB_BAREME = {"LOI_2010": "Loi 2010", "REFORME_2023": "Réforme 2023", "LFSS_2026": "LFSS 2026"}
LIB_REGLE = {
    "S01": "Doublons exacts de lignes de prestations", "S02": "Doublons fonctionnels (décomptes réémis)",
    "S03": "Dates de soins manquantes", "S04": "Dates de soins et de paiement inversées", "S05": "Codes poste non normalisés",
    "S06": "Bénéficiaires absents du référentiel", "S07": "Remboursement supérieur aux frais réels",
    "S08": "Paiements hors période", "S09": "Montants manquants", "A01": "Dates de naissance manquantes",
    "A02": "Salaires nuls en prévoyance collective", "A03": "Affiliations en double", "K01": "Contrats en double",
    "C01": "Quittances en double", "C02": "Cotisations négatives", "P01": "Sinistres en double",
    "P02": "Indemnités journalières manquantes", "P03": "Survenance antérieure à l'adhésion",
    "P04": "Déclaration antérieure à la survenance", "P05": "Données de calcul manquantes", "V01": "Paiements en double",
    "V02": "Paiements sans sinistre"}
LIB_ACTION = {"REJET": "Rejet", "QUARANTAINE": "Quarantaine", "CORRECTION": "Correction", "SIGNALEMENT": "Signalement"}
LIB_CONTROLE = {"L06": "Règles qualité majeures hors seuil : validation de l'actuaire requise",
                "L07": "Variation d'une branche supérieure à 25 %, expliquée par les faits marquants"}


NBSP = "\u00a0"


def meur(x, d=1):
    return f"{x / 1e6:,.{d}f}".replace(",", NBSP).replace(".", ",") + NBSP + "M€"


def pct(x, d=1, signe=False):
    s = f"{x * 100:+.{d}f}" if signe else f"{x * 100:.{d}f}"
    return s.replace(".", ",") + NBSP + "%"


def methodes_sante(h):
    elr, bf = h["nb_mois_sp_apriori"], h["nb_mois_bf"] - h["nb_mois_sp_apriori"]
    m = [f"Chain Ladder pondéré sur {h['profondeur_facteurs_mois']} mois calendaires pour les mois de soins anciens"]
    if bf:
        m.append(f"Bornhuetter-Ferguson sur {bf} mois de soins" + (" précédant les derniers" if elr else " les plus récents"))
    if elr:
        m.append(f"S/P a priori sur les {elr} derniers mois de soins (jugement d'expert)")
    return m


def preparer(n):
    src = json.loads((RACINE / "livraison" / f"exercice={n}" / f"reporting_{n}.json").read_text(encoding="utf-8"))
    hp = pd.DataFrame(src["historique_provisions"])
    kpi = pd.DataFrame(src["historique_kpi"])
    cs = pd.DataFrame(src["charge_survenance"])
    pont = pd.DataFrame(src["pont"])
    dq = pd.DataFrame(src["qualite"])
    rec = pd.DataFrame(src["reconciliation"])
    h, hp1 = src["hypotheses"][str(n)], src["hypotheses"].get(str(n - 1))

    tot = hp.groupby("exercice").montant.sum()
    par_branche = hp[hp.exercice == n].groupby("branche").montant.sum()
    var = tot[n] / tot[n - 1] - 1
    k = kpi[kpi.exercice == n]
    def kv(ind, branche=None):
        x = k[k.indicateur == ind]
        return x[x.branche == branche].valeur.sum() if branche else x.valeur.sum()
    cot = {b: kv("cotisations_acquises", b) for b in ("SANTE", "PREVOYANCE")}
    charge = {b: kv("charge_comptable", b) for b in ("SANTE", "PREVOYANCE")}
    sp = {b: charge[b] / cot[b] for b in cot}

    # ------------------------------------------------ pont global (hors PFGS)
    tp = pont.sum(numeric_only=True)
    etapes = [(f"Provisions {n - 1}", tp.provision_ouverture, "total"), ("Règlements", -tp.ecoulement, "delta"),
              ("Liquidation", -tp.ecart_liquidation, "delta"), ("Nouvelle survenance", tp.nouvelle_survenance, "delta"),
              ("Hypothèses", tp.effet_hypotheses, "delta"), (f"Provisions {n}", tp.provision_cloture, "total")]
    pb = pont.groupby("branche").sum(numeric_only=True)

    # ------------------------------------------------ sante
    sante_sp = cs[(cs.branche == "SANTE") & (cs.annee_survenance >= 2019)].pivot_table(index="annee_survenance", columns="segment", values="sp")
    sres = pd.DataFrame(src["sante_resume"])
    sres = sres[sres.jeu_hypotheses == "N"].set_index("segment")
    pay_sante = kpi[(kpi.exercice == n) & (kpi.indicateur == "prestations_payees") & (kpi.branche == "SANTE")].groupby("segment").valeur.sum()
    meth = pd.DataFrame(src["sante_methodes"])
    liq_s = pb.loc["SANTE"] if "SANTE" in pb.index else None
    liq_seg = pont[pont.branche == "SANTE"].set_index("segment")

    # ------------------------------------------------ prevoyance
    prev_hist = hp[hp.branche == "PREVOYANCE"].pivot_table(index="exercice", columns="garantie", values="montant", aggfunc="sum").fillna(0)
    jeux = pd.DataFrame(src["prevoyance_jeux"])
    effet_taux = (jeux["N-1_TAUX_N"] - jeux["N-1"]).sum() if len(jeux) and "N-1_TAUX_N" in jeux else 0.0
    effet_autres = pont.effet_hypotheses.sum() - effet_taux
    ib = pd.DataFrame(src["ibnr"])
    ibnr_g = ib.groupby("garantie").ibnr.sum() if len(ib) else pd.Series(dtype=float)
    encours = kpi[(kpi.indicateur == "nb_sinistres_en_cours") & (kpi.exercice == n)].groupby("garantie").valeur.sum()
    declares = kpi[(kpi.indicateur == "nb_sinistres_declares_exercice") & (kpi.garantie == "INCAPACITE")].groupby("exercice").valeur.sum()
    prev_types = hp[(hp.exercice == n) & (hp.branche == "PREVOYANCE")].groupby("type_provision").montant.sum().sort_values(ascending=False)
    liq_p = pont[pont.branche == "PREVOYANCE"].groupby("garantie").sum(numeric_only=True)

    # ------------------------------------------------ qualite
    hors = dq[dq.statut == "HORS_SEUIL"]
    reserves = [c for c in src["controles"] if c["statut"] == "KO"]
    rec_sante = rec[rec.branche == "SANTE"]
    ecart_brut = rec_sante.ecart_relatif_avant_nettoyage.abs().max()

    # ------------------------------------------------ message cle
    moteur_hausse = max([("prévoyance", pb.loc["PREVOYANCE"].provision_cloture - pb.loc["PREVOYANCE"].provision_ouverture),
                         ("santé", pb.loc["SANTE"].provision_cloture - pb.loc["SANTE"].provision_ouverture)], key=lambda x: abs(x[1]))
    titre_cle = (f"Les provisions atteignent {meur(tot[n])}, en {'hausse' if var >= 0 else 'baisse'} de "
                 f"{pct(abs(var))} sur un an.")
    liq_txt = f"{'boni' if tp.ecart_liquidation >= 0 else 'mali'} de {pct(abs(tp.ecart_liquidation / tp.provision_ouverture))}"
    sous_titre_cle = {
        2021: f"La reprise de l'historique tient : la liquidation de 2020 se solde par un {liq_txt} de l'ouverture.",
        2022: f"La hausse des taux allège les provisions de {meur(-effet_taux)}, mais l'afflux de nouveaux arrêts l'emporte.",
        2023: f"La réforme des retraites et la bascule du système santé ajoutent {meur(effet_autres)} hors effet taux : c'est l'essentiel de la hausse.",
        2024: f"La santé revient à la normale ; en prévoyance, le {liq_txt} appelle une étude d'expérience.",
        2025: f"L'entrée d'un grand compte porte la hausse ; taux et suspension de la réforme la modèrent ({meur(tp.effet_hypotheses)}).",
    }[n]

    deck = {
        "exercice": n, "entite": "Mutuelle Orsane", "date_arrete": f"31 décembre {n}",
        "version": h["version_note_technique"],
        "titre_cle": titre_cle, "sous_titre_cle": sous_titre_cle,
        "faits": FAITS_MARQUANTS[n], "recommandations": RECOMMANDATIONS[n],
        "chiffres": [
            {"valeur": meur(tot[n]), "libelle": "Provisions techniques totales, PFGS incluses"},
            {"valeur": pct(var, signe=True), "libelle": f"Variation par rapport au 31 décembre {n - 1}"},
            {"valeur": pct(sp["SANTE"], 0), "libelle": "S/P comptable santé (charge / cotisations acquises)"},
            {"valeur": pct(sp["PREVOYANCE"], 0), "libelle": "S/P comptable prévoyance, effet des hypothèses inclus"},
        ],
        "repartition": {"labels": ["Prévoyance", "Santé"], "valeurs": [round(par_branche["PREVOYANCE"] / 1e6, 2), round(par_branche["SANTE"] / 1e6, 2)],
                        "centre": pct(par_branche["PREVOYANCE"] / tot[n], 0),
                        "types": [{"type": LIB_TYPE.get(t, t), "montant": meur(v)} for t, v in prev_types.head(4).items()],
                        "sante": meur(par_branche["SANTE"])},
        "pont": [{"libelle": l, "valeur": round(v / 1e6, 3), "nature": t} for l, v, t in etapes],
        "pont_commentaire": [
            f"Règlements de l'exercice sur sinistres antérieurs : {meur(tp.ecoulement)}",
            f"Écart de liquidation : {meur(abs(tp.ecart_liquidation))} de {'boni' if tp.ecart_liquidation >= 0 else 'mali'}, soit {pct(tp.ecart_liquidation / tp.provision_ouverture, 1, True)} de l'ouverture",
            f"Effet des hypothèses : {meur(tp.effet_hypotheses)} (taux {meur(effet_taux)}, barème et autres {meur(effet_autres)})",
        ],
        "sante": {
            "annees": [str(a) for a in sante_sp.index], "sp_ind": [round(x, 3) for x in sante_sp.get("IND", pd.Series()).fillna(0)],
            "sp_col": [round(x, 3) for x in sante_sp.get("COL", pd.Series()).fillna(0)],
            "cartes": [
                {"titre": "PSAP santé", "valeur": meur(sres.psap.sum(), 2),
                 "texte": f"{pct(sres.psap.sum() / pay_sante.sum())} des prestations payées dans l'année ; PFGS de {pct(h['taux_pfgs_sante'], 0)} en sus."},
                {"titre": "Incertitude", "valeur": pct(sres.ecart_type_mack.sum() / sres.psap_chain_ladder.sum(), 0),
                 "texte": "Coefficient de variation de Mack sur la PSAP Chain Ladder, segments additionnés."},
                {"titre": "Liquidation N-1", "valeur": pct(liq_s.ecart_liquidation / liq_s.provision_ouverture, 1, True) if liq_s is not None else "n.d.",
                 "texte": " ; ".join(f"{s} {pct(r.taux_liquidation, 1, True)}" for s, r in liq_seg.iterrows()) + " (positif = boni)."},
            ],
            "methodes": methodes_sante(h),
        },
        "prevoyance": {
            "annees": [str(a) for a in prev_hist.index],
            "series": [{"nom": LIB_GARANTIE[g], "valeurs": [round(v / 1e6, 2) for v in prev_hist[g]]}
                       for g in ("INVALIDITE", "INCAPACITE", "DECES") if g in prev_hist],
            "total": meur(par_branche["PREVOYANCE"]),
            "effet_taux": meur(effet_taux), "effet_autres": meur(effet_autres),
            "encours": {g: int(v) for g, v in encours.items()},
            "ibnr": {LIB_GARANTIE[g]: meur(v, 2) for g, v in ibnr_g.items()},
            "declares_annees": [str(a) for a in declares.index], "declares": [int(v) for v in declares.values],
            "liquidation": [{"garantie": LIB_GARANTIE[g],
                             "taux": pct(r.ecart_liquidation / r.provision_ouverture, 1, True)} for g, r in liq_p.iterrows()],
        },
        "qualite": {
            "nb_regles": int(len(dq)), "nb_conformes": int((dq.statut == "CONFORME").sum()), "nb_toleres": int((dq.statut == "TOLERE").sum()),
            "nb_hors_seuil": int(len(hors)),
            "hors_seuil": [{"id": r.regle_id, "libelle": LIB_REGLE[r.regle_id], "severite": r.severite.capitalize(),
                            "nb": int(r.nb_anomalies), "action": LIB_ACTION[r.action]} for r in hors.itertuples()],
            "reconciliation_max": pct(rec.ecart_relatif.abs().max(), 2),
            "ecart_brut_sante": pct(ecart_brut, 2) if pd.notna(ecart_brut) else "n.d.",
            "reserves": [LIB_CONTROLE.get(c["code"], c["libelle"]) for c in reserves],
        },
        "hypotheses": [
            ["Taux d'actualisation", pct(h["taux_technique"], 2), pct(hp1["taux_technique"], 2) if hp1 else ""],
            ["Plafond A331-22 (75 % TME 24 mois)", pct(h["plafond_reglementaire"], 2), pct(hp1["plafond_reglementaire"], 2) if hp1 else ""],
            ["Barème de retraite", LIB_BAREME[h["bareme_retraite"]], LIB_BAREME[hp1["bareme_retraite"]] if hp1 else ""],
            ["Santé : mois en Bornhuetter-Ferguson", str(h["nb_mois_bf"] - h["nb_mois_sp_apriori"]), str(hp1["nb_mois_bf"] - hp1["nb_mois_sp_apriori"]) if hp1 else ""],
            ["Santé : mois en S/P a priori", str(h["nb_mois_sp_apriori"]), str(hp1["nb_mois_sp_apriori"]) if hp1 else ""],
            ["S/P a priori individuel / collectif", f"{pct(h['sp_apriori_sante_ind'], 0)} / {pct(h['sp_apriori_sante_col'], 0)}",
             f"{pct(hp1['sp_apriori_sante_ind'], 0)} / {pct(hp1['sp_apriori_sante_col'], 0)}" if hp1 else ""],
            ["Lois de maintien et de passage", "BCAC", "BCAC"],
            ["Chargement de gestion santé / prévoyance", f"{pct(h['taux_pfgs_sante'], 0)} / {pct(h['taux_pfgs_prevoyance'], 0)}",
             f"{pct(hp1['taux_pfgs_sante'], 0)} / {pct(hp1['taux_pfgs_prevoyance'], 0)}" if hp1 else ""],
        ],
    }
    sortie = RACINE / "reporting" / str(n)
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / f"deck_{n}.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
    return deck


if __name__ == "__main__":
    for a in (sys.argv[1:] or ["2021", "2022", "2023", "2024", "2025"]):
        d = preparer(int(a))
        print(a, d["titre_cle"])
