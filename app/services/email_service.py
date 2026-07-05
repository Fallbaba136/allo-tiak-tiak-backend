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


def send_kyc_approved_notification(rider_phone: str, rider_name: str):
    if not settings.RESEND_API_KEY:
        print(f"[EMAIL] KYC approuvé pour {rider_phone}")
        return

    resend.api_key = settings.RESEND_API_KEY

    try:
        resend.Emails.send({
            "from": "Allô Tiak-Tiak <onboarding@resend.dev>",
            "to": rider_phone + "@placeholder.com",  # sera remplacé par vrai email plus tard
            "subject": "✅ Votre compte Allô Tiak-Tiak est activé !",
            "html": f"""
            <div style="font-family:system-ui;max-width:600px;margin:0 auto;padding:24px">
                <h2 style="color:#00C853">✅ Compte activé — Allô Tiak-Tiak</h2>
                <p>Bonjour {rider_name or 'Livreur'},</p>
                <p>Votre dossier a été vérifié et approuvé. Vous pouvez maintenant accéder à la plateforme et commencer à recevoir des commandes.</p>
                <div style="background:#f5f5f5;border-radius:8px;padding:16px;margin:20px 0">
                    <p style="margin:0;color:#333">🏍️ Connectez-vous à l'application Allô Tiak-Tiak</p>
                    <p style="margin:8px 0 0;color:#777;font-size:13px">Numéro : {rider_phone}</p>
                </div>
                <p style="color:#777;font-size:12px">Allô Tiak-Tiak — Dakar, Sénégal</p>
            </div>
            """
        })
        print(f"[EMAIL] Notification approbation envoyée pour {rider_phone}")
    except Exception as e:
        print(f"[EMAIL] Erreur approbation : {e}")

def send_dispute_notification(
    order_id: int,
    client_phone: str,
    rider_phone: str,
    rider_name: str,
    reason: str,
    description: str,
    admin_email: str = None,
):
    if not settings.RESEND_API_KEY:
        print(f"[EMAIL] Litige ouvert commande #{order_id} — config manquante")
        return
    resend.api_key = settings.RESEND_API_KEY
    html = f"""
    <div style="font-family:system-ui;max-width:600px;margin:0 auto;padding:24px">
        <h2 style="color:#FF9800">⚠️ Nouveau litige — Allô Tiak-Tiak</h2>
        <p>Un client vient d'ouvrir un litige sur une commande.</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0">
            <tr style="background:#f5f5f5">
                <td style="padding:10px;font-weight:600">Commande</td>
                <td style="padding:10px">#{order_id}</td>
            </tr>
            <tr>
                <td style="padding:10px;font-weight:600">Client</td>
                <td style="padding:10px">{client_phone}</td>
            </tr>
            <tr style="background:#f5f5f5">
                <td style="padding:10px;font-weight:600">Livreur</td>
                <td style="padding:10px">{rider_name or rider_phone}</td>
            </tr>
            <tr>
                <td style="padding:10px;font-weight:600">Motif</td>
                <td style="padding:10px">{reason}</td>
            </tr>
            <tr style="background:#f5f5f5">
                <td style="padding:10px;font-weight:600">Description</td>
                <td style="padding:10px">{description}</td>
            </tr>
        </table>
        <a href="https://allo-tiak-tiak-admin.netlify.app"
           style="display:inline-block;background:#FF9800;color:#000;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700">
            Traiter le litige →
        </a>
        <p style="color:#777;font-size:12px;margin-top:24px">Allô Tiak-Tiak Admin — Dakar, Sénégal</p>
    </div>
    """
    # Notifier l'admin
    if settings.ADMIN_EMAIL:
        try:
            resend.Emails.send({
                "from": "Allô Tiak-Tiak <onboarding@resend.dev>",
                "to": settings.ADMIN_EMAIL,
                "subject": f"⚠️ Litige ouvert — Commande #{order_id}",
                "html": html,
            })
            print(f"[EMAIL] Litige notifié à l'admin pour commande #{order_id}")
        except Exception as e:
            print(f"[EMAIL] Erreur notification admin : {e}")


