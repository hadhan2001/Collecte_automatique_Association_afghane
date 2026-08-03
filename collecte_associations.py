from __future__ import annotations

import json
import math
import random
import re
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options

from noms_associations import extraire_nom


DOSSIER_DATA = Path("data")
BASE_SQLITE = DOSSIER_DATA / "associations_afghanistan_france.db"
CSV_FINAL = DOSSIER_DATA / "associations_afghanistan_france.csv"
SCORES_JSON = DOSSIER_DATA / "impact_scores.json"
TAGS_JSON = DOSSIER_DATA / "tags_associations.json"
NOMS_JSON = DOSSIER_DATA / "noms_associations.json"
RESULTATS_BRUTS = DOSSIER_DATA / "resultats_google_bruts.csv"
JOURNAL_FILTRAGE = DOSSIER_DATA / "journal_filtrage.csv"
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

# ------------------------------------------------------------------
# FILTRES STRICTS
# ------------------------------------------------------------------
MOTS_TYPE_ORGANISME = {
    "association": (
        "association", "associatif", "association loi 1901",
        "association à but non lucratif", "association a but non lucratif",
    ),
    "ONG": (
        "ong", "organisation non gouvernementale",
        "non-governmental organization", "non governmental organization",
    ),
    "fondation": (
        "fondation", "foundation",
    ),
    "collectif": (
        "collectif", "collective",
    ),
    "organisation": (
        "organisation", "organization", "organisme à but non lucratif",
        "organisme a but non lucratif", "nonprofit", "non-profit",
    ),
}

MOTS_AFGHANISTAN = (
    "afghanistan", "afghan", "afghane", "afghans", "afghanes",
    "kaboul", "kabul", "diaspora afghane", "réfugiés afghans",
    "refugies afghans", "afghan refugees",
)

MOTS_FRANCE = (
    "france", "français", "française", "francais", "francaise",
    "franco-afghan", "franco afghan", "paris", "île-de-france",
    "ile-de-france", "lyon", "marseille", "toulouse", "lille",
    "bordeaux", "nantes", "strasbourg", "rennes", "montpellier",
    "grenoble", "rouen", "nice", "association loi 1901",
    "préfecture", "prefecture", "joafe", "république française",
    "republique francaise", "+33",
)

MOTS_ACTION = (
    "mission", "missions", "objectif", "objectifs", "action", "actions",
    "activité", "activités", "activite", "activites", "projet", "projets",
    "programme", "programmes", "aide", "accompagnement", "soutien",
    "solidarité", "solidarite", "intégration", "integration", "insertion",
    "accueil", "culture", "éducation", "education", "formation", "droits",
    "humanitaire", "réfugié", "refugie", "coopération", "cooperation",
    "santé", "sante", "jeunesse", "femmes", "diaspora", "communauté",
    "communaute", "partenariat", "bénévole", "benevole",
)

MOTS_STRUCTURE = (
    "qui sommes-nous", "qui sommes nous", "à propos", "a propos", "about us",
    "notre mission", "nos missions", "nos actions", "nos activités",
    "nos activites", "notre histoire", "notre équipe", "notre equipe",
    "nos partenaires", "adhérer", "adherer", "devenir bénévole",
    "devenir benevole", "mentions légales", "mentions legales", "contact",
)

MOTS_CONTENU_EDITORIAL = (
    "publié le", "publie le", "mis à jour le", "mis a jour le",
    "temps de lecture", "par la rédaction", "par la redaction",
    "journaliste", "reportage", "article", "actualité", "actualite",
    "tribune", "communiqué de presse", "communique de presse",
)

DOMAINES_EXCLUS = (
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "youtu.be", "tiktok.com", "twitter.com", "x.com", "wikipedia.org",
    "leetchi.com", "gofundme.com", "change.org", "mesopinions.com",
    "onparticipe.fr", "cotizup.com", "ulule.com", "kisskissbankbank.com",
    "eventbrite.fr", "eventbrite.com", "billetweb.fr", "indeed.com",
    "indeed.fr", "welcometothejungle.com", "glassdoor.fr",
)

