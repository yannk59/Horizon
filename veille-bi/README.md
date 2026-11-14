# Veille BI : rapports de tendances startups, entrepreneuriat et tech

Cette couche « business intelligence » s'ajoute à Horizon. Horizon collecte et note les **signaux** chaque jour. Ce module les transforme en **rapports de tendances** prêts à vendre.

```
Sources (RSS, HN, Reddit, Google News, GitHub…)
        │  chaque jour, 06:17  (.github/workflows/daily-summary.yml)
        ▼
Horizon : briefing quotidien noté  ──►  GitHub Pages (_posts/AAAA-MM-JJ-summary-fr.md)
        │  chaque lundi, 07:23  (.github/workflows/rapport-tendances.yml)
        ▼
Agent 1 Analyste ──► Agent 2 Rédacteur ──► Agent 3 Vérificateur
        ▼
Brouillon : veille-bi/rapports/AAAA-MM-JJ-7j.md   ← tu relis et corriges
        ▼  bouton « publier »
Rapport en ligne sur GitHub Pages
```

## Contenu du dossier

| Fichier | Rôle |
|---|---|
| `agents/analyste.md` | Passe des signaux aux tendances (maturité, chiffres, preuves) |
| `agents/redacteur.md` | Rédige le rapport client (ton, longueur, recommandations) |
| `agents/verificateur.md` | Vérifie chaque chiffre et chaque lien face aux sources |
| `templates/rapport-hebdo.md` | La structure du rapport : c'est ton produit |
| `scripts/rapport_tendances.py` | Enchaîne les 3 agents |
| `rapports/` | Les brouillons générés, avec l'analyse intermédiaire |

Tu peux modifier les prompts directement sur GitHub (icône crayon). C'est là que se joue la qualité.

## Utilisation au quotidien (aucune ligne de code)

1. **Rien à faire le lundi matin.** Le brouillon de la semaine arrive tout seul dans `veille-bi/rapports/`.
2. **Relire.** Ouvre le fichier sur GitHub, clique sur le crayon, corrige et ajoute ton analyse d'expert, puis clique sur *Commit changes*.
3. **Publier.** Va dans l'onglet **Actions**, choisis *Rapport de tendances (veille BI)*, clique sur *Run workflow* et choisis `publier`.

Pour lancer un rapport à la demande, par exemple **mensuel** : *Run workflow*, `generer`, jours = `30`.

### Réglages (une seule fois)
- Le secret `ANTHROPIC_API_KEY` est déjà utilisé par Horizon, donc rien à ajouter.
- *Optionnel* : pour une rédaction plus fine que le modèle quotidien, crée une variable `VEILLE_MODEL` (Settings, puis Secrets and variables, Actions, onglet *Variables*) avec un modèle plus puissant.
- Le rapport ne vaut que par ses sources : enrichis `data/config.github.json` (flux RSS Maddyness, FrenchWeb, Sifted, EU-Startups, Bpifrance, etc.).

## Newsletter (Brevo)

Quand tu cliques sur `publier`, le rapport validé part aussi en **newsletter** vers ta liste Brevo. Il est mis en forme pour l'email, avec un bouton « Lire en ligne » et un lien de désabonnement conforme au RGPD (`scripts/newsletter_brevo.py`).

### Mise en place (une fois, environ 15 min)
1. Crée un compte sur **brevo.com** (gratuit jusqu'à 300 emails par jour).
2. Dans Brevo :
   - **Expéditeurs** : ajoute et valide ton adresse d'envoi (idéalement sur ton propre domaine).
   - **Contacts, puis Listes** : crée une liste, par exemple « Veille tendances », et note son **numéro** (ID).
   - **Formulaires** : crée un formulaire d'inscription relié à cette liste, avec double opt-in, et colle son lien sur ton site ou LinkedIn.
   - **SMTP & API, puis Clés API** : génère une clé.
3. Sur GitHub, va dans *Settings*, puis *Secrets and variables*, puis *Actions* :
   - onglet *Secrets* : `BREVO_API_KEY` = la clé API ;
   - onglet *Variables* :
     - `BREVO_LIST_ID` = le numéro de la liste ;
     - `BREVO_SENDER_EMAIL` = l'adresse validée ;
     - `BREVO_SENDER_NAME` = le nom affiché (par exemple « Veille Tendances · Yann Kervarec ») ;
     - `BREVO_TEST_EMAIL` = ton adresse, pour recevoir les tests.

### Au quotidien
- **Avant d'envoyer** : *Run workflow*, puis `tester-newsletter`. Tu reçois le dernier brouillon dans ta boîte, exactement comme tes abonnés le verront.
- **Pour envoyer** : *Run workflow*, puis `publier`. Le rapport est mis en ligne et la newsletter part à toute la liste.

Sans clé Brevo, `publier` met simplement le rapport en ligne, sans envoyer d'email.

## Du rapport au business

| Offre | Format | Cible |
|---|---|---|
| Briefing quotidien gratuit | Page web + newsletter | Audience, crédibilité |
| Rapport hebdo de tendances | Abonnement | Fondateurs, business angels, consultants |
| Baromètre mensuel / sectoriel | Rapport à l'unité ou abonnement pro | Fonds, incubateurs, directions innovation |
| Veille sur mesure | Profil Horizon dédié + rapport privé | Corporates, collectivités, écoles |

Ce qui te différencie : le regard France, Europe et Hauts-de-France, ta validation humaine d'expert et l'historique qui s'accumule (des tendances suivies dans le temps).

Pour l'**accès client privé**, mets ce dépôt (ou un dépôt dédié aux rapports) en privé et envoie les rapports par email, ou utilise Buzz (voir ci-dessous).

## Étape suivante : Buzz (block/buzz)

Quand tu voudras une vraie salle de rédaction avec clients et agents dans le même espace, ton fork `yannk59/buzz` pourra accueillir les mêmes agents :
- canaux `#signaux` → `#analyse` → `#brouillons` → `#validation` → `#clients` ;
- chaque agent reprend le prompt du dossier `agents/` ;
- un canal invité par client pour qu'il pose ses questions à l'analyste.

Buzz demande un serveur (Docker : relay Rust, PostgreSQL, Redis, S3/MinIO). Mieux vaut commencer avec ce module, qui tourne gratuitement sur GitHub Actions.
