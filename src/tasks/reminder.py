from datetime import datetime, timedelta
import sqlite3
import logging
from typing import Dict, List, Optional, Union
import threading
import time
from pathlib import Path
from dateutil import parser
from plyer import notification
from plyer import notification

class ReminderService:
    def __init__(self, config, db_path: str = "reminders.db"):
        """
        Initialize the reminder service.
        
        Args:
            config: Application configuration object
            db_path (str): Path to SQLite database
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        self.db_path = db_path
        self.config = config
        
        # Initialize database
        self._setup_database()
        
        # Start reminder checker thread
        self.active = True
        self.checker_thread = threading.Thread(target=self._check_reminders)
        self.checker_thread.daemon = True
        self.checker_thread.start()
    
    def _setup_logging(self):
        """Configure logging for the reminder service"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _setup_database(self):
        """Initialize SQLite database for reminders"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create reminders table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        due_time TIMESTAMP NOT NULL,
                        created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        priority INTEGER DEFAULT 1,
                        repeat_interval TEXT,
                        last_notification TIMESTAMP
                    )
                """)
                
                conn.commit()
                self.logger.info("Reminder database initialized")
                
        except Exception as e:
            self.logger.error(f"Database initialization error: {str(e)}")
            raise
    
    def create_reminder(self,
                       title: str,
                       due_time: Union[str, datetime],
                       description: Optional[str] = None,
                       priority: int = 1,
                       repeat_interval: Optional[str] = None) -> Dict:
        """
        Create a new reminder.
        
        Args:
            title (str): Reminder title
            due_time (Union[str, datetime]): When the reminder is due
            description (Optional[str]): Detailed description
            priority (int): Priority level (1-5)
            repeat_interval (Optional[str]): Repeat interval (daily, weekly, monthly)
            
        Returns:
            Dict: Created reminder information
        """
        try:
            # Parse due time if string
            if isinstance(due_time, str):
                due_time = parser.parse(due_time)
            
            # Validate priority
            priority = max(1, min(5, priority))
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO reminders 
                    (title, description, due_time, priority, repeat_interval)
                    VALUES (?, ?, ?, ?, ?)
                """, (title, description, due_time, priority, repeat_interval))
                
                reminder_id = cursor.lastrowid
                
                self.logger.info(f"Created reminder: {title} (ID: {reminder_id})")
                
                return {
                    'id': reminder_id,
                    'title': title,
                    'description': description,
                    'due_time': due_time.isoformat(),
                    'priority': priority,
                    'repeat_interval': repeat_interval,
                    'status': 'pending'
                }
                
        except Exception as e:
            self.logger.error(f"Error creating reminder: {str(e)}")
            raise
    
    def get_reminders(self, 
                     status: Optional[str] = None, 
                     priority: Optional[int] = None) -> List[Dict]:
        """
        Get reminders with optional filters.
        
        Args:
            status (Optional[str]): Filter by status (pending, completed, expired)
            priority (Optional[int]): Filter by priority level
            
        Returns:
            List[Dict]: List of reminders
        """
        try:
            query = "SELECT * FROM reminders"
            params = []
            
            # Add filters
            filters = []
            if status:
                filters.append("status = ?")
                params.append(status)
            if priority:
                filters.append("priority = ?")
                params.append(priority)
            
            if filters:
                query += " WHERE " + " AND ".join(filters)
            
            query += " ORDER BY due_time ASC"
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(query, params)
                reminders = cursor.fetchall()
                
                return [{
                    'id': row['id'],
                    'title': row['title'],
                    'description': row['description'],
                    'due_time': row['due_time'],
                    'status': row['status'],
                    'priority': row['priority'],
                    'repeat_interval': row['repeat_interval']
                } for row in reminders]
                
        except Exception as e:
            self.logger.error(f"Error getting reminders: {str(e)}")
            return []
    
    def update_reminder(self, 
                       reminder_id: int, 
                       updates: Dict) -> Dict:
        """
        Update an existing reminder.
        
        Args:
            reminder_id (int): ID of reminder to update
            updates (Dict): Dictionary of fields to update
            
        Returns:
            Dict: Updated reminder information
        """
        try:
            allowed_fields = {
                'title', 'description', 'due_time', 
                'status', 'priority', 'repeat_interval'
            }
            
            # Filter out invalid fields
            valid_updates = {
                k: v for k, v in updates.items() 
                if k in allowed_fields
            }
            
            if not valid_updates:
                raise ValueError("No valid fields to update")
            
            # Build update query
            query = "UPDATE reminders SET "
            query += ", ".join(f"{k} = ?" for k in valid_updates.keys())
            query += " WHERE id = ?"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Execute update
                cursor.execute(
                    query, 
                    [*valid_updates.values(), reminder_id]
                )
                
                if cursor.rowcount == 0:
                    raise ValueError(f"Reminder {reminder_id} not found")
                
                # Get updated reminder
                cursor.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
                row = cursor.fetchone()
                
                self.logger.info(f"Updated reminder {reminder_id}")
                
                return {
                    'id': row[0],
                    'title': row[1],
                    'description': row[2],
                    'due_time': row[3],
                    'status': row[5],
                    'priority': row[6],
                    'repeat_interval': row[7]
                }
                
        except Exception as e:
            self.logger.error(f"Error updating reminder: {str(e)}")
            raise
    
    def delete_reminder(self, reminder_id: int) -> bool:
        """
        Delete a reminder.
        
        Args:
            reminder_id (int): ID of reminder to delete
            
        Returns:
            bool: Success status
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "DELETE FROM reminders WHERE id = ?",
                    (reminder_id,)
                )
                
                success = cursor.rowcount > 0
                if success:
                    self.logger.info(f"Deleted reminder {reminder_id}")
                else:
                    self.logger.warning(f"Reminder {reminder_id} not found")
                
                return success
                
        except Exception as e:
            self.logger.error(f"Error deleting reminder: {str(e)}")
            return False
    
    def _check_reminders(self):
        """Background thread to check for due reminders"""
        while self.active:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Get pending reminders that are due
                    cursor.execute("""
                        SELECT id, title, description, due_time, repeat_interval 
                        FROM reminders 
                        WHERE status = 'pending' 
                        AND due_time <= datetime('now', 'localtime')
                        AND (last_notification IS NULL 
                             OR datetime('now', 'localtime') > 
                                datetime(last_notification, '+1 minute'))
                    """)
                    
                    due_reminders = cursor.fetchall()
                    
                    for reminder in due_reminders:
                        # Send notification
                        self._send_notification(
                            title=reminder[1],
                            message=reminder[2] or reminder[1]
                        )
                        
                        # Update last notification time
                        cursor.execute("""
                            UPDATE reminders 
                            SET last_notification = datetime('now', 'localtime')
                            WHERE id = ?
                        """, (reminder[0],))
                        
                        # Handle repeating reminders
                        if reminder[4]:  # repeat_interval
                            self._handle_repeat(cursor, reminder)
                        else:
                            # Mark one-time reminder as completed
                            cursor.execute("""
                                UPDATE reminders 
                                SET status = 'completed' 
                                WHERE id = ?
                            """, (reminder[0],))
                    
                    conn.commit()
                    
            except Exception as e:
                self.logger.error(f"Error checking reminders: {str(e)}")
            
            # Wait before next check
            time.sleep(60)
    
    def _handle_repeat(self, cursor, reminder):
        """Handle repeating reminders"""
        interval = reminder[4].lower()
        due_time = parser.parse(reminder[3])
        
        if interval == 'daily':
            next_due = due_time + timedelta(days=1)
        elif interval == 'weekly':
            next_due = due_time + timedelta(weeks=1)
        elif interval == 'monthly':
            # Add one month (approximately)
            next_due = due_time + timedelta(days=30)
        else:
            return
        
        cursor.execute("""
            UPDATE reminders 
            SET due_time = ?, status = 'pending', last_notification = NULL
            WHERE id = ?
        """, (next_due, reminder[0]))
    
    def _send_notification(self, title: str, message: str):
        """Send system notification"""
        try:
            notification.notify(
                title=title,
                message=message,
                app_icon=None,  # e.g. 'C:\\icon_32x32.ico'
                timeout=10,  # seconds
            )
        except Exception as e:
            self.logger.error(f"Error sending notification: {str(e)}")
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.active = False
        if hasattr(self, 'checker_thread'):
            self.checker_thread.join(timeout=1)