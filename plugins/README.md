# Plugins

Chaque fichier `.py` de ce dossier est chargé au démarrage. Il doit exposer :

```python
def register(api):
    api.add_action("Mon action", mon_callback, "Ctrl+Alt+M")

def mon_callback(window):
    window.notify("Bonjour")
```

API disponible :

- `api.add_action(texte, callback, raccourci="")` : ajoute une action au menu Outils.
- `api.document` : document actif (ou `None`).
- `api.notify(message)` : message dans la barre d'état.

`plugins/exemple.py` ajoute une bordure au calque actif.
