# 🚀 INSTALAÇÃO RÁPIDA - FASE 3

## ⚡ 3 Passos para Ativar

### 1️⃣ Instalar Dependências (1 minuto)

```bash
pip install APScheduler==3.10.4
pip install google-generativeai
```

**OU** (recomendado):
```bash
pip install -r requirements.txt
```

---

### 2️⃣ Executar Migrations (30 segundos)

```bash
python manage.py migrate
```

**Resultado esperado**:
```
Running migrations:
  Applying materiais.0028_configuracaowhatsapp_metricacotacao_comentariosc_sugestaoia... OK
```

---

### 3️⃣ Configurar Gemini AI (Opcional - 2 minutos)

**Editar**: `gestao_obra/settings.py`

Adicionar no final:
```python
# === FASE 3: API Gemini ===
GEMINI_API_KEY = 'sua-api-key-aqui'
```

**Obter API Key**:
1. Acessar: https://makersuite.google.com/app/apikey
2. Criar nova API Key
3. Copiar e colar no settings.py

**Nota**: Sistema funciona SEM API Key, mas justificativas IA serão padrão.

---

## ✅ Pronto! Iniciar Servidor

```bash
python manage.py runserver
```

**Logs esperados**:
```
System check identified no issues (0 silenced).
January 09, 2026 - 15:00:00
Django version 5.2.5, using settings 'gestao_obra.settings'
Starting development server at http://127.0.0.1:8000/

🚀 Agendador de tarefas FASE 3 iniciado!
📅 Tarefas agendadas:
  • Pendências: 08:00 (diário)
  • Métricas: 23:00 (diário)
  • WhatsApp: 08:00-18:00 (a cada 2h)
```

---

## 🧪 Testar Instalação (2 minutos)

### Teste 1: Dashboard de Métricas
```bash
# Gerar métricas
python manage.py calcular_metricas

# Acessar no navegador
http://localhost:8000/dashboard/metricas/
```

### Teste 2: Sugestões IA
```bash
python manage.py shell
```

```python
from materiais.ia_sugestoes import sugestao_ia_service
sugestoes = sugestao_ia_service.gerar_sugestoes(1, top_n=3)
print(f'✅ {len(sugestoes)} sugestões geradas!')
```

### Teste 3: Comentários
```python
from materiais.models import SolicitacaoCompra, ComentarioSC, User
sc = SolicitacaoCompra.objects.first()
usuario = User.objects.first()
comentario = ComentarioSC.objects.create(
    solicitacao=sc, autor=usuario, texto='Teste OK!'
)
print(f'✅ Comentário #{comentario.id} criado!')
```

---

## 🔧 Configuração WhatsApp (Opcional)

### Via Django Admin

1. **Acessar**: http://localhost:8000/admin/
2. **Login**: Usar credenciais de superuser
3. **Ir para**: Materiais → Configurações WhatsApp
4. **Adicionar nova**:
   - Ativo: ☐ (deixar desmarcado para teste)
   - API URL: `https://seu-servidor/v1/instance/123`
   - API Token: `seu-token-aqui`
   - Números: Adicionar números de teste
5. **Salvar**

### Testar Conexão

```python
from materiais.whatsapp_service import whatsapp_service
sucesso, msg = whatsapp_service.testar_conexao()
print(f'Status: {msg}')
```

---

## 📊 Acessar Funcionalidades

| Funcionalidade | URL |
|----------------|-----|
| Dashboard Principal | http://localhost:8000/dashboard/ |
| Dashboard Métricas | http://localhost:8000/dashboard/metricas/ |
| Admin Django | http://localhost:8000/admin/ |
| Gerenciar Cotações | http://localhost:8000/gerenciar-cotacoes/ |

---

## ❓ Problemas Comuns

### ❌ ImportError: No module named 'APScheduler'
```bash
pip install APScheduler==3.10.4
```

### ❌ ImportError: No module named 'google.generativeai'
```bash
pip install google-generativeai
```

### ❌ Scheduler não inicia
**Verificar**: Você está usando `python manage.py runserver`?  
**Nota**: Scheduler só inicia com runserver ou gunicorn.

### ❌ Dashboard de métricas vazio
**Normal!** Execute primeiro:
```bash
python manage.py calcular_metricas
```

### ❌ Sugestões IA sem justificativa personalizada
**Configurar**: Adicionar `GEMINI_API_KEY` no settings.py  
**Nota**: Funciona sem API Key, mas justificativa será padrão.

---

## 📋 Checklist de Verificação

Após instalação, verificar:

- [ ] Servidor inicia sem erros
- [ ] Aparece mensagem "Agendador iniciado" nos logs
- [ ] Dashboard de métricas carrega (pode estar vazio)
- [ ] Admin acessível em /admin/
- [ ] Pode criar comentários via shell
- [ ] Sugestões IA funcionam (mesmo sem API Key)

---

## 🎉 Instalação Completa!

**Próximos passos**:
1. ✅ Testar todas funcionalidades
2. ✅ Adicionar GEMINI_API_KEY (opcional)
3. ✅ Configurar WhatsApp (opcional)
4. ✅ Monitorar scheduler nos logs
5. ✅ Ver métricas diárias após 23:00

**Documentação completa**:
- [SISTEMA_COMPLETO.md](SISTEMA_COMPLETO.md) - Visão geral
- [FASE3_COMPLETO.md](FASE3_COMPLETO.md) - Detalhes técnicos
- [TESTE_RAPIDO_FASE3.md](TESTE_RAPIDO_FASE3.md) - Testes rápidos

---

**Sistema instalado com sucesso! 🚀**
