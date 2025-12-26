@echo off
REM Load environment variables from .env file
for /f "tokens=1* delims==" %%a in ('findstr /v "^#" "%~dp0..\.env"') do set %%a=%%b

REM Change to Navidrome directory
cd /d %NAVIDROME_DIR%

REM Start docker container
docker-compose up -d

REM Start caddy hidden + admin
powershell -Command "Start-Process -FilePath 'caddy' -ArgumentList 'run --config Caddyfile' -Verb runAs -WindowStyle Hidden"
exit
