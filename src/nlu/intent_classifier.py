from typing import Dict, List, Tuple, Optional, Any
import logging
import json
from pathlib import Path
import numpy as np
from sklearn.preprocessing import LabelEncoder
import torch
from transformers import AutoTokenizer, AutoModel
import re
from collections import defaultdict

class IntentClassifier:
    def __init__(self, 
                 model_name: str = "distilbert-base-uncased",
                 threshold: float = 0.5,
                 intents_file: Optional[str] = None):
        """
        Initialize the intent classifier.
        
        Args:
            model_name (str): Name of the transformer model to use
            threshold (float): Confidence threshold for intent classification
            intents_file (Optional[str]): Path to custom intents JSON file
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        try:
            # Load transformer model and tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.threshold = threshold
            
            # Load intent patterns
            self.intents = self._load_intents(intents_file)
            
            # Initialize label encoder
            self.label_encoder = LabelEncoder()
            self.label_encoder.fit(list(self.intents.keys()))
            
            self.logger.info(f"Initialized intent classifier with model: {model_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize intent classifier: {str(e)}")
            raise
    
    def _setup_logging(self):
        """Configure logging for the intent classifier"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _load_intents(self, intents_file: Optional[str]) -> Dict[str, Dict]:
        """
        Load intent patterns from file or use defaults.
        
        Args:
            intents_file (Optional[str]): Path to intents JSON file
            
        Returns:
            Dict[str, Dict]: Dictionary of intent patterns and examples
        """
        default_intents = {
            "greeting": {
                "patterns": [
                    "hello", "hi", "hey", "good morning", "good evening",
                    "what's up", "how are you"
                ],
                "responses": ["Hello! How can I help you today?"]
            },
            "farewell": {
                "patterns": [
                    "goodbye", "bye", "see you", "see you later", "good night"
                ],
                "responses": ["Goodbye! Have a great day!"]
            },
            "weather": {
                "patterns": [
                    "what's the weather", "weather forecast", "is it going to rain",
                    "temperature today", "weather report"
                ],
                "responses": ["Let me check the weather for you."]
            },
            "reminder": {
                "patterns": [
                    "set a reminder", "remind me", "set alarm", "create reminder",
                    "schedule task"
                ],
                "responses": ["I'll help you set a reminder."]
            },
            "email": {
                "patterns": [
                    "send email", "compose email", "write email", "new mail",
                    "send message"
                ],
                "responses": ["I'll help you compose an email."]
            }
        }
        
        if intents_file and Path(intents_file).exists():
            try:
                with open(intents_file, 'r') as f:
                    custom_intents = json.load(f)
                default_intents.update(custom_intents)
                self.logger.info("Loaded custom intents")
            except Exception as e:
                self.logger.error(f"Error loading custom intents: {str(e)}")
        
        return default_intents
    
    def classify(self, text: str) -> Dict[str, Any]:
        """
        Classify the intent of the input text.
        
        Args:
            text (str): Input text to classify
            
        Returns:
            Dict[str, Any]: Classification results including intent and confidence
        """
        if not text:
            return {"intent": None, "confidence": 0.0, "response": None}
        
        try:
            # First try rule-based matching
            rule_based_result = self._rule_based_classification(text.lower())
            if rule_based_result["confidence"] > self.threshold:
                return rule_based_result
            
            # Fall back to transformer-based classification
            return self._transformer_classification(text)
            
        except Exception as e:
            self.logger.error(f"Error classifying intent: {str(e)}")
            return {"intent": None, "confidence": 0.0, "response": None}
    
    def _rule_based_classification(self, text: str) -> Dict[str, Any]:
        """
        Perform rule-based intent classification using pattern matching.
        
        Args:
            text (str): Input text to classify
            
        Returns:
            Dict[str, Any]: Classification results
        """
        best_match = {"intent": None, "confidence": 0.0, "response": None}
        
        for intent, data in self.intents.items():
            for pattern in data["patterns"]:
                # Calculate similarity score
                similarity = self._calculate_similarity(text, pattern.lower())
                
                if similarity > best_match["confidence"]:
                    best_match = {
                        "intent": intent,
                        "confidence": similarity,
                        "response": np.random.choice(data["responses"])
                    }
        
        return best_match
    
    def _transformer_classification(self, text: str) -> Dict[str, Any]:
        """
        Perform transformer-based intent classification.
        
        Args:
            text (str): Input text to classify
            
        Returns:
            Dict[str, Any]: Classification results
        """
        # Tokenize and encode text
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True)
        
        # Get model outputs
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Get sentence embedding (mean pooling)
        embeddings = outputs.last_hidden_state.mean(dim=1)
        
        # Calculate similarity with each intent
        best_match = {"intent": None, "confidence": 0.0, "response": None}
        
        for intent, data in self.intents.items():
            # Get embeddings for intent patterns
            pattern_embeddings = []
            for pattern in data["patterns"]:
                pattern_inputs = self.tokenizer(pattern, return_tensors="pt", padding=True, truncation=True)
                with torch.no_grad():
                    pattern_outputs = self.model(**pattern_inputs)
                pattern_embeddings.append(pattern_outputs.last_hidden_state.mean(dim=1))
            
            # Calculate cosine similarity
            pattern_embeddings = torch.cat(pattern_embeddings)
            similarity = torch.nn.functional.cosine_similarity(embeddings, pattern_embeddings).mean().item()
            
            if similarity > best_match["confidence"]:
                best_match = {
                    "intent": intent,
                    "confidence": similarity,
                    "response": np.random.choice(data["responses"])
                }
        
        return best_match
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using simple metrics.
        
        Args:
            text1 (str): First text
            text2 (str): Second text
            
        Returns:
            float: Similarity score between 0 and 1
        """
        # Convert to sets of words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def add_intent(self, intent: str, patterns: List[str], responses: List[str]):
        """
        Add a new intent with patterns and responses.
        
        Args:
            intent (str): Name of the intent
            patterns (List[str]): List of pattern examples
            responses (List[str]): List of possible responses
        """
        try:
            self.intents[intent] = {
                "patterns": patterns,
                "responses": responses
            }
            
            # Update label encoder
            self.label_encoder.fit(list(self.intents.keys()))
            
            self.logger.info(f"Added new intent: {intent}")
        except Exception as e:
            self.logger.error(f"Error adding intent: {str(e)}")
    
    def get_intents(self) -> Dict[str, List[str]]:
        """
        Get all supported intents and their patterns.
        
        Returns:
            Dict[str, List[str]]: Dictionary of intents and their patterns
        """
        return {intent: data["patterns"] for intent, data in self.intents.items()}
    
    def save_intents(self, file_path: str):
        """
        Save current intents to a JSON file.
        
        Args:
            file_path (str): Path to save the intents file
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self.intents, f, indent=4)
            self.logger.info(f"Saved intents to {file_path}")
        except Exception as e:
            self.logger.error(f"Error saving intents: {str(e)}")