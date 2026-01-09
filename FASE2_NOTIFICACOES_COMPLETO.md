# FASE 2 - NOTIFICAÇÕES SECUNDÁRIAS - DOCUMENTAÇÃO COMPLETA

## Resumo da Implementação

A FASE 2 adiciona 11 notificações secundárias importantes ao sistema de gestão de materiais, complementando as 7 notificações críticas da FASE 1.

---

## Notificações Implementadas

### ✅ 1. Cotação Rejeitada
**Função**: `rejeitar_cotacao()` - linha ~846
**Quando**: Almoxarife ou diretor rejeita uma cotação recebida
**Quem recebe**:
- Fornecedor (via NotificacaoFornecedor) - pode enviar nova proposta
- Almoxarife de escritório - rastreamento
- Diretor - visibilidade

**Exemplo de mensagem**:
> "Sua cotação para SC 2025-001 foi rejeitada. Você pode enviar nova proposta."

---

### ✅ 2. Prazo de Resposta Vencido
**Função**: Command `verificar_pendencias.py` (automático)
**Quando**: Fornecedor não responde cotação após prazo estipulado
**Quem recebe**:
- Almoxarife de escritório - ação necessária
- Diretor - visibilidade

**Exemplo de mensagem**:
> "SC 2025-001: Fornecedor X não respondeu há 5 dia(s)."

**Configuração**:
- Execução: Diária via Task Scheduler
- Proteção: Não notifica mais de 1x por 24h para mesma SC

---

### ✅ 3. Cotação Parcial Registrada
**Função**: `iniciar_cotacao()` - linha ~670
**Quando**: Registram cotação manualmente com apenas alguns itens
**Quem recebe**:
- Almoxarife de escritório - acompanhamento

**Exemplo de mensagem**:
> "SC 2025-001: Apenas 3 de 5 itens foram cotados por Fornecedor X."

---

### ✅ 4. RM com Assinatura Pendente
**Função**: Command `verificar_pendencias.py` (automático)
**Quando**: RM está aguardando assinatura há mais de 3 dias
**Quem recebe**:
- Almoxarife de escritório (se pendente com ele)
- Diretor (se pendente com ele)

**Exemplo de mensagem**:
> "RM RM-2025-001 aguarda sua assinatura há 5 dias. Priorize!"

**Configuração**:
- Limite: 3 dias de atraso
- Execução: Diária
- Proteção: Não notifica mais de 1x por 24h

---

### ✅ 5. Material Recebido Parcialmente
**Função**: `iniciar_recebimento()` - linha ~3180
**Quando**: Almoxarife registra recebimento parcial dos materiais
**Quem recebe**:
- Solicitante - acompanhamento
- Engenheiro da obra - rastreamento
- Almoxarife de escritório - visibilidade

**Exemplo de mensagem**:
> "Parte dos materiais da sua SC 2025-001 foi recebida (3/5 itens completos)."

---

### ✅ 6. Material Recebido Totalmente
**Função**: `iniciar_recebimento()` - linha ~3180
**Quando**: Todos os materiais da SC foram recebidos
**Quem recebe**:
- Solicitante - conclusão do processo
- Engenheiro da obra - material disponível
- Almoxarife de escritório - encerramento

**Exemplo de mensagem**:
> "Todos os materiais da sua SC 2025-001 foram recebidos."

---

### ✅ 7. Novo Comentário em SC
**Status**: Não Aplicável
**Motivo**: Sistema de comentários não implementado no projeto atual
**Recomendação**: Implementar futuramente se houver necessidade

---

### ✅ 8. SC Editada após Aprovação
**Função**: `editar_solicitacao_escritorio()` - linha ~2188
**Quando**: Almoxarife edita SC já aprovada (antes de iniciar cotação)
**Quem recebe**:
- Solicitante - ciência das alterações
- Diretor - visibilidade
- Engenheiro responsável pela obra - atualização

**Exemplo de mensagem**:
> "Sua SC 2025-001 foi editada por João Silva. Revise as alterações."

---

### ✅ 9. Fornecedor Visualizou Cotação
**Função**: `lista_cotacoes_fornecedor()` - linha ~4183
**Quando**: Fornecedor acessa o portal de cotações
**Quem recebe**:
- Almoxarife de escritório - engajamento do fornecedor

**Exemplo de mensagem**:
> "Fornecedor X acessou o portal de cotações."

**Configuração**:
- Proteção: Máximo 1 notificação por 24h por fornecedor
- Evita spam quando fornecedor acessa múltiplas vezes

---

### ✅ 10. Lembretes Automáticos
**Função**: Command `verificar_pendencias.py` (automático)
**Quando**: X dias antes da data necessária da SC
**Quem recebe**:
- Solicitante - preparação
- Almoxarife de escritório - urgência
- Engenheiro da obra - planejamento

**Dias de antecedência**: 7, 3 e 1 dia antes

