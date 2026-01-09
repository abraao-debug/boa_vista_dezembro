"""
Agendador automático de tarefas usando APScheduler.
Executa verificação de pendências e cálculo de métricas automaticamente.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


# === FASE 2: VERIFICAÇÃO DE PENDÊNCIAS ===

def verificar_pendencias_automatico():
    """Executa o comando verificar_pendencias automaticamente."""
    try:
        logger.info("🤖 Iniciando verificação automática de pendências...")
        call_command('verificar_pendencias')
        logger.info("✅ Verificação automática concluída com sucesso!")
    except Exception as e:
        logger.error(f"❌ Erro na verificação automática: {str(e)}")


# === FASE 3: NOVAS TAREFAS AUTOMÁTICAS ===

def calcular_metricas_automatico():
    """Calcula métricas diárias de desempenho."""
    try:
        logger.info("📊 Iniciando cálculo automático de métricas...")
        call_command('calcular_metricas')
        logger.info("✅ Métricas calculadas com sucesso!")
    except Exception as e:
        logger.error(f"❌ Erro ao calcular métricas: {str(e)}")


def verificar_whatsapp_automatico():
    """Verifica eventos críticos e envia WhatsApp se configurado."""
    try:
        logger.info("📱 Verificando eventos para WhatsApp...")
        from materiais.whatsapp_service import (
            verificar_scs_urgentes,
            verificar_cotacoes_vencidas_whatsapp,
            verificar_rms_pendentes_whatsapp
        )
        
        verificar_scs_urgentes()
        verificar_cotacoes_vencidas_whatsapp()
        verificar_rms_pendentes_whatsapp()
        
        logger.info("✅ Verificação WhatsApp concluída!")
    except Exception as e:
        logger.error(f"❌ Erro na verificação WhatsApp: {str(e)}")


def start():
    """Inicia o agendador de tarefas com todas as rotinas."""
    scheduler = BackgroundScheduler()
    
    # === FASE 2: VERIFICAÇÃO DE PENDÊNCIAS ===
    # Executa todo dia às 8:00
    scheduler.add_job(
        verificar_pendencias_automatico,
        trigger=CronTrigger(hour=8, minute=0),
        id='verificar_pendencias_diario',
        name='Verificação diária de pendências',
        replace_existing=True
    )
    
    # === FASE 3: CÁLCULO DE MÉTRICAS ===
    # Executa todo dia às 23:00 (final do dia)
    scheduler.add_job(
        calcular_metricas_automatico,
        trigger=CronTrigger(hour=23, minute=0),
        id='calcular_metricas_diario',
        name='Cálculo diário de métricas',
        replace_existing=True
    )
    
    # === FASE 3: NOTIFICAÇÕES WHATSAPP ===
    # Executa a cada 2 horas durante horário comercial (8h às 18h)
    scheduler.add_job(
        verificar_whatsapp_automatico,
        trigger=CronTrigger(hour='8-18/2'),  # 8h, 10h, 12h, 14h, 16h, 18h
        id='verificar_whatsapp_periodico',
        name='Verificação periódica WhatsApp',
        replace_existing=True
    )
    
    scheduler.start()
    
    logger.info("🚀 Agendador de tarefas FASE 3 iniciado!")
    logger.info("📅 Tarefas agendadas:")
    logger.info("  • Pendências: 08:00 (diário)")
    logger.info("  • Métricas: 23:00 (diário)")
    logger.info("  • WhatsApp: 08:00-18:00 (a cada 2h)")

