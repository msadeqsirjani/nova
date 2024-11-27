from pathlib import Path
from typing import Dict, Any
import os
from dotenv import load_dotenv
import logging

class Config:
    def __init__(self, env_path: str = None):
        """
        Initialize configuration manager.
        
        Args:
            env_path (str): Path to .env file (optional)
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Load environment variables
        self._load_env(env_path)
        
        # Initialize configuration sections
        self.email = self._load_email_config()
        self.speech = self._load_speech_config()
        self.database = self._load_database_config()
        self.api_keys = self._load_api_config()
    
    def _setup_logging(self):
        """Configure logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _load_env(self, env_path: str = None):
        """
        Load environment variables from .env file.
        
        Args:
            env_path (str): Path to .env file
        """
        try:
            if env_path and Path(env_path).exists():
                load_dotenv(env_path)
            else:
                # Try to find .env file in common locations
                possible_paths = [
                    '.env',
                    '../.env',
                    '../../.env',
                    'src/config/.env'
                ]
                
                for path in possible_paths:
                    if Path(path).exists():
                        load_dotenv(path)
                        self.logger.info(f"Loaded environment from {path}")
                        break
                
        except Exception as e:
            self.logger.error(f"Error loading environment variables: {str(e)}")
    
    def _load_email_config(self) -> Dict[str, Any]:
        """Load email configuration from environment variables"""
        return {
            'email': os.getenv('EMAIL_ADDRESS'),
            'password': os.getenv('EMAIL_PASSWORD'),
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'use_tls': os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'
        }
    
    def _load_speech_config(self) -> Dict[str, Any]:
        """Load speech recognition configuration"""
        return {
            'language': os.getenv('SPEECH_LANGUAGE', 'en-US'),
            'timeout': int(os.getenv('SPEECH_TIMEOUT', '5')),
            'phrase_threshold': float(os.getenv('SPEECH_PHRASE_THRESHOLD', '0.3')),
            'voice_gender': os.getenv('VOICE_GENDER', 'female')
        }
    
    def _load_database_config(self) -> Dict[str, Any]:
        """Load database configuration"""
        return {
            'path': os.getenv('DB_PATH', 'conversation_history.db'),
            'max_history': int(os.getenv('MAX_HISTORY', '10')),
            'context_ttl': int(os.getenv('CONTEXT_TTL', '300'))
        }
    
    def _load_api_config(self) -> Dict[str, Any]:
        """Load API keys and configurations"""
        return {
            'openweather_api_key': os.getenv('OPENWEATHER_API_KEY'),
            'google_api_key': os.getenv('GOOGLE_API_KEY'),
            'news_api_key': os.getenv('NEWS_API_KEY')
        }
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            section (str): Configuration section
            key (str): Configuration key
            default (Any): Default value if not found
            
        Returns:
            Any: Configuration value
        """
        section_data = getattr(self, section, {})
        return section_data.get(key, default)
    
    def validate(self) -> Dict[str, bool]:
        """
        Validate required configuration values.
        
        Returns:
            Dict[str, bool]: Validation results
        """
        validation = {
            'email': all([
                self.email.get('email'),
                self.email.get('password'),
                self.email.get('smtp_server')
            ]),
            'database': bool(self.database.get('path')),
            'api_keys': any([
                self.api_keys.get('openweather_api_key'),
                self.api_keys.get('google_api_key'),
                self.api_keys.get('news_api_key')
            ])
        }
        
        # Log validation results
        for section, is_valid in validation.items():
            if not is_valid:
                self.logger.warning(f"Incomplete configuration for section: {section}")
        
        return validation
    
    def __str__(self) -> str:
        """String representation of configuration (with sensitive data masked)"""
        config_dict = {
            'email': {
                **self.email,
                'password': '****' if self.email.get('password') else None
            },
            'speech': self.speech,
            'database': self.database,
            'api_keys': {
                k: '****' if v else None 
                for k, v in self.api_keys.items()
            }
        }
        return str(config_dict)