# Les profils d'association restent acceptables même sans site propre.
DOMAINES_PROFILS = (
    "helloasso.com", "annuaire-entreprises.data.gouv.fr",
    "journal-officiel.gouv.fr", "pappers.fr", "assoce.fr",
)

CHEMINS_EXCLUS = (
    "/article/", "/articles/", "/actualite/", "/actualites/", "/news/",
    "/blog/", "/presse/", "/reportage/", "/podcast/", "/video/",
    "/videos/", "/cagnotte/", "/cagnottes/", "/petition/", "/petitions/",
    "/evenement/", "/evenements/", "/event/", "/events/", "/agenda/",
    "/billetterie/", "/emploi/", "/emplois/", "/stage/", "/stages/",
)

PAGES_UTILES = (
    "qui-sommes-nous", "qui sommes nous", "a-propos", "à propos", "about",
    "notre-histoire", "association", "nos-missions", "missions", "actions",
    "activites", "activités", "programmes", "mentions-legales", "contact",
)

# ------------------------------------------------------------------
# TAGS THÉMATIQUES
# ------------------------------------------------------------------
VOCABULAIRE_TAGS = {
    "aide humanitaire": (
        "aide humanitaire", "humanitaire", "urgence", "secours", "distribution",
        "alimentaire", "nourriture", "abri", "séisme", "seisme", "inondation",
        "réfugié", "refugie", "déplacé", "deplace", "victime",
    ),
    "accueil et intégration": (
        "accueil", "intégration", "integration", "insertion", "asile",
        "réfugié", "refugie", "accompagnement social", "hébergement",
        "hebergement", "emploi", "démarches", "demarches", "français langue",
    ),
    "culture": (
        "culture", "culturel", "patrimoine", "musique", "concert", "cinéma",
        "cinema", "film", "livre", "littérature", "litterature", "poésie",
        "poesie", "exposition", "art", "artisanat", "festival",
    ),
    "éducation et formation": (
        "éducation", "education", "école", "ecole", "université", "universite",
        "formation", "cours", "enseignement", "apprentissage", "étudiant",
        "etudiant", "élève", "eleve", "bourse", "alphabétisation",
        "alphabetisation",
    ),
    "droits et plaidoyer": (
        "droits", "plaidoyer", "advocacy", "justice", "liberté", "liberte",
        "démocratie", "democratie", "discrimination", "violence", "protection",
        "droits humains", "droits de l'homme", "droits des femmes",
    ),
    "santé": (
        "santé", "sante", "médical", "medical", "médecin", "medecin",
        "hôpital", "hopital", "soins", "vaccination", "nutrition",
        "psychologique", "santé mentale", "sante mentale", "handicap",
    ),
    "femmes": (
        "femme", "femmes", "filles", "égalité femmes", "egalite femmes",
        "droits des femmes", "autonomisation", "women", "girls",
    ),
    "jeunesse": (
        "jeunesse", "jeunes", "enfants", "adolescents", "mineurs",
        "youth", "children",
    ),
    "coopération franco-afghane": (
        "franco-afghan", "franco afghan", "coopération", "cooperation",
        "relations franco-afghanes", "échange", "echange", "partenariat",
        "jumelage", "amitié franco-afghane", "amitie franco-afghane",
    ),
    "diaspora et communauté": (
        "diaspora", "communauté afghane", "communaute afghane", "afghans de france",
        "vie communautaire", "réseau afghan", "reseau afghan", "communauté",
        "communaute",
    ),
    "collecte et solidarité": (
        "don", "dons", "collecte", "financement", "fonds", "solidarité",
        "solidarite", "générosité", "generosite", "bénévole", "benevole",
    ),
}

MOTS_ENJEUX = tuple(sorted({mot for mots in VOCABULAIRE_TAGS.values() for mot in mots})) + MOTS_ACTION


def nettoyer_texte(texte):
    texte = "" if texte is None else str(texte)
    texte = texte.replace("\xa0", " ")
    texte = texte.replace("\u200e", "").replace("\u200f", "")
    return re.sub(r"\s+", " ", texte).strip()


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


def domaine_de(url):
    return urlparse(normaliser_url(url)).netloc.lower().replace("www.", "")


