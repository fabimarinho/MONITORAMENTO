from datetime import datetime, date, timedelta
import json
from pathlib import Path
from fpdf import FPDF
from typing import List, Dict, Any

from config import Settings
from utils import now_str

class ReportGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_daily_report(self, for_date: date = None) -> str:
        if for_date is None:
            for_date = datetime.now(self.settings.tz).date()
            
        logs = self._get_logs_for_date(for_date)
        
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        self._write_daily_header(pdf, for_date)
        self._write_daily_summary(pdf, logs)
        self._write_daily_incidents(pdf, logs)
        
        out_path = self.settings.DAILY_DIR / f"{for_date.isoformat()}_report.pdf"
        pdf.output(str(out_path))
        return str(out_path)

    def generate_monthly_report(self, reference_date: date = None) -> str:
        if reference_date is None:
            reference_date = datetime.now(self.settings.tz).date()
            
        logs = self._get_logs_for_last_30_days(reference_date)
        
        pdf = FPDF()
        pdf.add_page()
        
        self._write_monthly_header(pdf, reference_date)
        self._write_monthly_summary(pdf, logs)
        self._write_monthly_incidents(pdf, logs)
        
        out_path = self.settings.MONTHLY_DIR / f"{reference_date.isoformat()}_monthly_report.pdf"
        pdf.output(str(out_path))
        return str(out_path)

    def _get_logs_for_date(self, for_date: date) -> List[Dict[str, Any]]:
        day_prefix = for_date.strftime("%Y-%m-%d")
        return [
            log for log in self._read_all_logs()
            if log.get("timestamp", "").startswith(day_prefix)
        ]

    def _get_logs_for_last_30_days(self, reference_date: date) -> List[Dict[str, Any]]:
        start_date = reference_date - timedelta(days=29)
        date_prefixes = [
            (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(30)
        ]
        return [
            log for log in self._read_all_logs()
            if log.get("timestamp", "").startswith(tuple(date_prefixes))
        ]

    def _read_all_logs(self) -> List[Dict[str, Any]]:
        logs = []
        if self.settings.LOG_FILE.exists():
            with open(self.settings.LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except:
                        continue
        return logs

    def _write_daily_header(self, pdf: FPDF, for_date: date):
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, f"Relatório Diário - {for_date.isoformat()}", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 7, f"Gerado: {now_str(self.settings)}", ln=True)
        pdf.ln(4)

    def _write_daily_summary(self, pdf: FPDF, logs: List[Dict[str, Any]]):
        ok_count = sum(1 for l in logs if l.get("ok_http") and l.get("ok_playwright"))
        total = len(logs)
        
        pdf.cell(0, 7, f"Total de checagens no dia: {total}", ln=True)
        pdf.cell(0, 7, f"Checagens OK: {ok_count}", ln=True)
        pdf.cell(0, 7, f"Falhas: {total - ok_count}", ln=True)
        pdf.ln(6)

    def _write_daily_incidents(self, pdf: FPDF, logs: List[Dict[str, Any]]):
        incidents = [l for l in logs if not (l.get("ok_http") and l.get("ok_playwright"))]
        
        if not incidents:
            pdf.cell(0, 6, "Nenhum incidente registrado.", ln=True)
            return
            
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "Incidentes / Detalhes:", ln=True)
        pdf.set_font("Arial", size=10)
        
        for idx, inc in enumerate(incidents, 1):
            self._write_incident(pdf, idx, inc)

    def _write_incident(self, pdf: FPDF, idx: int, incident: Dict[str, Any]):
        pdf.ln(2)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, f"{idx}. {incident.get('timestamp')}", ln=True)
        pdf.set_font("Arial", size=10)
        
        details = {
            "ok_http": incident.get("ok_http"),
            "http_detail": incident.get("http_detail"),
            "ok_playwright": incident.get("ok_playwright"),
            "playwright_detail": incident.get("playwright_detail")
        }
        pdf.multi_cell(0, 5, json.dumps(details, ensure_ascii=False))
        
        if incident.get("screenshot"):
            self._add_screenshot(pdf, incident["screenshot"])

    def _add_screenshot(self, pdf: FPDF, screenshot_path: str):
        screenshot = Path(screenshot_path)
        if screenshot.exists():
            try:
                pdf.add_page()
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, "Screenshot do incidente:", ln=True)
                pdf.image(str(screenshot), w=180)
                pdf.ln(4)
            except Exception as e:
                pdf.cell(0, 6, f"Erro ao adicionar imagem: {e}", ln=True)