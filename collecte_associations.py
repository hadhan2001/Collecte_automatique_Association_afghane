import json
import math
import random
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options


DOSSIER_DATA = Path("data")
BASE_SQLITE = DOSSIER_DATA / "associations_afghanistan_france.db"
CSV_FINAL = DOSSIER_DATA / "associations_afghanistan_france.csv"
SCORES_JSON = DOSSIER_DATA / "impact_scores.json"
RESULTATS_BRUTS = DOSSIER_DATA / "resultats_google_bruts.csv"
FICHIER_REQUETES = Path("queries.txt")

NOMBRE_PAGES_GOOGLE = 10
PAUSE_MIN = 3
PAUSE_MAX = 6

ENTETES = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )
}

MOTS_ASSOCIATION = (
    "association", "associatif", "collectif", "fondation", "ong",
    "organisation", "afghan", "afghane", "afghans", "afghanistan",
    "réfugié", "refugie", "diaspora", "humanitaire", "solidarité",
)

MOTS_ENJEUX = (
    "mission", "objectif", "action", "activité", "projet", "aide",
    "accompagnement", "soutien", "solidarité", "intégration",
    "insertion", "culture", "éducation", "formation", "droits",
    "humanitaire", "réfugié", "partenaire", "adhère", "réseau",
    "coopération", "femme", "jeunesse", "santé",
)

PAGES_UTILES = (
    "qui-sommes-nous", "a-propos", "about", "notre-histoire",
    "association", "nos-missions", "missions", "mentions-legales",
)

DOMAINES_NON_OFFICIELS = (
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "wikipedia.org", "helloasso.com", "journal-officiel.gouv.fr",
    "data.gouv.fr", "societe.com", "pappers.fr",
)


def nettoyer_texte(texte):
    texte = "" if texte is None else str(texte)
    texte = texte.replace("\xa0", " ")
    texte = re.sub(r"\s+", " ", texte)
    return texte.strip()


def normaliser_url(url):
    url = nettoyer_texte(url)
    if not url:
        return ""

    try:
        parties = urlparse(url)
        if parties.scheme not in ("http", "https"):
            return ""

        domaine = parties.netloc.lower().replace("www.", "")
        chemin = re.sub(r"/+$", "", parties.path or "")
        return urlunparse(("https", domaine, chemin, "", "", ""))
    except Exception:
        return ""


def charger_requetes():
    if not FICHIER_REQUETES.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {FICHIER_REQUETES.resolve()}"
        )

    requetes = [
        nettoyer_texte(ligne)
        for ligne in FICHIER_REQUETES.read_text(encoding="utf-8").splitlines()
        if nettoyer_texte(ligne) and not ligne.lstrip().startswith("#")
    ]

    if not requetes:
        raise RuntimeError("Le fichier queries.txt ne contient aucune requête.")

    return requetes


def creer_navigateur():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=fr-FR")

    try:
        return webdriver.Chrome(options=options)
    except WebDriverException as erreur:
        raise RuntimeError(
            "Impossible d'ouvrir Google Chrome avec Selenium. "
            "Vérifie que Chrome est installé et que Selenium est à jour."
        ) from erreur


