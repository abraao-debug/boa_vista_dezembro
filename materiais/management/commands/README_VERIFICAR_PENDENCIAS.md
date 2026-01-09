# Sistema de Notificações - Configuração de Tarefas Automáticas

## FASE 2 - Verificações Automáticas Implementadas

O comando `verificar_pendencias` foi criado para executar verificações automáticas e enviar notificações sobre:

1. **Prazos de resposta vencidos** - Cotações não respondidas após o prazo
2. **RMs com assinaturas pendentes** - Alertas quando há atrasos (>3 dias)
3. **Lembretes de data necessária** - Notificações 7, 3 e 1 dia antes

## Configuração no Windows (Task Scheduler)

### Passo 1: Criar arquivo batch

Crie um arquivo `verificar_pendencias.bat` na pasta do projeto:

```batch
@echo off
cd /d "C:\Users\Abraão\Desktop\Boa vista\Sistema Janeiro\boa_vista_dezembro"
call venv\Scripts\activate.bat
python manage.py verificar_pendencias
```

### Passo 2: Configurar Agendador de Tarefas do Windows

1. Abra o **Agendador de Tarefas** (Task Scheduler)
2. Clique em "Criar Tarefa Básica"
3. Configure:
   - **Nome**: Verificar Pendências - Sistema Gestão Obra
   - **Gatilho**: Diariamente às 8:00
   - **Ação**: Iniciar um programa
   - **Programa**: `C:\Users\Abraão\Desktop\Boa vista\Sistema Janeiro\boa_vista_dezembro\verificar_pendencias.bat`

### Passo 3: Configurações avançadas (recomendado)

- ☑ Executar se o usuário estiver conectado ou não
- ☑ Executar com privilégios mais altos
- ☑ Configurar para: Windows 10

## Teste Manual

Para testar o comando manualmente:

```powershell
cd "C:\Users\Abraão\Desktop\Boa vista\Sistema Janeiro\boa_vista_dezembro"
.\venv\Scripts\Activate.ps1
python manage.py verificar_pendencias
```

## Frequência Recomendada

- **Produção**: 1x por dia (8:00 da manhã)
- **Desenvolvimento/Teste**: Executar manualmente conforme necessário

## Logs

O comando exibe no console:
- ✓ Lembretes enviados com sucesso
- ⚠ Pendências detectadas (prazos vencidos, assinaturas atrasadas)
- ✗ Erros durante a execução

## Proteção Anti-Spam

O sistema verifica automaticamente se já enviou notificação nas últimas 24 horas para evitar:
- Duplicação de alertas
- Sobrecarga de notificações
- Spam para usuários

## Manutenção

Para ajustar os parâmetros:

1. **Dias de antecedência para lembretes**: Edite a lista `dias_antecedencia` em `verificar_pendencias.py`
2. **Limite de dias para assinaturas**: Altere `limite_dias = 3` no método `verificar_assinaturas_pendentes()`
3. **Intervalo de proteção anti-spam**: Ajuste `timedelta(hours=24)` nas verificações

## Desativar Verificações

Para desativar temporariamente:
1. Desabilite a tarefa no Agendador de Tarefas
2. Ou comente as linhas no método `handle()` do comando

## Troubleshooting

**Problema**: Comando não executa automaticamente
- Verifique se o caminho no .bat está correto
- Confirme que o Python está no PATH do sistema
- Teste o .bat manualmente clicando duas vezes

**Problema**: Notificações não aparecem
- Verifique se há registros no banco de dados (tabela `materiais_notificacao`)
- Confirme que os usuários têm os perfis corretos
- Execute com `--verbosity 2` para mais detalhes

**Problema**: Muitas notificações
- Reduza a frequência de execução
- Aumente o período de proteção anti-spam (atualmente 24h)
