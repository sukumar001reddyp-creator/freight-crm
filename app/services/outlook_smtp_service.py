import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase  # <--- ఇక్కడ సరిదిద్దబడింది
from email import encoders
import os
from app.models import User, EmailLog
from app import db

def send_user_smtp_email(user_id, recipient_email, subject, html_content, pdf_attachment_path=None):
    """
    లాగిన్ అయిన యూజర్ యొక్క వ్యక్తిగత Outlook SMTP క్రెడెన్షియల్స్ ఉపయోగించి మెయిల్ పంపడానికి
    """
    user = User.query.get(user_id)
    if not user or not user.smtp_email or not user.smtp_password:
        return False, "User Outlook SMTP settings not configured."
        
    sender_email = user.smtp_email
    sender_password = user.smtp_password
    
    # Outlook SMTP Configuration
    smtp_server = "smtp.office365.com"
    smtp_port = 587
    
    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Body content
        msg.attach(MIMEText(html_content, 'html'))
        
        # Attachment handling
        if pdf_attachment_path and os.path.exists(pdf_attachment_path):
            with open(pdf_attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            filename = os.path.basename(pdf_attachment_path)
            part.add_header("Content-Disposition", f"attachment; filename= {filename}")
            msg.attach(part)
            
        # Connect to server and send
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        
        # Log success
        log = EmailLog(user_id=user.id, recipient=recipient_email, subject=subject, status="Success")
        db.session.add(log)
        db.session.commit()
        
        return True, "Email sent successfully"
        
    except Exception as e:
        # Log failure
        try:
            log = EmailLog(user_id=user.id, recipient=recipient_email, subject=subject, status="Failed", error_message=str(e))
            db.session.add(log)
            db.session.commit()
        except:
            pass
            
        return False, str(e)