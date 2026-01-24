#!/bin/bash
# Скрипт для обновления кода на боевом сервере

set -e

echo "🔄 Обновление Ozon Review Service..."

cd /opt/OzonRevui/ozon-review-service

echo "📥 Получение обновлений из GitHub..."
git pull origin main

echo "📦 Обновление зависимостей Python..."
source venv/bin/activate
pip install -r requirements.txt

echo "🔄 Перезапуск сервиса..."
sudo systemctl restart ozon-service

echo "⏳ Ожидание запуска сервиса..."
sleep 2

if sudo systemctl is-active --quiet ozon-service; then
    echo "✅ Обновление завершено успешно!"
    echo "📊 Проверь статус: sudo systemctl status ozon-service"
else
    echo "❌ Ошибка при запуске сервиса!"
    echo "📋 Логи: sudo journalctl -u ozon-service -n 50"
    exit 1
fi
