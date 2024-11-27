import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict
from pathlib import Path
import json
import os
from datetime import datetime
from src.config import Config

class EmailSender:
    def __init__(self, config: Config):
        """
        Initialize the email sender.
        
        Args:
            config (Config): Configuration instance
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Get email configuration
        self.smtp_server = config.get('email', 'smtp_server', 'smtp.gmail.com')
        self.smtp_port = config.get('email', 'smtp_port', 587)
        self.username = config.get('email', 'email')
        self.password = config.get('email', 'password')
        self.use_tls = config.get('email', 'use_tls', True)
        
        # Validate configuration
        if not all([self.username, self.password]):
            self.logger.error("Email configuration incomplete")
        
        # Track email history
        self.email_history = []
    
    def _setup_logging(self):
        """Configure logging for the email sender"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """
        Load email configuration from file or environment variables.
        
        Args:
            config_path (Optional[str]): Path to configuration file
            
        Returns:
            Dict: Email configuration
        """
        config = {}
        
        # Try loading from file
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading config file: {str(e)}")
        
        # Fall back to environment variables
        config.update({
            'email': os.getenv('EMAIL_ADDRESS', config.get('email')),
            'password': os.getenv('EMAIL_PASSWORD', config.get('password')),
            'smtp_server': os.getenv('SMTP_SERVER', config.get('smtp_server', 'smtp.gmail.com')),
            'smtp_port': int(os.getenv('SMTP_PORT', config.get('smtp_port', 587)))
        })
        
        return config
    
    def send_email(self,
                  to_email: str,
                  subject: str,
                  body: str,
                  attachments: Optional[List[str]] = None,
                  cc: Optional[List[str]] = None,
                  bcc: Optional[List[str]] = None,
                  html: bool = False) -> Dict:
        """
        Send an email.
        
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            body (str): Email body
            attachments (Optional[List[str]]): List of file paths to attach
            cc (Optional[List[str]]): List of CC recipients
            bcc (Optional[List[str]]): List of BCC recipients
            html (bool): Whether the body contains HTML
            
        Returns:
            Dict: Result of the email sending operation
        """
        if not all([self.username, self.password]):
            return {
                'success': False,
                'error': 'Email credentials not configured'
            }
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add CC recipients
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # Add BCC recipients
            if bcc:
                msg['Bcc'] = ', '.join(bcc)
            
            # Add body
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    self._add_attachment(msg, file_path)
            
            # Get all recipients
            all_recipients = [to_email]
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg, from_addr=self.username, to_addrs=all_recipients)
            
            # Log success
            self._log_email(to_email, subject, success=True)
            
            return {
                'success': True,
                'message': 'Email sent successfully',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error sending email: {error_msg}")
            self._log_email(to_email, subject, success=False, error=error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """
        Add an attachment to the email message.
        
        Args:
            msg (MIMEMultipart): Email message
            file_path (str): Path to file to attach
        """
        try:
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                
            encoders.encode_base64(part)
            
            # Add header
            filename = Path(file_path).name
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            
            msg.attach(part)
            
        except Exception as e:
            self.logger.error(f"Error adding attachment {file_path}: {str(e)}")
            raise
    
    def _log_email(self, 
                   recipient: str, 
                   subject: str, 
                   success: bool, 
                   error: Optional[str] = None):
        """
        Log email sending attempt.
        
        Args:
            recipient (str): Email recipient
            subject (str): Email subject
            success (bool): Whether the email was sent successfully
            error (Optional[str]): Error message if sending failed
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'recipient': recipient,
            'subject': subject,
            'success': success,
            'error': error
        }
        
        self.email_history.append(log_entry)
        
        # Trim history if it gets too long
        if len(self.email_history) > 1000:
            self.email_history = self.email_history[-1000:]
    
    def get_email_history(self, 
                         limit: Optional[int] = None, 
                         success_only: bool = False) -> List[Dict]:
        """
        Get history of sent emails.
        
        Args:
            limit (Optional[int]): Maximum number of entries to return
            success_only (bool): Whether to return only successful emails
            
        Returns:
            List[Dict]: Email history entries
        """
        history = self.email_history
        
        if success_only:
            history = [entry for entry in history if entry['success']]
        
        if limit:
            history = history[-limit:]
            
        return history
    
    def test_connection(self) -> Dict:
        """
        Test SMTP connection and credentials.
        
        Returns:
            Dict: Connection test results
        """
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                
            return {
                'success': True,
                'message': 'Connection test successful'
            }
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Connection test failed: {error_msg}")
            
            return {
                'success': False,
                'error': error_msg
            }
