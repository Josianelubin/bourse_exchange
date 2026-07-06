# Bourse Exchange

Plateforme d'échange HTG ⇄ Cryptomonnaies (Django), avec dépôts/retraits **réels** via
MonCash (gourdes) et NOWPayments (crypto blockchain).

## ⚠️ Avant de mettre de l'argent réel en jeu

Ceci est une base solide et sécurisée, mais **aucun logiciel financier ne doit être lancé
en production sans audit externe**. Avant d'ouvrir le site au public avec de vrais fonds :

1. Fais auditer le code par un développeur/sécurité tiers (idéalement quelqu'un qui a déjà
   construit un exchange).
2. Vérifie les obligations légales en Haïti pour l'échange de cryptomonnaies contre HTG
   (licence, KYC/AML) — ce projet n'inclut pas de conseil juridique.
3. Configure une sauvegarde automatique de la base de données (Render propose des backups
   payants sur PostgreSQL).
4. Ne stocke JAMAIS de clé privée blockchain toi-même : NOWPayments gère la garde des fonds
   crypto côté processeur, ce qui est plus sûr que de gérer un wallet custodial maison.

### 🔴 Retraits automatiques (MonCash + Crypto) — lis ceci avant d'activer

Sur demande, les retraits sont maintenant **100% automatiques** : dès qu'un utilisateur
demande un retrait (MonCash ou crypto), les fonds sont envoyés immédiatement, **sans
validation d'un administrateur**. C'est activé par défaut (`SiteSettings.auto_process_withdrawals`).

Conséquence concrète : si le compte d'un utilisateur est piraté (mot de passe volé, session
volée), l'attaquant peut vider le portefeuille instantanément, et un envoi MonCash ou
blockchain réussi **ne peut pas être annulé**. Pour réduire ce risque sans repasser en
validation manuelle, envisage à terme :
- 2FA obligatoire avant tout retrait (le squelette `django-otp` est déjà installé),
- une limite de retrait quotidienne par utilisateur,
- une alerte e-mail/SMS automatique à chaque retrait.

### 🔴 Suppression d'historique — lis ceci avant de communiquer dessus aux utilisateurs

Le bouton "Supprimer" dans l'historique utilisateur efface maintenant la transaction
**définitivement et partout** (base de données incluse) — aucune trace n'est conservée,
ni pour l'utilisateur, ni pour l'admin. Concrètement : si un utilisateur supprime un retrait
puis prétend plus tard ne jamais l'avoir reçu, il n'existera plus aucune preuve pour trancher
le litige, y compris pour te protéger toi. Garde ça en tête si un jour tu dois gérer un
désaccord avec un client.

## Comment fonctionne l'automatisation réelle (une fois les clés API configurées)

### Dépôts (déjà automatiques dès que les clés sont bonnes)
- **MonCash** : l'utilisateur paie, MonCash redirige vers ton site, le site revérifie
  le paiement directement auprès de MonCash (jamais de confiance aveugle) puis crédite.
- **Crypto** : NOWPayments envoie un webhook signé dès qu'un dépôt est confirmé sur la
  blockchain, le site vérifie la signature puis crédite automatiquement.
- **Conversion HTG ⇄ Crypto** : se passe **entièrement dans la base de données du site**,
  aucune API externe n'est appelée. Elle fonctionne donc déjà, même sans aucune clé API —
  c'est un simple calcul (taux × montant − frais) entre deux soldes internes.

### Retraits (100% automatiques, sans validation admin — voir avertissement plus haut)
Dès que les clés API sont valides et que ton compte a assez de fonds :
- **MonCash** : `send_payment()` envoie l'argent au numéro MonCash de l'utilisateur immédiatement.
- **Crypto** : `create_payout()` envoie la crypto à l'adresse de l'utilisateur immédiatement.

### ⚠️ Point technique important sur les retraits crypto automatiques
Par défaut, NOWPayments exige un **code de vérification à deux facteurs envoyé par e-mail**
à chaque retrait (`payout`), même via l'API. Cela veut dire qu'un retrait ne part pas
tout seul tant que ce code n'est pas saisi — ce qui casse l'automatisation complète.
Pour un vrai fonctionnement automatique de bout en bout, deux options :
1. **Demander à NOWPayments de désactiver le 2FA sur les payouts** : envoie un e-mail à
   `whitelist@nowpayments.io` depuis l'adresse de ton compte, avec le texte exact :
   *"I'd like to disable 2fa for withdrawals and accept all risks related to it"*.
   NOWPayments déconseille cette option car elle réduit la sécurité — à toi de peser le risque.