def send_dispute_resolution_notification(
    order_id: int,
    status: str,
    resolution_note: str,
    client_phone: str,
    accused_phone: str,
):
    if not settings.RESEND_API_KEY or not settings.ADMIN_EMAIL:
        print(f"[EMAIL] Resolution litige #{order_id} — config manquante")
        return
    resend.api_key = settings.RESEND_API_KEY

    if status == "resolved":
        verdict = "✅ En faveur du client"
        color = "#00C853"
        client_msg = "Votre litige a ete resolu en votre faveur. La commande a ete annulee."
        rider_msg = "Le litige ouvert sur la commande #{} a ete resolu en faveur du client. La commission ne sera pas prelevee.".format(order_id)
    elif status == "rejected":
        verdict = "❌ Litige rejete"
        color = "#FF4444"
        client_msg = "Votre litige a ete examine et rejete. La commande est confirmee."
        rider_msg = "Le litige ouvert sur la commande #{} a ete rejete. La commande est confirmee normalement.".format(order_id)
    else:
        verdict = "🔍 Litige clos"
        color = "#FF9800"
        client_msg = "Votre litige a ete clos."
        rider_msg = "Le litige sur la commande #{} a ete clos.".format(order_id)

    def make_html(message):
        return f"""
        <div style="font-family:system-ui;max-width:600px;margin:0 auto;padding:24px">
            <h2 style="color:{color}">⚖️ Decision sur le litige — Commande #{order_id}</h2>
            <p>{message}</p>
            <div style="background:#f5f5f5;border-radius:8px;padding:16px;margin:20px 0">
                <p style="margin:0;font-weight:600">Verdict : {verdict}</p>
                <p style="margin:8px 0 0;color:#555">{resolution_note or 'Aucune note supplementaire.'}</p>
            </div>
            <p style="color:#777;font-size:12px">Allô Tiak-Tiak — Dakar, Sénégal</p>
        </div>
        """

    # Email à l'admin
    try:
        resend.Emails.send({
            "from": "Allô Tiak-Tiak <onboarding@resend.dev>",
            "to": settings.ADMIN_EMAIL,
            "subject": f"⚖️ Litige #{order_id} résolu — {verdict}",
            "html": make_html(f"Résolution de la commande #{order_id}."),
        })
    except Exception as e:
        print(f"[EMAIL] Erreur email admin resolution : {e}")


def send_support_message(user_phone: str, subject: str, message: str):
    if not settings.RESEND_API_KEY or not settings.ADMIN_EMAIL:
        print(f"[EMAIL] Support — config manquante")
        return
    resend.api_key = settings.RESEND_API_KEY
    try:
        resend.Emails.send({
            "from": "Allo Tiak-Tiak <onboarding@resend.dev>",
            "to": settings.ADMIN_EMAIL,
            "subject": f"[Support] {subject}",
            "html": f"""
            <div style="font-family:system-ui;max-width:600px;margin:0 auto;padding:24px">
                <h2 style="color:#00C853">📩 Nouveau message support</h2>
                <table style="width:100%;border-collapse:collapse;margin:20px 0">
                    <tr style="background:#f5f5f5">
                        <td style="padding:10px;font-weight:600">Utilisateur</td>
                        <td style="padding:10px">{user_phone}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px;font-weight:600">Sujet</td>
                        <td style="padding:10px">{subject}</td>
                    </tr>
                    <tr style="background:#f5f5f5">
                        <td style="padding:10px;font-weight:600">Message</td>
                        <td style="padding:10px">{message}</td>
                    </tr>
                </table>
                <p style="color:#777;font-size:12px">Allo Tiak-Tiak — Dakar, Senegal</p>
            </div>
            """
        })
        print(f"[EMAIL] Message support envoye depuis {user_phone}")
    except Exception as e:
        print(f"[EMAIL] Erreur support : {e}")
