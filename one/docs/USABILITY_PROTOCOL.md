# Protocole de test d'usabilité — MulemaCare One, Phase 2 (voie A)

Statut : **non exécuté**. Ce protocole est à conduire par Dajan avec 5 vraies personnes. Aucun
résultat ci-dessous n'a été mesuré : les tableaux sont des modèles vides à remplir. Un agent ne
peut pas simuler un utilisateur ; les tests automatiques (Vitest, Playwright, axe) prouvent que les
écrans fonctionnent et sont accessibles, pas qu'ils sont compris.

## 1. Ce que l'on veut savoir

| Question | Écran | Objectif chiffré |
| --- | --- | --- |
| Un adhérent comprend-il sa couverture sans formation ? | Espace adhérent, découverte étape 1 | 4 personnes sur 5 répondent juste à « combien payez-vous pour un soin de 10 000 FCFA ? » en **moins de 2 minutes** après la première ouverture |
| Sait-il présenter sa carte ? | Espace adhérent, « Présenter ma carte » | 5 sur 5 affichent le QR en plein écran en moins de 30 s |
| Sait-il suivre un remboursement ? | Espace adhérent, Soins, suivi | 4 sur 5 disent l'étape en cours d'un dossier en moins de 60 s |
| Comprend-il une notification et ce qu'il doit faire ? | Espace adhérent, notifications | 4 sur 5 disent quoi faire (payer avant une date, contacter la mutuelle) |
| Sait-il ce qu'il peut encore faire sans réseau ? | Espace adhérent, bandeau hors ligne | 4 sur 5 citent au moins une chose possible et une chose impossible |
| Un agent de comptoir mène-t-il un patient jusqu'à la décision à la première utilisation ? | Comptoir, aide de première utilisation | décision affichée en moins de 3 minutes, sans aide de l'animateur ; écran de décision < 10 s après le scan (objectif 1 du PRD), lu sur la page « Mesure » |
| L'aide du comptoir gêne-t-elle ? | Comptoir | 0 personne bloquée par une bulle ; la personne la retire ou l'ignore |
| Un gestionnaire trouve-t-il un dossier et lit-il une réponse de JOE avec ses sources ? | Console, palette Ctrl+K | dossier ouvert en moins de 20 s ; la personne montre une source et dit qui décide (« un humain, pas JOE ») |
| Un médecin-conseil distingue-t-il un brouillon de JOE d'une décision ? | Console, brouillon de décision | 2 personnes sur 2 disent que le brouillon n'a rien changé au dossier |

## 2. Participants (5)

Recruter des personnes qui n'ont jamais vu l'application ni ses maquettes, sans lien avec l'équipe.

| Code | Profil | Écrans testés | Remarque |
| --- | --- | --- | --- |
| P1 | Adhérent titulaire, à l'aise avec un téléphone | Espace adhérent (T1 à T5) | Téléphone Android personnel ou de test |
| P2 | Adhérent peu à l'aise à l'écrit | Espace adhérent (T1 à T5) | Profil pour lequel le budget « 2 minutes » a été écrit |
| P3 | Adhérent avec ayants droit | Espace adhérent (T1 à T5) | Ayant droit à la carte bloquée dans le jeu de test |
| P4 | Agent d'accueil d'une clinique conventionnée | Comptoir (T6, T7) | En situation : debout, téléphone à une main |
| P5 | Gestionnaire de mutuelle, ou médecin-conseil | Console (T8, T9) | Si possible, un médecin-conseil pour T9 |

Cinq personnes suffisent à faire apparaître la plupart des blocages ; ce n'est pas un échantillon
statistique : les objectifs « 4 sur 5 » sont des seuils de décision, pas des taux.

## 3. Matériel

- **Données fictives uniquement** (AGENTS.md, Interdits) : jeu de démonstration des tests
  (`apps/web/member/src/test/fixtures.ts`, `apps/web/counter/e2e/mock-api.ts`, console en mode
  démonstration). Jamais le compte réel d'un participant, même s'il est adhérent.