2. Sinon, garder un contrôle manuel léger : toi (admin) reçois le code par e-mail et le
   valides une fois par lot (moins automatique, mais plus sûr).

## Adresses de dépôt uniques par utilisateur (USDT TRC20 et TRX TRC20)

C'est déjà en place : quand un utilisateur clique sur "Obtenir mon adresse de dépôt"
(page `/crypto/depot/`), le site appelle NOWPayments qui génère une adresse dédiée à cet
utilisateur pour cette devise précise, et la stocke dans `CryptoWallet.deposit_address`.
Chaque utilisateur a donc sa propre adresse USDT et sa propre adresse TRX — jamais partagées.

## Le réseau doit être TRC20 pour USDT et pour TRX (à faire dans l'admin)

1. Va dans `/admin/wallets/cryptonetwork/` → crée **un seul réseau** nommé `TRC20` (code `trc20`).
2. Va dans `/admin/wallets/cryptocurrency/` → crée deux devises, toutes deux reliées à ce réseau `TRC20` :
   - **USDT** : `symbol` = `USDTTRC20` (code exact attendu par NOWPayments)
   - **TRX (Tronx)** : `symbol` = `TRX`
3. Comme les deux pointent vers le même réseau, tous les dépôts/retraits passent obligatoirement par TRC20 — c'est déjà appliqué dans le code, rien d'autre à faire.

## Comment trouver ta clé API sur NOWPayments.io

