import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from src.config import Config
from src.speech.speech_to_text import SpeechToText
from src.speech.text_to_speech import TextToSpeech
from src.nlu.intent_classifier import IntentClassifier
from src.nlu.entity_extractor import EntityExtractor
from src.tasks.reminder import ReminderService
from src.tasks.weather import WeatherService
from src.tasks.email_sender import EmailSender

class Assistant:
    def __init__(self, config: Config):
        """
        Initialize the virtual assistant.
        
        Args:
            config (Config): Application configuration object
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        try:
            # Initialize configuration
            self.config = config
            
            # Initialize core services
            self.speech_to_text = SpeechToText()
            self.text_to_speech = TextToSpeech()
            self.intent_classifier = IntentClassifier()
            self.entity_extractor = EntityExtractor()
            
            # Initialize task services
            self.reminder_service = ReminderService(config)
            self.weather_service = WeatherService(config)
            self.email_service = EmailSender(config)
            
            # State management
            self.conversation_context = {}
            self.is_listening = False
            
            self.logger.info("Assistant initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing assistant: {str(e)}")
            raise
    
    def _setup_logging(self):
        """Configure logging for the assistant"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def start(self):
        """Start the assistant"""
        try:
            self.is_listening = True
            self.text_to_speech.speak("Hello! How can I help you today?")
            
            while self.is_listening:
                # Listen for user input
                speech_result = self.speech_to_text.listen()
                
                if speech_result["success"]:
                    user_input = speech_result["text"]
                    self.logger.info(f"User said: {user_input}")
                    
                    # Process the input
                    self.process_input(user_input)
                else:
                    self.logger.error(f"Speech recognition error: {speech_result['error']}")
                    self.text_to_speech.speak("I'm sorry, I didn't catch that. Could you please repeat?")
        
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            self.logger.error(f"Error in assistant main loop: {str(e)}")
            self.stop()
    
    def process_input(self, user_input: str):
        """
        Process user input and generate appropriate response.
        
        Args:
            user_input (str): User's speech input
        """
        try:
            # Classify intent
            intent_result = self.intent_classifier.classify(user_input)
            intent = intent_result["intent"]
            confidence = intent_result["confidence"]
            
            self.logger.info(f"Detected intent: {intent} (confidence: {confidence:.2f})")
            
            # Extract entities
            entities = self.entity_extractor.extract_entities(user_input)
            
            # Update conversation context
            self.conversation_context.update({
                "last_intent": intent,
                "last_entities": entities,
                "timestamp": datetime.now().isoformat()
            })
            
            # Handle intent
            response = self._handle_intent(intent, entities)
            
            # Speak response
            if response:
                self.text_to_speech.speak(response)
            
        except Exception as e:
            self.logger.error(f"Error processing input: {str(e)}")
            self.text_to_speech.speak("I'm sorry, I encountered an error processing your request.")
    
    def _handle_intent(self, intent: str, entities: Dict[str, Any]) -> str:
        """
        Handle different intents and generate appropriate responses.
        
        Args:
            intent (str): Classified intent
            entities (Dict[str, Any]): Extracted entities
            
        Returns:
            str: Response to be spoken
        """
        try:
            if intent == "greeting":
                return "Hello! How can I help you today?"
            
            elif intent == "farewell":
                self.stop()
                return "Goodbye! Have a great day!"
            
            elif intent == "weather":
                return self._handle_weather_intent(entities)
            
            elif intent == "reminder":
                return self._handle_reminder_intent(entities)
            
            elif intent == "email":
                return self._handle_email_intent(entities)
            
            else:
                return "I'm not sure how to help with that yet."
            
        except Exception as e:
            self.logger.error(f"Error handling intent {intent}: {str(e)}")
            return "I'm sorry, I encountered an error handling your request."
    
    def _handle_weather_intent(self, entities: Dict[str, Any]) -> str:
        """Handle weather-related intents"""
        try:
            location = None
            for entity in entities.get("GPE", []):  # Location entities
                location = entity["text"]
                break
            
            if not location:
                return "Which city would you like to know the weather for?"
            
            weather = self.weather_service.get_current_weather(location)
            if weather:
                return (f"The current weather in {weather.location} is "
                       f"{weather.temperature:.1f}°C with {weather.description}. "
                       f"The humidity is {weather.humidity}%.")
            else:
                return f"I'm sorry, I couldn't get the weather information for {location}."
            
        except Exception as e:
            self.logger.error(f"Error handling weather intent: {str(e)}")
            return "I'm sorry, I encountered an error getting the weather information."
    
    def _handle_reminder_intent(self, entities: Dict[str, Any]) -> str:
        """Handle reminder-related intents"""
        try:
            # Extract time and description
            time_entity = next((e for e in entities.get("TIME", [])), None)
            description = " ".join(e["text"] for e in entities.get("TASK", []))
            
            if not time_entity or not description:
                return "Please specify both the time and what you'd like to be reminded about."
            
            reminder = self.reminder_service.create_reminder(
                title="Reminder",
                description=description,
                due_time=time_entity["text"]
            )
            
            if reminder:
                return f"I'll remind you about {description} at {time_entity['text']}."
            else:
                return "I'm sorry, I couldn't set the reminder."
            
        except Exception as e:
            self.logger.error(f"Error handling reminder intent: {str(e)}")
            return "I'm sorry, I encountered an error setting the reminder."
    
    def _handle_email_intent(self, entities: Dict[str, Any]) -> str:
        """Handle email-related intents"""
        try:
            # Extract email address and message
            recipient = next((e["text"] for e in entities.get("EMAIL", [])), None)
            message = " ".join(e["text"] for e in entities.get("MESSAGE", []))
            
            if not recipient or not message:
                return "Please specify both the recipient and the message for the email."
            
            result = self.email_service.send_email(
                to_email=recipient,
                subject="Message from Virtual Assistant",
                body=message
            )
            
            if result["success"]:
                return f"I've sent your email to {recipient}."
            else:
                return "I'm sorry, I couldn't send the email."
            
        except Exception as e:
            self.logger.error(f"Error handling email intent: {str(e)}")
            return "I'm sorry, I encountered an error sending the email."
    
    def stop(self):
        """Stop the assistant"""
        self.is_listening = False
        self.logger.info("Assistant stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the assistant.
        
        Returns:
            Dict[str, Any]: Current status information
        """
        return {
            "is_listening": self.is_listening,
            "conversation_context": self.conversation_context,
            "last_update": datetime.now().isoformat()
        }
