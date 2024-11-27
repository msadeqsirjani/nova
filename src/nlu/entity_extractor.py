import spacy
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
import json
from datetime import datetime
import re

class EntityExtractor:
    def __init__(self, model_name: str = "en_core_web_sm", 
                 custom_entities_path: Optional[str] = None):
        """
        Initialize the entity extractor.
        
        Args:
            model_name (str): Name of the spaCy model to use
            custom_entities_path (Optional[str]): Path to custom entities JSON file
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        try:
            # Load spaCy model
            self.nlp = spacy.load(model_name)
            self.logger.info(f"Loaded spaCy model: {model_name}")
            
            # Custom entity patterns
            self.custom_patterns = self._load_custom_patterns(custom_entities_path)
            
            # Add custom pattern matcher
            self._setup_custom_patterns()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize entity extractor: {str(e)}")
            raise
    
    def _setup_logging(self):
        """Configure logging for the entity extractor"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _load_custom_patterns(self, custom_entities_path: Optional[str]) -> Dict:
        """
        Load custom entity patterns from JSON file.
        
        Args:
            custom_entities_path (Optional[str]): Path to custom entities JSON file
            
        Returns:
            Dict: Custom entity patterns
        """
        default_patterns = {
            "datetime_patterns": [
                r"(\d{1,2}:\d{2}\s*(?:am|pm)?)",
                r"(tomorrow|today|yesterday)",
                r"(next|last)\s+(week|month|year)",
                r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))",
            ],
            "email_patterns": [
                r"[\w\.-]+@[\w\.-]+\.\w+",
            ],
            "phone_patterns": [
                r"\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
            ],
            "url_patterns": [
                r"https?://(?:[\w\-])+(?:\.[\w\-]+)+[\w\-\._~:/?#[\]@!\$&'\(\)\*\+,;=.]+",
            ]
        }
        
        if custom_entities_path and Path(custom_entities_path).exists():
            try:
                with open(custom_entities_path, 'r') as f:
                    custom_patterns = json.load(f)
                default_patterns.update(custom_patterns)
                self.logger.info("Loaded custom entity patterns")
            except Exception as e:
                self.logger.error(f"Error loading custom patterns: {str(e)}")
        
        return default_patterns
    
    def _setup_custom_patterns(self):
        """Set up custom pattern matching rules"""
        self.matcher = spacy.matcher.Matcher(self.nlp.vocab)
        
        # Add patterns for custom entity types
        for entity_type, patterns in self.custom_patterns.items():
            for pattern in patterns:
                self.matcher.add(entity_type, [[{"TEXT": {"REGEX": pattern}}]])
    
    def extract_entities(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract entities from text using both spaCy and custom patterns.
        
        Args:
            text (str): Input text to extract entities from
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of extracted entities
        """
        if not text:
            return {}
        
        try:
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Initialize results dictionary
            entities = {
                "standard": self._extract_spacy_entities(doc),
                "custom": self._extract_custom_entities(doc),
                "numeric": self._extract_numeric_entities(doc)
            }
            
            self.logger.info(f"Extracted {sum(len(v) for v in entities.values())} entities from text")
            return entities
            
        except Exception as e:
            self.logger.error(f"Error extracting entities: {str(e)}")
            return {}
    
    def _extract_spacy_entities(self, doc) -> List[Dict[str, Any]]:
        """Extract standard spaCy entities"""
        return [
            {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "confidence": 1.0  # spaCy doesn't provide confidence scores
            }
            for ent in doc.ents
        ]
    
    def _extract_custom_entities(self, doc) -> List[Dict[str, Any]]:
        """Extract entities using custom patterns"""
        custom_entities = []
        matches = self.matcher(doc)
        
        for match_id, start, end in matches:
            span = doc[start:end]
            entity_type = self.nlp.vocab.strings[match_id]
            
            custom_entities.append({
                "text": span.text,
                "label": entity_type,
                "start": span.start_char,
                "end": span.end_char,
                "confidence": 0.9  # Custom confidence score for pattern matches
            })
        
        return custom_entities
    
    def _extract_numeric_entities(self, doc) -> List[Dict[str, Any]]:
        """Extract numeric values and quantities"""
        numeric_entities = []
        
        for token in doc:
            if token.like_num or token.is_currency:
                numeric_entities.append({
                    "text": token.text,
                    "label": "QUANTITY" if token.is_currency else "NUMBER",
                    "start": token.idx,
                    "end": token.idx + len(token.text),
                    "value": self._parse_numeric_value(token.text),
                    "confidence": 1.0
                })
        
        return numeric_entities
    
    def _parse_numeric_value(self, text: str) -> Optional[float]:
        """Convert numeric text to float value"""
        try:
            # Remove currency symbols and other non-numeric characters
            cleaned_text = re.sub(r'[^\d.-]', '', text)
            return float(cleaned_text)
        except:
            return None
    
    def add_custom_pattern(self, entity_type: str, pattern: str):
        """
        Add a new custom pattern for entity recognition.
        
        Args:
            entity_type (str): Type of entity to recognize
            pattern (str): Regex pattern for matching
        """
        try:
            if entity_type not in self.custom_patterns:
                self.custom_patterns[entity_type] = []
            
            self.custom_patterns[entity_type].append(pattern)
            self.matcher.add(entity_type, [[{"TEXT": {"REGEX": pattern}}]])
            
            self.logger.info(f"Added new pattern for entity type: {entity_type}")
        except Exception as e:
            self.logger.error(f"Error adding custom pattern: {str(e)}")
    
    def get_supported_entities(self) -> Dict[str, List[str]]:
        """
        Get list of supported entity types.
        
        Returns:
            Dict[str, List[str]]: Dictionary of supported entity types
        """
        return {
            "spacy": [ent for ent in self.nlp.pipe_labels['ner']],
            "custom": list(self.custom_patterns.keys())
        }