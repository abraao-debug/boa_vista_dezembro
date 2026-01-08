from django.core.management.base import BaseCommand
from materiais.models import Cotacao
import re


class Command(BaseCommand):
    help = 'Corrige as formas de pagamento nas cotações existentes'

    def handle(self, *args, **options):
        # Mapeamento de códigos para nomes formatados
        formas_pagamento_dict = {
            'AVISTA': 'À Vista',
            'PIX': 'Pix',
            'BOLETO': 'Boleto Bancário',
            'CARTAO_CREDITO': 'Cartão de Crédito',
            'CARTAO_DEBITO': 'Cartão de Débito',
            'TRANSFERENCIA': 'Transferência Bancária',
            'A_NEGOCIAR': 'A Negociar',
            'CARTAO': 'Cartão de Crédito',  # Valor antigo
        }

        cotacoes_atualizadas = 0
        
        # Busca todas as cotações que NÃO são "Atende"
        cotacoes = Cotacao.objects.exclude(condicao_pagamento='Atende')
        
        for cotacao in cotacoes:
            condicao_atual = cotacao.condicao_pagamento
            
            if not condicao_atual or condicao_atual == 'Atende':
                continue
            
            # Extrai o código e os dias usando regex
            # Exemplo: "CARTAO_CREDITO - 15 dias" -> grupos: ("CARTAO_CREDITO", "15")
            match = re.match(r'^([A-Z_]+)\s*-\s*(\d+)\s*dias?$', condicao_atual, re.IGNORECASE)
            
            if match:
                codigo_antigo = match.group(1).upper()
                dias = match.group(2)
                
                # Busca o nome formatado no dicionário
                if codigo_antigo in formas_pagamento_dict:
                    novo_valor = f"{formas_pagamento_dict[codigo_antigo]} - {dias} dias"
                    
                    if novo_valor != condicao_atual:
                        cotacao.condicao_pagamento = novo_valor
                        cotacao.save()
                        cotacoes_atualizadas += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Cotação {cotacao.id}: "{condicao_atual}" → "{novo_valor}"'
                            )
                        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Concluído! {cotacoes_atualizadas} cotações atualizadas.'
            )
        )