- Espace adhérent et comptoir : `next build` puis `next start` de chaque application avec
  `NEXT_PUBLIC_MULEMA_AUTH_MODE=test`, servis par l'API de test ou par `make mock-api` ; console :
  `NEXT_PUBLIC_API_MOCKING=enabled`.
- Téléphone Android d'entrée de gamme (écran ≈ 360 px), luminosité réelle ; pour T5, mode avion.
- Effacer les données du navigateur avant chaque participant (sinon la découverte ne se rejoue pas
  comme une première visite).
- Chronomètre, grille papier (§6), formulaire de consentement (§7) imprimé.
- Mesure produit : la page « Mesure » de la console donne `onboarding_completion_rate`,
  `first_card_median_ms` et `counter_decision_display_median_ms`, masqués sous 5 contributeurs ;
  elle complète le chronomètre, ne le remplace pas.

## 4. Déroulé (45 min par personne)

1. Accueil et consentement (5 min). Lire §7, faire signer, rappeler : « On teste l'application,
   pas vous. Il n'y a pas de mauvaise réponse. »
2. Tâches (30 min), une par une, consigne lue mot pour mot (§5). Penser à voix haute.
   L'animateur ne montre rien, ne répond pas aux questions sur l'écran (« que feriez-vous chez
   vous ? »). Il n'intervient qu'après 3 minutes de blocage : la tâche est alors un échec.
3. Questions de fin (10 min) : « Qu'est-ce qui vous a gêné ? », « Qu'est-ce que vous diriez à un
   proche sur cette application ? », note SEQ de chaque tâche si elle n'a pas été prise.

## 5. Tâches et critères de réussite

Le chronomètre démarre à la fin de la lecture de la consigne et s'arrête quand la personne dit
« c'est fait » ou donne sa réponse.

