# pilotage_sp : provisionnement santé-prévoyance automatisé (étape 0)

Chaîne Databricks complète d'arrêté des provisions techniques santé et prévoyance, de la réception des extractions à la livraison des chiffres et des présentations. Portefeuille fictif : **Mutuelle Orsane** (aucune donnée réelle).

Principe : le calcul est déterministe, versionné et rejouable ; l'IA (étape suivante) lira les tables gold pour analyser et rédiger, elle ne produira jamais une provision.

## Contenu

| Dossier | Rôle |
|---|---|
| `src/pilotage_sp/` | Bibliothèque : moteurs santé (Chain Ladder, Mack, Bornhuetter-Ferguson, S/P a priori) et prévoyance (BCAC, rentes en attente, PMGD, IBNR), pont N-1 vers N, catalogue qualité, barèmes de retraite, hypothèses, abstraction Databricks ou local |
| `notebooks/` | 10 notebooks Databricks (format source) : 00 initialisation à 09 livraison |
| `databricks.yml`, `resources/` | Asset Bundle : job d'arrêté annuel (DAG de 10 tâches) et job de rejeu historique 2020-2025 |
| `data/referentiels/` | Tables BCAC, TH/TF 00-02, série mensuelle des TME, hypothèses versionnées par arrêté |
| `outils/generation_donnees/` | Générateur déterministe du portefeuille fictif et des extractions 2020 (reprise) à 2025 |
| `outils/execution_locale/` | Exécution des notebooks sur Spark local, sans modification du code |
| `outils/reporting/` | Génération des présentations d'arrêté (PPTX puis PDF) depuis le JSON de livraison |
| `reporting/2021` à `2025` | Présentations d'arrêté, charte Dalverne (gabarit B) |
| `docs/` | Note technique (LaTeX et PDF, exemples calculés par le moteur), note de process (DOCX et PDF), dictionnaire de données |
| `livraison/` | Dernière livraison locale : exports CSV, synthèse XLSX, JSON de reporting, manifeste |
| `resultats_reference/` | Résultats figés servant de test de non-régression |
| `tests/` | Tests unitaires des moteurs et non-régression |

## Démarrage local

Prérequis : Python 3.11+, Java 17+, Node 18+ avec `pptxgenjs` et `docx`, LibreOffice pour les PDF, XeLaTeX pour la note technique.

```bash
pip install -r requirements.txt
python outils/generation_donnees/generer_donnees.py          # ~30 s, data/raw/exercice=2020..2025
python outils/execution_locale/run_local.py                  # ~15 min, les 6 arrêtés dans l'ordre
python -m pytest -q tests                                     # tests unitaires + non-régression
./outils/reporting/generer_tout.sh                            # présentations 2021 à 2025
python docs/note_technique/exemples.py && (cd docs/note_technique && xelatex note_technique.tex && xelatex note_technique.tex)
node docs/note_process/generer_note_process.js
python docs/dictionnaire/generer_dictionnaire.py
```

Un arrêté isolé : `python outils/execution_locale/run_local.py --exercices 2025` (l'arrêté N-1 doit exister pour le pont). Une tâche isolée : `--notebooks 07`.

## Déploiement Databricks

1. Créer le catalogue (`sp_pilotage_dev` par défaut), puis déployer : `databricks bundle deploy -t dev`.
2. Lancer une fois le job ou la tâche 00 : elle crée les schémas `landing`, `bronze`, `silver`, `gold`, `ops`, `ref` et les volumes.
3. Déposer les extractions dans `/Volumes/<catalogue>/landing/raw/exercice=N/`.
4. Rejeu complet : `databricks bundle run rejeu_historique -t dev` ; arrêté courant : `databricks bundle run arrete_annuel -t dev --params exercice=2025`.

Le code détecte l'environnement (`plateforme.py`) : Delta et `replaceWhere` sur Databricks, parquet et écrasement dynamique de partition en local. Testé en local avec PySpark 4.0.1 et pandas 3.0.2 ; les runtimes Databricks récents (pandas 2.x) sont supportés.

## Décisions structurantes

- **Arrêté 2020 = reprise** : bilan d'ouverture recalculé sur la plateforme, indispensable au pont 2021.
- **Double calcul** à chaque arrêté (hypothèses N et N-1, plus un jeu « N-1 avec taux N ») : l'effet des hypothèses est séparé de l'aléa de liquidation, et l'effet taux de l'effet barème.
- **Taux d'actualisation** : le plafond A331-22 est recalculé depuis la série des TME (75 % de la moyenne sur 24 mois) ; un taux au-dessus bloque l'arrêté.
- **Barèmes de retraite** : loi 2010, réforme 2023, suspension LFSS 2026, retenus selon la date d'arrêté.
- **Qualité** : 22 règles déclaratives, trois niveaux de sévérité, réconciliation comptable bloquante à 0,10 %.
- **Hors périmètre** : PPNA (contrats en année civile), PRC, rentes éducation et de conjoint, revalorisation, réassurance.

## Ce qui est fictif ou indicatif

- Portefeuille, assurés, sinistres, entreprises (dont Veltane Logistique) : fictifs, simulés par le générateur (graine fixe).
- Série TME : reprise d'une publication de place reproduisant la série de la Banque de France ; à brancher sur la source officielle en production.
- Commentaires d'actuaire des présentations (faits marquants, recommandations) : saisis dans `outils/reporting/preparer_deck.py`, à relire à chaque arrêté.
- La vérité simulée (`outils/generation_donnees/verite/`) sert uniquement au rétro-test des méthodes ; elle n'est jamais branchée sur la chaîne.

## Limites connues

Voir la section 8 de la note technique : lois BCAC sans ajustement d'expérience, catégorie d'invalidité future supposée égale à 2, coefficient de surmortalité de la PMGD non calibré, coût moyen IBNR non revalorisé.
