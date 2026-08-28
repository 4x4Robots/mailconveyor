# MailingLists app utilities
# AD-003: SMTP password encryption
# AD-004: Email sending service

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .models import SmtpConfig, EncryptionUtils


class SmtpEmailSender:
    """
    Utility class for sending emails via SMTP.
    
    Handles the connection, authentication, and sending of emails
    using the configured SMTP settings from SmtpConfig.
    """
    
    def __init__(self, smtp_config):
        """
        Initialize with SMTP configuration.
        
        Args:
            smtp_config: SmtpConfig instance with SMTP settings
        """
        self.smtp_config = smtp_config
        self.connection = None
        self.error_message = None
    
    def _get_decrypted_password(self):
        """Get the decrypted SMTP password."""
        if self.smtp_config._password:
            return EncryptionUtils.decrypt(self.smtp_config._password)
        return None
    
    def connect(self):
        """
        Establish connection to SMTP server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            host = self.smtp_config.host
            port = self.smtp_config.port
            
            # Create connection based on SSL/TLS settings
            if self.smtp_config.use_ssl:
                self.connection = smtplib.SMTP_SSL(host, port)
            else:
                self.connection = smtplib.SMTP(host, port)
            
            # Start TLS if enabled
            if self.smtp_config.use_tls and not self.smtp_config.use_ssl:
                self.connection.starttls()
            
            # Authenticate if username and password are provided
            username = self.smtp_config.username
            password = self._get_decrypted_password()
            
            if username and password:
                self.connection.login(username, password)
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.connection = None
            return False
    
    def send_email(self, from_email, to_email, subject, body, is_html=False):
        """
        Send an email using the configured SMTP server.
        
        Args:
            from_email: Sender email address
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            is_html: Whether the body is HTML (default: False)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.connection:
            if not self.connect():
                return False, f"Failed to connect to SMTP server: {self.error_message}"
        
        try:
            # Create message
            if is_html:
                msg = MIMEMultipart('alternative')
                msg.attach(MIMEText(body, 'html'))
            else:
                msg = MIMEText(body, 'plain')
            
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = to_email
            
            # Send email
            self.connection.sendmail(from_email, [to_email], msg.as_string())
            
            return True, "Email sent successfully!"
            
        except Exception as e:
            error_msg = str(e)
            return False, f"Failed to send email: {error_msg}"
        
        finally:
            # Close connection
            if self.connection:
                try:
                    self.connection.quit()
                except:
                    pass
                self.connection = None
    
    def test_connection(self):
        """
        Test the SMTP connection without sending an email.
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.connect():
            return False, f"Failed to connect to SMTP server: {self.error_message}"
        
        try:
            # Test connection by sending a NOOP command
            self.connection.noop()
            return True, "SMTP connection successful!"
            
        except Exception as e:
            error_msg = str(e)
            return False, f"SMTP connection test failed: {error_msg}"
        
        finally:
            # Close connection
            if self.connection:
                try:
                    self.connection.quit()
                except:
                    pass
                self.connection = None


def send_test_email(smtp_config, from_email, to_email, subject, body):
    """
    Send a test email using the provided SMTP configuration.
    
    Args:
        smtp_config: SmtpConfig instance
        from_email: Sender email address
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        
    Returns:
        tuple: (success: bool, message: str)
    """
    sender = SmtpEmailSender(smtp_config)
    return sender.send_email(from_email, to_email, subject, body)


def test_smtp_connection(smtp_config):
    """
    Test the SMTP connection without sending an email.
    
    Args:
        smtp_config: SmtpConfig instance
        
    Returns:
        tuple: (success: bool, message: str)
    """
    sender = SmtpEmailSender(smtp_config)
    return sender.test_connection()