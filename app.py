import html
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st


BASE_SQLITE = Path("data/associations_afghanistan_france.db")
SCORES_JSON = Path("data/impact_scores.json")
NOMS_JSON = Path("data/noms_associations.json")

st.set_page_config(
    page_title="Associations Afghanistan – France",
    page_icon="🔎",
    layout="wide",
)

st.title("Associations œuvrant pour l’Afghanistan et les Afghans en France")
st.caption(
    "Dans la colonne « URL web », le nom de l’association est cliquable "
    "et ouvre directement son site."
)


def nom_depuis_url(url):
    """Nom de secours si aucun nom précis n'a encore été extrait."""
    try:
        domaine = urlparse(str(url)).netloc.lower().removeprefix("www.")
        partie = domaine.split(".")[0]
        partie = re.sub(r"[-_]+", " ", partie)
        return partie.title() or "Association"
    except Exception:
        return "Association"


def url_http_valide(url):
    valeur = str(url or "").strip()
    try:
        parties = urlparse(valeur)
        if parties.scheme in ("http", "https") and parties.netloc:
            return valeur
    except Exception:
        pass
    return ""


def texte_html(valeur):
    if pd.isna(valeur):
        return ""
    return html.escape(str(valeur))


def creer_tableau_html(dataframe):
    lignes = [
        '<div class="table-wrapper">',
        '<table class="associations-table">',
        "<thead><tr>",
        "<th>Rang</th>",
        "<th>URL web</th>",
        "<th>Fondateur ou auteur</th>",
        "<th>Date de création</th>",
        "<th>Siège ou lieu</th>",
        "<th>Enjeux de l’association</th>",
        "</tr></thead>",
        "<tbody>",
    ]

    for rang, (_, ligne) in enumerate(dataframe.iterrows(), start=1):
        url = url_http_valide(ligne.get("url_web", ""))
        nom = texte_html(ligne.get("_nom_association", "Association"))

        if url:
            cellule_url = (
                f'<a href="{html.escape(url, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">{nom}</a>'
            )
        else:
            cellule_url = nom

        lignes.extend([
            "<tr>",
            f"<td class='rang'>{rang}</td>",
            f"<td class='url-association'>{cellule_url}</td>",
            f"<td>{texte_html(ligne.get('fondateur_ou_auteur', ''))}</td>",
            f"<td>{texte_html(ligne.get('date_de_creation', ''))}</td>",
            f"<td>{texte_html(ligne.get('siege_ou_lieu', ''))}</td>",
            f"<td>{texte_html(ligne.get('enjeux_de_l_association', ''))}</td>",
            "</tr>",
        ])

    lignes.extend(["</tbody>", "</table>", "</div>"])
    return "".join(lignes)


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

noms = {}
if NOMS_JSON.exists():
    noms = json.loads(NOMS_JSON.read_text(encoding="utf-8"))

tableau["_score"] = tableau["url_web"].map(
    lambda url: scores.get(url, {}).get("score_impact", 0)
)
tableau["_nom_association"] = tableau["url_web"].map(
    lambda url: noms.get(url) or nom_depuis_url(url)
)

tableau = tableau.sort_values(
    "_score",
    ascending=False,
).reset_index(drop=True)

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
    tableau = tableau[masque].reset_index(drop=True)

st.write(f"{len(tableau)} résultat(s)")

st.markdown(
    """
    <style>
    .table-wrapper {
        width: 100%;
        overflow-x: auto;
        border: 1px solid rgba(128, 128, 128, 0.28);
        border-radius: 8px;
    }

    .associations-table {
        width: 100%;
        min-width: 1250px;
        border-collapse: collapse;
        font-size: 0.93rem;
    }

    .associations-table th,
    .associations-table td {
        padding: 10px 12px;
        border-bottom: 1px solid rgba(128, 128, 128, 0.22);
        text-align: left;
        vertical-align: top;
    }

    .associations-table th {
        background: var(--secondary-background-color);
    }

    .associations-table tr:hover td {
        background: rgba(128, 128, 128, 0.07);
    }

    .rang {
        width: 55px;
        text-align: center !important;
        font-weight: 600;
    }

    .url-association {
        min-width: 230px;
        font-weight: 700;
    }

    .url-association a {
        text-decoration: none;
    }

    .url-association a:hover {
        text-decoration: underline;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    creer_tableau_html(tableau),
    unsafe_allow_html=True,
)

# Le téléchargement conserve exactement les cinq colonnes de la base.
affichage_csv = tableau[
    [
        "url_web",
        "fondateur_ou_auteur",
        "date_de_creation",
        "siege_ou_lieu",
        "enjeux_de_l_association",
    ]
]

csv = affichage_csv.to_csv(
    index=False,
    encoding="utf-8-sig",
).encode("utf-8-sig")

st.download_button(
    "Télécharger les résultats",
    data=csv,
    file_name="associations_afghanistan_france.csv",
    mime="text/csv",
)
