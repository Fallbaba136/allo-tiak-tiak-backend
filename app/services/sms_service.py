import africastalking
import ssl
from app.core.config import settings

_initialized = False

def get_sms_service():
    global _initialized
    if not _initialized:
        ssl._create_default_https_context = ssl._create_unverified_context
        africastalking.initialize(
            username=settings.AT_USERNAME,
            api_key=settings.AT_API_KEY,
        )
        _initialized = True
    return africastalking.SMS

def send_delivery_code_sms(receiver_phone: str, code: str, order_id: int):
    # En DEV on simule le SMS
    if settings.DEV:
        print(f"[SMS-DEV] SMS simulé → {receiver_phone}: Code {code} pour commande #{order_id}")
        return {"status": "simulated"}

    # En PROD on envoie le vrai SMS
    try:
        sms = get_sms_service()
        message = f"Allô Tiak-Tiak — Votre code de réception est : {code}. Commande #{order_id}. Ne le partagez qu'au livreur."
        response = sms.send(message, [receiver_phone])
        print(f"[SMS] Envoyé à {receiver_phone}: {response}")
        return response
    except Exception as e:
        print(f"[SMS] Erreur: {e}")
        return None