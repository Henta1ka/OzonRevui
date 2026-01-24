#!/bin/bash
# Скрипт развертывания Ozon Review Service на сервер

set -e

echo "=== Ozon Review Service Deployment Script ==="
echo "IP: 147.45.185.92"
echo "Domain: review-assistant.ru"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Проверка корневых прав
if [[ $EUID -ne 0 ]]; then
   error "Этот скрипт должен запускаться с sudo!"
fi

info "Обновление системы..."
apt update && apt upgrade -y

info "Установка зависимостей..."
apt install -y \
    python3.9 \
    python3-pip \
    git \
    curl \
    nginx \
    certbot \
    python3-certbot-nginx \
    supervisor

info "Клонирование репозитория..."
cd /opt || mkdir -p /opt && cd /opt
if [ -d "OzonRevui" ]; then
    info "Обновление существующего репо..."
    cd OzonRevui
    git pull origin main
    cd /opt
else
    git clone https://github.com/Henta1ka/OzonRevui.git
fi

cd /opt/OzonRevui/ozon-review-service

info "Создание виртуального окружения Python..."
python3.9 -m venv venv
source venv/bin/activate

info "Установка Python зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

info "Создание .env файла..."
cat > .env << 'EOF'
# Ozon API
OZON_CLIENT_ID=your_client_id
OZON_API_KEY=your_api_key

# OpenAI API
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-3.5-turbo

# YandexGPT API
YANDEX_API_KEY=your_yandex_key
YANDEX_FOLDER_ID=your_folder_id
YANDEX_MODEL=yandexgpt-3

# AI Provider (openai or yandex)
AI_PROVIDER=openai

# Database
DATABASE_URL=sqlite:///./ozon_reviews.db

# Response Settings
RESPONSE_TONE=friendly
RESPONSE_SIGNATURE=С уважением,\nКоманда маркетплейса

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Polling
POLLING_INTERVAL_MINUTES=30
EOF

warn "⚠️ ВАЖНО! Отредактируй .env файл с реальными ключами:"
warn "nano /opt/OzonRevui/ozon-review-service/.env"
echo ""
read -p "Нажми Enter когда отредактируешь .env файл..."

info "Создание системного сервиса..."
cat > /etc/systemd/system/ozon-service.service << 'EOF'
[Unit]
Description=Ozon Review Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/OzonRevui/ozon-review-service
Environment="PATH=/opt/OzonRevui/ozon-review-service/venv/bin"
ExecStart=/opt/OzonRevui/ozon-review-service/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

info "Включение сервиса в автозагрузку..."
systemctl daemon-reload
systemctl enable ozon-service
systemctl start ozon-service

info "Проверка статуса сервиса..."
sleep 2
if systemctl is-active --quiet ozon-service; then
    info "✅ Сервис запущен успешно!"
else
    error "❌ Сервис не запустился. Проверь ошибки:"
    systemctl status ozon-service
fi

info "Настройка Nginx..."
cat > /etc/nginx/sites-available/review-assistant.ru << 'EOF'
upstream ozon_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name review-assistant.ru;
    client_max_body_size 10M;

    location / {
        proxy_pass http://ozon_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # WebSocket поддержка если нужна
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static/ {
        alias /opt/OzonRevui/ozon-review-service/frontend/;
    }
}
EOF

# Включить сайт
ln -sf /etc/nginx/sites-available/review-assistant.ru /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Проверить конфиг Nginx
if nginx -t 2>&1 | grep -q "successful"; then
    info "Nginx конфиг OK"
    systemctl restart nginx
else
    error "Ошибка в конфиге Nginx"
fi

info "Настройка SSL сертификата через Let's Encrypt..."
certbot --nginx -d review-assistant.ru --non-interactive --agree-tos -m admin@review-assistant.ru

info ""
echo "========================================="
echo "✅ РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО УСПЕШНО!"
echo "========================================="
echo ""
echo "Сервис запущен на:"
echo "  🌐 https://review-assistant.ru"
echo "  📊 API: https://review-assistant.ru/api"
echo "  📚 Docs: https://review-assistant.ru/docs"
echo ""
echo "Полезные команды:"
echo "  Проверить статус: systemctl status ozon-service"
echo "  Просмотреть логи: journalctl -u ozon-service -f"
echo "  Отредактировать .env: nano /opt/OzonRevui/ozon-review-service/.env"
echo "  Перезапустить: systemctl restart ozon-service"
echo ""
echo "Следующие шаги:"
echo "  1. Отредактируй .env с реальными ключами (если еще не сделал)"
echo "  2. Проверь логи на ошибки"
echo "  3. Откройся https://review-assistant.ru и проверь"
echo ""
