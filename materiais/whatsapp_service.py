"""
Serviço de Notificações WhatsApp para eventos críticos.
Integração com APIs WhatsApp (Evolution API, WPPCONNECT, etc.)
"""
import requests
import logging
from django.conf import settings
from materiais.models import ConfiguracaoWhatsApp, User

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Gerencia envio de notificações via WhatsApp"""
    
    def __init__(self):
        self.config = None
        self._carregar_configuracao()
    
    def _carregar_configuracao(self):
        """Carrega configuração do banco de dados"""
        try:
            self.config = ConfiguracaoWhatsApp.objects.first()
            if not self.config:
                logger.warning("⚠️ Configuração WhatsApp não encontrada no banco")
        except Exception as e:
            logger.error(f"❌ Erro ao carregar configuração WhatsApp: {e}")
    
    def esta_ativo(self):
        """Verifica se o serviço WhatsApp está ativo"""
        return self.config and self.config.ativo and self.config.api_url and self.config.api_token
    
    def enviar_mensagem(self, numero, mensagem, titulo=""):
        """
        Envia mensagem WhatsApp para um número.
        
        Args:
            numero: Número de telefone (formato: 5511999999999)
            mensagem: Texto da mensagem
            titulo: Título opcional (será em negrito)
            
        Returns:
            bool: True se enviado com sucesso
        """
        if not self.esta_ativo():
            logger.warning("⚠️ WhatsApp não está ativo. Mensagem não enviada.")
            return False
        
        try:
            # Remove caracteres não numéricos
            numero_limpo = ''.join(filter(str.isdigit, numero))
            
            if not numero_limpo:
                logger.error("❌ Número de telefone inválido")
                return False
            
            # Monta mensagem formatada
            texto_completo = f"*{titulo}*\n\n{mensagem}" if titulo else mensagem
            
            # Payload para Evolution API (formato padrão)
            payload = {
                "number": numero_limpo,
                "text": texto_completo
            }
            
            headers = {
                "Content-Type": "application/json",
                "apikey": self.config.api_token
            }
            
            # Envia requisição
            response = requests.post(
                f"{self.config.api_url}/message/sendText",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ WhatsApp enviado para {numero_limpo}")
                return True
            else:
                logger.error(f"❌ Erro ao enviar WhatsApp: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout ao enviar WhatsApp")
            return False
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao enviar WhatsApp: {e}")
            return False
    
    def notificar_sc_urgente(self, solicitacao):
        """
        Notifica sobre SC urgente (data necessária em menos de 3 dias).
        
        Args:
            solicitacao: Instância de SolicitacaoCompra
        """
        if not self.esta_ativo() or not self.config.notificar_sc_urgente:
            return False
        
        titulo = "🚨 SOLICITAÇÃO URGENTE"
        mensagem = (
            f"SC {solicitacao.numero}\n"
            f"Obra: {solicitacao.obra.nome}\n"
            f"Necessário: {solicitacao.data_necessidade.strftime('%d/%m/%Y')}\n"
            f"Itens: {solicitacao.itens.count()}\n\n"
            f"⚠️ ATENÇÃO: Prazo curto! Iniciar cotação imediatamente."
        )
        
        # Notifica almoxarife e diretor
        enviados = 0
        if self.config.numero_almoxarife:
            if self.enviar_mensagem(self.config.numero_almoxarife, mensagem, titulo):
                enviados += 1
        
        if self.config.numero_diretor:
            if self.enviar_mensagem(self.config.numero_diretor, mensagem, titulo):
                enviados += 1
        
        return enviados > 0
    
    def notificar_cotacao_vencida(self, envio_cotacao):
        """
        Notifica sobre cotação com prazo vencido e sem resposta.
        
        Args:
            envio_cotacao: Instância de EnvioCotacao
        """
        if not self.esta_ativo() or not self.config.notificar_cotacao_vencida:
            return False
        
        dias_vencido = (timezone.now().date() - envio_cotacao.prazo_resposta).days
        
        titulo = "⏰ COTAÇÃO VENCIDA"
        mensagem = (
            f"SC {envio_cotacao.solicitacao.numero}\n"
            f"Fornecedor: {envio_cotacao.fornecedor.nome_fantasia}\n"
            f"Prazo vencido há: {dias_vencido} dia(s)\n\n"
            f"⚠️ Verificar com fornecedor ou buscar alternativas."
        )
        
        # Notifica apenas almoxarife
        if self.config.numero_almoxarife:
            return self.enviar_mensagem(self.config.numero_almoxarife, mensagem, titulo)
        
        return False
    
    def notificar_rm_pendente_7dias(self, requisicao):
        """
        Notifica sobre RM com assinatura pendente há 7+ dias.
        
        Args:
            requisicao: Instância de RequisicaoMaterial
        """
        if not self.esta_ativo() or not self.config.notificar_rm_pendente_7dias:
            return False
        
        titulo = "📋 RM PENDENTE DE ASSINATURA"
        mensagem = (
            f"RM para SC {requisicao.solicitacao_compra.numero}\n"
            f"Fornecedor: {requisicao.fornecedor.nome_fantasia}\n"
            f"Valor: R$ {requisicao.cotacao.valor_total:,.2f}\n"
            f"Criada há: {(timezone.now().date() - requisicao.data_criacao.date()).days} dias\n\n"
            f"⚠️ Assinaturas pendentes:\n"
        )
        
        if not requisicao.assinatura_almoxarife:
            mensagem += "• Almoxarife\n"
        if not requisicao.assinatura_engenheiro:
            mensagem += "• Engenheiro\n"
        if not requisicao.assinatura_diretor:
            mensagem += "• Diretor\n"
        
        # Notifica diretor e engenheiro
        enviados = 0
        if self.config.numero_diretor:
            if self.enviar_mensagem(self.config.numero_diretor, mensagem, titulo):
                enviados += 1
        
        if self.config.numero_engenheiro:
            if self.enviar_mensagem(self.config.numero_engenheiro, mensagem, titulo):
                enviados += 1
        
        return enviados > 0
    
    def testar_conexao(self):
        """
        Testa a conexão com a API WhatsApp.
        
        Returns:
            tuple: (sucesso: bool, mensagem: str)
        """
        if not self.config:
            return False, "Configuração não encontrada"
        
        if not self.config.api_url or not self.config.api_token:
            return False, "API URL ou Token não configurados"
        
        try:
            headers = {
                "Content-Type": "application/json",
                "apikey": self.config.api_token
            }
            
            # Tenta verificar status da instância
            response = requests.get(
                f"{self.config.api_url}/instance/connectionState",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return True, f"Conexão OK: {data.get('state', 'conectado')}"
            else:
                return False, f"Erro: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Timeout - API não responde"
        except Exception as e:
            return False, f"Erro: {str(e)}"


# Instância global
whatsapp_service = WhatsAppService()


# === FUNÇÕES DE VERIFICAÇÃO AUTOMÁTICA (para scheduler) ===

from django.utils import timezone
from datetime import timedelta
from materiais.models import SolicitacaoCompra, EnvioCotacao, RequisicaoMaterial
from django.db.models import Q


def verificar_scs_urgentes():
    """Verifica SCs com prazo apertado (< 3 dias) e notifica via WhatsApp"""
    if not whatsapp_service.esta_ativo():
        return
    
    limite = timezone.now().date() + timedelta(days=3)
    
    scs_urgentes = SolicitacaoCompra.objects.filter(
        status='aprovado',
        data_necessidade__lte=limite
    )
    
    for sc in scs_urgentes:
        whatsapp_service.notificar_sc_urgente(sc)
        logger.info(f"📱 WhatsApp enviado para SC urgente: {sc.numero}")


def verificar_cotacoes_vencidas_whatsapp():
    """Verifica cotações vencidas há mais de 2 dias e notifica via WhatsApp"""
    if not whatsapp_service.esta_ativo():
        return
    
    limite = timezone.now().date() - timedelta(days=2)
    
    envios_vencidos = EnvioCotacao.objects.filter(
        status='aguardando',
        prazo_resposta__lt=limite
    )
    
    for envio in envios_vencidos:
        whatsapp_service.notificar_cotacao_vencida(envio)
        logger.info(f"📱 WhatsApp enviado para cotação vencida: {envio.fornecedor.nome_fantasia}")


def verificar_rms_pendentes_whatsapp():
    """Verifica RMs com assinatura pendente há 7+ dias e notifica via WhatsApp"""
    if not whatsapp_service.esta_ativo():
        return
    
    limite = timezone.now() - timedelta(days=7)
    
    rms_pendentes = RequisicaoMaterial.objects.filter(
        data_criacao__lte=limite
    ).filter(
        Q(assinatura_almoxarife__isnull=True) |
        Q(assinatura_engenheiro__isnull=True) |
        Q(assinatura_diretor__isnull=True)
    )
    
    for rm in rms_pendentes:
        whatsapp_service.notificar_rm_pendente_7dias(rm)
        logger.info(f"📱 WhatsApp enviado para RM pendente: {rm.id}")
