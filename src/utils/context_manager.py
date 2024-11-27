from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
from collections import deque

class ContextManager:
    def __init__(self, 
                 context_ttl: int = 300,  # Time to live in seconds
                 max_history: int = 10,   # Maximum conversation history
                 db_path: Optional[str] = "conversation_history.db"):
        """
        Initialize the context manager.
        
        Args:
            context_ttl (int): Time-to-live for context items in seconds
            max_history (int): Maximum number of conversation turns to retain
            db_path (Optional[str]): Path to SQLite database for persistence
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Initialize context settings
        self.context_ttl = context_ttl
        self.max_history = max_history
        
        # Initialize context storage
        self.current_context = {}
        self.conversation_history = deque(maxlen=max_history)
        self.active_session = None
        
        # Set up persistent storage
        self.db_path = db_path
        if db_path:
            self._setup_database()
    
    def _setup_logging(self):
        """Configure logging for the context manager"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _setup_database(self):
        """Initialize SQLite database for conversation persistence"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create conversations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        session_id TEXT PRIMARY KEY,
                        start_time TIMESTAMP,
                        last_updated TIMESTAMP,
                        context TEXT
                    )
                """)
                
                # Create history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        timestamp TIMESTAMP,
                        speaker TEXT,
                        message TEXT,
                        intent TEXT,
                        FOREIGN KEY (session_id) REFERENCES conversations(session_id)
                    )
                """)
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Database initialization error: {str(e)}")
            self.db_path = None
    
    def start_session(self) -> str:
        """
        Start a new conversation session.
        
        Returns:
            str: Session ID
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.active_session = session_id
        
        if self.db_path:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO conversations (session_id, start_time, last_updated, context)
                        VALUES (?, ?, ?, ?)
                    """, (session_id, datetime.now(), datetime.now(), '{}'))
                    conn.commit()
            except Exception as e:
                self.logger.error(f"Error starting session: {str(e)}")
        
        self.logger.info(f"Started new session: {session_id}")
        return session_id
    
    def update_context(self, data: Dict[str, Any]):
        """
        Update the current context with new information.
        
        Args:
            data (Dict[str, Any]): New context information
        """
        try:
            # Update timestamp for new data
            timestamp = datetime.now()
            
            # Add timestamp to each context item
            for key, value in data.items():
                self.current_context[key] = {
                    'value': value,
                    'timestamp': timestamp
                }
            
            # Clean expired context
            self._clean_expired_context()
            
            # Update database if enabled
            if self.db_path and self.active_session:
                self._persist_context()
                
            self.logger.info("Context updated successfully")
            
        except Exception as e:
            self.logger.error(f"Error updating context: {str(e)}")
    
    def add_to_history(self, 
                      message: str, 
                      speaker: str = "user", 
                      intent: Optional[str] = None):
        """
        Add a message to conversation history.
        
        Args:
            message (str): The message content
            speaker (str): Who sent the message ("user" or "assistant")
            intent (Optional[str]): Identified intent of the message
        """
        try:
            timestamp = datetime.now()
            
            # Add to memory
            self.conversation_history.append({
                'timestamp': timestamp,
                'speaker': speaker,
                'message': message,
                'intent': intent
            })
            
            # Persist to database if enabled
            if self.db_path and self.active_session:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO conversation_history 
                        (session_id, timestamp, speaker, message, intent)
                        VALUES (?, ?, ?, ?, ?)
                    """, (self.active_session, timestamp, speaker, message, intent))
                    conn.commit()
                    
            self.logger.info(f"Added message to history: {speaker}")
            
        except Exception as e:
            self.logger.error(f"Error adding to history: {str(e)}")
    
    def get_context(self, key: Optional[str] = None) -> Any:
        """
        Get current context value(s).
        
        Args:
            key (Optional[str]): Specific context key to retrieve
            
        Returns:
            Any: Requested context value(s)
        """
        self._clean_expired_context()
        
        if key:
            return self.current_context.get(key, {}).get('value')
        return {k: v['value'] for k, v in self.current_context.items()}
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent conversation history.
        
        Args:
            limit (Optional[int]): Maximum number of history items to return
            
        Returns:
            List[Dict[str, Any]]: Recent conversation history
        """
        history = list(self.conversation_history)
        if limit:
            history = history[-limit:]
        return history
    
    def _clean_expired_context(self):
        """Remove expired context items based on TTL"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, data in self.current_context.items():
            age = current_time - data['timestamp']
            if age.total_seconds() > self.context_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.current_context[key]
    
    def _persist_context(self):
        """Persist current context to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE conversations 
                    SET context = ?, last_updated = ?
                    WHERE session_id = ?
                """, (
                    json.dumps(self.current_context),
                    datetime.now(),
                    self.active_session
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error persisting context: {str(e)}")
    
    def load_session(self, session_id: str) -> bool:
        """
        Load a previous conversation session.
        
        Args:
            session_id (str): ID of session to load
            
        Returns:
            bool: Success status
        """
        if not self.db_path:
            return False
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Load context
                cursor.execute("""
                    SELECT context FROM conversations 
                    WHERE session_id = ?
                """, (session_id,))
                result = cursor.fetchone()
                
                if result:
                    self.current_context = json.loads(result[0])
                    self.active_session = session_id
                    
                    # Load recent history
                    cursor.execute("""
                        SELECT timestamp, speaker, message, intent 
                        FROM conversation_history 
                        WHERE session_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (session_id, self.max_history))
                    
                    history = cursor.fetchall()
                    self.conversation_history.clear()
                    for item in reversed(history):
                        self.conversation_history.append({
                            'timestamp': datetime.fromisoformat(item[0]),
                            'speaker': item[1],
                            'message': item[2],
                            'intent': item[3]
                        })
                    
                    self.logger.info(f"Loaded session: {session_id}")
                    return True
                    
                return False
                
        except Exception as e:
            self.logger.error(f"Error loading session: {str(e)}")
            return False
    
    def clear_context(self):
        """Clear all current context data"""
        self.current_context.clear()
        self.conversation_history.clear()
        self.active_session = None
        self.logger.info("Context cleared")