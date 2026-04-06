#!/bin/bash
# ─── Bot Financiero USD/ARS — Instalador Mac ───────────────────────────────
cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║      BOT FINANCIERO USD/ARS          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# 1. Verificar Python
if ! command -v python3 &>/dev/null; then
    echo "❌  Python no está instalado."
    echo ""
    echo "Instalalo desde: https://www.python.org/downloads/"
    echo "(descargá el botón amarillo grande 'Download Python')"
    echo ""
    read -p "Presioná Enter para cerrar..."
    exit 1
fi
echo "✅  Python encontrado: $(python3 --version)"

# 2. Verificar/crear .env con el token
if [ -f .env ] && grep -q "BOT_TOKEN=" .env && ! grep -q "tu-token" .env; then
    echo "✅  Token ya configurado."
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  PASO 1 — Crear el bot en Telegram"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  1. Abrí Telegram en tu celular o computadora"
    echo "  2. Buscá el contacto:  @BotFather"
    echo "  3. Escribile:  /newbot"
    echo "  4. Cuando te pida nombre, escribí por ej:  Financiera"
    echo "  5. Cuando te pida usuario, escribí por ej:  financiera_santi_bot"
    echo "     (tiene que terminar en 'bot' y no estar usado)"
    echo "  6. BotFather te va a dar un TOKEN, algo así:"
    echo "     123456789:AABBCCxxxxxxxxxxxxxxxxxxx"
    echo ""
    read -p "  Pegá el token acá y presioná Enter: " TOKEN
    if [ -z "$TOKEN" ]; then
        echo "❌  No ingresaste ningún token. Cerrando."
        read -p "Presioná Enter..."
        exit 1
    fi
    echo "BOT_TOKEN=$TOKEN" > .env
    echo "✅  Token guardado."
fi

# 3. Instalar dependencias
echo ""
echo "⏳  Instalando dependencias (solo la primera vez)..."
pip3 install python-telegram-bot==21.6 openpyxl==3.1.2 -q
if [ $? -ne 0 ]; then
    pip3 install python-telegram-bot openpyxl -q
fi
echo "✅  Dependencias instaladas."

# 4. Cargar token y arrancar
export $(cat .env | grep -v '#' | xargs)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PASO 2 — Agregar el bot a tu grupo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  1. Creá un grupo en Telegram con los 4 integrantes"
echo "  2. Agregá tu bot al grupo (buscalo por el nombre que le pusiste)"
echo "  3. En el grupo, mandá:  /inicio USD_inicial ARS_inicial"
echo "     Ejemplo:  /inicio 5000 500000"
echo ""
echo "  Operaciones que entiende el bot:"
echo "    compro Melania 3000 x 1350"
echo "    vendo Raul 5000 x 1382"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🤖  BOT INICIADO — no cierres esta ventana"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python3 bot.py
