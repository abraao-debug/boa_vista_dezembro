from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q, Sum, F, DecimalField, Prefetch
from django.core.paginator import EmptyPage, PageNotAnInteger 
from django.db.models.functions import Coalesce
from django.views.decorators.csrf import csrf_exempt
from difflib import SequenceMatcher
from django.core.paginator import Paginator
from .forms import SolicitacaoCompraForm
from django.db.models import Case, When, Value, IntegerField
from decimal import Decimal
from . import rm_config
import numpy as np
from .models import (
    NotificacaoFornecedor, User, SolicitacaoCompra, ItemSolicitacao, Fornecedor, ItemCatalogo, 
    Obra, Cotacao, RequisicaoMaterial, HistoricoSolicitacao, 
    ItemCotacao, CategoriaSC, EnvioCotacao, CategoriaItem, Tag, UnidadeMedida, DestinoEntrega,
    Recebimento, ItemRecebido, NotificacaoFornecedor # <-- NOVOS MODELOS PRESENTES
)
import json # Adicione esta importação no topo do seu arquivo views.py
from django.db import transaction
from django.urls import reverse

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from . import rm_config
from django.core.mail import send_mail
from django.conf import settings

#solicitacao = SolicitacaoCompra.objects.create(...)cadastrar_itens
def similaridade_texto(a, b):  
    """Calcula similaridade entre dois textos (0 a 1)"""  
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('materiais:dashboard')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    return render(request, 'materiais/login.html')


def logout_view(request):
    logout(request)
    return redirect('materiais:login')


@login_required
def dashboard(request):
    perfil = request.user.perfil

    # --- PASSO 4: REDIRECIONAMENTO IMEDIATO ---
    # Se for fornecedor, sai da função antes de processar as queries de obras
    if perfil == 'fornecedor':
        return redirect('materiais:dashboard_fornecedor')

    user_obras = request.user.obras.all()
    
    # --- LÓGICA DE FILTRAGEM CORRIGIDA ---
    if perfil == 'diretor':
        base_query = SolicitacaoCompra.objects.all()
    elif perfil in ['almoxarife_escritorio', 'engenheiro', 'almoxarife_obra']:
        if user_obras.exists():
            base_query = SolicitacaoCompra.objects.filter(obra__in=user_obras)
        else:
            base_query = SolicitacaoCompra.objects.none()
    else:
        base_query = SolicitacaoCompra.objects.none()

    aprovado_statuses = ['aprovada', 'aprovado_engenharia']
    cotacao_statuses = ['em_cotacao', 'aguardando_resposta', 'cotacao_selecionada']
    
    context = {
        'em_aberto': base_query.filter(status='pendente_aprovacao').count(),
        'aprovado': base_query.filter(status__in=aprovado_statuses).count(),
        'em_cotacao': base_query.filter(status__in=cotacao_statuses).count(),
        'requisicoes': base_query.filter(status='finalizada').count(),
        'a_caminho': base_query.filter(status__in=['a_caminho', 'recebida_parcial']).count(),
        'entregue': base_query.filter(status='recebida').count(),
    }

    # Renderização baseada no perfil
    if perfil == 'almoxarife_obra':
        return render(request, 'materiais/dashboard_almoxarife_obra.html', context)
    elif perfil == 'engenheiro':
        return render(request, 'materiais/dashboard_engenheiro.html', context)
    elif perfil == 'almoxarife_escritorio':
        return render(request, 'materiais/dashboard_almoxarife_escritorio.html', context)
    elif perfil == 'diretor':
        return render(request, 'materiais/dashboard_diretor.html', context)
    else:
        return render(request, 'materiais/dashboard.html', context)

@login_required
def lista_solicitacoes(request):
    status_filtrado = request.GET.get('status', None)
    user = request.user
    
    # --- LÓGICA DE FILTRAGEM CORRIGIDA (IDÊNTICA À DO DASHBOARD) ---
    if user.perfil == 'diretor':
        base_query = SolicitacaoCompra.objects.all()
    
    elif user.perfil in ['almoxarife_escritorio', 'almoxarife_obra', 'engenheiro']:
        user_obras = user.obras.all()
        if user_obras.exists():
            base_query = SolicitacaoCompra.objects.filter(obra__in=user_obras)
        else:
            base_query = SolicitacaoCompra.objects.none()
            
    else:
        base_query = SolicitacaoCompra.objects.none()

    # Aplica o filtro de status (se houver) na query base
    solicitacoes = base_query
    if status_filtrado:
        if status_filtrado == 'aprovada':
            aprovado_statuses = ['aprovada', 'aprovado_engenharia']
            solicitacoes = solicitacoes.filter(status__in=aprovado_statuses)
        
        elif status_filtrado == 'em_cotacao':
            cotacao_statuses = ['em_cotacao', 'aguardando_resposta', 'cotacao_selecionada']
            solicitacoes = solicitacoes.filter(status__in=cotacao_statuses)
            
        # Adiciona o filtro para o card "A Caminho" incluir os parciais
        elif status_filtrado == 'a_caminho':
            solicitacoes = solicitacoes.filter(status__in=['a_caminho', 'recebida_parcial'])
            
        else:
            solicitacoes = solicitacoes.filter(status=status_filtrado)

    # Monta o contexto final para o template
    context = {
        'solicitacoes': solicitacoes.select_related('obra').prefetch_related('requisicao').order_by('-data_criacao'),
        'status_filtrado': status_filtrado,
        'status_choices': dict(SolicitacaoCompra.STATUS_CHOICES)
    }
    return render(request, 'materiais/lista_solicitacoes.html', context)

@login_required
def minhas_solicitacoes(request):
    # --- Toda a sua lógica de filtros e ordenação continua a mesma ---
    termo_busca = request.GET.get('q', '').strip()
    ano = request.GET.get('ano', '')
    mes = request.GET.get('mes', '')
    categoria_id = request.GET.get('categoria', '')
    sort_by = request.GET.get('sort', 'data_criacao')
    direction = request.GET.get('dir', 'desc')

    base_query = SolicitacaoCompra.objects.filter(solicitante=request.user)
    # ... (filtros Q(...) para busca) ...
    if termo_busca:
        base_query = base_query.filter(
            Q(numero__icontains=termo_busca) | Q(nome_descritivo__icontains=termo_busca) |
            Q(itens__descricao__icontains=termo_busca) | Q(obra__nome__icontains=termo_busca)
        ).distinct()
    if ano: base_query = base_query.filter(data_criacao__year=ano)
    if mes: base_query = base_query.filter(data_criacao__month=mes)
    if categoria_id: base_query = base_query.filter(categoria_sc_id=categoria_id)

    # ... (lógica de anotação e ordenação) ...
    base_query = base_query.annotate(item_count=Count('itens'))
    status_order = Case(*[When(status=s[0], then=Value(i)) for i, s in enumerate(SolicitacaoCompra.STATUS_CHOICES)], output_field=IntegerField())
    base_query = base_query.annotate(status_order=status_order)
    valid_sort_fields = {'codigo': 'numero', 'obra': 'obra__nome', 'data_criacao': 'data_criacao', 'status': 'status_order', 'itens': 'item_count'}
    order_field = valid_sort_fields.get(sort_by, 'data_criacao')
    order = f'-{order_field}' if direction == 'desc' else order_field
    solicitacoes_list = base_query.select_related('obra').order_by(order)

    # --- INÍCIO DA LÓGICA DE PAGINAÇÃO ---
    per_page = request.GET.get('per_page', 10) # Padrão de 10 itens por página
    paginator = Paginator(solicitacoes_list, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # --- FIM DA LÓGICA DE PAGINAÇÃO ---

    context = {
        'solicitacoes': page_obj, # IMPORTANTE: Enviamos o objeto da página, não mais a lista completa
        'per_page': per_page,
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'meses_opcoes': range(1, 13),
        'filtros_aplicados': { 'q': termo_busca, 'ano': ano, 'mes': mes, 'categoria': categoria_id, },
        'current_sort': sort_by,
        'current_dir': direction,
    }
    
    return render(request, 'materiais/minhas_solicitacoes.html', context)


@login_required
def nova_solicitacao(request):
    if request.method == 'POST':
        try:
            obra_id = request.POST.get('obra')
            data_necessidade = request.POST.get('data_necessidade')
            justificativa = request.POST.get('justificativa')
            is_emergencial = request.POST.get('is_emergencial') == 'on'
            categoria_sc_id = request.POST.get('categoria_sc')
            destino_id = request.POST.get('destino') # Captura o novo campo
            
            itens_json = request.POST.get('itens_json', '[]')
            itens_data = json.loads(itens_json)

            if not all([obra_id, data_necessidade, itens_data]):
                messages.error(request, 'Erro: Obra, data de necessidade e ao menos um item são obrigatórios.')
                return redirect('materiais:nova_solicitacao')

            obra = get_object_or_404(Obra, id=obra_id)
            status_inicial = 'aprovada' if request.user.perfil in ['engenheiro', 'almoxarife_escritorio', 'diretor'] else 'pendente_aprovacao'

            with transaction.atomic():
                solicitacao = SolicitacaoCompra.objects.create(
                    solicitante=request.user, obra=obra, data_necessidade=data_necessidade,
                    justificativa=justificativa, is_emergencial=is_emergencial,
                    status=status_inicial, categoria_sc_id=categoria_sc_id,
                    destino_id=destino_id if destino_id else None # Salva o novo campo
                )
                HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="Solicitação Criada")

                for item_data in itens_data:
                    item_catalogo = get_object_or_404(ItemCatalogo, id=item_data.get('item_id'))
                    ItemSolicitacao.objects.create(
                        solicitacao=solicitacao,
                        item_catalogo=item_catalogo,
                        descricao=item_catalogo.descricao,
                        unidade=item_catalogo.unidade.sigla,
                        categoria=str(item_catalogo.categoria),
                        quantidade=float(item_data.get('quantidade')),
                        observacoes=item_data.get('observacao')
                    )
                
                if request.user.perfil in ['engenheiro', 'almoxarife_escritorio']:
                    solicitacao.aprovador = request.user
                    solicitacao.data_aprovacao = timezone.now()
                    solicitacao.save()
                    HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="Aprovada na Criação")
                
                messages.success(request, f'Solicitação {solicitacao.numero} criada com sucesso!')
                return redirect('materiais:lista_solicitacoes')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao processar sua solicitação: {e}')
            return redirect('materiais:nova_solicitacao')

    if request.user.perfil == 'almoxarife_escritorio':
        obras = Obra.objects.filter(ativa=True).order_by('nome')
    else:
        obras = request.user.obras.filter(ativa=True).order_by('nome')
    
    context = {
        'obras': obras,
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'categorias_principais': CategoriaItem.objects.filter(categoria_mae__isnull=True).order_by('nome'),
    }
    
    return render(request, 'materiais/nova_solicitacao.html', context)
#solicitacao.save()
@login_required
def lista_fornecedores(request):
    return render(request, 'materiais/lista_fornecedores.html')


@login_required
def analisar_solicitacoes(request):
    if request.user.perfil != 'engenheiro':
        messages.error(request, 'Acesso negado. Apenas engenheiros podem analisar solicitações.')
        return redirect('materiais:dashboard')

    solicitacoes_pendentes = SolicitacaoCompra.objects.filter(
        status='pendente_aprovacao'
    ).order_by('-data_criacao')

    return render(request, 'materiais/analisar_solicitacoes.html', {
        'solicitacoes_pendentes': solicitacoes_pendentes
    })


@login_required
def aprovar_solicitacao(request, solicitacao_id):
    if request.user.perfil != 'engenheiro':
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    
    if solicitacao.status != 'pendente_aprovacao':
        return JsonResponse({'success': False, 'message': 'Solicitação não pode ser aprovada'})
    
    # --- MUDANÇA PARA O NOVO STATUS ---
    solicitacao.status = 'aprovado_engenharia'
    solicitacao.aprovador = request.user
    solicitacao.data_aprovacao = timezone.now()
    solicitacao.save()
    
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="Aprovada pelo Engenheiro",
        detalhes="Todos os itens foram aprovados."
    )
    
    messages.success(request, f'Solicitação {solicitacao.numero} aprovada com sucesso!')
    return JsonResponse({'success': True, 'message': 'Solicitação aprovada!'})

@login_required
def rejeitar_solicitacao(request, solicitacao_id):
    if request.user.perfil != 'engenheiro':
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    
    if solicitacao.status != 'pendente_aprovacao':
        return JsonResponse({'success': False, 'message': 'Solicitação não pode ser rejeitada'})
    
    solicitacao.status = 'rejeitada'
    solicitacao.aprovador = request.user
    solicitacao.data_aprovacao = timezone.now()
    
    observacoes = request.POST.get('observacoes', 'Rejeitada pelo engenheiro')
    solicitacao.observacoes_aprovacao = observacoes
    solicitacao.save()
    
    # --- REGISTRO DE HISTÓRICO ---
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="Solicitação Rejeitada",
        detalhes=observacoes
    )
    # --- FIM DO REGISTRO ---
    
    messages.success(request, f'Solicitação {solicitacao.numero} rejeitada!')
    return JsonResponse({'success': True, 'message': 'Solicitação rejeitada!'})

    
@login_required
def editar_solicitacao(request, solicitacao_id):
    # View placeholder para a futura tela de edição.
    # No momento, ela apenas exibe uma mensagem e redireciona.
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    messages.info(request, f'A funcionalidade "Editar" para a SC {solicitacao.numero} está em desenvolvimento.')
    
    # Redireciona de volta para a página mais relevante
    if request.user.perfil == 'almoxarife_escritorio':
        return redirect('materiais:gerenciar_cotacoes')
    
 

from datetime import datetime


from datetime import datetime
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import SolicitacaoCompra, Fornecedor, EnvioCotacao, Cotacao, ItemCotacao, HistoricoSolicitacao, Obra

@login_required
def iniciar_cotacao(request, solicitacao_id, fornecedor_id=None):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
        
    solicitacao = get_object_or_404(SolicitacaoCompra.objects.select_related('obra', 'destino'), id=solicitacao_id)
    fornecedor_selecionado = get_object_or_404(Fornecedor, id=fornecedor_id)
    envio_original = EnvioCotacao.objects.filter(solicitacao=solicitacao, fornecedor=fornecedor_selecionado).first()

    if request.method == 'POST':
        # --- 1. PROCESSAMENTO DE PRAZO ---
        aceita_prazo = request.POST.get('aceita_prazo')
        if aceita_prazo == 'sim':
            prazo_final = "Atende"
            motivo_prazo = "Dentro do prazo solicitado"
        else:
            data_raw = request.POST.get('prazo_entrega_data')
            prazo_final = datetime.strptime(data_raw, '%Y-%m-%d').strftime('%d/%m/%Y') if data_raw else "Não informado"
            motivo_prazo = request.POST.get('motivo_divergencia_prazo')
            if motivo_prazo == "Outro":
                motivo_prazo = request.POST.get('outro_motivo_prazo')

        # --- 2. PROCESSAMENTO DE PAGAMENTO ---
        aceita_pgto = request.POST.get('aceita_pagamento')
        if aceita_pgto == 'sim':
            pgto_final = "Atende"
            motivo_pgto = "Conforme solicitado"
        else:
            forma_codigo = request.POST.get('nova_forma_pagamento', '')
            dias = request.POST.get('novo_prazo_dias', '0')
            
            # Mapeamento de códigos para nomes formatados
            formas_pagamento_dict = {
                'avista': 'À Vista',
                'pix': 'Pix',
                'boleto': 'Boleto Bancário',
                'cartao_credito': 'Cartão de Crédito',
                'cartao_debito': 'Cartão de Débito',
                'transferencia': 'Transferência Bancária',
                'a_negociar': 'A Negociar',
            }
            
            forma_nome = formas_pagamento_dict.get(forma_codigo, forma_codigo.upper())
            pgto_final = f"{forma_nome} - {dias} dias"
            motivo_pgto = request.POST.get('motivo_divergencia_pagamento')
            if motivo_pgto == "Outro":
                motivo_pgto = request.POST.get('outro_motivo_pagamento')

        # --- 3. ENDEREÇO DE ENTREGA (CORREÇÃO DE CHAVE ESTRANGEIRA) ---
        endereco_id_raw = request.POST.get('endereco_entrega')
        if not endereco_id_raw or str(endereco_id_raw).strip() == "":
            # Se não foi fornecido, usa destino se existir, senão usa a própria obra
            endereco_id = solicitacao.destino_id if solicitacao.destino_id else solicitacao.obra_id
        else:
            try:
                endereco_id = int(endereco_id_raw)
            except (ValueError, TypeError):
                endereco_id = solicitacao.destino_id if solicitacao.destino_id else solicitacao.obra_id

        # --- 4. CÁLCULO DE CONFORMIDADE (SEMÁFORO) ---
        conf = 'verde'
        # Verifica se o endereço de entrega é diferente do solicitado
        endereco_solicitado_id = solicitacao.destino_id if solicitacao.destino_id else solicitacao.obra_id
        endereco_divergente = (endereco_id != endereco_solicitado_id)
        
        # VERMELHO: prazo divergente OU endereço divergente (urgência alta)
        if aceita_prazo == 'nao' or endereco_divergente:
            conf = 'vermelho'
        # AMARELO: apenas pagamento divergente (comercial)
        elif aceita_pgto == 'nao':
            conf = 'amarelo'

        valor_frete_str = request.POST.get('valor_frete', '0').replace('.', '').replace(',', '.')

        try:
            with transaction.atomic():
                nova_cotacao, created = Cotacao.objects.update_or_create(
                    solicitacao=solicitacao, 
                    fornecedor=fornecedor_selecionado, 
                    defaults={
                        'prazo_entrega': prazo_final,
                        'condicao_pagamento': pgto_final, 
                        'valor_frete': float(valor_frete_str) if valor_frete_str else 0.0,
                        'endereco_entrega_id': endereco_id, 
                        'conformidade': conf,
                        'motivo_divergencia_prazo': motivo_prazo,
                        'motivo_divergencia_pagamento': motivo_pgto,
                        'observacoes': request.POST.get('observacoes'),
                        'origem': 'manual',
                        'registrado_por': request.user,
                        'data_registro': datetime.now()
                    }
                )

                nova_cotacao.itens_cotados.all().delete()
                itens_count = 0
                base_itens = envio_original.itens.all() if envio_original else solicitacao.itens.all()
                
                for item_sol in base_itens:
                    preco_raw = request.POST.get(f'preco_{item_sol.id}')
                    if preco_raw:
                        preco_limpo = preco_raw.replace('R$', '').strip().replace('.', '').replace(',', '.')
                        ItemCotacao.objects.create(cotacao=nova_cotacao, item_solicitacao=item_sol, preco=float(preco_limpo))
                        itens_count += 1
                
                if itens_count == 0:
                    raise ValueError("Nenhum preço válido informado.")

                if solicitacao.status in ['aprovada', 'aprovado_engenharia']:
                    solicitacao.status = 'aguardando_resposta'
                    solicitacao.save()

                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao, usuario=request.user, acao="Cotação Registrada",
                    detalhes=f"Preços de {fornecedor_selecionado.nome_fantasia} registrados via escritório."
                )
                
                messages.success(request, "Cotação registrada com sucesso!")
                return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=recebidas")

        except Exception as e:
            messages.error(request, f"Erro ao salvar: {str(e)}")
            return redirect(request.path)

    context = {
        'solicitacao': solicitacao,
        'fornecedor_selecionado': fornecedor_selecionado,
        'envio_cotacao': envio_original,
        'itens_para_cotar': envio_original.itens.all() if envio_original else solicitacao.itens.all(),
        'obras_entrega': Obra.objects.filter(ativa=True).order_by('nome')
    }
    return render(request, 'materiais/iniciar_cotacao.html', context)

