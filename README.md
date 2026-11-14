# Paint Amélioré

![tests](https://github.com/hugo94z/paint-amelior/actions/workflows/tests.yml/badge.svg)

Clone de Paint réécrit en Python, avec PySide6 et numpy. Pensé pour être **plus rapide** qu'un Paint classique et **plus agréable** au quotidien : onglets, calques, sélection avancée, filtres avec aperçu, animation et installateur Windows.

## Fonctionnalités

- **Multi-documents** : onglets, zoom et historique indépendants, fermeture protégée.
- **Pinceau / gomme** : taille, opacité, dureté, espacement, **pression de tablette**, ligne droite `Maj+clic`, aperçu du trait.
- **Pot de peinture** vectorisé numpy, tolérance, respect des sélections et des masques.
- **Formes** : ligne, rectangle, ellipse, rectangle arrondi, polygone, dégradé linéaire/radial.
- **Texte** avec police, taille, gras, italique, retour à la ligne.
- **Sélection avancée** : rectangle, lasso, **baguette magique** (contigu/global, tous calques), **contour progressif**, modes remplacer/ajouter/soustraire/intersecter, inversion, déplacement, copier/couper/coller, **transformation** (rotation, échelle, miroirs).
- **Recadrage** avec règle des tiers et **taille du canevas** avec ancrage.
- **Calques** : vignettes, glisser-déposer, duplication, fusion, **masques de fusion**, **calques de réglage non destructifs**, verrouillage, verrouillage alpha, 12 modes de fusion.
- **Filtres avec aperçu en direct** : flou gaussien, netteté, luminosité, contraste, saturation, **niveaux**, **teinte**, **vignettage**, **flou directionnel**, niveaux de gris, pixelisation, inversion.
- **Historique par tuiles** avec budget mémoire configurable, annuler/rétablir.
- **Image** : redimensionnement, rotations 90°/180°, miroirs, recadrage, taille du canevas — tous annulables.
- **Formats** : projet `.paint` (calques, masques, réglages, images d'animation), export PNG/JPEG/WebP/BMP/TIFF, **PDF**, **SVG**, **GIF/APNG**, import **PSD aplati**, **traitement par lot** (UI et CLI).
- **Animation** : capture d'images, durée par image, lecture, export GIF/APNG.
- **Confort** : onglets, glisser-déposer, documents récents, **autosave et récupération après crash**, grille, thème clair/sombre, palette de commandes `Ctrl+K`, plugins Python, vérification des mises à jour.
- **Zoom** 5 % à 3200 %, ascenseurs, sélecteur de zoom, ajustement automatique.

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
Mémoire allouée à l'application : 15008 Mo
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
| Baguette magique / Recadrage | `W` / `C` |
| Taille du pinceau | `[` `]` |
| Ligne droite au pinceau | `Maj+clic` |
| Pipette temporaire | `Alt` |
| Échanger avant-plan / arrière-plan | `X` |
| Annuler / Rétablir | `Ctrl+Z` / `Ctrl+Y` |
| Copier / Couper / Coller | `Ctrl+C` `Ctrl+X` `Ctrl+V` |
| Tout sélectionner / Désélectionner | `Ctrl+A` / `Ctrl+D` |
| Inverser la sélection | `Ctrl+Maj+I` |
| Transformer la sélection | `Ctrl+T` |
| Palette de commandes | `Ctrl+K` |
| Grille | `Ctrl+G` |
| Nouveau / Ouvrir / Enregistrer | `Ctrl+N` `Ctrl+O` `Ctrl+S` |
| Zoom / ajuster / taille réelle | `Ctrl+molette` / `Ctrl+0` / `Ctrl+1` |
| Déplacement du canevas | `Espace + glisser` ou bouton du milieu |
| Ouvrir une image | glisser-déposer sur le canevas |
| Recadrer | outil `C` puis `Entrée` |

## Architecture

```
paint/
  app.py            fenêtre, onglets, menus, actions, E/S, session
  canvas.py         rendu : zoom, pan, dirty-rect, fourmis, grille, tablette
  document.py       calques, masques, réglages, sélection, transformations
  history.py        transactions et historique par tuiles 128×128
  brush.py          tampons, cache LRU, buffer de trait
  filters.py        flood fill numpy + filtres Pillow
  autosave.py       sauvegarde de secours et récupération
  batch.py          conversion par lot (UI et CLI)
  hardware.py       détection matérielle et allocation
  plugins.py        chargement des plugins Python
  updater.py        vérification des releases GitHub
  io/               images, projets, PDF/SVG, animations
  tools/            un outil par fichier
  ui/               toolbar, options, docks, thème, icônes, filtres
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

Tests automatisés sur Python 3.11, 3.12 et 3.13 via GitHub Actions.

## Formats

- **.paint** : archive zip contenant `project.json`, un PNG par calque, les masques et les images d'animation.
- **PNG** (transparence conservée), **JPEG/BMP** (fond blanc automatique), **WebP**, **TIFF**.
- **PDF** (page à la taille de l'image), **SVG**, **GIF/APNG** depuis les images d'animation.
- **PSD** : import de l'image aplatie.
- **Traitement par lot** : `python -m paint.batch source sortie --width 1920 --format jpg`.

## Animation

Le dock **Animation** (Affichage → Animation) permet de capturer l'image courante, dupliquer, régler la durée, lire la séquence et exporter en GIF ou APNG.

## Autosave et récupération

Les documents modifiés sont sauvegardés toutes les 90 secondes dans `%LOCALAPPDATA%\PaintAmeliore\autosave`. Au démarrage suivant, l'application propose de restaurer les documents retrouvés après un arrêt brutal. Une sauvegarde normale efface l'autosave correspondant.

## Plugins

Déposez un fichier `.py` dans `plugins/` exposant `register(api)`. L'API fournit `api.add_action(texte, callback, raccourci)`, `api.document` et `api.notify`. Exemple fourni : `plugins/exemple.py`.

## Build et publication

```powershell
.\build.ps1                 # executable autonome + dist\Paint-Ameliore-win64.zip
```

Un tag `v1.5.0` déclenche le workflow GitHub Actions qui construit l'exécutable et publie la release ; l'application vérifie ensuite les mises à jour via l'API GitHub. Un manifeste winget est fourni dans `packaging/winget/`.

## Limites connues (1.5)

- Les **groupes de calques** et **styles de calque** (ombre/contour) ne sont pas encore implémentés.
- Import PSD **aplati** uniquement (pas de calques PSD).
- Interface en français uniquement.
- Règles/repères avec magnétisme non inclus (grille d'affichage disponible).
