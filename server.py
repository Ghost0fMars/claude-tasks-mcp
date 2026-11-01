"""Serveur MCP Google Tasks (perso, compte Gmail d'Étienne).

Outils : listes (lister, créer, renommer) et tâches (lister, créer, modifier, terminer, rouvrir, supprimer).
Autorisation OAuth « application de bureau », seul droit demandé : tasks.
Fichiers à côté du script : client_secret.json (à télécharger depuis Google Cloud), token.json (créé à la 1re connexion).

python server.py --login   -> ouvre le navigateur pour autoriser l'accès, écrit token.json
python server.py           -> serveur MCP (stdio), lancé par Claude Code
"""
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

DOSSIER = Path(__file__).resolve().parent
SECRET = DOSSIER / "client_secret.json"
TOKEN = DOSSIER / "token.json"
SCOPES = ["https://www.googleapis.com/auth/tasks"]

mcp = FastMCP("google-tasks")


def _identifiants(interactif=False):
    cred = Credentials.from_authorized_user_file(TOKEN, SCOPES) if TOKEN.exists() else None
    if cred and cred.expired and cred.refresh_token:
        cred.refresh(Request())
    elif not cred or not cred.valid:
        if not interactif:
            raise RuntimeError("Pas de connexion Google : lancer « python server.py --login » une fois.")
        cred = InstalledAppFlow.from_client_secrets_file(SECRET, SCOPES).run_local_server(port=0)
    TOKEN.write_text(cred.to_json(), encoding="utf-8")
    return cred


def _api():
    return build("tasks", "v1", credentials=_identifiants(), cache_discovery=False)


def _rfc3339(jour):
    """'2026-11-05' -> '2026-11-05T00:00:00.000Z' (Google Tasks ne garde que la date)."""
    return f"{jour}T00:00:00.000Z" if jour and "T" not in jour else jour


def _liste_id(api, nom_ou_id):
    """Accepte un identifiant ou le titre exact d'une liste."""
    listes = api.tasklists().list(maxResults=100).execute().get("items", [])
    for l in listes:
        if nom_ou_id in (l["id"], l["title"]):
            return l["id"]
    raise ValueError(f"Liste introuvable : {nom_ou_id}. Listes : {[l['title'] for l in listes]}")


def _tache(t):
    return {"id": t["id"], "titre": t.get("title", ""), "echeance": (t.get("due") or "")[:10],
            "notes": t.get("notes", ""), "statut": t.get("status", "")}


@mcp.tool()
def lister_listes() -> list[dict]:
    """Liste les listes de tâches (id et titre)."""
    return [{"id": l["id"], "titre": l["title"]}
            for l in _api().tasklists().list(maxResults=100).execute().get("items", [])]


@mcp.tool()
def creer_liste(titre: str) -> dict:
    """Crée une liste de tâches. Ne fait rien si une liste du même titre existe déjà."""
    api = _api()
    for l in api.tasklists().list(maxResults=100).execute().get("items", []):
        if l["title"] == titre:
            return {"id": l["id"], "titre": titre, "deja_existante": True}
    l = api.tasklists().insert(body={"title": titre}).execute()
    return {"id": l["id"], "titre": l["title"], "deja_existante": False}


@mcp.tool()
def renommer_liste(liste: str, nouveau_titre: str) -> dict:
    """Renomme une liste (identifiée par son titre ou son id)."""
    api = _api()
    l = api.tasklists().patch(tasklist=_liste_id(api, liste), body={"title": nouveau_titre}).execute()
    return {"id": l["id"], "titre": l["title"]}


@mcp.tool()
def lister_taches(liste: str, avec_terminees: bool = False) -> list[dict]:
    """Liste les tâches d'une liste (titre ou id). Par défaut seulement celles à faire."""
    api = _api()
    lid, out, page = _liste_id(api, liste), [], None
    while True:
        r = api.tasks().list(tasklist=lid, showCompleted=avec_terminees, showHidden=avec_terminees,
                             maxResults=100, pageToken=page).execute()
        out += [_tache(t) for t in r.get("items", [])]
        page = r.get("nextPageToken")
        if not page:
            return out


@mcp.tool()
def creer_tache(liste: str, titre: str, echeance: str = "", notes: str = "") -> dict:
    """Crée une tâche. echeance au format AAAA-MM-JJ (facultatif). Ne crée pas de doublon :
    si une tâche à faire porte déjà ce titre dans la liste, elle est renvoyée telle quelle."""
    api = _api()
    lid = _liste_id(api, liste)
    for t in lister_taches(liste):
        if t["titre"] == titre:
            return {**t, "deja_existante": True}
    corps = {"title": titre}
    if echeance:
        corps["due"] = _rfc3339(echeance)
    if notes:
        corps["notes"] = notes
    return {**_tache(api.tasks().insert(tasklist=lid, body=corps).execute()), "deja_existante": False}


@mcp.tool()
def modifier_tache(liste: str, tache_id: str, titre: str = "", echeance: str = "", notes: str = "") -> dict:
    """Modifie le titre, l'échéance (AAAA-MM-JJ) ou les notes d'une tâche ; les champs vides ne changent pas."""
    api = _api()
    corps = {k: v for k, v in (("title", titre), ("due", _rfc3339(echeance)), ("notes", notes)) if v}
    return _tache(api.tasks().patch(tasklist=_liste_id(api, liste), task=tache_id, body=corps).execute())


@mcp.tool()
def terminer_tache(liste: str, tache_id: str) -> dict:
    """Marque une tâche comme terminée."""
    api = _api()
    return _tache(api.tasks().patch(tasklist=_liste_id(api, liste), task=tache_id,
                                    body={"status": "completed"}).execute())


@mcp.tool()
def rouvrir_tache(liste: str, tache_id: str) -> dict:
    """Remet une tâche terminée à faire."""
    api = _api()
    return _tache(api.tasks().patch(tasklist=_liste_id(api, liste), task=tache_id,
                                    body={"status": "needsAction", "completed": None}).execute())


@mcp.tool()
def supprimer_tache(liste: str, tache_id: str) -> str:
    """Supprime définitivement une tâche (à n'utiliser que sur demande explicite)."""
    api = _api()
    api.tasks().delete(tasklist=_liste_id(api, liste), task=tache_id).execute()
    return "supprimée"


if __name__ == "__main__":
    if "--login" in sys.argv:
        _identifiants(interactif=True)
        print("Connexion enregistrée dans", TOKEN)
    else:
        mcp.run()
