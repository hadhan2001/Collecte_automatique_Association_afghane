from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from collecte_associations import (
    BASE_SQLITE,
    CSV_FINAL,
    JOURNAL_FILTRAGE,
    NOMS_JSON,
    SCORES_JSON,
    TAGS_JSON,
    liens_pages_utiles,
    nettoyer_texte,
    page_est_pertinente,
    telecharger_page,
    texte_visible,
)


def sauvegarder_fichier(path: Path, dossier: Path) -> None:
    if path.exists():
        shutil.copy2(path, dossier / path.name)


def main() -> None:
    if not BASE_SQLITE.exists():
        raise FileNotFoundError(f"Base introuvable : {BASE_SQLITE.resolve()}")

    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    dossier_backup = Path("data") / f"sauvegarde_avant_filtrage_{horodatage}"
    dossier_backup.mkdir(parents=True, exist_ok=True)

    for path in (BASE_SQLITE, CSV_FINAL, SCORES_JSON, TAGS_JSON, NOMS_JSON):
        sauvegarder_fichier(path, dossier_backup)

    connexion = sqlite3.connect(BASE_SQLITE)
    tableau = pd.read_sql_query("SELECT * FROM associations", connexion)
    connexion.close()

    tags = {}
    journal = []
    indices_conserves = []

    for numero, ligne in tableau.iterrows():
        url = str(ligne.get("url_web", "")).strip()
        print(f"{numero + 1}/{len(tableau)} vérification : {url}")

        url_finale, html = telecharger_page(url)
        if not html:
            journal.append({
                "url": url,
                "statut": "REJETÉ",
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

        texte_total = nettoyer_texte(" ".join(textes))
        valide, raison, meta = page_est_pertinente(
            "", "", texte_total, "\n".join(htmls), url_finale
        )

        if valide:
            indices_conserves.append(numero)
            tags[url] = meta
            journal.append({
                "url": url,
                "statut": "ACCEPTÉ",
                "raison": raison,
                "type_organisme": meta["type_organisme"],
                "tags": " | ".join(meta["tags"]),
            })
        else:
            journal.append({"url": url, "statut": "REJETÉ", "raison": raison})

    filtre = tableau.loc[indices_conserves].reset_index(drop=True)
    filtre.to_csv(CSV_FINAL, index=False, encoding="utf-8-sig")

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
    filtre.to_sql("associations", connexion, if_exists="append", index=False)
    connexion.commit()
    connexion.close()

    TAGS_JSON.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(journal).to_csv(JOURNAL_FILTRAGE, index=False, encoding="utf-8-sig")

    urls_valides = set(filtre["url_web"].astype(str))
    for json_path in (SCORES_JSON, NOMS_JSON):
        if json_path.exists():
            donnees = json.loads(json_path.read_text(encoding="utf-8"))
            donnees = {url: valeur for url, valeur in donnees.items() if url in urls_valides}
            json_path.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nFiltrage terminé.")
    print(f"Avant : {len(tableau)} association(s)")
    print(f"Après : {len(filtre)} association(s)")
    print(f"Sauvegarde : {dossier_backup.resolve()}")
    print(f"Journal : {JOURNAL_FILTRAGE.resolve()}")


if __name__ == "__main__":
    main()
