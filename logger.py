import os
from datetime import datetime
from pathlib import Path

class DialogLogger:
    def __init__(self, log_dir='logs'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
    
    def _get_log_file(self, user_id):
        return self.log_dir / f"{user_id}.log"
    
    def log_message(self, user_id, username, message, is_bot=False):
        log_file = self._get_log_file(user_id)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sender = 'BOT' if is_bot else f'USER ({username})'
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {sender}: {message}\n")
    
    def get_dialog_history(self, user_id):
        log_file = self._get_log_file(user_id)
        if not log_file.exists():
            return None
        
        with open(log_file, 'r', encoding='utf-8') as f:
            return f.read()