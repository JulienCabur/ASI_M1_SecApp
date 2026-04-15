# SécuApp

Dans le dossier .build
    Créer un fichier .env suivant le modèle env.example
Dans le dossier .build/pki
    Créer un fichier .env suivant le modèle pkienv.example
Pour démarrer le projet :

```bash
cd ./.build
docker-compose up -d
```

L'instance keycloak est accessbile via l'url : http://localhost:8080 ou https://localhost:8443

En cas de modification de la configuration du Keycloak, à la fin :

```bash
docker exec -it build-keycloak-1 /opt/keycloak/bin/kc.sh export --file /opt/keycloak/conf/realm-export.json --realm health_app --users same_file
docker cp build-keycloak-1:/opt/keycloak/conf/realm-export.json .\keycloak\import\realm-export.json
```

Pour supprimer le volume

```bash
docker compose down -v
```

Pour restart backend après modif :
```bash
docker compose down backend
docker-compose build --no-cache backend
docker compose up backend -d
```

Pour restart frontend après modif :
```bash
pnpm build
```