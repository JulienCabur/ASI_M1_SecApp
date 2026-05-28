# SécuApp
## Contributors
RUELLE Thomas - etu51177  
DEMIR Erdem - etu51195  
CLAUS Gatien - etu51716  
MOMBAERTS Ciaran - etu51729  

## Description

Application web de gestion de dossiers médicaux avec authentification forte. Le backend est en Python (FastAPI), le frontend en React/TypeScript. L'identité est gérée par Keycloak (OIDC). Les médecins disposent en plus d'une authentification par certificat X.509 émis par une PKI interne à trois niveaux. Les fichiers médicaux sont chiffrés côté client (chiffrement de bout en bout) : le serveur ne manipule jamais le contenu en clair. Les logs d'audit sont centralisés dans une stack ELK (Elasticsearch, Logstash, Kibana).

## Prérequis

- Docker et Docker Compose
- pnpm (pour le build du frontend)
- Node.js >= 18

## Architecture des services

| Service | URL locale | Description |
|---|---|---|
| Application (Nginx) | https://localhost | Frontend + reverse proxy vers le backend |
| Backend (FastAPI) | http://localhost:8081 | API REST (accès direct, hors Nginx) |
| Keycloak | http://localhost:8080 / https://localhost:8443 | Fournisseur d'identité OIDC |
| Kibana | http://localhost:5601 | Dashboards et alertes ELK |
| Elasticsearch | http://localhost:9200 | Moteur de recherche/indexation des logs |
| PostgreSQL | localhost:5432 | Base de données (Keycloak + backend) |
| Mailcatcher | http://localhost:1080 | Serveur mail de développement (SMTP : 1025) |

## Deployment

### 1. Préparer l'environnement

Dans le dossier `.build`, créer un fichier `.env` à partir du modèle :

```bash
cp .build/env.example .build/.env
```

Ou utiliser le script fourni :

```bash
# Linux/macOS
bash .build/env-creation.sh

# Windows (PowerShell)
.\.build\env-creation.ps1
```

Puis éditer `.build/.env` et remplacer toutes les valeurs `A_CHANGER_*` par des mots de passe aléatoires. La clé `XPACK_ENCRYPTION_KEY` doit faire au minimum 32 caractères.

### 2. Créer le dossier secrets

Ce dossier est nécessaire pour que la PKI y dépose les certificats générés :

```bash
mkdir .build/secrets
```

### 3. Builder le frontend

Le frontend est servi comme des fichiers statiques par Nginx. Il faut donc le compiler avant de lancer Docker :

```bash
cd src/site
pnpm install
pnpm build
```

### 4. Démarrer le projet

```bash
cd .build
docker-compose up -d
```

Au premier démarrage, la PKI génère automatiquement tous les certificats, puis les services démarrent dans l'ordre. L'opération peut prendre une à deux minutes.

L'instance Keycloak est accessible via : http://localhost:8080 ou https://localhost:8443  
L'application est accessible via : https://localhost

---

### Exporter la configuration Keycloak

En cas de modification de la configuration du Keycloak, à la fin :

```bash
docker exec -it keycloak /opt/keycloak/bin/kc.sh export --file /opt/keycloak/conf/realm-export.json --realm health_app --users same_file
docker cp keycloak:/opt/keycloak/conf/realm-export.json .\keycloak\import\realm-export.json
```

### Exporter la configuration Kibana

En cas de modification de la configuration de Kibana (Data Views, Règles d'alerte), à la fin :

```bash
cd .build/elk-stack/setup
ELASTIC_PASSWORD="<mot_de_passe_elastic>" bash export-kibana.sh
```

Cela met à jour le fichier `.build/elk-stack/setup/kibana_export.ndjson`.
Au prochain `docker-compose up`, la configuration est automatiquement réimportée dans Kibana.

### Supprimer les volumes

```bash
docker compose down -v
```

Attention, il faut également vider les différents fichiers générés par la pki du dossier .build/secrets.
Pour ce faire, un autre script est mis à disposition :
```bash
# Linux/macOS
bash .build/clean-secrets.sh

# Windows (PowerShell)
.\.build\clean-secrets.ps1
```

### Redémarrer le backend après modification

```bash
docker compose down backend
docker-compose build --no-cache backend
docker compose up backend -d
```

### Redémarrer le frontend après modification

```bash
cd src/site
pnpm build
```

Les fichiers compilés dans `src/site/dist/` sont montés directement dans le conteneur Nginx, aucun redémarrage de conteneur n'est nécessaire.

## Développement

Pour travailler sur le frontend avec le rechargement automatique :

```bash
cd src/site
pnpm dev
```

Le serveur de développement Vite démarre sur http://localhost:5173. Il faut que la stack Docker soit déjà en cours d'exécution pour que les appels API fonctionnent.

## Stack technique

**Backend**
- Python 3.13, FastAPI, SQLAlchemy 2, PostgreSQL (psycopg2)
- Authentification : PyJWT, python-keycloak, itsdangerous (sessions HMAC)
- Cryptographie : bibliothèque `cryptography` (X.509, RSA, PSS)

**Frontend**
- React 19, TypeScript, Vite
- UI : Ant Design 6
- État global : Zustand
- Crypto client : node-forge (génération de CSR, chiffrement)

**Infrastructure**
- Keycloak 23 (OIDC, Authorization Code + PKCE)
- Nginx (reverse proxy, TLS)
- PKI OpenSSL 3 niveaux : Root CA, Signing CA 1 (médecins), Signing CA 2 (services)
- ELK 9.3 : Elasticsearch, Logstash, Kibana