@login_required
def selecionar_cotacao_vencedora(request, cotacao_id):
    """
    Finaliza o processo de cotação: seleciona a vencedora, gera a RM,
    notifica o fornecedor (Portal e E-mail) e registra a justificativa de aprovação.
    Ajuste: Implementada limpeza em cascata para remover SC do portal dos perdedores.
    """
    # 1. Verificação de permissão
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
        
    if request.method == 'POST':
        cotacao_vencedora = get_object_or_404(Cotacao.objects.select_related('fornecedor', 'solicitacao__obra'), id=cotacao_id)
        solicitacao = cotacao_vencedora.solicitacao
        
        # --- BLINDAGEM: Captura a justificativa enviada pelo modal ---
        justificativa = request.POST.get('justificativa_diretoria', '')

        # --- SEGURANÇA: Evita criação de RMs duplicadas ---
        if hasattr(solicitacao, 'requisicao'):
            messages.warning(request, f'A RM para a SC {solicitacao.numero} já foi gerada anteriormente.')
            return redirect('materiais:gerenciar_requisicoes')

        try:
            with transaction.atomic():
                # 2. LIMPEZA EM CASCATA: Remove outras cotações e envios (convites) desta SC
                # Isso faz a SC sumir do portal de todos os fornecedores que não venceram
                solicitacao.cotacoes.exclude(pk=cotacao_vencedora.pk).delete()
                solicitacao.envios_cotacao.all().delete()
                
                # 3. Marca como vencedora
                cotacao_vencedora.vencedora = True
                cotacao_vencedora.save()

                # 4. Criação da Requisição de Material (RM)
                nova_rm = RequisicaoMaterial.objects.create(
                    solicitacao_origem=solicitacao,
                    cotacao_vencedora=cotacao_vencedora,
                    valor_total=cotacao_vencedora.valor_total,
                    status_assinatura='pendente' 
                )

                # 5. Atualiza status da Solicitação
                solicitacao.status = 'finalizada'
                solicitacao.save()
                
                # 6. Registro de Auditoria no Histórico
                detalhes_hist = f"Cotação de {cotacao_vencedora.fornecedor.nome_fantasia} selecionada. RM {nova_rm.numero} gerada."
                if justificativa:
                    detalhes_hist += f" | JUSTIFICATIVA DE EXCEÇÃO: {justificativa}"

                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao, 
                    usuario=request.user, 
                    acao="RM Gerada",
                    detalhes=detalhes_hist
                )

                # 7. NOVA NOTIFICAÇÃO INTERNA (ALERTA NO PORTAL DO FORNECEDOR)
                NotificacaoFornecedor.objects.create(
                    fornecedor=cotacao_vencedora.fornecedor,
                    titulo="Cotação Vencedora!",
                    mensagem=f"Sua proposta para a SC {solicitacao.numero} foi selecionada. Obra: {solicitacao.obra.nome}.",
                    link=reverse('materiais:lista_pedidos_fornecedor')
                )

                # 8. ENVIO AUTOMÁTICO DE E-MAIL AO FORNECEDOR
                if cotacao_vencedora.fornecedor.email:
                    assunto = f"Cotação Vencedora! - SC {solicitacao.numero}"
                    corpo = f"Olá {cotacao_vencedora.fornecedor.nome_fantasia},\n\n" \
                            f"Sua proposta para a Solicitação {solicitacao.numero} foi selecionada como vencedora!\n\n" \
                            f"Detalhes:\n" \
                            f"Obra: {solicitacao.obra.nome}\n" \
                            f"Valor Total: R$ {cotacao_vencedora.valor_total}\n\n" \
                            f"Em breve você receberá a Ordem de Compra oficial após as assinaturas de alçada."
                    try:
                        send_mail(assunto, corpo, settings.DEFAULT_FROM_EMAIL, [cotacao_vencedora.fornecedor.email])
                    except Exception as e:
                        print(f"Erro ao enviar e-mail: {e}")

            messages.success(request, f"Cotação selecionada! RM {nova_rm.numero} gerada e fornecedor notificado.")
            
        except Exception as e:
            messages.error(request, f"Erro ao processar seleção: {e}")
            return redirect('materiais:gerenciar_cotacoes')
    
    return redirect('materiais:gerenciar_requisicoes')

@login_required
def rejeitar_cotacao(request, cotacao_id):
    """
    Remove apenas o orçamento recebido (Cotacao), mantendo o convite (EnvioCotacao).
    A SC volta para a aba 'Em Cotação' e o fornecedor pode cotar novamente.
    """
    if request.method == 'POST':
        cotacao = get_object_or_404(Cotacao, id=cotacao_id)
        solicitacao = cotacao.solicitacao
        fornecedor = cotacao.fornecedor
        fornecedor_nome = fornecedor.nome_fantasia

        try:
            with transaction.atomic():
                # CORREÇÃO: Apaga APENAS a Cotacao (preços), mantém o EnvioCotacao
                cotacao.delete()

                historico_detalhes = f"Os preços do fornecedor {fornecedor_nome} foram removidos. O convite permanece ativo para nova cotação."
                
                # Verifica se a SC ficou sem nenhuma outra cotação registrada
                if not solicitacao.cotacoes.exists():
                    # Se não houver mais cotações, reverte o status para aguardar novas cotações
                    # Isso faz a SC aparecer novamente em "Em Cotação"
                    solicitacao.status = 'aguardando_resposta'
                    solicitacao.save()
                    historico_detalhes += " A SC retornou ao estado 'Em Cotação' aguardando novas respostas."

                # Registro de Auditoria
                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao,
                    usuario=request.user,
                    acao="Cotação Alterada",
                    detalhes=historico_detalhes
                )

            messages.success(request, f"Os preços do fornecedor {fornecedor_nome} foram removidos. O convite permanece ativo para nova cotação.")
            
            # Redireciona para a aba correta conforme lógica original
            if solicitacao.status == 'aguardando_resposta':
                return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=aguardando")
            else:
                return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=recebidas")

        except Exception as e:
            messages.error(request, f"Erro ao rejeitar cotação: {str(e)}")
            return redirect('materiais:gerenciar_cotacoes')

    return redirect('materiais:gerenciar_cotacoes')

'''@login_required
def receber_material(request):
    if request.user.perfil != 'almoxarife_obra':
        messages.error(request, 'Acesso negado. Apenas almoxarife da obra pode receber materiais.')
        return redirect('materiais:dashboard')

    scs_finalizadas = SolicitacaoCompra.objects.filter(
        status='finalizada'
    ).select_related('obra', 'solicitante').prefetch_related('itens').order_by('-data_criacao')

    return render(request, 'materiais/receber_material.html', {
        'scs_finalizadas': scs_finalizadas
    })'''


'''@login_required
def iniciar_recebimento(request, solicitacao_id):
    if request.user.perfil != 'almoxarife_obra':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status='finalizada')

    if request.method == 'POST':
        from django.db import transaction
        
        with transaction.atomic():
            ultimo_rm = RequisicaoMaterial.objects.order_by('-id').first()
            if ultimo_rm:
                numero_rm = f"RM-{str(ultimo_rm.id + 1).zfill(3)}"
            else:
                numero_rm = "RM-001"
            
            rm = RequisicaoMaterial.objects.create(
                numero=numero_rm,
                solicitacao_origem=solicitacao,
                recebedor=request.user,
                data_recebimento=timezone.now().date(),
                observacoes=request.POST.get('observacoes_gerais', '')
            )
            
            quantidades_recebidas = request.POST.getlist('quantidade_recebida[]')
            observacoes_recebimento = request.POST.getlist('observacoes_recebimento[]')
            itens_processados = 0

            for i, item in enumerate(solicitacao.itens.all()):
                if i < len(quantidades_recebidas) and quantidades_recebidas[i]:
                    quantidade_recebida = float(quantidades_recebidas[i])
                    if quantidade_recebida > 0:
                        ItemRecebimento.objects.create(
                            requisicao=rm,
                            item_original=item,
                            quantidade_recebida=quantidade_recebida,
                            observacoes=observacoes_recebimento[i] if i < len(observacoes_recebimento) else ''
                        )
                        itens_processados += 1
            
            if itens_processados > 0:
                solicitacao.status = 'recebida'
                solicitacao.recebedor = request.user
                solicitacao.data_recebimento = timezone.now()
                solicitacao.save()
                
                # --- REGISTRO DE HISTÓRICO ---
                # Este bloco está corretamente indentado dentro do "if"
                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao,
                    usuario=request.user,
                    acao="Material Recebido",
                    detalhes=f"Recebimento parcial/total registrado na RM {rm.numero}."
                )
                # --- FIM DO REGISTRO ---
                
                messages.success(request, f'✅ Material recebido com sucesso! RM {numero_rm} criada.')
                return redirect('materiais:receber_material')
            else:
                rm.delete()
                messages.error(request, 'Informe pelo menos um item recebido.')

    return render(request, 'materiais/iniciar_recebimento.html', {
        'solicitacao': solicitacao
    })'''




from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger 
# ... (outras imports) ...


# ... (outras funções) ...


@login_required
def historico_recebimentos(request):
    # Lista de perfis permitidos a VISUALIZAR o Histórico de Recebimentos
    perfis_permitidos = ['almoxarife_obra', 'engenheiro', 'almoxarife_escritorio', 'diretor']

    if request.user.perfil not in perfis_permitidos:
        messages.error(request, 'Acesso negado. Apenas Almoxarife (Obra/Escritório), Engenheiro e Diretor podem visualizar este histórico.')
        return redirect('materiais:dashboard')

    # --- INÍCIO DA LÓGICA DE FILTROS, ORDENAÇÃO E PAGINAÇÃO ---
    
    # 1. Captura de Parâmetros
    termo_busca = request.GET.get('q', '').strip()
    ano = request.GET.get('ano', '')
    mes = request.GET.get('mes', '')
    categoria_id = request.GET.get('categoria', '')
    per_page_str = request.GET.get('per_page', '10') # Padrão 10 itens por página
    sort_by = request.GET.get('sort', '-data_recebimento') # Ordenação padrão: mais recente
    sort_dir = request.GET.get('dir', 'desc')
    page = request.GET.get('page')
    
    try:
        per_page = int(per_page_str)
        if per_page <= 0: per_page = 10
    except ValueError:
        per_page = 10
        
    # Ajusta a ordenação para o Django
    if sort_dir == 'desc' and sort_by[0] != '-':
        sort_key = f'-{sort_by}'
    elif sort_dir == 'asc' and sort_by[0] == '-':
        sort_key = sort_by[1:]
    else:
        sort_key = sort_by
        
    # 2. Construção da Query Base (OTIMIZAÇÃO PARA NOVO DESIGN)
    base_query = Recebimento.objects.filter(
        recebedor=request.user
    ).select_related(
        'solicitacao__obra', 
        'solicitacao__categoria_sc',
        # Pré-carrega a Requisição, Cotação e Fornecedor para evitar N+1 queries
        'solicitacao__requisicao',
        'solicitacao__requisicao__cotacao_vencedora',
        'solicitacao__requisicao__cotacao_vencedora__fornecedor',
    ).prefetch_related('itens_recebidos__item_solicitado') # Pré-carrega os itens recebidos

    # 3. Aplicação dos Filtros
    recebimentos_feitos = base_query
    
    # Filtro de Busca Rápida (q): Busca em RM, SC e Itens
    if termo_busca:
        recebimentos_feitos = recebimentos_feitos.filter(
            Q(solicitacao__numero__icontains=termo_busca) |
            Q(solicitacao__requisicao__numero__icontains=termo_busca) |
            Q(itens_recebidos__item_solicitado__descricao__icontains=termo_busca)
        ).distinct()
    
    # Filtros por Ano/Mês (data do recebimento)
    if ano:
        recebimentos_feitos = recebimentos_feitos.filter(data_recebimento__year=ano)
    
    if mes:
        recebimentos_feitos = recebimentos_feitos.filter(data_recebimento__month=mes)
        
    # Filtro por Categoria da SC
    if categoria_id:
        recebimentos_feitos = recebimentos_feitos.filter(solicitacao__categoria_sc_id=categoria_id)

    # 4. Ordenação e Paginação
    recebimentos_feitos = recebimentos_feitos.order_by(sort_key)
    
    paginator = Paginator(recebimentos_feitos, per_page)
    try:
        recebimentos_paginados = paginator.page(page)
    except PageNotAnInteger:
        recebimentos_paginados = paginator.page(1)
    except EmptyPage:
        recebimentos_paginados = paginator.page(paginator.num_pages)

    # --- FIM DA LÓGICA DE FILTROS, ORDENAÇÃO E PAGINAÇÃO ---

    context = {
        'materiais_recebidos': recebimentos_paginados,
        
        # Variáveis para filtros/paginação
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'meses_opcoes': range(1, 13),
        'filtros_aplicados': {
            'q': termo_busca,
            'ano': ano,
            'mes': mes,
            'categoria': categoria_id,
        },
        'per_page_options': [10, 25, 50, 100],
        'per_page': per_page,
        'current_sort': sort_by.lstrip('-'),
        'current_dir': sort_dir,
    }
    return render(request, 'materiais/historico_recebimentos.html', context)


@login_required
def cadastrar_itens(request):
    # PERMISSÃO AMPLIADA PARA ENGENHEIRO E ALMOXARIFE DE OBRA
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor', 'engenheiro','almoxarife_obra']:
        messages.error(request, 'Acesso negado. Apenas o escritório ou diretoria pode cadastrar itens.')
        return redirect('materiais:dashboard')

    # --- INÍCIO DA LÓGICA DE FILTROS, ORDENAÇÃO E PAGINAÇÃO ---
    termo_busca = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'descricao')
    direction = request.GET.get('dir', 'asc')
    page = request.GET.get('page')
    per_page_str = request.GET.get('per_page', '25')

    try:
        per_page = int(per_page_str)
        if per_page not in [10, 25, 50, 100]:
            per_page = 25
    except ValueError:
        per_page = 25
    
    base_query = ItemCatalogo.objects.filter(
        categoria__categoria_mae__isnull=False 
    ).select_related('categoria__categoria_mae', 'unidade')
    
    if termo_busca:
        base_query = base_query.filter(
            Q(codigo__icontains=termo_busca) |
            Q(descricao__icontains=termo_busca) |
            Q(categoria__nome__icontains=termo_busca) |
            Q(categoria__categoria_mae__nome__icontains=termo_busca) |
            Q(unidade__sigla__icontains=termo_busca)
        ).distinct()
    
    valid_sort_fields = {
        'codigo': 'codigo',
        'descricao': 'descricao',
        'categoria_mae': 'categoria__categoria_mae__nome',
        'subcategoria': 'categoria__nome',
        'unidade': 'unidade__sigla',
        'ativo': 'ativo',
    }
    
    order_field = valid_sort_fields.get(sort_by, 'descricao')
    order = f'-{order_field}' if direction == 'desc' else order_field
    itens_list = base_query.order_by(order)
    
    paginator = Paginator(itens_list, per_page)
    try:
        itens_paginados = paginator.page(page)
    except PageNotAnInteger:
        itens_paginados = paginator.page(1)
    except EmptyPage:
        itens_paginados = paginator.page(paginator.num_pages)
    # --- FIM DA LÓGICA DE FILTROS, ORDENAÇÃO E PAGINAÇÃO ---

    categorias_principais_list = CategoriaItem.objects.filter(
        categoria_mae__isnull=True, 
        subcategorias__isnull=False
    ).distinct().order_by('nome')
    
    unidades_list = UnidadeMedida.objects.all().order_by('nome')
    tags_list = Tag.objects.all().order_by('nome')

    if request.method == 'POST':
        subcategoria_id = request.POST.get('subcategoria')
        descricao = request.POST.get('descricao', '').strip()
        unidade_id = request.POST.get('unidade')
        tags_ids = request.POST.getlist('tags')
        status_ativo = request.POST.get('status') == 'on'
        # Captura se o cadastro foi forçado pelo Modal de Similaridade
        forcar_cadastro = request.POST.get('forcar_cadastro') == 'true'
        
        # Contexto de erro reutilizável
        contexto_erro = {
            'itens': itens_paginados, 
            'categorias_principais': categorias_principais_list,
            'unidades': unidades_list,
            'tags': tags_list,
            'form_data': request.POST,
            'search_query': termo_busca,
            'current_sort': sort_by,
            'current_dir': direction,
            'per_page': per_page,
            'per_page_options': [10, 25, 50, 100],
        }

        # Validação de campos obrigatórios
        erros = []
        if not descricao: erros.append("O campo 'Descrição' é obrigatório.")
        if not request.POST.get('categoria'): erros.append("A 'Categoria' é obrigatória.")
        if not subcategoria_id: erros.append("A 'Subcategoria' é obrigatória.")
        if not unidade_id: erros.append("A 'Unidade' é obrigatória.")

        if erros:
            for erro in erros: messages.error(request, erro)
            return render(request, 'materiais/cadastrar_itens.html', contexto_erro)

        # LÓGICA DE DUPLICIDADE (RESTAURADA DA VERSÃO ANTIGA)
        # Verifica se já existe descrição idêntica (independente de maiúsculas/minúsculas)
        # Se existir e o usuário não clicou em "Forçar" no modal, bloqueia.
        if ItemCatalogo.objects.filter(descricao__iexact=descricao).exists() and not forcar_cadastro:
            messages.error(request, f'❌ Já existe um item cadastrado com a descrição "{descricao}"!')
            # Retorna o status 'duplicado' para o frontend processar (opcional, se usar AJAX)
            return render(request, 'materiais/cadastrar_itens.html', contexto_erro)
        
        try:
            categoria_final_obj = get_object_or_404(CategoriaItem, id=subcategoria_id)
            unidade_obj = get_object_or_404(UnidadeMedida, id=unidade_id)
            
            novo_item = ItemCatalogo(
                descricao=descricao,
                categoria=categoria_final_obj,
                unidade=unidade_obj,
                ativo=status_ativo
            )
            novo_item.save()
            
            if tags_ids:
                novo_item.tags.set(tags_ids)

            messages.success(request, f'✅ Item "{novo_item.descricao}" (Código: {novo_item.codigo}) cadastrado com sucesso!')
            return redirect('materiais:cadastrar_itens')
        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao salvar o item: {e}')
            return render(request, 'materiais/cadastrar_itens.html', contexto_erro)

    # Contexto padrão GET
    context = {
        'itens': itens_paginados,
        'categorias_principais': categorias_principais_list,
        'unidades': unidades_list,
        'tags': tags_list,
        'search_query': termo_busca,
        'current_sort': sort_by,
        'current_dir': direction,
        'per_page': per_page,
        'per_page_options': [10, 25, 50, 100],
    }
    return render(request, 'materiais/cadastrar_itens.html', context)