| Tâche | Consigne lue | Réussite | Temps cible |
| --- | --- | --- | --- |
| T1 Couverture | « Vous venez d'ouvrir l'application de votre mutuelle. Je voudrais savoir combien vous paierez vous-même pour un soin de 10 000 francs. » | Réponse juste (part de l'adhérent selon le taux de la carte : 2 000 FCFA à 80 %), avec ou sans la question de vérification | < 2 min |
| T2 Carte au comptoir | « Vous êtes à l'accueil d'une clinique. Montrez votre carte à l'agent. » | QR affiché en plein écran | < 30 s |
| T3 Suivi | « La clinique Pharmacie Riviera 3 a fait une demande pour vous. Où en est-elle ? » | Dit l'étape en cours (« virement en cours ») | < 60 s |
| T4 Notification | « L'application a quelque chose à vous dire. Que devez-vous faire ? » | Ouvre les notifications et dit l'action attendue (payer avant le JJ/MM, contacter la mutuelle) | < 90 s |
| T5 Sans réseau | Mode avion activé par l'animateur. « Vous n'avez plus Internet. Que pouvez-vous encore faire ? Que ne pouvez-vous plus faire ? » | Une chose possible ET une chose impossible citées | < 60 s |
| T6 Comptoir, premier patient | « Un adhérent se présente avec sa carte (numéro MC-00000042) pour une consultation, une NFS et un ECG. Faites le nécessaire. » | Écran de décision atteint, montant à encaisser dit à voix haute | < 3 min |
| T7 Comptoir, coupure | Réseau coupé par l'animateur à l'étape des actes. « Le réseau vient de tomber. Pouvez-vous continuer ? » | Dit ce qui reste possible (accord provisoire sous le seuil) et obtient l'accord provisoire | < 2 min |
| T8 Console, recherche et JOE | « Retrouvez le dossier PEC-26-09813, puis demandez combien de dossiers attendent le médecin-conseil. Qui décide ? » | Dossier ouvert ; réponse de JOE lue ; une source montrée ; « un humain » | < 20 s pour le dossier, < 2 min en tout |
| T9 Console, brouillon | (médecin-conseil) « Préparez une recommandation pour ce dossier. Est-il accordé ? » | Dit que le brouillon n'a rien changé et que la décision se prend dans le dossier | < 2 min |

## 6. Grille de notation (une ligne par participant et par tâche)

- **Réussite** : 2 = seul, sans erreur ; 1 = seul, avec une erreur corrigée (retour arrière,
  mauvais onglet) ; 0 = échec ou aide de l'animateur.
- **Temps** en secondes ; « > cible » si dépassé.
- **Erreurs** : nombre de gestes inutiles (mauvais bouton, retour, défilement perdu).
- **SEQ** (Single Ease Question) : « Cette tâche était… » de 1 (très difficile) à 7 (très facile).
- **Verbatim** : phrase exacte, sans nom.

| Participant | Tâche | Réussite (0/1/2) | Temps (s) | Erreurs | SEQ (1-7) | Verbatim (anonymisé) |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | T1 | | | | | |
| … | … | | | | | |

**Synthèse par tâche** : taux de réussite (réussites 1 ou 2 sur 5), temps médian, SEQ médiane.
**Règles de décision** :
- objectif du §1 atteint et SEQ médiane ≥ 5 : écran gardé ;
- objectif atteint mais SEQ médiane < 5 : corriger le texte ou l'ordre, sans refonte ;
- objectif manqué : problème bloquant ; revoir l'écran avant tout pilote, puis retester ce seul
  écran avec 3 nouvelles personnes.
- Tout participant qui croit que JOE décide (T8, T9) est un problème bloquant, quel que soit le
  taux.

## 7. Consentement et anonymisation

Texte lu puis signé (une copie au participant) :

> Nous testons une application de la mutuelle MulemaCare, pas vos capacités. La séance dure
> environ 45 minutes. Nous notons vos gestes, le temps passé et ce que vous dites à voix haute.
> Avec votre accord, l'écran du téléphone est filmé, sans votre visage ni votre voix. Vous
> utilisez un faux compte : aucune de vos données de santé ou de mutuelle n'est utilisée. Vous
> pouvez arrêter à tout moment sans vous justifier ; cela n'a aucune conséquence sur votre
> adhésion ou votre travail. Vos réponses sont conservées sans votre nom, sous un code (P1 à P5),
> pendant 6 mois, puis effacées.
>
> J'accepte de participer : oui / non. J'accepte que l'écran soit filmé : oui / non.

- Codes P1 à P5 seulement : la table de correspondance code → nom est sur papier, gardée à part,
  détruite à la fin de l'analyse. Aucun nom, téléphone ou numéro d'adhérent dans les notes, les
  verbatims, les captures ou les vidéos.
- Captures et vidéos : écran seul, jeu de données fictif ; flouter toute notification personnelle
  du téléphone qui apparaîtrait.
- Données conservées dans le pays de l'instance (R9), sur un support de la mutuelle, pas dans un
  service en ligne tiers.
- Un participant qui révèle une information de santé personnelle pendant la séance : ne pas la
  noter.
- Indemnisation éventuelle identique pour tous et annoncée avant la séance, sans lien avec la
  réussite.

## 8. Après la séance

1. Remplir la grille le jour même.
2. Classer chaque problème : bloquant (empêche la tâche), majeur (erreur ou > cible), mineur.
3. Reporter les problèmes bloquants et majeurs dans le suivi du lot, avec la tâche, le profil et
   le verbatim.
4. Comparer le temps de T1 et de T6 avec les indicateurs de la page « Mesure » sur la même
   période (s'ils sont publiés, c'est-à-dire avec au moins 5 contributeurs).
5. Écrire la synthèse sous ce document, datée, au nom de la personne qui a animé.

## 9. Synthèse (à remplir par l'animateur)

Aucune séance tenue à ce jour.
