#!/bin/bash
# Quick Start Script for Ozon Review Service

echo "🚀 Ozon Review Service - Quick Start"
echo "====================================="
echo ""

# Check Python
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.9+"
    exit 1
fi

echo "✅ Python found: $(python --version)"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

echo ""

# Activate virtual environment
echo "🔧 Activating virtual environment..."
if [ -f "venv/Scripts/activate" ]; then
    # Windows
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    # Linux/Mac
    source venv/bin/activate
fi

echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "📚 Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Create .env if doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys!"
    echo ""
    cat .env
else
    echo "✅ .env file already exists"
fi

echo ""
echo "🎯 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API credentials:"
echo "   - OZON_CLIENT_ID"
echo "   - OZON_API_KEY"
echo "   - OPENAI_API_KEY"
echo ""
echo "2. Run the server:"
echo "   python main.py"
echo ""
echo "3. Open in browser:"
echo "   http://localhost:8000"
echo ""
echo "4. API docs:"
echo "   http://localhost:8000/docs"
echo ""