def buscar_itens_similares(request):
    descricao = request.GET.get('descricao', '').strip()
    if len(descricao) < 3:
        return JsonResponse({'status': 'curto'})

    # Busca no banco itens que contenham parte da descrição informada
    similares = ItemCatalogo.objects.filter(descricao__icontains=descricao)[:5]
    
    if similares.exists():
        itens_data = [{'id': i.id, 'descricao': i.descricao, 'codigo': i.codigo} for i in similares]
        return JsonResponse({'status': 'encontrado', 'itens': itens_data})
    
    return JsonResponse({'status': 'limpo'})

@login_required
def cadastrar_obras(request):
    # PERMISSÃO CORRIGIDA PARA INCLUIR O DIRETOR
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado. Apenas o escritório ou diretoria pode cadastrar obras.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        nome = request.POST.get('nome')
        endereco = request.POST.get('endereco')
        
        if nome:
            Obra.objects.create(
                nome=nome,
                endereco=endereco or ''
            )
            messages.success(request, f'Obra {nome} cadastrada com sucesso!')
            return redirect('materiais:cadastrar_obras')

    obras = Obra.objects.all().order_by('nome')
    return render(request, 'materiais/cadastrar_obras.html', {
        'obras': obras
    })


@login_required
def gerenciar_fornecedores(request):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        cnpj = request.POST.get('cnpj')
        username_novo = request.POST.get('username_fornecedor')
        senha_nova = request.POST.get('senha_fornecedor')

        # Validação de campos obrigatórios do utilizador
        if not username_novo or not senha_nova:
            messages.error(request, 'Obrigatório informar Utilizador e Senha para o acesso do fornecedor.')
            return redirect('materiais:gerenciar_fornecedores')

        if User.objects.filter(username=username_novo).exists():
            messages.error(request, f'O nome de utilizador "{username_novo}" já está em uso.')
            return redirect('materiais:gerenciar_fornecedores')

        if Fornecedor.objects.filter(cnpj=cnpj).exists():
            messages.error(request, f'❌ CNPJ {cnpj} já cadastrado!')
        else:
            try:
                with transaction.atomic():
                    # 1. Cria o Fornecedor
                    novo_fornecedor = Fornecedor.objects.create(
                        nome_fantasia=request.POST.get('nome_fantasia'),
                        razao_social=request.POST.get('razao_social'),
                        cnpj=cnpj,
                        tipo=request.POST.get('tipo'),
                        email=request.POST.get('email'),
                        contato_nome=request.POST.get('contato_nome'),
                        contato_telefone=request.POST.get('contato_telefone'),
                        contato_whatsapp=request.POST.get('contato_whatsapp'),
                        cep=request.POST.get('cep'),
                        logradouro=request.POST.get('logradouro'),
                        numero=request.POST.get('numero'),
                        bairro=request.POST.get('bairro'),
                        cidade=request.POST.get('cidade'),
                        estado=(request.POST.get('estado') or '').upper(),
                        ativo=True
                    )

                    # 2. Cria o Utilizador vinculado
                    user_fornecedor = User.objects.create_user(
                        username=username_novo,
                        password=senha_nova,
                        perfil='fornecedor',
                        fornecedor=novo_fornecedor
                    )

                messages.success(request, f'✅ Fornecedor {novo_fornecedor.nome_fantasia} e utilizador "{username_novo}" criados com sucesso!')
                return redirect('materiais:gerenciar_fornecedores')
            except Exception as e:
                messages.error(request, f'Ocorreu um erro ao cadastrar: {e}')

    context = {
        'fornecedores': Fornecedor.objects.all().order_by('nome_fantasia'),
        'categorias_principais': CategoriaItem.objects.filter(categoria_mae__isnull=True).order_by('nome')
    }
    return render(request, 'materiais/gerenciar_fornecedores.html', context)

@login_required
def finalizar_compra(request, solicitacao_id):
    if request.user.perfil != 'almoxarife_escritorio':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status='cotacao_selecionada')
    cotacao_selecionada = solicitacao.cotacoes.filter(selecionada=True).first()

    if request.method == 'POST':
        observacoes_finalizacao = request.POST.get('observacoes_finalizacao', '')
        
        solicitacao.status = 'finalizada'
        # As observações da finalização podem ser salvas em um campo apropriado se desejar
        # solicitacao.observacoes_aprovacao = observacoes_finalizacao
        solicitacao.save()

        # --- REGISTRO DE HISTÓRICO ---
        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            acao="Compra Finalizada",
            detalhes=f"Pedido de compra efetuado com o fornecedor {cotacao_selecionada.fornecedor.nome}. Observações: {observacoes_finalizacao}"
        )
        # --- FIM DO REGISTRO ---
        
        messages.success(request, f'✅ Compra da SC {solicitacao.numero} finalizada com sucesso!')
        return redirect('materiais:gerenciar_cotacoes') # Melhor redirecionar para a lista de cotações

    return render(request, 'materiais/finalizar_compra.html', {
        'solicitacao': solicitacao,
        'cotacao_selecionada': cotacao_selecionada
    })

@login_required
def selecionar_item_cotado(request, item_cotado_id):
    if request.method == 'POST' and request.user.perfil == 'almoxarife_escritorio':
        item_vencedor = get_object_or_404(ItemCotacao, id=item_cotado_id)
        item_solicitado_original = item_vencedor.item_solicitacao

        # Garante que estamos trabalhando com a solicitação de compra correta
        solicitacao_principal = item_solicitado_original.solicitacao

        with transaction.atomic():
            # Desmarca qualquer outro item vencedor para esta mesma solicitação de item
            item_solicitado_original.itens_cotados.update(selecionado=False)
            
            # Marca o item selecionado como vencedor
            item_vencedor.selecionado = True
            item_vencedor.save()
            
            # Atualiza status da solicitação principal para 'Cotação Selecionada'
            # Isso indica que pelo menos um item já tem um vencedor.
            if solicitacao_principal.status != 'cotacao_selecionada':
                solicitacao_principal.status = 'cotacao_selecionada'
                solicitacao_principal.save()

            # Adiciona ao histórico
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao_principal,
                usuario=request.user,
                acao="Item de Cotação Selecionado",
                detalhes=f"Item '{item_solicitado_original.descricao}' do fornecedor '{item_vencedor.cotacao.fornecedor.nome}' foi selecionado como vencedor."
            )

        messages.success(request, f"Item '{item_solicitado_original.descricao}' do fornecedor '{item_vencedor.cotacao.fornecedor.nome}' selecionado!")

    # Redireciona de volta para a tela de gerenciamento, focando na aba correta.
    return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=recebidas")


