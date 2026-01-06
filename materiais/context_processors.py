from .models import Notificacao

def notificacoes_globais(request):
    if request.user.is_authenticated:
        # Busca notificações não lidas para o utilizador logado
        notificacoes = Notificacao.objects.filter(usuario_destino=request.user, lida=False)[:5]
        count = Notificacao.objects.filter(usuario_destino=request.user, lida=False).count()
        return {
            'notificacoes_recentes': notificacoes,
            'notificacoes_count': count
        }
    return {}