#!/usr/bin/env bash
# SYSTEM VERIFICATION SCRIPT - ПРОВЕРКА ВСЕ СИСТЕМ

echo "🔍 OZON REVIEW SERVICE - СИСТЕМА ПРОВЕРКИ"
echo "=========================================="
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Счётчики
PASSED=0
FAILED=0
WARNINGS=0

# Функция для вывода результата
check() {
    local test_name=$1
    local result=$2
    local message=$3
    
    if [ "$result" -eq 0 ]; then
        echo -e "${GREEN}✅${NC} $test_name"
        ((PASSED++))
    else
        if [ -n "$message" ] && [[ "$message" == "WARNING"* ]]; then
            echo -e "${YELLOW}⚠️${NC} $test_name - $message"
            ((WARNINGS++))
        else
            echo -e "${RED}❌${NC} $test_name"
            ((FAILED++))
        fi
    fi
}

echo "1️⃣  ПРОВЕРКА PYTHON ОКРУЖЕНИЯ"
echo "================================"

# Проверка Python
python --version > /dev/null 2>&1
check "Python установлен" $?

# Проверка virtualenv/conda (опционально)
if [ -d "venv" ] || [ -d ".venv" ]; then
    echo -e "${GREEN}✅${NC} Virtual environment найдена"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠️${NC} WARNING: Virtual environment не найдена"
    ((WARNINGS++))
fi

echo ""
echo "2️⃣  ПРОВЕРКА ЗАВИСИМОСТЕЙ"
echo "================================"

# Проверка requirements.txt
if [ -f "requirements.txt" ]; then
    check "requirements.txt существует" 0
    
    # Проверка основных пакетов
    python -c "import fastapi" > /dev/null 2>&1
    check "FastAPI установлен" $?
    
    python -c "import sqlalchemy" > /dev/null 2>&1
    check "SQLAlchemy установлен" $?
    
    python -c "import openai" > /dev/null 2>&1
    check "OpenAI клиент установлен" $?
    
    python -c "import httpx" > /dev/null 2>&1
    check "httpx установлен" $?
else
    echo -e "${RED}❌${NC} requirements.txt не найден"
    ((FAILED++))
fi

echo ""
echo "3️⃣  ПРОВЕРКА КОНФИГУРАЦИИ"
echo "================================"

# Проверка .env файла
if [ -f ".env" ]; then
    check ".env файл существует" 0
    
    # Проверка наличия переменных
    if grep -q "OZON_CLIENT_ID=" .env; then
        echo -e "${GREEN}✅${NC} OZON_CLIENT_ID переменная задана"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️${NC} OZON_CLIENT_ID не заполнена"
        ((WARNINGS++))
    fi
    
    if grep -q "OPENAI_API_KEY=" .env; then
        echo -e "${GREEN}✅${NC} OPENAI_API_KEY переменная задана"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️${NC} OPENAI_API_KEY не заполнена"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}❌${NC} .env файл не найден"
    ((FAILED++))
fi

echo ""
echo "4️⃣  ПРОВЕРКА ФАЙЛОВОЙ СТРУКТУРЫ"
echo "================================"

# Проверка основных файлов
check "main.py существует" $([ -f "main.py" ] && echo 0 || echo 1)
check "app/ директория существует" $([ -d "app" ] && echo 0 || echo 1)
check "app/database.py существует" $([ -f "app/database.py" ] && echo 0 || echo 1)
check "app/config.py существует" $([ -f "app/config.py" ] && echo 0 || echo 1)
check "app/services/ директория существует" $([ -d "app/services" ] && echo 0 || echo 1)
check "app/api/ директория существует" $([ -d "app/api" ] && echo 0 || echo 1)
check "app/models/ директория существует" $([ -d "app/models" ] && echo 0 || echo 1)
check "frontend/index.html существует" $([ -f "frontend/index.html" ] && echo 0 || echo 1)
check "Dockerfile существует" $([ -f "Dockerfile" ] && echo 0 || echo 1)
check "docker-compose.yml существует" $([ -f "docker-compose.yml" ] && echo 0 || echo 1)

echo ""
echo "5️⃣  ПРОВЕРКА API ENDPOINTS"
echo "================================"

if command -v curl &> /dev/null; then
    # Проверка health endpoint
    RESPONSE=$(curl -s http://localhost:8000/api/health/status 2>/dev/null)
    if echo "$RESPONSE" | grep -q "healthy"; then
        check "GET /api/health/status" 0
    else
        check "GET /api/health/status" 1 "WARNING: Cannot connect to server on localhost:8000"
    fi
    
    # Проверка integrations endpoint
    RESPONSE=$(curl -s http://localhost:8000/api/health/integrations 2>/dev/null)
    if echo "$RESPONSE" | grep -q "ozon_api"; then
        check "GET /api/health/integrations" 0
    else
        check "GET /api/health/integrations" 1 "WARNING: Cannot connect to server"
    fi
else
    echo -e "${YELLOW}⚠️${NC} curl не установлен, пропускаем проверку API"
    ((WARNINGS++))
fi

echo ""
echo "6️⃣  ПРОВЕРКА ДОКУМЕНТАЦИИ"
echo "================================"

check "README.md существует" $([ -f "README.md" ] && echo 0 || echo 1)
check "SETUP_GUIDE.md существует" $([ -f "SETUP_GUIDE.md" ] && echo 0 || echo 1)
check "VERIFICATION_CHECKLIST.md существует" $([ -f "VERIFICATION_CHECKLIST.md" ] && echo 0 || echo 1)
check "PROJECT_OVERVIEW.md существует" $([ -f "PROJECT_OVERVIEW.md" ] && echo 0 || echo 1)
check "QUICK_REFERENCE.md существует" $([ -f "QUICK_REFERENCE.md" ] && echo 0 || echo 1)
check "DEVELOPMENT.md существует" $([ -f "DEVELOPMENT.md" ] && echo 0 || echo 1)

echo ""
echo "=========================================="
echo "📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ:"
echo "=========================================="
echo -e "✅ Пройдено:    ${GREEN}$PASSED${NC}"
echo -e "⚠️  Предупреждения: ${YELLOW}$WARNINGS${NC}"
echo -e "❌ Ошибок:     ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ВСЕ СИСТЕМЫ ГОТОВЫ!${NC}"
    echo ""
    echo "Следующие шаги:"
    echo "1. Заполните .env файл с вашими API ключами:"
    echo "   - OZON_CLIENT_ID"
    echo "   - OZON_API_KEY"
    echo "   - OPENAI_API_KEY"
    echo ""
    echo "2. Запустите сервер: python main.py"
    echo ""
    echo "3. Откройте админ-панель: http://localhost:8000"
    echo ""
    echo "4. Нажмите на статус-индикаторы для тестирования подключений"
    echo ""
else
    echo -e "${RED}⚠️  НАЙДЕНЫ ПРОБЛЕМЫ!${NC}"
    echo "Пожалуйста, исправьте ошибки перед использованием."
fi

exit $FAILED