def extraire_resultats_google(driver, requete, page):
    debut = (page - 1) * 10
    url_google = (
        "https://www.google.com/search?"
        f"q={quote_plus(requete)}&start={debut}&num=10&hl=fr&gl=fr"
    )

    driver.get(url_google)
    time.sleep(random.uniform(PAUSE_MIN, PAUSE_MAX))

    url_courante = driver.current_url.lower()
    contenu = driver.page_source.lower()

    if "sorry/index" in url_courante or "captcha" in contenu:
        print("\nGoogle demande une vérification.")
        input(
            "Résous le CAPTCHA dans Chrome, puis appuie sur Entrée ici..."
        )
        time.sleep(2)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    blocs = soup.select("div.MjjYud")
    if not blocs:
        blocs = soup.select("div.g")

    resultats = []
    position_page = 0

    for bloc in blocs:
        titre_tag = bloc.select_one("h3")
        if not titre_tag:
            continue

        lien_tag = titre_tag.find_parent("a")
        if not lien_tag:
            continue

        lien = normaliser_url(lien_tag.get("href", ""))
        if not lien:
            continue

        domaine = urlparse(lien).netloc.lower()
        if "google." in domaine:
            continue

        position_page += 1

        extrait_tag = (
            bloc.select_one("div.VwiC3b")
            or bloc.select_one("div.IsZvec")
            or bloc.select_one("span.aCOpRe")
        )

        resultats.append({
            "requete": requete,
            "page_google": page,
            "position_page": position_page,
            "position_globale": debut + position_page,
            "titre_google": nettoyer_texte(titre_tag.get_text(" ", strip=True)),
            "url": lien,
            "description_google": nettoyer_texte(
                extrait_tag.get_text(" ", strip=True) if extrait_tag else ""
            ),
        })

    return resultats


def collecter_google():
    requetes = charger_requetes()
    navigateur = creer_navigateur()
    tous = []

    try:
        navigateur.get("https://www.google.com/")
        print(
            "\nChrome est ouvert. Accepte les cookies Google si nécessaire."
        )
        input("Quand Google est prêt, appuie sur Entrée ici...")

        for numero, requete in enumerate(requetes, start=1):
            print(f"\nRequête {numero}/{len(requetes)} : {requete}")

            for page in range(1, NOMBRE_PAGES_GOOGLE + 1):
                print(f"  Page {page}/{NOMBRE_PAGES_GOOGLE}")
                resultats = extraire_resultats_google(
                    navigateur, requete, page
                )
                tous.extend(resultats)

                pd.DataFrame(tous).to_csv(
                    RESULTATS_BRUTS,
                    index=False,
                    encoding="utf-8-sig",
                )

    finally:
        navigateur.quit()

    return pd.DataFrame(tous)


def telecharger_page(url):
    try:
        reponse = requests.get(
            url,
            headers=ENTETES,
            timeout=15,
            allow_redirects=True,
        )
        reponse.raise_for_status()

        type_contenu = reponse.headers.get("Content-Type", "")
        if "text/html" not in type_contenu:
            return "", ""

        return reponse.url, reponse.text
    except requests.RequestException:
        return "", ""


