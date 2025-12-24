#!/bin/bash
# Quick start script for Tamio backend

echo "🚀 Starting Tamio Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup first:"
    echo "   python -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env with your configuration before running again."
    exit 1
fi

# Run migrations
echo "📊 Running database migrations..."
alembic upgrade head

# Start the server
echo "✅ Starting server on http://localhost:8000"
echo "📚 API docs available at http://localhost:8000/docs"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