1. Crée un compte sur **https://nowpayments.io** et connecte-toi à ton tableau de bord.
2. Va dans **Store Settings** → renseigne un portefeuille de sortie (wallet), clique sur **Save**.
3. Remonte en haut de la page jusqu'à la section **"API keys"** → clique sur **"Add new key"**.
4. Ta clé API s'affiche : copie-la immédiatement (elle ne sera plus jamais affichée en entier après).
5. Toujours dans les réglages, active **Custody** (case "I have read and accepted Custody Solution
   user agreement") : c'est ce qui te permet de garder un solde interne pour payer les retraits.
6. Pour l'**IPN Secret** (vérification des webhooks) : section **Store Settings → Payment Settings**
   → génère la clé IPN, à mettre dans `NOWPAYMENTS_IPN_SECRET`.
7. Pour la sécurité : whiteliste l'IP de ton serveur Render dans les réglages NOWPayments
   (nécessaire pour les payouts automatiques).

## Comment l'administrateur fait de l'argent, et où va cet argent

Tes revenus viennent des frais que tu configures (conversion, retrait, réseau — voir tableau
plus bas). Ils sont suivis automatiquement dans un **compte bloqué interne**
(`/admin/wallets/platformrevenue/`, lecture seule) qui te montre combien tu as gagné, par devise
(HTG, USDT, TRX), à chaque retrait ou conversion réussie.

**Important à comprendre : ce compte bloqué n'est qu'un compteur, pas un vrai portefeuille.**
L'argent réel ne bouge jamais vers une "adresse admin" automatiquement — il reste simplement
**dans ton solde marchand** :
- Les **frais en HTG** restent dans ton **compte business MonCash** (la différence entre ce que
  les utilisateurs déposent/retirent et ce qu'ils reçoivent réellement).
- Les **frais en USDT/TRX** restent dans ton **solde Custody NOWPayments**.

Pour transformer ce profit accumulé en argent que tu peux dépenser :
- **Côté MonCash** : connecte-toi à ton portail marchand MonCash Business et transfère le solde
  vers ton propre numéro MonCash ou compte bancaire (en dehors de ce site, directement chez Digicel).
- **Côté crypto** : dans ton tableau de bord NOWPayments, section **Custody**, clique sur
  **"Withdraw"** et envoie le montant de ton choix vers ton propre portefeuille personnel
  (Binance, Trust Wallet, Ledger...). Ce n'est pas automatique et c'est volontaire : c'est toi
  qui décides quand sortir tes gains, séparément des retraits des utilisateurs.

## Thème visuel "style Binance" et logos à ajouter toi-même

Le CSS est déjà en place :
- `static/css/binance_theme.css` — couleurs, formes, boutons, menu, cartes, formulaires,
  pages de connexion/inscription, sélecteurs de devise, tout en noir/jaune façon Binance.
- Les logos USDT et TRX sont déjà affichés automatiquement (bibliothèque libre
  `cryptocurrency-icons`, licence MIT, via CDN jsDelivr) — rien à faire de ton côté.

Deux images doivent être ajoutées par toi (je ne peux pas générer d'images) :
- `static/img/nono.png` → logo du site (favicon + logo admin). Format carré, fond
  transparent, 512×512px conseillé.
- Le logo officiel MonCash n'est pas inclus (droits de marque Digicel) : un badge textuel
  stylisé "📱 MonCash" est utilisé à la place sur les pages de dépôt/retrait. Si tu veux le
  vrai logo, télécharge-le depuis le site officiel MonCash Business et remplace le badge
  dans `wallets/templates/wallets/moncash_deposit.html` et `moncash_withdraw.html` par
  une balise `<img src="/static/img/moncash.png">`.

## Configurer les frais et minimums depuis l'admin (sans toucher au code)

| Frais / minimum | Valeur actuelle | Où le modifier dans `/gestion-secrete/` |
|---|---|---|
| Frais de retrait MonCash (%) | **2,5 %** | Réglages du site → `moncash_withdraw_fee_percent` |
| Montant minimum de retrait MonCash | **1000 HTG** | Déjà appliqué dans le formulaire (`wallets/forms.py`) |
| Frais de dépôt MonCash (%) | 0 % (gratuit) | Réglages du site → `moncash_deposit_fee_percent` |
| Frais de retrait USDT (fixe) | **2 USDT** | Cryptomonnaies → ligne USDT → `withdraw_fee_fixed` |
| Frais de retrait TRX (fixe) | **3 TRX** | Cryptomonnaies → ligne TRX → `withdraw_fee_fixed` |
| Montant minimum de retrait USDT | **10 USDT** | Cryptomonnaies → ligne USDT → `min_withdraw_amount` |
| Montant minimum de retrait TRX | **13 TRX** | Cryptomonnaies → ligne TRX → `min_withdraw_amount` |
| Frais de conversion HTG ⇄ USDT | 1 % | Cryptomonnaies → ligne USDT → `conversion_fee_percent` |
| Frais de conversion HTG ⇄ TRX | 1 % | Cryptomonnaies → ligne TRX → `conversion_fee_percent` |
| Frais réseau TRC20 (fixe, optionnel) | 0 | Réseaux crypto → ligne TRC20 → `withdraw_fee_fixed` |

Le frais total sur un retrait crypto = frais fixe de la devise + frais réseau (optionnel) +
frais en % (optionnel, à 0% par défaut maintenant que les frais fixes sont utilisés).

⚠️ Ces valeurs par défaut (2 USDT, 3 TRX, 1000 HTG minimum...) ne s'appliquent automatiquement
que sur une **base de données neuve**. Si tu as déjà lancé le site avant cette mise à jour,
va corriger manuellement ces champs dans l'admin — la création automatique ne modifie jamais
une ligne qui existe déjà.

## Mettre à jour les prix HTG/USDT/TRX — manuellement ou vraiment automatiquement

### Option 1 — Bouton manuel (le plus simple)

Dans `/gestion-secrete/wallets/cryptocurrency/` : sélectionne une ou plusieurs lignes →
menu d'actions → **"🔄 Actualiser les taux HTG automatiquement"**. Tu dois cliquer chaque fois.

### Option 2 — Vraiment automatique (toutes les heures, sans rien cliquer)

Le site expose une URL protégée par un jeton secret, à appeler périodiquement par un service
de cron **gratuit** externe (le site lui-même ne peut pas se réveiller tout seul) :

```
GET https://TON-DOMAINE.onrender.com/portefeuille/actualiser-taux/?token=TON_JETON_SECRET
```

1. Choisis un jeton secret long et aléatoire toi-même (ex: une suite de 40 caractères).
2. Ajoute sur Render : `RATE_UPDATE_SECRET_TOKEN` = ce jeton.
3. Crée un compte gratuit sur **https://cron-job.org** (ou tout autre service de cron gratuit).
4. Crée une tâche qui appelle l'URL ci-dessus (avec ton vrai domaine et ton vrai jeton)
   toutes les heures (ou selon la fréquence de ton choix).

Sans le bon jeton dans l'URL, la requête est automatiquement rejetée (403) — personne d'autre
ne peut déclencher cette mise à jour à ta place.

### Les deux options ont besoin de ces clés gratuites

Ça récupère le prix réel USDT/TRX en dollars (CoinGecko) puis le convertit en HTG via le taux
de change USD→HTG du jour (ExchangeRate-API) :

1. **CoinGecko** (prix crypto en USD) — CoinGecko exige maintenant une clé même en gratuit :
   - Va sur https://www.coingecko.com/en/api/pricing → clique **"Create Free Account"**
   - Connecte-toi → **Developer's Dashboard** → onglet **"API Keys"** → **"+ Add New Key"**
   - Copie la clé → ajoute sur Render : `COINGECKO_API_KEY` = ta clé
   - (Gratuit : 10 000 appels/mois, largement suffisant pour une mise à jour horaire)
2. **ExchangeRate-API** (taux USD→HTG) :
   - Crée un compte gratuit sur https://www.exchangerate-api.com/ → copie ta clé API
   - Ajoute sur Render : `EXCHANGE_RATE_API_KEY` = ta clé

Sans ces clés, le bouton/l'URL affichent une erreur claire au lieu de planter — tu peux
toujours modifier les taux manuellement en attendant.

## Nouveautés de cette version

- **Bug corrigé** : `TypeError: args or kwargs must be provided` sur `/admin/accounts/customuser/`
  (Django 6 exige un argument dans `format_html`, même pour du texte fixe).
- **USDT (TRC20) et TRX (TRC20) créés automatiquement** après chaque `migrate` — tu n'as plus besoin
  de les créer toi-même dans l'admin. ⚠️ Les taux de change par défaut (132 HTG/USDT, 13 HTG/TRX)
  sont des valeurs d'exemple : va dans `/admin/wallets/cryptocurrency/` et mets les **vrais taux du jour**
  avant d'ouvrir au public.
- **Adresse de dépôt générée automatiquement à l'inscription** : dès qu'un nouvel utilisateur
  crée son compte, le site tente immédiatement de générer ses adresses USDT-TRC20 et TRX-TRC20
  via NOWPayments (sans bouton à cliquer, sans admin). Si la clé API n'est pas encore configurée
  au moment de l'inscription, l'adresse sera simplement générée un peu plus tard, à la première
  visite de la page de dépôt — rien ne bloque jamais la création de compte.
- **Menu admin compact** : sidebar et textes réduits pour voir plus de lignes/colonnes d'un coup.
  Raccourcis ajoutés en haut de l'admin : "⚙️ Réglages & Frais" et "💰 Revenus".
- **Paramètres utilisateur simplifiés** : informations du compte, sélecteur de thème clair/sombre
  (mémorisé sur l'appareil), bouton modifier le profil, bouton supprimer le compte. La mention 2FA
  a été retirée (fonctionnalité non activée sur ce projet).
- **Barre de navigation mobile flottante** façon capture d'écran fournie (icône active en cercle
  surélevé) — visible en bas de l'écran sur mobile, cachée sur grand écran.

## Logos à ajouter toi-même (3 fichiers)

Le code référence maintenant des fichiers locaux (plus de dépendance à un CDN externe) :

| Fichier à créer | Utilisé pour |
|---|---|
| `static/img/nono.png` | Logo du site + favicon + logo admin |
| `static/img/usdt.png` | Logo USDT (dépôt, retrait, tableau de bord) |
| `static/img/trx.png` | Logo TRX/Tronx (dépôt, retrait, tableau de bord) |
| `static/img/moncash.png` | Logo MonCash (dépôt/retrait HTG) — si absent, un badge texte stylisé s'affiche automatiquement à la place |

Pour USDT/TRX, tu peux télécharger des icônes libres de droits (licence MIT) ici, puis les
renommer `usdt.png` / `trx.png` :
- https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/usdt.png
- https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/trx.png

Pour le logo MonCash officiel, télécharge-le depuis le portail MonCash Business (droits Digicel) —
si tu ne le fais pas, le site continue de fonctionner normalement avec le badge texte de secours.

## Faire fonctionner "Mot de passe oublié" (envoi réel par Gmail)

En local (`DEBUG=True`), les e-mails s'affichent simplement dans le terminal — pratique pour tester
sans rien configurer. En production, il faut un vrai compte Gmail avec un **mot de passe
d'application** (pas ton mot de passe Gmail normal, Google le bloque pour les connexions SMTP) :

1. Active la validation en 2 étapes sur ton compte Gmail (obligatoire pour l'étape suivante) :
   https://myaccount.google.com/security
2. Va sur https://myaccount.google.com/apppasswords → crée un mot de passe d'application
   (choisis "Autre", nomme-le "Bourse Exchange") → copie le code de 16 caractères généré.
3. Sur Render, dans les variables d'environnement :
   - `EMAIL_HOST_USER` = ton adresse Gmail complète
   - `EMAIL_HOST_PASSWORD` = le mot de passe d'application de 16 caractères (pas ton vrai mot de passe)
4. Le lien de réinitialisation envoyé est valable **3 jours** par défaut (comportement standard Django).
5. Teste avec un vrai compte utilisateur : `/mot-de-passe/reinitialiser/` → l'e-mail doit arriver
   dans les secondes qui suivent. S'il n'arrive pas, vérifie les logs Render pour l'erreur SMTP exacte.

## Comment obtenir tes clés MonCash (Client ID / Client Secret) — étapes confirmées

1. Crée ton compte marchand sandbox : https://sandbox.moncashbutton.digicelgroup.com/Moncash-business/New
2. Confirme ton e-mail (lien envoyé par `mbutton@digicelgroup.com`), puis connecte-toi :
   https://sandbox.moncashbutton.digicelgroup.com/Moncash-business/Login?environment=test
3. Onglet **"General Info"** → clique **"New"** pour ajouter une entreprise.
4. Remplis le formulaire, en particulier :
   - **Return URL** : `https://TON-DOMAINE.onrender.com/moncash/retour/`
   - **Alert URL** : `https://TON-DOMAINE.onrender.com/portefeuille/` (ou une autre page de confirmation)
5. Sauvegarde, puis clique **"View"** sur l'entreprise créée → **"Create ClientRestAPI"** →
   tu obtiens ton **Client Id** et **Client Secret**.
6. Une fois testé en sandbox, contacte `MFS_B.Services@digicelgroup.com` (ou le 202 depuis Haïti)
   pour passer en production/live — tu refais les mêmes étapes sur le portail live
   (`moncashbutton.digicelgroup.com`, sans "sandbox") pour obtenir de nouvelles clés live
   (les clés sandbox et live sont totalement différentes et non interchangeables).

## Check-list de dépannage MonCash (pourquoi ça échoue, dans l'ordre à vérifier)

1. **`MONCASH_CLIENT_ID` / `MONCASH_CLIENT_SECRET` absents ou faux** → dépôt et retrait échouent
   immédiatement, message "Impossible de contacter MonCash". Vérifie ces deux variables sur Render.
2. **`MONCASH_MODE` mal réglé** → si tu testes avec des clés sandbox mais `MONCASH_MODE=live` (ou
   l'inverse), toutes les requêtes échouent car elles ne tapent pas le bon serveur MonCash.
   Sandbox et Live ont des clés totalement différentes, non interchangeables.
3. **Return URL mal renseignée lors de la création du "business"** (étape 4 ci-dessus) → le
   dépôt reste bloqué sur "Retour MonCash incomplet" après le paiement. Vérifie/corrige-la en
   éditant ton "business" dans l'onglet "General Info" du portail marchand.
4. **Droits de retrait ("Transfert") non activés** → les dépôts fonctionnent mais tous les
   retraits échouent avec une erreur d'autorisation. Il faut le demander explicitement au
   support MonCash Business (voir plus haut).
5. **Montant trop faible** → MonCash impose un montant minimum par transaction ; vérifie que
   le montant testé dépasse ce seuil (généralement autour de 10-50 HTG selon le compte).
6. **Sandbox : identifiants génériques acceptés** — en mode `sandbox`, MonCash n'exige pas de
   vraies informations de paiement pour tester (numéro de test accepté), donc si un dépôt
   échoue en sandbox, le problème vient presque toujours des points 1 à 3 ci-dessus, pas de
   tes informations de test.

## Correction importante vérifiée contre la vraie documentation MonCash

En comparant le code à la documentation officielle (RestAPI_MonCash_doc.pdf), deux bugs réels
ont été trouvés et corrigés :
- Le retrait utilisait un endpoint `/v1/SendPayment` qui **n'existe pas** — le bon est
  `/v1/Transfert`, et il exige 4 champs obligatoires (`amount`, `receiver`, `desc`, `reference`),
  alors que seuls 2 étaient envoyés avant. Sans cette correction, tous les retraits MonCash
  auraient échoué avec une erreur 404/400.
- La vérification de dépôt utilisait `/v1/RetrieveTransactionPayment` (qui cherche par
  transactionId MonCash) au lieu de `/v1/RetrieveOrderPayment` (qui cherche par notre propre
  orderId, ce qu'on utilise réellement) — corrigé aussi.

⚠️ Point à faire toi-même auprès de Digicel : les droits de **retrait** (`Transfert`) ne sont
pas activés par défaut sur un compte marchand MonCash Business. Contacte le support MonCash
Business pour demander l'activation de cette fonctionnalité sur ton compte, sinon les retraits
échoueront même avec de bonnes clés API (erreur d'autorisation).

## Vérification d'identité (KYC) — bloque le site tant qu'elle n'est pas validée

Chaque utilisateur doit envoyer le **recto ET le verso** de sa carte d'identité/passeport,
plus un selfie, sur `/verification-identite/`. Pour chaque champ, le sélecteur de fichier du
téléphone propose automatiquement le choix entre **"Prendre une photo"** (appareil photo) et
**"Choisir un fichier"** (galerie/documents) — aucune configuration supplémentaire nécessaire,
c'est le comportement natif du navigateur avec `<input type="file" accept="image/*">`.
Tant que le statut n'est pas "Vérifié", tout le reste du site (portefeuille, MonCash, crypto)
reste bloqué.

**Comment ça marche pour toi (admin)** :
1. Va dans `/admin/accounts/identityverification/` — tu vois la liste des utilisateurs avec
   leur statut (Non soumis / En attente / Vérifié / Rejeté).
2. Clique sur une ligne "En attente" pour voir la pièce d'identité et le selfie en grand.
3. Sélectionne la ligne puis choisis l'action **"✅ Approuver"** ou **"❌ Rejeter"** en haut de la liste.
4. **Dans les deux cas, les images sont supprimées automatiquement immédiatement après ton
   choix** — on ne garde jamais un document d'identité en base plus longtemps que nécessaire.
   Seul le statut (approuvé/rejeté) reste enregistré, pas les photos.

⚠️ Sur Render, sans Cloudinary configuré (`CLOUDINARY_URL`), les fichiers uploadés sont perdus
au moindre redéploiement — configure Cloudinary avant d'ouvrir cette fonctionnalité au public
(compte gratuit sur https://cloudinary.com, l'URL de connexion est dans ton tableau de bord
Cloudinary sous "API Environment variable").

## 1. Comptes et clés API à créer

| Service | Lien | Pourquoi |
|---|---|---|
| MonCash Business | https://moncashbutton.digicelgroup.com/ | Dépôts/retraits en gourdes (HTG) |
| Documentation MonCash | https://moncashbutton.digicelgroup.com/Moncash-business/document | CLIENT_ID / CLIENT_SECRET |
| NOWPayments | https://nowpayments.io | Dépôts/retraits crypto réels (USDT TRC20/ERC20...) |
| TronGrid (vérif. TRC20) | https://www.trongrid.io | Optionnel : vérifier des transactions Tron manuellement |
| Etherscan API | https://etherscan.io/apis | Optionnel : vérifier des transactions ERC20 |
| Render | https://render.com | Hébergement + base PostgreSQL |

Une fois les clés obtenues, mets-les dans les variables d'environnement Render
(jamais dans le code — voir `.env.example`).

## 2. Base de données : SQLite en local, PostgreSQL en ligne

Le projet bascule **automatiquement** :
- **En local** (Termux ou autre) : si `DATABASE_URL` n'est pas défini dans `.env`, Django utilise SQLite (`db.sqlite3`) sans rien configurer.
- **Sur Render** : `DATABASE_URL` est fourni automatiquement par `render.yaml` (base PostgreSQL gratuite) — rien à faire non plus.

Tu n'as donc **jamais besoin de modifier `settings.py`** pour changer de base : c'est la présence ou non de `DATABASE_URL` qui décide.

## 3. Support client WhatsApp

Un bouton WhatsApp flottant (en bas à droite de chaque page) est déjà en place, relié au numéro
**+509 3168-2323**. Pour le changer plus tard, modifie le lien `https://wa.me/50931682323` dans
`templates/base.html`.

## 4. Lancer en local (Termux ou autre)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis remplis SECRET_KEY etc.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## 5. Déployer sur Render

1. Pousse ce dossier sur un dépôt GitHub/GitLab.
2. Sur Render : **New > Blueprint**, connecte le dépôt (le fichier `render.yaml` configure
   automatiquement le service web + la base PostgreSQL gratuite).
3. Dans l'onglet **Environment** du service, renseigne :
   `MONCASH_CLIENT_ID`, `MONCASH_CLIENT_SECRET`, `NOWPAYMENTS_API_KEY`,
   `NOWPAYMENTS_IPN_SECRET`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`.
4. Configure l'URL de webhook NOWPayments (dans leur tableau de bord) vers :
   `https://TON-DOMAINE.onrender.com/crypto/webhook/nowpayments/`
5. Configure l'URL de retour MonCash vers :
   `https://TON-DOMAINE.onrender.com/moncash/retour/`
6. Render exécute automatiquement `build.sh` (migrations + fichiers statiques) à chaque déploiement.

## 6. Sécurité déjà en place

- **HTTPS forcé** + cookies sécurisés + HSTS en production.
- **django-axes** : blocage automatique après 5 tentatives de connexion échouées.
- **Limitation de débit (rate limiting)** sur connexion, dépôts, retraits, conversions.
- **Transactions atomiques + verrouillage de lignes** (`select_for_update`) pour empêcher
  qu'un utilisateur retire deux fois les mêmes fonds en cliquant rapidement (race condition).
- **Vérification de signature HMAC** sur les webhooks NOWPayments : un faux webhook ne peut
  pas créditer de faux dépôts.
- **Aucun crédit de dépôt MonCash sans revérification serveur-à-serveur** — on ne fait jamais
  confiance à un simple retour de redirection.
- **Montants en `Decimal`** partout (jamais de `float` pour de l'argent).
- **Content-Security-Policy**, `X-Frame-Options: DENY`, `SECURE_CONTENT_TYPE_NOSNIFF`.
- **Mots de passe** : 10 caractères minimum + validateurs Django standards.
- **Comptes bloqués par un admin** : déconnexion immédiate, même si une session est déjà ouverte.
- **Suppression de compte** : nécessite mot de passe + confirmation tapée.
- **Historique utilisateur** : le bouton "Supprimer" masque la transaction du côté utilisateur
  uniquement — la preuve comptable reste en base pour audit (obligatoire pour un service financier,
  sinon impossible de résoudre un litige).
- **Journal d'activité** (`AccountActivityLog`) : connexions, déconnexions, inscriptions tracées.

## 7. Panneau d'administration

- Recherche d'utilisateur (nom, e-mail, téléphone) dans `/admin/accounts/customuser/`.
- Actions groupées **Bloquer / Débloquer** un ou plusieurs utilisateurs.
- Badge visuel de statut (Actif/Bloqué) et solde HTG affichés dans la liste.
- Fiche complète de chaque utilisateur (portefeuilles, transactions, journal d'activité).
- Validation manuelle recommandée pour tout retrait (HTG ou crypto) avant exécution réelle
  des fonds — les vues créent une transaction `PENDING`, à toi de déclencher l'envoi réel
  (`MonCashClient.send_payment` / `NowPaymentsClient.create_payout`) une fois vérifié en admin,
  plutôt que de l'automatiser entièrement dès le départ.

## 8. Ce qu'il reste à compléter avant un vrai lancement

- Brancher réellement `django-otp` sur les pages de connexion (2FA obligatoire pour les retraits).
- Ajouter Celery + Redis pour vérifier périodiquement les paiements MonCash en attente.
- Ajouter des limites de retrait quotidiennes/mensuelles par utilisateur.
- Ajouter un vrai flux KYC (pièce d'identité) avant d'autoriser des gros montants.
- Tests automatisés sur les fonctions de conversion et de retrait (argent réel = zéro tolérance
  aux bugs de calcul).