def texte_visible(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    return nettoyer_texte(soup.get_text(" ", strip=True))


def liens_pages_utiles(url_base, html):
    soup = BeautifulSoup(html, "html.parser")
    domaine = urlparse(url_base).netloc
    trouves = []

    for lien in soup.select("a[href]"):
        href = urljoin(url_base, lien.get("href", ""))
        texte = nettoyer_texte(lien.get_text(" ", strip=True)).lower()
        chemin = urlparse(href).path.lower()

        if urlparse(href).netloc != domaine:
            continue

        if any(mot in texte or mot in chemin for mot in PAGES_UTILES):
            normalisee = normaliser_url(href)
            if normalisee and normalisee not in trouves:
                trouves.append(normalisee)

    return trouves[:4]


def est_probablement_association(titre, extrait, texte):
    ensemble = f"{titre} {extrait} {texte[:5000]}".lower()
    points = sum(1 for mot in MOTS_ASSOCIATION if mot in ensemble)
    return points >= 2


def extraire_fondateur(texte, html):
    motifs = [
        r"(?:fondée|fondé|créée|créé)\s+(?:en\s+\d{4}\s+)?par\s+([^.;:]{3,100})",
        r"(?:fondateur|fondatrice|cofondateur|cofondatrice)\s*[:\-]\s*([^.;:]{3,100})",
        r"(?:à l'initiative de|a l'initiative de)\s+([^.;:]{3,100})",
    ]

    for motif in motifs:
        resultat = re.search(motif, texte, flags=re.IGNORECASE)
        if resultat:
            return nettoyer_texte(resultat.group(1))

    soup = BeautifulSoup(html, "html.parser")
    auteur = (
        soup.select_one('meta[name="author"]')
        or soup.select_one('meta[property="article:author"]')
    )
    if auteur and auteur.get("content"):
        return nettoyer_texte(auteur.get("content"))

    return "Non trouvé automatiquement"


def extraire_date_creation(texte):
    motifs = [
        r"(?:fondée|fondé|créée|créé|naissance|depuis)\s+(?:le\s+)?"
        r"(\d{1,2}\s+[a-zéû]+\s+\d{4})",
        r"(?:fondée|fondé|créée|créé|depuis)\s+(?:en\s+)?((?:19|20)\d{2})",
        r"(?:date de création|date de creation)\s*[:\-]\s*([^.;]{4,40})",
    ]

    for motif in motifs:
        resultat = re.search(motif, texte, flags=re.IGNORECASE)
        if resultat:
            return nettoyer_texte(resultat.group(1))

    return "Non trouvée automatiquement"


def extraire_siege(texte, html):
    soup = BeautifulSoup(html, "html.parser")

    adresse = soup.select_one("address")
    if adresse:
        valeur = nettoyer_texte(adresse.get_text(" ", strip=True))
        if valeur:
            return valeur[:180]

    motifs = [
        r"(?:siège social|siege social|siège|siege)\s*[:\-]?\s*([^.;]{5,180})",
        r"(\d{1,4}\s+[^.;]{3,80}\s+\d{5}\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÿ\- ]{2,40})",
    ]

    for motif in motifs:
        resultat = re.search(motif, texte, flags=re.IGNORECASE)
        if resultat:
            return nettoyer_texte(resultat.group(1))[:180]

    return "Non trouvé automatiquement"


def extraire_enjeux(texte):
    phrases = re.split(r"(?<=[.!?])\s+", texte)
    retenues = []

    for phrase in phrases:
        phrase_propre = nettoyer_texte(phrase)
        phrase_min = phrase_propre.lower()

        if (
            35 <= len(phrase_propre) <= 350
            and any(mot in phrase_min for mot in MOTS_ENJEUX)
        ):
            retenues.append(phrase_propre)

        if len(retenues) == 3:
            break

    if retenues:
        return " ".join(retenues)[:900]

    return "Non trouvés automatiquement"


def nombre_public(texte):
    motif = (
        r"(\d[\d\s.,]*)\s*([kKmM]?)\s*"
        r"(?:vues|abonnés|abonnes|followers)"
    )
    valeurs = []

    for nombre, unite in re.findall(motif, texte, flags=re.IGNORECASE):
        valeur_texte = nombre.replace(" ", "").replace(",", ".")
        try:
            valeur = float(valeur_texte)
        except ValueError:
            continue

        if unite.lower() == "k":
            valeur *= 1_000
        elif unite.lower() == "m":
            valeur *= 1_000_000

        valeurs.append(int(valeur))

    return max(valeurs) if valeurs else 0


def calculer_scores(resultats):
    par_url = defaultdict(list)

    for ligne in resultats.to_dict("records"):
        par_url[ligne["url"]].append(ligne)

    scores = {}

    for url, occurrences in par_url.items():
        meilleure_position = min(
            int(ligne["position_globale"]) for ligne in occurrences
        )
        requetes_distinctes = len({
            ligne["requete"] for ligne in occurrences
        })

        signal_public = 0
        for ligne in occurrences:
            signal_public = max(
                signal_public,
                nombre_public(
                    f"{ligne['titre_google']} "
                    f"{ligne['description_google']}"
                ),
            )

        score_position = max(1, 101 - meilleure_position)
        bonus_requetes = min(20, (requetes_distinctes - 1) * 4)
        bonus_public = min(
            15,
            round(math.log10(signal_public + 1) * 3, 2)
            if signal_public else 0,
        )

        domaine = urlparse(url).netloc.lower()
        bonus_site = 0 if any(
            domaine.endswith(d) for d in DOMAINES_NON_OFFICIELS
        ) else 5

        score = min(
            100,
            round(
                score_position * 0.65
                + bonus_requetes
                + bonus_public
                + bonus_site,
                2,
            ),
        )

        scores[url] = {
            "score_impact": score,
            "meilleure_position_google": meilleure_position,
            "nombre_requetes": requetes_distinctes,
            "vues_ou_abonnes_publics": signal_public,
        }

    return scores


def enrichir(resultats, scores):
    lignes_finales = []
    urls_traitees = set()

    urls_ordonnees = sorted(
        scores,
        key=lambda url: scores[url]["score_impact"],
        reverse=True,
    )

    infos_google = {
        url: resultats[resultats["url"] == url].iloc[0].to_dict()
        for url in urls_ordonnees
    }

    for numero, url in enumerate(urls_ordonnees, start=1):
        if url in urls_traitees:
            continue
        urls_traitees.add(url)

        info = infos_google[url]
        print(
            f"\nEnrichissement {numero}/{len(urls_ordonnees)} : {url}"
        )

        url_finale, html = telecharger_page(url)
        if not html:
            continue

        texte = texte_visible(html)

        if not est_probablement_association(
            info["titre_google"],
            info["description_google"],
            texte,
        ):
            continue

        textes = [texte]
        htmls = [html]

        for page_utile in liens_pages_utiles(url_finale, html):
            _, html_utile = telecharger_page(page_utile)
            if html_utile:
                textes.append(texte_visible(html_utile))
                htmls.append(html_utile)
                time.sleep(0.5)

        texte_total = nettoyer_texte(" ".join(textes))
        html_total = "\n".join(htmls)

        lignes_finales.append({
            "url_web": normaliser_url(url_finale) or url,
            "fondateur_ou_auteur": extraire_fondateur(
                texte_total, html_total
            ),
            "date_de_creation": extraire_date_creation(texte_total),
            "siege_ou_lieu": extraire_siege(texte_total, html_total),
            "enjeux_de_l_association": extraire_enjeux(texte_total),
        })

    return lignes_finales


def enregistrer_base(lignes, scores):
    DOSSIER_DATA.mkdir(parents=True, exist_ok=True)

    def score_ligne(ligne):
        url = normaliser_url(ligne["url_web"])
        return scores.get(url, {}).get("score_impact", 0)

    lignes = sorted(lignes, key=score_ligne, reverse=True)
    tableau = pd.DataFrame(lignes, columns=[
        "url_web",
        "fondateur_ou_auteur",
        "date_de_creation",
        "siege_ou_lieu",
        "enjeux_de_l_association",
    ])

    tableau.to_csv(
        CSV_FINAL,
        index=False,
        encoding="utf-8-sig",
    )

    connexion = sqlite3.connect(BASE_SQLITE)
    connexion.execute("DROP TABLE IF EXISTS associations")
    connexion.execute("""
        CREATE TABLE associations (
            url_web TEXT PRIMARY KEY,
            fondateur_ou_auteur TEXT,
            date_de_creation TEXT,
            siege_ou_lieu TEXT,
            enjeux_de_l_association TEXT
        )
    """)

    tableau.to_sql(
        "associations",
        connexion,
        if_exists="append",
        index=False,
    )
    connexion.commit()
    connexion.close()

    scores_finaux = {
        normaliser_url(ligne["url_web"]): scores.get(
            normaliser_url(ligne["url_web"]), {}
        )
        for ligne in lignes
    }

    SCORES_JSON.write_text(
        json.dumps(
            scores_finaux,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nTerminé.")
    print(f"Base SQLite : {BASE_SQLITE.resolve()}")
    print(f"CSV : {CSV_FINAL.resolve()}")
    print(f"Scores internes : {SCORES_JSON.resolve()}")


def main():
    DOSSIER_DATA.mkdir(parents=True, exist_ok=True)

    print("Collecte des 10 premières pages Google...")
    resultats = collecter_google()

    if resultats.empty:
        raise RuntimeError("Aucun résultat Google n'a été récupéré.")

    scores = calculer_scores(resultats)
    lignes = enrichir(resultats, scores)
    enregistrer_base(lignes, scores)


if __name__ == "__main__":
    main()
