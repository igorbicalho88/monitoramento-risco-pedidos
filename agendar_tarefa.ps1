# Cria (ou atualiza) uma tarefa no Agendador de Tarefas do Windows que roda
# src\prever_novos.py a cada 5 minutos, sem abrir janela.
# Uso (na pasta do projeto):
#   powershell -ExecutionPolicy Bypass -File agendar_tarefa.ps1
#   powershell -ExecutionPolicy Bypass -File agendar_tarefa.ps1 -Minutos 15
param([int]$Minutos = 5)

$pasta  = $PSScriptRoot
$python = Join-Path $pasta ".venv\Scripts\pythonw.exe"
$script = Join-Path $pasta "src\prever_novos.py"
$nome   = "RiscoPedidos - Previsao"

if (-not (Test-Path $python)) { Write-Error "Ambiente .venv nao encontrado em $pasta"; exit 1 }

$acao    = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $pasta
$gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Minutos)
$config  = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
           -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho -Settings $config -Force `
    -Description "Calcula o risco de avaliacao negativa dos pedidos entregues (projeto monitoramento-risco-pedidos)." | Out-Null

Write-Host "Tarefa '$nome' criada: roda a cada $Minutos minuto(s)."
Write-Host "Acompanhe em logs\previsoes.log ou na tabela execucoes do banco."
