import httpx

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

def send_order_notification(fcm_token: str, order_id: int, pickup: str, dropoff: str):
    if not fcm_token:
        return
    
    # Supporte les deux formats : Expo token et FCM token
    if fcm_token.startswith("ExponentPushToken"):
        try:
            pickup_short = pickup[:25] + '...' if len(pickup) > 25 else pickup
            dropoff_short = dropoff[:25] + '...' if len(dropoff) > 25 else dropoff
            payload = {
                "to": fcm_token,
                "title": "🏍️ Nouvelle commande disponible",
                "body": f"📍 {pickup_short}\n🏁 {dropoff_short}",
                "data": {"order_id": str(order_id), "type": "new_order"},
                "sound": "default",
                "priority": "high",
                "badge": 1,
            }
            with httpx.Client() as client:
                res = client.post(EXPO_PUSH_URL, json=payload, timeout=10)
                print(f"[NOTIF] Expo push envoyé : {res.status_code}")
                return res.json()
        except Exception as e:
            print(f"[NOTIF] Erreur Expo push : {e}")
    else:
        # FCM natif (ancien système)
        try:
            from firebase_admin import messaging
            from app.firebase.firebase_init import get_firebase_app
            get_firebase_app()
            message = messaging.Message(
                notification=messaging.Notification(
                    title="Nouvelle commande 🏍️",
                    body=f"De {pickup} → {dropoff}",
                ),
                data={"order_id": str(order_id), "type": "new_order"},
                token=fcm_token,
            )
            return messaging.send(message)
        except Exception as e:
            print(f"[NOTIF] Erreur FCM : {e}")


def send_notification(fcm_token: str, title: str, body: str, data: dict = None):
    if not fcm_token:
        return
    try:
        import httpx
        payload = {
            "to": fcm_token,
            "title": title,
            "body": body,
            "data": data or {},
            "sound": "default",
            "priority": "high",
        }
        with httpx.Client() as client:
            res = client.post("https://exp.host/--/api/v2/push/send", json=payload, timeout=10)
            print(f"[NOTIF] {title} — {res.status_code}")
    except Exception as e:
        print(f"[NOTIF] Erreur : {e}")


def estimate_eta(rider_lat, rider_lng, pickup_lat=None, pickup_lng=None):
    """Estimation simple du temps d'arrivée en minutes"""
    if not rider_lat or not rider_lng:
        return None
    if not pickup_lat or not pickup_lng:
        # Estimation par défaut pour Dakar
        return 10
    # Distance à vol d'oiseau en km
    import math
    R = 6371
    dlat = math.radians(pickup_lat - rider_lat)
    dlng = math.radians(pickup_lng - rider_lng)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(rider_lat)) * math.cos(math.radians(pickup_lat)) * math.sin(dlng/2)**2
    distance = R * 2 * math.asin(math.sqrt(a))
    # Vitesse moyenne moto en ville : 25 km/h
    eta_minutes = int((distance / 25) * 60)
    return max(3, min(eta_minutes, 45))  # Entre 3 et 45 minutes

def send_rider_accepted_notification(client_fcm_token: str, order_id: int, rider_name: str, rider_lat=None, rider_lng=None):
    if not client_fcm_token:
        return
    eta = estimate_eta(rider_lat, rider_lng)
    if eta:
        body = f"{rider_name or 'Votre livreur'} est en route — arrive dans ~{eta} min"
    else:
        body = f"{rider_name or 'Votre livreur'} a accepté votre commande et arrive bientôt"
    send_notification(
        fcm_token=client_fcm_token,
        title="🏍️ Livreur en route !",
        body=body,
        data={"order_id": str(order_id), "type": "order_accepted", "eta": str(eta or 0)}
    )
