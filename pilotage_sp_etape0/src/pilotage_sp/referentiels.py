"""Chargement et validation des tables biometriques de reference.

Conventions verifiees a l'import (et non supposees) :
- maintien en incapacite BCAC : ages d'entree 20 a 65, anciennete 0 a 35 en MOIS, lx pour 10 000 entrees ;
- passage incapacite vers invalidite BCAC : ages 20 a 62, anciennete 0 a 35 en MOIS, nombre de passages
  au cours du mois pour 10 000 entrees en incapacite (au mois 35, tous les maintenus passent) ;
- maintien en invalidite BCAC : ages d'entree 20 a 64, anciennete 0 a 45 en ANNEES ;
- mortalite TH00-02 / TF00-02 : ages 0 a 120, lx et qx.

Confondre mois et annees sur le maintien en invalidite diviserait la provision par
un facteur voisin de douze : les plages sont donc controlees.

Les fonctions acceptent soit un repertoire de CSV (execution locale, generation),
soit des DataFrame pandas deja lus (execution Databricks depuis les tables ref).
"""

from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

FICHIERS = {
    "incapacite": "bcac_maintien_incapacite.csv",
    "passage": "bcac_passage_invalidite.csv",
    "invalidite": "bcac_maintien_invalidite.csv",
    "mortalite_H": "mortalite_TH0002.csv",
    "mortalite_F": "mortalite_TF0002.csv",
}


@dataclass
class TablesBiometriques:
    age_min_inc: int
    lx_inc: np.ndarray        # [age - age_min_inc, mois 0..36], colonne 36 = 0
    age_min_pas: int
    nb_pas: np.ndarray        # [age - age_min_pas, mois 0..35]
    age_min_inv: int
    lx_inv_annuel: np.ndarray  # [age - age_min_inv, annee 0..45]
    qx: dict                  # {"H": array[0..120], "F": array[0..120]}

    # ------------------------------------------------------------ acces bornes
    def ligne_incapacite(self, ages):
        a = np.clip(np.asarray(ages, dtype=int), self.age_min_inc, self.age_min_inc + self.lx_inc.shape[0] - 1)
        return self.lx_inc[a - self.age_min_inc]

    def ligne_passage(self, ages):
        """Passages ; au-dela de 62 ans la table ne prevoit pas de passage (fin de droits a la retraite)."""
        ages = np.asarray(ages, dtype=int)
        a = np.clip(ages, self.age_min_pas, self.age_min_pas + self.nb_pas.shape[0] - 1)
        lignes = self.nb_pas[a - self.age_min_pas].copy()
        lignes[ages > self.age_min_pas + self.nb_pas.shape[0] - 1] = 0.0
        return lignes

    def lx_invalidite_mensuel(self, age, nb_mois):
        """lx de maintien en invalidite interpole lineairement au pas mensuel."""
        a = int(np.clip(age, self.age_min_inv, self.age_min_inv + self.lx_inv_annuel.shape[0] - 1))
        valeurs = self.lx_inv_annuel[a - self.age_min_inv]
        annees = np.arange(len(valeurs), dtype=float)
        mois = np.arange(nb_mois + 1, dtype=float) / 12.0
        return np.interp(mois, annees, valeurs, right=0.0)


def _lire(source, cle):
    if isinstance(source, dict):
        return source[cle].copy()
    return pd.read_csv(Path(source) / FICHIERS[cle], sep=";")


def _pivot(df, col_age, col_duree, col_valeur):
    t = df.pivot(index=col_age, columns=col_duree, values=col_valeur).sort_index()
    t = t.reindex(sorted(t.columns), axis=1)
    return int(t.index.min()), t.to_numpy(dtype=float), (int(t.index.max()), int(max(t.columns)))


def charger_tables(source):
    """Charge et controle les tables. `source` : repertoire ou dict de DataFrame."""
    age_inc, lx_inc, bornes_inc = _pivot(_lire(source, "incapacite"), "age_entree", "anciennete_mois", "lx")
    age_pas, nb_pas, bornes_pas = _pivot(_lire(source, "passage"), "age_entree", "anciennete_mois", "nb_passages")
    age_inv, lx_inv, bornes_inv = _pivot(_lire(source, "invalidite"), "age_entree", "anciennete_annees", "lx")

    anomalies = []
    if (age_inc, bornes_inc) != (20, (65, 35)):
        anomalies.append(f"maintien incapacite : plage {age_inc}-{bornes_inc}")
    if (age_pas, bornes_pas) != (20, (62, 35)):
        anomalies.append(f"passage : plage {age_pas}-{bornes_pas}")
    if (age_inv, bornes_inv) != (20, (64, 45)):
        anomalies.append(f"maintien invalidite : plage {age_inv}-{bornes_inv}")
    if not (np.diff(lx_inc, axis=1) <= 1e-6).all():
        anomalies.append("lx incapacite non decroissants")
    if not (np.diff(lx_inv, axis=1) <= 1e-6).all():
        anomalies.append("lx invalidite non decroissants")
    # Coherence passage / maintien : les passages d'un mois ne peuvent exceder les sorties du mois
    # (tolerance de 10 % : les deux lois sont lissees separement par le BCAC).
    lx_c = np.concatenate([lx_inc, np.zeros((lx_inc.shape[0], 1))], axis=1)[: nb_pas.shape[0]]
    sorties = lx_c[:, :-1] - lx_c[:, 1:]
    if (nb_pas > sorties * 1.10 + 1.0).any():
        anomalies.append("passages superieurs aux sorties d'incapacite sur au moins un mois")
    if anomalies:
        raise ValueError("Tables biometriques non conformes : " + " ; ".join(anomalies))

    lx_inc = np.concatenate([lx_inc, np.zeros((lx_inc.shape[0], 1))], axis=1)
    qx = {}
    for sexe, cle in (("H", "mortalite_H"), ("F", "mortalite_F")):
        m = _lire(source, cle).set_index("age")["qx"].reindex(range(0, 121)).fillna(1.0)
        qx[sexe] = m.to_numpy(dtype=float)
    return TablesBiometriques(age_inc, lx_inc, age_pas, nb_pas, age_inv, lx_inv, qx)
