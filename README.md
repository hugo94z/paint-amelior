# Paint Amélioré

![tests](https://github.com/hugo94z/paint-amelior/actions/workflows/tests.yml/badge.svg)
![version](https://img.shields.io/badge/version-1.6.5-blue)

Clone de Paint réécrit en Python, avec PySide6 et numpy. Pensé pour être **plus rapide** qu'un Paint classique et **plus agréable** au quotidien : onglets, calques, sélection avancée, filtres avec aperçu, animation, impression et installateur Windows.

Version actuelle : **1.6.5** (affichée dans la barre d'état et dans Aide → À propos).

## Nouveautés 1.6.5

- **Groupes de calques** : dossiers imbriqués, visibilité et opacité de groupe, modes de fusion, glisser-déposer, dissolution et suppression, sauvegarde dans les projets.
- **Allocation de ressources adaptative** : RAM disponible réelle, marge système, budget par document, nombre de threads basé sur les cœurs physiques, réglages manuels dans les préférences.
- **Taille de feuille personnalisable** : unités px / mm / cm / pouces, DPI, orientation, verrou de ratio, aperçu, estimation mémoire et formats mémorisés.
- **Règles et repères aimantés**, rotation et miroir de la vue, **navigateur**.
- **Roue chromatique HSV**, hexadécimal, palettes nommées et couleurs mémorisées.
- **Préférences** : thème, sauvegarde automatique, budget d'annulation, format par défaut.
- **Impression** et aperçu avant impression, **export redimensionné** avec DPI et qualité.
- **Nouveaux outils** : tampon de clonage, densité (éclaircir/assombrir), goutte d'eau.
- **Presets de pinceaux**, embouts PNG, dispersion, **remplissage par motif**.
- **Styles de calque** : ombre portée et contour, annulables.
- **Import PSD multi-calques** (via `psd-tools`).
- **Performances** : remplissage 4K ~4,4× plus rapide, redimensionnement annulable, masques transformés avec les calques.

## Fonctionnalités

- **Multi-documents** : onglets, zoom et historique indépendants, fermeture protégée.
- **Feuille personnalisable** : presets papier (A0 → A6, Letter, Legal, Tabloid), photos, écrans, carrés et formats web ; unités physiques et DPI ; portrait/paysage ; ratios 1:1, 4:3, 3:2, 16:9, √2 ; formats maison enregistrés ; fond blanc, transparent ou couleur ; estimation mémoire.
- **Pinceau / gomme** : taille, opacité, dureté, espacement, dispersion, **pression de tablette**, ligne droite `Maj+clic`, aperçu du trait, **presets** et **embouts PNG** importés.
- **Tampon de clonage** : source `Alt+clic`, mode aligné, échantillonnage du calque ou de l'image composée.
- **Densité** : éclaircir / assombrir avec intensité et dureté réglables.
- **Goutte d'eau** : étalement des couleurs avec intensité et dureté.
- **Pot de peinture vectorisé numpy** : tolérance, respect des sélections et des masques, **remplissage par motif** avec échelle.
- **Formes** : ligne, rectangle, ellipse, rectangle arrondi, polygone, dégradé linéaire/radial.
- **Texte** avec police, taille, gras, italique, retour à la ligne.
- **Sélection avancée** : rectangle, lasso, **baguette magique** (contigu/global, tous calques), **contour progressif**, modes remplacer/ajouter/soustraire/intersecter, inversion, déplacement, copier/couper/coller, **transformation** (rotation, échelle, miroirs).
- **Recadrage** avec règle des tiers et **taille du canevas** avec ancrage, unités et mode relatif.
- **Calques** : arborescence avec **groupes imbriqués**, vignettes, glisser-déposer, duplication, fusion, **masques de fusion**, **calques de réglage non destructifs**, verrouillage, verrouillage alpha, 12 modes de fusion, **ombre portée et contour**.
- **Filtres avec aperçu en direct** : flou gaussien, netteté, luminosité, contraste, saturation, **niveaux**, **teinte**, **vignettage**, **flou directionnel**, niveaux de gris, pixelisation, inversion. Les filtres ne traitent que le rectangle de sélection.
- **Historique par tuiles** avec budget mémoire configurable, annuler/rétablir, y compris propriétés et styles de calque.
- **Image** : redimensionnement, rotations 90°/180°, miroirs, recadrage, taille du canevas — tous annulables, **masques transformés avec les calques**.
- **Formats** : projet `.paint` (calques, masques, réglages, styles, DPI, repères, images d'animation), export PNG/JPEG/WebP/BMP/TIFF, **PDF**, **SVG**, **GIF/APNG**, import **PSD multi-calques**, **traitement par lot** (UI et CLI).
- **Impression** : page à la taille physique de la feuille, orientation automatique, aperçu avant impression.
- **Animation** : capture d'images, durée par image, lecture, export GIF/APNG.
- **Confort** : onglets, glisser-déposer, documents récents, **autosave et récupération après crash**, grille, **règles**, **repères aimantés**, thème clair/sombre, **roue chromatique**, palettes, **préférences**, palette de commandes `Ctrl+K`, plugins Python, vérification des mises à jour.
- **Vue** : rotation et miroir d'affichage (sans modifier l'image), mini-navigateur cliquable.
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
3. installe PySide6, numpy, Pillow et psd-tools ;
4. **scanne la configuration du PC** (processeur, cœurs physiques/logiques, RAM, carte graphique) et écrit `hardware.json` ;
5. **alloue les ressources** : analyse la RAM réellement disponible, réserve une marge système, puis répartit threads, mémoire par document, budget d'annulation et cache des pinceaux ;
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

Version installée : `python run.py --version` (affiche `Paint Amélioré 1.6.5`).

## Raccourcis

| Action | Touche |
| --- | --- |
| Pinceau / Gomme / Pot / Pipette | `B` `E` `G` `I` |
| Tampon / Densité / Goutte d'eau | `S` `K` `J` |
| Ligne / Rectangle / Ellipse / Arrondi | `L` `R` `O` `U` |
| Polygone / Dégradé / Texte / Sélection | `Y` `D` `T` `M` |
| Baguette magique / Recadrage | `W` / `C` |
| Taille du pinceau | `[` `]` |
| Ligne droite au pinceau | `Maj+clic` |
| Source du tampon de clonage | `Alt+clic` |
| Pipette temporaire | `Alt` |
| Échanger avant-plan / arrière-plan | `X` |
| Annuler / Rétablir | `Ctrl+Z` / `Ctrl+Y` |
| Grouper le calque actif | `Ctrl+Maj+G` |
| Copier / Couper / Coller | `Ctrl+C` `Ctrl+X` `Ctrl+V` |
| Tout sélectionner / Désélectionner | `Ctrl+A` / `Ctrl+D` |
| Inverser la sélection | `Ctrl+Maj+I` |
| Transformer la sélection | `Ctrl+T` |
| Palette de commandes | `Ctrl+K` |
| Grille | `Ctrl+G` |
| Magnétisme | `Ctrl+Maj+;` |
| Vue : pivoter à gauche / droite | `Ctrl+Maj+L` / `Ctrl+Maj+R` |
| Vue : réinitialiser | `Ctrl+Maj+0` |
| Nouveau / Ouvrir / Enregistrer | `Ctrl+N` `Ctrl+O` `Ctrl+S` |
| Exporter / Imprimer | `Ctrl+E` / `Ctrl+P` |
| Préférences | `Ctrl+,` |
| Zoom / ajuster / taille réelle | `Ctrl+molette` / `Ctrl+0` / `Ctrl+1` |
| Déplacement du canevas | `Espace + glisser` ou bouton du milieu |
| Ouvrir une image | glisser-déposer sur le canevas |
| Recadrer | outil `C` puis `Entrée` |
| Créer un repère | glisser depuis une règle |
| Déplacer / supprimer un repère | `Ctrl+glisser` / `Ctrl+double-clic` |

## Architecture

```
paint/
  app.py            fenêtre, onglets, menus, actions, E/S, session
  sheet.py          unités, DPI, presets de feuille, estimations
  brush.py          tampons, cache LRU, buffer de trait
  brushes.py        presets de pinceaux
  canvas.py         rendu : zoom, pan, rotation de vue, repères, tablette
  document.py       calques, groupes, masques, styles, réglages, sélection, transformations
  config.py         scan matériel et allocation adaptative des ressources
  history.py        transactions et historique par tuiles 128×128
  filters.py        flood fill numpy + filtres Pillow + motifs
  autosave.py       sauvegarde de secours et récupération
  batch.py          conversion par lot (UI et CLI)
  hardware.py       détection matérielle et allocation
  plugins.py        chargement des plugins Python
  updater.py        vérification des releases GitHub
  io/               images, projets, PDF/SVG, impression, PSD, animations
  tools/            un outil par fichier
  ui/               toolbar, options, docks, règles, roue, dialogues, thème, icônes
```

Choix de performance :

- recomposition **uniquement du rectangle sale** et blit limité au viewport ;
- trait dessiné dans un **buffer de stroke réutilisé** puis fusionné une seule fois (pas d'accumulation d'opacité) ;
- gomme calculée sur une copie du viewport, jamais sur toute l'image ;
- remplissage par **runs de lignes vectorisés** (index de runs calculé d'un coup), écriture par masque `uint32` et chemin rapide à tolérance zéro ;
- filtres et remplissages limités au **rectangle de sélection** ;
- historique **par tuiles** : seules les zones touchées sont copiées, taille des commandes mise en cache ;
- cache de tampons LRU borné par la mémoire allouée ;
- invalidation sélective des propriétés de calque (pas de recomposition pour un renommage).

Mesures de référence (Ryzen 7 5850U, canevas 3840×2160, bench inclus) :

| Opération | 1.5 | 1.6 |
| --- | --- | --- |
| Trait de ~1500 tampons | ~26 ms | **~19 ms** |
| Recomposition des calques | ~18 ms | **~9 ms** |
| Remplissage complet | ~366 ms | **~82 ms** |
| Annuler une zone 512×512 | < 1 ms | < 1 ms |
| Export PNG 4K | ~220 ms | ~215 ms |

```powershell
python -m pytest tests -q
python benchmarks\bench.py
```

Tests automatisés sur Python 3.11, 3.12 et 3.13 via GitHub Actions.

## Formats

- **.paint** : archive zip contenant `project.json`, un PNG par calque, les masques et les images d'animation. Le fichier conserve les DPI, les repères, les styles et les réglages.
- **PNG** (transparence conservée), **JPEG/BMP** (fond blanc automatique), **WebP**, **TIFF** avec redimensionnement, DPI et qualité à l'export.
- **PDF** (page à la taille de l'image), **SVG**, **GIF/APNG** depuis les images d'animation.
- **PSD** : import multi-calques avec position, opacité, visibilité et mode de fusion ; les groupes PSD sont aplatis en calques nommés. Sans `psd-tools`, repli sur l'image aplatie.
- **Traitement par lot** : `python -m paint.batch source sortie --width 1920 --format jpg`.

## Impression

Fichier → Imprimer (`Ctrl+P`) ou Aperçu avant impression (`Ctrl+Maj+P`). La page reprend la taille physique de la feuille (pixels / DPI) et l'image est centrée sans déformation. Les transparents sont imprimés sur fond blanc.

## Animation

Le dock **Animation** (Affichage → Animation) permet de capturer l'image courante, dupliquer, régler la durée, lire la séquence et exporter en GIF ou APNG.

## Autosave et récupération

Les documents modifiés sont sauvegardés toutes les 90 secondes dans `%LOCALAPPDATA%\PaintAmeliore\autosave`. Au démarrage suivant, l'application propose de restaurer les documents retrouvés après un arrêt brutal. Une sauvegarde normale efface l'autosave correspondant. L'intervalle se règle dans **Préférences**.

## Ressources système

Au démarrage (ou à l'installation), l'application lit `hardware.json`, mesure la **RAM réellement disponible** et réserve une marge pour Windows et les autres logiciels. Elle en déduit :

- le nombre de **threads** (cœurs physiques, 1 à 32) ;
- la **mémoire de l'application** et le **budget par document** ;
- le **budget d'annulation** et le **cache des pinceaux** ;
- une **taille de feuille conseillée** (nombre de mégapixels pour 3 calques).

Ces valeurs sont visibles dans Aide → Configuration système et se règlent dans **Préférences** (threads CPU, mémoire de l'application, budget d'annulation). Le dialogue de nouvelle feuille indique en rouge un format qui dépasse le budget conseillé. Le GPU est détecté mais n'est pas utilisé pour le rendu, faute de dépendance CUDA/OpenGL.

## Plugins

Déposez un fichier `.py` dans `plugins/` exposant `register(api)`. L'API fournit `api.add_action(texte, callback, raccourci)`, `api.document` et `api.notify`. Exemple fourni : `plugins/exemple.py`.

## Build et publication

```powershell
.\build.ps1                 # executable autonome + dist\Paint-Ameliore-win64.zip
```

Un tag `v1.6.5` déclenche le workflow GitHub Actions qui construit l'exécutable et publie la release ; l'application vérifie ensuite les mises à jour via l'API GitHub. Un manifeste winget est fourni dans `packaging/winget/`.

## Limites connues (1.6.5)

- Import PSD : les groupes sont **aplatis** en calques nommés (pas de dossiers PSD).
- Interface en français uniquement.
- Les repères ne sont pas exportés dans les images (ils sont conservés dans les projets `.paint`).
