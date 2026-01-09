"""
Script para testar notificações e diagnosticar problemas.
Executar: python testar_notificacoes.py
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_obra.settings')
django.setup()

from materiais.models import Notificacao, User, SolicitacaoCompra
from materiais.views import criar_notificacao_sistema
from django.utils import timezone

print("=" * 70)
print("🔔 DIAGNÓSTICO DO SISTEMA DE NOTIFICAÇÕES")
print("=" * 70)

# 1. Verificar usuários
print("\n📋 USUÁRIOS NO SISTEMA:")
usuarios = User.objects.all()
for u in usuarios:
    print(f"  • {u.username} ({u.get_perfil_display()}) - {'Ativo' if u.is_active else 'Inativo'}")

# 2. Verificar notificações existentes
print("\n🔔 NOTIFICAÇÕES NO BANCO:")
total = Notificacao.objects.count()
nao_lidas = Notificacao.objects.filter(lida=False).count()
print(f"  • Total: {total}")
print(f"  • Não lidas: {nao_lidas}")

if total > 0:
    print("\n📬 ÚLTIMAS 10 NOTIFICAÇÕES:")
    for n in Notificacao.objects.all()[:10]:
        status = "🔴 Não lida" if not n.lida else "✅ Lida"
        print(f"  {status} | {n.usuario_destino.username} | {n.titulo}")
        print(f"           {n.mensagem[:60]}...")
        print(f"           {n.data_criacao.strftime('%d/%m/%Y %H:%M')}\n")

# 3. Verificar SCs pendentes que deveriam gerar notificações
print("\n📊 SOLICITAÇÕES DE COMPRA (que geram notificações):")
scs_pendentes = SolicitacaoCompra.objects.filter(status='pendente').count()
scs_aprovadas = SolicitacaoCompra.objects.filter(status='aprovada').count()
scs_cotacao = SolicitacaoCompra.objects.filter(status__in=['aguardando_resposta', 'cotacao']).count()
print(f"  • Pendentes (aguardando aprovação): {scs_pendentes}")
print(f"  • Aprovadas (aguardando cotação): {scs_aprovadas}")
print(f"  • Em cotação: {scs_cotacao}")

# 4. Teste de criação de notificação
print("\n🧪 TESTANDO CRIAÇÃO DE NOTIFICAÇÃO...")
usuario_teste = User.objects.first()
if usuario_teste:
    try:
        criar_notificacao_sistema(
            destinatario_usuario=usuario_teste,
            titulo="🧪 Teste de Notificação",
            mensagem=f"Esta é uma notificação de teste criada em {timezone.now().strftime('%d/%m/%Y %H:%M')}",
            link="/dashboard/"
        )
        print(f"  ✅ Notificação de teste criada para {usuario_teste.username}")
        
        # Verificar se foi criada
        notif_teste = Notificacao.objects.filter(
            usuario_destino=usuario_teste,
            titulo__contains="Teste"
        ).first()
        
        if notif_teste:
            print(f"  ✅ Notificação confirmada no banco: ID {notif_teste.id}")
        else:
            print(f"  ❌ Notificação NÃO encontrada no banco!")
            
    except Exception as e:
        print(f"  ❌ Erro ao criar notificação: {e}")
else:
    print("  ⚠️  Nenhum usuário encontrado para teste")

# 5. Verificar context processor
print("\n⚙️  VERIFICANDO CONTEXT PROCESSOR:")
from materiais.context_processors import notificacoes_globais

class FakeRequest:
    def __init__(self, user):
        self.user = user

if usuario_teste:
    fake_req = FakeRequest(usuario_teste)
    context = notificacoes_globais(fake_req)
    print(f"  • Notificações no contexto: {context['notificacoes_count']}")
    print(f"  • Recentes no contexto: {len(context['notificacoes_recentes'])}")
    
    if context['notificacoes_recentes']:
        print(f"\n  📬 NOTIFICAÇÕES QUE APARECEM NO SINO:")
        for n in context['notificacoes_recentes']:
            print(f"    • {n.titulo}")

print("\n" + "=" * 70)
print("✅ DIAGNÓSTICO CONCLUÍDO")
print("=" * 70)
print("\n💡 DICAS:")
print("  1. Se não há notificações, execute ações que as criam:")
print("     - Criar uma SC (diretor recebe notificação)")
print("     - Aprovar uma SC (solicitante e almoxarife recebem)")
print("     - Enviar cotação (almoxarife recebe)")
print("  2. O sino só mostra notificações NÃO LIDAS")
print("  3. As notificações aparecem imediatamente (sem precisar do scheduler)")
print("  4. O scheduler (08:00) apenas verifica pendências antigas\n")
