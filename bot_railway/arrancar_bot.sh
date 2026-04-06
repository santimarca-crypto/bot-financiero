#!/bin/bash
# Arranca el bot (doble clic o desde terminal)
cd "$(dirname "$0")"

# Instalar dependencias si no están
pip install -r requirements.txt -q

# Cargar token desde .env
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

if [ -z "$BOT_TOKEN" ]; then
    echo ""
    echo "❌  Falta el BOT_TOKEN"
    echo ""
    echo "Pasos para obtenerlo:"
    echo "  1. Abrí Telegram y buscá @BotFather"
    echo "  2. Mandá /newbot"
    echo "  3. Seguí los pasos (elegís nombre y username del bot)"
    echo "  4. BotFather te da un token tipo: 123456:ABC-xxxxx"
    echo "  5. Copialo y pegalo en el archivo .env (está en esta carpeta)"
    echo "     Ejemplo:  BOT_TOKEN=123456:ABC-tu-token-acá"
    echo ""
    read -p "Presioná Enter para cerrar..."
    exit 1
fi

echo "✅  Token encontrado. Iniciando bot..."
python bot.py
