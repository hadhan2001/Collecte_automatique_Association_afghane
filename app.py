from __future__ import annotations

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
TAGS_JSON = Path("data/tags_associations.json")

st.set_page_config(
    page_title="Associations Afghanistan – France",
    page_icon="🔎",
    layout="wide",
)

st.title("Associations œuvrant pour l’Afghanistan et les Afghans en France")
st.caption(
    "Les résultats ont été filtrés pour conserver les associations, ONG, "
    "fondations, collectifs ou organisations ayant un lien clair avec "
    "l’Afghanistan, la France et une action associative identifiable."
)


def charger_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def nom_depuis_url(url):
    try:
        domaine = urlparse(str(url)).netloc.lower().removeprefix("www.")
        partie = re.sub(r"[-_]+", " ", domaine.split(".")[0])
        return partie.title() or "Association"
    except Exception:
        return "Association"


def url_http_valide(url):
    valeur = str(url or "").strip()
    try:
        parties = urlparse(valeur)
        return valeur if parties.scheme in ("http", "https") and parties.netloc else ""
    except Exception:
        return ""


def texte_html(valeur):
    return "" if pd.isna(valeur) else html.escape(str(valeur))


def badges_html(type_organisme, tags):
    badges = []
    if type_organisme:
        badges.append(f"<span class='badge badge-type'>{html.escape(type_organisme)}</span>")
    for tag in tags:
        badges.append(f"<span class='badge'>{html.escape(tag)}</span>")
    return " ".join(badges)


def creer_tableau_html(dataframe):
    lignes = [
        '<div class="table-wrapper">',
        '<table class="associations-table">',
        '<thead><tr><th>Rang</th><th>URL web</th><th>Fondateur ou auteur</th>',
        '<th>Date de création</th><th>Siège ou lieu</th>',
        '<th>Enjeux de l’association</th></tr></thead><tbody>',
    ]

    for rang, (_, ligne) in enumerate(dataframe.iterrows(), start=1):
        url = url_http_valide(ligne.get("url_web", ""))
        nom = texte_html(ligne.get("_nom_association", "Association"))
        lien = (
            f'<a href="{html.escape(url, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer">{nom}</a>' if url else nom
        )
        badges = badges_html(
            str(ligne.get("_type_organisme", "")),
            ligne.get("_tags", []) if isinstance(ligne.get("_tags", []), list) else [],
        )
        cellule_url = f"{lien}<div class='badges'>{badges}</div>"

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

    lignes.extend(["</tbody></table></div>"])
    return "".join(lignes)


if not BASE_SQLITE.exists():
    st.error(
        "La base n’existe pas. Lance `python collecte_associations.py` "
        "ou copie une base existante dans le dossier `data`."
    )
    st.stop()

connexion = sqlite3.connect(BASE_SQLITE)
tableau = pd.read_sql_query("SELECT * FROM associations", connexion)
connexion.close()

scores = charger_json(SCORES_JSON)
noms = charger_json(NOMS_JSON)
metadonnees = charger_json(TAGS_JSON)

tableau["_score"] = tableau["url_web"].map(
    lambda url: scores.get(url, {}).get("score_impact", 0)
)
tableau["_nom_association"] = tableau["url_web"].map(
    lambda url: noms.get(url) or nom_depuis_url(url)
)
tableau["_type_organisme"] = tableau["url_web"].map(
    lambda url: metadonnees.get(url, {}).get("type_organisme", "non distingué")
)
tableau["_tags"] = tableau["url_web"].map(
    lambda url: metadonnees.get(url, {}).get("tags", ["non distingué"])
)

tableau = tableau.sort_values("_score", ascending=False).reset_index(drop=True)

tous_types = sorted({str(x) for x in tableau["_type_organisme"] if str(x)})
tous_tags = sorted({tag for tags in tableau["_tags"] for tag in tags})

st.sidebar.header("Filtres")
selection_types = st.sidebar.multiselect("Type d’organisme", tous_types)
selection_tags = st.sidebar.multiselect("Thématiques", tous_tags)
mode_tags = st.sidebar.radio(
    "Correspondance des thématiques",
    ["Au moins une", "Toutes"],
    horizontal=True,
)

recherche = st.text_input(
    "Rechercher",
    placeholder="Nom, ville, fondateur, mission, partenaire, thématique…",
)

if selection_types:
    tableau = tableau[tableau["_type_organisme"].isin(selection_types)]

if selection_tags:
    if mode_tags == "Toutes":
        tableau = tableau[
            tableau["_tags"].map(lambda tags: all(tag in tags for tag in selection_tags))
        ]
    else:
        tableau = tableau[
            tableau["_tags"].map(lambda tags: any(tag in tags for tag in selection_tags))
        ]

if recherche:
    recherche_min = recherche.lower()
    masque = tableau.apply(
        lambda ligne: recherche_min in " ".join([
            str(ligne.get("_nom_association", "")),
            str(ligne.get("_type_organisme", "")),
            " ".join(ligne.get("_tags", [])),
            str(ligne.get("url_web", "")),
            str(ligne.get("fondateur_ou_auteur", "")),
            str(ligne.get("date_de_creation", "")),
            str(ligne.get("siege_ou_lieu", "")),
            str(ligne.get("enjeux_de_l_association", "")),
        ]).lower(),
        axis=1,
    )
    tableau = tableau[masque]

tableau = tableau.reset_index(drop=True)
st.write(f"{len(tableau)} résultat(s)")

st.markdown("""
<style>
.table-wrapper { width:100%; overflow-x:auto; border:1px solid rgba(128,128,128,.28); border-radius:8px; }
.associations-table { width:100%; min-width:1250px; border-collapse:collapse; font-size:.93rem; }
.associations-table th,.associations-table td { padding:10px 12px; border-bottom:1px solid rgba(128,128,128,.22); text-align:left; vertical-align:top; }
.associations-table th { background:var(--secondary-background-color); }
.associations-table tr:hover td { background:rgba(128,128,128,.07); }
.rang { width:55px; text-align:center!important; font-weight:600; }
.url-association { min-width:260px; font-weight:700; }
.url-association a { text-decoration:none; }
.url-association a:hover { text-decoration:underline; }
.badges { margin-top:7px; line-height:1.9; font-weight:400; }
.badge { display:inline-block; padding:1px 7px; margin:1px 3px 1px 0; border-radius:999px; background:rgba(128,128,128,.16); font-size:.76rem; }
.badge-type { font-weight:650; border:1px solid rgba(128,128,128,.32); }
</style>
""", unsafe_allow_html=True)

st.markdown(creer_tableau_html(tableau), unsafe_allow_html=True)

colonnes_base = [
    "url_web", "fondateur_ou_auteur", "date_de_creation",
    "siege_ou_lieu", "enjeux_de_l_association",
]
affichage_csv = tableau[colonnes_base]
st.download_button(
    "Télécharger les cinq colonnes de la base",
    data=affichage_csv.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
    file_name="associations_afghanistan_france.csv",
    mime="text/csv",
)

avec_tags = tableau[colonnes_base].copy()
avec_tags.insert(1, "nom_association", tableau["_nom_association"])
avec_tags["type_organisme"] = tableau["_type_organisme"]
avec_tags["tags"] = tableau["_tags"].map(lambda tags: " | ".join(tags))
st.download_button(
    "Télécharger les résultats avec les tags",
    data=avec_tags.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
    file_name="associations_afghanistan_france_avec_tags.csv",
    mime="text/csv",
)
