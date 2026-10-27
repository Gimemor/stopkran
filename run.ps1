#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Локальная среда «Стоп-кран»: Postgres + pgAdmin + FastAPI через docker compose.

.EXAMPLE
  .\run.ps1              # поднять всё и дождаться готовности БД
  .\run.ps1 -Logs        # смотреть логи API
  .\run.ps1 -Down        # остановить (данные сохраняются)
  .\run.ps1 -Reset       # снести volume и поднять чистую БД
  .\run.ps1 -NoPgAdmin   # без pgAdmin
#>
[CmdletBinding()]
param(
    [switch]$Down,
    [switch]$Reset,
    [switch]$Logs,
    [switch]$NoPgAdmin
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# Чтобы русский текст корректно печатался в PowerShell 5.1
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Console]::OutputEncoding
} catch { }

$dbUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "stopkran" }
$dbName = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "stopkran" }
$pgAdminEmail = if ($env:PGADMIN_EMAIL) { $env:PGADMIN_EMAIL } else { "admin@example.com" }
$pgAdminPassword = if ($env:PGADMIN_PASSWORD) { $env:PGADMIN_PASSWORD } else { "admin" }

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker не найден в PATH. Установите Docker Desktop и перезапустите терминал."
    }
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon не отвечает. Запустите Docker Desktop."
    }
}

function Wait-ForDatabase {
    Write-Host "Ждём Postgres" -NoNewline
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        docker compose exec -T db pg_isready -U $dbUser -d $dbName *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host " — готово." -ForegroundColor Green
            return
        }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
    throw "Postgres не поднялся за 120 секунд. Логи: docker compose logs db"
}

Assert-Docker

if ($Down) {
    Write-Host "Останавливаю окружение (данные сохраняются)..." -ForegroundColor Yellow
    docker compose down
    exit $LASTEXITCODE
}

if ($Reset) {
    Write-Host "Удаляю контейнеры и volume с данными..." -ForegroundColor Yellow
    docker compose down -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$services = @("db", "api")
if (-not $NoPgAdmin) { $services += "pgadmin" }

Write-Host "Собираю и запускаю: $($services -join ', ')" -ForegroundColor Cyan
docker compose up -d --build $services
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose завершился с ошибкой. Частая причина — нет доступа к Docker Hub." -ForegroundColor Red
    exit $LASTEXITCODE
}

Wait-ForDatabase

if ($Logs) {
    docker compose logs -f api
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Готово. Локальная среда запущена:" -ForegroundColor Green
Write-Host "  API / Swagger : http://localhost:8000/docs"
Write-Host "  Лента (JSON)  : http://localhost:8000/api/feed"
Write-Host "  Postgres      : localhost:5432   db=$dbName user=$dbUser pass=stopkran"
Write-Host "  pgAdmin       : http://localhost:5050   $pgAdminEmail / $pgAdminPassword"
Write-Host ""
Write-Host "Фронтенд: index.html открывайте через локальный сервер, не file://"
Write-Host "  npx --yes serve -l 5500 .    →  http://localhost:5500"
Write-Host ""
Write-Host "Логи:  .\run.ps1 -Logs     Стоп:  .\run.ps1 -Down     Чистая БД:  .\run.ps1 -Reset"
