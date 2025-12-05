#!/bin/bash

# Grocery Price Comparator Setup Script

echo "🛒 Setting up Grocery Price Comparator..."
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# Setup environment file
if [ ! -f .env ]; then
    echo ""
    echo "🔑 Creating .env file..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  Please edit .env and add your OpenRouter API key"
    echo "   Get a free key at: https://openrouter.ai/"
else
    echo ""
    echo "✓ .env file already exists"
fi

# Create Cookies directory if it doesn't exist
if [ ! -d "Cookies" ]; then
    mkdir Cookies
    echo "✓ Created Cookies directory"
fi

# Initialize database
echo ""
echo "🗄️  Database will be initialized on first run"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your OpenRouter API key"
echo "2. (Optional) Add cookie files to Cookies/ directory"
echo "3. Run: python3 app.py"
echo "4. Open: http://127.0.0.1:5000"
echo ""
