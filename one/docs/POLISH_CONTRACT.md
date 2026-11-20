# POLISH_CONTRACT — MulemaCare One

Oct 1, 2026 · Phase 0 (direction artistique) · statut : à valider par Dajan

Contrat de design de la console (gestionnaire, médecin-conseil), du comptoir PWA (clinique), de l'espace adhérent et du lien de paiement. À lire avant toute modification frontend. En cas d'écart, ce contrat et `specs/design/mulemacare-tokens.css` gagnent sur `specs/design/prototype.html`, qui reste la référence des parcours et des contenus, plus celle des couleurs.

## 1. Direction : « Registre émeraude »

**Concept :** la confiance d'un document officiel, la vitesse d'une application de paiement.

Le Bio-Clinical Emerald du site preprod.mulemacare.com (`site/assets/css/mulema-tokens.css`, `docs/ART_ESPACES.md`, `docs/MCARE_ART.md`), poussé plutôt que recopié :

- **Une seule couleur agit.** L'émeraude `#097268` est réservée à l'action (bouton principal, navigation active, lien, focus). Les statuts ne l'utilisent jamais (§5).
- **Le montant est le héros.** Sur chaque écran d'argent, un montant en Inter tabulaire de 40 px est le point focal au-dessus de la ligne de flottaison (« À encaisser auprès du patient », « 41,92 € »).
- **Trois motifs repris du site, pas plus :** le filet or devant chaque surtitre (`.eyebrow::before` du site), la guilloche de la carte adhérent (cercles concentriques `.gu` du site, poussés en rosette), le pouls du logo (tracé or du favicon). S'y ajoute un motif propre à One : le **cachet**, un double cercle qui marque toute décision (accordé, refusé).
- **Ce qui n'est pas repris du site :** le flou d'arrière-plan des en-têtes (`backdrop-filter`), les dégradés WhatsApp, les gradients or de la puce de carte, les badges émeraude pour « payé/actif » (le site mêle marque et statut), les polices chargées depuis Google Fonts, le pulse animé en boucle.

Planche de référence : `specs/design/direction/index.html` (cinq écrans, captures dans `direction/screenshots/`).

## 2. Jetons

Source unique : `specs/design/mulemacare-tokens.css`. Aucune couleur hexadécimale, `rgb()`, `hsl()` ou `oklch()` dans le code des composants (gardes : `apps/web/console/tests/unit/design-guards.test.ts`, `apps/web/counter/src/design-rules.test.ts`).