@login_required
def api_solicitacao_itens(request, solicitacao_id):
    """API para buscar itens de uma solicitação (usado na aprovação parcial e na cotação)"""
    # PERMISSÃO CORRIGIDA PARA INCLUIR O DIRETOR
    if request.user.perfil not in ['engenheiro', 'almoxarife_escritorio', 'diretor']:
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    try:
        solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
        
        # Busca todos os itens que já foram enviados para cotação
        itens_ja_enviados = set()
        for envio in solicitacao.envios_cotacao.all():
            itens_ja_enviados.update(envio.itens.values_list('id', flat=True))
        
        itens_data = []
        for item in solicitacao.itens.all():
            itens_data.append({
                'id': item.id,
                'descricao': item.descricao,
                'quantidade': float(item.quantidade),
                'unidade': item.unidade,
                'observacoes': item.observacoes or '',
                'ja_enviado': item.id in itens_ja_enviados  # NOVO: flag para indicar se já foi enviado
            })
        
        return JsonResponse({
            'success': True,
            'itens': itens_data,
            'solicitacao': {
                'id': solicitacao.id,
                'numero': solicitacao.numero,
                'obra': solicitacao.obra.nome,
                'solicitante': solicitacao.solicitante.get_full_name() or solicitacao.solicitante.username
            }
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def api_verificar_envios_anteriores(request, solicitacao_id):
    """API para verificar se fornecedores já receberam cotação anterior desta SC"""
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    try:
        fornecedor_id = request.GET.get('fornecedor_id')
        if not fornecedor_id:
            return JsonResponse({'success': False, 'message': 'Fornecedor não especificado'})
        
        envio_anterior = EnvioCotacao.objects.filter(
            solicitacao_id=solicitacao_id,
            fornecedor_id=fornecedor_id
        ).first()
        
        if envio_anterior:
            return JsonResponse({
                'success': True,
                'tem_envio_anterior': True,
                'condicoes': {
                    'forma_pagamento': envio_anterior.forma_pagamento,
                    'forma_pagamento_display': envio_anterior.get_forma_pagamento_display(),
                    'prazo_pagamento': envio_anterior.prazo_pagamento,
                    'prazo_resposta': envio_anterior.prazo_resposta.strftime('%d/%m/%Y') if envio_anterior.prazo_resposta else 'Não definido',
                    'data_envio': envio_anterior.data_envio.strftime('%d/%m/%Y %H:%M'),
                    'itens_enviados': list(envio_anterior.itens.values_list('id', flat=True))
                }
            })
        else:
            return JsonResponse({
                'success': True,
                'tem_envio_anterior': False
            })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def aprovar_parcial(request, solicitacao_id):
    """Função para aprovação parcial de solicitações"""
    if request.user.perfil != 'engenheiro':
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método não permitido'})
    
    try:
        solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
        
        if solicitacao.status != 'pendente_aprovacao':
            return JsonResponse({'success': False, 'message': 'Solicitação não pode ser aprovada parcialmente'})
        
        itens_aprovados_ids = request.POST.getlist('itens_aprovados[]')
        observacoes = request.POST.get('observacoes', '')
        
        if not itens_aprovados_ids:
            return JsonResponse({'success': False, 'message': 'Selecione pelo menos um item para aprovar'})
        
        from django.db import transaction
        
        with transaction.atomic():
            # Cria a nova solicitação com os itens aprovados
            nova_solicitacao = SolicitacaoCompra.objects.create(
                solicitante=solicitacao.solicitante,
                obra=solicitacao.obra,
                data_necessidade=solicitacao.data_necessidade,
                justificativa=f"Aprovação parcial da SC {solicitacao.numero}",
                status='aprovada',
                aprovador=request.user,
                data_aprovacao=timezone.now(),
                observacoes_aprovacao=observacoes
            )
            
            # Move os itens da solicitação original para a nova
            itens_aprovados = ItemSolicitacao.objects.filter(id__in=itens_aprovados_ids, solicitacao=solicitacao)
            for item_original in itens_aprovados:
                ItemSolicitacao.objects.create(
                    solicitacao=nova_solicitacao,
                    descricao=item_original.descricao,
                    quantidade=item_original.quantidade,
                    unidade=item_original.unidade,
                    observacoes=item_original.observacoes
                )
            
            # Remove os itens movidos da solicitação original
            itens_aprovados.delete()
            
            # --- REGISTRO DE HISTÓRICO ---
            detalhes_historico = f"Itens aprovados movidos para a nova SC {nova_solicitacao.numero}."
            if observacoes:
                detalhes_historico += f" Observações: {observacoes}"

            # Adiciona histórico na solicitação original
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=request.user,
                acao="Aprovação Parcial",
                detalhes=detalhes_historico
            )
            # Adiciona histórico na nova solicitação
            HistoricoSolicitacao.objects.create(
                solicitacao=nova_solicitacao,
                usuario=request.user,
                acao="Criação por Aprovação Parcial",
                detalhes=f"Originada da SC {solicitacao.numero}."
            )
            # --- FIM DO REGISTRO ---

            # Se a solicitação original ficou sem itens, marca como rejeitada/finalizada
            if not solicitacao.itens.exists():
                solicitacao.status = 'rejeitada' # Ou outro status que faça sentido
                solicitacao.aprovador = request.user
                solicitacao.data_aprovacao = timezone.now()
                solicitacao.observacoes_aprovacao = f"Todos os itens foram movidos para a SC {nova_solicitacao.numero}."
            
            solicitacao.save()
            
        return JsonResponse({
            'success': True, 
            'message': f'Aprovação parcial realizada! Nova SC {nova_solicitacao.numero} criada com {len(itens_aprovados_ids)} item(ns) aprovado(s).'
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Erro: {str(e)}'})

@login_required
def dashboard_relatorios(request):
    if request.user.perfil not in ['engenheiro', 'almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    # --- 1. Cálculos Gerais (Visão Geral) ---
    all_scs = SolicitacaoCompra.objects.all()
    aprovado_statuses = ['aprovada', 'aprovado_engenharia']
    cotacao_statuses = ['em_cotacao', 'aguardando_resposta', 'cotacao_selecionada']

    contexto_geral = {
        'total_solicitacoes': all_scs.count(),
        'solicitacoes_pendentes': all_scs.filter(status='pendente_aprovacao').count(),
        'solicitacoes_aprovadas': all_scs.filter(status__in=aprovado_statuses).count(),
        'solicitacoes_em_cotacao': all_scs.filter(status__in=cotacao_statuses).count(),
        'solicitacoes_finalizadas': all_scs.filter(status='finalizada').count(),
        'solicitacoes_recebidas': all_scs.filter(status='recebida').count(),
        'solicitacoes_rejeitadas': all_scs.filter(status='rejeitada').count(),
        'obras_ativas': Obra.objects.filter(ativa=True).count(),
    }

    # --- 2. Detalhes e Novas Métricas por Obra ---
    obras_com_scs = Obra.objects.filter(ativa=True, solicitacaocompra__isnull=False).distinct()
    obras_stats_detalhado = []

    for obra in obras_com_scs:
        obra_scs = SolicitacaoCompra.objects.filter(obra=obra)
        
        stats = {
            'obra': obra,
            'pendentes': obra_scs.filter(status='pendente_aprovacao').count(),
            'aprovadas': obra_scs.filter(status__in=aprovado_statuses).count(),
            'em_cotacao': obra_scs.filter(status__in=cotacao_statuses).count(),
            'finalizadas': obra_scs.filter(status='finalizada').count(),
            'a_caminho': obra_scs.filter(status='a_caminho').count(),
            'recebidas': obra_scs.filter(status__in=['recebida', 'recebida_parcial']).count(),
            'rejeitadas': obra_scs.filter(status='rejeitada').count(),
        }

        # MÉTRICA: Itens Mais Solicitados (Top 5 por Quantidade)
        stats['itens_mais_solicitados'] = ItemSolicitacao.objects.filter(
            solicitacao__obra=obra
        ).values('descricao', 'unidade').annotate(
            total_quantidade=Sum('quantidade')
        ).order_by('-total_quantidade')[:5]

        # MÉTRICA: Consumo por Categoria (Valor Total em R$)
        # ---- INÍCIO DA CORREÇÃO ----
        consumo_valor_categoria = ItemCotacao.objects.filter(
            cotacao__solicitacao__obra=obra, cotacao__vencedora=True
        ).annotate(
            subtotal=F('preco') * F('item_solicitacao__quantidade')
        ).values(
            categoria_nome=F('item_solicitacao__item_catalogo__categoria__categoria_mae__nome')
        ).annotate(
            valor_total=Sum('subtotal')
        ).order_by('-valor_total')
        
        # MÉTRICA: Consumo por Categoria (Quantidade Total de Itens)
        consumo_qtd_categoria = ItemSolicitacao.objects.filter(
            solicitacao__obra=obra, item_catalogo__isnull=False
        ).values(
            categoria_nome=F('item_catalogo__categoria__categoria_mae__nome')
        ).annotate(
            qtd_total=Sum('quantidade')
        ).order_by('-qtd_total')

        # Prepara os dados para os gráficos em formato JSON
        stats['consumo_valor_json'] = json.dumps({
            'labels': [c['categoria_nome'] or 'Sem Categoria Principal' for c in consumo_valor_categoria],
            'data': [float(c['valor_total']) for c in consumo_valor_categoria]
        })
        
        stats['consumo_qtd_json'] = json.dumps({
            'labels': [c['categoria_nome'] or 'Sem Categoria Principal' for c in consumo_qtd_categoria],
            'data': [float(c['qtd_total']) for c in consumo_qtd_categoria]
        })
        # ---- FIM DA CORREÇÃO ----

        obras_stats_detalhado.append(stats)

    context = {
        'geral': contexto_geral,
        'obras_stats_detalhado': obras_stats_detalhado,
    }
    
    return render(request, 'materiais/dashboard_relatorios.html', context)

@login_required
def buscar_solicitacoes(request):
    """Função de busca avançada para solicitações"""
    termo_busca = request.GET.get('q', '').strip()
    status_filtro = request.GET.get('status', '')
    obra_filtro = request.GET.get('obra', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    solicitante_filtro = request.GET.get('solicitante', '')
    
    if request.user.perfil == 'engenheiro':
        solicitacoes = SolicitacaoCompra.objects.all()
    else:
        solicitacoes = SolicitacaoCompra.objects.filter(solicitante=request.user)
    
    if termo_busca:
        solicitacoes = solicitacoes.filter(
            Q(numero__icontains=termo_busca) |
            Q(justificativa__icontains=termo_busca) |
            Q(itens__descricao__icontains=termo_busca)
        ).distinct()
    
    if status_filtro:
        solicitacoes = solicitacoes.filter(status=status_filtro)
    
    if obra_filtro:
        solicitacoes = solicitacoes.filter(obra_id=obra_filtro)
    
    if data_inicio:
        solicitacoes = solicitacoes.filter(data_criacao__gte=data_inicio)
    
    if data_fim:
        solicitacoes = solicitacoes.filter(data_criacao__lte=data_fim)
    
    if solicitante_filtro and request.user.perfil == 'engenheiro':
        solicitacoes = solicitacoes.filter(solicitante_id=solicitante_filtro)
    
    solicitacoes = solicitacoes.order_by('-data_criacao')
    
    obras = Obra.objects.filter(ativa=True).order_by('nome')
    usuarios = User.objects.filter(perfil__in=['almoxarife_obra', 'engenheiro']).order_by('first_name', 'username')
    
    context = {
        'solicitacoes': solicitacoes,
        'obras': obras,
        'usuarios': usuarios,
        'termo_busca': termo_busca,
        'status_filtro': status_filtro,
        'obra_filtro': obra_filtro,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'solicitante_filtro': solicitante_filtro,
        'status_choices': SolicitacaoCompra.STATUS_CHOICES,
    }
    
    return render(request, 'materiais/buscar_solicitacoes.html', context)


@login_required
def exportar_relatorio(request):
    """Exporta relatório de solicitações em CSV"""
    if request.user.perfil not in ['engenheiro', 'almoxarife_escritorio']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
    
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="relatorio_solicitacoes_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    response.write('\ufeff')
    
    writer = csv.writer(response)
    
    writer.writerow([
        'Número SC', 'Status', 'Obra', 'Solicitante', 'Data Criação', 
        'Data Aprovação', 'Aprovador', 'Justificativa', 'Itens', 'Observações'
    ])
    
    solicitacoes = SolicitacaoCompra.objects.select_related(
        'obra', 'solicitante', 'aprovador'
    ).prefetch_related('itens').order_by('-data_criacao')
    
    for sc in solicitacoes:
        itens_str = '; '.join([
            f"{item.descricao} ({item.quantidade} {item.unidade})" 
            for item in sc.itens.all()
        ])
        
        writer.writerow([
            sc.numero,
            sc.get_status_display(),
            sc.obra.nome,
            sc.solicitante.get_full_name() or sc.solicitante.username,
            sc.data_criacao.strftime('%d/%m/%Y %H:%M') if sc.data_criacao else '',
            sc.data_aprovacao.strftime('%d/%m/%Y %H:%M') if sc.data_aprovacao else '',
            sc.aprovador.get_full_name() or sc.aprovador.username if sc.aprovador else '',
            sc.justificativa,
            itens_str,
            sc.observacoes_aprovacao or ''
        ])
    
    return response


@login_required
def duplicar_solicitacao(request, solicitacao_id):
    """Duplica uma solicitação existente"""
    if request.user.perfil not in ['almoxarife_obra', 'engenheiro']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
    
    solicitacao_original = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    
    if request.user.perfil != 'engenheiro' and solicitacao_original.solicitante != request.user:
        messages.error(request, 'Você só pode duplicar suas próprias solicitações.')
        return redirect('materiais:lista_solicitacoes')
    
    try:
        from django.db import transaction
    
        with transaction.atomic():
            nova_solicitacao = SolicitacaoCompra.objects.create(
                solicitante=request.user,
                obra=solicitacao_original.obra,
                data_necessidade=solicitacao_original.data_necessidade,
                justificativa=f"Duplicação da SC {solicitacao_original.numero} - {solicitacao_original.justificativa}",
                status='aprovada' if request.user.perfil == 'engenheiro' else 'pendente_aprovacao'
            )
            
            for item_original in solicitacao_original.itens.all():
                ItemSolicitacao.objects.create(
                    solicitacao=nova_solicitacao,
                    descricao=item_original.descricao,
                    quantidade=item_original.quantidade,
                    unidade=item_original.unidade,
                    observacoes=item_original.observacoes
                )
            
            if request.user.perfil == 'engenheiro':
                nova_solicitacao.aprovador = request.user
                nova_solicitacao.data_aprovacao = timezone.now()
                nova_solicitacao.save()
                messages.success(request, f'✅ SC {nova_solicitacao.numero} duplicada e aprovada automaticamente!')
            else:
                messages.success(request, f'✅ SC {nova_solicitacao.numero} duplicada com sucesso!')
            
        return redirect('materiais:lista_solicitacoes')
    
    except Exception as e:
        messages.error(request, f'Erro ao duplicar solicitação: {str(e)}')
        return redirect('materiais:lista_solicitacoes')




@login_required
def api_solicitacao_detalhes(request, solicitacao_id):
    try:
        solicitacao = SolicitacaoCompra.objects.select_related(
            'categoria_sc', 'solicitante', 'obra', 'destino'
        ).get(id=solicitacao_id)
        
        dados = {
            'numero': solicitacao.numero,
            'status': solicitacao.get_status_display(),
            'nome_descritivo': solicitacao.nome_descritivo,
            'solicitante': solicitacao.solicitante.get_full_name() or solicitacao.solicitante.username,
            'obra': solicitacao.obra.nome,
            'destino': solicitacao.destino.nome if solicitacao.destino else "Endereço da Obra",
            'data_criacao': timezone.localtime(solicitacao.data_criacao).strftime('%d/%m/%Y'),
            'data_necessaria': solicitacao.data_necessidade.strftime('%d/%m/%Y'),
            'observacoes': solicitacao.justificativa,
            'is_emergencial': solicitacao.is_emergencial
        }

        itens = []
        for item in solicitacao.itens.all():
            # --- LÓGICA DE SEPARAÇÃO DA CATEGORIA ---
            categoria_principal = "-"
            subcategoria = "-"
            # O campo 'categoria' no seu modelo é um texto 'Pai -> Filho'
            # Vamos separá-lo aqui
            if ' -> ' in item.categoria:
                parts = item.categoria.split(' -> ', 1)
                categoria_principal = parts[0]
                subcategoria = parts[1]
            elif item.categoria:
                categoria_principal = item.categoria

            itens.append({
                'descricao': item.descricao, 
                'quantidade': f"{item.quantidade:g}",
                'unidade': item.unidade,
                'categoria_principal': categoria_principal, # Novo campo
                'subcategoria': subcategoria              # Novo campo
            })
        dados['itens'] = itens

        historico = []
        for evento in solicitacao.historico.select_related('usuario').all():
            timestamp_local = timezone.localtime(evento.timestamp)
            historico.append({
                'status': evento.acao, 'timestamp': timestamp_local.strftime('%d/%m/%Y às %H:%M'),
                'usuario': evento.usuario.get_full_name() or evento.usuario.username if evento.usuario else "Sistema",
                'detalhes': evento.detalhes or ''
            })
        dados['historico'] = historico

        return JsonResponse(dados)
    
    except SolicitacaoCompra.DoesNotExist:
        return JsonResponse({'error': 'Solicitação não encontrada'}, status=404)
    
# Adicione esta nova função ao seu arquivo materiais/views.py cadastrar_itens
@login_required
def gerenciar_categorias(request):
    # PERMISSÃO AMPLIADA PARA ENGENHEIRO
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor', 'engenheiro','almoxarife_obra']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        nome = request.POST.get('nome')

        if not nome:
            messages.error(request, 'O nome da categoria não pode ser vazio.')
            return redirect('materiais:gerenciar_categorias')

        # Lógica para criar Categoria de Item (Principal ou Subcategoria)
        if form_type == 'categoria_item':
            categoria_mae_id = request.POST.get('categoria_mae') # Pode ser None ou um ID
            
            query = CategoriaItem.objects.filter(nome__iexact=nome, categoria_mae_id=categoria_mae_id)
            if query.exists():
                messages.error(request, 'Uma categoria com este nome e nesta mesma hierarquia já existe.')
            else:
                CategoriaItem.objects.create(nome=nome, categoria_mae_id=categoria_mae_id)
                messages.success(request, f'Categoria de Item "{nome}" cadastrada com sucesso!')

        # Lógica para criar Categoria de SC
        elif form_type == 'categoria_sc':
            if not CategoriaSC.objects.filter(nome__iexact=nome).exists():
                CategoriaSC.objects.create(nome=nome)
                messages.success(request, f'Categoria de SC "{nome}" cadastrada!')
            else:
                messages.error(request, 'Essa Categoria de SC já existe.')
        
        return redirect('materiais:gerenciar_categorias')

    context = {
        'categorias_principais': CategoriaItem.objects.filter(categoria_mae__isnull=True).prefetch_related('subcategorias').order_by('nome'),
        'categorias_sc': CategoriaSC.objects.all().order_by('nome')
    }
    return render(request, 'materiais/gerenciar_categorias.html', context)


@login_required
def historico_aprovacoes(request):
    # Garante que apenas engenheiros acessem esta página
    if request.user.perfil != 'engenheiro':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    # Pega os valores dos filtros da URL (GET)
    termo_busca = request.GET.get('q', '').strip()
    ano = request.GET.get('ano', '')
    mes = request.GET.get('mes', '')
    categoria_id = request.GET.get('categoria', '')
    page = request.GET.get('page')
    
    # [NOVO] Captura o número de itens por página ou define o padrão
    num_paginas_str = request.GET.get('num_paginas', '20')
    try:
        num_paginas = int(num_paginas_str)
        if num_paginas <= 0 or num_paginas > 100: # Limite sensato para evitar problemas
            num_paginas = 20
    except ValueError:
        num_paginas = 20

    # 1. Query base: filtra APENAS as solicitações APROVADAS pelo usuário logado
    base_query = SolicitacaoCompra.objects.filter(
        aprovador=request.user
    ).select_related('obra', 'solicitante', 'categoria_sc').prefetch_related('itens').order_by('-data_aprovacao')

    # 2. Aplica os filtros adicionais
    solicitacoes_aprovadas = base_query
    if termo_busca:
        solicitacoes_aprovadas = solicitacoes_aprovadas.filter(
            Q(numero__icontains=termo_busca) |
            Q(justificativa__icontains=termo_busca) |
            Q(itens__descricao__icontains=termo_busca) |
            Q(obra__nome__icontains=termo_busca)
        ).distinct()
    
    if ano:
        # Filtra pelo ano de criação da SC
        solicitacoes_aprovadas = solicitacoes_aprovadas.filter(data_criacao__year=ano)
    
    if mes:
        # Filtra pelo mês de criação da SC
        solicitacoes_aprovadas = solicitacoes_aprovadas.filter(data_criacao__month=mes)
        
    if categoria_id:
        solicitacoes_aprovadas = solicitacoes_aprovadas.filter(categoria_sc_id=categoria_id)

    # 3. OTIMIZAÇÃO: Adiciona a contagem de itens
    solicitacoes_aprovadas = solicitacoes_aprovadas.annotate(num_itens=Count('itens'))
    
    # 4. PAGINAÇÃO - Usa a variável num_paginas
    paginator = Paginator(solicitacoes_aprovadas, num_paginas)
    try:
        solicitacoes_paginadas = paginator.page(page)
    except PageNotAnInteger:
        solicitacoes_paginadas = paginator.page(1)
    except EmptyPage:
        solicitacoes_paginadas = paginator.page(paginator.num_pages)
    
    # 5. Monta o contexto
    context = {
        # Envia a página de objetos em vez do queryset completo
        'solicitacoes': solicitacoes_paginadas,
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'meses_opcoes': range(1, 13),
        'filtros_aplicados': {
            'q': termo_busca,
            'ano': ano,
            'mes': mes,
            'categoria': categoria_id,
        },
        # [NOVO] Adiciona as opções de paginação ao contexto
        'num_paginas_opcoes': [10, 25, 50, 100],
        'num_paginas': num_paginas
    }
    
    return render(request, 'materiais/historico_aprovacoes.html', context)    

@login_required
def rejeitar_pelo_escritorio(request, solicitacao_id):
    if request.user.perfil != 'almoxarife_escritorio':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status='aprovada')
        
        # Opcional: pegar motivo da rejeição, se houver um campo no POST
        motivo = request.POST.get('motivo', 'Rejeitada pelo escritório antes da cotação.')

        solicitacao.status = 'rejeitada'
        solicitacao.aprovador = request.user # Registra quem tomou a decisão final
        solicitacao.data_aprovacao = timezone.now() # Registra quando
        solicitacao.observacoes_aprovacao = motivo
        solicitacao.save()
        
        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            acao="Solicitação Rejeitada",
            detalhes=motivo
        )

        messages.warning(request, f'A SC "{solicitacao.nome_descritivo}" foi rejeitada.')
        return redirect('materiais:gerenciar_cotacoes')

    # Redireciona de volta se o método não for POST
    return redirect('materiais:gerenciar_cotacoes')

# Adicione esta nova função ao seu arquivo views.py
@login_required
def escritorio_editar_sc(request, solicitacao_id):
    # View placeholder para a futura tela de edição
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    messages.info(request, f'A funcionalidade "Editar" para a SC {solicitacao.numero} está em desenvolvimento.')
    return redirect('materiais:gerenciar_cotacoes')


# Substitua sua função gerenciar_cotacoes por esta
@login_required
def gerenciar_cotacoes(request):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    base_query = SolicitacaoCompra.objects.order_by('-is_emergencial', 'data_criacao')
    scs_para_iniciar = base_query.filter(status__in=['aprovada', 'aprovado_engenharia'])
    
    # Adiciona informação de itens pendentes para cada SC
    for sc in scs_para_iniciar:
        todos_itens = set(sc.itens.values_list('id', flat=True))
        itens_enviados = set()
        for envio in sc.envios_cotacao.all():
            itens_enviados.update(envio.itens.values_list('id', flat=True))
        
        itens_pendentes_ids = todos_itens - itens_enviados
        sc.itens_pendentes = sc.itens.filter(id__in=itens_pendentes_ids)
        sc.tem_envios_parciais = bool(itens_enviados and itens_pendentes_ids)
        sc.total_itens = len(todos_itens)
        sc.itens_enviados_count = len(itens_enviados)
    
    # Busca automática das escolhas do Model para o Modal
    formas_pagamento = EnvioCotacao.FORMAS_PAGAMENTO

    # Lógica de Abas (Preservada conforme original)
    scs_recebidas = base_query.filter(
        Q(status='cotacao_selecionada') | Q(status='aguardando_resposta', cotacoes__isnull=False)
    ).distinct().prefetch_related('cotacoes__fornecedor', 'envios_cotacao__fornecedor')

    for sc in scs_recebidas:
        sc.cotacoes_recebidas_ids = set(sc.cotacoes.values_list('fornecedor_id', flat=True))

    # NOVA LÓGICA: Inclui SCs com status 'aguardando_resposta' OU que tenham envios mesmo estando 'aprovada'
    scs_em_cotacao_raw = base_query.filter(
        Q(status='aguardando_resposta') | Q(status__in=['aprovada', 'aprovado_engenharia'], envios_cotacao__isnull=False)
    ).distinct().prefetch_related('envios_cotacao__fornecedor', 'cotacoes')
    
    scs_em_cotacao = []
    for sc in scs_em_cotacao_raw:
        # Verifica se tem envios
        if not sc.envios_cotacao.exists():
            continue
            
        respondidos = set(sc.cotacoes.values_list('fornecedor_id', flat=True))
        convidados = set(sc.envios_cotacao.values_list('fornecedor_id', flat=True))
        
        # Verifica se há itens pendentes
        todos_itens_sc = set(sc.itens.values_list('id', flat=True))
        itens_enviados_sc = set()
        for envio in sc.envios_cotacao.all():
            itens_enviados_sc.update(envio.itens.values_list('id', flat=True))
        
        itens_pendentes = todos_itens_sc - itens_enviados_sc
        
        # Se tem fornecedores aguardando resposta ou tem itens pendentes, adiciona
        if any(f_id not in respondidos for f_id in convidados) or itens_pendentes:
            sc.cotacoes_recebidas_ids = respondidos
            sc.tem_itens_pendentes = bool(itens_pendentes)
            sc.itens_pendentes_count = len(itens_pendentes)
            sc.total_itens = len(todos_itens_sc)
            sc.itens_enviados_count = len(itens_enviados_sc)
            scs_em_cotacao.append(sc)

    context = {
        'scs_para_iniciar': scs_para_iniciar,
        'scs_em_cotacao': scs_em_cotacao,
        'scs_recebidas': scs_recebidas,
        'aguardando_resposta_count': len(scs_em_cotacao),
        'formas_pagamento': formas_pagamento, # Injeção automática
    }
    return render(request, 'materiais/gerenciar_cotacoes.html', context)

@login_required
def editar_solicitacao_escritorio(request, solicitacao_id):
    if request.user.perfil != 'almoxarife_escritorio':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:gerenciar_cotacoes')

    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status__in=['aprovada', 'aprovado_engenharia'])

    if request.method == 'POST':
        try:
            solicitacao.obra_id = request.POST.get('obra')
            # Captura e salva o 'destino'
            solicitacao.destino_id = request.POST.get('destino') if request.POST.get('destino') else None # NOVO
            solicitacao.data_necessidade = request.POST.get('data_necessidade')
            solicitacao.justificativa = request.POST.get('justificativa')
            solicitacao.is_emergencial = request.POST.get('is_emergencial') == 'on'
            solicitacao.categoria_sc_id = request.POST.get('categoria_sc')
            
            itens_json = request.POST.get('itens_json', '[]')
            itens_data = json.loads(itens_json)

            if not itens_data:
                messages.error(request, 'A solicitação deve ter pelo menos um item.')
                return redirect('materiais:editar_solicitacao_escritorio', solicitacao_id=solicitacao.id)

            with transaction.atomic():
                solicitacao.itens.all().delete()
                for item_data in itens_data:
                    item_catalogo = get_object_or_404(ItemCatalogo, id=item_data.get('item_id'))
                    ItemSolicitacao.objects.create(
                        solicitacao=solicitacao, item_catalogo=item_catalogo,
                        descricao=item_catalogo.descricao, unidade=item_catalogo.unidade.sigla,
                        categoria=str(item_catalogo.categoria), quantidade=float(item_data.get('quantidade')),
                        observacoes=item_data.get('observacao')
                    )
                solicitacao.save()
                HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="SC Editada", detalhes="A solicitação foi editada pelo escritório.")

            messages.success(request, f'Solicitação "{solicitacao.numero}" atualizada com sucesso!')
            return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=iniciar-cotacao")

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao salvar as alterações: {e}')
            return redirect('materiais:editar_solicitacao_escritorio', solicitacao_id=solicitacao.id)

    itens_existentes = []
    for item in solicitacao.itens.all():
        itens_existentes.append({
            "item_id": item.item_catalogo_id, "descricao": item.descricao, "unidade": item.unidade,
            "quantidade": f"{item.quantidade:g}", "observacao": item.observacoes
        })
    
    context = {
        'solicitacao': solicitacao,
        'itens_existentes_json': json.dumps(itens_existentes),
        'obras': Obra.objects.filter(ativa=True).order_by('nome'),
        'itens_catalogo_json': json.dumps(list(ItemCatalogo.objects.filter(ativo=True).values('id', 'codigo', 'descricao', 'unidade__sigla'))),
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'destinos_entrega': Obra.objects.filter(ativa=True).order_by('nome'),
    }
    
    return render(request, 'materiais/editar_solicitacao.html', context)
@login_required
def api_buscar_fornecedores(request):
    termo = request.GET.get('term', '').strip()
    
    # --- CONSULTA CORRIGIDA ---
    # Agora, a busca é feita em ambos os campos: nome_fantasia E razao_social.
    # Usamos um objeto Q para criar uma condição OR na busca.
    fornecedores = Fornecedor.objects.filter(
        Q(nome_fantasia__icontains=termo) | Q(razao_social__icontains=termo),
        ativo=True
    ).order_by('nome_fantasia')[:10]
    
    # --- RESULTADO CORRIGIDO ---
    # O texto exibido no dropdown agora vem do campo 'nome_fantasia'.
    resultados = [{'id': f.id, 'text': f.nome_fantasia} for f in fornecedores]
    
    return JsonResponse(resultados, safe=False)

# materials/views.py

@login_required
def enviar_cotacao_fornecedor(request, solicitacao_id):
    """
    Processa solicitações de cotação individualmente via AJAX.
    Inclui suporte a timeout e fallback manual pelo frontend.
    """
    if request.method == 'POST' and request.user.perfil in ['almoxarife_escritorio', 'diretor']:
        solicitacao_original = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
        
        # Captura de dados enviados pelo FormData do AJAX
        fornecedor_id = request.POST.get('fornecedor')
        tipo_envio = request.POST.get('tipo_envio')  # 'auto' ou 'manual'
        itens_selecionados_ids = request.POST.getlist('itens_cotacao')
        
        # Dados de negociação e prazos
        prazo_resposta = request.POST.get('prazo_resposta')
        forma_pagamento = request.POST.get('forma_pagamento')
        prazo_pagamento = request.POST.get('prazo_pagamento', 0)
        observacoes = request.POST.get('observacoes')

        if not all([fornecedor_id, itens_selecionados_ids]):
            return JsonResponse({'success': False, 'message': 'Fornecedor ou itens não selecionados.'}, status=400)

        try:
            with transaction.atomic():
                fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
                
                # VALIDAÇÃO CRÍTICA: Verifica se já existe envio anterior para este fornecedor
                envio_anterior = EnvioCotacao.objects.filter(
                    solicitacao=solicitacao_original,
                    fornecedor=fornecedor
                ).first()
                
                if envio_anterior:
                    # Verifica se as condições comerciais são diferentes
                    if (envio_anterior.forma_pagamento != forma_pagamento or 
                        str(envio_anterior.prazo_pagamento) != str(prazo_pagamento)):
                        return JsonResponse({
                            'success': False,
                            'message': f'❌ BLOQUEIO: Este fornecedor já recebeu cotação com condições diferentes!\n\n'
                                     f'Condições anteriores:\n'
                                     f'• Pagamento: {envio_anterior.get_forma_pagamento_display()}\n'
                                     f'• Prazo: {envio_anterior.prazo_pagamento} dias\n\n'
                                     f'Novas condições solicitadas:\n'
                                     f'• Pagamento: {dict(EnvioCotacao.FORMAS_PAGAMENTO).get(forma_pagamento)}\n'
                                     f'• Prazo: {prazo_pagamento} dias\n\n'
                                     f'⚠️ Para evitar confusão, não é permitido enviar itens adicionais '
                                     f'da mesma SC ao mesmo fornecedor com condições comerciais diferentes.\n\n'
                                     f'Recomendação: Use as mesmas condições ou exclua o envio anterior.'
                        }, status=400)
                
                # Se já existe envio com as MESMAS condições, apenas adiciona os novos itens
                if envio_anterior:
                    envio = envio_anterior
                    # Adiciona os novos itens aos já existentes (usando .add() para M2M)
                    novos_itens = ItemSolicitacao.objects.filter(id__in=itens_selecionados_ids)
                    envio.itens.add(*novos_itens)
                    # Atualiza observações se houver novas
                    if observacoes and observacoes != envio.observacoes:
                        envio.observacoes = f"{envio.observacoes}\n\n--- Atualização ---\n{observacoes}"
                        envio.save()
                else:
                    # Criação do registro de envio (primeira vez para este fornecedor)
                    envio = EnvioCotacao.objects.create(
                        solicitacao=solicitacao_original, 
                        fornecedor=fornecedor,
                        forma_pagamento=forma_pagamento,
                        prazo_pagamento=prazo_pagamento,
                        prazo_resposta=prazo_resposta if prazo_resposta else None,
                        observacoes=observacoes,
                        # Garante que o fornecedor saiba a data de necessidade da obra
                        data_entrega_solicitada=solicitacao_original.data_necessidade 
                    )
                    
                    # Associa os itens específicos que o usuário marcou no modal
                    envio.itens.set(ItemSolicitacao.objects.filter(id__in=itens_selecionados_ids))

                # NOVA LÓGICA: Verifica se TODOS os itens da SC foram enviados para pelo menos 1 fornecedor
                # Pega todos os itens da SC
                todos_itens_sc = set(solicitacao_original.itens.values_list('id', flat=True))
                # Pega todos os itens que já foram enviados (em todos os envios desta SC)
                itens_enviados = set()
                for e in solicitacao_original.envios_cotacao.all():
                    itens_enviados.update(e.itens.values_list('id', flat=True))
                
                # Só muda o status se TODOS os itens foram cobertos
                if todos_itens_sc.issubset(itens_enviados):
                    if solicitacao_original.status in ['aprovada', 'aprovado_engenharia']:
                        solicitacao_original.status = 'aguardando_resposta'
                        solicitacao_original.save()

                # Notificação interna (Sininho do Portal do Fornecedor) - RESTAURADO
                NotificacaoFornecedor.objects.create(
                    fornecedor=fornecedor,
                    titulo="Nova Cotação Disponível",
                    mensagem=f"Solicitação {solicitacao_original.numero} - Obra: {solicitacao_original.obra.nome}",
                    link=reverse('materiais:lista_cotacoes_fornecedor')
                )

                # CORREÇÃO: Envia e-mail em AMBOS os casos (auto e manual)
                # A única diferença é que no manual também abre a tela de confirmação/texto
                try:
                    enviar_email_convite_automatico(fornecedor, solicitacao_original, envio)
                except Exception as e:
                    # Em caso de erro no e-mail, registra mas não impede o processo
                    print(f"Aviso: E-mail não enviado para {fornecedor.nome_fantasia}: {e}")
                    # Não levanta exceção para não bloquear o fluxo

            # Resposta de sucesso para o modal de Etapa 2
            return JsonResponse({
                'success': True,
                'message': 'Convite registrado com sucesso.',
                # URL necessária para abrir a nova aba caso o tipo seja 'manual'
                'url_confirmacao': reverse('materiais:confirmar_envios_cotacao', args=[solicitacao_original.id]) + f"?envios_ids={envio.id}"
            })

        except Exception as e:
            # Retorna erro para o frontend ativar o fallback manual (botão amarelo)
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Método não permitido ou acesso negado.'}, status=403)

# FUNÇÃO AUXILIAR PARA O E-MAIL (Adicione no final do views.py ou antes da def acima)
def enviar_email_convite_automatico(fornecedor, solicitacao, envio):
    """
    Tenta disparar o e-mail. Se falhar, apenas registra o erro sem interromper o fluxo.
    Utilizado tanto para envio AUTO quanto MANUAL.
    """
    if not fornecedor.email:
        print(f"Aviso: Fornecedor {fornecedor.nome_fantasia} não possui e-mail cadastrado.")
        return False

    assunto = f"Solicitação de Cotação - SC {solicitacao.numero} - {solicitacao.obra.nome}"
    
    # Mapeamento para visualização amigável
    formas = dict([
        ('a_negociar', 'A Negociar'), ('avista', 'À Vista'), 
        ('pix', 'Pix'), ('boleto', 'Boleto Bancário'), 
        ('cartao_credito', 'Cartão de Crédito')
    ])
    forma_label = formas.get(envio.forma_pagamento, 'A Negociar')

    corpo = f"""
    Prezado(a) {fornecedor.nome_fantasia},

    Convidamos sua empresa a participar da cotação para a Solicitação de Compra nº {solicitacao.numero}.

    DADOS DA SOLICITAÇÃO:
    - Obra: {solicitacao.obra.nome}
    - Prazo de Entrega Desejado: {solicitacao.data_necessidade.strftime('%d/%m/%Y')}

    CONDIÇÕES DE NEGOCIAÇÃO SUGERIDAS:
    - Forma de Pagamento: {forma_label}
    - Prazo de Pagamento: {envio.prazo_pagamento} dias
    - Observações: {envio.observacoes or 'Nenhuma.'}

    Por favor, acesse o nosso portal para registrar seus preços e prazos:
    {settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'Acesse nosso Portal'}

    Atenciosamente,
    Departamento de Compras
    """

    try:
        # Envia o e-mail de fato
        send_mail(
            assunto,
            corpo,
            settings.DEFAULT_FROM_EMAIL,
            [fornecedor.email],
            fail_silently=False,
        )
        print(f"✓ E-mail enviado com sucesso para {fornecedor.nome_fantasia} ({fornecedor.email})")
        return True
    except Exception as e:
        # Log do erro para o administrador, sem travar o usuário
        print(f"✗ FALHA NO SMTP: Erro ao enviar e-mail para {fornecedor.email}: {e}")
        # NÃO lança exceção - permite que o processo continue normalmente
        return False


def self_email_fornecedor(fornecedor, solicitacao):
    """Função auxiliar para disparar o e-mail de convite."""
    if fornecedor.email:
        assunto = f"Solicitação de Cotação - {solicitacao.numero} - Construtora"
        mensagem = f"""
        Olá, {fornecedor.nome_fantasia}.
        
        Você recebeu um convite para cotar a Solicitação de Compra {solicitacao.numero}.
        Obra: {solicitacao.obra.nome}
        Prazo de entrega desejado: {solicitacao.data_necessidade.strftime('%d/%m/%Y')}
        
        Por favor, acesse o nosso portal do fornecedor para registrar seus preços e condições.
        """
        try:
            send_mail(assunto, mensagem, settings.DEFAULT_FROM_EMAIL, [fornecedor.email])
        except Exception:
            pass # Evita que erro de e-mail trave o sistema

@login_required
def gerar_email_cotacao(request, envio_id):
    envio = get_object_or_404(EnvioCotacao.objects.select_related('solicitacao', 'fornecedor'), id=envio_id)
    
    itens_list_str = "\n".join([f"- {item.quantidade:g} {item.unidade} de {item.descricao}" for item in envio.itens.all()])
    
    email_body = (
        f"Prezados(as) da empresa {envio.fornecedor.nome_fantasia},\n\n"
        f"Gostaríamos de solicitar um orçamento para os seguintes itens, referentes à nossa Solicitação de Compra nº {envio.solicitacao.numero}:\n\n"
        f"{itens_list_str}\n\n"
        f"Condições sugeridas:\n"
        f"- Forma de Pagamento: {envio.get_forma_pagamento_display()}\n"
        f"- Prazo para Pagamento: {envio.prazo_pagamento} dias\n\n"
        f"Observações adicionais: {envio.observacoes}\n\n"
        f"Agradeceríamos se pudessem nos enviar a proposta até a data de {envio.prazo_resposta.strftime('%d/%m/%Y') if envio.prazo_resposta else 'o mais breve possível'}.\n\n"
        f"Atenciosamente,\n"
        f"{request.user.get_full_name() or request.user.username}"
    )
    
    url_retorno = reverse('materiais:confirmar_envios_cotacao', args=[envio.solicitacao.id]) + f"?envios_ids={envio.id}"

    context = {
        'envio': envio,
        'email_subject': f"Solicitação de Orçamento - SC {envio.solicitacao.numero}",
        'email_body': email_body,
        'url_retorno': url_retorno,
    }
    # A LINHA ABAIXO FOI CORRIGIDA COM O PARÊNTESE FINAL
    return render(request, 'materiais/gerar_email_cotacao.html', context)

@login_required
def enviar_automatico_placeholder(request):
    messages.info(request, 'A funcionalidade de envio automático de e-mail está em desenvolvimento.')
    return redirect('materiais:gerenciar_cotacoes')

@login_required
def confirmar_envio_manual(request, envio_id):
    envio = get_object_or_404(EnvioCotacao.objects.select_related('fornecedor', 'solicitacao'), id=envio_id)
    solicitacao = envio.solicitacao
    
    if solicitacao.status == 'em_cotacao':
        solicitacao.status = 'aguardando_resposta'
        solicitacao.save()
    
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="Confirmação de Envio Manual",
        # CORREÇÃO APLICADA AQUI: .nome -> .nome_fantasia
        detalhes=f"Usuário confirmou o envio do e-mail de cotação para o fornecedor {envio.fornecedor.nome_fantasia}."
    )
    
    # CORREÇÃO APLICADA AQUI: .nome -> .nome_fantasia
    messages.success(request, f"Envio de e-mail para {envio.fornecedor.nome_fantasia} confirmado com sucesso!")
    
    url_retorno = request.GET.get('next') or reverse('materiais:gerenciar_cotacoes') + '?tab=aguardando'
    return redirect(url_retorno)
    
