import pyttsx3
import logging
from typing import Dict, List, Optional
from pathlib import Path

class TextToSpeech:
    def __init__(self, voice_gender: str = "female", 
                 rate: int = 175, 
                 volume: float = 1.0):
        """
        Initialize the text to speech engine.
        
        Args:
            voice_gender (str): Preferred voice gender ("male" or "female")
            rate (int): Speech rate (words per minute)
            volume (float): Volume level (0.0 to 1.0)
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        try:
            # Initialize the text-to-speech engine
            self.engine = pyttsx3.init()
            
            # Configure default settings
            self.set_rate(rate)
            self.set_volume(volume)
            
            # Set up voice
            self._setup_voice(voice_gender)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize text-to-speech engine: {str(e)}")
            raise
    
    def _setup_logging(self):
        """Configure logging for the TTS module"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _setup_voice(self, voice_gender: str):
        """
        Set up the voice based on preferred gender.
        
        Args:
            voice_gender (str): Preferred voice gender ("male" or "female")
        """
        voices = self.engine.getProperty('voices')
        
        if not voices:
            self.logger.warning("No voices found in the system")
            return
        
        # Filter voices by gender
        selected_voice = None
        for voice in voices:
            # Check if voice gender matches preference
            # Note: This is system dependent and might need adjustment
            if voice_gender.lower() in voice.name.lower():
                selected_voice = voice
                break
        
        # If no matching voice found, use the first available voice
        if not selected_voice and voices:
            selected_voice = voices[0]
            self.logger.warning(f"Preferred {voice_gender} voice not found. Using default voice.")
        
        if selected_voice:
            self.engine.setProperty('voice', selected_voice.id)
            self.logger.info(f"Using voice: {selected_voice.name}")
    
    def speak(self, text: str, save_to_file: Optional[str] = None) -> bool:
        """
        Convert text to speech and either play it or save to file.
        
        Args:
            text (str): Text to convert to speech
            save_to_file (Optional[str]): If provided, save audio to this file path
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not text:
            self.logger.warning("Empty text provided")
            return False
        
        try:
            if save_to_file:
                # Ensure the directory exists
                Path(save_to_file).parent.mkdir(parents=True, exist_ok=True)
                self.engine.save_to_file(text, save_to_file)
                self.engine.runAndWait()
                self.logger.info(f"Speech saved to file: {save_to_file}")
            else:
                self.engine.say(text)
                self.engine.runAndWait()
                self.logger.info(f"Successfully spoke: {text[:50]}...")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during speech synthesis: {str(e)}")
            return False
    
    def set_rate(self, rate: int) -> bool:
        """
        Set the speaking rate.
        
        Args:
            rate (int): Words per minute (typical range: 100-300)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.engine.setProperty('rate', rate)
            self.logger.info(f"Speech rate set to {rate}")
            return True
        except Exception as e:
            self.logger.error(f"Error setting speech rate: {str(e)}")
            return False
    
    def set_volume(self, volume: float) -> bool:
        """
        Set the speaking volume.
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            volume = max(0.0, min(1.0, volume))  # Clamp between 0.0 and 1.0
            self.engine.setProperty('volume', volume)
            self.logger.info(f"Volume set to {volume}")
            return True
        except Exception as e:
            self.logger.error(f"Error setting volume: {str(e)}")
            return False
    
    def get_available_voices(self) -> List[Dict]:
        """
        Get a list of available voices.
        
        Returns:
            List[Dict]: List of voice information dictionaries
        """
        voices = []
        for voice in self.engine.getProperty('voices'):
            voices.append({
                'id': voice.id,
                'name': voice.name,
                'languages': voice.languages,
                'gender': voice.gender if hasattr(voice, 'gender') else 'unknown'
            })
        return voices
    
    def get_current_settings(self) -> Dict:
        """
        Get current TTS settings.
        
        Returns:
            Dict: Current settings including rate, volume, and voice
        """
        return {
            'rate': self.engine.getProperty('rate'),
            'volume': self.engine.getProperty('volume'),
            'voice': self.engine.getProperty('voice')
        }
    
    def __del__(self):
        """Cleanup when the object is destroyed"""
        try:
            self.engine.stop()
        except:
            pass