def contient_un(texte, mots):
    valeur = texte.lower()
    return any(mot.lower() in valeur for mot in mots)


def compter_signaux(texte, mots):
    valeur = texte.lower()
    return sum(1 for mot in mots if mot.lower() in valeur)


def url_est_exclue(url):
    url = normaliser_url(url)
    if not url:
        return True, "URL invalide"

    domaine = domaine_de(url)
    chemin = urlparse(url).path.lower()

    if any(domaine == d or domaine.endswith("." + d) for d in DOMAINES_EXCLUS):
        return True, f"Domaine exclu : {domaine}"

    if any(motif in chemin for motif in CHEMINS_EXCLUS):
        return True, "Page éditoriale, événementielle ou commerciale"

    return False, ""


def detecter_type_organisme(texte):
    texte_min = texte.lower()
    scores = {
        type_organisme: sum(1 for mot in mots if mot in texte_min)
        for type_organisme, mots in MOTS_TYPE_ORGANISME.items()
    }
    meilleur = max(scores, key=scores.get)
    return meilleur if scores[meilleur] > 0 else "non distingué"


def detecter_tags(texte):
    texte_min = texte.lower()
    scores = {
        tag: sum(1 for mot in mots if mot in texte_min)
        for tag, mots in VOCABULAIRE_TAGS.items()
    }
    tags = [tag for tag, score in scores.items() if score >= 1]
    return tags or ["non distingué"]


def page_est_pertinente(titre, extrait, texte, html, url):
    exclue, raison = url_est_exclue(url)
    if exclue:
        return False, raison, {}

    ensemble = nettoyer_texte(f"{titre} {extrait} {texte[:18000]}")
    type_organisme = detecter_type_organisme(ensemble)
    score_afghan = compter_signaux(ensemble, MOTS_AFGHANISTAN)
    score_france = compter_signaux(ensemble, MOTS_FRANCE)
    score_action = compter_signaux(ensemble, MOTS_ACTION)
    score_structure = compter_signaux(ensemble, MOTS_STRUCTURE)
    score_editorial = compter_signaux(ensemble, MOTS_CONTENU_EDITORIAL)

    # Une adresse postale française est aussi un signal France.
    if re.search(r"\b\d{5}\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÿ' -]{2,50}\b", ensemble):
        score_france += 1

    if type_organisme == "non distingué":
        return False, "Aucun statut associatif/ONG/fondation/collectif identifiable", {}
    if score_afghan == 0:
        return False, "Aucun lien clair avec l'Afghanistan ou les Afghans", {}
    if score_france == 0:
        return False, "Aucun lien clair avec la France", {}
    if score_action == 0:
        return False, "Aucune mission ou action associative identifiable", {}
    if score_editorial >= 2 and score_structure == 0:
        return False, "Simple article ou contenu éditorial", {}

    metadonnees = {
        "type_organisme": type_organisme,
        "tags": detecter_tags(ensemble),
        "preuves_filtrage": {
            "signaux_afghanistan": score_afghan,
            "signaux_france": score_france,
            "signaux_actions": score_action,
            "signaux_structure": score_structure,
        },
    }
    return True, "Association pertinente validée", metadonnees


def charger_requetes():
    if not FICHIER_REQUETES.exists():
        raise FileNotFoundError(f"Fichier introuvable : {FICHIER_REQUETES.resolve()}")
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
            "Impossible d'ouvrir Google Chrome avec Selenium. Vérifie Chrome et Selenium."
        ) from erreur


