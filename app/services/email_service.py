import resend
from app.core.config import settings

def send_kyc_notification(rider_phone: str, rider_name: str, user_id: int):
    if not settings.RESEND_API_KEY or not settings.ADMIN_EMAIL:
        print(f"[EMAIL] Config manquante — KYC soumis par {rider_phone}")
        return

    resend.api_key = settings.RESEND_API_KEY

    try:
        resend.Emails.send({
            "from": "Allô Tiak-Tiak <onboarding@resend.dev>",
            "to": settings.ADMIN_EMAIL,
            "subject": f"🏍️ Nouveau dossier KYC — {rider_name or rider_phone}",
            "html": f"""
            <div style="font-family:system-ui;max-width:600px;margin:0 auto;padding:24px">
                <h2 style="color:#00C853">🏍️ Allô Tiak-Tiak — Nouveau dossier KYC</h2>
                <p>Un livreur vient de soumettre son dossier de vérification.</p>
                <table style="width:100%;border-collapse:collapse;margin:20px 0">
                    <tr style="background:#f5f5f5">
                        <td style="padding:10px;font-weight:600">Livreur</td>
                        <td style="padding:10px">{rider_name or 'Non renseigné'}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px;font-weight:600">Téléphone</td>
                        <td style="padding:10px">{rider_phone}</td>
                    </tr>
                    <tr style="background:#f5f5f5">
                        <td style="padding:10px;font-weight:600">User ID</td>
                        <td style="padding:10px">#{user_id}</td>
                    </tr>
                </table>
                <a href="https://allo-tiak-tiak-admin.netlify.app" 
                   style="display:inline-block;background:#00C853;color:#000;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700">
                    Vérifier le dossier →
                </a>
                <p style="color:#777;font-size:12px;margin-top:24px">
                    Allô Tiak-Tiak Admin — Dakar, Sénégal
                </p>
            </div>
            """
        })
        print(f"[EMAIL] Notification KYC envoyée pour {rider_phone}")
    except Exception as e:
        print(f"[EMAIL] Erreur : {e}")