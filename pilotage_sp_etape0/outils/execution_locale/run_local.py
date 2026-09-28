"""Execution locale des notebooks Databricks (format source) sur Spark local.

Usage : python outils/execution_locale/run_local.py [--exercices 2020 2021 ...] [--notebooks 00 01 ...]
Chaque notebook est decoupe en cellules (# COMMAND ----------), les cellules Markdown (# MAGIC) sont ignorees,
`spark`, `dbutils` (widgets) et `display` sont fournis par des substituts. Meme code qu'en production.
"""

import argparse
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))
from pilotage_sp.plateforme import session_locale  # noqa: E402

NOTEBOOKS = ["00_initialisation", "01_controle_disponibilite", "02_ingestion_bronze", "03_qualite_donnees",
             "04_preparation_silver", "05_triangles", "06_provisions_sante", "07_provisions_prevoyance",
             "08_agregation_kpi", "09_controles_livraison"]


class Widgets:
    def __init__(self, valeurs):
        self.valeurs = dict(valeurs)

    def text(self, nom, defaut, libelle=None):
        self.valeurs.setdefault(nom, defaut)

    def get(self, nom):
        return str(self.valeurs[nom])


class DbUtils:
    def __init__(self, valeurs):
        self.widgets = Widgets(valeurs)


def afficher(obj, n=25):
    try:
        import pandas as pd
        if isinstance(obj, pd.DataFrame):
            with pd.option_context("display.width", 200, "display.max_columns", 20):
                print(obj.head(n).to_string())
            return
    except ImportError:
        pass
    if hasattr(obj, "show"):
        obj.show(n, truncate=False)
    else:
        print(obj)


def cellules(chemin):
    texte = chemin.read_text(encoding="utf-8")
    for bloc in texte.split("# COMMAND ----------"):
        lignes = [l for l in bloc.splitlines() if not l.startswith("# Databricks notebook source")]
        code = [l for l in lignes if l.strip()]
        if code and all(l.startswith("# MAGIC") for l in code):
            continue
        yield "\n".join(lignes)


def executer(spark, notebook, parametres, silencieux=True):
    chemin = RACINE / "notebooks" / f"{notebook}.py"
    espace = {"spark": spark, "dbutils": DbUtils(parametres), "display": (lambda *a, **k: None) if silencieux else afficher,
              "__name__": "__notebook__"}
    os.chdir(chemin.parent)
    for i, code in enumerate(cellules(chemin)):
        exec(compile(code, f"{notebook}[cellule {i}]", "exec"), espace)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exercices", nargs="*", type=int, default=[2020, 2021, 2022, 2023, 2024, 2025])
    parser.add_argument("--notebooks", nargs="*", default=None)
    parser.add_argument("--verbeux", action="store_true")
    args = parser.parse_args()
    spark = session_locale(RACINE)
    spark.sparkContext.setLogLevel("ERROR")
    spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
    choix = [n for n in NOTEBOOKS if args.notebooks is None or n[:2] in args.notebooks]
    for exercice in args.exercices:
        for nb in choix:
            t = time.time()
            executer(spark, nb, {"catalog": "local", "exercice": exercice}, silencieux=not args.verbeux)
            print(f"[{exercice}] {nb:<28} {time.time() - t:6.1f} s", flush=True)


if __name__ == "__main__":
    main()
