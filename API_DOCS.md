# Allô Tiak-Tiak — Documentation API

**Base URL** : `https://allo-tiak-tiak-backend.onrender.com`  
**Version** : 0.1.0  
**Format** : JSON  
**Auth** : Bearer Token JWT (header `Authorization: Bearer <token>`)

---

## Sommaire

1. [Authentification](#authentification)
2. [Livreurs](#livreurs)
3. [Clients](#clients)
4. [Commandes](#commandes)
5. [Localisation](#localisation)
6. [Litiges](#litiges)
7. [Avis](#avis)
8. [Statistiques](#statistiques)
9. [Flux complet](#flux-complet)
10. [Codes d'erreur](#codes-derreur)

---

## Authentification

### Demander un OTP

```
POST /auth/otp/start
```

Envoie un code OTP par SMS au numéro indiqué. En mode DEV, le code est retourné directement dans la réponse.

**Body**
```json
{
  "phone": "+221700000000"
}
```

**Réponse**
```json
{
  "message": "OTP generated (MVP).",
  "expires_in_minutes": 10,
  "otp_for_test": "123456"
}
```

> `otp_for_test` n'apparaît qu'en mode DEV.

---

### Vérifier l'OTP et obtenir un token

```
POST /auth/otp/verify
```

Vérifie le code OTP et retourne un JWT. Si c'est la première connexion, crée le compte avec le rôle indiqué.

**Body**
```json
{
  "phone": "+221700000000",
  "code": "123456",
  "role": "client"
}
```

| Champ | Type | Obligatoire | Valeurs |
|-------|------|-------------|---------|
| `phone` | string | ✅ | Format international ex: `+221xxxxxxxxx` |
| `code` | string | ✅ | Code OTP reçu par SMS |
| `role` | string | ❌ | `client` (défaut) ou `rider` |

**Réponse**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

> ⚠️ Le token expire après 60 minutes. Il faut en demander un nouveau via `/auth/otp/start`.

---

## Livreurs

> Tous les endpoints livreurs nécessitent un token JWT avec `role: rider`.

### Créer / Mettre à jour le profil livreur

```
PUT /riders/me
Authorization: Bearer <token>
```

**Body**
```json
{
  "full_name": "Moussa Diop",
  "zone": "Dakar Centre",
  "payment_provider": "wave",
  "payment_phone": "+221770000000"
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `full_name` | string | Nom complet du livreur |
| `zone` | string | Zone de livraison (ex: Plateau, Almadies) |
| `payment_provider` | string | `wave` ou `orange_money` |
| `payment_phone` | string | Numéro Wave/Orange Money |

**Réponse**
```json
{
  "phone": "+221700000001",
  "full_name": "Moussa Diop",
  "zone": "Dakar Centre",
  "payment_provider": "wave",
  "payment_phone": "+221770000000",
  "is_available": false,
  "is_verified": false
}
```

---

### Consulter son profil livreur

```
GET /riders/me
Authorization: Bearer <token>
```

**Réponse** : même structure que `PUT /riders/me`

---

### Mettre à jour sa disponibilité

```
POST /riders/me/availability?is_available=true
Authorization: Bearer <token>
```

| Paramètre query | Type | Description |
|-----------------|------|-------------|
| `is_available` | boolean | `true` = disponible, `false` = indisponible |

**Réponse**
```json
{
  "message": "Disponibilité mise à jour"
}
```

---

### Lister les livreurs disponibles

```
GET /riders/available?zone=Plateau
```

> Endpoint public — pas d'auth requise.

| Paramètre query | Type | Description |
|-----------------|------|-------------|
| `zone` | string | Optionnel — filtrer par zone |

**Réponse**
```json
[
  {
    "phone": "+221700000001",
    "full_name": "Moussa Diop",
    "zone": "Dakar Centre",
    "payment_provider": "wave",
    "payment_phone": "+221770000000",
    "is_available": true,
    "is_verified": true
  }
]
```

---

### Mettre à jour le token FCM (notifications push)

```
POST /riders/me/fcm-token
Authorization: Bearer <token>
```

**Body**
```json
{
  "fcm_token": "token_firebase_ici"
}
```

---

### [ADMIN] Vérifier un livreur

```
POST /riders/admin/riders/verify?phone=+221700000001
X-Admin-Secret: <admin_secret>
```

Permet à l'admin de valider un livreur (`is_verified = true`).

---

## Clients

> Tous les endpoints clients nécessitent un token JWT avec `role: client`.

### Consulter son profil client

```
GET /clients/me
Authorization: Bearer <token>
```

**Réponse**
```json
{
  "phone": "+221700000000",
  "full_name": "Amadou Sall",
  "address": "Plateau, Dakar"
}
```

---

### Créer / Mettre à jour son profil client

```
PUT /clients/me
Authorization: Bearer <token>
```

**Body**
```json
{
  "full_name": "Amadou Sall",
  "address": "Plateau, Dakar"
}
```

**Réponse** : même structure que `GET /clients/me`

---

## Commandes

### Créer une commande

```
POST /orders/
Authorization: Bearer <token>  (role: client)
```

**Body**
```json
{
  "pickup_address": "Plateau, Dakar",
  "delivery_address": "Almadies, Dakar",
  "description": "Colis fragile",
  "zone": "Dakar Centre",
  "rider_id": 2,
  "receiver_phone": "+221700000001",
  "amount": 2000
}
```

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `pickup_address` | string | ✅ | Adresse de ramassage |
| `delivery_address` | string | ✅ | Adresse de livraison |
| `description` | string | ❌ | Description du colis |
| `zone` | string | ❌ | Zone géographique |
| `rider_id` | integer | ✅ | ID du livreur choisi |
| `receiver_phone` | string | ✅ | Téléphone du destinataire |
| `amount` | number | ✅ | Montant en FCFA |

**Réponse**
```json
{
  "id": 1,
  "client_id": 1,
  "rider_id": 2,
  "pickup_address": "Plateau, Dakar",
  "delivery_address": "Almadies, Dakar",
  "description": "Colis fragile",
  "zone": null,
  "receiver_phone": "+221700000001",
  "status": "pending",
  "amount": 2000.0,
  "commission": null,
  "payment_method": null,
  "payment_status": "pending",
  "accepted_at": null,
  "picked_up_at": null,
  "delivered_at": null,
  "confirmed_at": null,
  "cancelled_at": null,
  "payment_confirmed_at": null,
  "created_at": "2026-05-09T13:09:19.940886Z"
}
```

---

### Mes commandes

```
GET /orders/my-orders
Authorization: Bearer <token>
```

Retourne les commandes du client connecté, ou les livraisons du livreur connecté.

**Réponse** : liste d'objets `OrderOut` (même structure que ci-dessus)

---

### Mettre à jour le statut d'une commande

```
PATCH /orders/{order_id}/status
Authorization: Bearer <token>
```

**Body**
```json
{
  "status": "accepted"
}
```

**Statuts possibles selon le rôle :**

| Rôle | Statuts autorisés |
|------|-------------------|
| `rider` | `accepted`, `in_progress`, `delivered` |
| `client` | `cancelled`, `disputed` |

**Cycle de vie d'une commande :**

```
pending → accepted → in_progress → delivered → confirmed
                                             ↘ cancelled / disputed
```

> Quand le livreur passe en `accepted`, un code de livraison à 6 chiffres est généré et envoyé par SMS au destinataire.

---

### Vérifier le code de livraison

```
POST /orders/{order_id}/verify-delivery
Authorization: Bearer <token>  (role: rider)
```

**Body**
```json
{
  "code": "727274"
}
```

> Le code est valable 24h. Si correct, la commande passe en `confirmed`.

**Réponse** : objet `OrderOut` avec `status: confirmed`

---

### Résumé du paiement

```
GET /orders/{order_id}/payment-summary
Authorization: Bearer <token>  (role: client)
```

> Disponible uniquement quand `status: confirmed`

**Réponse**
```json
{
  "amount": 2000,
  "commission": 100,
  "rider_net": 1900,
  "payment_method": "wave",
  "rider_payment_phone": "+221770000000"
}
```

---

### Confirmer le paiement

```
POST /orders/{order_id}/confirm-payment
Authorization: Bearer <token>  (role: rider)
```

**Body**
```json
{
  "payment_method": "wave"
}
```

| Valeurs `payment_method` | Description |
|--------------------------|-------------|
| `wave` | Paiement via Wave |
| `orange_money` | Paiement via Orange Money |

**Réponse** : objet `OrderOut` avec `payment_status: paid` et `commission: 100.0` (5% du montant)

---

## Localisation

### Mettre à jour sa position (livreur)

```
POST /location/update
Authorization: Bearer <token>  (role: rider)
```

**Body**
```json
{
  "latitude": 14.6937,
  "longitude": -17.4441,
  "order_id": 1
}
```

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `latitude` | number | ✅ | Latitude GPS |
| `longitude` | number | ✅ | Longitude GPS |
| `order_id` | integer | ❌ | Commande en cours |

**Réponse**
```json
{
  "rider_id": 2,
  "latitude": 14.6937,
  "longitude": -17.4441,
  "order_id": 1,
  "updated_at": "2026-05-09T13:15:00Z"
}
```

---

### Obtenir la position du livreur

```
GET /location/order/{order_id}
Authorization: Bearer <token>
```

**Réponse** : même structure que ci-dessus

> À appeler en polling toutes les 5-10 secondes pour le suivi en temps réel.

---

## Litiges

### Créer un litige

```
POST /disputes/
Authorization: Bearer <token>
```

**Body**
```json
{
  "order_id": 1,
  "reason": "Colis endommagé",
  "description": "Le colis est arrivé avec des dommages visibles."
}
```

**Réponse**
```json
{
  "id": 1,
  "complainant_id": 1,
  "accused_id": 2,
  "order_id": 1,
  "reason": "Colis endommagé",
  "description": "Le colis est arrivé avec des dommages visibles.",
  "status": "open",
  "resolution_note": null,
  "expires_at": "2026-05-16T13:00:00Z",
  "created_at": "2026-05-09T13:00:00Z"
}
```

---

### Mes litiges

```
GET /disputes/my-disputes
Authorization: Bearer <token>
```

**Réponse** : liste d'objets `DisputeOut`

---

### [ADMIN] Résoudre un litige

```
PATCH /disputes/{dispute_id}/resolve
Authorization: Bearer <token>  (role: admin)
```

**Body**
```json
{
  "status": "resolved",
  "resolution_note": "Remboursement accordé au client."
}
```

| Valeurs `status` | Description |
|------------------|-------------|
| `resolved` | Litige résolu |
| `rejected` | Litige rejeté |

---

## Avis

### Laisser un avis sur un livreur

```
POST /reviews/
Authorization: Bearer <token>  (role: client)
```

**Body**
```json
{
  "order_id": 1,
  "rating": 5,
  "comment": "Très rapide et professionnel !"
}
```

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `order_id` | integer | ✅ | ID de la commande |
| `rating` | integer | ✅ | Note de 1 à 5 |
| `comment` | string | ❌ | Commentaire libre |

---

### Avis d'un livreur

```
GET /reviews/rider/{rider_id}
```

> Endpoint public — pas d'auth requise.

**Réponse** : liste d'objets `ReviewOut`

---

### Résumé de notation d'un livreur

```
GET /reviews/rider/{rider_id}/summary
```

> Endpoint public — pas d'auth requise.

**Réponse**
```json
{
  "rider_id": 2,
  "average_rating": 4.5,
  "total_reviews": 12,
  "total_orders": 20
}
```

---

## Statistiques

### Bilan mensuel client

```
GET /stats/client/monthly?month=5&year=2026
Authorization: Bearer <token>  (role: client)
```

---

### Bilan mensuel livreur

```
GET /stats/rider/monthly?month=5&year=2026
Authorization: Bearer <token>  (role: rider)
```

---

## Flux complet

Voici le flux typique d'une livraison de bout en bout :

```
1. Client demande OTP          POST /auth/otp/start
2. Client vérifie OTP          POST /auth/otp/verify  (role: client)
3. Livreur demande OTP         POST /auth/otp/start
4. Livreur vérifie OTP         POST /auth/otp/verify  (role: rider)
5. Livreur crée son profil     PUT  /riders/me
6. Livreur se rend disponible  POST /riders/me/availability?is_available=true
7. Client liste les livreurs   GET  /riders/available
8. Client crée une commande    POST /orders/
9. Livreur accepte             PATCH /orders/{id}/status  {"status": "accepted"}
10. Livreur prend le colis     PATCH /orders/{id}/status  {"status": "in_progress"}
11. Livreur livre              PATCH /orders/{id}/status  {"status": "delivered"}
12. Livreur vérifie le code    POST /orders/{id}/verify-delivery
13. Client voit résumé paiement GET /orders/{id}/payment-summary
14. Livreur confirme paiement  POST /orders/{id}/confirm-payment
15. Client laisse un avis      POST /reviews/
```

---

## Codes d'erreur

| Code | Description |
|------|-------------|
| `400` | Requête invalide (champ manquant, code OTP incorrect, etc.) |
| `401` | Token manquant ou expiré |
| `403` | Action non autorisée pour ce rôle |
| `404` | Ressource introuvable |
| `422` | Erreur de validation des données |
| `429` | Trop de demandes OTP (attendre 60s) |

---

## Notes importantes

- **Commission** : 5% sur chaque commande, calculée au moment de la confirmation du paiement
- **Code de livraison** : valable 24h après génération
- **Token JWT** : expire après 60 minutes
- **OTP** : expire après 10 minutes, une nouvelle demande possible après 60s
- **Paiement** : Manuel MVP — Wave ou Orange Money, confirmé manuellement par le livreur
- **Géolocalisation** : Polling recommandé toutes les 5-10 secondes