@login_required
def api_dados_confirmacao_rm(request, cotacao_id):
    """
    Retorna detalhes da cotação blindados, incluindo o status de conformidade
    para o controle de justificativa do modal.
    """
    cotacao = get_object_or_404(
        Cotacao.objects.select_related('fornecedor', 'solicitacao', 'endereco_entrega'), 
        id=cotacao_id
    )
    solicitacao = cotacao.solicitacao
    
    # Lógica de Pendentes
    convidados_ids = solicitacao.envios_cotacao.values_list('fornecedor_id', flat=True)
    responderam_ids = solicitacao.cotacoes.values_list('fornecedor_id', flat=True)
    pendentes = Fornecedor.objects.filter(id__in=convidados_ids).exclude(id__in=responderam_ids).values_list('nome_fantasia', flat=True)
    
    # Processamento de Itens
    itens_lista = []
    for ic in cotacao.itens_cotados.select_related('item_solicitacao').all():
        qtd = ic.item_solicitacao.quantidade
        preco = ic.preco or 0
        itens_lista.append({
            'descricao': ic.item_solicitacao.descricao,
            'quantidade': f"{qtd:g}",
            'unidade': ic.item_solicitacao.unidade,
            'preco_unitario': f"R$ {preco:.2f}".replace('.', ','),
            'subtotal': f"R$ {(qtd * preco):.2f}".replace('.', ',')
        })

    # Dados do que foi solicitado (para comparação no modal de divergência)
    envio = solicitacao.envios_cotacao.first()
    solicitado_data = {}
    if envio:
        solicitado_data = {
            'prazo': envio.data_entrega_solicitada.strftime('%d/%m/%Y') if envio.data_entrega_solicitada else 'Prazo flexível',
            'pagamento': f"{envio.get_forma_pagamento_display()} em {envio.prazo_pagamento} dias",
            'local': f"{solicitacao.destino.nome} - {solicitacao.destino.endereco}" if solicitacao.destino else f"{solicitacao.obra.nome} - {solicitacao.obra.endereco}"
        }

    # RETORNO JSON COM O CAMPO 'conformidade' PARA O MODAL
    return JsonResponse({
        'conformidade': cotacao.conformidade,  # Define se o JS pedirá justificativa
        'vencedora': {
            'fornecedor': cotacao.fornecedor.nome_fantasia or cotacao.fornecedor.nome,
            'valor_total': f"{cotacao.valor_total:.2f}".replace('.', ','),
            'frete': f"{(cotacao.valor_frete or 0):.2f}".replace('.', ','),
            'prazo': cotacao.prazo_entrega or "Não informado",
            'pagamento': cotacao.condicao_pagamento or "Não informado",
            'local': f"{cotacao.endereco_entrega.nome} - {cotacao.endereco_entrega.endereco}" if cotacao.endereco_entrega else "Não informado"
        },
        'solicitado': solicitado_data,
        'pendentes': list(pendentes),
        'itens': itens_lista,
    })

@login_required
@require_http_methods(["POST"])
def api_validar_senha(request):
    """
    Valida a senha do usuário logado.
    Usado para confirmar aprovação de cotações divergentes.
    """
    import json
    try:
        data = json.loads(request.body)
        senha = data.get('senha')
        
        if not senha:
            return JsonResponse({'success': False, 'error': 'Senha não fornecida'}, status=400)
        
        # Valida a senha usando authenticate
        from django.contrib.auth import authenticate
        user = authenticate(username=request.user.username, password=senha)
        
        if user is not None:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Senha incorreta'})
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def gerenciar_requisicoes(request):
    base_query = RequisicaoMaterial.objects.select_related(
        'cotacao_vencedora__fornecedor', 
        'assinatura_almoxarife', 
        'assinatura_diretor'
    ).order_by('-data_criacao')

    pendentes = base_query.filter(status_assinatura='pendente')
    aguardando_assinatura = base_query.filter(status_assinatura='aguardando_diretor')
    assinadas_enviadas = base_query.filter(status_assinatura='assinada')

    
    context = {
        'pendentes': pendentes,
        'aguardando_assinatura': aguardando_assinatura,
        'assinadas_enviadas': assinadas_enviadas,
    }
    return render(request, 'materiais/gerenciar_requisicoes.html', context)