| Rôle | Jeton | Clair | Sombre | Plein soleil |
| --- | --- | --- | --- | --- |
| Fond de page | `--bg` | `#F6F9FB` | `#0D1417` | `#FFFFFF` |
| Surface (carte, panneau) | `--surface` | `#FFFFFF` | `#131C20` | `#FFFFFF` |
| Creux (champ, onglet, ligne survolée) | `--sunk` | `#EEF3F6` | `#0A1013` | `#EBEBEB` |
| Filet décoratif | `--line` | `#E2E8F0` | `#22303A` | `#000000` |
| Bord de contrôle (champ, bouton secondaire) | `--line-2` | `#7A8A9E` | `#5F7282` | `#000000` |
| Encre | `--fg` | `#0F172A` | `#E7EEF1` | `#000000` |
| Texte secondaire | `--fg-2` | `#334155` | `#B3C1C8` | `#000000` |
| Texte tertiaire (console seulement) | `--fg-3` | `#5B6B7F` | `#8D9DA6` | `#000000` |
| Accent (action) | `--accent` | `#097268` | `#4FC2B0` | `#00473F` |
| Accent survolé (assombrit, ne s'éclaircit jamais) | `--accent-hover` | `#075E56` | `#6FD3C3` | `#00332D` |
| Fond de sélection | `--accent-2` | `#E3F3EF` | `#123430` | `#D7F0EA` |
| Texte sur accent | `--accent-fg` | `#FFFFFF` | `#04211D` | `#FFFFFF` |
| Focus | `--focus` | `#097268` | `#4FC2B0` | `#000000` |
| Ok | `--ok` / `--ok-bg` | `#166534` / `#E6F4EA` | `#6FCF8E` / `#12291B` | `#0A4F22` / `#DCF3E2` |
| Attention | `--warn` / `--warn-bg` | `#92400E` / `#FEF3C7` | `#F0B45E` / `#33250F` | `#5C3300` / `#FFE9B8` |
| Critique | `--crit` / `--crit-bg` | `#B91C1C` / `#FDECEC` | `#F38E86` / `#3A1816` | `#8E0000` / `#FFE0E0` |
| En cours, en attente (royal) | `--info` / `--info-bg` | `#1E40AF` / `#EAF0FD` | `#9BB4F6` / `#172343` | `#0A2A8A` / `#E2E9FF` |
| Émeraude profond (carte, marque) | `--brand-deep` | `#064A43` | `#0B3F3A` | `#00332D` |
| Or (décor) | `--brand-gold` | `#D97706` | `#D97706` | `#D97706` |

Jetons de marque complémentaires : `--brand-on-deep`, `--brand-on-deep-2`, `--brand-gold-soft`, `--brand-gold-on-deep`, `--brand-royal`. Le royal du site devient la couleur sémantique « en cours » (`--info`) : remboursement en cours, pièces demandées, virement en route.

## 3. Contraste (calculé, WCAG 2.2)

Seuils : texte AA 4,5:1 (clair, sombre), **7:1 en plein soleil** ; composants et repères graphiques 3:1 (WCAG 1.4.11). Le tableau est recalculé par `apps/api/tests/contracts/test_design_tokens.py::test_contrastes_du_contrat` : un jeton qui fait tomber une paire casse `make check`.

| Paire | Usage | Clair | Sombre | Plein soleil |
| --- | --- | --- | --- | --- |
| `--fg` / `--bg` | Texte principal | 16,88 | 15,85 | 21,00 |
| `--fg` / `--surface` | | 17,85 | 14,73 | 21,00 |
| `--fg` / `--sunk` | | 15,97 | 16,32 | 17,62 |
| `--fg` / `--accent-2` | Texte sur sélection | 15,59 | 11,48 | 17,54 |
| `--fg-2` / `--surface` | Texte secondaire | 10,35 | 9,37 | 21,00 |
| `--fg-2` / `--sunk` | | 9,26 | 10,38 | 17,62 |
| `--fg-3` / `--bg` | Texte tertiaire (console) | 5,15 | 6,65 | 21,00 |
| `--fg-3` / `--sunk` | | 4,87 | 6,85 | 17,62 |
| `--accent` / `--surface` | Lien, onglet actif | 5,80 | 7,97 | 10,64 |
| `--accent` / `--accent-2` | Navigation active | 5,07 | 6,20 | 8,89 |
| `--accent-fg` / `--accent` | Bouton principal | 5,80 | 7,80 | 10,64 |
| `--accent-fg` / `--accent-hover` | Bouton principal survolé | 7,65 | 9,50 | 13,89 |
| `--ok` / `--ok-bg` | Statut ok | 6,28 | 8,09 | 8,34 |
| `--warn` / `--warn-bg` | Statut attention | 6,37 | 8,07 | 9,13 |
| `--crit` / `--crit-bg` | Statut critique | 5,66 | 6,83 | 7,90 |
| `--info` / `--info-bg` | Statut en cours | 7,63 | 7,55 | 10,13 |
| `--brand-on-deep` / `--brand-deep` | Carte adhérent | 10,15 | 11,76 | 13,89 |
| `--brand-on-deep-2` / `--brand-deep` | Carte, texte secondaire | 7,35 | 8,51 | 10,05 |
| `--line-2` / `--surface` | Bord de champ (composant, 3:1) | 3,53 | 3,47 | 21,00 |
| `--focus` / `--surface` | Anneau de focus (composant, 3:1) | 5,80 | 7,97 | 21,00 |
| `--brand-gold` / `--surface` | **Or : décor seul** | 3,19 | 5,43 | 3,19 |

**L'or `#D97706` échoue AA en texte sur fond clair (3,19:1).** Il ne porte jamais de texte, ni d'icône seule porteuse de sens : filet, tracé du pouls, anneau du QR, puce décorative. Le texte « attention » utilise `--warn` (`#92400E`, 6,37:1 sur `--warn-bg`). Sur la carte émeraude profond, l'or éclairci `--brand-gold-on-deep` (`#E3A23B`, 4,59:1) reste décoratif lui aussi.

Anciennes paires du site corrigées : le bleu-vert de survol `#0D9488` (3,74:1 sous du texte blanc) est remplacé par un survol plus sombre ; le gris `#CBD5E1` des bords de champ (1,5:1) par `--line-2` (3,53:1).

## 4. Typographie

| Famille | Jeton | Usage | Poids |
| --- | --- | --- | --- |
| Outfit (site) | `--f-display` | Titres, numéro d'étape, marque | 600, 700 |
| Plus Jakarta Sans (site) | `--f-body` | Tout le texte d'interface | 400, 500, 600, 700 |
| Inter (site, chiffres) | `--f-num` | Montants (`--num-features` : `tnum`, `lnum`), identifiants (`--id-features` : sans `tnum`, qui élargit le tiret de `MC-00928194`) | 500 à 700 |
| Monospace système | `--f-mono` | Clés techniques brutes seulement (empreinte, clé d'idempotence) | — |

Échelle, six tailles et pas une de plus : 12 / 16 (`--fs-caption`), 14 / 20 (`--fs-dense`), 16 / 24 (`--fs-body`), 20 / 28 (`--fs-title`), 28 / 36 (`--fs-headline`), 40 / 48 (`--fs-display`). Titres : interlettrage `-0.02em`. Surtitres : capitales, `+0.12em`, 12 px, console seulement.

- Console : texte courant 14 px, tableaux 14 px, légendes 12 px.
- Comptoir, espace adhérent, lien de paiement : **16 px minimum partout**, aucun texte en capitales réduites, aucun texte secondaire pâle (`--fg-2`, `--fg-3` et l'opacité sur le texte y sont interdits ; la hiérarchie passe par la graisse).
- Montant héros : `--fs-display` en Inter 700, unité en `--fs-title` 600 à côté.
- Nombres en français : espace fine insécable entre milliers (`27 500`), espace insécable avant l'unité (`27 500 FCFA`, `41,92 €`), virgule décimale.
- Polices auto-hébergées (`@fontsource-variable/outfit`, `plus-jakarta-sans`, `inter`, OFL-1.1), `font-display: swap`, sous-ensemble latin, préchargement de la seule police de texte. Aucun appel à Google Fonts. Remplacement des paquets Geist et Schibsted Grotesk : Phase 1 (justification dans `DEPENDENCIES.md`).

## 5. Sémantique : ok / warn / crit / info, jamais l'accent

- Un statut utilise `--ok`, `--warn`, `--crit`, `--info` ou le neutre (`--sunk` + `--fg-2`). L'accent ne marque jamais un statut, même « payé » ou « actif ».
- Un statut n'est jamais porté par la couleur seule : pastille = icône + mot (`✓ Droits ouverts`, `⏱ 18 min`, `⚠ Retard 12 min`). Une barre de risque est toujours suivie de sa valeur (`0,72`).
- Correspondance : accordé, payé, équilibré → ok ; en revue, échéance proche, impayé → warn ; refusé, fraude, retard, déséquilibre → crit ; en cours, pièces demandées, virement en route → info ; contre-passation, archivé → neutre.
- La sélection (ligne active, navigation courante) utilise l'accent : c'est un état d'interface, pas un statut métier.
- Toute décision s'affiche avec le cachet (`#i-seal`, `#i-seal-x`) et sa règle versionnée (`R-12 · v3`).

## 6. Grille, rayons, ombres

- **Grille de 8 px** : `--sp-2` 8, `--sp-4` 16, `--sp-5` 24, `--sp-6` 32, `--sp-7` 48, `--sp-8` 64. Demi-pas 4 et 12 (`--sp-1`, `--sp-3`) à l'intérieur d'un composant seulement, jamais entre deux sections.
- Gouttières : 16 px sous 600 px, 24 px au-delà ; colonne de lecture max 1120 px ; console : barre latérale 232 px, panneau de détail 380 px.
- Rayons : `--r-sm` 6 (pastille de code), `--r-md` 10 (champ, bouton console), `--r-btn` 12 (bouton comptoir), `--r-lg` 16 (panneau), `--r-xl` 24 (carte adhérent, feuille), `--r-pill`.
- Ombres : aucune au repos, un filet `--line` suffit. `--shadow-1` pour l'onglet actif, `--shadow-2` pour la carte adhérent et la carte de paiement, `--shadow` pour les fenêtres. Plein soleil : aucune ombre, traits de 2 px.

## 7. Mouvement

| Jeton | Durée | Courbe | Usage |
| --- | --- | --- | --- |
| `--dur-press` | 90 ms | `--ease-standard` `cubic-bezier(0.2,0,0,1)` | Pression d'un bouton (1 px vers le bas) |
| `--dur-hover` | 140 ms | standard | Survol, focus, changement de couleur |
| `--dur-enter` | 200 ms | `--ease-enter` `cubic-bezier(0.05,0.7,0.1,1)` | Toast, menu, pastille qui change |
| `--dur-panel` | 280 ms | entrée ; sortie à 70 % de la durée en `--ease-exit` `cubic-bezier(0.3,0,0.8,0.15)` | Tiroir, feuille, fenêtre |
| `--dur-reveal` | 400 ms | entrée | Cachet de décision, remplissage d'une jauge ; une seule fois |

Déplacements : `--move-sm` 4 px, `--move-md` 12 px. Jamais de rebond, jamais de rotation continue décorative, jamais plus d'une animation signature par écran.

**`prefers-reduced-motion: reduce`** : les jetons passent à 0 px de déplacement, fondus de 120 ms, pression et survol instantanés. Toute animation (`@keyframes`) est déclarée dans `@media (prefers-reduced-motion: no-preference)` ; rien ne boucle en mouvement réduit (le squelette de chargement devient statique, l'anneau du QR aussi).

## 8. États obligatoires

Chaque écran qui charge des données livre : **chargement, vide, erreur, succès**, plus hors ligne pour le comptoir. Un écran sans l'un d'eux n'est pas fini.

- **Chargement** : squelette à la forme du contenu, affiché après 300 ms seulement ; jamais de toupie plein écran. Bouton en cours : libellé conservé, toupie à gauche, bouton désactivé.
- **Vide** : cachet en contour, une phrase qui dit pourquoi c'est vide et ce qui arrivera (« Les nouveaux dossiers arrivent ici en temps réel »), une action si elle existe.
- **Erreur** : ce qui s'est passé, quoi faire, code stable (`R-01`, `E-NET-02`) ; bouton « Réessayer ». Jamais « Une erreur est survenue » seul. Erreur de champ sous le champ, liée par `aria-describedby`.
- **Succès** : cachet ok + preuve (numéro de dossier, délai : « Droits ouverts, 14 s après votre paiement »).
- **Hors ligne (comptoir)** : bandeau warn persistant, ce qui reste possible (« accords sous 50 000 FCFA signés sur l'appareil, valables 2 h »).
- Survol, focus visible, désactivé (jamais par opacité seule sur le comptoir), sélectionné.

## 9. Règles du comptoir et de l'espace adhérent

- `data-surface="counter"` sur le layout.
- Zone tactile **48 px** minimum ; action principale **56 px**, pleine largeur, collée en bas de l'écran sous le pouce, une seule par écran.
- Texte **16 px** minimum, montants 40 px, aucun gris pâle.
- Une question par écran, formulée comme au comptoir (« La personne en face de vous est-elle bien celle-ci ? »).
- **Plein soleil** (`data-sun`) : noir sur blanc, 7:1 minimum, traits de 2 px, aucune ombre, focus noir de 3 px, quel que soit le thème.
- Clavier numérique pour les codes (`inputmode="numeric"`, `autocomplete="one-time-code"`).
- Le QR de la carte reste foncé sur blanc dans tous les thèmes.

## 10. Accessibilité et focus

- Focus visible sur tout contrôle : `outline: var(--focus-w) solid var(--focus)`, décalage 2 px (3 px en plein soleil).
- Cibles console 32 px minimum (WCAG 2.5.8 exige 24).
- Un seul `h1` par écran, une intention par écran, un seul bouton principal.
- `lang="fr"`, textes dans les fichiers de traduction, aucun texte d'interface en dur.
- Audit axe WCAG 2.2 A/AA sans violation, en clair, sombre et plein soleil.

## 11. Métriques de design mesurables

| Métrique | Seuil | Mesure |
| --- | --- | --- |
| Contraste texte | ≥ 4,5:1 clair et sombre, ≥ 7:1 plein soleil | `test_design_tokens.py` (calcul sur les jetons) ; axe `color-contrast` sur chaque écran |
| Contraste composant | ≥ 3:1 (bord de champ, focus, jauge) | idem |
| Violations axe WCAG 2.2 AA | 0, dans les trois thèmes | `make a11y` (comptoir), `specs/design/direction/capture.mjs` (planche) |
| Taille de cible | ≥ 48 px comptoir et adhérent, action principale ≥ 56 px, ≥ 32 px console | `apps/web/counter/e2e/touch.spec.ts` |
| Texte minimum | 16 px comptoir et adhérent, 12 px console | comptoir : `design-rules.test.ts` (échelle Tailwind qui commence à 16 px) ; console : à ajouter en Phase 1 |
| Débordement horizontal | 0 px à 375, 768, 1280 | `capture.mjs` (`scrollWidth - innerWidth`) |
| LCP | < 2,5 s sur 3G rapide (1,6 Mb/s, RTT 150 ms, processeur ralenti ×4), percentile 75 | Lighthouse mobile sur le comptoir et le lien de paiement |
| CLS | < 0,1 | Lighthouse ; dimensions réservées pour la carte, le QR, les squelettes |
| INP | < 200 ms | Lighthouse / Web Vitals |
| Poids des polices | ≤ 110 Ko (trois variables latines woff2 : 32 + 27 + 48 Ko) | taille des fichiers servis |
| JavaScript initial du comptoir | ≤ 170 Ko compressé | sortie de `next build` |
| Décision au comptoir | Écran de décision affiché < 10 s après le scan (PRD objectif 1) | à chronométrer dans l'e2e du comptoir (Phase 1) |

## 12. Interdits

1. Fond obsidian, glow néon, glassmorphism, `backdrop-filter`, dégradés émeraude/cyan/violet « IA ».
2. L'or en texte sur fond clair ; l'accent pour un statut ; un statut porté par la couleur seule.
3. Une couleur hors jetons dans un composant ; une 7ᵉ taille de texte ; un espacement hors grille.
4. Une police chargée depuis un CDN ; un thème alternatif (`data-skin`).
5. Une animation hors `prefers-reduced-motion: no-preference`, une animation en boucle hors chargement, un rebond.
6. Un écran sans état vide, chargement et erreur ; « Une erreur est survenue » sans action.
7. Un diagnostic, un motif médical ou une ordonnance affichés au gestionnaire, à la clinique ou dans une recommandation de JOE ; JOE présenté comme décideur (il « recommande », « avis, pas décision »).
8. Le symbole étincelle ✦ ou tout pictogramme « IA » générique pour JOE : son repère est le monogramme « J » sur émeraude profond.
9. Des données réelles d'adhérents dans les maquettes et captures ; un faux chiffre présenté comme réel (« N médecins en ligne »).
10. Un émoji dans l'interface.
