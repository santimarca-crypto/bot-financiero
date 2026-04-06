@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════╗
echo ║      BOT FINANCIERO USD/ARS          ║
echo ╚══════════════════════════════════════╝
echo.

:: 1. Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌  Python no esta instalado.
    echo.
    echo Instalalо desde: https://www.python.org/downloads/
    echo Descarga el boton amarillo grande "Download Python"
    echo IMPORTANTE: al instalar, tilda la opcion "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
echo ✅  Python encontrado.

:: 2. Verificar/crear .env
if exist .env (
    findstr /C:"tu-token" .env >nul
    if errorlevel 1 (
        echo ✅  Token ya configurado.
        goto INSTALL
    )
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   PASO 1 — Crear el bot en Telegram
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo   1. Abri Telegram en tu celu o PC
echo   2. Busca el contacto:  @BotFather
echo   3. Escribile:  /newbot
echo   4. Nombre del bot, ej:  Financiera
echo   5. Usuario, ej:  financiera_santi_bot  (termina en 'bot')
echo   6. BotFather te da un TOKEN tipo:
echo      123456789:AABBCCxxxxxxxxxxxxxxxxxxx
echo.
set /p TOKEN="  Pega el token aca y presiona Enter: "
if "%TOKEN%"=="" (
    echo ❌  No ingresaste ningun token.
    pause
    exit /b 1
)
echo BOT_TOKEN=%TOKEN%> .env
echo ✅  Token guardado.

:INSTALL
echo.
echo ⏳  Instalando dependencias (solo la primera vez)...
pip install python-telegram-bot==21.6 openpyxl==3.1.2 -q
echo ✅  Dependencias instaladas.

:: Cargar token
for /f "tokens=1,2 delims==" %%a in (.env) do set %%a=%%b

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   PASO 2 — Agregar el bot a tu grupo
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo   1. Crea un grupo en Telegram con los 4 integrantes
echo   2. Agrega tu bot al grupo
echo   3. En el grupo manda:  /inicio 5000 500000
echo.
echo   Operaciones reconocidas:
echo     compro Melania 3000 x 1350
echo     vendo Raul 5000 x 1382
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   🤖  BOT INICIADO — no cierres esta ventana
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
python bot.py
pause
