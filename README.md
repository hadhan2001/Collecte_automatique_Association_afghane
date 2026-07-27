# Associations afghanes en France

Ce projet collecte des associations et collectifs afghans ou aidant les Afghans en France, puis affiche les résultats dans une interface Streamlit.

## Installation

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Lancer la collecte

```bat
python collecte_associations.py
```

## Afficher le nom des associations dans la colonne URL web

Pour une base déjà créée, lance une seule fois :

```bat
python creer_noms_associations.py
```

Ce script crée :

```text
data/noms_associations.json
```

La base SQLite n’est pas modifiée.

## Lancer l’interface

```bat
python -m streamlit run app.py
```

Dans la colonne **URL web**, le nom de l’association est affiché à la place de « Ouvrir le site ».

Le nom reste cliquable et ouvre le site correspondant.

## Fichiers générés

```text
data/associations_afghanistan_france.db
data/associations_afghanistan_france.csv
data/impact_scores.json
data/noms_associations.json
data/resultats_google_bruts.csv
```

