# 🧪 TESTE RÁPIDO - FASE 3

## ⚡ Teste em 5 Minutos

### 1️⃣ Verificar Scheduler (30 segundos)

```bash
python manage.py runserver
```

**Deve aparecer no console**:
```
🚀 Agendador de tarefas FASE 3 iniciado!
📅 Tarefas agendadas:
  • Pendências: 08:00 (diário)
  • Métricas: 23:00 (diário)
  • WhatsApp: 08:00-18:00 (a cada 2h)
```

✅ **Se apareceu = APScheduler funcionando!**

---

### 2️⃣ Testar Cálculo de Métricas (1 minuto)

```bash
python manage.py calcular_metricas
```

**Deve mostrar**:
```
📊 Calculando métricas para 09/01/2026...

✅ Métricas calculadas com sucesso!

📅 Data: 09/01/2026
📦 SOLICITAÇÕES DE COMPRA:
  • Criadas hoje: X
  • Aprovadas hoje: X
  • Em cotação: X
  ...
```

✅ **Se calculou = Métricas funcionando!**

---

### 3️⃣ Acessar Dashboard (30 segundos)

**URL**: http://localhost:8000/dashboard/metricas/

**Deve mostrar**:
- 📊 Cards com números de SCs, cotações, etc.
- 📈 Tabela com histórico
- 👥 Ranking de fornecedores

✅ **Se carregou = Dashboard funcionando!**

---

### 4️⃣ Testar API de Sugestões (1 minuto)

**Console Python**:
```bash
python manage.py shell
```

```python
from materiais.ia_sugestoes import sugestao_ia_service

# Testar com primeira SC
sugestoes = sugestao_ia_service.gerar_sugestoes(solicitacao_id=1, top_n=3)

for s in sugestoes:
    print(f'{s.fornecedor.nome_fantasia}: Score {s.score_total:.1f}')
```

**Deve mostrar**:
```
ABC Materiais: Score 87.5
XYZ Construções: Score 82.3
...
```

✅ **Se gerou sugestões = IA funcionando!**

---

### 5️⃣ Testar Comentários (1 minuto)

**Console Python**:
```python
from materiais.models import SolicitacaoCompra, ComentarioSC, User

sc = SolicitacaoCompra.objects.first()
usuario = User.objects.first()

# Criar comentário
comentario = ComentarioSC.objects.create(
    solicitacao=sc,
    autor=usuario,
    texto='Teste de comentário FASE 3 funcionando!'
)

print(f'✅ Comentário #{comentario.id} criado!')
print(f'Total: {sc.comentarios.count()} comentários')
```

✅ **Se criou = Comentários funcionando!**

---

### 6️⃣ Testar WhatsApp (Opcional - 1 minuto)

**1. Configurar primeiro**:
- Acessar: http://localhost:8000/admin/materiais/configuracaowhatsapp/
- Criar nova configuração
- Marcar "Ativo" = False (para não enviar de verdade)
- Salvar

**2. Testar conexão**:
```python
from materiais.whatsapp_service import whatsapp_service

sucesso, mensagem = whatsapp_service.testar_conexao()
print(f'Status: {mensagem}')
```

**Se configurado**:
```
Status: Conexão OK: conectado
```

**Se não configurado**:
```
Status: Configuração não encontrada
```

✅ **Ambos estão corretos!**

---

## ✅ Checklist Final

- [ ] Scheduler iniciou automaticamente
- [ ] Comando calcular_metricas funciona
- [ ] Dashboard carrega sem erros
- [ ] API de sugestões gera scores
- [ ] Comentários são criados
- [ ] WhatsApp configurado (opcional)

---

## 🐛 Problemas Comuns

### ❌ "ModuleNotFoundError: No module named 'APScheduler'"
**Solução**:
```bash
pip install APScheduler==3.10.4
```

### ❌ "ModuleNotFoundError: No module named 'google.generativeai'"
**Solução**:
```bash
pip install google-generativeai
```

### ❌ Scheduler não inicia
**Verificar**: `materiais/apps.py` deve ter:
```python
def ready(self):
    if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0]:
        from . import scheduler
        scheduler.start()
```

### ❌ Dashboard vazio
**Normal se não houver dados!**
```bash
# Criar algumas métricas primeiro
python manage.py calcular_metricas
```

### ❌ Sugestões IA sem GEMINI_API_KEY
**Funciona parcial**: Gera scores, mas justificativa será padrão.
**Solução completa**: Adicionar `GEMINI_API_KEY` no settings.py

---

## 🎯 Teste Completo Passou?

Se TODOS os itens acima funcionaram:

✅ **FASE 3 está 100% operacional!**

### Você pode agora:
1. Usar dashboard de métricas diariamente
2. Ver sugestões IA ao convidar fornecedores
3. Adicionar comentários nas SCs
4. Receber notificações WhatsApp (se configurado)
5. Deixar o scheduler rodar automaticamente

---

## 📞 Suporte

**Dúvidas?**
- Ver documentação completa: [FASE3_COMPLETO.md](FASE3_COMPLETO.md)
- Ver resumo executivo: [FASE3_RESUMO.md](FASE3_RESUMO.md)

**Tudo funcionando?**
🎉 Parabéns! Sistema completo implementado! 🎉
