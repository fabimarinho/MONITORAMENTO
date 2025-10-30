 # Lógica de verificação
# Adicionar estratégia customizada
# ...existing code...
"""
checker.py
Lógica de verificação do site e portal com Playwright
Implementa retry mechanism e esperas explícitas
"""
import time
import traceback
from typing import Dict, Optional
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright, Page, expect

from config import config
from logger import logger
from notifications import notifier


class SiteChecker:
    """Realiza verificações no site e portal"""
    
    def __init__(self):
        self.config = config
    
    def check_with_retry(self) -> Dict:
        """
        Executa checagem com mecanismo de retry
        Tenta até MAX_RETRIES vezes antes de registrar falha definitiva
        """
        last_result = None
        
        for attempt in range(1, config.retry_attempts + 1):
            logger.info(f"Tentativa {attempt}/{config.retry_attempts}")
            
            result = self._perform_single_check()
            last_result = result
            
            # Se teve sucesso completo, retorna imediatamente
            if result["ok_http"] and result["ok_playwright"]:
                logger.info("✅ Checagem bem-sucedida")
                return result
            
            # Se falhou, mas ainda tem tentativas, aguarda e tenta novamente
            if attempt < config.retry_attempts:
                logger.warning(
                    f"⚠️ Tentativa {attempt} falhou. "
                    f"Aguardando {config.retry_delay_seconds}s antes de tentar novamente..."
                )
                time.sleep(config.retry_delay_seconds)
        
        # Todas as tentativas falharam
        logger.error(f"❌ Todas as {config.retry_attempts} tentativas falharam")
        return last_result
    
    def _perform_single_check(self) -> Dict:
        """Realiza uma única checagem completa"""
        timestamp = logger.now_str()
        result = {
            "timestamp": timestamp,
            "site_url": config.site_url,
            "portal_url": config.portal_url,
            "ok_http": False,
            "http_detail": None,
            "ok_playwright": False,
            "playwright_detail": None,
            "playwright_elapsed": 0,
            "screenshot": None,
        }
        
        # 1. Checagem HTTP
        result = self._check_http(result)
        
        # 2. Checagem Playwright
        result = self._check_playwright(result)
        
        # 3. Análise de performance
        result = self._analyze_performance(result)
        
        return result
    
    def _check_http(self, result: Dict) -> Dict:
        """Realiza checagem HTTP simples"""
        try:
            start_time = time.time()
            response = requests.get(
                config.site_url,
                timeout=config.http_timeout
            )
            elapsed = time.time() - start_time
            
            result["http_detail"] = {
                "status_code": response.status_code,
                "elapsed": elapsed,
                "content_length": len(response.content)
            }
            result["ok_http"] = (response.status_code == 200)
            
            if response.status_code != 200:
                logger.warning(f"HTTP retornou status {response.status_code}")
            
        except requests.Timeout:
            result["http_detail"] = {"error": "Timeout na requisição HTTP"}
            result["ok_http"] = False
            logger.error("HTTP Timeout")
            
        except requests.ConnectionError as e:
            result["http_detail"] = {"error": f"Erro de conexão: {str(e)}"}
            result["ok_http"] = False
            logger.error(f"Erro de conexão HTTP: {e}")
            
        except Exception as e:
            result["http_detail"] = {"error": str(e)}
            result["ok_http"] = False
            logger.error(f"Erro HTTP: {e}")
        
        return result
    
    def _check_playwright(self, result: Dict) -> Dict:
        """Realiza checagem com Playwright (automação browser)"""
        screenshot_path = None
        detail_msgs = []
        start_time = time.time()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080}
                )
                page = context.new_page()
                page.set_default_timeout(config.playwright_timeout)
                
                # Navega para o portal
                logger.info(f"Acessando {config.portal_url}")
                page.goto(config.portal_url)
                detail_msgs.append("Página carregada")
                
                # Tenta selecionar a organização
                org_selected = self._select_organization(page, detail_msgs)
                
                if org_selected:
                    # Tenta abrir o primeiro documento
                    doc_opened = self._open_first_document(page, detail_msgs)
                    
                    if doc_opened:
                        # Verifica se o documento foi realmente aberto
                        content_verified = self._verify_document_content(page, detail_msgs)
                        result["ok_playwright"] = content_verified
                    else:
                        result["ok_playwright"] = False
                else:
                    result["ok_playwright"] = False
                
                # Captura screenshot se falhou
                if not result["ok_playwright"]:
                    screenshot_path = self._capture_screenshot(page)
                
                browser.close()
                
        except Exception as e:
            tb = traceback.format_exc()
            detail_msgs.append(f"Erro crítico: {str(e)}")
            result["ok_playwright"] = False
            logger.error(f"Erro no Playwright: {e}\n{tb}")
        
        elapsed = time.time() - start_time
        result["playwright_elapsed"] = elapsed
        result["playwright_detail"] = {"messages": detail_msgs}
        if screenshot_path:
            result["screenshot"] = screenshot_path
        
        return result
    
    def _select_organization(self, page: Page, msgs: list) -> bool:
        """
        Tenta selecionar a organização usando múltiplas estratégias
        com esperas explícitas
        """
        try:
            # Estratégia 1: Procurar por select dropdown
            selects = page.locator("select").all()
            if selects:
                for select in selects:
                    try:
                        # Aguarda o select estar visível
                        expect(select).to_be_visible(timeout=5000)
                        
                        # Tenta selecionar por label
                        select.select_option(label=config.success_org_label)
                        msgs.append(f"✓ Select: selecionado '{config.success_org_label}'")
                        
                        # Aguarda possível atualização da página
                        page.wait_for_load_state("networkidle", timeout=5000)
                        return True
                    except Exception as e:
                        msgs.append(f"Select falhou: {str(e)[:100]}")
                        continue
            
            # Estratégia 2: Clicar no texto exato da organização
            try:
                org_locator = page.get_by_text(config.success_org_label, exact=True)
                
                # Aguarda elemento estar visível
                expect(org_locator).to_be_visible(timeout=5000)
                
                org_locator.first.click()
                msgs.append(f"✓ Click: clicou em '{config.success_org_label}'")
                
                # Aguarda carregamento
                page.wait_for_load_state("networkidle", timeout=5000)
                return True
                
            except Exception as e:
                msgs.append(f"Click no texto falhou: {str(e)[:100]}")
            
            # Estratégia 3: Procurar por data-testid ou IDs específicos
            # (adicione aqui se houver atributos específicos no HTML)
            
            msgs.append("⚠️ Nenhuma estratégia de seleção funcionou")
            return False
            
        except Exception as e:
            msgs.append(f"Erro ao selecionar organização: {str(e)}")
            return False
    
    def _open_first_document(self, page: Page, msgs: list) -> bool:
        """Tenta abrir o primeiro documento listado"""
        try:
            # Aguarda lista de documentos carregar
            page.wait_for_selector("a", timeout=5000)
            
            # Estratégia 1: Links que parecem ser documentos
            doc_links = page.locator("a").all()
            
            for link in doc_links:
                try:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip().lower()
                    
                    # Heurística: detectar links de documentos
                    if any(keyword in href.lower() or keyword in text for keyword in [
                        "publicacao", "download", "documento", "pdf",
                        "visualizar", "abrir", "ver"
                    ]):
                        expect(link).to_be_visible(timeout=3000)
                        link.click()
                        msgs.append(f"✓ Documento: clicou em link (href={href[:60]})")
                        
                        # Aguarda navegação ou modal
                        page.wait_for_load_state("networkidle", timeout=10000)
                        return True
                        
                except Exception:
                    continue
            
            # Fallback: clicar no primeiro link
            if doc_links:
                doc_links[0].click()
                msgs.append("⚠️ Fallback: clicou no primeiro link")
                page.wait_for_load_state("networkidle", timeout=10000)
                return True
            
            msgs.append("❌ Nenhum link de documento encontrado")
            return False
            
        except Exception as e:
            msgs.append(f"Erro ao abrir documento: {str(e)}")
            return False
    
    def _verify_document_content(self, page: Page, msgs: list) -> bool:
        """Verifica se o documento foi realmente aberto"""
        try:
            # Procura por indicadores de que o PDF/documento está aberto
            indicators = [
                "iframe",  # PDF em iframe
                "embed",   # PDF embed
                'object[type="application/pdf"]',
                'a[href*=".pdf"]'
            ]
            
            for indicator in indicators:
                try:
                    element = page.locator(indicator)
                    if element.count() > 0:
                        expect(element.first).to_be_visible(timeout=3000)
                        msgs.append(f"✓ Conteúdo: encontrado {indicator}")
                        return True
                except Exception:
                    continue
            
            # Verifica se há conteúdo relevante na página
            # (adapte isso para o portal específico)
            body_text = page.locator("body").inner_text().lower()
            if any(keyword in body_text for keyword in ["diário oficial", "publicação", "documento"]):
                msgs.append("✓ Conteúdo: texto relevante encontrado")
                return True
            
            msgs.append("⚠️ Conteúdo: nenhum indicador de documento encontrado")
            return False
            
        except Exception as e:
            msgs.append(f"Erro ao verificar conteúdo: {str(e)}")
            return False
    
    def _capture_screenshot(self, page: Page) -> Optional[str]:
        """Captura screenshot para diagnóstico"""
        try:
            timestamp = int(time.time())
            screenshot_name = f"failure_{timestamp}.png"
            screenshot_path = str(config.fail_dir / screenshot_name)
            
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot capturado: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot: {e}")
            return None
    
    def _analyze_performance(self, result: Dict) -> Dict:
        """Analisa performance e adiciona flags de degradação"""
        http_elapsed = result.get("http_detail", {}).get("elapsed", 0)
        pw_elapsed = result.get("playwright_elapsed", 0)
        
        # Thresholds de performance (configuráveis)
        HTTP_SLOW_THRESHOLD = 5.0  # segundos
        PW_SLOW_THRESHOLD = 30.0   # segundos
        
        result["performance_degraded"] = (
            http_elapsed > HTTP_SLOW_THRESHOLD or 
            pw_elapsed > PW_SLOW_THRESHOLD
        )
        
        if result["performance_degraded"]:
            logger.warning(
                f"⚠️ Performance degradada - "
                f"HTTP: {http_elapsed:.2f}s, Playwright: {pw_elapsed:.2f}s"
            )
        
        return result


# Instância global
checker = SiteChecker()










