# claude-tasks-mcp

Petit serveur MCP personnel qui permet à Claude Code de lire et d'écrire dans les listes **Google Tasks** de son propriétaire.

- Usage strictement personnel : un seul utilisateur (le propriétaire du compte Google).
- Portée demandée : `https://www.googleapis.com/auth/tasks` (Google Tasks uniquement).
- Aucun serveur distant : le code s'exécute en local, le jeton reste sur le poste (`token.json`, non versionné).

## Installation

1. Créer un projet Google Cloud, activer l'API Google Tasks, créer un ID client OAuth « Application de bureau » et l'enregistrer sous `client_secret.json` à côté de `server.py`.
2. `pip install -r requirements.txt`
3. `python server.py --login` (autorise l'accès dans le navigateur)
4. Déclarer le serveur dans Claude Code : `claude mcp add google-tasks -- python server.py`

Voir [PRIVACY.md](PRIVACY.md) pour les règles de confidentialité.
