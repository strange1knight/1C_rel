import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

CONFIGURATIONS = {
    'bp_prof': {
        'name': 'Bukhgalteriya predpriyatiya PROF',
        'project_id': 'Accounting30',
        'nick': 'Accounting30'
    },
    'bp_corp': {
        'name': 'Bukhgalteriya predpriyatiya KORP',
        'project_id': 'AccountingCorp30',
        'nick': 'AccountingCorp30'
    },
    'zup_prof': {
        'name': 'Zarplata i Upravlenie Personalom PROF',
        'project_id': 'HRM30',
        'nick': 'HRM30'
    },
    'zup_corp': {
        'name': 'Zarplata i Upravlenie Personalom KORP',
        'project_id': 'HRMCorp30',
        'nick': 'HRMCorp30'
    },
    'ut11': {
        'name': 'Upravlenie torgovley, redaktsiya 11',
        'project_id': 'Trade110',
        'nick': 'Trade110'
    }
}

API_BASE_URL = 'https://releases.1c.ru'