**Exemplo de mensagem**:
> "Sua SC 2025-001 tem data necessária em 3 dia(s). Status atual: Em Cotação."

**Configuração**:
- Execução: Diária
- Aplica a SCs não finalizadas
- Proteção: 1 notificação por dia por SC

---

### ✅ 11. Status "A Caminho" Atualizado
**Status**: Já implementado na FASE 1
**Função**: `enviar_rm_fornecedor()` - linha ~2828
**Quando**: RM é enviada ao fornecedor
**Quem recebe**:
- Fornecedor - material deve ser providenciado
- Solicitante - material em processo
- Engenheiro - material a caminho
- Almoxarife da obra - preparar para recebimento

---

## Sistema de Verificação Automática

### Comando Django: `verificar_pendencias`

**Localização**: `materiais/management/commands/verificar_pendencias.py`

**O que verifica**:
1. Prazos de resposta vencidos
2. Assinaturas pendentes há mais de 3 dias
3. Datas necessárias próximas (7, 3, 1 dia)

**Como executar manualmente**:
```powershell
python manage.py verificar_pendencias
```

**Execução automática**:
- Via Task Scheduler do Windows
- Arquivo: `verificar_pendencias.bat`
- Frequência recomendada: Diariamente às 8:00

### Proteção Anti-Spam

Todas as verificações automáticas incluem:
- Verificação de última notificação enviada
- Intervalo mínimo de 24h entre notificações similares
- Evita duplicações e sobrecarga

---

## Configuração do Agendador

### Windows Task Scheduler

1. **Criar tarefa**:
   - Nome: "Verificar Pendências - Sistema Gestão Obra"
   - Gatilho: Diariamente às 8:00
   - Ação: Executar `verificar_pendencias.bat`

2. **Configurações avançadas**:
   - ☑ Executar se usuário estiver conectado ou não
   - ☑ Executar com privilégios elevados
   - ☑ Configurar para Windows 10

3. **Teste**:
   - Execute manualmente clicando com botão direito > Executar
   - Verifique logs de execução na aba Histórico

---

## Parâmetros Ajustáveis

### Dias de antecedência para lembretes
**Arquivo**: `verificar_pendencias.py` linha ~170
```python
dias_antecedencia = [7, 3, 1]  # Modificar conforme necessário
```

### Limite de dias para assinaturas pendentes
**Arquivo**: `verificar_pendencias.py` linha ~112
```python
limite_dias = 3  # Aumentar ou diminuir conforme política
```

### Proteção anti-spam
**Arquivo**: `verificar_pendencias.py` (múltiplas linhas)
```python
data_criacao__gte=timezone.now() - timedelta(hours=24)  # Ajustar intervalo
```

---

## Testes Recomendados

### 1. Teste de Cotação Rejeitada
1. Acesse gerenciar cotações
2. Rejeite uma cotação recebida
3. Verifique notificações do fornecedor, almoxarife e diretor

### 2. Teste de Recebimento
1. Registre recebimento parcial de uma SC
2. Verifique notificações enviadas
3. Complete o recebimento e verifique notificações finais

### 3. Teste de SC Editada
1. Edite uma SC aprovada
2. Verifique se solicitante e diretor receberam notificação

### 4. Teste de Verificação Automática
```powershell
python manage.py verificar_pendencias
```
Verifique console para ver pendências detectadas

---

## Estatísticas da FASE 2

- **Total de notificações implementadas**: 10 (1 não aplicável)
- **Notificações manuais**: 5
- **Notificações automáticas**: 3
- **Já implementadas na FASE 1**: 1
- **Sistema de verificação**: 1 comando Django
- **Proteção anti-spam**: 100% das notificações automáticas

---

## Próximos Passos (FASE 3)

1. **Integração com Gemini AI**: Sugestões inteligentes de fornecedores
2. **Dashboard de métricas**: Tempo médio de cotação, taxa de resposta
3. **Notificações via WhatsApp/SMS**: Para urgências críticas
4. **Sistema de comentários**: Implementar para habilitar notificação 7

---

## Suporte e Manutenção

**Visualizar notificações no banco**:
```sql
SELECT * FROM materiais_notificacao 
WHERE data_criacao >= CURRENT_DATE 
ORDER BY data_criacao DESC;
```

**Limpar notificações antigas** (>90 dias):
```python
from materiais.models import Notificacao
from django.utils import timezone
from datetime import timedelta

Notificacao.objects.filter(
    data_criacao__lt=timezone.now() - timedelta(days=90)
).delete()
```

**Estatísticas de notificações**:
```python
from materiais.models import Notificacao
from django.db.models import Count

Notificacao.objects.values('titulo').annotate(
    total=Count('id')
).order_by('-total')
```

---

## Contato

Para dúvidas ou sugestões sobre o sistema de notificações:
- Documentação completa em `/materiais/management/commands/README_VERIFICAR_PENDENCIAS.md`
- Configuração do comando em `verificar_pendencias.py`
- Helpers de notificação em `views.py` linhas 35-170
