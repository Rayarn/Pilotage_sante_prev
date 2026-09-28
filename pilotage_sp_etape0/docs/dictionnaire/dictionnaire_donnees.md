# Dictionnaire de donnees

Genere par `docs/dictionnaire/generer_dictionnaire.py`. Catalogue Unity Catalog parametrable (`catalog`), schemas `landing`, `bronze`, `silver`, `gold`, `ops`, `ref`. Toutes les tables operationnelles sont partitionnees par `exercice`.

## 1. Extractions (zone landing, CSV `;`, UTF-8, dates ISO)

### REF_CONTRATS_N

| Colonne | Type |
|---|---|
| `id_contrat` | string |
| `branche` | string |
| `segment` | string |
| `code_produit` | string |
| `formule` | string |
| `id_entreprise` | string |
| `raison_sociale` | string |
| `code_naf` | string |
| `departement` | string |
| `date_effet` | date |
| `date_resiliation` | date |
| `franchise_incap_jours` | double |
| `taux_ij` | double |
| `taux_rente_invalidite` | double |
| `multiple_capital_non_cadre` | double |
| `multiple_capital_cadre` | double |

### REF_ASSURES_N

| Colonne | Type |
|---|---|
| `id_assure` | string |
| `id_personne` | string |
| `id_personne_principale` | string |
| `id_contrat` | string |
| `branche` | string |
| `segment` | string |
| `qualite` | string |
| `sexe` | string |
| `date_naissance` | date |
| `date_adhesion` | date |
| `date_radiation` | date |
| `csp` | string |
| `salaire_annuel` | double |
| `ij_garantie_journaliere` | double |
| `franchise_jours` | double |
| `rente_invalidite_garantie_annuelle` | double |
| `capital_deces_garanti` | double |
| `departement` | string |

### FLX_COTISATIONS_N

| Colonne | Type |
|---|---|
| `id_quittance` | string |
| `id_contrat` | string |
| `branche` | string |
| `segment` | string |
| `garantie` | string |
| `date_debut_periode` | date |
| `date_fin_periode` | date |
| `date_emission` | date |
| `montant_cotisation_ht` | double |

### FLX_PRESTATIONS_SANTE_N

| Colonne | Type |
|---|---|
| `id_ligne` | string |
| `id_decompte` | string |
| `id_assure` | string |
| `id_contrat` | string |
| `segment` | string |
| `poste` | string |
| `date_soins` | date |
| `date_paiement` | date |
| `frais_reels` | double |
| `base_remboursement` | double |
| `montant_ro` | double |
| `montant_rembourse` | double |
| `nb_actes` | int |
| `canal` | string |
| `type_ligne` | string |

### SNP_SINISTRES_PREVOYANCE_N

| Colonne | Type |
|---|---|
| `id_sinistre` | string |
| `id_sinistre_origine` | string |
| `id_assure` | string |
| `id_contrat` | string |
| `segment` | string |
| `garantie` | string |
| `sexe` | string |
| `date_naissance` | date |
| `csp` | string |
| `salaire_reference` | double |
| `date_survenance` | date |
| `date_declaration` | date |
| `franchise_jours` | int |
| `date_debut_indemnisation` | date |
| `ij_journaliere` | double |
| `categorie_invalidite` | int |
| `rente_annuelle` | double |
| `capital` | double |
| `rente_invalidite_garantie` | double |
| `capital_deces_garanti` | double |
| `statut` | string |
| `date_cloture` | date |
| `motif_cloture` | string |

### FLX_PRESTATIONS_PREVOYANCE_N

| Colonne | Type |
|---|---|
| `id_paiement` | string |
| `id_sinistre` | string |
| `garantie` | string |
| `type_paiement` | string |
| `date_debut_periode` | date |
| `date_fin_periode` | date |
| `date_paiement` | date |
| `montant` | double |

### CPT_BALANCE_N

| Colonne | Type |
|---|---|
| `exercice` | int |
| `branche` | string |
| `segment` | string |
| `garantie` | string |
| `poste_comptable` | string |
| `montant` | double |