def extraire_resultats_google(driver, requete, page):
    debut = (page - 1) * 10
    url_google = (
        "https://www.google.com/search?"
        f"q={quote_plus(requete)}&start={debut}&num=10&hl=fr&gl=fr"
    )
    driver.get(url_google)
    time.sleep(random.uniform(PAUSE_MIN, PAUSE_MAX))

    if "sorry/index" in driver.current_url.lower() or "captcha" in driver.page_source.lower():
        print("\nGoogle demande une vérification.")
        input("Résous le CAPTCHA dans Chrome, puis appuie sur Entrée ici...")
        time.sleep(2)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    blocs = soup.select("div.MjjYud") or soup.select("div.g")
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
        if not lien or "google." in urlparse(lien).netloc.lower():
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
        print("\nChrome est ouvert. Accepte les cookies Google si nécessaire.")
        input("Quand Google est prêt, appuie sur Entrée ici...")
        for numero, requete in enumerate(requetes, start=1):
            print(f"\nRequête {numero}/{len(requetes)} : {requete}")
            for page in range(1, NOMBRE_PAGES_GOOGLE + 1):
                print(f"  Page {page}/{NOMBRE_PAGES_GOOGLE}")
                tous.extend(extraire_resultats_google(navigateur, requete, page))
                pd.DataFrame(tous).to_csv(
                    RESULTATS_BRUTS, index=False, encoding="utf-8-sig"
                )
    finally:
        navigateur.quit()
    return pd.DataFrame(tous)


def telecharger_page(url):
    try:
        reponse = requests.get(
            url, headers=ENTETES, timeout=18, allow_redirects=True
        )
        reponse.raise_for_status()
        if "text/html" not in reponse.headers.get("Content-Type", ""):
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
    return trouves[:5]


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
    auteur = soup.select_one('meta[name="author"]') or soup.select_one(
        'meta[property="article:author"]'
    )
    if auteur and auteur.get("content"):
        return nettoyer_texte(auteur.get("content"))
    return "Non trouvé automatiquement"


