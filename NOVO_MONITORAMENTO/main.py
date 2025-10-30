from datetime import datetime, timedelta
import time
import traceback
from apscheduler.schedulers.background import BackgroundScheduler

from config import load_settings
from check import SiteChecker
from report import ReportGenerator
from utils import send_slack

def main():
    # Carrega configurações
    settings = load_settings()
    
    # Inicializa componentes
    checker = SiteChecker(settings)
    report_gen = ReportGenerator(settings)
    
    # Configura scheduler
    scheduler = BackgroundScheduler(timezone=settings.TIMEZONE)
    
    # Job: checagem periódica
    def job_check():
        try:
            checker.perform_check()
        except Exception as e:
            send_slack(settings, f"Erro crítico no job_check: {e}\n{traceback.format_exc()}")
    
    # Job: relatório diário
    def job_daily_report():
        try:
            today = datetime.now(settings.tz).date()
            report_gen.generate_daily_report(for_date=today)
        except Exception as e:
            send_slack(settings, f"Erro ao gerar relatório diário: {e}\n{traceback.format_exc()}")
    
    # Job: relatório mensal
    def job_monthly_report():
        try:
            report_gen.generate_monthly_report()
        except Exception as e:
            send_slack(settings, f"Erro ao gerar relatório mensal: {e}\n{traceback.format_exc()}")
    
    # Agenda jobs
    # Executa checagem periódica em minutos (configurável via CHECK_INTERVAL_MINUTES)
    scheduler.add_job(
        job_check,
        'interval',
        minutes=settings.CHECK_INTERVAL_MINUTES,
        next_run_time=datetime.now(settings.tz)
    )

    # Gera relatório diário em PDF a cada 24 horas
    scheduler.add_job(
        job_daily_report,
        'interval',
        days=1,
        next_run_time=datetime.now(settings.tz) + timedelta(seconds=10)
    )
    
    scheduler.add_job(
        job_monthly_report,
        'interval',
        days=30,
        next_run_time=datetime.now(settings.tz) + timedelta(seconds=10)
    )

    # Inicia scheduler
    print("Iniciando scheduler...")
    scheduler.start()
    
    # Executa checagem inicial
    job_check()
    
    # Loop principal
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        print("Encerrando...")
        scheduler.shutdown()

if __name__ == "__main__":
    main()