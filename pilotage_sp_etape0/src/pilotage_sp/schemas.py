"""Contrats d'interface des extractions (structure attendue des fichiers bruts)."""

S, D, F, I = "string", "date", "double", "int"

FICHIERS = {
    "REF_CONTRATS": {"id_contrat": S, "branche": S, "segment": S, "code_produit": S, "formule": S, "id_entreprise": S,
                     "raison_sociale": S, "code_naf": S, "departement": S, "date_effet": D, "date_resiliation": D,
                     "franchise_incap_jours": F, "taux_ij": F, "taux_rente_invalidite": F,
                     "multiple_capital_non_cadre": F, "multiple_capital_cadre": F},
    "REF_ASSURES": {"id_assure": S, "id_personne": S, "id_personne_principale": S, "id_contrat": S, "branche": S, "segment": S,
                    "qualite": S, "sexe": S, "date_naissance": D, "date_adhesion": D, "date_radiation": D, "csp": S,
                    "salaire_annuel": F, "ij_garantie_journaliere": F, "franchise_jours": F,
                    "rente_invalidite_garantie_annuelle": F, "capital_deces_garanti": F, "departement": S},
    "FLX_COTISATIONS": {"id_quittance": S, "id_contrat": S, "branche": S, "segment": S, "garantie": S,
                        "date_debut_periode": D, "date_fin_periode": D, "date_emission": D, "montant_cotisation_ht": F},
    "FLX_PRESTATIONS_SANTE": {"id_ligne": S, "id_decompte": S, "id_assure": S, "id_contrat": S, "segment": S, "poste": S,
                              "date_soins": D, "date_paiement": D, "frais_reels": F, "base_remboursement": F,
                              "montant_ro": F, "montant_rembourse": F, "nb_actes": I, "canal": S, "type_ligne": S},
    "SNP_SINISTRES_PREVOYANCE": {"id_sinistre": S, "id_sinistre_origine": S, "id_assure": S, "id_contrat": S, "segment": S,
                                 "garantie": S, "sexe": S, "date_naissance": D, "csp": S, "salaire_reference": F,
                                 "date_survenance": D, "date_declaration": D, "franchise_jours": I,
                                 "date_debut_indemnisation": D, "ij_journaliere": F, "categorie_invalidite": I,
                                 "rente_annuelle": F, "capital": F, "rente_invalidite_garantie": F,
                                 "capital_deces_garanti": F, "statut": S, "date_cloture": D, "motif_cloture": S},
    "FLX_PRESTATIONS_PREVOYANCE": {"id_paiement": S, "id_sinistre": S, "garantie": S, "type_paiement": S,
                                   "date_debut_periode": D, "date_fin_periode": D, "date_paiement": D, "montant": F},
    "CPT_BALANCE": {"exercice": I, "branche": S, "segment": S, "garantie": S, "poste_comptable": S, "montant": F},
}

TABLES_BRONZE = {k: k.lower() for k in FICHIERS}

POSTES_SANTE = ["PHARMACIE", "SOINS_COURANTS", "BIOLOGIE", "DENTAIRE", "OPTIQUE", "AUDIOLOGIE", "HOSPITALISATION"]
TRANSCODAGE_POSTES = {"Pharmacie": "PHARMACIE", "SOINS COURANTS": "SOINS_COURANTS", "DENT": "DENTAIRE", "optique": "OPTIQUE",
                      "BIO": "BIOLOGIE", "HOSPI": "HOSPITALISATION", "AUDIO": "AUDIOLOGIE"}


def schema_spark(nom):
    from pyspark.sql import types as T
    conv = {S: T.StringType(), D: T.DateType(), F: T.DoubleType(), I: T.IntegerType()}
    return T.StructType([T.StructField(c, conv[t], True) for c, t in FICHIERS[nom].items()])


def lire_csv(spark, chemin, nom):
    """Lecture typee d'une extraction (separateur ';', dates ISO, UTF-8)."""
    return spark.read.csv(chemin, header=True, sep=";", schema=schema_spark(nom), dateFormat="yyyy-MM-dd", encoding="UTF-8",
                          mode="PERMISSIVE")
