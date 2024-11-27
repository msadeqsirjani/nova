import speech_recognition as sr
from typing import Optional, Dict
import json
import logging
from pathlib import Path

class SpeechToText:
    def __init__(self, language: str = "en-US", timeout: int = 5, 
                 phrase_threshold: float = 0.3, noise_duration: float = 1):
        """
        Initialize the speech to text converter.
        
        Args:
            language (str): Language code for speech recognition
            timeout (int): Maximum time to wait for phrase completion in seconds
            phrase_threshold (float): Minimum seconds of speaking audio before we consider the speaking complete
            noise_duration (float): Duration in seconds to calibrate noise levels
        """
        # Initialize recognizer and microphone
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Configuration
        self.language = language
        self.timeout = timeout
        
        # Set up recognition parameters
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 4000
        self.recognizer.pause_threshold = 1.0  # Changed from phrase_threshold
        self.recognizer.phrase_threshold = phrase_threshold
        self.recognizer.non_speaking_duration = 0.5  # Added explicit non_speaking_duration
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Perform initial noise calibration
        self._calibrate_noise(duration=noise_duration)
    
    def _setup_logging(self):
        """Configure logging for the speech recognition module"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _calibrate_noise(self, duration: float = 1):
        """
        Calibrate the recognizer for ambient noise levels.
        
        Args:
            duration (float): Duration in seconds to sample ambient noise
        """
        try:
            self.logger.info("Calibrating for ambient noise... Please remain quiet.")
            with self.microphone as source:
                # Ensure proper relationship between thresholds
                self.recognizer.pause_threshold = 1.0
                self.recognizer.non_speaking_duration = 0.5
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
            self.logger.info("Calibration complete!")
        except Exception as e:
            self.logger.error(f"Error during noise calibration: {str(e)}")
            raise

    def listen(self, timeout: Optional[int] = None) -> Dict[str, str]:
        """
        Listen for voice input and convert to text.
        
        Args:
            timeout (Optional[int]): Override default timeout value
            
        Returns:
            Dict containing recognition results and status
        """
        timeout = timeout or self.timeout
        result = {
            "success": False,
            "error": None,
            "text": None,
            "confidence": None
        }
        
        try:
            with self.microphone as source:
                self.logger.info("Listening for speech...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=10  # Maximum phrase duration
                )
            
            # Try multiple recognition services in order of preference
            text = self._recognize_with_fallback(audio)
            
            if text:
                result["success"] = True
                result["text"] = text
                self.logger.info(f"Successfully recognized: {text}")
            
        except sr.WaitTimeoutError:
            result["error"] = "Listening timed out. Please try again."
            self.logger.warning("Listening timed out")
            
        except sr.UnknownValueError:
            result["error"] = "Could not understand audio"
            self.logger.warning("Speech was not understood")
            
        except sr.RequestError as e:
            result["error"] = f"Recognition service error: {str(e)}"
            self.logger.error(f"Service error: {str(e)}")
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            self.logger.error(f"Unexpected error during recognition: {str(e)}")
        
        return result
    
    def _recognize_with_fallback(self, audio) -> Optional[str]:
        """
        Try multiple speech recognition services with fallback options.
        
        Args:
            audio: Audio data to recognize
            
        Returns:
            Recognized text or None if all services fail
        """
        # Try Google Speech Recognition first
        try:
            text = self.recognizer.recognize_google(
                audio,
                language=self.language,
                show_all=True
            )
            if text and isinstance(text, dict) and 'alternative' in text:
                return text['alternative'][0]['transcript']
            return text
        except:
            self.logger.warning("Google Speech Recognition failed, trying Sphinx")
        
        # Fall back to Sphinx (offline recognition)
        try:
            return self.recognizer.recognize_sphinx(audio, language=self.language)
        except:
            self.logger.warning("Sphinx recognition failed")
        
        return None
    
    def save_audio(self, audio_data, filename: str = "recorded_audio.wav"):
        """
        Save recorded audio to a file.
        
        Args:
            audio_data: Audio data to save
            filename (str): Output filename
        """
        try:
            path = Path("recorded_audio") / filename
            path.parent.mkdir(exist_ok=True)
            
            with open(path, "wb") as f:
                f.write(audio_data.get_wav_data())
            self.logger.info(f"Audio saved to {path}")
        except Exception as e:
            self.logger.error(f"Error saving audio: {str(e)}")
    
    def get_microphone_list(self) -> list:
        """Return a list of available microphone devices"""
        return [mic.name for mic in sr.Microphone.list_microphone_names()]
    
    def update_settings(self, settings: Dict):
        """
        Update recognition settings.
        
        Args:
            settings (Dict): Dictionary of settings to update
        """
        if 'energy_threshold' in settings:
            self.recognizer.energy_threshold = settings['energy_threshold']
        if 'pause_threshold' in settings:
            self.recognizer.pause_threshold = settings['pause_threshold']
        if 'language' in settings:
            self.language = settings['language']
        if 'timeout' in settings:
            self.timeout = settings['timeout']