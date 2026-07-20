import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


BASE_SQLITE = Path("data/associations_afghanistan_france.db")
SCORES_JSON = Path("data/impact_scores.json")

st.set_page_config(
    page_title="Associations Afghanistan – France",
    page_icon="🔎",
    layout="wide",
)

st.title("Associations œuvrant pour l’Afghanistan et les Afghans en France")
st.caption(
    "Les résultats sont classés par impact estimé : position Google, "
    "présence dans plusieurs recherches et vues/abonnés lorsqu’ils sont publics."
)

if not BASE_SQLITE.exists():
    st.error(
        "La base n’existe pas encore. Lance d’abord : "
        "`python collecte_associations.py`"
    )
    st.stop()

connexion = sqlite3.connect(BASE_SQLITE)
tableau = pd.read_sql_query("SELECT * FROM associations", connexion)
connexion.close()

scores = {}
if SCORES_JSON.exists():
    scores = json.loads(SCORES_JSON.read_text(encoding="utf-8"))

tableau["_score"] = tableau["url_web"].map(
    lambda url: scores.get(url, {}).get("score_impact", 0)
)
tableau = tableau.sort_values("_score", ascending=False).reset_index(drop=True)
tableau.index = tableau.index + 1

recherche = st.text_input(
    "Rechercher",
    placeholder="Nom, ville, fondateur, mission, partenaire...",
)

if recherche:
    masque = tableau.astype(str).apply(
        lambda colonne: colonne.str.contains(
            recherche,
            case=False,
            na=False,
            regex=False,
        )
    ).any(axis=1)

    tableau = tableau[masque]

st.write(f"{len(tableau)} résultat(s)")

affichage = tableau.drop(columns=["_score"])
st.dataframe(
    affichage,
    use_container_width=True,
    hide_index=False,
    column_config={
        "url_web": st.column_config.LinkColumn(
            "URL web",
            display_text="Ouvrir le site",
        ),
        "fondateur_ou_auteur": "Fondateur ou auteur",
        "date_de_creation": "Date de création",
        "siege_ou_lieu": "Siège ou lieu",
        "enjeux_de_l_association": "Enjeux de l’association",
    },
)

csv = affichage.to_csv(
    index=False,
    encoding="utf-8-sig",
).encode("utf-8-sig")

st.download_button(
    "Télécharger les résultats",
    data=csv,
    file_name="associations_afghanistan_france.csv",
    mime="text/csv",
)
