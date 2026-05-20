import re
from datetime import datetime
from bs4 import BeautifulSoup
import requests

class ReleaseScraper:
    
    def __init__(self, session=None):
        self.session = session or requests.Session()
    
    def parse_releases_page(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        
        table = soup.find('table', {'id': 'versionsTable'})
        if not table:
            table = soup.find('table', class_=re.compile(r'.*table.*'))
        
        if not table:
            return None
        
        releases = []
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')
        
        for row in rows[:5]:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
            
            version_link = row.find('a')
            if not version_link:
                continue
            
            version = version_link.get_text(strip=True)
            
            date_text = None
            for cell in cells:
                if re.search(r'\d{2}\.\d{2}\.\d{2}', cell.get_text()):
                    date_text = cell.get_text(strip=True)
                    break
            
            release_date = None
            if date_text:
                try:
                    day, month, year = date_text.split('.')
                    full_year = 2000 + int(year)
                    release_date = datetime(full_year, int(month), int(day))
                except:
                    release_date = None
            
            min_versions = ''
            for cell in cells:
                if 'platform' in cell.get_text().lower() or 'platformy' in cell.get_text().lower():
                    min_versions = cell.get_text(strip=True)
                    break
            
            releases.append({
                'version': version,
                'date': release_date,
                'date_str': date_text,
                'min_platform_versions': min_versions,
                'url': version_link.get('href', '')
            })
        
        return releases
    
    def get_latest_release(self, project_id):
        url = f'https://releases.1c.ru/project/{project_id}'
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            releases = self.parse_releases_page(response.text)
            
            if releases and len(releases) > 0:
                releases.sort(key=lambda x: self._version_to_tuple(x['version']), reverse=True)
                return releases[0]
            
            return None
        except Exception as e:
            print(f"Scraping error: {e}")
            return None
    
    def _version_to_tuple(self, version_str):
        parts = re.findall(r'\d+', version_str)
        return tuple(int(p) for p in parts)