def extraire_date_creation(texte):
    motifs = [
        r"(?:fondée|fondé|créée|créé|naissance|depuis)\s+(?:le\s+)?(\d{1,2}\s+[a-zéû]+\s+\d{4})",
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
        propre = nettoyer_texte(phrase)
        if 35 <= len(propre) <= 350 and contient_un(propre, MOTS_ENJEUX):
            retenues.append(propre)
        if len(retenues) == 3:
            break
    return " ".join(retenues)[:900] if retenues else "Non trouvés automatiquement"


def nombre_public(texte):
    motif = r"(\d[\d\s.,]*)\s*([kKmM]?)\s*(?:vues|abonnés|abonnes|followers)"
    valeurs = []
    for nombre, unite in re.findall(motif, texte, flags=re.IGNORECASE):
        try:
            valeur = float(nombre.replace(" ", "").replace(",", "."))
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
        meilleure_position = min(int(x["position_globale"]) for x in occurrences)
        requetes_distinctes = len({x["requete"] for x in occurrences})
        signal_public = max(
            (nombre_public(f"{x['titre_google']} {x['description_google']}") for x in occurrences),
            default=0,
        )
        score_position = max(1, 101 - meilleure_position)
        bonus_requetes = min(20, (requetes_distinctes - 1) * 4)
        bonus_public = min(15, round(math.log10(signal_public + 1) * 3, 2)) if signal_public else 0
        domaine = domaine_de(url)
        bonus_site = 0 if any(domaine == d or domaine.endswith("." + d) for d in DOMAINES_PROFILS) else 5
        score = min(100, round(score_position * 0.65 + bonus_requetes + bonus_public + bonus_site, 2))
        scores[url] = {
            "score_impact": score,
            "meilleure_position_google": meilleure_position,
            "nombre_requetes": requetes_distinctes,
            "vues_ou_abonnes_publics": signal_public,
        }
    return scores


def url_canonique(url_finale):
    url_finale = normaliser_url(url_finale)
    domaine = domaine_de(url_finale)
    if any(domaine == d or domaine.endswith("." + d) for d in DOMAINES_PROFILS):
        return url_finale
    return f"https://{domaine}"


def enrichir(resultats, scores):
    lignes_finales = []
    journal = []
    tags_finaux = {}
    noms_finaux = {}
    entites_deja_ajoutees = set()

    urls_ordonnees = sorted(scores, key=lambda url: scores[url]["score_impact"], reverse=True)
    infos_google = {
        url: resultats[resultats["url"] == url].iloc[0].to_dict()
        for url in urls_ordonnees
    }

    for numero, url in enumerate(urls_ordonnees, start=1):
        info = infos_google[url]
        print(f"\nVérification {numero}/{len(urls_ordonnees)} : {url}")

        exclue, raison = url_est_exclue(url)
        if exclue:
            journal.append({"url": url, "statut": "REJETÉ", "raison": raison})
            continue

        url_finale, html = telecharger_page(url)
        if not html:
            journal.append({
                "url": url, "statut": "REJETÉ",
                "raison": "Page inaccessible ou non HTML",
            })
            continue

        textes = [texte_visible(html)]
        htmls = [html]
        for page_utile in liens_pages_utiles(url_finale, html):
            _, html_utile = telecharger_page(page_utile)
            if html_utile:
                textes.append(texte_visible(html_utile))
                htmls.append(html_utile)
                time.sleep(0.4)

        texte_total = nettoyer_texte(" ".join(textes))
        html_total = "\n".join(htmls)
        valide, raison, metadonnees = page_est_pertinente(
            info["titre_google"], info["description_google"],
            texte_total, html_total, url_finale,
        )
        if not valide:
            journal.append({"url": url, "statut": "REJETÉ", "raison": raison})
            continue

        url_entite = url_canonique(url_finale)
        if url_entite in entites_deja_ajoutees:
            journal.append({
                "url": url, "statut": "DOUBLON",
                "raison": f"Déjà enregistré sous {url_entite}",
            })
            continue
        entites_deja_ajoutees.add(url_entite)

        lignes_finales.append({
            "url_web": url_entite,
            "fondateur_ou_auteur": extraire_fondateur(texte_total, html_total),
            "date_de_creation": extraire_date_creation(texte_total),
            "siege_ou_lieu": extraire_siege(texte_total, html_total),
            "enjeux_de_l_association": extraire_enjeux(texte_total),
            "_score_impact": scores[url]["score_impact"],
            "_score_details": scores[url],
        })
        tags_finaux[url_entite] = metadonnees
        noms_finaux[url_entite] = extraire_nom(
            html, info.get("titre_google", ""), url_entite
        )
        journal.append({
            "url": url,
            "url_conservee": url_entite,
            "statut": "ACCEPTÉ",
            "raison": raison,
            "type_organisme": metadonnees["type_organisme"],
            "tags": " | ".join(metadonnees["tags"]),
        })

    pd.DataFrame(journal).to_csv(
        JOURNAL_FILTRAGE, index=False, encoding="utf-8-sig"
    )
    return lignes_finales, tags_finaux, noms_finaux


def enregistrer_base(lignes, tags, noms):
    DOSSIER_DATA.mkdir(parents=True, exist_ok=True)
    lignes = sorted(lignes, key=lambda x: x["_score_impact"], reverse=True)
    colonnes = [
        "url_web", "fondateur_ou_auteur", "date_de_creation",
        "siege_ou_lieu", "enjeux_de_l_association",
    ]
    tableau = pd.DataFrame(
        [{colonne: ligne[colonne] for colonne in colonnes} for ligne in lignes],
        columns=colonnes,
    )
    tableau.to_csv(CSV_FINAL, index=False, encoding="utf-8-sig")

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
    tableau.to_sql("associations", connexion, if_exists="append", index=False)
    connexion.commit()
    connexion.close()

    scores_finaux = {
        ligne["url_web"]: {**ligne["_score_details"], "score_impact": ligne["_score_impact"]}
        for ligne in lignes
    }
    SCORES_JSON.write_text(json.dumps(scores_finaux, ensure_ascii=False, indent=2), encoding="utf-8")
    TAGS_JSON.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")
    NOMS_JSON.write_text(json.dumps(noms, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nTerminé.")
    print(f"Associations conservées : {len(tableau)}")
    print(f"Base SQLite : {BASE_SQLITE.resolve()}")
    print(f"Tags : {TAGS_JSON.resolve()}")
    print(f"Journal de filtrage : {JOURNAL_FILTRAGE.resolve()}")


def main():
    DOSSIER_DATA.mkdir(parents=True, exist_ok=True)
    print("Collecte stricte des associations Afghanistan–France...")
    resultats = collecter_google()
    if resultats.empty:
        raise RuntimeError("Aucun résultat Google n'a été récupéré.")
    scores = calculer_scores(resultats)
    lignes, tags, noms = enrichir(resultats, scores)
    enregistrer_base(lignes, tags, noms)


if __name__ == "__main__":
    main()
