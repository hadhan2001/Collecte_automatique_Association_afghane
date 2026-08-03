from collecte_associations import page_est_pertinente, detecter_tags


def main():
    bon = (
        "Association franco-afghane loi 1901 basée à Paris. "
        "Notre mission est l'aide humanitaire, l'éducation des jeunes "
        "et l'accompagnement des réfugiés afghans en France."
    )
    valide, raison, meta = page_est_pertinente("", "", bon, "", "https://exemple.fr")
    assert valide, raison
    assert meta["type_organisme"] == "association"
    assert "aide humanitaire" in meta["tags"]
    assert "éducation et formation" in meta["tags"]

    article = (
        "Article publié le 3 janvier. Reportage sur l'Afghanistan et la France. "
        "Par la rédaction, temps de lecture 5 minutes."
    )
    valide, _, _ = page_est_pertinente("", "", article, "", "https://journal.fr/article/test")
    assert not valide

    sans_france = "ONG humanitaire active en Afghanistan avec plusieurs programmes d'aide."
    valide, _, _ = page_est_pertinente("", "", sans_france, "", "https://ong.org")
    assert not valide

    assert detecter_tags("festival culturel et exposition d'art afghan") == ["culture"]
    print("Tests réussis : filtres stricts et tags fonctionnent.")


if __name__ == "__main__":
    main()
