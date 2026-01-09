#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para verificar e popular mensagens personalizadas"""

import os
import sys
import django

# Configura o Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_obra.settings')
django.setup()

from materiais.models import MensagemPersonalizada

# Verifica quantas mensagens existem
count = MensagemPersonalizada.objects.count()
print(f"\n📊 Atualmente existem {count} mensagens no banco de dados\n")

if count > 0:
    print("Mensagens existentes:")
    for msg in MensagemPersonalizada.objects.all().order_by('categoria', 'tipo'):
        print(f"  • [{msg.categoria}] {msg.get_tipo_display()}")
    print()

# Se tiver menos de 17, vamos popular
if count < 17:
    print("🔧 Populando banco com as 17 mensagens padrão...\n")
    
    templates_padrao = [
        # NOTIFICAÇÕES INTERNAS (10)
        {'tipo': 'sc_criada_diretor', 'categoria': 'notificacao_interna', 'assunto': '', 
         'corpo': 'Nova SC {numero_sc} criada por {solicitante} para aprovação.\nObra: {obra}\nJustificativa: {justificativa}',
         'variaveis_disponiveis': '{numero_sc}, {solicitante}, {obra}, {justificativa}'},
        
        {'tipo': 'sc_aprovada_escritorio', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': 'SC {numero_sc} foi aprovada e está pronta para cotação.\nObra: {obra}\nItens: {quantidade_itens}',
         'variaveis_disponiveis': '{numero_sc}, {obra}, {quantidade_itens}'},
        
        {'tipo': 'sc_editada_escritorio', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': 'Sua SC {numero_sc} foi editada por {editor}.\nObra: {obra}',
         'variaveis_disponiveis': '{numero_sc}, {editor}, {obra}'},
        
        {'tipo': 'cotacao_recebida_almoxarife', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': 'Fornecedor {fornecedor} respondeu a SC {numero_sc}.\nTotal: R$ {valor_total}',
         'variaveis_disponiveis': '{fornecedor}, {numero_sc}, {valor_total}'},
        
        {'tipo': 'cotacao_atualizada', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': '{fornecedor} atualizou sua cotação para SC {numero_sc}.\nNovo total: R$ {valor_total}',
         'variaveis_disponiveis': '{fornecedor}, {numero_sc}, {valor_total}'},
        
        {'tipo': 'cotacao_excluida', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': '{fornecedor} removeu sua cotação da SC {numero_sc}.',
         'variaveis_disponiveis': '{fornecedor}, {numero_sc}'},
        
        {'tipo': 'rm_aprovada_solicitante', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': 'Sua RM {numero_rm} foi aprovada e está pronta para retirada.\nLocal: {destino}\nItens: {quantidade_itens}',
         'variaveis_disponiveis': '{numero_rm}, {destino}, {quantidade_itens}'},
        
        {'tipo': 'recebimento_registrado', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': 'Recebimento parcial registrado para RM {numero_rm}.\nRecebido por: {recebedor}',
         'variaveis_disponiveis': '{numero_rm}, {recebedor}'},
        
        {'tipo': 'lembrete_cotacao_pendente', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': 'Lembrete: Cotação pendente para SC {numero_sc}.\nPrazo: {prazo_resposta}',
         'variaveis_disponiveis': '{numero_sc}, {prazo_resposta}'},
        
        {'tipo': 'fornecedor_visualizou_portal', 'categoria': 'notificacao_interna', 'assunto': '',
         'corpo': '{fornecedor} acessou o portal de cotações.',
         'variaveis_disponiveis': '{fornecedor}'},
        
        # E-MAILS PARA FORNECEDORES (5)
        {'tipo': 'email_convite_cotacao', 'categoria': 'email_fornecedor', 
         'assunto': 'Solicitação de Cotação - SC {numero_sc}',
         'corpo': '''Prezado(a) {fornecedor},

A Boa Vista Construtora convida sua empresa a participar da cotação referente à SC {numero_sc}.

Obra: {obra}
Prazo de Entrega: {prazo_entrega}
Forma de Pagamento: {forma_pagamento}

Por favor, responda até {prazo_resposta}.

Acesse o portal: {link_portal}

Atenciosamente,
Departamento de Compras
Boa Vista Construtora''',
         'variaveis_disponiveis': '{fornecedor}, {numero_sc}, {obra}, {prazo_entrega}, {forma_pagamento}, {prazo_resposta}, {link_portal}'},
        
        {'tipo': 'email_lembrete_cotacao', 'categoria': 'email_fornecedor',
         'assunto': 'Lembrete - Cotação Pendente SC {numero_sc}',
         'corpo': '''Prezado(a) {fornecedor},

Este é um lembrete sobre a cotação pendente da SC {numero_sc}.

Prazo final: {prazo_resposta}

Por favor, responda o mais breve possível através do portal.

Atenciosamente,
Departamento de Compras''',
         'variaveis_disponiveis': '{fornecedor}, {numero_sc}, {prazo_resposta}'},
        
        {'tipo': 'email_cotacao_aprovada', 'categoria': 'email_fornecedor',
         'assunto': 'Parabéns! Sua Cotação foi Aprovada - SC {numero_sc}',
         'corpo': '''Prezado(a) {fornecedor},

Informamos que sua cotação para a SC {numero_sc} foi APROVADA!

Valor Total: R$ {valor_total}
Obra: {obra}

Em breve entraremos em contato com a Requisição de Material (RM) oficial.

Atenciosamente,
Departamento de Compras''',
         'variaveis_disponiveis': '{fornecedor}, {numero_sc}, {valor_total}, {obra}'},
        
        {'tipo': 'email_cotacao_rejeitada', 'categoria': 'email_fornecedor',
         'assunto': 'Cotação Não Aprovada - SC {numero_sc}',
         'corpo': '''Prezado(a) {fornecedor},

Informamos que sua cotação para a SC {numero_sc} não foi selecionada desta vez.

Motivo: {motivo}

Agradecemos sua participação e esperamos contar com você em futuras oportunidades.

Atenciosamente,
Departamento de Compras''',
         'variaveis_disponiveis': '{fornecedor}, {numero_sc}, {motivo}'},
        
        {'tipo': 'email_rm_enviada', 'categoria': 'email_fornecedor',
         'assunto': 'Requisição de Material - RM {numero_rm}',
         'corpo': '''Prezado(a) {fornecedor},

Segue Requisição de Material RM {numero_rm}.

Obra: {obra}
Total: R$ {valor_total}
Prazo de Entrega: {prazo_entrega}

O documento completo está em anexo.

Atenciosamente,
Departamento de Compras''',
         'variaveis_disponiveis': '{fornecedor}, {numero_rm}, {obra}, {valor_total}, {prazo_entrega}'},
        
        # E-MAILS PARA USUÁRIOS (2)
        {'tipo': 'email_sc_rejeitada', 'categoria': 'email_usuario',
         'assunto': 'SC {numero_sc} foi Rejeitada',
         'corpo': '''Prezado(a) {solicitante},

Sua Solicitação de Compra {numero_sc} foi REJEITADA pela diretoria.

Motivo: {motivo}

Por favor, revise e crie uma nova solicitação se necessário.

Atenciosamente,
Sistema de Gestão de Obras''',
         'variaveis_disponiveis': '{solicitante}, {numero_sc}, {motivo}'},
        
        {'tipo': 'email_rm_aprovada', 'categoria': 'email_usuario',
         'assunto': 'RM {numero_rm} Aprovada e Disponível',
         'corpo': '''Prezado(a) {solicitante},

Sua Requisição de Material {numero_rm} foi aprovada e está disponível para retirada.

Local: {destino}
Fornecedor: {fornecedor}
Itens: {quantidade_itens}

Apresente este documento no momento da retirada.

Atenciosamente,
Departamento de Compras''',
         'variaveis_disponiveis': '{solicitante}, {numero_rm}, {destino}, {fornecedor}, {quantidade_itens}'},
    ]
    
    criadas = 0
    atualizadas = 0
    erros = 0
    
    for template in templates_padrao:
        try:
            obj, created = MensagemPersonalizada.objects.update_or_create(
                tipo=template['tipo'],
                defaults={
                    'categoria': template['categoria'],
                    'assunto': template['assunto'],
                    'corpo': template['corpo'],
                    'variaveis_disponiveis': template['variaveis_disponiveis'],
                }
            )
            if created:
                criadas += 1
                print(f'  ✓ Criada: {obj.get_tipo_display()}')
            else:
                atualizadas += 1
                print(f'  ↻ Atualizada: {obj.get_tipo_display()}')
        except Exception as e:
            erros += 1
            print(f'  ✗ Erro em {template["tipo"]}: {str(e)}')
    
    total = MensagemPersonalizada.objects.count()
    print(f'\n{"="*70}')
    print(f'✅ Concluído!')
    print(f'   • Criadas: {criadas}')
    print(f'   • Atualizadas: {atualizadas}')
    print(f'   • Erros: {erros}')
    print(f'   • Total no sistema: {total} mensagens')
    print(f'{"="*70}\n')
    
    if total == 17:
        print("✨ Perfeito! Todas as 17 mensagens estão no banco.")
        print("Agora você pode acessar /gerenciar-mensagens/ e elas aparecerão.\n")
else:
    print("✅ Já existem 17 mensagens. Banco está completo!\n")
