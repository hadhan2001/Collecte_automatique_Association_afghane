# Associations Afghanistan – France

Cette version crée une base SQLite contenant exactement cinq colonnes :

1. `url_web`
2. `fondateur_ou_auteur`
3. `date_de_creation`
4. `siege_ou_lieu`
5. `enjeux_de_l_association`

Le classement d’impact n’est pas stocké dans la table SQLite afin de respecter
la limite de cinq colonnes. Il est calculé dans un fichier séparé :

```text
data/impact_scores.json
```

L’interface Streamlit utilise ce fichier pour afficher les associations de la
plus importante à la moins importante.

## Calcul de l’impact

Le classement combine :

- la meilleure position obtenue dans les dix premières pages Google ;
- le nombre de requêtes différentes où l’association apparaît ;
- les vues, abonnés ou followers lorsqu’un nombre public est visible ;
- un léger bonus lorsque l’URL semble être un site officiel.

Le nombre réel de visites d’un site n’est généralement pas public. Le score
est donc un indicateur de visibilité, et non une mesure d’audience exacte.

## Installation

Dans CMD :

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Lancer la collecte

```bat
python collecte_associations.py
```

Chrome s’ouvre. Accepte les cookies Google si nécessaire, puis confirme dans
le terminal. Le programme visite les dix premières pages pour chaque requête
de `queries.txt`.

La collecte directe peut déclencher un CAPTCHA. Dans ce cas, résous-le
manuellement dans Chrome, puis reviens dans le terminal.

## Résultats

```text
data/associations_afghanistan_france.db
data/associations_afghanistan_france.csv
data/impact_scores.json
data/resultats_google_bruts.csv
```

## Lancer l’interface

```bat
streamlit run app.py
```

L’interface affiche uniquement les cinq colonnes demandées. Le numéro de ligne
correspond au classement d’impact.