## 2. Tables de la plateforme

### Schema `ref`

- `ref.bcac_maintien_incapacite` : Loi BCAC de maintien en incapacite (age d'entree x anciennete en mois).
  Colonnes : `age_entree` (bigint), `anciennete_mois` (bigint), `lx` (double).

- `ref.bcac_passage_invalidite` : Loi BCAC de passage en invalidite (nombres de passages par mois).
  Colonnes : `age_entree` (bigint), `anciennete_mois` (bigint), `nb_passages` (double), `probabilite_conditionnelle` (double).

- `ref.bcac_maintien_invalidite` : Loi BCAC de maintien en invalidite (annuelle).
  Colonnes : `age_entree` (bigint), `anciennete_annees` (bigint), `lx` (double).

- `ref.mortalite_th0002` : Table de mortalite TH 00-02.
  Colonnes : `age` (bigint), `lx` (double), `qx` (double).

- `ref.mortalite_tf0002` : Table de mortalite TF 00-02.
  Colonnes : `age` (bigint), `lx` (double), `qx` (double).

- `ref.hypotheses_arrete` : Hypotheses versionnees, une ligne par arrete.
  Colonnes : `exercice` (bigint), `date_arrete` (string), `version_note_technique` (string), `taux_technique` (double), `bareme_retraite` (string), `nb_mois_bf` (bigint), `nb_mois_sp_apriori` (bigint), `profondeur_facteurs_mois` (bigint), `sp_apriori_sante_ind` (double), `sp_apriori_sante_col` (double), `taux_pfgs_sante` (double), `taux_pfgs_prevoyance` (double), `coef_surmortalite_pmgd` (double), `nb_annees_cout_moyen_ibnr` (bigint), `commentaire` (string).

- `ref.tme_mensuel` : Serie mensuelle des TME.
  Colonnes : `mois` (string), `tme` (double).

- `ref.dq_regles` : Catalogue des regles de qualite.
  Colonnes : `id` (string), `table` (string), `dimension` (string), `severite` (string), `seuil` (double), `action` (string), `libelle` (string), `requete` (string).

### Schema `bronze`

- `bronze.ref_contrats` : Extraction REF_CONTRATS telle que livree, typee, partitionnee par exercice.
  Colonnes : `id_contrat` (string), `branche` (string), `segment` (string), `code_produit` (string), `formule` (string), `id_entreprise` (string), `raison_sociale` (string), `code_naf` (string), `departement` (string), `date_effet` (date), `date_resiliation` (date), `franchise_incap_jours` (double), `taux_ij` (double), `taux_rente_invalidite` (double), `multiple_capital_non_cadre` (double), `multiple_capital_cadre` (double), `_fichier_source` (string), `_horodatage_ingestion` (timestamp), `exercice` (int).

- `bronze.ref_assures` : Extraction REF_ASSURES telle que livree, typee, partitionnee par exercice.
  Colonnes : `id_assure` (string), `id_personne` (string), `id_personne_principale` (string), `id_contrat` (string), `branche` (string), `segment` (string), `qualite` (string), `sexe` (string), `date_naissance` (date), `date_adhesion` (date), `date_radiation` (date), `csp` (string), `salaire_annuel` (double), `ij_garantie_journaliere` (double), `franchise_jours` (double), `rente_invalidite_garantie_annuelle` (double), `capital_deces_garanti` (double), `departement` (string), `_fichier_source` (string), `_horodatage_ingestion` (timestamp), `exercice` (int).

- `bronze.flx_cotisations` : Extraction FLX_COTISATIONS telle que livree, typee, partitionnee par exercice.
  Colonnes : `id_quittance` (string), `id_contrat` (string), `branche` (string), `segment` (string), `garantie` (string), `date_debut_periode` (date), `date_fin_periode` (date), `date_emission` (date), `montant_cotisation_ht` (double), `_fichier_source` (string), `_horodatage_ingestion` (timestamp), `exercice` (int).

- `bronze.flx_prestations_sante` : Extraction FLX_PRESTATIONS_SANTE telle que livree, typee, partitionnee par exercice.
  Colonnes : `id_ligne` (string), `id_decompte` (string), `id_assure` (string), `id_contrat` (string), `segment` (string), `poste` (string), `date_soins` (date), `date_paiement` (date), `frais_reels` (double), `base_remboursement` (double), `montant_ro` (double), `montant_rembourse` (double), `nb_actes` (int), `canal` (string), `type_ligne` (string), `_fichier_source` (string), `_horodatage_ingestion` (timestamp), `exercice` (int).

- `bronze.snp_sinistres_prevoyance` : Extraction SNP_SINISTRES_PREVOYANCE telle que livree, typee, partitionnee par exercice.
  Colonnes : `id_sinistre` (string), `id_sinistre_origine` (string), `id_assure` (string), `id_contrat` (string), `segment` (string), `garantie` (string), `sexe` (string), `date_naissance` (date), `csp` (string), `salaire_reference` (double), `date_survenance` (date), `date_declaration` (date), `franchise_jours` (int), `date_debut_indemnisation` (date), `ij_journaliere` (double), `categorie_invalidite` (int), `rente_annuelle` (double), `capital` (double), `rente_invalidite_garantie` (double), `capital_deces_garanti` (double), `statut` (string), `date_cloture` (date), `motif_cloture` (string), `_fichier_source` (string), `_horodatage_ingestion` (timestamp), `exercice` (int).

- `bronze.flx_prestations_prevoyance` : Extraction FLX_PRESTATIONS_PREVOYANCE telle que livree, typee, partitionnee par exercice.
  Colonnes : `id_paiement` (string), `id_sinistre` (string), `garantie` (string), `type_paiement` (string), `date_debut_periode` (date), `date_fin_periode` (date), `date_paiement` (date), `montant` (double), `_fichier_source` (string), `_horodatage_ingestion` (timestamp), `exercice` (int).

- `bronze.cpt_balance` : Extraction CPT_BALANCE telle que livree, typee, partitionnee par exercice.
  Colonnes : `exercice_comptable` (int), `branche` (string), `segment` (string), `garantie` (string), `poste_comptable` (string), `montant` (double), `_fichier_source` (string), `_horodatage_ingestion` (timestamp), `exercice` (int).

### Schema `silver`

- `silver.prestations_sante` : Prestations sante nettoyees (colonne _corrections).
  Colonnes : `id_ligne` (string), `id_decompte` (string), `id_assure` (string), `id_contrat` (string), `segment` (string), `poste` (string), `date_soins` (date), `date_paiement` (date), `frais_reels` (double), `base_remboursement` (double), `montant_ro` (double), `montant_rembourse` (double), `nb_actes` (int), `canal` (string), `type_ligne` (string), `_corrections` (string), `exercice` (int).

- `silver.cotisations` : Quittances dedoublonnees.
  Colonnes : `id_quittance` (string), `id_contrat` (string), `branche` (string), `segment` (string), `garantie` (string), `date_debut_periode` (date), `date_fin_periode` (date), `date_emission` (date), `montant_cotisation_ht` (double), `exercice` (int).

- `silver.assures` : Affiliations de l'extraction.
  Colonnes : `id_assure` (string), `id_personne` (string), `id_personne_principale` (string), `id_contrat` (string), `branche` (string), `segment` (string), `qualite` (string), `sexe` (string), `date_naissance` (date), `date_adhesion` (date), `date_radiation` (date), `csp` (string), `salaire_annuel` (double), `ij_garantie_journaliere` (double), `franchise_jours` (double), `rente_invalidite_garantie_annuelle` (double), `capital_deces_garanti` (double), `departement` (string), `exercice` (int).

- `silver.contrats` : Contrats de l'extraction.
  Colonnes : `id_contrat` (string), `branche` (string), `segment` (string), `code_produit` (string), `formule` (string), `id_entreprise` (string), `raison_sociale` (string), `code_naf` (string), `departement` (string), `date_effet` (date), `date_resiliation` (date), `franchise_incap_jours` (double), `taux_ij` (double), `taux_rente_invalidite` (double), `multiple_capital_non_cadre` (double), `multiple_capital_cadre` (double), `exercice` (int).

- `silver.sinistres_prevoyance` : Dossiers de prevoyance a l'arrete, hors quarantaine, enrichis des garanties.
  Colonnes : `id_sinistre` (string), `id_sinistre_origine` (string), `id_assure` (string), `id_contrat` (string), `segment` (string), `garantie` (string), `sexe` (string), `date_naissance` (date), `csp` (string), `salaire_reference` (double), `date_survenance` (date), `date_declaration` (date), `franchise_jours` (int), `date_debut_indemnisation` (date), `ij_journaliere` (double), `categorie_invalidite` (int), `rente_annuelle` (double), `capital` (double), `rente_invalidite_garantie` (double), `capital_deces_garanti` (double), `statut` (string), `date_cloture` (date), `motif_cloture` (string), `_corrections` (string), `rente_invalidite_potentielle` (double), `capital_deces_potentiel` (double), `exercice` (int).

- `silver.paiements_prevoyance` : Paiements de prevoyance dedoublonnes.
  Colonnes : `id_paiement` (string), `id_sinistre` (string), `garantie` (string), `type_paiement` (string), `date_debut_periode` (date), `date_fin_periode` (date), `date_paiement` (date), `montant` (double), `exercice` (int).

### Schema `gold`

- `gold.increments_sante` : Increments de paiements (segment, mois de soins, mois de paiement).
  Colonnes : `segment` (string), `mois_soins` (string), `mois_paiement` (string), `montant` (double), `nb_lignes` (bigint), `exercice` (int).

- `gold.cotisations_mensuelles` : Cotisations acquises par mois.
  Colonnes : `branche` (string), `segment` (string), `garantie` (string), `mois` (string), `montant` (double), `exercice` (int).

- `gold.triangles_nombres_prevoyance` : Triangles de nombres.
  Colonnes : `annee_survenance` (bigint), `delai_declaration` (bigint), `nb_cumule` (double), `garantie` (string), `segment` (string), `exercice` (bigint).

- `gold.provisions_sante_detail` : PSAP par segment et mois de soins, jeux N et N-1.
  Colonnes : `segment` (string), `mois_soins` (string), `anciennete_mois` (bigint), `paye_cumule` (double), `facteur_cumule` (double), `cotisation_acquise` (double), `ultime_chain_ladder` (double), `ultime_bornhuetter_ferguson` (double), `ultime_sp_a_priori` (double), `methode` (string), `ultime_retenu` (double), `psap` (double), `ecart_type_mack` (double), `annee_soins` (bigint), `pfgs` (double), `jeu_hypotheses` (string), `exercice` (bigint).

- `gold.provisions_sante_resume` : PSAP et ecart-type de Mack par segment.
  Colonnes : `segment` (string), `psap` (double), `psap_chain_ladder` (double), `ecart_type_mack` (double), `facteurs` (string), `jeu_hypotheses` (string), `exercice` (bigint).

- `gold.facteurs_sante` : Facteurs de developpement.
  Colonnes : `segment` (string), `anciennete` (bigint), `facteur` (double), `sigma2` (double), `exercice` (bigint).

- `gold.provisions_prevoyance_sinistres` : Provisions par dossier (PM, PMGD, echues), jeux d'hypotheses.
  Colonnes : `id_sinistre` (string), `id_sinistre_origine` (string), `segment` (string), `garantie` (string), `statut` (string), `date_survenance` (string), `annee_survenance_origine` (int), `paye_cumule` (double), `pm_incapacite` (double), `pm_passage` (double), `pm_invalidite` (double), `pmgd` (double), `psap_deces` (double), `psap_echues` (double), `provision` (double), `charge` (double), `anciennete_mois` (double), `mois_avant_retraite` (double), `jeu_hypotheses` (string), `exercice` (bigint).

- `gold.ibnr_prevoyance` : IBNR par garantie, segment et annee de survenance.
  Colonnes : `garantie` (string), `segment` (string), `annee_survenance` (bigint), `nb_declares` (double), `nb_ultime` (double), `nb_ibnr` (double), `cout_moyen` (double), `ibnr` (double), `jeu_hypotheses` (string), `exercice` (bigint).

- `gold.provisions_prevoyance_synthese` : Provisions de prevoyance par type et annee de survenance.
  Colonnes : `segment` (string), `garantie` (string), `type_provision` (string), `annee_survenance` (bigint), `montant` (double), `jeu_hypotheses` (string), `exercice` (bigint).

- `gold.facteurs_declaration` : Facteurs de declaration IBNR.
  Colonnes : `garantie` (string), `segment` (string), `facteurs` (string), `jeu_hypotheses` (string), `exercice` (bigint).

- `gold.provisions_detail` : Table longue de toutes les provisions (branche, segment, garantie, type, survenance, jeu).
  Colonnes : `branche` (string), `segment` (string), `garantie` (string), `type_provision` (string), `annee_survenance` (bigint), `jeu_hypotheses` (string), `montant` (double), `exercice` (bigint).

- `gold.provisions_synthese` : Synthese de l'arrete (jeu N).
  Colonnes : `branche` (string), `segment` (string), `garantie` (string), `type_provision` (string), `montant` (double), `exercice` (bigint).

- `gold.pont_provisions` : Pont N-1 vers N.
  Colonnes : `branche` (string), `segment` (string), `garantie` (string), `provision_ouverture` (double), `ecoulement` (double), `ecart_liquidation` (double), `provision_residuelle` (double), `nouvelle_survenance` (double), `effet_hypotheses` (double), `provision_cloture` (double), `taux_liquidation` (double), `controle_bouclage` (double), `exercice` (bigint).

- `gold.charge_survenance` : Charge et S/P par annee de survenance.
  Colonnes : `segment` (string), `annee_survenance` (bigint), `paye` (double), `provision` (double), `cotisations` (double), `charge` (double), `sp` (double), `branche` (string), `exercice` (bigint).

- `gold.kpi_exercice` : Indicateurs de pilotage (table longue).
  Colonnes : `indicateur` (string), `branche` (string), `segment` (string), `garantie` (string), `valeur` (double), `exercice` (bigint).

### Schema `ops`

- `ops.journal_etapes` : Trace d'execution des taches.
  Colonnes : `exercice` (int), `etape` (string), `statut` (string), `message` (string), `horodatage_utc` (string).

- `ops.controle_disponibilite` : Controles du temoin.
  Colonnes : `fichier` (string), `present` (boolean), `temoin_present` (boolean), `sha256_ok` (boolean), `structure_ok` (boolean), `nb_lignes` (bigint), `nb_lignes_ok` (boolean), `somme_controle_ok` (boolean), `periode_debut` (string), `periode_fin` (string), `type_extraction` (string), `statut` (string), `exercice` (bigint).

- `ops.dq_resultats` : Resultats des regles de qualite.
  Colonnes : `regle_id` (string), `table_controlee` (string), `dimension` (string), `libelle` (string), `severite` (string), `action` (string), `seuil` (double), `nb_lignes` (bigint), `nb_anomalies` (bigint), `taux_anomalies` (double), `statut` (string), `bloquant` (boolean), `exercice` (bigint).

- `ops.dq_anomalies` : Cles des lignes en anomalie.
  Colonnes : `regle_id` (string), `table_controlee` (string), `cle` (string), `exercice` (int).

- `ops.reconciliation` : Ecarts flux contre balance.
  Colonnes : `branche` (string), `segment` (string), `garantie` (string), `poste_comptable` (string), `montant_comptable` (double), `montant_donnees` (double), `ecart` (double), `ecart_relatif` (double), `statut` (string), `montant_brut` (double), `ecart_relatif_avant_nettoyage` (double), `exercice` (bigint).

- `ops.controles_livraison` : Controles de livraison.
  Colonnes : `code` (string), `libelle` (string), `statut` (string), `severite` (string), `valeur` (string), `exercice` (bigint).

- `ops.journal_arrete` : Journal d'arrete et validation.
  Colonnes : `date_execution_utc` (string), `version_code` (string), `version_hypotheses` (string), `provisions_totales` (double), `statut` (string), `reserves` (string), `validation_actuaire` (string), `exercice` (bigint).

## 3. Catalogue des regles de qualite

| Id | Table | Dimension | Severite | Seuil | Action | Libelle |
|---|---|---|---|---|---|---|
| S01 | flx_prestations_sante | UNICITE | MINEUR | 0.50% | REJET | Doublon exact (ligne integree deux fois) |
| S02 | flx_prestations_sante | UNICITE | MAJEUR | 0.10% | REJET | Doublon fonctionnel (meme acte re-emis sous un autre identifiant) |
| S03 | flx_prestations_sante | COMPLETUDE | MINEUR | 0.10% | CORRECTION | Date de soins manquante (imputee : date de paiement - 15 jours) |
| S04 | flx_prestations_sante | COHERENCE | MINEUR | 0.10% | CORRECTION | Date de soins posterieure au paiement (colonnes permutees) |
| S05 | flx_prestations_sante | VALIDITE | MINEUR | 0.50% | CORRECTION | Code poste hors nomenclature (transcodage) |
| S06 | flx_prestations_sante | INTEGRITE | MAJEUR | 0.10% | QUARANTAINE | Beneficiaire absent du referentiel des assures |
| S07 | flx_prestations_sante | COHERENCE | MINEUR | 0.20% | SIGNALEMENT | Remboursement total superieur aux frais reels |
| S08 | flx_prestations_sante | EXHAUSTIVITE | BLOQUANT | 0.10% | QUARANTAINE | Paiement hors de la periode declaree au temoin (apres correction S04) |
| S09 | flx_prestations_sante | COMPLETUDE | BLOQUANT | 0.00% | REJET | Montant rembourse manquant |
| A01 | ref_assures | COMPLETUDE | MAJEUR | 0.50% | SIGNALEMENT | Date de naissance manquante |
| A02 | ref_assures | VALIDITE | MAJEUR | 0.00% | SIGNALEMENT | Salaire nul ou manquant (assure actif en prevoyance collective) |
| A03 | ref_assures | UNICITE | BLOQUANT | 0.00% | REJET | Identifiant d'affiliation en double |
| K01 | ref_contrats | UNICITE | BLOQUANT | 0.00% | REJET | Identifiant de contrat en double |
| C01 | flx_cotisations | UNICITE | MINEUR | 0.10% | REJET | Quittance en double |
| C02 | flx_cotisations | VALIDITE | MINEUR | 0.10% | SIGNALEMENT | Cotisation negative |
| P01 | snp_sinistres_prevoyance | UNICITE | BLOQUANT | 0.00% | REJET | Identifiant de sinistre en double |
| P02 | snp_sinistres_prevoyance | COMPLETUDE | MAJEUR | 0.00% | CORRECTION | Incapacite en cours sans indemnite journaliere (deduite du dernier paiement) |
| P03 | snp_sinistres_prevoyance | COHERENCE | MAJEUR | 0.00% | QUARANTAINE | Survenance anterieure a l'adhesion (a instruire par la gestion) |
| P04 | snp_sinistres_prevoyance | COHERENCE | MAJEUR | 0.00% | QUARANTAINE | Declaration anterieure a la survenance |
| P05 | snp_sinistres_prevoyance | COMPLETUDE | BLOQUANT | 0.00% | REJET | Donnee indispensable au calcul manquante (naissance, rente, capital) |
| V01 | flx_prestations_prevoyance | UNICITE | MINEUR | 0.10% | REJET | Paiement en double |
| V02 | flx_prestations_prevoyance | INTEGRITE | MAJEUR | 0.10% | QUARANTAINE | Paiement rattache a un sinistre inconnu |