@login_required
def assinar_requisicao(request, rm_id):
    if request.method == 'POST':
        rm = get_object_or_404(RequisicaoMaterial, id=rm_id)
        password = request.POST.get('password')

        if not request.user.check_password(password):
            messages.error(request, 'Senha incorreta. A assinatura não foi concluída.')
            return redirect('materiais:gerenciar_requisicoes')

        # --- INÍCIO DA LÓGICA ADICIONADA ---
        solicitacao = rm.solicitacao_origem # Pegamos a SC original
        # --- FIM DA LÓGICA ADICIONADA ---

        if request.user.perfil == 'almoxarife_escritorio' and not rm.assinatura_almoxarife:
            rm.assinatura_almoxarife = request.user
            rm.data_assinatura_almoxarife = timezone.now()
            rm.status_assinatura = 'aguardando_diretor'
            messages.success(request, f'RM {rm.numero} assinada por você. Aguardando Diretor.')
            
            # --- INÍCIO DA LÓGICA ADICIONADA ---
            # Adiciona um registro no histórico da SC
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao, usuario=request.user, acao="RM Assinada (1/2)",
                detalhes=f"Primeira assinatura (Almoxarife Escritório) confirmada para a RM {rm.numero}."
            )
            # --- FIM DA LÓGICA ADICIONADA ---
        
        elif request.user.perfil == 'diretor' and rm.assinatura_almoxarife and not rm.assinatura_diretor:
            rm.assinatura_diretor = request.user
            rm.data_assinatura_diretor = timezone.now()
            rm.status_assinatura = 'assinada'
            messages.success(request, f'RM {rm.numero} assinada! Todas as assinaturas foram coletadas.')

            # --- INÍCIO DA LÓGICA ADICIONADA ---
            # Adiciona um registro no histórico da SC
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao, usuario=request.user, acao="RM Assinada (2/2)",
                detalhes=f"Segunda assinatura (Diretor) confirmada. RM {rm.numero} pronta para envio."
            )
            # --- FIM DA LÓGICA ADICIONADA ---
        
        else:
            messages.warning(request, f'Não foi possível registrar a assinatura na RM {rm.numero}. Verifique o estado da requisição.')

        rm.save()
    return redirect('materiais:gerenciar_requisicoes')



@login_required
def enviar_rm_fornecedor(request, rm_id):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    rm = get_object_or_404(RequisicaoMaterial, id=rm_id)

    if rm.status_assinatura != 'assinada':
        messages.warning(request, f'A RM {rm.numero} não está no status "Assinada" e não pode ser enviada.')
        return redirect('materiais:gerenciar_requisicoes')

    if request.method == 'POST':
        # --- NOVO: CAPTURA E SALVA O HEADER ESCOLHIDO ---
        header_choice = request.POST.get('header_choice', 'A') 
        
        # Inicia a transação
        with transaction.atomic():
            solicitacao = rm.solicitacao_origem

            # 1. Atualiza e salva o campo do cabeçalho antes de alterar o status
            rm.header_choice = header_choice
            
            # 2. Atualiza o status da RM para envio
            rm.status_assinatura = 'enviada'
            rm.enviada_fornecedor = True
            rm.data_envio_fornecedor = timezone.now()
            rm.save() # Salva o campo header_choice
            
            # 3. ATUALIZA O STATUS DA SC ORIGINAL PARA "A CAMINHO"
            solicitacao.status = 'a_caminho'
            solicitacao.save()

            # 4. ADICIONA O EVENTO CORRETO AO HISTÓRICO DA SC
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=request.user,
                acao="Material a Caminho",
                detalhes=f"A RM {rm.numero} foi enviada para o fornecedor {rm.cotacao_vencedora.fornecedor.nome_fantasia}. Cabeçalho utilizado: {header_choice}."
            )
        
        messages.success(request, f'Envio da RM {rm.numero} confirmado com sucesso! Cabeçalho {header_choice} utilizado.')
        return redirect('materiais:gerenciar_requisicoes')

    # --- Adiciona a lista de opções de headers ao contexto GET ---
    from . import rm_config
    context = {
        'rm': rm,
        'header_choices': rm_config.HEADER_CHOICES,
    }
    return render(request, 'materiais/enviar_rm.html', context)

@login_required
def editar_item(request, item_id):
    # PERMISSÕES: Inclui todos os perfis operacionais e de gestão
    PERFIS_PERMITIDOS = ['almoxarife_escritorio', 'diretor', 'engenheiro', 'almoxarife_obra']
    if request.user.perfil not in PERFIS_PERMITIDOS:
        messages.error(request, 'Você não tem permissão para editar itens do catálogo.')
        return redirect('materiais:dashboard')

    item_para_editar = get_object_or_404(ItemCatalogo, id=item_id)

    if request.method == 'POST':
        subcategoria_id = request.POST.get('subcategoria')
        descricao = request.POST.get('descricao')
        unidade_id = request.POST.get('unidade')
        tags_ids = request.POST.getlist('tags')
        status_ativo = request.POST.get('status') == 'on'

        if not all([descricao, subcategoria_id, unidade_id]):
            messages.error(request, 'Todos os campos obrigatórios (Descrição, Subcategoria e Unidade) devem ser preenchidos.')
        else:
            try:
                # Verificação de duplicidade (evita renomear para algo que já existe)
                if ItemCatalogo.objects.filter(descricao__iexact=descricao).exclude(id=item_id).exists():
                    messages.error(request, f'Já existe outro item com a descrição "{descricao}".')
                else:
                    # Atualiza os campos
                    item_para_editar.categoria_id = subcategoria_id
                    item_para_editar.descricao = descricao
                    item_para_editar.unidade_id = unidade_id
                    item_para_editar.ativo = status_ativo
                    
                    # Atualiza as Tags (ManyToMany)
                    item_para_editar.tags.set(tags_ids)
                    
                    # IMPORTANTE: Se a descrição mudou, limpamos o embedding para forçar a atualização
                    # na próxima vez que o script de IA rodar, mantendo a busca inteligente precisa.
                    item_para_editar.embedding = None 
                    
                    item_para_editar.save()

                    messages.success(request, f'Item "{item_para_editar.descricao}" atualizado com sucesso!')
                    return redirect('materiais:cadastrar_itens')
                    
            except Exception as e:
                messages.error(request, f'Erro ao atualizar o item: {str(e)}')

    # Lógica para carregar a página (GET)
    # Buscamos a categoria pai para carregar a lista correta de subcategorias via contexto
    categoria_mae = item_para_editar.categoria.categoria_mae if item_para_editar.categoria else None

    context = {
        'item': item_para_editar,
        'categorias_principais': CategoriaItem.objects.filter(categoria_mae__isnull=True).order_by('nome'),
        'subcategorias_atuais': CategoriaItem.objects.filter(categoria_mae=categoria_mae).order_by('nome') if categoria_mae else [],
        'unidades': UnidadeMedida.objects.all().order_by('nome'),
        'tags': Tag.objects.all().order_by('nome'),
    }
    return render(request, 'materiais/editar_item.html', context)

@login_required
def visualizar_rm_pdf(request, rm_id):
    rm = get_object_or_404(
        RequisicaoMaterial.objects.select_related(
            'solicitacao_origem__solicitante',
            'solicitacao_origem__obra',
            'solicitacao_origem__destino',
            'cotacao_vencedora__fornecedor'
        ), 
        id=rm_id
    )

    # Lógica de seleção do cabeçalho
    # O parâmetro 'header' da URL tem precedência sobre o valor salvo no RM.
    header_key = request.GET.get('header', rm.header_choice or 'A') 
    
    # Busca os dados da empresa no dicionário DADOS_EMPRESAS.
    empresa_data = rm_config.DADOS_EMPRESAS.get(header_key, rm_config.DADOS_EMPRESA) 

    # ===================================================================
    # INÍCIO DA LINHA ADICIONADA: Calcula o subtotal apenas dos itens
    # ===================================================================
    subtotal_itens = rm.valor_total - rm.cotacao_vencedora.valor_frete
    # ===================================================================
    # FIM DA LINHA ADICIONADA
    # ===================================================================

    context = {
        'rm': rm,
        'solicitacao': rm.solicitacao_origem,
        'fornecedor': rm.cotacao_vencedora.fornecedor,
        'itens_cotados': rm.cotacao_vencedora.itens_cotados.select_related('item_solicitacao').all(),
        'empresa': empresa_data, # <-- Usa o cabeçalho dinâmico
        'subtotal_itens': subtotal_itens, 
    }
    
    html_string = render_to_string('materiais/rm_pdf_template.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
    
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="RM_{rm.numero}.pdf"'
    return response

@login_required
def api_itens_filtrados(request):
    categoria_id = request.GET.get('categoria_id')
    subcategoria_id = request.GET.get('subcategoria_id')
    
    itens_query = ItemCatalogo.objects.filter(ativo=True)
    
    # Prioriza o filtro de subcategoria, se ele for especificado
    if subcategoria_id:
        itens_query = itens_query.filter(categoria_id=subcategoria_id)
    # Se não houver subcategoria, filtra pela categoria principal
    elif categoria_id:
        # Busca itens cuja categoria tenha a categoria principal informada como 'mãe'
        itens_query = itens_query.filter(categoria__categoria_mae_id=categoria_id)
    
    # Se nenhum filtro for aplicado, retorna todos os itens (comportamento inicial)
    
    itens = list(itens_query.select_related('unidade').values('id', 'codigo', 'descricao', 'unidade__sigla'))
    return JsonResponse(itens, safe=False)

@login_required
def confirmar_envios_cotacao(request, solicitacao_id):
    """
    Exibe os textos formatados para cópia manual.
    """
    ids_param = request.GET.get('envios_ids', '')
    if not ids_param:
        return HttpResponse("Nenhum envio selecionado.")
    
    ids_list = ids_param.split(',')
    envios = EnvioCotacao.objects.filter(id__in=ids_list).select_related('fornecedor', 'solicitacao__obra')
    
    return render(request, 'materiais/confirmar_envios_cotacao.html', {
        'envios': envios
    })

@login_required
def api_get_itens_para_receber(request, solicitacao_id):
    try:
        sc = SolicitacaoCompra.objects.select_related('solicitante', 'obra').get(id=solicitacao_id)
        
        itens_data = []
        for item in sc.itens.all():
            total_recebido = ItemRecebido.objects.filter(item_solicitado=item).aggregate(total=Sum('quantidade_recebida'))['total'] or 0
            quantidade_pendente = item.quantidade - total_recebido
            
            if quantidade_pendente > 0:
                itens_data.append({
                    'id': item.id,
                    'descricao': item.descricao,
                    'quantidade_solicitada': f"{item.quantidade:g}",
                    'quantidade_pendente': f"{quantidade_pendente:g}",
                    'unidade': item.unidade,
                })
        
        return JsonResponse({
            'success': True,
            'sc': {
                'numero': sc.numero,
                'solicitante': sc.solicitante.get_full_name() or sc.solicitante.username,
                'obra': sc.obra.nome,
                'data_criacao': sc.data_criacao.strftime('%d/%m/%Y')
            },
            'itens': itens_data,
        })
    except SolicitacaoCompra.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Solicitação não encontrada'}, status=404)


from django.db.models import Q # Certifique-se de que esta importação está no topo do arquivo

@login_required
def registrar_recebimento(request):
    user = request.user
    perfil = user.perfil

    if perfil not in ['almoxarife_obra', 'almoxarife_escritorio', 'diretor', 'engenheiro']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
        
    search_query = request.GET.get('q', '').strip()

    if perfil in ['almoxarife_escritorio', 'diretor']:
        base_query = SolicitacaoCompra.objects.filter(status__in=['a_caminho', 'recebida_parcial'])
    else: 
        user_obras = user.obras.all()
        base_query = SolicitacaoCompra.objects.filter(
            obra__in=user_obras,
            status__in=['a_caminho', 'recebida_parcial']
        )
    
    # Otimiza a consulta para buscar todos os dados de uma vez
    base_query = base_query.select_related(
        'obra', 
        'requisicao__cotacao_vencedora__fornecedor'
    ).prefetch_related(
        'itens__recebimentos'  # Pré-busca os itens e seus recebimentos
    ).distinct()

    if search_query:
        base_query = base_query.filter(
            Q(numero__icontains=search_query) |
            Q(itens__descricao__icontains=search_query) |
            Q(requisicao__cotacao_vencedora__fornecedor__nome_fantasia__icontains=search_query)
        )

    # Função interna para processar as SCs
    def processar_solicitacoes(solicitacoes):
        for sc in solicitacoes:
            itens_pendentes = []
            sc.itens_completos = 0
            sc.total_itens = sc.itens.count()

            for item in sc.itens.all():
                # Acessa os recebimentos pré-buscados em memória, sem nova consulta
                total_recebido = sum(rec.quantidade_recebida for rec in item.recebimentos.all())
                
                if total_recebido < item.quantidade:
                    item.quantidade_pendente = item.quantidade - total_recebido
                    itens_pendentes.append(item)
                else:
                    sc.itens_completos += 1
            
            sc.itens_pendentes = itens_pendentes
            try:
                sc.fornecedor = sc.requisicao.cotacao_vencedora.fornecedor.nome_fantasia
            except:
                sc.fornecedor = "Não encontrado"
        return solicitacoes

    scs_a_receber = processar_solicitacoes(base_query.filter(status='a_caminho').order_by('data_criacao'))
    scs_parciais = processar_solicitacoes(base_query.filter(status='recebida_parcial').order_by('data_criacao'))

    context = {
        'scs_a_receber': scs_a_receber,
        'scs_parciais': scs_parciais,
        'search_query': search_query,
    }
    return render(request, 'materiais/registrar_recebimento.html', context)

@login_required
def iniciar_recebimento(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    user = request.user
    perfil = user.perfil

    # PERMISSÃO AMPLIADA PARA ENGENHEIRO
    if perfil not in ['almoxarife_obra', 'almoxarife_escritorio', 'diretor', 'engenheiro']:
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('materiais:dashboard')
    
    # Se for Almoxarife de Obra OU Engenheiro, verifica se a SC pertence a uma de suas obras
    if perfil in ['almoxarife_obra', 'engenheiro'] and solicitacao.obra not in user.obras.all():
        messages.error(request, 'Acesso negado a esta solicitação.')
        return redirect('materiais:registrar_recebimento')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                novo_recebimento = Recebimento.objects.create(
                    solicitacao=solicitacao,
                    recebedor=request.user,
                    observacoes=request.POST.get('observacoes', ''),
                    nota_fiscal=request.FILES.get('nota_fiscal'),
                    sc_assinada=request.FILES.get('sc_assinada'),
                    boleto_comprovante=request.FILES.get('boleto_comprovante')
                )
                itens_selecionados_ids = request.POST.getlist('itens_selecionados')
                for item_id in itens_selecionados_ids:
                    quantidade_str = request.POST.get(f'quantidade_recebida_{item_id}')
                    if quantidade_str and float(quantidade_str) > 0:
                        ItemRecebido.objects.create(
                            recebimento=novo_recebimento, item_solicitado_id=item_id,
                            quantidade_recebida=float(quantidade_str),
                            observacoes=request.POST.get(f'observacoes_{item_id}', '')
                        )

                total_itens_sc = solicitacao.itens.count()
                itens_completos = 0
                for item_solicitado in solicitacao.itens.all():
                    total_recebido_do_item = item_solicitado.recebimentos.aggregate(total=Sum('quantidade_recebida'))['total'] or 0
                    if total_recebido_do_item >= item_solicitado.quantidade:
                        itens_completos += 1
                
                if itens_completos == total_itens_sc:
                    solicitacao.status = 'recebida'
                    acao_historico = "Material Recebido (Total)"
                else:
                    solicitacao.status = 'recebida_parcial'
                    acao_historico = "Material Recebido (Parcial)"
                solicitacao.save()

                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao, usuario=request.user, acao=acao_historico,
                    detalhes=f"Recebimento de {len(itens_selecionados_ids)} item(ns) registrado."
                )
                
                messages.success(request, f'Recebimento da SC {solicitacao.numero} registrado com sucesso!')
                return redirect('materiais:registrar_recebimento')
        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao registrar o recebimento: {e}')

    itens_pendentes = []
    for item in solicitacao.itens.all():
        total_recebido = item.recebimentos.aggregate(total=Sum('quantidade_recebida'))['total'] or 0
        quantidade_pendente = item.quantidade - total_recebido
        if quantidade_pendente > 0:
            itens_pendentes.append({
                'id': item.id,
                'descricao': item.descricao,
                'quantidade_solicitada': f"{item.quantidade:g}",
                'quantidade_pendente': f"{quantidade_pendente:g}",
                'unidade': item.unidade,
            })
    
    context = {
        'sc': solicitacao,
        'itens_para_receber': itens_pendentes,
    }
    return render(request, 'materiais/iniciar_recebimento.html', context)

@login_required
def editar_solicitacao_analise(request, solicitacao_id):
    # Garante que apenas engenheiros e diretores possam usar esta função.
    if request.user.perfil not in ['engenheiro', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    # Busca a solicitação que está pendente de aprovação
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status='pendente_aprovacao')

    if request.method == 'POST':
        try:
            # A lógica para salvar os dados é a mesma da tela do escritório
            solicitacao.obra_id = request.POST.get('obra')
            solicitacao.destino_id = request.POST.get('destino') if request.POST.get('destino') else None
            solicitacao.data_necessidade = request.POST.get('data_necessidade')
            solicitacao.justificativa = request.POST.get('justificativa')
            solicitacao.is_emergencial = request.POST.get('is_emergencial') == 'on'
            solicitacao.categoria_sc_id = request.POST.get('categoria_sc')
            
            itens_json = request.POST.get('itens_json', '[]')
            itens_data = json.loads(itens_json)

            if not itens_data:
                messages.error(request, 'A solicitação deve ter pelo menos um item.')
                return redirect('materiais:analisar_editar_solicitacao', solicitacao_id=solicitacao.id)

            with transaction.atomic():
                # Remove os itens antigos para substituí-los pelos novos
                solicitacao.itens.all().delete()
                for item_data in itens_data:
                    item_catalogo = get_object_or_404(ItemCatalogo, id=item_data.get('item_id'))
                    ItemSolicitacao.objects.create(
                        solicitacao=solicitacao,
                        item_catalogo=item_catalogo,
                        descricao=item_catalogo.descricao,
                        unidade=item_catalogo.unidade.sigla,
                        categoria=str(item_catalogo.categoria),
                        quantidade=float(item_data.get('quantidade')),
                        observacoes=item_data.get('observacao')
                    )
                
                # *** PONTO CHAVE DA MUDANÇA ***
                # Ao salvar, o status muda para o próximo passo do fluxo do engenheiro.
                solicitacao.status = 'aprovado_engenharia'
                solicitacao.aprovador = request.user
                solicitacao.data_aprovacao = timezone.now()
                solicitacao.save()
                
                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao,
                    usuario=request.user,
                    acao="Aprovada com Edição",
                    detalhes="A solicitação foi editada e aprovada pelo engenheiro."
                )

            messages.success(request, f'Solicitação "{solicitacao.numero}" foi editada e aprovada com sucesso!')
            # Redireciona de volta para a lista de análise
            return redirect('materiais:analisar_solicitacoes')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao salvar as alterações: {e}')
            return redirect('materiais:analisar_editar_solicitacao', solicitacao_id=solicitacao.id)

    # A lógica para carregar a página (GET) é a mesma da tela do escritório
    itens_existentes = []
    for item in solicitacao.itens.all():
        itens_existentes.append({
            "item_id": item.item_catalogo_id, "descricao": item.descricao, "unidade": item.unidade,
            "quantidade": f"{item.quantidade:g}", "observacao": item.observacoes
        })
    
    context = {
        'solicitacao': solicitacao,
        'itens_existentes_json': json.dumps(itens_existentes),
        'obras': Obra.objects.filter(ativa=True).order_by('nome'),
        'itens_catalogo_json': json.dumps(list(ItemCatalogo.objects.filter(ativo=True).values('id', 'codigo', 'descricao', 'unidade__sigla'))),
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'destinos_entrega': DestinoEntrega.objects.all().order_by('nome'),
    }
    
    # *** PONTO CHAVE DA REUTILIZAÇÃO ***
    # Nós renderizamos o mesmo template que o escritório usa!
    return render(request, 'materiais/editar_solicitacao.html', context)

