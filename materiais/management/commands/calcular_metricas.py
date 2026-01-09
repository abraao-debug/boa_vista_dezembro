"""
Comando de management para calcular métricas diárias de cotações.
Execução automática via APScheduler.

Uso manual: python manage.py calcular_metricas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Avg, Count, F, Q, Sum
from datetime import timedelta, datetime
from decimal import Decimal
from materiais.models import (
    SolicitacaoCompra, EnvioCotacao, Cotacao, MetricaCotacao, Fornecedor
)


class Command(BaseCommand):
    help = 'Calcula e armazena métricas diárias de desempenho de cotações'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data',
            type=str,
            help='Data específica para calcular (formato: YYYY-MM-DD)'
        )

    def handle(self, *args, **options):
        data_calculo = options.get('data')
        
        if data_calculo:
            try:
                data = datetime.strptime(data_calculo, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('❌ Formato de data inválido. Use YYYY-MM-DD'))
                return
        else:
            # Calcula métricas do dia anterior
            data = (timezone.now() - timedelta(days=1)).date()
        
        self.stdout.write(f'\n📊 Calculando métricas para {data.strftime("%d/%m/%Y")}...\n')
        
        # Verifica se já existem métricas para esta data
        metrica, criada = MetricaCotacao.objects.get_or_create(data=data)
        
        # Define o range de tempo para o dia
        inicio_dia = timezone.make_aware(datetime.combine(data, datetime.min.time()))
        fim_dia = timezone.make_aware(datetime.combine(data, datetime.max.time()))
        
        # === MÉTRICAS DE SCS ===
        metrica.total_scs_criadas = SolicitacaoCompra.objects.filter(
            data_criacao__range=(inicio_dia, fim_dia)
        ).count()
        
        metrica.total_scs_aprovadas = SolicitacaoCompra.objects.filter(
            data_aprovacao_diretor__range=(inicio_dia, fim_dia)
        ).count()
        
        metrica.total_scs_em_cotacao = SolicitacaoCompra.objects.filter(
            status='em_cotacao',
            data_criacao__lte=fim_dia
        ).count()
        
        metrica.total_scs_finalizadas = SolicitacaoCompra.objects.filter(
            status='finalizado',
            data_criacao__lte=fim_dia
        ).count()
        
        # === MÉTRICAS DE COTAÇÕES ===
        metrica.total_cotacoes_enviadas = EnvioCotacao.objects.filter(
            data_envio__range=(inicio_dia, fim_dia)
        ).count()
        
        metrica.total_cotacoes_recebidas = Cotacao.objects.filter(
            data_registro__range=(inicio_dia, fim_dia)
        ).count()
        
        # Cotações com prazo vencido (até a data de cálculo)
        metrica.total_cotacoes_vencidas = EnvioCotacao.objects.filter(
            status='aguardando',
            prazo_resposta__lt=data
        ).count()
        
        # === MÉTRICAS DE TEMPO ===
        # Tempo médio de aprovação (criação -> aprovação diretor)
        scs_aprovadas = SolicitacaoCompra.objects.filter(
            data_aprovacao_diretor__isnull=False,
            data_criacao__isnull=False
        ).annotate(
            tempo_aprovacao=F('data_aprovacao_diretor') - F('data_criacao')
        )
        
        if scs_aprovadas.exists():
            tempo_medio_segundos = sum(
                [sc.tempo_aprovacao.total_seconds() for sc in scs_aprovadas],
                0
            ) / scs_aprovadas.count()
            metrica.tempo_medio_aprovacao = tempo_medio_segundos / 3600  # Converte para horas
        
        # Tempo médio de cotação (envio -> resposta)
        cotacoes_respondidas = []
        for envio in EnvioCotacao.objects.filter(status='respondido'):
            cotacao = envio.cotacoes_recebidas.first()
            if cotacao and cotacao.data_registro:
                tempo = (cotacao.data_registro - envio.data_envio).total_seconds() / 3600
                cotacoes_respondidas.append(tempo)
        
        if cotacoes_respondidas:
            metrica.tempo_medio_resposta_fornecedor = sum(cotacoes_respondidas) / len(cotacoes_respondidas)
        
        # === MÉTRICAS DE FORNECEDORES ===
        total_envios = EnvioCotacao.objects.filter(data_envio__lte=fim_dia).count()
        total_respostas = EnvioCotacao.objects.filter(
            status='respondido',
            data_envio__lte=fim_dia
        ).count()
        
        if total_envios > 0:
            metrica.taxa_resposta_fornecedores = (total_respostas / total_envios) * 100
        
        # Top 5 fornecedores mais rápidos
        fornecedores_tempo = []
        for fornecedor in Fornecedor.objects.all():
            tempos = []
            for envio in fornecedor.cotacoes_enviadas.filter(status='respondido'):
                cotacao = envio.cotacoes_recebidas.first()
                if cotacao:
                    tempo = (cotacao.data_registro - envio.data_envio).total_seconds() / 3600
                    tempos.append(tempo)
            
            if tempos:
                tempo_medio = sum(tempos) / len(tempos)
                fornecedores_tempo.append({
                    'nome': fornecedor.nome_fantasia,
                    'tempo_medio': round(tempo_medio, 2),
                    'total_respostas': len(tempos)
                })
        
        # Ordena por tempo médio
        fornecedores_tempo.sort(key=lambda x: x['tempo_medio'])
        metrica.fornecedores_mais_rapidos = fornecedores_tempo[:5] if fornecedores_tempo else []
        metrica.fornecedores_mais_lentos = fornecedores_tempo[-5:][::-1] if len(fornecedores_tempo) > 5 else []
        
        # === MÉTRICAS DE VALORES ===
        cotacoes_dia = Cotacao.objects.filter(data_registro__range=(inicio_dia, fim_dia))
        
        if cotacoes_dia.exists():
            metrica.valor_total_cotado = cotacoes_dia.aggregate(
                total=Sum('valor_total')
            )['total'] or Decimal('0')
            
            metrica.valor_medio_cotacao = cotacoes_dia.aggregate(
                media=Avg('valor_total')
            )['media'] or Decimal('0')
        
        # Economia total (diferença entre maior e menor cotação aceita)
        economia = Decimal('0')
        for sc in SolicitacaoCompra.objects.filter(status='finalizado'):
            cotacoes_sc = sc.cotacoes.all()
            if cotacoes_sc.count() > 1:
                valores = [c.valor_total for c in cotacoes_sc]
                economia += max(valores) - min(valores)
        
        metrica.economia_total = economia
        
        # Salva métricas
        metrica.save()
        
        # === RELATÓRIO ===
        self.stdout.write(self.style.SUCCESS('\n✅ Métricas calculadas com sucesso!\n'))
        self.stdout.write(f'📅 Data: {data.strftime("%d/%m/%Y")}')
        self.stdout.write(f'\n📦 SOLICITAÇÕES DE COMPRA:')
        self.stdout.write(f'  • Criadas hoje: {metrica.total_scs_criadas}')
        self.stdout.write(f'  • Aprovadas hoje: {metrica.total_scs_aprovadas}')
        self.stdout.write(f'  • Em cotação: {metrica.total_scs_em_cotacao}')
        self.stdout.write(f'  • Finalizadas: {metrica.total_scs_finalizadas}')
        
        self.stdout.write(f'\n💰 COTAÇÕES:')
        self.stdout.write(f'  • Enviadas hoje: {metrica.total_cotacoes_enviadas}')
        self.stdout.write(f'  • Recebidas hoje: {metrica.total_cotacoes_recebidas}')
        self.stdout.write(f'  • Vencidas (total): {metrica.total_cotacoes_vencidas}')
        
        self.stdout.write(f'\n⏱️ TEMPO:')
        if metrica.tempo_medio_aprovacao:
            self.stdout.write(f'  • Aprovação média: {metrica.tempo_medio_aprovacao:.1f}h')
        if metrica.tempo_medio_resposta_fornecedor:
            self.stdout.write(f'  • Resposta fornecedor: {metrica.tempo_medio_resposta_fornecedor:.1f}h')
        
        self.stdout.write(f'\n👥 FORNECEDORES:')
        if metrica.taxa_resposta_fornecedores:
            self.stdout.write(f'  • Taxa de resposta: {metrica.taxa_resposta_fornecedores:.1f}%')
        
        if metrica.fornecedores_mais_rapidos:
            self.stdout.write(f'  • Mais rápidos:')
            for f in metrica.fornecedores_mais_rapidos[:3]:
                self.stdout.write(f'    - {f["nome"]}: {f["tempo_medio"]:.1f}h')
        
        self.stdout.write(f'\n💵 VALORES:')
        self.stdout.write(f'  • Total cotado hoje: R$ {metrica.valor_total_cotado:,.2f}')
        self.stdout.write(f'  • Média por cotação: R$ {metrica.valor_medio_cotacao:,.2f}')
        self.stdout.write(f'  • Economia total: R$ {metrica.economia_total:,.2f}')
        
        self.stdout.write(f'\n🎯 Status: {"Nova métrica criada" if criada else "Métrica atualizada"}\n')
