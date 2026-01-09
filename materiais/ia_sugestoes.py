"""
Serviço de Sugestões Inteligentes de Fornecedores usando Gemini AI.
Analisa histórico e características para recomendar os melhores fornecedores.
"""
import google.generativeai as genai
from django.conf import settings
from django.db.models import Avg, Count, Q
from datetime import timedelta
from django.utils import timezone
from materiais.models import (
    Fornecedor, SolicitacaoCompra, Cotacao, EnvioCotacao, SugestaoIA
)


class SugestaoFornecedorIA:
    """Gera sugestões inteligentes de fornecedores usando Gemini AI"""
    
    def __init__(self):
        # Configura a API do Gemini
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            self.model = None
            print(f"⚠️ Gemini AI não configurado: {e}")
    
    def analisar_fornecedor(self, fornecedor):
        """
        Analisa o desempenho histórico de um fornecedor.
        
        Returns:
            dict: {
                'confiabilidade': float (0-100),
                'preco': float (0-100),
                'prazo': float (0-100),
                'detalhes': dict
            }
        """
        agora = timezone.now()
        seis_meses_atras = agora - timedelta(days=180)
        
        # Busca cotações dos últimos 6 meses
        cotacoes = Cotacao.objects.filter(
            fornecedor=fornecedor,
            data_registro__gte=seis_meses_atras
        )
        
        total_cotacoes = cotacoes.count()
        
        if total_cotacoes == 0:
            return {
                'confiabilidade': 50,  # Neutro para novos fornecedores
                'preco': 50,
                'prazo': 50,
                'detalhes': {
                    'total_cotacoes': 0,
                    'mensagem': 'Fornecedor novo, sem histórico'
                }
            }
        
        # === SCORE DE CONFIABILIDADE ===
        # Baseado em taxa de resposta e cumprimento de prazos
        envios_total = EnvioCotacao.objects.filter(
            fornecedor=fornecedor,
            data_envio__gte=seis_meses_atras
        ).count()
        
        taxa_resposta = (total_cotacoes / envios_total * 100) if envios_total > 0 else 0
        
        # Verifica cumprimento de prazos de resposta
        envios_respondidos = EnvioCotacao.objects.filter(
            fornecedor=fornecedor,
            status='respondido',
            data_envio__gte=seis_meses_atras
        )
        
        prazos_cumpridos = 0
        for envio in envios_respondidos:
            cotacao = envio.cotacoes_recebidas.first()
            if cotacao and envio.prazo_resposta:
                if cotacao.data_registro.date() <= envio.prazo_resposta:
                    prazos_cumpridos += 1
        
        taxa_cumprimento = (prazos_cumpridos / envios_respondidos.count() * 100) if envios_respondidos.count() > 0 else 50
        
        # Score de confiabilidade (média ponderada)
        score_confiabilidade = (taxa_resposta * 0.6 + taxa_cumprimento * 0.4)
        
        # === SCORE DE PREÇO ===
        # Compara com média de mercado
        cotacoes_aceitas = cotacoes.filter(
            Q(requisicao_material__isnull=False)  # Cotação vencedora
        )
        
        total_aceitas = cotacoes_aceitas.count()
        
        if total_aceitas > 0:
            # Fornecedor competitivo se ganhou muitas cotações
            taxa_vitoria = (total_aceitas / total_cotacoes) * 100
            score_preco = min(100, taxa_vitoria * 2)  # Multiplica por 2 para dar peso
        else:
            # Analisa se os preços são competitivos (compara com médias)
            valores_fornecedor = list(cotacoes.values_list('valor_total', flat=True))
            
            if valores_fornecedor:
                media_fornecedor = sum(valores_fornecedor) / len(valores_fornecedor)
                
                # Compara com média geral do mercado (todas cotações)
                media_mercado = Cotacao.objects.filter(
                    data_registro__gte=seis_meses_atras
                ).aggregate(Avg('valor_total'))['valor_total__avg'] or media_fornecedor
                
                # Score: quanto menor o preço em relação ao mercado, melhor
                if media_mercado > 0:
                    razao = float(media_fornecedor) / float(media_mercado)
                    score_preco = max(0, min(100, (2 - razao) * 50))  # Normaliza 0-100
                else:
                    score_preco = 50
            else:
                score_preco = 50
        
        # === SCORE DE PRAZO ===
        # Baseado em tempo médio de resposta
        tempos_resposta = []
        for envio in envios_respondidos:
            cotacao = envio.cotacoes_recebidas.first()
            if cotacao:
                tempo = (cotacao.data_registro - envio.data_envio).total_seconds() / 3600  # horas
                tempos_resposta.append(tempo)
        
        if tempos_resposta:
            tempo_medio = sum(tempos_resposta) / len(tempos_resposta)
            
            # Score: quanto mais rápido, melhor
            # 24h = 100, 168h (7 dias) = 0
            score_prazo = max(0, min(100, 100 - (tempo_medio / 168 * 100)))
        else:
            score_prazo = 50
        
        return {
            'confiabilidade': round(score_confiabilidade, 2),
            'preco': round(score_preco, 2),
            'prazo': round(score_prazo, 2),
            'detalhes': {
                'total_cotacoes': total_cotacoes,
                'total_vitorias': total_aceitas,
                'taxa_resposta': round(taxa_resposta, 1),
                'taxa_cumprimento_prazo': round(taxa_cumprimento, 1),
                'tempo_medio_resposta': round(sum(tempos_resposta) / len(tempos_resposta), 1) if tempos_resposta else None
            }
        }
    
    def gerar_sugestoes(self, solicitacao_id, top_n=5):
        """
        Gera sugestões de fornecedores para uma SC.
        
        Args:
            solicitacao_id: ID da SolicitacaoCompra
            top_n: Número de sugestões a retornar
            
        Returns:
            list: Lista de SugestaoIA ordenadas por score
        """
        try:
            sc = SolicitacaoCompra.objects.get(id=solicitacao_id)
        except SolicitacaoCompra.DoesNotExist:
            return []
        
        # Remove sugestões antigas
        SugestaoIA.objects.filter(solicitacao=sc).delete()
        
        # Busca fornecedores ativos
        fornecedores = Fornecedor.objects.filter(ativo=True)
        
        sugestoes = []
        
        for fornecedor in fornecedores:
            # Analisa histórico do fornecedor
            analise = self.analisar_fornecedor(fornecedor)
            
            # Calcula score total (média ponderada)
            score_total = (
                analise['confiabilidade'] * 0.4 +
                analise['preco'] * 0.35 +
                analise['prazo'] * 0.25
            )
            
            # Gera justificativa com IA (se disponível)
            justificativa = self._gerar_justificativa_ia(
                fornecedor, 
                sc, 
                analise
            )
            
            # Cria sugestão
            sugestao = SugestaoIA.objects.create(
                solicitacao=sc,
                fornecedor=fornecedor,
                score_confiabilidade=analise['confiabilidade'],
                score_preco=analise['preco'],
                score_prazo=analise['prazo'],
                score_total=score_total,
                justificativa=justificativa
            )
            
            sugestoes.append(sugestao)
        
        # Retorna top N ordenadas por score
        return sorted(sugestoes, key=lambda x: x.score_total, reverse=True)[:top_n]
    
    def _gerar_justificativa_ia(self, fornecedor, solicitacao, analise):
        """
        Usa Gemini AI para gerar justificativa humanizada.
        """
        if not self.model:
            return self._justificativa_padrao(analise)
        
        try:
            # Monta prompt para a IA
            prompt = f"""
Você é um assistente especializado em análise de fornecedores para construção civil.

FORNECEDOR: {fornecedor.nome_fantasia}
SOLICITAÇÃO: {solicitacao.nome_descritivo}
OBRA: {solicitacao.obra.nome}

ANÁLISE DE DESEMPENHO:
- Score de Confiabilidade: {analise['confiabilidade']:.1f}/100
- Score de Preço Competitivo: {analise['preco']:.1f}/100
- Score de Rapidez: {analise['prazo']:.1f}/100

DETALHES:
- Total de cotações: {analise['detalhes']['total_cotacoes']}
- Taxa de resposta: {analise['detalhes'].get('taxa_resposta', 0):.1f}%
- Taxa de cumprimento de prazo: {analise['detalhes'].get('taxa_cumprimento_prazo', 0):.1f}%

Gere uma justificativa CURTA (máximo 2 linhas) explicando por que este fornecedor é recomendado ou não para esta SC.
Seja objetivo, profissional e use dados concretos.
"""
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            print(f"⚠️ Erro ao gerar justificativa IA: {e}")
            return self._justificativa_padrao(analise)
    
    def _justificativa_padrao(self, analise):
        """Gera justificativa padrão sem IA"""
        detalhes = analise['detalhes']
        
        if detalhes['total_cotacoes'] == 0:
            return "Fornecedor novo no sistema, sem histórico de cotações anteriores."
        
        pontos = []
        
        if analise['confiabilidade'] >= 80:
            pontos.append(f"alta confiabilidade ({analise['confiabilidade']:.0f}/100)")
        elif analise['confiabilidade'] < 50:
            pontos.append(f"confiabilidade a melhorar ({analise['confiabilidade']:.0f}/100)")
        
        if analise['preco'] >= 70:
            pontos.append(f"preços competitivos ({detalhes.get('total_vitorias', 0)} vitórias)")
        
        if analise['prazo'] >= 80:
            pontos.append("respostas rápidas")
        
        if pontos:
            return f"Recomendado por: {', '.join(pontos)}. Total de {detalhes['total_cotacoes']} cotações nos últimos 6 meses."
        else:
            return f"Desempenho médio. {detalhes['total_cotacoes']} cotações nos últimos 6 meses."


# Instância global
sugestao_ia_service = SugestaoFornecedorIA()
