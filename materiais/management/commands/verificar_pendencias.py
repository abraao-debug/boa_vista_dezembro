"""
Command Django para verificar pendências e enviar notificações automáticas.
Deve ser executado diariamente via cron job ou Task Scheduler.

Uso:
    python manage.py verificar_pendencias
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from materiais.models import (
    SolicitacaoCompra, EnvioCotacao, RequisicaoMaterial, 
    Notificacao, HistoricoSolicitacao
)


class Command(BaseCommand):
    help = 'Verifica pendências e envia notificações automáticas - FASE 2'

    def criar_notificacao_sistema(self, destinatario_perfil=None, destinatario_usuario=None, 
                                   titulo='', mensagem='', link=''):
        """Helper para criar notificações do sistema."""
        from materiais.models import User
        
        if destinatario_usuario:
            Notificacao.objects.create(
                usuario_destino=destinatario_usuario,
                titulo=titulo,
                mensagem=mensagem,
                link=link
            )
        elif destinatario_perfil:
            usuarios = User.objects.filter(perfil=destinatario_perfil, is_active=True)
            for usuario in usuarios:
                Notificacao.objects.create(
                    usuario_destino=usuario,
                    titulo=titulo,
                    mensagem=mensagem,
                    link=link
                )

    def handle(self, *args, **options):
        """Executa todas as verificações de pendências."""
        
        self.stdout.write(self.style.SUCCESS('Iniciando verificação de pendências...'))
        
        # TASK 2: Verifica prazos de resposta vencidos
        self.verificar_prazos_resposta_vencidos()
        
        # TASK 4: Verifica RMs com assinaturas pendentes há muito tempo
        self.verificar_assinaturas_pendentes()
        
        # TASK 10: Lembretes automáticos X dias antes da data necessária
        self.enviar_lembretes_data_necessaria()
        
        self.stdout.write(self.style.SUCCESS('Verificação concluída!'))

    def verificar_prazos_resposta_vencidos(self):
        """FASE 2 - Task 2: Notifica sobre cotações não respondidas após prazo."""
        hoje = timezone.now().date()
        
        # Busca envios com prazo vencido que ainda não responderam
        envios_vencidos = EnvioCotacao.objects.filter(
            prazo_resposta__lt=hoje,
            solicitacao__status__in=['aguardando_resposta', 'em_cotacao']
        ).select_related('fornecedor', 'solicitacao')
        
        # Verifica quais ainda não têm cotação
        for envio in envios_vencidos:
            from materiais.models import Cotacao
            
            # Se já tem cotação, pula
            if Cotacao.objects.filter(
                solicitacao=envio.solicitacao, 
                fornecedor=envio.fornecedor
            ).exists():
                continue
            
            dias_vencido = (hoje - envio.prazo_resposta).days
            
            # Verifica se já notificou nas últimas 24h para evitar spam
            ultima_notificacao = Notificacao.objects.filter(
                titulo__icontains="Prazo de Resposta Vencido",
                mensagem__icontains=envio.fornecedor.nome_fantasia,
                mensagem__icontains=envio.solicitacao.numero,
                data_criacao__gte=timezone.now() - timedelta(hours=24)
            ).first()
            
            if ultima_notificacao:
                continue
            
            # Notifica almoxarife
            self.criar_notificacao_sistema(
                destinatario_perfil='almoxarife_escritorio',
                titulo="Prazo de Resposta Vencido",
                mensagem=f"SC {envio.solicitacao.numero}: {envio.fornecedor.nome_fantasia} não respondeu há {dias_vencido} dia(s).",
                link=reverse('materiais:gerenciar_cotacoes') + '?tab=aguardando'
            )
            
            # Notifica diretor
            self.criar_notificacao_sistema(
                destinatario_perfil='diretor',
                titulo="Prazo de Resposta Vencido",
                mensagem=f"SC {envio.solicitacao.numero}: Prazo vencido há {dias_vencido} dia(s). Fornecedor: {envio.fornecedor.nome_fantasia}.",
                link=reverse('materiais:gerenciar_cotacoes') + '?tab=aguardando'
            )
            
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠ Prazo vencido: SC {envio.solicitacao.numero} - {envio.fornecedor.nome_fantasia} ({dias_vencido} dias)'
                )
            )

    def verificar_assinaturas_pendentes(self):
        """FASE 2 - Task 4: Notifica sobre RMs com assinaturas pendentes há muito tempo."""
        hoje = timezone.now()
        limite_dias = 3  # Notifica se está pendente há mais de 3 dias
        
        # RMs aguardando almoxarife
        rms_aguardando_almoxarife = RequisicaoMaterial.objects.filter(
            status_assinatura='aguardando_almoxarife',
            data_criacao__lte=hoje - timedelta(days=limite_dias)
        ).select_related('solicitacao_origem')
        
        for rm in rms_aguardando_almoxarife:
            dias_pendente = (hoje - rm.data_criacao).days
            
            # Verifica se já notificou nas últimas 24h
            ultima_notificacao = Notificacao.objects.filter(
                titulo__icontains="Assinatura Pendente",
                mensagem__icontains=rm.numero,
                data_criacao__gte=hoje - timedelta(hours=24)
            ).first()
            
            if ultima_notificacao:
                continue
            
            self.criar_notificacao_sistema(
                destinatario_perfil='almoxarife_escritorio',
                titulo="Assinatura Pendente - Urgente",
                mensagem=f"RM {rm.numero} aguarda sua assinatura há {dias_pendente} dias. Priorize!",
                link=reverse('materiais:gerenciar_requisicoes')
            )
            
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠ RM pendente: {rm.numero} - Almoxarife ({dias_pendente} dias)'
                )
            )
        
        # RMs aguardando diretor
        rms_aguardando_diretor = RequisicaoMaterial.objects.filter(
            status_assinatura='aguardando_diretor',
            data_assinatura_almoxarife__lte=hoje - timedelta(days=limite_dias)
        ).select_related('solicitacao_origem')
        
        for rm in rms_aguardando_diretor:
            dias_pendente = (hoje - rm.data_assinatura_almoxarife).days
            
            # Verifica se já notificou nas últimas 24h
            ultima_notificacao = Notificacao.objects.filter(
                titulo__icontains="Assinatura Pendente",
                mensagem__icontains=rm.numero,
                data_criacao__gte=hoje - timedelta(hours=24)
            ).first()
            
            if ultima_notificacao:
                continue
            
            self.criar_notificacao_sistema(
                destinatario_perfil='diretor',
                titulo="Assinatura Pendente - Urgente",
                mensagem=f"RM {rm.numero} aguarda sua assinatura há {dias_pendente} dias. Priorize!",
                link=reverse('materiais:gerenciar_requisicoes')
            )
            
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠ RM pendente: {rm.numero} - Diretor ({dias_pendente} dias)'
                )
            )

    def enviar_lembretes_data_necessaria(self):
        """FASE 2 - Task 10: Envia lembretes X dias antes da data necessária."""
        hoje = timezone.now().date()
        dias_antecedencia = [7, 3, 1]  # Notifica 7, 3 e 1 dia antes
        
        for dias in dias_antecedencia:
            data_alvo = hoje + timedelta(days=dias)
            
            # Busca SCs que ainda não foram finalizadas e têm data necessária próxima
            scs_proximas = SolicitacaoCompra.objects.filter(
                data_necessidade=data_alvo,
                status__in=['aprovada', 'em_cotacao', 'aguardando_resposta', 'aprovado_engenharia']
            ).select_related('solicitante', 'obra', 'destino')
            
            for sc in scs_proximas:
                # Verifica se já notificou hoje para esta SC
                ultima_notificacao = Notificacao.objects.filter(
                    titulo__icontains="Lembrete",
                    mensagem__icontains=sc.numero,
                    data_criacao__date=hoje
                ).first()
                
                if ultima_notificacao:
                    continue
                
                # Notifica solicitante
                self.criar_notificacao_sistema(
                    destinatario_usuario=sc.solicitante,
                    titulo=f"Lembrete: Material Necessário em {dias} Dia(s)",
                    mensagem=f"Sua SC {sc.numero} tem data necessária em {dias} dia(s). Status atual: {sc.get_status_display()}.",
                    link=reverse('materiais:visualizar_solicitacao', args=[sc.id])
                )
                
                # Notifica almoxarife
                self.criar_notificacao_sistema(
                    destinatario_perfil='almoxarife_escritorio',
                    titulo=f"Lembrete: Data Necessária Próxima",
                    mensagem=f"SC {sc.numero} precisa de material em {dias} dia(s). Status: {sc.get_status_display()}.",
                    link=reverse('materiais:visualizar_solicitacao', args=[sc.id])
                )
                
                # Notifica engenheiro se houver
                if sc.destino and sc.destino.engenheiro:
                    self.criar_notificacao_sistema(
                        destinatario_usuario=sc.destino.engenheiro,
                        titulo=f"Lembrete: Material em {dias} Dia(s)",
                        mensagem=f"SC {sc.numero} (obra {sc.destino.nome}) tem entrega prevista em {dias} dia(s).",
                        link=reverse('materiais:visualizar_solicitacao', args=[sc.id])
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Lembrete enviado: SC {sc.numero} ({dias} dias)'
                    )
                )
