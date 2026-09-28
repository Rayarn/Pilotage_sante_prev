"""Qualite des donnees : catalogue declaratif de regles, evaluation en Spark SQL, reconciliation comptable.

Chaque regle : identifiant, table controlee, dimension, severite, seuil de tolerance (taux d'anomalies),
action. La requete renvoie la cle des lignes en anomalie ; {t} designe la table bronze filtree sur
l'exercice, {bronze} le schema bronze, {n} l'exercice, {debut}/{fin} la periode declaree au temoin.

Statut : CONFORME (aucune anomalie), TOLERE (taux <= seuil), HORS_SEUIL (taux > seuil).
Une regle BLOQUANTE hors seuil arrete la chaine ; une regle MAJEURE hors seuil exige une validation
explicite (journal d'arrete) ; les actions sont appliquees dans tous les cas lors du passage en silver.
"""

import pandas as pd

TOLERANCE_RECONCILIATION = 0.001  # 0,10 %

REGLES = [
    # ------------------------------------------------------------------ prestations sante
    dict(id="S01", table="flx_prestations_sante", dimension="UNICITE", severite="MINEUR", seuil=0.005, action="REJET",
         libelle="Doublon exact (ligne integree deux fois)",
         requete="SELECT id_ligne AS cle FROM (SELECT id_ligne, row_number() OVER (PARTITION BY id_ligne ORDER BY id_ligne) rn FROM {t}) WHERE rn > 1"),
    dict(id="S02", table="flx_prestations_sante", dimension="UNICITE", severite="MAJEUR", seuil=0.001, action="REJET",
         libelle="Doublon fonctionnel (meme acte re-emis sous un autre identifiant)",
         requete="SELECT id_ligne AS cle FROM (SELECT id_ligne, row_number() OVER (PARTITION BY id_assure, poste, date_soins, "
                 "frais_reels, montant_rembourse, type_ligne ORDER BY id_ligne) rn FROM (SELECT DISTINCT * FROM {t} "
                 "WHERE date_soins IS NOT NULL)) WHERE rn > 1"),
    dict(id="S03", table="flx_prestations_sante", dimension="COMPLETUDE", severite="MINEUR", seuil=0.001, action="CORRECTION",
         libelle="Date de soins manquante (imputee : date de paiement - 15 jours)",
         requete="SELECT id_ligne AS cle FROM {t} WHERE date_soins IS NULL"),
    dict(id="S04", table="flx_prestations_sante", dimension="COHERENCE", severite="MINEUR", seuil=0.001, action="CORRECTION",
         libelle="Date de soins posterieure au paiement (colonnes permutees)",
         requete="SELECT id_ligne AS cle FROM {t} WHERE date_soins > date_paiement"),
    dict(id="S05", table="flx_prestations_sante", dimension="VALIDITE", severite="MINEUR", seuil=0.005, action="CORRECTION",
         libelle="Code poste hors nomenclature (transcodage)",
         requete="SELECT id_ligne AS cle FROM {t} WHERE poste NOT IN ({postes})"),
    dict(id="S06", table="flx_prestations_sante", dimension="INTEGRITE", severite="MAJEUR", seuil=0.001, action="QUARANTAINE",
         libelle="Beneficiaire absent du referentiel des assures",
         requete="SELECT id_ligne AS cle FROM {t} p LEFT ANTI JOIN (SELECT DISTINCT id_assure FROM {bronze}.ref_assures "
                 "WHERE exercice <= {n}) a ON p.id_assure = a.id_assure"),
    dict(id="S07", table="flx_prestations_sante", dimension="COHERENCE", severite="MINEUR", seuil=0.002, action="SIGNALEMENT",
         libelle="Remboursement total superieur aux frais reels",
         requete="SELECT id_ligne AS cle FROM {t} WHERE type_ligne = 'PRESTATION' AND montant_ro + montant_rembourse > frais_reels + 0.01"),
    dict(id="S08", table="flx_prestations_sante", dimension="EXHAUSTIVITE", severite="BLOQUANT", seuil=0.001, action="QUARANTAINE",
         libelle="Paiement hors de la periode declaree au temoin (apres correction S04)",
         requete="SELECT id_ligne AS cle FROM {t} WHERE greatest(date_paiement, coalesce(date_soins, date_paiement)) "
                 "NOT BETWEEN DATE'{debut}' AND DATE'{fin}'"),
    dict(id="S09", table="flx_prestations_sante", dimension="COMPLETUDE", severite="BLOQUANT", seuil=0.0, action="REJET",
         libelle="Montant rembourse manquant", requete="SELECT id_ligne AS cle FROM {t} WHERE montant_rembourse IS NULL"),
    # ------------------------------------------------------------------ referentiels
    dict(id="A01", table="ref_assures", dimension="COMPLETUDE", severite="MAJEUR", seuil=0.005, action="SIGNALEMENT",
         libelle="Date de naissance manquante", requete="SELECT id_assure AS cle FROM {t} WHERE date_naissance IS NULL"),
    dict(id="A02", table="ref_assures", dimension="VALIDITE", severite="MAJEUR", seuil=0.0, action="SIGNALEMENT",
         libelle="Salaire nul ou manquant (assure actif en prevoyance collective)",
         requete="SELECT id_assure AS cle FROM {t} WHERE branche = 'PREVOYANCE' AND segment = 'COL' AND qualite = 'ASSURE' "
                 "AND date_radiation IS NULL AND coalesce(salaire_annuel, 0) <= 0"),
    dict(id="A03", table="ref_assures", dimension="UNICITE", severite="BLOQUANT", seuil=0.0, action="REJET",
         libelle="Identifiant d'affiliation en double",
         requete="SELECT id_assure AS cle FROM {t} GROUP BY id_assure HAVING count(*) > 1"),
    dict(id="K01", table="ref_contrats", dimension="UNICITE", severite="BLOQUANT", seuil=0.0, action="REJET",
         libelle="Identifiant de contrat en double",
         requete="SELECT id_contrat AS cle FROM {t} GROUP BY id_contrat HAVING count(*) > 1"),
    # ------------------------------------------------------------------ cotisations
    dict(id="C01", table="flx_cotisations", dimension="UNICITE", severite="MINEUR", seuil=0.001, action="REJET",
         libelle="Quittance en double",
         requete="SELECT id_quittance AS cle FROM (SELECT id_quittance, row_number() OVER (PARTITION BY id_quittance "
                 "ORDER BY id_quittance) rn FROM {t}) WHERE rn > 1"),
    dict(id="C02", table="flx_cotisations", dimension="VALIDITE", severite="MINEUR", seuil=0.001, action="SIGNALEMENT",
         libelle="Cotisation negative", requete="SELECT id_quittance AS cle FROM {t} WHERE montant_cotisation_ht < 0"),
    # ------------------------------------------------------------------ sinistres et paiements prevoyance
    dict(id="P01", table="snp_sinistres_prevoyance", dimension="UNICITE", severite="BLOQUANT", seuil=0.0, action="REJET",
         libelle="Identifiant de sinistre en double",
         requete="SELECT id_sinistre AS cle FROM {t} GROUP BY id_sinistre HAVING count(*) > 1"),
    dict(id="P02", table="snp_sinistres_prevoyance", dimension="COMPLETUDE", severite="MAJEUR", seuil=0.0, action="CORRECTION",
         libelle="Incapacite en cours sans indemnite journaliere (deduite du dernier paiement)",
         requete="SELECT id_sinistre AS cle FROM {t} WHERE garantie = 'INCAPACITE' AND statut = 'EN_COURS' AND ij_journaliere IS NULL"),
    dict(id="P03", table="snp_sinistres_prevoyance", dimension="COHERENCE", severite="MAJEUR", seuil=0.0, action="QUARANTAINE",
         libelle="Survenance anterieure a l'adhesion (a instruire par la gestion)",
         requete="SELECT s.id_sinistre AS cle FROM {t} s JOIN (SELECT id_assure, min(date_adhesion) AS date_adhesion "
                 "FROM {bronze}.ref_assures WHERE exercice <= {n} GROUP BY id_assure) a ON s.id_assure = a.id_assure "
                 "WHERE s.garantie IN ('INCAPACITE', 'DECES') AND s.id_sinistre_origine IS NULL AND s.date_survenance < a.date_adhesion"),
    dict(id="P04", table="snp_sinistres_prevoyance", dimension="COHERENCE", severite="MAJEUR", seuil=0.0, action="QUARANTAINE",
         libelle="Declaration anterieure a la survenance",
         requete="SELECT id_sinistre AS cle FROM {t} WHERE date_declaration < date_survenance"),
    dict(id="P05", table="snp_sinistres_prevoyance", dimension="COMPLETUDE", severite="BLOQUANT", seuil=0.0, action="REJET",
         libelle="Donnee indispensable au calcul manquante (naissance, rente, capital)",
         requete="SELECT id_sinistre AS cle FROM {t} WHERE statut = 'EN_COURS' AND (date_naissance IS NULL OR "
                 "(garantie = 'INVALIDITE' AND rente_annuelle IS NULL) OR (garantie = 'DECES' AND capital IS NULL))"),
    dict(id="V01", table="flx_prestations_prevoyance", dimension="UNICITE", severite="MINEUR", seuil=0.001, action="REJET",
         libelle="Paiement en double",
         requete="SELECT id_paiement AS cle FROM (SELECT id_paiement, row_number() OVER (PARTITION BY id_paiement "
                 "ORDER BY id_paiement) rn FROM {t}) WHERE rn > 1"),
    dict(id="V02", table="flx_prestations_prevoyance", dimension="INTEGRITE", severite="MAJEUR", seuil=0.001, action="QUARANTAINE",
         libelle="Paiement rattache a un sinistre inconnu",
         requete="SELECT id_paiement AS cle FROM {t} p LEFT ANTI JOIN (SELECT DISTINCT id_sinistre FROM {bronze}.snp_sinistres_prevoyance "
                 "WHERE exercice = {n}) s ON p.id_sinistre = s.id_sinistre"),
]


