from datetime import datetime
import json
import traceback
from typing import Dict, Any
import requests
from playwright.sync_api import sync_playwright, expect
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings
from utils import now_str, append_log, send_slack

class SiteChecker:
    def __init__(self, settings: Settings):
        self.settings = settings
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def perform_check(self) -> Dict[str, Any]:
        timestamp = now_str(self.settings)
        result = {
            "timestamp": timestamp,
            "site_url": self.settings.SITE_URL,
            "portal_url": self.settings.PORTAL_URL,
            "ok_http": False,
            "http_detail": None,
            "ok_playwright": False,
            "playwright_detail": None,
            "screenshot": None,
        }

        # HTTP check
        result.update(self._do_http_check())
        
        # Playwright check
        result.update(self._do_playwright_check())

        # Log result
        append_log(self.settings, result)

        # Notify if failed
        if not result["ok_http"] or not result["ok_playwright"]:
            self._notify_failure(result)

        return result

    def _do_http_check(self) -> Dict[str, Any]:
        try:
            r = requests.get(self.settings.SITE_URL, timeout=15)
            return {
                "http_detail": {"status_code": r.status_code, "elapsed": r.elapsed.total_seconds()},
                "ok_http": (r.status_code == 200)
            }
        except Exception as e:
            return {
                "http_detail": {"error": str(e)},
                "ok_http": False
            }

    def _do_playwright_check(self) -> Dict[str, Any]:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                
                page.goto(self.settings.PORTAL_URL, wait_until="networkidle", timeout=30000)
                
                detail_msgs = []
                playwright_ok = self._interact_with_page(page, detail_msgs)
                
                screenshot_path = None
                if not playwright_ok:
                    screenshot_path = self._take_failure_screenshot(page)
                    
                browser.close()
                
                return {
                    "ok_playwright": playwright_ok,
                    "playwright_detail": {"messages": detail_msgs},
                    "screenshot": screenshot_path
                }
                
        except Exception as e:
            tb = traceback.format_exc()
            return {
                "ok_playwright": False,
                "playwright_detail": {"error": str(e), "traceback": tb}
            }

    def _interact_with_page(self, page, detail_msgs):
        try:
            # Localiza e interage com select da organização
            org_select = page.locator('[data-testid="org-select"], select:has-text("Organização")')
            expect(org_select).to_be_visible(timeout=1000) #Aumentando o timeout
            org_select.select_option(label=self.settings.SUCCESS_ORG_LABEL)
            detail_msgs.append("select: organização selecionada")
            
            # Espera lista de documentos
            doc_list = page.locator('[data-testid="doc-list"], .documents-list')
            expect(doc_list).to_be_visible(timeout=10000)
            
            # Abre primeiro documento
            first_doc = page.locator('[data-testid="doc-link"], a:has-text("Visualizar")').first
            expect(first_doc).to_be_visible(timeout=5000)
            first_doc.click()
            
            # Verifica se documento abriu
            doc_viewer = page.locator('iframe[src*="pdf"], embed[type="application/pdf"]')
            expect(doc_viewer).to_be_visible(timeout=10000)
            
            detail_msgs.append("documento aberto com sucesso")
            return True
            
        except Exception as e:
            detail_msgs.append(f"erro: {str(e)}")
            return False

    def _take_failure_screenshot(self, page) -> str:
        """Tira screenshot em caso de falha"""
        timestamp = datetime.now(self.settings.tz).strftime("%Y%m%d_%H%M%S")
        screenshot_path = str(self.settings.FAIL_DIR / f"fail_{timestamp}.png")
        try:
            # Garante que a pasta failures existe
            self.settings.FAIL_DIR.mkdir(parents=True, exist_ok=True)
            
            # Tira o screenshot da página inteira
            page.screenshot(
                path=screenshot_path,
                full_page=True  # Captura a página inteira
            )
            print(f"Screenshot salvo em: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            print(f"Erro ao tirar screenshot: {e}")
            return None

    def _notify_failure(self, result: Dict[str, Any]):
        msg = (
            f"🚨 Problema detectado em {result['site_url']} em {result['timestamp']}.\n"
            f"HTTP OK: {result['ok_http']}\n"
            f"Playwright OK: {result['ok_playwright']}\n"
            f"Detalhes: {result.get('playwright_detail')}\n"
        )
        if result.get("screenshot"):
            msg += f"Screenshot: {result['screenshot']}\n"
        send_slack(self.settings, msg)