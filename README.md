# Paint Amélioré

Clone de Paint réécrit en Python, avec PySide6 et numpy. Pensé pour être **plus rapide** qu'un Paint classique et **plus agréable** au quotidien : calques, sélection, filtres, zoom fluide, raccourcis clavier.

## Fonctionnalités

- **Pinceau / gomme** avec taille, opacité, dureté, espacement des tampons et aperçu du trait.
- **Pot de peinture** vectorisé numpy (remplissage par régions, tolérance réglable, respect de la sélection).
- **Formes** : ligne, rectangle, ellipse, rectangle arrondi, polygone, dégradé linéaire/radial.
- **Texte** avec police, taille, gras, italique, retour à la ligne automatique.
- **Sélection** rectangle et lasso, déplacement des pixels, copier/couper/coller, effacement, fourmis animées.
- **Calques** : ajout, duplication, suppression, réorganisation, fusion vers le bas, opacité, modes de fusion.
- **Filtres** : flou gaussien, netteté, luminosité, contraste, saturation, niveaux de gris, pixelisation, inversion.
- **Historique par tuiles** avec budget mémoire configurable (annuler/rétablir illimité en pratique).
- **Formats** : projet `.paint` non destructif (zip + PNG par calque) et export PNG/JPEG/WebP/BMP/TIFF.
- **Zoom** 5 % à 3200 % centré sur le curseur, déplacement au clavier/souris, ajustement automatique.
- Thème sombre, interface française, barre d'options contextuelle, palette et couleurs récentes.

## Installation depuis GitHub

Remplacez `hugo94z/paint-amelior` par votre dépôt si nécessaire.

```powershell
$repo = "hugo94z/paint-amelior"
iwr -useb "https://raw.githubusercontent.com/$repo/main/install.ps1" -OutFile "$env:TEMP\paint-install.ps1"
& "$env:TEMP\paint-install.ps1" -Repo $repo
```

Ou, depuis un clone local :

```powershell
.\install.cmd
```

L'installateur :

1. récupère le projet depuis GitHub (archive zip, repli sur `git clone`) ou depuis le dossier local ;
2. vérifie Python 3.10+ et crée un environnement virtuel isolé (repli automatique sur une installation locale dans `libs/` si le module `venv` manque) ;
3. installe PySide6, numpy et Pillow ;
4. **scanne la configuration du PC** (processeur, cœurs physiques/logiques, RAM, carte graphique) et écrit `hardware.json` ;
5. **alloue les ressources** : threads de travail, budget mémoire de l'application, budget de l'historique, cache des pinceaux ;
6. crée un lanceur et des raccourcis Bureau / menu Démarrer.

Exemple de scan :

```
Processeur : AMD Ryzen 7 PRO 5850U with Radeon Graphics
Cœurs physiques : 8  •  cœurs logiques : 16
Mémoire vive : 31.3 Go
Threads alloués à l'application : 15
Mémoire allouée à l'application : 15360 Mo
Budget historique (annuler) : 4096 Mo
```

Pour installer ailleurs : `.\install.ps1 -InstallDir "D:\Apps\Paint" -Repo "utilisateur/depot" -Branch main`.
Sans raccourcis : `-NoShortcut`. Désinstallation : `uninstall.ps1` (ou `-Force`).

## Lancement manuel (développement)

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python run.py
```

## Raccourcis

| Action | Touche |
| --- | --- |
| Pinceau / Gomme / Pot / Pipette | `B` `E` `G` `I` |
| Ligne / Rectangle / Ellipse / Arrondi | `L` `R` `O` `U` |
| Polygone / Dégradé / Texte / Sélection | `Y` `D` `T` `M` |
| Taille du pinceau | `[` `]` |
| Pipette temporaire | `Alt` |
| Annuler / Rétablir | `Ctrl+Z` / `Ctrl+Y` |
| Copier / Couper / Coller | `Ctrl+C` `Ctrl+X` `Ctrl+V` |
| Tout sélectionner / Désélectionner | `Ctrl+A` / `Ctrl+D` |
| Nouveau / Ouvrir / Enregistrer | `Ctrl+N` `Ctrl+O` `Ctrl+S` |
| Zoom / ajuster / taille réelle | `Ctrl+molette` / `Ctrl+0` / `Ctrl+1` |
| Déplacement du canevas | `Espace + glisser` ou bouton du milieu |

## Architecture

```
paint/
  app.py            fenêtre, menus, actions, E/S
  canvas.py         rendu : zoom, pan, dirty-rect, fourmis
  document.py       calques, composite mis en cache, sélection
  history.py        transactions et historique par tuiles 128×128
  brush.py          tampons, cache LRU, buffer de trait
  filters.py        flood fill numpy + filtres Pillow
  hardware.py       détection matérielle et allocation
  tools/            un outil par fichier
  ui/               toolbar, options, docks, thème, icônes
```

Choix de performance :

- recomposition **uniquement du rectangle sale** et blit limité au viewport ;
- trait dessiné dans un **buffer de stroke** puis fusionné une seule fois (pas d'accumulation d'opacité) ;
- gomme calculée sur une copie du viewport, jamais sur toute l'image ;
- remplissage par **runs de lignes** vectorisés, avec chemin rapide pour une zone uniforme ;
- historique **par tuiles** : seules les zones touchées sont copiées ;
- cache de tampons LRU borné par la mémoire allouée.

Mesures de référence (Ryzen 7 5850U, canevas 3840×2160, bench inclus) :

| Opération | Temps |
| --- | --- |
| Trait de ~1500 tampons | ~18 ms |
| Recomposition des calques | ~9 ms |
| Remplissage complet | ~300 ms |
| Export PNG 4K | ~220 ms |
| Annuler une zone 512×512 | < 1 ms |

```powershell
python -m pytest tests -q
python benchmarks\bench.py
```

## Formats

- **.paint** : archive zip contenant `project.json` et un PNG par calque (opacité, mode de fusion, visibilité, ordre et calque actif).
- **PNG** (transparence conservée), **JPEG/BMP** (fond blanc automatique), **WebP**, **TIFF**.
