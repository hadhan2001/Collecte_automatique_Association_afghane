# Associations Afghanistan – France — filtres et tags

Cette version applique un filtrage strict avant de conserver un résultat.

## Conditions obligatoires

Une page est conservée uniquement si elle présente :

1. un statut identifiable : association, ONG, fondation, collectif ou organisation à but non lucratif ;
2. un lien clair avec l’Afghanistan ou les Afghans ;
3. un lien clair avec la France ;
4. au moins une mission ou une action associative identifiable.

Les simples articles, actualités, événements, cagnottes, pétitions, offres
d’emploi et pages de réseaux sociaux sont rejetés.

## Tags

Les tags ne sont pas ajoutés aux cinq colonnes de la base SQLite. Ils sont
conservés séparément dans :

```text
data/tags_associations.json
```

Tags possibles :

```text
aide humanitaire
accueil et intégration
culture
éducation et formation
droits et plaidoyer
santé
femmes
jeunesse
coopération franco-afghane
diaspora et communauté
collecte et solidarité
non distingué
```

## Cinq colonnes SQLite conservées

```text
url_web
fondateur_ou_auteur
date_de_creation
siege_ou_lieu
enjeux_de_l_association
```

## Utilisation

### Installation

Double-cliquer sur :

```text
installer.bat
```

### Nouvelle collecte complète

```text
1_collecte_complete.bat
```

### Appliquer les filtres à une base déjà existante

Copier la base dans :

```text
data/associations_afghanistan_france.db
```

Puis lancer :

```text
2_filtrer_base_existante.bat
```

Une sauvegarde automatique est créée avant toute suppression.

### Interface

```text
3_lancer_interface.bat
```

L’interface permet de filtrer par :

- type d’organisme ;
- thématique ;
- recherche textuelle.

Les tags apparaissent sous le nom de l’association, sans ajouter une colonne à
la base SQLite.

## Fichiers générés

```text
data/associations_afghanistan_france.db
data/associations_afghanistan_france.csv
data/impact_scores.json
data/noms_associations.json
data/tags_associations.json
data/journal_filtrage.csv
data/resultats_google_bruts.csv
```
