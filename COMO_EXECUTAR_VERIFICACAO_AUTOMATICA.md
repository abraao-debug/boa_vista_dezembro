# ========================================
# GUIA: Como Executar Verificação Automática de Pendências
# ========================================

O comando `verificar_pendencias` precisa rodar automaticamente todos os dias.
Existem 3 formas de fazer isso:

---

## 📋 OPÇÃO 1: Task Scheduler do Windows (RECOMENDADO)

### Vantagens:
✅ Simples de configurar
✅ Não precisa instalar bibliotecas extras
✅ Funciona mesmo se o Django não estiver rodando
✅ Ideal para servidores Windows

### Como configurar:

1. **Abrir Task Scheduler**:
   ```
   Win + R → Digite: taskschd.msc → Enter
   ```

2. **Criar Nova Tarefa**:
   - Ações → Criar Tarefa Básica
   - Nome: "Verificar Pendências - Sistema Gestão"
   - Gatilho: Diariamente às 08:00
   - Ação: Iniciar programa
   - Programa: `C:\Users\Abraão\Desktop\Boa vista\Sistema Janeiro\boa_vista_dezembro\verificar_pendencias.bat`

3. **Configurações Avançadas** (aba Configurações):
   - ☑ Executar mesmo se usuário não estiver conectado
   - ☑ Executar com privilégios elevados
   - Se falhar, tentar novamente: 10 minutos (3 tentativas)

4. **Testar**:
   - Clique direito na tarefa → Executar
   - Verifique se apareceram notificações no sistema

---

## 🐍 OPÇÃO 2: APScheduler (Dentro do Django)

### Vantagens:
✅ Executa automaticamente enquanto Django roda
✅ Não depende do sistema operacional
✅ Fácil de debugar (logs aparecem no console)

### Como configurar:

1. **Instalar APScheduler**:
   ```powershell
   pip install APScheduler==3.10.4
   ```

2. **Arquivos já criados**:
   - ✅ `materiais/scheduler.py` (agendador)
   - ✅ `materiais/apps.py` (inicializador)

3. **Iniciar Django normalmente**:
   ```powershell
   python manage.py runserver
   ```
   
   O agendador inicia automaticamente e executa às 08:00!

4. **Ver logs**:
   ```
   🤖 Iniciando verificação automática de pendências...
   ✅ Verificação automática concluída com sucesso!
   ```

### Personalizar horários:

Edite `materiais/scheduler.py`:

```python
# Executar às 8h, 14h e 20h
scheduler.add_job(
    verificar_pendencias_automatico,
    trigger=CronTrigger(hour='8,14,20', minute=0),
    ...
)

# Executar a cada 4 horas
scheduler.add_job(
    verificar_pendencias_automatico,
    trigger=CronTrigger(hour='*/4'),
    ...
)

# Executar todos os dias úteis às 9h
from apscheduler.triggers.cron import CronTrigger
scheduler.add_job(
    verificar_pendencias_automatico,
    trigger=CronTrigger(day_of_week='mon-fri', hour=9, minute=0),
    ...
)
```

---

## 🐧 OPÇÃO 3: Cron Job (Linux/Ubuntu)

Se o servidor for Linux:

1. **Editar crontab**:
   ```bash
   crontab -e
   ```

2. **Adicionar linha**:
   ```bash
   0 8 * * * cd /caminho/projeto && /caminho/venv/bin/python manage.py verificar_pendencias
   ```

3. **Verificar**:
   ```bash
   crontab -l
   ```

---

## 🎯 QUAL USAR?

| Situação | Recomendação |
|----------|--------------|
| **Servidor Windows** | Task Scheduler (Opção 1) |
| **Desenvolvimento local** | APScheduler (Opção 2) |
| **Servidor Linux** | Cron Job (Opção 3) |
| **Quer simplicidade** | Task Scheduler (Opção 1) |
| **Quer controle total** | APScheduler (Opção 2) |

---

## 🔍 Verificar se está funcionando

### Task Scheduler:
1. Abra Task Scheduler
2. Procure "Verificar Pendências"
3. Clique direito → Histórico
4. Veja execuções passadas

### APScheduler:
1. Olhe o console do Django
2. Procure por: "🤖 Iniciando verificação automática"
3. Se não aparecer nada, pode não ter pendências

### Manualmente:
```powershell
python manage.py verificar_pendencias
```

---

## 📊 Logs e Monitoramento

### Ver últimas notificações criadas:
```python
from materiais.models import Notificacao
from django.utils import timezone
from datetime import timedelta

# Notificações das últimas 24h
Notificacao.objects.filter(
    data_criacao__gte=timezone.now() - timedelta(hours=24)
).order_by('-data_criacao')
```

### Ver pendências detectadas:
O comando exibe no console:
```
⚠ Prazo vencido: SC 2025-001 - Fornecedor X (5 dias)
⚠ RM pendente: RM-2025-001 - Almoxarife (3 dias)
✓ Lembrete enviado: SC 2025-002 (7 dias)
```

---

## 🛠️ Troubleshooting

### Tarefa não executa no Task Scheduler:
- Verifique se o caminho do .bat está correto
- Certifique-se que "Executar com privilégios elevados" está marcado
- Veja no Histórico se há erros

### APScheduler não inicia:
- Verifique se instalou: `pip install APScheduler`
- Confirme que `materiais/apps.py` tem o código do ready()
- Reinicie o Django: `Ctrl+C` e depois `python manage.py runserver`

### Notificações não aparecem:
- Execute manualmente: `python manage.py verificar_pendencias`
- Veja se há pendências reais (prazos vencidos, etc)
- Verifique tabela Notificacao no banco de dados

---

## 📝 Recomendação Final

Para **servidor de produção no Windows**:
→ Use **Task Scheduler** (Opção 1) - mais confiável

Para **desenvolvimento e testes**:
→ Use **APScheduler** (Opção 2) - mais conveniente

**Ambos funcionam perfeitamente!** Escolha o que for mais fácil para você.
