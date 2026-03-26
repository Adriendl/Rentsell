# 🏠 JustePrix Immo

> Jeu d'estimation de prix immobilier basé sur de vraies annonces françaises.

**🎮 Jouer maintenant → [adriendl.github.io/Rentsell](https://adriendl.github.io/Rentsell/)**

---

## C'est quoi ?

JustePrix Immo te présente de vraies annonces de vente d'appartements en France (photos, carte, surface, ville) et tu as **60 secondes** pour deviner le prix. Plus tu es précis et rapide, plus tu marques de points.

- 🗓️ **10 manches** par partie
- 🏙️ Joue sur **toute la France** ou filtre sur une **métropole**
- 📱 Conçu pour le **mobile** (swipe, clavier adapté, plein écran)
- 🔄 Les annonces sont **rafraîchies automatiquement** 2× par jour via scraping

---

## Règles du jeu

| Écart avec le vrai prix | Points précision |
|---|---|
| Exact | 1 000 pts |
| ≤ 5 % | 800 pts |
| ≤ 10 % | 600 pts |
| ≤ 15 % | 400 pts |
| ≤ 25 % | 200 pts |
| ≤ 40 % | 100 pts |
| > 40 % | 0 pt |

**+ Bonus temps** : jusqu'à 200 pts selon le temps restant.
**Score max** : 1 200 pts/manche × 10 = **12 000 pts**.

---

## Stack technique

**Frontend**
- React 18 + Vite
- Tailwind CSS v4 (dark mode)
- Lucide React (icônes)
- OpenStreetMap (carte)

**Backend** *(local / futur déploiement)*
- Python 3.12 · FastAPI · SQLAlchemy 2 async
- PostgreSQL 16 · Redis · Celery
- httpx + BeautifulSoup4 (scraping)

**CI/CD**
- GitHub Actions : déploiement automatique + scraping 2×/jour

---

## Lancer le projet en local

### Prérequis
- Node.js 22+
- Python 3.12+
- Docker Desktop

### Frontend uniquement (données statiques)

```bash
git clone https://github.com/Adriendl/Rentsell.git
cd Rentsell
npm install
npm run dev
# → http://localhost:5173
```

### Avec le backend complet

```bash
# 1. Variables d'environnement
cp backend/.env.example backend/.env

# 2. Démarrer PostgreSQL, Redis et l'API
docker compose up -d

# 3. Installer les dépendances Python
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 4. Charger les données initiales
cd .. && backend/.venv/bin/python scripts/seed.py

# 5. Frontend connecté à l'API
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
```

### Rafraîchir les annonces manuellement

```bash
backend/.venv/bin/python scripts/export_listings.py
```

---

## Données immobilières

Les annonces proviennent de sites publics français :

| Source | Statut | Villes |
|---|---|---|
| [Laforêt Immobilier](https://www.laforet.com) | ✅ Actif | 83 agences / 10 métropoles |
| [PAP.fr](https://www.pap.fr) | ✅ Actif | 10 métropoles |
| SeLoger | 🔜 Prévu | — |

**Volume actuel** : ~1 300 annonces · ~190 villes

Le script de scraping tourne automatiquement dans GitHub Actions chaque jour à **06h00 et 18h00 UTC**. Si des nouvelles annonces sont détectées, `apartments.json` est mis à jour et le site redéployé automatiquement.

---

## Structure du projet

```
├── JustePrixImmo.jsx          # Composant principal du jeu
├── apartments.json            # Base de données statique (auto-générée)
├── src/
│   ├── App.jsx
│   ├── main.jsx
│   └── hooks/
│       └── useFetchListings.js  # Hook API avec fallback JSON
├── backend/
│   ├── app/
│   │   ├── api/               # Routes FastAPI (listings, cities)
│   │   ├── scrapers/          # Laforêt, PAP, SeLoger (squelette)
│   │   ├── pipeline/          # Normalisation, validation, déduplication
│   │   └── worker/            # Celery tasks + scheduler
│   └── tests/
├── scripts/
│   ├── export_listings.py     # Scrape → apartments.json (sans BDD)
│   ├── seed.py                # Charge apartments.json en PostgreSQL
│   └── run_scraper.py         # Lancement manuel d'un scraper
├── .github/workflows/
│   ├── deploy.yml             # Déploiement GitHub Pages
│   └── refresh-listings.yml   # Scraping automatique 2×/jour
└── docs/
    └── SFD.md                 # Spécifications Fonctionnelles Détaillées
```

---

## Sélection géographique

La sélection par métropole utilise la **distance de Haversine** : une annonce à Boulogne-Billancourt apparaît dans le mode Paris, Carquefou dans le mode Nantes, Antibes dans le mode Nice, etc.

| Métropole | Rayon |
|---|---|
| Paris 🗼 | 25 km |
| Marseille ⛵ | 25 km |
| Nice 🌴 | 25 km |
| Lyon 🦁 | 20 km |
| Toulouse 🚀 | 20 km |
| Nantes 🐘 | 20 km |
| Bordeaux 🍷 | 20 km |
| Montpellier ☀️ | 20 km |
| Strasbourg 🥨 | 20 km |
| Lille 🧱 | 20 km |

---

## Statut du projet

> **Proof of Concept** — en phase de tests bêta fermée.

- [x] Jeu fonctionnel (10 manches, score, chrono)
- [x] Vraies photos et annonces scrappées
- [x] Sélection par métropole avec proximité géographique
- [x] Refresh automatique 2×/jour
- [x] Optimisé mobile (swipe, viewport fixe)
- [x] Backend Python complet (local)
- [ ] Déploiement backend en production
- [ ] Leaderboard / comptes utilisateurs
- [ ] Scraper SeLoger
- [ ] Mode location

---

## Documentation

La documentation fonctionnelle complète est disponible dans [`docs/SFD.md`](docs/SFD.md).

---

*Données issues d'annonces immobilières publiques. Projet à vocation pédagogique et ludique.*
