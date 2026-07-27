import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_SQLITE = Path("data/associations_afghanistan_france.db")
NOMS_JSON = Path("data/noms_associations.json")
RESULTATS_BRUTS = Path("data/resultats_google_bruts.csv")

ENTETES = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )
}


def nettoyer_texte(texte):
    texte = "" if texte is None else str(texte)
    texte = texte.replace("\xa0", " ")
    return re.sub(r"\s+", " ", texte).strip()


def nom_depuis_domaine(url):
    domaine = urlparse(url).netloc.lower().replace("www.", "")
    partie = domaine.split(".")[0]
    partie = re.sub(r"[-_]+", " ", partie)
    return partie.title() or "Association"


def telecharger(url):
    try:
        reponse = requests.get(
            url,
            headers=ENTETES,
            timeout=18,
            allow_redirects=True,
        )
        reponse.raise_for_status()

        if "text/html" not in reponse.headers.get("Content-Type", ""):
            return ""

        return reponse.text
    except requests.RequestException:
        return ""


def extraire_nom(html, titre_google, url):
    soup = BeautifulSoup(html, "html.parser")

    generiques = {
        "accueil", "home", "bienvenue", "welcome", "association",
        "collectif", "site officiel", "official website", "contact",
        "qui sommes-nous", "à propos", "a propos",
    }

    def propre(nom):
        nom = nettoyer_texte(nom)
        if not nom:
            return ""

        nom = re.sub(
            r"\s*[\-|–—|]\s*"
            r"(accueil|home|site officiel|official website|qui sommes-nous|"
            r"à propos|a propos|contact)\s*$",
            "",
            nom,
            flags=re.IGNORECASE,
        ).strip()

        if not (2 <= len(nom) <= 160):
            return ""

        if nom.lower().strip(" .:-") in generiques:
            return ""

        return nom

    def parcourir_json(objet):
        if isinstance(objet, dict):
            type_objet = objet.get("@type", "")
            types = (
                [str(x).lower() for x in type_objet]
                if isinstance(type_objet, list)
                else [str(type_objet).lower()]
            )

            if any(
                valeur in {
                    "organization",
                    "ngo",
                    "nonprofitorganization",
                    "foundation",
                }
                for valeur in types
            ):
                nom = propre(objet.get("name", ""))
                if nom:
                    return nom

            for valeur in objet.values():
                nom = parcourir_json(valeur)
                if nom:
                    return nom

        elif isinstance(objet, list):
            for element in objet:
                nom = parcourir_json(element)
                if nom:
                    return nom

        return ""

    for script in soup.select('script[type="application/ld+json"]'):
        contenu = script.string or script.get_text()
        try:
            donnees = json.loads(contenu)
        except (json.JSONDecodeError, TypeError):
            continue

        nom = parcourir_json(donnees)
        if nom:
            return nom

    for selecteur in (
        'meta[property="og:site_name"]',
        'meta[name="application-name"]',
        'meta[name="apple-mobile-web-app-title"]',
    ):
        balise = soup.select_one(selecteur)
        if balise and balise.get("content"):
            nom = propre(balise.get("content"))
            if nom:
                return nom

    for h1 in soup.select("h1"):
        nom = propre(h1.get_text(" ", strip=True))
        if nom:
            return nom

    if soup.title:
        nom = propre(soup.title.get_text(" ", strip=True))
        if nom:
            return nom

    nom = propre(titre_google)
    return nom or nom_depuis_domaine(url)


def charger_titres_google():
    if not RESULTATS_BRUTS.exists():
        return {}

    tableau = pd.read_csv(RESULTATS_BRUTS)

    if not {"url", "titre_google"}.issubset(tableau.columns):
        return {}

    return (
        tableau.dropna(subset=["url"])
        .drop_duplicates(subset=["url"])
        .set_index("url")["titre_google"]
        .fillna("")
        .to_dict()
    )


def main():
    if not BASE_SQLITE.exists():
        raise FileNotFoundError(
            f"Base introuvable : {BASE_SQLITE.resolve()}"
        )

    connexion = sqlite3.connect(BASE_SQLITE)
    urls = [
        ligne[0]
        for ligne in connexion.execute(
            "SELECT url_web FROM associations"
        ).fetchall()
    ]
    connexion.close()

    titres = charger_titres_google()
    noms_existants = {}

    if NOMS_JSON.exists():
        noms_existants = json.loads(
            NOMS_JSON.read_text(encoding="utf-8")
        )

    for numero, url in enumerate(urls, start=1):
        if noms_existants.get(url):
            print(
                f"{numero}/{len(urls)} déjà renseigné : "
                f"{noms_existants[url]}"
            )
            continue

        print(f"{numero}/{len(urls)} recherche du nom : {url}")
        contenu = telecharger(url)
        nom = extraire_nom(
            contenu,
            titres.get(url, ""),
            url,
        )
        noms_existants[url] = nom
        print(f"  -> {nom}")

    NOMS_JSON.write_text(
        json.dumps(
            noms_existants,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nTerminé.")
    print(f"Noms enregistrés : {NOMS_JSON.resolve()}")
    print("La base SQLite n'a pas été modifiée.")


if __name__ == "__main__":
    main()
