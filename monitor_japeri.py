#!/usr/bin/env python3
"""
monitor_japeri.py
Monitora o Diário Oficial de Japeri / portal de transparência:
- checagens a cada X horas (padrão 3h)
- tenta selecionar "PREFEITURA MUNICIPAL DE JAPERI" e abrir o primeiro documento
- logs em relatorio/logs.jsonl
- screenshots em relatorio/failures/
- gera relatorio diário em PDF em relatorio/daily/
- gera relatorio mensal em relatorio/monthly/ (a cada 30 dias)
- envia alertas ao Slack via webhook se configurado
"""

import os, sys, time, json, traceback
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import load_dotenv
import requests

from fpdf import FPDF
from apscheduler.schedulers.background import BackgroundScheduler
from playwright.sync_api import sync_playwright

# --- Carrega config ---
load_dotenv()
SITE_URL = os.getenv("SITE_URL").strip()
PORTAL_URL = os.getenv("PORTAL_URL").strip()
SUCCESS_ORG_LABEL = os.getenv("SUCCESS_ORG_LABEL", "PREFEITURA MUNICIPAL DE JAPERI")
CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "3"))
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK", "").strip()
TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "23"))

# --- Pastas ---
BASE = Path.cwd() / "relatorio"
FAIL_DIR = BASE / "failures"
DAILY_DIR = BASE / "daily"
MONTHLY_DIR = BASE / "monthly"
LOG_FILE = BASE / "logs.jsonl"

for d in (BASE, FAIL_DIR, DAILY_DIR, MONTHLY_DIR):
    d.mkdir(parents=True, exist_ok=True)

TZ = ZoneInfo(TIMEZONE)

def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

def append_log(entry: dict):
    entry['recorded_at'] = now_str()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def send_slack(text):
    if not SLACK_WEBHOOK:
        print("[SLACK] webhook não configurado. Mensagem:", text)
        return
    try:
        requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    except Exception as e:
        print("Erro ao enviar Slack:", e)

