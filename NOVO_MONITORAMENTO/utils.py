from datetime import datetime
import json
import requests
from config import Settings

def now_str(settings: Settings) -> str:
    """Retorna timestamp atual formatado"""
    return datetime.now(settings.tz).strftime("%Y-%m-%d %H:%M:%S %Z")

def append_log(settings: Settings, entry: dict):
    """Adiciona entrada ao arquivo de log"""
    entry['recorded_at'] = now_str(settings)
    with open(settings.LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def send_slack(settings: Settings, text: str):
    """Envia mensagem para Slack"""
    if not settings.SLACK_WEBHOOK:
        print("[SLACK] webhook não configurado. Mensagem:", text)
        return
        
    try:
        requests.post(settings.SLACK_WEBHOOK, json={"text": text}, timeout=10)
    except Exception as e:
        print("Erro ao enviar Slack:", e)