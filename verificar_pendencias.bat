@echo off
REM Script para executar verificação de pendências
REM Sistema de Gestão de Obra - Boa Vista

echo ========================================
echo   VERIFICACAO DE PENDENCIAS - FASE 2
echo ========================================
echo.

cd /d "C:\Users\Abraão\Desktop\Boa vista\Sistema Janeiro\boa_vista_dezembro"

echo Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo.
echo Executando verificacao de pendencias...
python manage.py verificar_pendencias

echo.
echo ========================================
echo   VERIFICACAO CONCLUIDA
echo ========================================
echo.

REM Pausar apenas se executado manualmente (não pelo Task Scheduler)
if "%1"=="" pause