# --- Função de verificação principal ---
def perform_check():
    """
    Realiza a checagem:
    1) HTTP simples ao SITE_URL
    2) Navegação Playwright ao PORTAL_URL, selecionar organização, abrir primeiro documento
    Salva screenshot em caso de falha. Retorna dicionário de resultado.
    """
    timestamp = now_str()
    result = {
        "timestamp": timestamp,
        "site_url": SITE_URL,
        "portal_url": PORTAL_URL,
        "ok_http": False,
        "http_detail": None,
        "ok_playwright": False,
        "playwright_detail": None,
        "screenshot": None,
    }

    # 1) HTTP simple
    try:
        r = requests.get(SITE_URL, timeout=15)
        result["http_detail"] = {"status_code": r.status_code, "elapsed": r.elapsed.total_seconds()}
        result["ok_http"] = (r.status_code == 200)
    except Exception as e:
        result["http_detail"] = {"error": str(e)}
        result["ok_http"] = False

    # 2) Playwright flow
    screenshot_path = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            # 2a: abrir a página portal (direto)
            page.goto(PORTAL_URL, timeout=20000)
            time.sleep(1)  # deixa carregar
            # Tenta selecionar a organização pelo select (label) primeiro
            playwright_ok = False
            detail_msgs = []
            try:
                # tentativa 1: procurar <select> e selecionar por label (alguns portais usam <select>)
                selects = page.query_selector_all("select")
                if selects:
                    selected = False
                    for s in selects:
                        try:
                            # tenta selecionar por label/valor (pode falhar sem o valor)
                            s.select_option(label=SUCCESS_ORG_LABEL)
                            selected = True
                            detail_msgs.append("select: selecionado por label")
                            break
                        except Exception:
                            continue
                    if not selected:
                        detail_msgs.append("select: não encontrou opção por label")
                else:
                    detail_msgs.append("select: nenhum <select> encontrado")
            except Exception as e:
                detail_msgs.append("select exception: " + str(e))

            # tentativa 2: clicar no texto "PREFEITURA MUNICIPAL DE JAPERI"
            if not any("selecionado" in m for m in detail_msgs):
                try:
                    # localiza por texto e clica (se existir)
                    org_loc = page.locator(f"text=\"{SUCCESS_ORG_LABEL}\"")
                    if org_loc.count() > 0:
                        org_loc.first.click()
                        detail_msgs.append("click: clicou no texto da organização")
                    else:
                        detail_msgs.append("click: não encontrou texto exato da organização")
                except Exception as e:
                    detail_msgs.append("click error: " + str(e))

            # espera carregar lista de publicações
            time.sleep(2)
            # tenta abrir o primeiro documento listado
            first_doc_opened = False
            try:
                # opção 1: link direto para publicacao (href com 'publicacao' / 'download')
                anchors = page.query_selector_all("a")
                if anchors:
                    # procura por anchors que pareçam publicações (heurística)
                    for a in anchors:
                        href = a.get_attribute("href") or ""
                        text = (a.inner_text() or "").strip()
                        if "publicacao" in href.lower() or "download" in href.lower() or "visualizar" in text.lower() or "baixar" in text.lower():
                            a.click()
                            first_doc_opened = True
                            detail_msgs.append(f"clicou em link heurístico: {href[:80]}")
                            break
                    # fallback: clicar no primeiro anchor se nada foi detectado
                    if not first_doc_opened and anchors:
                        anchors[0].click()
                        first_doc_opened = True
                        detail_msgs.append("clicou no primeiro <a> como fallback")
                else:
                    detail_msgs.append("nenhum <a> encontrado")
            except Exception as e:
                detail_msgs.append("erro ao abrir documento: " + str(e))

            # espera e verifica se abriu documento (procura por PDF embed ou elemento que indique)
            time.sleep(3)
            # heurística para determinar sucesso: verificar se há iframe, embed ou link ativo para PDF
            try:
                iframe = page.query_selector("iframe")
                embed = page.query_selector("embed")
                pdf_found = bool(iframe or embed)
                if pdf_found or first_doc_opened:
                    playwright_ok = True
                    detail_msgs.append("documento aberto (iframe/embed ou link aberto)")
                else:
                    detail_msgs.append("não detectado iframe/embed e o clique não provou abertura")
                    playwright_ok = False
            except Exception as e:
                detail_msgs.append("verificação pdf erro: " + str(e))
                playwright_ok = False

            if not playwright_ok:
                # salva screenshot para diagnóstico
                screenshot_name = f"failure_{int(time.time())}.png"
                screenshot_path = str(FAIL_DIR / screenshot_name)
                try:
                    page.screenshot(path=screenshot_path, full_page=True)
                except Exception as e:
                    detail_msgs.append("erro ao tirar screenshot: " + str(e))
            browser.close()

            result["ok_playwright"] = bool(playwright_ok)
            result["playwright_detail"] = {"messages": detail_msgs}
            if screenshot_path:
                result["screenshot"] = screenshot_path

    except Exception as e:
        # erro grave com Playwright
        tb = traceback.format_exc()
        result["ok_playwright"] = False
        result["playwright_detail"] = {"error": str(e), "traceback": tb}
        # tente salvar screenshot externo (não garantido)
        # (não podemos usar page aqui pois contexto pode ter sido perdido)

    # grava e reage
    append_log(result)

    # se houve falha em qualquer parte, notifica e garante screenshot se houver
    if not result["ok_http"] or not result["ok_playwright"]:
        msg = f"🚨 Problema detectado em {SITE_URL} em {result['timestamp']}.\nHTTP OK: {result['ok_http']}\nPlaywright OK: {result['ok_playwright']}\nDetalhes: {result.get('playwright_detail')}\n"
        if result.get("screenshot"):
            msg += f"Screenshot: {result['screenshot']}\n"
        send_slack(msg)
    else:
        print(f"[{result['timestamp']}] Checagem OK.")

    return result

# --- Relatórios em PDF ---
def generate_daily_report(for_date: date = None):
    """
    Gera relatório diário em PDF com os logs do dia especificado (default = hoje).
    Salva em relatorio/daily/YYYY-MM-DD_report.pdf
    """
    if for_date is None:
        for_date = datetime.now(TZ).date()
    start = datetime(for_date.year, for_date.month, for_date.day, tzinfo=TZ)
    end = start + timedelta(days=1)

    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    rec_time = datetime.fromisoformat(obj['recorded_at'].rsplit(" ", 2)[0])
                    # recorded_at includes timezone abbreviation — fragile; instead parse timestamp field
                except Exception:
                    obj = json.loads(line)
                # we'll filter by 'timestamp' string
                ts_str = obj.get("timestamp")
                try:
                    ts_dt = datetime.strptime(ts_str.split(" ")[0], "%Y-%m-%d")
                except Exception:
                    ts_dt = None
                logs.append(obj)
    # Filtra logs do dia (simple: timestamp startswith date)
    day_prefix = for_date.strftime("%Y-%m-%d")
    logs_of_day = [l for l in logs if l.get("timestamp", "").startswith(day_prefix)]

    # Cria PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, f"Relatório Diário - {for_date.isoformat()}", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, f"Gerado: {now_str()}", ln=True)
    pdf.ln(4)

    ok_count = sum(1 for l in logs_of_day if l.get("ok_http") and l.get("ok_playwright"))
    total = len(logs_of_day)
    pdf.cell(0, 7, f"Total de checagens no dia: {total}", ln=True)
    pdf.cell(0, 7, f"Checagens OK: {ok_count}", ln=True)
    pdf.cell(0, 7, f"Falhas: {total - ok_count}", ln=True)
    pdf.ln(6)

    if total == 0:
        pdf.cell(0, 7, "Nenhuma checagem registrada neste dia.", ln=True)
    else:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "Incidentes / Detalhes:", ln=True)
        pdf.set_font("Arial", size=10)
        incidents = [l for l in logs_of_day if not (l.get("ok_http") and l.get("ok_playwright"))]
        if not incidents:
            pdf.cell(0, 6, "Nenhum incidente registrado.", ln=True)
        else:
            for idx, inc in enumerate(incidents, 1):
                pdf.ln(2)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, f"{idx}. {inc.get('timestamp')}", ln=True)
                pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 5, json.dumps({
                    "ok_http": inc.get("ok_http"),
                    "http_detail": inc.get("http_detail"),
                    "ok_playwright": inc.get("ok_playwright"),
                    "playwright_detail": inc.get("playwright_detail")
                }, ensure_ascii=False))
                # incorpora screenshot se houver
                if inc.get("screenshot") and Path(inc["screenshot"]).exists():
                    try:
                        pdf.add_page()
                        pdf.set_font("Arial", "B", 11)
                        pdf.cell(0, 6, "Screenshot do incidente:", ln=True)
                        pdf.image(str(inc["screenshot"]), w=180)
                        pdf.ln(4)
                    except Exception as e:
                        pdf.cell(0, 6, f"Erro ao adicionar imagem: {e}", ln=True)

    out_path = DAILY_DIR / f"{for_date.isoformat()}_report.pdf"
    pdf.output(str(out_path))
    print(f"Relatório diário gravado em {out_path}")
    return str(out_path)