@login_required
def editar_fornecedor(request, fornecedor_id):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
    
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # DADOS BÁSICOS
                fornecedor.nome_fantasia = request.POST.get('nome_fantasia')
                fornecedor.razao_social = request.POST.get('razao_social')
                fornecedor.tipo = request.POST.get('tipo')
                
                # CONTATOS (Blindagem contra erro NOT NULL)
                fornecedor.email = request.POST.get('email', '')
                fornecedor.contato_nome = request.POST.get('contato_nome', '')
                fornecedor.contato_telefone = request.POST.get('contato_telefone', '')
                fornecedor.contato_whatsapp = request.POST.get('contato_whatsapp', '')
                
                # ENDEREÇO
                fornecedor.cep = request.POST.get('cep', '')
                fornecedor.logradouro = request.POST.get('logradouro', '')
                fornecedor.numero = request.POST.get('numero', '')
                fornecedor.bairro = request.POST.get('bairro', '')
                fornecedor.cidade = request.POST.get('cidade', '')
                fornecedor.estado = request.POST.get('estado', '').upper()
                
                fornecedor.save()

                # ATUALIZAÇÃO DE CATEGORIAS (MANY TO MANY)
                produtos_ids = request.POST.get('produtos_fornecidos', '')
                if produtos_ids:
                    ids_list = [int(x) for x in produtos_ids.split(',') if x.isdigit()]
                    # Se o seu modelo usa o campo 'categorias', o nome abaixo deve ser 'categorias'
                    # fornecedor.categorias.set(ids_list)
                
            messages.success(request, f'Fornecedor {fornecedor.nome_fantasia} atualizado com sucesso!')
            return redirect('materiais:gerenciar_fornecedores')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar: {e}')

    # Contexto para renderizar a página
    context = {
        'fornecedor': fornecedor,
        'categorias_principais': CategoriaItem.objects.filter(categoria_mae__isnull=True).order_by('nome'),
        'categorias_selecionadas_json': json.dumps([
            {'id': c.id, 'nome': c.nome} for c in fornecedor.categorias.all()
        ]) if hasattr(fornecedor, 'categorias') else "[]"
    }
    return render(request, 'materiais/editar_fornecedor.html', context)

@login_required
def editar_acesso_fornecedor(request, fornecedor_id):
    """View robusta para alterar credenciais de acesso."""
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        return JsonResponse({'success': False, 'message': 'Acesso negado.'}, status=403)
        
    if request.method == 'POST':
        fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
        user_fornecedor = fornecedor.usuarios_fornecedor.first()
        
        if not user_fornecedor:
            return JsonResponse({'success': False, 'message': 'Este fornecedor não possui um usuário vinculado.'})

        novo_username = request.POST.get('novo_username', '').strip()
        nova_senha = request.POST.get('nova_senha', '').strip()

        try:
            with transaction.atomic():
                if novo_username and novo_username != user_fornecedor.username:
                    if User.objects.filter(username=novo_username).exists():
                        return JsonResponse({'success': False, 'message': 'Este nome de utilizador já está em uso.'})
                    user_fornecedor.username = novo_username
                
                if nova_senha:
                    if len(nova_senha) < 6:
                        return JsonResponse({'success': False, 'message': 'A senha deve ter no mínimo 6 caracteres.'})
                    user_fornecedor.set_password(nova_senha)
                
                user_fornecedor.save()
                return JsonResponse({'success': True, 'message': 'Credenciais atualizadas com sucesso!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


# Nova View para Alteração de Status (ativar/inativar via AJAX)
@login_required
@csrf_exempt # Permite o POST simples via AJAX/fetch
def alterar_status_fornecedor(request, fornecedor_id):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        return JsonResponse({'success': False, 'message': 'Acesso negado.'}, status=403)
        
    if request.method == 'POST':
        fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
        novo_status_str = request.POST.get('ativo', 'false')
        
        # Converte a string 'true'/'false' em booleano
        novo_status = novo_status_str == 'true'

        try:
            fornecedor.ativo = novo_status
            fornecedor.save()
            
            acao = "Ativado" if novo_status else "Inativado"
            messages.success(request, f'Fornecedor {fornecedor.nome_fantasia} {acao} com sucesso!')
            return JsonResponse({'success': True})
        
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Método não permitido.'})

@login_required
def excluir_categoria_item(request, categoria_id):
    if request.method == 'POST':
        if request.user.perfil not in ['almoxarife_escritorio', 'diretor','almoxarife_obra','engenhairo']:
            messages.error(request, 'Acesso negado.')
            return redirect('materiais:dashboard')

        categoria = get_object_or_404(CategoriaItem, id=categoria_id)

        try:
            # Se for uma categoria principal (não tem pai)
            if categoria.categoria_mae is None:
                if categoria.subcategorias.exists():
                    messages.error(request, f'Não é possível excluir a categoria principal "{categoria.nome}", pois ela contém subcategorias.')
                else:
                    nome_categoria = categoria.nome
                    categoria.delete()
                    messages.success(request, f'Categoria principal "{nome_categoria}" excluída com sucesso.')
            # Se for uma subcategoria
            else:
                if ItemCatalogo.objects.filter(categoria=categoria).exists():
                    messages.error(request, f'Não é possível excluir a subcategoria "{categoria.nome}", pois ela está associada a itens do catálogo.')
                else:
                    nome_categoria = categoria.nome
                    categoria.delete()
                    messages.success(request, f'Subcategoria "{nome_categoria}" excluída com sucesso.')
        
        except Exception as e:
            messages.error(request, f"Ocorreu um erro ao tentar excluir: {e}")

    return redirect('materiais:gerenciar_categorias')

@login_required
def cotacao_agregado(request, solicitacao_id):
    sc_mae = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, "Acesso negado.")
        return redirect('materiais:gerenciar_cotacoes')
    
    item_solicitado = sc_mae.itens.first()
    is_agregado_valido = False
    if item_solicitado and item_solicitado.item_catalogo and item_solicitado.item_catalogo.categoria and item_solicitado.item_catalogo.categoria.categoria_mae:
        if item_solicitado.item_catalogo.categoria.categoria_mae.nome.lower() == 'agregados':
            is_agregado_valido = True

    if not is_agregado_valido:
        messages.error(request, "Esta solicitação não é válida para o fluxo de agregados.")
        return redirect('materiais:gerenciar_cotacoes')

    if request.method == 'POST':
        try:
            fornecedor_id = request.POST.get('fornecedor')
            preco_unitario_str = request.POST.get('preco_unitario', '0')
            
            quantidade_total = Decimal(request.POST.get('quantidade_total'))
            quantidade_particao = Decimal(request.POST.get('quantidade_particao'))
            
            fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
            preco_unitario = Decimal(preco_unitario_str)
            
            if quantidade_particao <= 0 or quantidade_total <= 0:
                raise ValueError("Quantidades devem ser maiores que zero.")

            num_particoes = int(quantidade_total / quantidade_particao)
            
            with transaction.atomic():
                # Criamos as entregas fracionadas (Filhas)
                for i in range(num_particoes):
                    sc_filha = SolicitacaoCompra.objects.create(
                        solicitante=sc_mae.solicitante, 
                        obra=sc_mae.obra,
                        data_necessidade=sc_mae.data_necessidade,
                        justificativa=f"Entrega {i+1}/{num_particoes} do pedido original {sc_mae.numero}.",
                        status='finalizada',
                        aprovador=request.user, 
                        data_aprovacao=timezone.now(),
                        sc_mae=sc_mae
                    )
                    
                    item_filho = ItemSolicitacao.objects.create(
                        solicitacao=sc_filha, 
                        item_catalogo=item_solicitado.item_catalogo,
                        descricao=item_solicitado.descricao, 
                        unidade=item_solicitado.unidade,
                        categoria=item_solicitado.categoria, 
                        quantidade=quantidade_particao
                    )
                    
                    cotacao = Cotacao.objects.create(
                        solicitacao=sc_filha, 
                        fornecedor=fornecedor,
                        vencedora=True, 
                        data_cotacao=timezone.now()
                    )
                    
                    ItemCotacao.objects.create(
                        cotacao=cotacao, 
                        item_solicitacao=item_filho, 
                        preco=preco_unitario
                    )
                    
                    RequisicaoMaterial.objects.create(
                        solicitacao_origem=sc_filha, 
                        cotacao_vencedora=cotacao,
                        valor_total=preco_unitario * quantidade_particao
                    )

                # --- CORREÇÃO DO BUG DE DUPLICIDADE ---
                # Definimos a SC mãe como 'desativada' para que ela não apareça 
                # nas listas de RMs pendentes ou cotações, pois o volume já foi 
                # totalmente processado pelas SCs filhas acima.
                sc_mae.status = 'desativada'
                sc_mae.save()

                HistoricoSolicitacao.objects.create(
                    solicitacao=sc_mae, 
                    usuario=request.user, 
                    acao="Processado como Agregado",
                    detalhes=f"Pedido de {quantidade_total} total dividido em {num_particoes} RMs de {quantidade_particao} cada."
                )

            messages.success(request, f"{num_particoes} RMs de agregado geradas. A SC mãe {sc_mae.numero} foi arquivada.")
            return redirect('materiais:gerenciar_requisicoes')

        except Exception as e:
            messages.error(request, f"Erro ao processar o pedido: {e}")

    context = {
        'solicitacao': sc_mae,
        'item': item_solicitado,
        'fornecedores': Fornecedor.objects.filter(ativo=True).order_by('nome_fantasia'),
    }
    return render(request, 'materiais/cotacao_agregado.html', context)

@login_required
def dividir_solicitacao_agregado(request, solicitacao_id):
    """
    Esta view identifica itens de agregado em uma SC mista,
    cria uma nova SC filha apenas com eles, e redireciona para o fluxo simplificado.
    """
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, "Acesso negado.")
        return redirect('materiais:gerenciar_cotacoes')

    sc_original = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)

    itens_agregados = []
    itens_comuns = []

    for item in sc_original.itens.all():
        is_agregado = False
        if item.item_catalogo and item.item_catalogo.categoria and item.item_catalogo.categoria.categoria_mae:
            if item.item_catalogo.categoria.categoria_mae.nome.lower() == 'agregados':
                is_agregado = True
        
        if is_agregado:
            itens_agregados.append(item)
        else:
            itens_comuns.append(item)

    # Se não houver itens de agregado ou comuns, não há o que dividir.
    if not itens_agregados or not itens_comuns:
        messages.warning(request, "Esta solicitação não precisa ser dividida.")
        return redirect('materiais:gerenciar_cotacoes')

    try:
        with transaction.atomic():
            # 1. Cria a nova SC filha para os agregados
            sc_filha_agregado = SolicitacaoCompra.objects.create(
                solicitante=sc_original.solicitante,
                obra=sc_original.obra,
                data_necessidade=sc_original.data_necessidade,
                justificativa=f"Itens de agregado separados da SC original {sc_original.numero}.",
                status='aprovada', # Já nasce pronta para o fluxo de agregado
                aprovador=request.user,
                data_aprovacao=timezone.now(),
                sc_mae=sc_original # Vincula à SC original
            )

            # 2. Move os itens de agregado da SC original para a nova SC filha
            for item_agregado in itens_agregados:
                item_agregado.solicitacao = sc_filha_agregado
                item_agregado.save()
            
            # 3. Adiciona histórico em ambas as SCs
            HistoricoSolicitacao.objects.create(
                solicitacao=sc_original, usuario=request.user, acao="SC Dividida",
                detalhes=f"Itens de agregado foram movidos para a nova SC {sc_filha_agregado.numero}."
            )
            HistoricoSolicitacao.objects.create(
                solicitacao=sc_filha_agregado, usuario=request.user, acao="Criação por Divisão",
                detalhes=f"Originada da SC mista {sc_original.numero}."
            )

            messages.success(request, f"A SC {sc_original.numero} foi dividida. Os itens de agregado estão na nova SC {sc_filha_agregado.numero}.")
            
            # 4. Redireciona para o fluxo simplificado da SC de agregado recém-criada
            return redirect('materiais:cotacao_agregado', solicitacao_id=sc_filha_agregado.id)

    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao tentar dividir a solicitação: {e}")
        return redirect('materiais:gerenciar_cotacoes')

@login_required
def api_item_check(request):
    """API para verificar duplicidade ou similaridade de item em tempo real."""
    # PERFIS CORRIGIDOS para incluir 'engenheiro', conforme a regra de acesso à função de cadastro.
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor', 'engenheiro','almoxarife_obra']:
        return JsonResponse({'status': 'denied', 'message': 'Acesso negado para esta função de API.'}, status=403)
        
    descricao = request.GET.get('descricao', '').strip()

    if not descricao:
        return JsonResponse({'status': 'ok', 'message': 'Descrição vazia.'})

    # 1. Verifica Duplicidade Exata (Case-Insensitive)
    if ItemCatalogo.objects.filter(descricao__iexact=descricao).exists():
        return JsonResponse({'status': 'exact_duplicate', 'message': '❌ Item idêntico já cadastrado no catálogo.'})

    # 2. Verifica Similaridade (Fuzzy Match, usando threshold de 0.6 para maior sensibilidade)
    itens_similares = []
    threshold = 0.6 # Valor ajustado anteriormente para maior sensibilidade
    for item_existente in ItemCatalogo.objects.only('codigo', 'descricao'):
        similaridade = similaridade_texto(descricao, item_existente.descricao)
        if similaridade >= threshold:
            itens_similares.append({
                'id': item_existente.id, 
                'codigo': item_existente.codigo,
                'descricao': item_existente.descricao,
                'similaridade': round(similaridade * 100, 1)
            })

    if itens_similares:
        return JsonResponse({
            'status': 'similar', 
            'message': 'Encontrado(s) item(ns) similar(es). Por favor, confirme o cadastro para evitar duplicidade.',
            'itens': itens_similares
        })

    return JsonResponse({'status': 'ok', 'message': 'Descrição única.'})

@login_required
def apagar_item(request, item_id):
    """View para apagar um item do catálogo."""
    PERFIS_PERMITIDOS = ['almoxarife_escritorio', 'diretor', 'engenheiro','almoxarife_obra']
    if request.user.perfil not in PERFIS_PERMITIDOS:
        messages.error(request, 'Você não tem permissão para apagar itens do catálogo.')
        return redirect('materiais:cadastrar_itens')

    item = get_object_or_404(ItemCatalogo, pk=item_id)

    # A exclusão só deve ser processada via POST (segurança)
    if request.method == 'POST':
        try:
            item.delete()
            messages.success(request, f'Item "{item.descricao}" (Código: {item.codigo}) apagado com sucesso do catálogo.')
            return redirect('materiais:cadastrar_itens')
        except Exception as e:
            messages.error(request, f'Erro ao apagar o item: {e}')
            return redirect('materiais:cadastrar_itens')

    # Caso alguém tente acessar via GET, redireciona com aviso
    messages.warning(request, 'A exclusão deve ser feita via POST (botão de apagar).')
    return redirect('materiais:cadastrar_itens')

# FUNÇÃO CORRIGIDA PARA SUBSTITUIR NO views.py
# No topo de materiais/views.py, adicione estas importações
from django.db.models import Q

import json
from django.db import transaction
from django.urls import reverse

# Novas importações necessárias

# (Todas as suas outras views, como login_view, dashboard, etc., devem estar aqui)
# ...

# No topo de materiais/views.py, adicione ou confirme que estas importações existem
from django.db.models import Q
from .models import CategoriaItem, UnidadeMedida # E outros modelos que você já usa
import math
# E substitua a sua função api_sugerir_categoria por esta versão completa e final:



@login_required
def api_subcategorias(request, categoria_id):
    # Certifique-se de que a importação de CategoriaItem está no cabeçalho
    subcategorias = CategoriaItem.objects.filter(categoria_mae_id=categoria_id).order_by('nome')
    data = [{'id': sub.id, 'nome': sub.nome} for sub in subcategorias]
    return JsonResponse(data, safe=False)

