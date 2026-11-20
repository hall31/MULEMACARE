# Direction « Registre émeraude » — planche Phase 0

**Parti pris.** MulemaCare One doit inspirer la confiance d'un document officiel et la vitesse d'une application de paiement : une seule couleur de marque (l'émeraude) qui agit, des statuts ok / attention / critique / en cours qui ne lui ressemblent jamais, et sur chaque écran d'argent un montant héros en chiffres tabulaires. La décision est le moment fort : elle s'affiche comme un cachet avec sa règle versionnée, et c'est la seule animation signature (400 ms, une fois, rien en mouvement réduit). Le reste est retenu : aucune ombre au repos, grille de 8 px, six tailles de texte, et le même système tient en clair, en sombre et en plein soleil (7:1).

**Repris du site preprod.mulemacare.com.** La palette Bio-Clinical Emerald (`#097268`, royal `#1E40AF`, or `#D97706`, fond `#F6F9FB`, encre `#0F172A`) et ses trois polices (Outfit, Plus Jakarta Sans, Inter pour les chiffres), désormais auto-hébergées ; le filet or devant les surtitres ; la guilloche de la carte adhérent ; le pouls or du logo ; la carte émeraude profond avec QR ; la frise d'étapes du remboursement. **Écarté :** les badges émeraude pour « payé/actif » (marque et statut mêlés), le flou d'en-tête, les dégradés, l'or en texte (3,19:1), le survol plus clair qui faisait tomber le contraste, les polices Google.

## Contenu

- `index.html` : la planche. Ouvrir dans un navigateur ; `?screen=comptoir|revue|adherent|paiement|grand-livre` affiche un écran seul, `&theme=dark`, `&sun=1` pour le plein soleil. Les couleurs viennent uniquement de `../mulemacare-tokens.css` et les contrastes affichés sont calculés en direct.
- `screenshots/` : 375 / 768 / 1280 en clair et sombre pour les cinq écrans, plein soleil à 375, le pli du téléphone (`-pli`), la planche entière à 1440.
- `capture.mjs` : régénère les captures et audite chaque écran (axe WCAG 2.2 AA, débordement horizontal). `node specs/design/direction/capture.mjs` depuis `one/` ; réutilise Playwright et axe de `apps/web/console`, aucune dépendance ajoutée.
- `fonts/` : Outfit, Plus Jakarta Sans, Inter en woff2 variables latins (107 Ko au total), licence OFL-1.1 (`OFL-*.txt`), extraits de `@fontsource-variable/*` 5.3.0.

Données fictives (Awa Koné, Clinique Les Palmiers…, reprises du prototype). Contrat complet : `docs/POLISH_CONTRACT.md`.
