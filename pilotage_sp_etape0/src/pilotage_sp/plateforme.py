"""Abstraction d'execution : Databricks (Unity Catalog, Delta, volumes) ou poste local (Spark local, parquet, repertoires).

Le code des notebooks est identique dans les deux cas ; seules les fonctions de ce module different.
"""

import os
from pathlib import Path

SCHEMAS = ("landing", "bronze", "silver", "gold", "ops", "ref")


def est_databricks():
    return "DATABRICKS_RUNTIME_VERSION" in os.environ


class Contexte:
    def __init__(self, spark, catalog, exercice, racine_depot=None):
        self.spark = spark
        self.exercice = int(exercice)
        self.databricks = est_databricks()
        self.catalog = catalog if self.databricks else "spark_catalog"
        self.racine = Path(racine_depot) if racine_depot else Path(__file__).resolve().parents[2]
        self.format = "delta" if self.databricks else "parquet"

    # ------------------------------------------------------------------ noms et chemins
    def table(self, schema, nom):
        return f"{self.catalog}.{schema}.{nom}"

    def chemin_landing(self, exercice=None):
        n = exercice or self.exercice
        if self.databricks:
            return f"/Volumes/{self.catalog}/landing/raw/exercice={n}"
        return str(self.racine / "data" / "raw" / f"exercice={n}")

    def chemin_livraison(self, exercice=None):
        n = exercice or self.exercice
        if self.databricks:
            return f"/Volumes/{self.catalog}/gold/livraison/exercice={n}"
        p = self.racine / "livraison" / f"exercice={n}"
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    def chemin_referentiels(self):
        return str(self.racine / "data" / "referentiels")

    # ------------------------------------------------------------------ ecriture idempotente
    def creer_schemas(self):
        for s in SCHEMAS:
            self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS {self.catalog}.{s}")
        if self.databricks:
            self.spark.sql(f"CREATE VOLUME IF NOT EXISTS {self.catalog}.landing.raw")
            self.spark.sql(f"CREATE VOLUME IF NOT EXISTS {self.catalog}.gold.livraison")

    def ecrire(self, df, schema, nom, partition="exercice"):
        """Remplace la partition de l'exercice (rejouable), ou toute la table si `partition` est None."""
        cible = self.table(schema, nom)
        existe = self.spark.catalog.tableExists(cible)
        if partition is None:
            df.write.format(self.format).mode("overwrite").option("overwriteSchema", "true").saveAsTable(cible)
            return cible
        valeurs = [r[0] for r in df.select(partition).distinct().collect()]
        if not existe:
            df.write.format(self.format).mode("overwrite").partitionBy(partition).saveAsTable(cible)
        elif self.databricks:
            condition = " OR ".join(f"{partition} = {v}" for v in valeurs) or "1 = 0"
            df.write.format("delta").mode("overwrite").option("replaceWhere", condition).saveAsTable(cible)
        else:
            self.spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
            colonnes = self.spark.table(cible).columns
            df.select(*colonnes).write.mode("overwrite").insertInto(cible)
        return cible

    def journaliser(self, etape, statut, message=""):
        """Trace d'execution (ops.journal_etapes, ajout seul)."""
        import datetime as dt
        ligne = [(self.exercice, etape, statut, str(message)[:2000], dt.datetime.utcnow().isoformat(timespec="seconds"))]
        df = self.spark.createDataFrame(ligne, "exercice int, etape string, statut string, message string, horodatage_utc string")
        df.write.format(self.format).mode("append").saveAsTable(self.table("ops", "journal_etapes"))

    def ecrire_pandas(self, pdf, schema, nom, partition="exercice"):
        import pandas as pd
        pdf = pdf.copy()
        for c in pdf.columns:
            t = pdf[c].dtype
            if pd.api.types.is_bool_dtype(t):
                pdf[c] = pdf[c].astype(bool)
            elif pd.api.types.is_integer_dtype(t) and str(t)[0] == "I":
                pdf[c] = pdf[c].astype("float64")
            elif pd.api.types.is_datetime64_any_dtype(t):
                pdf[c] = pd.to_datetime(pdf[c])
            elif not pd.api.types.is_numeric_dtype(t):
                pdf[c] = pdf[c].astype(object).where(pdf[c].notna(), None).map(lambda v: v if v is None else str(v))
        return self.ecrire(self.spark.createDataFrame(pdf), schema, nom, partition)

    def lire(self, schema, nom, jusqu_a=None, exercice=None):
        df = self.spark.table(self.table(schema, nom))
        if exercice is not None:
            df = df.where(f"exercice = {int(exercice)}")
        elif jusqu_a is not None:
            df = df.where(f"exercice <= {int(jusqu_a)}")
        return df


def session_locale(racine):
    """SparkSession locale (tests et execution hors Databricks) avec metastore persistant dans le depot."""
    from pyspark.sql import SparkSession
    entrepot = Path(racine) / ".spark-warehouse"
    return (SparkSession.builder.master("local[4]").appName("pilotage_sp")
            .config("spark.sql.warehouse.dir", str(entrepot))
            .config("spark.sql.catalogImplementation", "hive")
            .config("javax.jdo.option.ConnectionURL", f"jdbc:derby:;databaseName={entrepot}/metastore_db;create=true")
            .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.driver.memory", "4g")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.ui.enabled", "false")
            .getOrCreate())
