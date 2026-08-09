import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from app.models import User, EmailLog
from app import db

def send_user_smtp_email(user_id, recipient_email, subject, html_content, pdf_attachment_path=None, cc_emails=None, bcc_emails=None):
    """
    Sends email using the specific user's stored Outlook SMTP credentials.
    """
    try:
        # 1. యూజర్ యొక్క SMTP వివరాలను డేటాబేస్ నుండి తీసుకోవడం
        user = User.query.get(user_id)
        if not user or not user.smtp_email or not user.smtp_password:
            EmailLog.log_email(user_id, recipient_email, subject, "Failed", "User SMTP credentials not configured in profile")
            return False, "SMTP credentials not configured in your profile."

        sender_email = user.smtp_email
        sender_password = user.smtp_password  # Outlook App Password

        # 2. మెయిల్ స్ట్రక్చర్ క్రియేట్ చేయడం
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # CC మరియు BCC లిస్ట్ హ్యాండ్లింగ్
        recipients_list = [recipient_email]
        
        if cc_emails:
            clean_cc = [cc.strip() for cc in cc_emails if cc.strip()]
            if clean_cc:
                msg['CC'] = ", ".join(clean_cc)
                recipients_list.extend(clean_cc)

        if bcc_emails:
            clean_bcc = [bcc.strip() for bcc in bcc_emails if bcc.strip()]
            recipients_list.extend(clean_bcc)

        # HTML బాడీ యాడ్ చేయడం
        msg.attach(MIMEText(html_content, 'html'))

        # 3. PDF అటాచ్‌మెంట్ ఉంటే దాన్ని జత చేయడం
        if pdf_attachment_path and os.path.exists(pdf_attachment_path):
            with open(pdf_attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                filename = os.path.basename(pdf_attachment_path)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {filename}"
                )
                msg.attach(part)

        # 4. Outlook SMTP సర్వర్‌కి కనెక్ట్ అయి మెయిల్ పంపడం (Port 587 with STARTTLS)
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)
        
        server.sendmail(sender_email, recipients_list, msg.as_string())
        server.quit()

        # సక్సెస్ లాగ్ రికార్డ్ చేయడం
        EmailLog.log_email(user_id, recipient_email, subject, "Sent")
        return True, "Email sent successfully via Outlook SMTP!"

    except Exception as e:
        error_msg = str(e)
        EmailLog.log_email(user_id, recipient_email, subject, "Failed", error_msg)
        return False, f"SMTP Error: {error_msg}"