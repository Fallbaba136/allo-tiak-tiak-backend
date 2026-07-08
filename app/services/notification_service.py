import httpx

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

def send_order_notification(fcm_token: str, order_id: int, pickup: str, dropoff: str):
    if not fcm_token:
        return
    
    # Supporte les deux formats : Expo token et FCM token
    if fcm_token.startswith("ExponentPushToken"):
        try:
            payload = {
                "to": fcm_token,
                "title": "Nouvelle commande 🏍️",
                "body": f"De {pickup[:30]} → {dropoff[:30]}",
                "data": {"order_id": str(order_id), "type": "new_order"},
                "sound": "default",
                "priority": "high",
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