@login_required
def excluir_envio_cotacao(request, envio_id):
    """
    Remove um convite de cotação enviado a um fornecedor específico.
    BLINDAGEM: Bloqueia a exclusão se já existir um orçamento respondido.
    """
    if request.method == 'POST' and request.user.perfil in ['almoxarife_escritorio', 'diretor']:
        envio = get_object_or_404(EnvioCotacao, id=envio_id)
        solicitacao = envio.solicitacao
        fornecedor_nome = envio.fornecedor.nome_fantasia

        # --- BLINDAGEM: Verifica se já existe cotação respondida deste fornecedor ---
        cotacao_existente = solicitacao.cotacoes.filter(fornecedor=envio.fornecedor).exists()
        if cotacao_existente:
            messages.error(
                request, 
                f"Não é possível excluir o convite do fornecedor {fornecedor_nome} "
                f"pois já existe um orçamento respondido. Exclua primeiro o orçamento na aba 'Recebidas'."
            )
            return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=aguardando")

        with transaction.atomic():
            envio.delete()
            
            # Se não sobrar nenhum envio e nenhuma cotação, volta a SC para 'aprovada'
            if not solicitacao.envios_cotacao.exists() and not solicitacao.cotacoes.exists():
                solicitacao.status = 'aprovada'
                solicitacao.save()

            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=request.user,
                acao="Convite Removido",
                detalhes=f"O fornecedor {fornecedor_nome} foi removido da lista de cotação."
            )

        messages.success(request, f"Fornecedor {fornecedor_nome} removido com sucesso.")
        return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=aguardando")
    
    return redirect('materiais:gerenciar_cotacoes')

@login_required
def finalizar_coleta_precos(request, solicitacao_id):
    """
    Força a mudança de status da SC para 'cotacao_selecionada', 
    mesmo que nem todos os fornecedores tenham respondido.
    """
    if request.method == 'POST':
        solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
        
        # Verifica se existe pelo menos uma cotação registrada
        if solicitacao.cotacoes.exists():
            solicitacao.status = 'cotacao_selecionada'
            solicitacao.save()
            messages.success(request, f'Coleta de preços de "{solicitacao.nome_descritivo}" finalizada. Agora ela está disponível para análise final.')
        else:
            messages.error(request, 'Não é possível finalizar sem pelo menos um preço registrado.')
            
        return redirect('materiais:gerenciar_cotacoes')

@login_required
def api_detalhes_cotacao_recebida(request, cotacao_id):
    """Retorna itens detalhados de uma cotação específica."""
    cotacao = get_object_or_404(Cotacao, id=cotacao_id)
    itens = []
    
    # Busca os itens vinculados a esta cotação vencedora
    for ic in cotacao.itens_cotados.all():
        itens.append({
            'descricao': ic.item_solicitacao.descricao,
            'quantidade': f"{ic.item_solicitacao.quantidade:g}",
            'unidade': ic.item_solicitacao.unidade,
            'preco_unitario': f"R$ {ic.preco|floatformat:2}",
            'subtotal': f"R$ {(ic.preco * ic.item_solicitacao.quantidade)|floatformat:2}"
        })
    
    return JsonResponse({'success': True, 'itens': itens})

@login_required
def editar_acesso_fornecedor(request, fornecedor_id):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        return JsonResponse({'success': False, 'message': 'Acesso negado.'}, status=403)
        
    if request.method == 'POST':
        fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
        # Busca o primeiro utilizador vinculado a este fornecedor
        user_fornecedor = fornecedor.usuarios_fornecedor.first()
        
        if not user_fornecedor:
            return JsonResponse({'success': False, 'message': 'Nenhum utilizador encontrado para este fornecedor.'})

        novo_username = request.POST.get('novo_username')
        nova_senha = request.POST.get('nova_senha')

        try:
            with transaction.atomic():
                # Altera o utilizador (se não houver conflito)
                if novo_username and novo_username != user_fornecedor.username:
                    if User.objects.filter(username=novo_username).exists():
                        return JsonResponse({'success': False, 'message': 'Este nome de utilizador já existe.'})
                    user_fornecedor.username = novo_username
                
                # Altera a senha (se informada)
                if nova_senha:
                    user_fornecedor.set_password(nova_senha)
                
                user_fornecedor.save()
            
            messages.success(request, f'Credenciais de {fornecedor.nome_fantasia} atualizadas!')
            return redirect('materiais:gerenciar_fornecedores')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar: {e}')
            return redirect('materiais:gerenciar_fornecedores')

@login_required
def marcar_notificacao_lida(request, notificacao_id):
    notificacao = get_object_or_404(Notificacao, id=notificacao_id, usuario_destino=request.user)
    notificacao.lida = True
    notificacao.save()
    if notificacao.link:
        return redirect(notificacao.link)
    return redirect('materiais:dashboard')

@login_required
def dashboard_fornecedor(request):
    """
    Dashboard principal do portal do fornecedor com contadores de status
    e sistema de alertas/notificações internas.
    """
    # Verificação de segurança de perfil
    if request.user.perfil != 'fornecedor' or not request.user.fornecedor:
        messages.error(request, 'Acesso restrito ao portal do fornecedor.')
        return redirect('materiais:dashboard')

    fornecedor = request.user.fornecedor

    # 1. Cotações em Aberto (Vermelho): Convites sem preços registrados
    # CORREÇÃO: Incluído 'aprovada' para aceitar envios parciais
    abertas = EnvioCotacao.objects.filter(
        fornecedor=fornecedor,
        solicitacao__status__in=['aprovada', 'aguardando_resposta']
    ).exclude(
        solicitacao__cotacoes__fornecedor=fornecedor
    ).distinct()

    # 2. Cotações Enviadas (Amarelo): Aguardando decisão do comprador
    enviadas = Cotacao.objects.filter(
        fornecedor=fornecedor,
        solicitacao__status__in=['aprovada', 'aguardando_resposta']
    )

    # 3. Cotações Compradas (Verde): Onde este fornecedor venceu
    compradas = Cotacao.objects.filter(
        fornecedor=fornecedor,
        vencedora=True
    )

    # 4. Sistema de Alertas (Notificações Internas)
    # Buscamos as notificações não lidas para o contador
    notificacoes_queryset = NotificacaoFornecedor.objects.filter(
        fornecedor=fornecedor, 
        lida=False
    ).order_by('-data_criacao')

    context = {
        'count_abertas': abertas.count(),
        'count_enviadas': enviadas.count(),
        'count_compradas': compradas.count(),
        'novos_alertas': notificacoes_queryset.count(),  # Número para o "Sininho"
        'alertas_recentes': notificacoes_queryset[:5],  # Últimas 5 notificações para a lista
    }

    return render(request, 'materiais/dashboard_fornecedor.html', context)

@login_required
def responder_cotacao_fornecedor(request, solicitacao_id):
    # Localiza a solicitação e valida o perfil do fornecedor
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    fornecedor = getattr(request.user, 'fornecedor', None)

    if not fornecedor:
        messages.error(request, "Acesso restrito a fornecedores vinculados.")
        return redirect('materiais:dashboard')

    # Busca cotação existente para o caso de edição
    cotacao_existente = Cotacao.objects.filter(solicitacao=solicitacao, fornecedor=fornecedor).first()

    if request.method == 'POST':
        # --- 1. PROCESSAMENTO DO PRAZO DE ENTREGA ---
        aceita_prazo = request.POST.get('aceita_prazo')
        if aceita_prazo == 'sim':
            prazo_final = "Atende"
            motivo_prazo = "Dentro do prazo solicitado"
        else:
            # Captura o valor do input type="date" (Formato AAAA-MM-DD)
            data_raw = request.POST.get('prazo_entrega_data')
            if data_raw:
                # Converte para formato brasileiro para salvar como string no banco
                prazo_final = datetime.strptime(data_raw, '%Y-%m-%d').strftime('%d/%m/%Y')
            else:
                prazo_final = "Não informado"
            
            # Captura motivo: se for "Outro", pega o campo de texto livre
            motivo_prazo = request.POST.get('motivo_divergencia_prazo')
            if motivo_prazo == "Outro":
                motivo_prazo = request.POST.get('outro_motivo_prazo')

        # --- 2. PROCESSAMENTO DA CONDIÇÃO DE PAGAMENTO ---
        aceita_pgto = request.POST.get('aceita_pagamento')
        if aceita_pgto == 'sim':
            pgto_final = "Atende"
            motivo_pgto = "Conforme solicitado"
        else:
            forma_codigo = request.POST.get('nova_forma_pagamento')
            dias = request.POST.get('novo_prazo_dias')
            
            # Mapeamento de códigos para nomes formatados
            formas_pagamento_dict = {
                'avista': 'À Vista',
                'pix': 'Pix',
                'boleto': 'Boleto Bancário',
                'cartao_credito': 'Cartão de Crédito',
                'cartao_debito': 'Cartão de Débito',
                'transferencia': 'Transferência Bancária',
                'a_negociar': 'A Negociar',
            }
            
            forma_nome = formas_pagamento_dict.get(forma_codigo, forma_codigo.upper() if forma_codigo else 'Não especificado')
            # Estrutura a string de pagamento (ex: Boleto Bancário - 30 dias)
            pgto_final = f"{forma_nome} - {dias} dias" if forma_codigo and dias else "A combinar"
            
            # Captura justificativa: se for "Outro", pega o campo de texto livre
            motivo_pgto = request.POST.get('motivo_divergencia_pagamento')
            if motivo_pgto == "Outro":
                motivo_pgto = request.POST.get('outro_motivo_pagamento')

        # --- 3. CÁLCULO DA CONFORMIDADE (SEMÁFORO) ---
        conf = 'verde'
        # Verifica se o endereço de entrega é diferente do solicitado
        endereco_solicitado_id = solicitacao.destino_id if solicitacao.destino_id else solicitacao.obra_id
        endereco_cotacao_id = request.POST.get('endereco_entrega_id')
        endereco_divergente = False
        if endereco_cotacao_id:
            try:
                endereco_divergente = (int(endereco_cotacao_id) != endereco_solicitado_id)
            except (ValueError, TypeError):
                pass
        
        # VERMELHO: prazo divergente OU endereço divergente (urgência alta)
        if aceita_prazo == 'nao' or endereco_divergente:
            conf = 'vermelho' # Divergência de prazo ou endereço é crítica
        # AMARELO: apenas pagamento divergente (comercial)
        elif aceita_pgto == 'nao':
            conf = 'amarelo'  # Divergência de pagamento é comercial

        try:
            with transaction.atomic():
                # --- 4. SALVAMENTO DA COTAÇÃO ---
                # Define o endereço de entrega: se não foi enviado, usa o endereço solicitado original
                endereco_entrega_id = request.POST.get('endereco_entrega_id')
                if not endereco_entrega_id:
                    # Se fornecedor não informou, usa o endereço da SC (destino ou obra)
                    endereco_entrega_id = solicitacao.destino_id if solicitacao.destino_id else solicitacao.obra_id
                
                cotacao, created = Cotacao.objects.update_or_create(
                    solicitacao=solicitacao,
                    fornecedor=fornecedor,
                    defaults={
                        'prazo_entrega': prazo_final,
                        'condicao_pagamento': pgto_final,
                        'valor_frete': request.POST.get('valor_frete') or 0,
                        'endereco_entrega_id': endereco_entrega_id,
                        'conformidade': conf,
                        'motivo_divergencia_prazo': motivo_prazo,
                        'motivo_divergencia_pagamento': motivo_pgto,
                        'origem': 'portal',
                        'registrado_por': request.user,
                        # Salva o estado original para comparação no dashboard do escritório
                        'prazo_original_escritorio': solicitacao.data_necessidade.strftime('%d/%m/%Y'),
                        'pagamento_original_escritorio': f"{solicitacao.envios_cotacao.first().get_forma_pagamento_display()} / {solicitacao.envios_cotacao.first().prazo_pagamento} dias" if solicitacao.envios_cotacao.exists() else "Padronizado"
                    }
                )

                # --- 5. PROCESSAMENTO DOS PREÇOS DOS ITENS ---
                # CORREÇÃO CRÍTICA: Busca apenas os itens enviados PARA ESTE FORNECEDOR
                envio = EnvioCotacao.objects.filter(solicitacao=solicitacao, fornecedor=fornecedor).first()
                if not envio:
                    raise Exception("Envio de cotação não encontrado para este fornecedor.")
                
                # Processa apenas os itens que foram enviados para este fornecedor específico
                for item_sol in envio.itens.all():
                    preco_raw = request.POST.get(f'preco_{item_sol.id}')
                    if preco_raw:
                        # Limpa a formatação da máscara de dinheiro (remove pontos e troca vírgula por ponto)
                        preco_limpo = preco_raw.replace('.', '').replace(',', '.')
                        ItemCotacao.objects.update_or_create(
                            cotacao=cotacao,
                            item_solicitacao=item_sol,
                            defaults={'preco': float(preco_limpo)}
                        )
            
            messages.success(request, "Cotação registrada e enviada com sucesso!")
            return redirect('materiais:dashboard_fornecedor')

        except Exception as e:
            messages.error(request, f"Erro técnico ao salvar cotação: {str(e)}")

    # CORREÇÃO: Busca apenas os itens enviados para ESTE fornecedor específico
    envio = EnvioCotacao.objects.filter(solicitacao=solicitacao, fornecedor=fornecedor).first()
    itens_para_cotar = envio.itens.all() if envio else []
    
    context = {
        'solicitacao': solicitacao,
        'cotacao': cotacao_existente,
        'itens_para_cotar': itens_para_cotar,  # Apenas itens enviados para este fornecedor
        'envio_original': envio,
    }
    return render(request, 'materiais/responder_cotacao.html', context)

@login_required
def lista_cotacoes_fornecedor(request):
    if request.user.perfil != 'fornecedor' or not request.user.fornecedor:
        messages.error(request, 'Acesso restrito.')
        return redirect('materiais:dashboard')

    fornecedor = request.user.fornecedor
    filtro = request.GET.get('filtro') # Captura se é 'aberto' ou 'enviadas'

    # 1. CORREÇÃO: Busca todas as SCs onde o fornecedor foi convidado (incluindo envios parciais)
    # Não filtra mais por status específico - se há EnvioCotacao, o fornecedor pode responder!
    solicitacoes_base = SolicitacaoCompra.objects.filter(
        envios_cotacao__fornecedor=fornecedor,
        status__in=['aprovada', 'em_cotacao', 'aguardando_resposta']  # Incluído 'aprovada' para envios parciais
    ).distinct()

    # 2. Identifica quais já foram respondidas
    respondidas_ids = Cotacao.objects.filter(
        fornecedor=fornecedor
    ).values_list('solicitacao_id', flat=True)

    # 3. Aplica a lógica do filtro
    if filtro == 'aberto':
        solicitacoes = solicitacoes_base.exclude(id__in=respondidas_ids).order_by('-data_criacao')
        titulo_pagina = "Cotações em Aberto"
    elif filtro == 'enviadas':
        solicitacoes = solicitacoes_base.filter(id__in=respondidas_ids).order_by('-data_criacao')
        titulo_pagina = "Cotações Enviadas"
    else:
        solicitacoes = solicitacoes_base.order_by('-data_criacao')
        titulo_pagina = "Todas as Solicitações"

    context = {
        'solicitacoes': solicitacoes,
        'respondidas_ids': list(respondidas_ids),
        'titulo_pagina': titulo_pagina,
        'filtro_atual': filtro
    }
    return render(request, 'materiais/lista_cotacoes_fornecedor.html', context)

@login_required
def fornecedor_excluir_propria_cotacao(request, solicitacao_id):
    """Permite ao fornecedor excluir os preços enviados por ele ou pela construtora."""
    if request.method == 'POST' and request.user.perfil == 'fornecedor':
        solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
        fornecedor = request.user.fornecedor

        # Busca a cotação vinculada a este fornecedor
        cotacao = Cotacao.objects.filter(solicitacao=solicitacao, fornecedor=fornecedor).first()

        if cotacao:
            # Se a cotação já foi selecionada como vencedora, impede a exclusão
            if cotacao.vencedora:
                messages.error(request, "Esta cotação já foi finalizada pela construtora e não pode ser excluída.")
                return redirect('materiais:lista_cotacoes_fornecedor')

            nome_fornecedor = fornecedor.nome_fantasia
            with transaction.atomic():
                cotacao.delete()
                
                # Reverte o status da SC para aguardando_resposta
                solicitacao.status = 'aguardando_resposta'
                solicitacao.save()
                
                # Registra no histórico da SC que o fornecedor removeu os preços
                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao,
                    usuario=request.user,
                    acao="Preços Removidos pelo Fornecedor",
                    detalhes=f"O fornecedor {nome_fornecedor} excluiu sua proposta de preços. Status revertido para Em Aberto."
                )

            messages.success(request, "Seus preços foram removidos. Você pode enviar uma nova proposta quando desejar.")
        
        return redirect('materiais:lista_cotacoes_fornecedor')

    return redirect('materiais:dashboard_fornecedor')

@login_required
def lista_pedidos_fornecedor(request):
    if request.user.perfil != 'fornecedor' or not request.user.fornecedor:
        return redirect('materiais:dashboard')

    fornecedor = request.user.fornecedor
    
    # Filtra cotações que foram marcadas como vencedoras para este fornecedor
    pedidos_comprados = Cotacao.objects.filter(
        fornecedor=fornecedor,
        vencedora=True
    ).select_related('solicitacao__obra').order_by('-data_registro')

    context = {
        'pedidos': pedidos_comprados,
        'titulo_pagina': "Meus Pedidos (Cotações Compradas)"
    }
    return render(request, 'materiais/lista_pedidos_fornecedor.html', context)

@login_required
def marcar_notificacao_lida(request, notificacao_id):
    """
    Marca uma notificação específica como lida e redireciona o fornecedor
    para o link de destino (ex: a cotação ou o pedido).
    """
    # Garante que o fornecedor só consiga marcar como lida as suas próprias notificações
    notificacao = get_object_or_404(
        NotificacaoFornecedor, 
        id=notificacao_id, 
        fornecedor=request.user.fornecedor
    )
    
    notificacao.lida = True
    notificacao.save()
    
    # Se a notificação tiver um link, leva o utilizador até lá
    if notificacao.link:
        return redirect(notificacao.link)
        
    # Caso contrário, volta para o dashboard
    return redirect('materiais:dashboard_fornecedor')