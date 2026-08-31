from app.models import Notification
from app import db
from datetime import datetime, timezone, timedelta

def create_notification(title, message, target_url):
    # 30 రోజులకు పైబడిన పాత నోటిఫికేషన్లను డిలీట్ చేయడం
    threshold = datetime.now(timezone.utc) - timedelta(days=30)
    Notification.query.filter(Notification.created_at < threshold).delete()

    # గరిష్టంగా 50 కన్నా ఎక్కువ ఉంటే అత్యంత పాతదాన్ని తొలగించడం
    count = Notification.query.count()
    if count >= 50:
        oldest = Notification.query.order_by(Notification.created_at.asc()).first()
        if oldest:
            db.session.delete(oldest)

    # కొత్త నోటిఫికేషన్‌ను సేవ్ చేయడం
    notif = Notification(
        title=title,
        message=message,
        target_url=target_url,
        is_read=False
    )
    db.session.add(notif)
    db.session.commit()