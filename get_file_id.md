run this command

~~~

python -c "import json,urllib.request; from backend.core.config import get_settings; t=get_settings().bot_token; d=json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{t}/getUpdates')); [(print('\nFILE:',m['document'].get('file_name'),'\nFILE_ID:',m['document']['file_id'],'\n')) for u in d.get('result',[]) for m in [u.get('message') or u.get('channel_post') or {}] if m.get('document')]"

~~~