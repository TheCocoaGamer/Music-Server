@echo off
REM Load environment variables from .env file
for /f "tokens=1* delims==" %%a in ('findstr /v "^#" "%~dp0..\.env"') do set %%a=%%b

REM Change to Navidrome directory
cd /d %NAVIDROME_DIR%
docker-compose down
caddy stop