def generate_monthly_report(reference_date: date = None):
    """
    Gera relatório mensal agregando relatórios diários dos últimos 30 dias (ou do mês corrente).
    Salva em relatorio/monthly/YYYY-MM-DD_monthly_report.pdf
    """
    if reference_date is None:
        reference_date = datetime.now(TZ).date()
    start_date = reference_date - timedelta(days=29)
    # Coleta logs dos últimos 30 dias
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    logs.append(obj)
                except:
                    continue
    logs_30 = [l for l in logs if l.get("timestamp", "").startswith(tuple(
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)
    ))]
    total = len(logs_30)
    ok_count = sum(1 for l in logs_30 if l.get("ok_http") and l.get("ok_playwright"))
    incidents = [l for l in logs_30 if not (l.get("ok_http") and l.get("ok_playwright"))]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, f"Relatório Mensal (últimos 30 dias) - até {reference_date.isoformat()}", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, f"Gerado: {now_str()}", ln=True)
    pdf.ln(4)
    pdf.cell(0, 7, f"Total checagens (30 dias): {total}", ln=True)
    pdf.cell(0, 7, f"Checagens OK: {ok_count}", ln=True)
    pdf.cell(0, 7, f"Incidentes: {len(incidents)}", ln=True)
    pdf.ln(6)

    # sumariza incidentes (até 20)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Incidentes (amostragem):", ln=True)
    pdf.set_font("Arial", size=10)
    for inc in incidents[:20]:
        pdf.multi_cell(0, 5, f"- {inc.get('timestamp')} | HTTP: {inc.get('ok_http')} | PW: {inc.get('ok_playwright')}")
    out_path = MONTHLY_DIR / f"{reference_date.isoformat()}_monthly_report.pdf"
    pdf.output(str(out_path))
    print(f"Relatório mensal gravado em {out_path}")
    return str(out_path)

# --- Agendamento ---
scheduler = BackgroundScheduler(timezone=TIMEZONE)

# Job: checagem periódica
def job_check():
    try:
        perform_check()
    except Exception as e:
        send_slack(f"Erro crítico no job_check: {e}\n{traceback.format_exc()}")

scheduler.add_job(job_check, 'interval', hours=CHECK_INTERVAL_HOURS, next_run_time=datetime.now(TZ))

# Job: gerar relatório diário em hora definida
def job_daily_report():
    try:
        today = datetime.now(TZ).date()
        generate_daily_report(for_date=today)
    except Exception as e:
        send_slack(f"Erro ao gerar relatório diário: {e}\n{traceback.format_exc()}")

scheduler.add_job(job_daily_report, 'cron', hour=DAILY_REPORT_HOUR, minute=5)

# Job: gerar relatório mensal a cada 30 dias (simples)
def job_monthly_report():
    try:
        generate_monthly_report()
    except Exception as e:
        send_slack(f"Erro ao gerar relatório mensal: {e}\n{traceback.format_exc()}")

# agenda mensal a cada 30 dias a partir de hoje
scheduler.add_job(job_monthly_report, 'interval', days=30, next_run_time=datetime.now(TZ) + timedelta(seconds=10))

if __name__ == "__main__":
    print("Iniciando scheduler...")
    scheduler.start()
    # faz uma checagem inicial imediata
    job_check()
    try:
        # mantem o processo vivo
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        print("Encerrando...")
        scheduler.shutdown()
