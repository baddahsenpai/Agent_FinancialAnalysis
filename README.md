# finance-agent

Agent local d'analyse de résultats financiers journaliers. Lit un export CSV de la
valeur d'un portefeuille, calcule les rendements (en excluant dépôts et retraits),
les compare à un objectif de rentabilité annualisé, et émet un verdict chiffré.

Aucune connexion à un courtier : l'outil travaille uniquement sur vos propres fichiers.

## Format du CSV

Colonnes : `date`, `value`, `deposit` (optionnel), `withdrawal` (optionnel).

- `date` : `YYYY-MM-DD` (ou `DD/MM/YYYY`)
- `value` : valeur totale du portefeuille en fin de journée
- `deposit` / `withdrawal` : flux du jour (un dépôt ne doit pas être compté comme un gain)

Exemple : voir `data/exemple.csv`.

## Utilisation

```bash
python3 finance_agent.py data/exemple.csv --target-annual 0.08 --horizon-days 365
python3 finance_agent.py mon_export.csv --target-annual 0.10 --end-date 2026-01-31 --output rapport.txt
```

Options :

- `--target-annual` : objectif de rendement annualisé (ex. `0.08` pour 8 %)
- `--horizon-days` : horizon en jours calendaires
- `--end-date` : date d'échéance `YYYY-MM-DD` (prioritaire sur `--horizon-days`)
- `--output` : fichier de sortie du rapport (sinon affiché dans le terminal)

## Métriques calculées

Rendement total et pondéré par les flux, rendement/volatilité annualisés (252 jours
de bourse), ratio de Sharpe, drawdown maximal, taux de jours gagnants, meilleur/pire
jour. Côté objectif : rendement journalier requis, valeur visée vs valeur projetée,
score z et verdict (en avance / atteignable / exigeant / peu réaliste).

## Tests

```bash
python3 -m unittest discover -s tests
```