def catalogue():
    """Catalogue des regles sous forme de table (ref.dq_regles, dictionnaire de donnees)."""
    return pd.DataFrame([{k: v for k, v in r.items() if k != "requete"} | {"requete": " ".join(r["requete"].split())}
                         for r in REGLES])


def evaluer(spark, ctx, periodes):
    """Evalue toutes les regles sur l'exercice. `periodes` : {table: (debut, fin)} issues du temoin.

    Retour : (resultats pandas, anomalies Spark DataFrame [exercice, regle_id, table_controlee, cle]).
    """
    from pyspark.sql import functions as Fn
    from .schemas import POSTES_SANTE
    n = ctx.exercice
    bronze = f"{ctx.catalog}.bronze"
    resultats, anomalies = [], None
    totaux = {}
    for table in sorted({r["table"] for r in REGLES}):
        df = spark.table(f"{bronze}.{table}").where(f"exercice = {n}").cache()
        df.createOrReplaceTempView(f"v_dq_{table}")
        totaux[table] = df.count()
    for r in REGLES:
        vue = f"v_dq_{r['table']}"
        debut, fin = periodes.get(r["table"], (f"{n}-01-01", f"{n}-12-31"))
        requete = r["requete"].format(t=vue, bronze=bronze, n=n, debut=debut, fin=fin,
                                      postes=", ".join(f"'{p}'" for p in POSTES_SANTE))
        a = spark.sql(requete).select(Fn.lit(n).alias("exercice"), Fn.lit(r["id"]).alias("regle_id"),
                                      Fn.lit(r["table"]).alias("table_controlee"), Fn.col("cle").cast("string"))
        a = a.cache()
        nb = a.count()
        total = totaux[r["table"]]
        taux = nb / total if total else 0.0
        statut = "CONFORME" if nb == 0 else ("TOLERE" if taux <= r["seuil"] else "HORS_SEUIL")
        resultats.append({"exercice": n, "regle_id": r["id"], "table_controlee": r["table"], "dimension": r["dimension"],
                          "libelle": r["libelle"], "severite": r["severite"], "action": r["action"], "seuil": r["seuil"],
                          "nb_lignes": total, "nb_anomalies": nb, "taux_anomalies": taux, "statut": statut,
                          "bloquant": statut == "HORS_SEUIL" and r["severite"] == "BLOQUANT"})
        anomalies = a if anomalies is None else anomalies.unionByName(a)
    return pd.DataFrame(resultats), anomalies


def reconcilier(silver_flux, balance, exercice):
    """Ecart relatif entre flux nettoyes et balance comptable, par branche, segment, garantie et poste."""
    cle = ["branche", "segment", "garantie", "poste_comptable"]
    x = balance.merge(silver_flux, on=cle, how="outer", suffixes=("_comptable", "_donnees")).fillna(0.0)
    x["ecart"] = x.montant_donnees - x.montant_comptable
    x["ecart_relatif"] = x.ecart / x.montant_comptable.where(x.montant_comptable != 0)
    x["statut"] = (x.ecart_relatif.abs() <= TOLERANCE_RECONCILIATION).map({True: "CONFORME", False: "HORS_SEUIL"})
    x["exercice"] = exercice
    return x
