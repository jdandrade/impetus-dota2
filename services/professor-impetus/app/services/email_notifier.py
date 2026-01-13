"""
Email notification service.
Sends error notifications via email.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Simple email notifier for error alerts."""
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
    ):
        """
        Initialize email notifier.
        
        Args:
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port
            smtp_user: SMTP authentication username
            smtp_password: SMTP authentication password
            from_email: Sender email address
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        
        logger.info(f"Email notifier initialized with server: {smtp_server}")
    
    def send_error_notification(
        self,
        to_email: str,
        subject: str,
        error_log: str,
    ) -> bool:
        """
        Send an error notification email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            error_log: Error log content
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg["Subject"] = f"[Professor Impetus] {subject}"
            
            body = f"""
Professor Impetus encountered an error:

{error_log}

---
This is an automated message from Professor Impetus.
            """.strip()
            
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Error notification sent to {to_email}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to send error notification: {e}")
            return False


class NoOpEmailNotifier:
    """No-op email notifier for when email is not configured."""
    
    def send_error_notification(
        self,
        to_email: str,
        subject: str,
        error_log: str,
    ) -> bool:
        """Log error but don't send email."""
        logger.warning(
            f"Email not configured. Would send to {to_email}: {subject}"
        )
        return False


def create_email_notifier(
    smtp_server: Optional[str] = None,
    smtp_port: int = 587,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
    from_email: Optional[str] = None,
) -> EmailNotifier | NoOpEmailNotifier:
    """
    Factory function to create an email notifier.
    
    Returns NoOpEmailNotifier if configuration is incomplete.
    """
    if all([smtp_server, smtp_user, smtp_password, from_email]):
        return EmailNotifier(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            from_email=from_email,
        )
    else:
        logger.warning("Email configuration incomplete, using no-op notifier")
        return NoOpEmailNotifier()
