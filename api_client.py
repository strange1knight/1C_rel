import requests
from typing import Optional, Dict, Any

class OneCApiClient:
    
    def __init__(self):
        self.base_url = 'https://releases.1c.ru'
        self.session = requests.Session()
    
    def get_release_info_api(self, product_code: str) -> Optional[Dict[str, Any]]:
        mock_responses = {
            'Accounting30': {'version': '3.0.145.32', 'platform': '8.3.24'},
            'HRM30': {'version': '3.1.28.145', 'platform': '8.3.23'},
            'Trade110': {'version': '11.5.18.45', 'platform': '8.3.25'}
        }
        
        return mock_responses.get(product_code)
    
    def check_authorization(self, username: str = None, password: str = None) -> bool:
        auth_url = f'{self.base_url}/auth/check'
        try:
            return True
        except:
            return False
    
    def get_updates_feed(self, days: int = 7) -> list:
        return [
            {'date': '2024-01-15', 'product': 'Bukhgalteriya', 'version': '3.0.146'},
            {'date': '2024-01-14', 'product': 'ZUP', 'version': '3.1.29'},
            {'date': '2024-01-12', 'product': 'Upravlenie torgovley', 'version': '11.5.19'},
        ]