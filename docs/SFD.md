# Spécifications Fonctionnelles Détaillées — JustePrix Immo

**Version** : 1.0
**Date** : Mars 2026
**Auteur** : Adrien de Lestapis
**Statut** : Proof of Concept — Phase de test bêta fermée

---

## Table des matières

1. [Présentation générale](#1-présentation-générale)
2. [Contexte et objectifs](#2-contexte-et-objectifs)
3. [Utilisateurs cibles](#3-utilisateurs-cibles)
4. [Architecture technique](#4-architecture-technique)
5. [Parcours utilisateur](#5-parcours-utilisateur)
6. [Règles de jeu](#6-règles-de-jeu)
7. [Données immobilières](#7-données-immobilières)
8. [Pipeline de collecte automatique](#8-pipeline-de-collecte-automatique)
9. [Module de sélection géographique](#9-module-de-sélection-géographique)
10. [Interfaces et composants UI](#10-interfaces-et-composants-ui)
11. [Comportement mobile](#11-comportement-mobile)
12. [Infrastructure et déploiement](#12-infrastructure-et-déploiement)
13. [Sécurité et données sensibles](#13-sécurité-et-données-sensibles)
14. [Évolutions prévues](#14-évolutions-prévues)
15. [Glossaire](#15-glossaire)

---

## 1. Présentation générale

**JustePrix Immo** est un jeu web en mode solo d'estimation de prix immobilier. Le joueur est confronté à de vraies annonces de vente d'appartements français (photos, carte, surface, localisation) et doit en deviner le prix dans un temps imparti. L'application est entièrement en français et ciblée sur le territoire métropolitain français.

### Dénomination
- **Nom du projet** : JustePrix Immo
- **URL publique actuelle** : `https://adriendl.github.io/Rentsell/`
- **Dépôt GitHub** : `github.com/Adriendl/Rentsell` (public)

---

## 2. Contexte et objectifs

### Contexte
Le projet est né d'une volonté d'éduquer les utilisateurs aux réalités du marché immobilier français de manière ludique. L'immobilier étant un sujet opaque pour beaucoup, un format jeu permet d'apprendre sans friction.

### Objectifs du Proof of Concept
- Valider l'expérience de jeu sur mobile (usage cible principal)
- Tester la qualité des données scrappées auprès de beta-testeurs
- Identifier les bugs UX sur différents appareils
- Préparer une mise en production pérenne avec backend déployé

### Hors scope (PoC)
- Système de compte utilisateur / inscription
- Classements multijoueur ou leaderboard
- Monétisation
- Annonces de location (uniquement la vente pour l'instant)
- Maisons / villas (uniquement les appartements)

---

## 3. Utilisateurs cibles

| Profil | Description |
|---|---|
| Grand public | Curieux de l'immobilier, joue par amusement |
| Futurs acheteurs | Veulent calibrer leur connaissance du marché local |
| Professionnels immo | Auto-évaluation de leur expertise |
| Beta-testeurs PoC | Invités à tester avant mise en production |

**Usage principal** : mobile (smartphone), secondairement tablette et desktop.

---

## 4. Architecture technique

### Frontend
| Technologie | Usage |
|---|---|
| React 18 | Composants UI, gestion d'état (`useReducer`) |
| Vite | Bundler + dev server |
| Tailwind CSS v4 | Styles utilitaires, dark mode |
| Lucide React | Icônes |
| OpenStreetMap (iframe) | Carte de localisation |

### Backend (local / production future)
| Technologie | Usage |
|---|---|
| Python 3.12 | Langage principal |
| FastAPI + uvicorn | API REST |
| SQLAlchemy 2 (asyncpg) | ORM async |
| PostgreSQL 16 | Base de données |
| Redis 7 | Broker Celery |
| Celery + Celery Beat | Worker et scheduler |
| httpx + BeautifulSoup4 | Scraping HTTP |
| pydantic-settings | Configuration par variables d'environnement |
| Alembic | Migrations BDD |

### Infrastructure PoC (sans backend déployé)
```
GitHub Actions (cron)
    └─ Scraping Laforêt + PAP
    └─ Export → apartments.json
    └─ Commit + push → main
          └─ Déclenche Deploy to GitHub Pages
```

### Infrastructure future (avec backend déployé)
```
Frontend (GitHub Pages ou hébergeur)
    └─ API HTTPS → FastAPI
          └─ PostgreSQL
          └─ Redis + Celery (scraping automatisé)
          └─ Stockage S3 (mirroring photos)
```

---

## 5. Parcours utilisateur

### 5.1 Schéma général

```
Accueil
  └─ Sélection de zone géographique
        ├─ Toute la France
        └─ Métropole (Paris, Lyon, Marseille, etc.)
              └─ Manche 1..10
                    └─ Affichage annonce (photos + carte + infos)
                    └─ Saisie estimation + chronomètre
                    └─ Validation → Écran résultat intermédiaire
                          └─ (Manche < 10) → Manche suivante
                          └─ (Manche = 10) → Écran de fin de partie
                                └─ Rejouer (retour sélection de zone)
```

### 5.2 Écran d'accueil (phase : `menu`)

- Logo / titre "JustePrix Immo"
- Accroche courte
- Bouton **"Jouer"** → charge les annonces (API ou JSON) → phase `citySelect`
- Indicateur de chargement pendant le fetch

### 5.3 Sélection de zone (phase : `citySelect`)

- Deux options :
  - **Toute la France** : pool de toutes les annonces disponibles
  - **Choisir une métropole** : grille des 10 grandes villes (voir §9)
- Chaque tuile métropole affiche : emoji, nom de la ville, nombre d'annonces disponibles
- Les métropoles avec moins de 3 annonces dans la base sont masquées
- Sélection → démarre immédiatement la partie (phase `playing`)

### 5.4 Manche en cours (phase : `playing`)

Voir §6 pour les règles détaillées.

### 5.5 Résultat intermédiaire (phase : `result`)

- Affichage du score de la manche (points précision + bonus temps)
- Comparaison estimation vs prix réel avec indicateur visuel
- Bouton **"Voir l'annonce originale"** → ouvre l'annonce sur le site vendeur dans un nouvel onglet (si URL disponible)
- Bouton **"Appartement suivant"**

### 5.6 Fin de partie (phase : `gameover`)

- Score total sur 12 000 pts maximum (10 manches × 1 200 pts max)
- Tableau récapitulatif de toutes les manches (ville, surface, estimation, prix réel, écart, score)
- Bouton **"Rejouer"** → retour à la sélection de zone

---

## 6. Règles de jeu

### 6.1 Structure d'une partie
- **10 manches** par partie (`ROUNDS_PER_GAME = 10`)
- Annonces sélectionnées aléatoirement dans le pool filtré

### 6.2 Chronomètre
- **60 secondes** par manche (`TIMER_SECONDS = 60`)
- Décompte en temps réel affiché
- À l'expiration : l'estimation en cours est soumise automatiquement avec `timeRemaining = 0`

### 6.3 Saisie de l'estimation
- Champ numérique avec formatage automatique en français (espaces de séparation des milliers)
- Valeurs acceptées : entiers positifs en euros
- Le champ n'est **pas** focus automatiquement à l'arrivée sur une manche (évite l'apparition du clavier mobile non sollicité)
- Bouton **"Valider"** ou touche Entrée pour soumettre

### 6.4 Calcul du score

#### Points de précision (0 à 1 000 pts)
| Écart vs prix réel | Points |
|---|---|
| 0 % (exact) | 1 000 |
| ≤ 5 % | 800 |
| ≤ 10 % | 600 |
| ≤ 15 % | 400 |
| ≤ 25 % | 200 |
| ≤ 40 % | 100 |
| > 40 % | 0 |

#### Bonus de temps (0 à 200 pts)
`bonus = floor((tempsRestant / 60) × 200)`

#### Score maximum par manche
1 000 (précision) + 200 (temps) = **1 200 pts**

#### Score maximum par partie
10 × 1 200 = **12 000 pts**

### 6.5 Indicateurs visuels du score
| Écart | Emoji | Label |
|---|---|---|
| 0 % | 🎯 | Parfait ! |
| ≤ 5 % | 🔥 | Excellent ! |
| ≤ 10 % | 💪 | Très bien ! |
| ≤ 15 % | 👍 | Bien ! |
| ≤ 25 % | 🙂 | Pas mal |
| ≤ 40 % | 😐 | Bof... |
| > 40 % | 😬 | Raté ! |

---

## 7. Données immobilières

### 7.1 Source des données
- **Laforêt Immobilier** (réseau de franchises) — priorité 1
- **PAP.fr** (particulier à particulier) — priorité 2
- **SeLoger** — prévu (squelette Playwright, non actif)

### 7.2 Structure d'une annonce

```json
{
  "id": "identifiant unique (source_id du scraper)",
  "city": "Bordeaux (33000)",
  "lat": 44.8378,
  "lng": -0.5792,
  "surface": 68,
  "rooms": 3,
  "price": 299000,
  "images": ["https://cdn.example.com/photo1.jpg", "..."],
  "source": "https://www.laforet.com/achat-immobilier/..."
}
```

### 7.3 Volume actuel (PoC)
- **~1 300 annonces** valides dans `apartments.json`
- **~192 villes** couvertes (dont agglomérations)
- Top villes : Nice (83), Montpellier (65), Bordeaux (64), Toulouse (50)

### 7.4 Critères de validation des annonces
Les annonces ne respectant pas les critères suivants sont rejetées automatiquement :

| Critère | Règle |
|---|---|
| Prix au m² | Compris entre 800 et 30 000 €/m² |
| Surface | Comprise entre 8 et 500 m² |
| Photos | Au moins 1 photo requise |
| Coordonnées GPS | Dans le bounding box France métropolitaine : lat ∈ [41.3, 51.1], lng ∈ [-5.2, 9.6] |

---

## 8. Pipeline de collecte automatique

### 8.1 Déclenchement

| Mode | Fréquence |
|---|---|
| Automatique (GitHub Actions) | 06h00 UTC et 18h00 UTC chaque jour |
| Manuel (interface GitHub) | À la demande via "Run workflow" |

### 8.2 Étapes du pipeline

```
1. Scraping Laforêt
   └─ Parcourt 83 agences réparties sur 10 métropoles
   └─ Récupère les annonces en HTML statique (httpx + BeautifulSoup)
   └─ Délai aléatoire 1.5s–3s entre requêtes

2. Scraping PAP
   └─ Recherche par ville avec code g-PAP
   └─ Récupère jusqu'à 2 pages de résultats par ville
   └─ Fetch individuel de chaque page de détail (photos, coordonnées)

3. Normalisation
   └─ Surface : parse "68 m²", "68.5m2", "68" → int
   └─ Prix : supprime espaces/€/FAI → int
   └─ Ville : nettoyage des artefacts de parsing (ex: "05 m² Bordeaux" → "Bordeaux")

4. Géocodage (si lat/lng absents)
   └─ API Adresse gouvernementale : api-adresse.data.gouv.fr (sans clé)
   └─ Résultat mis en cache pour la durée du process

5. Validation
   └─ Rejet silencieux si hors critères (§7.4)

6. Déduplication
   └─ Clé : source + source_id (une annonce ne peut apparaître deux fois)
   └─ Conservation des annonces existantes non re-scrappées ce cycle

7. Export
   └─ Écriture dans apartments.json (tri par ville, puis prix)
   └─ Commit automatique si des changements sont détectés
   └─ Push → main → déclenchement automatique du workflow de déploiement
```

### 8.3 Anti-détection
- Pool de 5 User-Agents desktop récents, rotation aléatoire
- Délai aléatoire configurable (`MIN_DELAY`, `MAX_DELAY`)
- Retry exponentiel sur HTTP 429 / 503 (max 3 tentatives, attente 5–30s)
- Vérification `robots.txt` avant premier appel par domaine

---

## 9. Module de sélection géographique

### 9.1 Les 10 métropoles

| Clé | Label | Rayon (km) | Emoji |
|---|---|---|---|
| `paris` | Paris | 25 | 🗼 |
| `marseille` | Marseille | 25 | ⛵ |
| `lyon` | Lyon | 20 | 🦁 |
| `toulouse` | Toulouse | 20 | 🚀 |
| `nice` | Nice | 25 | 🌴 |
| `nantes` | Nantes | 20 | 🐘 |
| `montpellier` | Montpellier | 20 | ☀️ |
| `strasbourg` | Strasbourg | 20 | 🥨 |
| `bordeaux` | Bordeaux | 20 | 🍷 |
| `lille` | Lille | 20 | 🧱 |

### 9.2 Logique de proximité

Le filtre géographique utilise la **distance de Haversine** (distance à vol d'oiseau sur la sphère terrestre) entre les coordonnées GPS de l'annonce et le centre de la métropole.

**Exemples de villes incluses par métropole :**
- Paris (25 km) → Boulogne-Billancourt, Montreuil, Vincennes, Saint-Denis, Levallois-Perret, Issy-les-Moulineaux, Clichy…
- Nantes (20 km) → Carquefou, Rezé, Saint-Herblain, Saint-Sébastien-sur-Loire…
- Nice (25 km) → Antibes, Cannes, Cagnes-sur-Mer, Villefranche-sur-Mer…

### 9.3 Seuil de disponibilité
Une métropole n'est proposée dans la sélection que si elle dispose d'au moins **3 annonces valides** dans la base.

---

## 10. Interfaces et composants UI

### 10.1 Design général
- **Mode sombre** exclusif (fond `gray-900`)
- **Couleur d'accent** : émeraude (`emerald-400` / `emerald-500`)
- **Typographie** : système (sans-serif)
- **Animations** : fadeIn CSS, transition d'opacité sur photos, compteur animé (requestAnimationFrame)

### 10.2 Composants principaux

#### `PhotoCarousel`
- Carrousel d'images avec navigation gauche/droite
- Swipe horizontal sur mobile pour changer de photo
- Swipe vertical non intercepté (laisse le scroll natif fonctionner)
- Indicateur de position (points)

#### `MapEmbed`
- Iframe OpenStreetMap centrée sur les coordonnées de l'annonce
- Zoom fixe (niveau 15)
- Marqueur de position via l'URL de l'API OSM

#### `InfoBadges`
- Surface en m²
- Nombre de pièces
- Ville (nom uniquement, sans code postal)

#### `TimerDisplay`
- Décompte circulaire visuel
- Couleur progressivement rouge quand le temps s'épuise (< 10s)

#### `PriceInput`
- Champ `<input type="tel">` (évite le clavier décimal sur iOS)
- Formatage temps réel avec espaces de séparation (ex: `299 000`)
- Pas de focus automatique à l'arrivée sur la manche

#### `AnimatedNumber`
- Compteur qui s'anime vers la valeur cible (requestAnimationFrame)
- Utilisé pour afficher le score final

#### `ResultScreen`
- Comparaison estimation / prix réel
- Score de précision + bonus temps détaillés
- Bouton "Voir l'annonce originale" (`target="_blank"`, `rel="noopener noreferrer"`)

#### `GameOverScreen`
- Score total animé
- Tableau de toutes les manches
- Bouton "Rejouer"

---

## 11. Comportement mobile

### 11.1 Viewport fixe
La page est configurée pour ne pas être scrollable au niveau du navigateur (`overflow: hidden` sur `body`). Cela reproduit le comportement d'une application mobile native et évite les conflits avec le scroll du navigateur.

### 11.2 Zone de contenu scrollable
La zone photos / carte / informations (haut de l'écran en mode jeu) est scrollable verticalement via un conteneur `overflow-y-auto` interne.

### 11.3 Gestion du clavier
Le champ d'estimation n'est pas focalisé automatiquement pour éviter l'apparition non sollicitée du clavier virtuel, particulièrement gênant sur les petits écrans (le clavier masque la moitié de l'interface).

### 11.4 Swipe
- Swipe horizontal sur les photos → photo suivante / précédente
- Swipe vertical sur les photos → scroll vertical dans la zone de contenu (comportement natif préservé grâce à `touch-action: pan-y`)

---

## 12. Infrastructure et déploiement

### 12.1 Environnement PoC actuel

| Composant | Solution |
|---|---|
| Hébergement frontend | GitHub Pages (gratuit, public) |
| CI/CD | GitHub Actions |
| Scraping automatique | GitHub Actions (cron) |
| Base de données | Fichier `apartments.json` statique |
| Backend | Non déployé (local uniquement) |

### 12.2 Workflows GitHub Actions

#### `deploy.yml` — Déploiement
- **Déclencheur** : push sur `main`
- **Étapes** : checkout → `npm ci` → `npm run build` → deploy GitHub Pages
- **Durée** : ~25 secondes

#### `refresh-listings.yml` — Rafraîchissement des données
- **Déclencheur** : cron 06h00 / 18h00 UTC + déclenchement manuel
- **Étapes** : checkout → install Python deps → `scripts/export_listings.py` → commit si changements → push
- **Durée** : ~5 minutes (scraping avec délais anti-détection)
- **Effet secondaire** : le push déclenche automatiquement `deploy.yml`

### 12.3 Configuration frontend

| Variable | Fichier | Valeur par défaut | Rôle |
|---|---|---|---|
| `VITE_API_URL` | `.env.local` | `` (vide) | URL de l'API backend. Si vide, fallback JSON statique |

### 12.4 Fallback données
Si `VITE_API_URL` est vide ou si l'API ne répond pas, le frontend charge silencieusement `apartments.json` (données statiques). Aucune erreur visible pour l'utilisateur.

### 12.5 Roadmap infrastructure (après PoC)

- Déploiement du backend FastAPI sur un VPS ou PaaS (Railway, Render…)
- Branchement du frontend sur l'API (`VITE_API_URL`)
- Mirroring des photos sur un bucket S3-compatible (URLs stables)
- Suppression automatique des annonces non vues depuis > 7 jours

---

## 13. Sécurité et données sensibles

### 13.1 Ce qui est dans le dépôt public
- Code source frontend et backend (sans credentials)
- Fichiers `.env.example` avec des valeurs placeholder uniquement
- `apartments.json` : données publiques issues d'annonces immobilières publiques

### 13.2 Ce qui est exclu du dépôt
Fichiers listés dans `.gitignore` :
- `backend/.env` (credentials base de données, clés S3, etc.)
- `.env` / `.env.local` (variables Vite avec URL API)
- `node_modules/`, `.venv/`, `dist/`, `__pycache__/`

### 13.3 Credentials de développement
Les credentials présents dans `docker-compose.yml` (`justeprix` / `justeprix`) sont des valeurs de développement local sans valeur pour un attaquant. Ils ne sont **jamais** utilisés en production.

### 13.4 Données personnelles
- Aucune donnée personnelle des utilisateurs n'est collectée (pas de compte, pas de tracking)
- Les données scrappées sont des annonces immobilières publiques (prix, surface, photos) sans information personnelle des vendeurs

---

## 14. Évolutions prévues

### Court terme (avant mise en production)
- [ ] Déploiement du backend FastAPI (VPS ou PaaS)
- [ ] Branchement frontend → API backend
- [ ] Mirroring photos sur CDN stable (Laforêt CDN peut changer)
- [ ] Implémentation du scraper SeLoger (Playwright stealth)
- [ ] Augmentation du corpus PAP (+ de pages, + de villes)

### Moyen terme
- [ ] Système de compte utilisateur (progression, historique)
- [ ] Leaderboard / classement national et par ville
- [ ] Mode multijoueur (défi entre amis)
- [ ] Extension aux maisons
- [ ] Extension à la location

### Long terme
- [ ] Application mobile native (React Native ou PWA)
- [ ] Partenariat avec agences pour accès direct aux données
- [ ] Mode "expert" avec informations sur le quartier, DPE, etc.

---

## 15. Glossaire

| Terme | Définition |
|---|---|
| **Annonce** | Fiche d'un bien immobilier à la vente, issue d'un scraping |
| **Manche** | Une session d'estimation sur un appartement |
| **Partie** | Ensemble de 10 manches consécutives |
| **Métropole** | Zone géographique centrée sur une grande ville, avec un rayon de proximité |
| **Pipeline** | Chaîne de traitement : scraping → normalisation → validation → déduplication → export |
| **Scraper** | Module Python chargé de collecter les annonces sur un site source |
| **PoC** | Proof of Concept — version de démonstration avant mise en production |
| **CDN** | Content Delivery Network — réseau de distribution de contenu (ici, les photos) |
| **Haversine** | Formule de calcul de distance entre deux points GPS sur une sphère |
| **Géocodage** | Conversion d'une adresse textuelle en coordonnées GPS (lat/lng) |
| **Fallback** | Comportement de repli en cas d'indisponibilité du service principal |
| **SFD** | Spécifications Fonctionnelles Détaillées — ce document |
