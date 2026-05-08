from firebase_admin import messaging
from app.firebase.firebase_init import get_firebase_app

def send_order_notification(fcm_token: str, order_id: int, pickup: str, dropoff: str):
    get_firebase_app()

    message = messaging.Message(
        notification=messaging.Notification(
            title="Nouvelle commande 🛵",
            body=f"De {pickup} → {dropoff}",
        ),
        data={
            "order_id": str(order_id),
            "type": "new_order",
        },
        token=fcm_token,
    )

    response = messaging.send(message)
    return response