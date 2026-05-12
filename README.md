# SécuApp

Dans le dossier .build
    Créer un fichier .env suivant le modèle env.example
Dans le dossier .build/pki
    Créer un fichier .env suivant le modèle pkienv.example
il faut créer le dossier .build/secrets avant de deploy
Pour démarrer le projet :

```bash
cd ./.build
docker-compose up -d
```

L'instance keycloak est accessbile via l'url : http://localhost:8080 ou https://localhost:8443

En cas de modification de la configuration du Keycloak, à la fin :

```bash
docker exec -it keycloak /opt/keycloak/bin/kc.sh export --file /opt/keycloak/conf/realm-export.json --realm health_app --users same_file
docker cp keycloak:/opt/keycloak/conf/realm-export.json .\keycloak\import\realm-export.json
```

En cas de modification de la configuration de Kibana (Data Views, Règles d'alerte), à la fin :

```bash
cd .build/elk-stack/setup
ELASTIC_PASSWORD="<mot_de_passe_elastic>" bash export-kibana.sh
```

Cela met à jour le fichier `.build/elk-stack/setup/kibana_export.ndjson`
Au prochain `docker-compose up`, la configuration est automatiquement réimportée dans Kibana.

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