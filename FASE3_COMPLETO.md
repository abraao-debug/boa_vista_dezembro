# FASE 3 - FUNCIONALIDADES AVANÇADAS - DOCUMENTAÇÃO COMPLETA

## 🎯 Resumo Executivo

A FASE 3 adiciona funcionalidades avançadas de inteligência artificial, análise de dados e automação ao sistema de gestão de materiais, transformando-o em uma plataforma completa e inteligente.

---

## 📋 Índice

1. [Novos Models](#novos-models)
2. [Sistema de Comentários](#sistema-de-comentários)
3. [Dashboard de Métricas](#dashboard-de-métricas)
4. [Sugestões IA com Gemini](#sugestões-ia-com-gemini)
5. [Notificações WhatsApp](#notificações-whatsapp)
6. [APScheduler Integrado](#apscheduler-integrado)
7. [Instalação e Configuração](#instalação-e-configuração)
8. [Testes e Validação](#testes-e-validação)

---

## 🗄️ Novos Models

### 1. ComentarioSC
**Propósito**: Sistema de comentários internos em Solicitações de Compra  
**Campos principais**:
- `solicitacao` - FK para SolicitacaoCompra
- `autor` - FK para User
- `texto` - Conteúdo do comentário
- `usuarios_mencionados` - ManyToMany (suporta @mencoes)
- `editado` - Boolean
- `data_criacao` - DateTime

**Funcionalidades**:
- ✅ Mencionar usuários com @username
- ✅ Notificações automáticas para mencionados
- ✅ Histórico completo de discussões
- ✅ Identificação de edições

### 2. MetricaCotacao
**Propósito**: Armazenamento de métricas diárias de desempenho  
**Campos principais**:
- `data` - Data da métrica (unique)
- `total_scs_*` - Contadores de SCs por status
- `total_cotacoes_*` - Contadores de cotações
- `tempo_medio_*` - Tempos médios em horas
- `taxa_resposta_fornecedores` - Percentual
- `fornecedores_mais_rapidos` - JSON com top 5
- `valor_total_cotado` - Decimal
- `economia_total` - Decimal

**Cálculo automático**: Diariamente às 23:00 via APScheduler

### 3. SugestaoIA
**Propósito**: Sugestões inteligentes de fornecedores usando Gemini AI  
**Campos principais**:
- `solicitacao` - FK para SC
- `fornecedor` - FK para Fornecedor
- `score_confiabilidade` - Float 0-100
- `score_preco` - Float 0-100
- `score_prazo` - Float 0-100
- `score_total` - Média ponderada
- `justificativa` - Texto gerado pela IA
- `aceita` - Boolean (se usuário seguiu sugestão)

**Algoritmo**:
- **Confiabilidade**: Taxa de resposta (60%) + Cumprimento de prazos (40%)
- **Preço**: Taxa de vitórias em cotações + Competitividade vs mercado
- **Prazo**: Tempo médio de resposta (24h = 100, 168h = 0)
- **Score Final**: Confiabilidade (40%) + Preço (35%) + Prazo (25%)

### 4. ConfiguracaoWhatsApp
**Propósito**: Configurações para integração WhatsApp  
**Campos principais**:
- `ativo` - Boolean
- `api_url` - URL da API (Evolution, WPPCONNECT, etc.)
- `api_token` - Token de autenticação
- `numero_almoxarife` - Telefone para notificações críticas
- `numero_diretor` - Telefone para notificações críticas
- `numero_engenheiro` - Telefone para notificações críticas
- `notificar_sc_urgente` - Boolean
- `notificar_cotacao_vencida` - Boolean
- `notificar_rm_pendente_7dias` - Boolean

**Eventos suportados**:
1. SC urgente (data necessária < 3 dias)
2. Cotação vencida há 2+ dias
3. RM pendente há 7+ dias

---

## 💬 Sistema de Comentários

### Funcionalidades

#### 1. Adicionar Comentário
**Endpoint**: `POST /sc/<sc_id>/comentarios/adicionar/`

**Parâmetros**:
```json
{
    "texto": "Preciso aprovar urgente @joao @maria"
}
```

**Resposta**:
```json
{
    "sucesso": true,
    "comentario": {
        "id": 123,
        "autor": "abraao",
        "texto": "Preciso aprovar urgente @joao @maria",
        "data": "09/01/2026 14:30"
    }
}
```

**Notificações automáticas**:
- ✅ Usuários mencionados (@username)
- ✅ Solicitante da SC
- ✅ Todos os diretores
- ✅ Engenheiro (se houver)

#### 2. Listar Comentários
**Endpoint**: `GET /sc/<sc_id>/comentarios/`

**Resposta**:
```json
{
    "comentarios": [
        {
            "id": 123,
            "autor": "abraao",
            "texto": "Preciso aprovar urgente",
            "data": "09/01/2026 14:30",
            "editado": false
        }
    ]
}
```

### Exemplo de Uso no Frontend (JavaScript)

```javascript
// Adicionar comentário
function adicionarComentario(scId, texto) {
    fetch(`/sc/${scId}/comentarios/adicionar/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: `texto=${encodeURIComponent(texto)}`
    })
    .then(res => res.json())
    .then(data => {
        console.log('Comentário adicionado:', data);
        carregarComentarios(scId);
    });
}

// Carregar comentários
function carregarComentarios(scId) {
    fetch(`/sc/${scId}/comentarios/`)
        .then(res => res.json())
        .then(data => {
            const lista = document.getElementById('comentarios-lista');
            lista.innerHTML = data.comentarios.map(c => `
                <div class="comentario">
                    <strong>${c.autor}</strong> - ${c.data}
                    <p>${c.texto}</p>
                </div>
            `).join('');
        });
}
```

---

## 📊 Dashboard de Métricas

### Acesso
**URL**: `/dashboard/metricas/`  
**Permissão**: Usuários autenticados (almoxarife_escritorio, diretor)

### Informações Exibidas

#### 1. Resumo Executivo (Cards)
- 📦 **SCs em Cotação**: Total atual
- ✉️ **Cotações Recebidas**: Do dia
- ⚠️ **Cotações Vencidas**: Sem resposta
- 👥 **Taxa de Resposta**: Percentual global

#### 2. Métricas de Tempo
- ⏱️ **Tempo Médio de Aprovação**: Horas da criação até aprovação diretor
- ⏱️ **Tempo Médio de Resposta**: Horas do envio até cotação recebida

#### 3. Métricas Financeiras
- 💵 **Valor Total Cotado**: Soma do dia
- 💰 **Economia Total**: Diferença entre maior e menor cotação aceita
- 📈 **Média por Cotação**: Valor médio

#### 4. Ranking de Fornecedores
- ⚡ **Top 5 Mais Rápidos**: Menor tempo médio de resposta
- 🐢 **Top 5 Mais Lentos**: Maior tempo médio de resposta

#### 5. Histórico (15 dias)
Tabela com:
- Data
- SCs criadas
- Cotações enviadas
- Cotações recebidas
- Taxa de resposta
- Valor total

### Comando de Cálculo Manual

```bash
# Calcular métricas de hoje
python manage.py calcular_metricas

# Calcular data específica
python manage.py calcular_metricas --data 2026-01-08
```

### Cálculo Automático
Configurado no `scheduler.py`:
- **Horário**: 23:00 (diariamente)
- **Trigger**: `CronTrigger(hour=23, minute=0)`

---

## 🤖 Sugestões IA com Gemini

### Configuração

#### 1. Obter API Key do Google
1. Acesse: https://makersuite.google.com/app/apikey
2. Crie uma API Key
3. Adicione ao `settings.py`:

```python
# settings.py
GEMINI_API_KEY = 'sua-api-key-aqui'
```

#### 2. Instalar Dependência
```bash
pip install google-generativeai
```

### Como Funciona

#### Análise de Fornecedor
O sistema analisa **últimos 6 meses** de cada fornecedor:

1. **Score de Confiabilidade (0-100)**:
   - Taxa de resposta: 60% do score
   - Cumprimento de prazos: 40% do score

2. **Score de Preço (0-100)**:
   - Taxa de vitórias em cotações
   - Competitividade vs média de mercado

3. **Score de Prazo (0-100)**:
   - Tempo médio de resposta
   - 24h = 100 pontos
   - 168h (7 dias) = 0 pontos

4. **Score Total**:
   - Confiabilidade: 40%
   - Preço: 35%
   - Prazo: 25%

#### Justificativa com IA
A IA Gemini analisa os scores e gera uma justificativa humanizada:

**Exemplo**:
> "Recomendado por: alta confiabilidade (92/100), preços competitivos (3 vitórias), respostas rápidas. Total de 28 cotações nos últimos 6 meses."

### API para Buscar Sugestões

**Endpoint**: `GET /api/sc/<sc_id>/sugestoes-fornecedores/`

**Resposta**:
```json
{
    "sugestoes": [
        {
            "fornecedor_id": 5,
            "fornecedor_nome": "Materiais ABC Ltda",
            "score_total": 87.5,
            "score_confiabilidade": 92.0,
            "score_preco": 85.0,
            "score_prazo": 83.0,
            "justificativa": "Fornecedor altamente confiável..."
        }
    ]
}
```

### Uso no Frontend (JavaScript)

```javascript
function carregarSugestoes(scId) {
    fetch(`/api/sc/${scId}/sugestoes-fornecedores/`)
        .then(res => res.json())
        .then(data => {
            const lista = document.getElementById('sugestoes-lista');
            lista.innerHTML = data.sugestoes.map(s => `
                <div class="sugestao-card">
                    <h5>${s.fornecedor_nome}</h5>
                    <div class="scores">
                        <span>Score Total: ${s.score_total}</span>
                        <span>Confiabilidade: ${s.score_confiabilidade}</span>
                        <span>Preço: ${s.score_preco}</span>
                        <span>Prazo: ${s.score_prazo}</span>
                    </div>
                    <p>${s.justificativa}</p>
                    <button onclick="selecionarFornecedor(${s.fornecedor_id})">
                        Selecionar
                    </button>
                </div>
            `).join('');
        });
}
```

### Cache de Sugestões
- Sugestões são válidas por **24 horas**
- Após 24h, são recalculadas automaticamente
- Evita sobrecarga da API Gemini

---

## 📱 Notificações WhatsApp

### APIs Suportadas
- ✅ Evolution API
- ✅ WPPCONNECT
- ✅ Baileys
- ✅ Venom Bot

### Configuração

#### 1. Configurar API WhatsApp
No Django Admin, acesse **Configuração WhatsApp**:

```
/admin/materiais/configuracaowhatsapp/
```

**Campos obrigatórios**:
- ✅ **Ativo**: Marcar como True
- ✅ **API URL**: Ex: `https://seu-servidor.com/v1/instance/123`
- ✅ **API Token**: Token de autenticação

**Números para notificações**:
- 📱 **Número Almoxarife**: 5511999999999
- 📱 **Número Diretor**: 5511888888888
- 📱 **Número Engenheiro**: 5511777777777

**Eventos para notificar**:
- ☑️ SC Urgente (< 3 dias)
- ☑️ Cotação Vencida (> 2 dias)
- ☑️ RM Pendente (> 7 dias)

#### 2. Testar Conexão

**Via API**:
```javascript
fetch('/api/whatsapp/testar/', {
    method: 'POST',
    headers: {'X-CSRFToken': getCookie('csrftoken')}
})
.then(res => res.json())
.then(data => {
    console.log('Status:', data.mensagem);
});
```

**Via Python**:
```python
from materiais.whatsapp_service import whatsapp_service

sucesso, mensagem = whatsapp_service.testar_conexao()
print(f'Conexão: {mensagem}')
```

### Eventos Automáticos

#### 1. SC Urgente
**Quando**: Data necessária em menos de 3 dias  
**Mensagem**:
```
🚨 SOLICITAÇÃO URGENTE

SC 2026-001
Obra: Centro Administrativo
Necessário: 12/01/2026
Itens: 5

⚠️ ATENÇÃO: Prazo curto! Iniciar cotação imediatamente.
```

**Destinatários**: Almoxarife + Diretor

#### 2. Cotação Vencida
**Quando**: Fornecedor não responde há 2+ dias  
**Mensagem**:
```
⏰ COTAÇÃO VENCIDA

SC 2026-001
Fornecedor: ABC Materiais Ltda
Prazo vencido há: 3 dia(s)

⚠️ Verificar com fornecedor ou buscar alternativas.
```

**Destinatários**: Almoxarife

#### 3. RM Pendente
**Quando**: Assinatura pendente há 7+ dias  
**Mensagem**:
```
📋 RM PENDENTE DE ASSINATURA

RM para SC 2026-001
Fornecedor: ABC Materiais Ltda
Valor: R$ 15.000,00
Criada há: 8 dias

⚠️ Assinaturas pendentes:
• Engenheiro
• Diretor
```

**Destinatários**: Diretor + Engenheiro

### Verificação Automática
Configurado no `scheduler.py`:
- **Horário**: A cada 2 horas (8h-18h)
- **Trigger**: `CronTrigger(hour='8-18/2')`
- **Executa**: 8h, 10h, 12h, 14h, 16h, 18h

---

## ⏰ APScheduler Integrado

### Tarefas Agendadas

#### 1. Verificação de Pendências (FASE 2)
- **Horário**: 08:00 (diariamente)
- **Função**: `verificar_pendencias_automatico()`
- **Ações**:
  - Verifica prazos de resposta vencidos
  - Verifica assinaturas pendentes > 3 dias
  - Envia lembretes de data necessária (7, 3, 1 dias)

#### 2. Cálculo de Métricas (FASE 3)
- **Horário**: 23:00 (diariamente)
- **Função**: `calcular_metricas_automatico()`
- **Ações**:
  - Calcula métricas do dia
  - Armazena em MetricaCotacao
  - Gera rankings de fornecedores

#### 3. Verificação WhatsApp (FASE 3)
- **Horário**: 08:00-18:00 (a cada 2h)
- **Função**: `verificar_whatsapp_automatico()`
- **Ações**:
  - Verifica SCs urgentes
  - Verifica cotações vencidas
  - Verifica RMs pendentes
  - Envia WhatsApp se configurado

### Arquivo: materiais/scheduler.py

```python
def start():
    """Inicia o agendador de tarefas com todas as rotinas."""
    scheduler = BackgroundScheduler()
    
    # FASE 2: Verificação de pendências
    scheduler.add_job(
        verificar_pendencias_automatico,
        trigger=CronTrigger(hour=8, minute=0),
        id='verificar_pendencias_diario',
        name='Verificação diária de pendências',
        replace_existing=True
    )
    
    # FASE 3: Cálculo de métricas
    scheduler.add_job(
        calcular_metricas_automatico,
        trigger=CronTrigger(hour=23, minute=0),
        id='calcular_metricas_diario',
        name='Cálculo diário de métricas',
        replace_existing=True
    )
    
    # FASE 3: Notificações WhatsApp
    scheduler.add_job(
        verificar_whatsapp_automatico,
        trigger=CronTrigger(hour='8-18/2'),
        id='verificar_whatsapp_periodico',
        name='Verificação periódica WhatsApp',
        replace_existing=True
    )
    
    scheduler.start()
```

### Inicialização Automática

**Arquivo**: `materiais/apps.py`

```python
def ready(self):
    """Executado quando o Django está pronto."""
    if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0]:
        from . import scheduler
        scheduler.start()
```

**Logs no Console**:
```
🚀 Agendador de tarefas FASE 3 iniciado!
📅 Tarefas agendadas:
  • Pendências: 08:00 (diário)
  • Métricas: 23:00 (diário)
  • WhatsApp: 08:00-18:00 (a cada 2h)
```

---

## 🚀 Instalação e Configuração

### 1. Instalar Dependências

```bash
pip install APScheduler==3.10.4
pip install google-generativeai
pip install requests  # já instalado
```

### 2. Executar Migrations

```bash
python manage.py migrate
```

**Resultado**:
```
Applying materiais.0028_configuracaowhatsapp_metricacotacao_comentariosc_sugestaoai... OK
```

### 3. Configurar Gemini AI

**Editar**: `gestao_obra/settings.py`

```python
# API do Google Gemini
GEMINI_API_KEY = 'sua-api-key-aqui'
```

**Obter API Key**: https://makersuite.google.com/app/apikey

### 4. Configurar WhatsApp (Opcional)

**Via Django Admin**: `/admin/materiais/configuracaowhatsapp/`

1. Criar nova configuração
2. Marcar **Ativo** = True
3. Preencher **API URL** e **API Token**
4. Adicionar números de telefone
5. Selecionar eventos para notificar

### 5. Iniciar Servidor

```bash
python manage.py runserver
```

**Logs esperados**:
```
System check identified no issues (0 silenced).
January 09, 2026 - 14:30:00
Django version 4.2.7, using settings 'gestao_obra.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.

🚀 Agendador de tarefas FASE 3 iniciado!
📅 Tarefas agendadas:
  • Pendências: 08:00 (diário)
  • Métricas: 23:00 (diário)
  • WhatsApp: 08:00-18:00 (a cada 2h)
```

---

## 🧪 Testes e Validação

### 1. Testar Comentários

```bash
# Via Python Shell
python manage.py shell
```

```python
from materiais.models import SolicitacaoCompra, ComentarioSC, User

sc = SolicitacaoCompra.objects.first()
usuario = User.objects.get(username='abraao')

# Criar comentário
comentario = ComentarioSC.objects.create(
    solicitacao=sc,
    autor=usuario,
    texto='Teste de comentário @joao'
)

print(f'Comentário #{comentario.id} criado!')
print(f'Total de comentários da SC: {sc.comentarios.count()}')
```

### 2. Testar Métricas

```bash
# Calcular métricas manualmente
python manage.py calcular_metricas
```

**Resultado esperado**:
```
📊 Calculando métricas para 09/01/2026...

✅ Métricas calculadas com sucesso!

📅 Data: 09/01/2026
📦 SOLICITAÇÕES DE COMPRA:
  • Criadas hoje: 3
  • Aprovadas hoje: 2
  • Em cotação: 5
  • Finalizadas: 12

💰 COTAÇÕES:
  • Enviadas hoje: 8
  • Recebidas hoje: 5
  • Vencidas (total): 2

⏱️ TEMPO:
  • Aprovação média: 12.5h
  • Resposta fornecedor: 28.3h

👥 FORNECEDORES:
  • Taxa de resposta: 75.0%
  • Mais rápidos:
    - ABC Materiais: 8.2h
    - XYZ Construções: 12.5h

💵 VALORES:
  • Total cotado hoje: R$ 45.230,00
  • Média por cotação: R$ 9.046,00
  • Economia total: R$ 3.450,00
```

### 3. Testar Sugestões IA

```python
from materiais.ia_sugestoes import sugestao_ia_service

# Gerar sugestões para uma SC
sugestoes = sugestao_ia_service.gerar_sugestoes(solicitacao_id=1, top_n=5)

for s in sugestoes:
    print(f'{s.fornecedor.nome_fantasia}: {s.score_total:.1f}')
    print(f'  Justificativa: {s.justificativa}')
```

### 4. Testar WhatsApp

**Via API**:
```bash
curl -X POST http://localhost:8000/api/whatsapp/testar/ \
  -H "X-CSRFToken: seu-token"
```

**Via Python**:
```python
from materiais.whatsapp_service import whatsapp_service

sucesso, mensagem = whatsapp_service.testar_conexao()
print(f'Status: {mensagem}')

# Enviar mensagem de teste
whatsapp_service.enviar_mensagem(
    numero='5511999999999',
    titulo='Teste Sistema',
    mensagem='Esta é uma mensagem de teste!'
)
```

### 5. Verificar Scheduler

**No console do runserver**, você verá:
```
🚀 Agendador de tarefas FASE 3 iniciado!
📅 Tarefas agendadas:
  • Pendências: 08:00 (diário)
  • Métricas: 23:00 (diário)
  • WhatsApp: 08:00-18:00 (a cada 2h)

🤖 Iniciando verificação automática de pendências...
✅ Verificação automática concluída com sucesso!
```

---

## 📈 Estatísticas FASE 3

### Novos Arquivos Criados
1. ✅ `materiais/models.py` - 4 novos models (150 linhas)
2. ✅ `materiais/ia_sugestoes.py` - Serviço de IA (300 linhas)
3. ✅ `materiais/whatsapp_service.py` - Serviço WhatsApp (250 linhas)
4. ✅ `materiais/scheduler.py` - Scheduler atualizado (80 linhas)
5. ✅ `materiais/views.py` - 7 novas views (150 linhas)
6. ✅ `materiais/templates/materiais/dashboard_metricas.html` - Dashboard (300 linhas)
7. ✅ `materiais/management/commands/calcular_metricas.py` - Comando (200 linhas)
8. ✅ `materiais/migrations/0028_*.py` - Migration automática

### Total de Código
- **Linhas de Python**: ~1.400
- **Linhas de HTML/JS**: ~300
- **Total**: ~1.700 linhas

### Funcionalidades
- ✅ Sistema de comentários com @mencoes
- ✅ Dashboard de métricas com gráficos
- ✅ Sugestões IA de fornecedores
- ✅ Notificações WhatsApp automáticas
- ✅ 3 tarefas agendadas no APScheduler
- ✅ 7 novas rotas de API
- ✅ 4 novos models no banco

---

## 🎓 Próximos Passos (FASE 4 - Opcional)

1. **Integração SMS**: Twilio ou similar
2. **Dashboard de Custos**: Análise detalhada de gastos por obra
3. **Previsão de Demanda**: Machine Learning para prever necessidades
4. **App Mobile**: React Native ou Flutter
5. **Gestão de Estoque**: Controle de entrada/saída
6. **Integração ERP**: SAP, TOTVS, etc.

---

## 🆘 Suporte

**Dúvidas sobre FASE 3?**
- Documentação de métricas: Ver `dashboard_metricas.html`
- Documentação de IA: Ver `ia_sugestoes.py`
- Documentação de WhatsApp: Ver `whatsapp_service.py`
- Scheduler: Ver `scheduler.py` e `apps.py`

**Contato**: Sistema desenvolvido para Boa Vista Obras - Janeiro 2026
