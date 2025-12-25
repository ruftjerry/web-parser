#!/bin/bash

echo "🚀 Setting up Smart HTML Extraction Pipeline"
echo ""

# Create directories
echo "📁 Creating directories..."
mkdir -p Pi_Inbox/Research_Queue
mkdir -p Pi_Inbox/Processed_Archive
mkdir -p Pi_Inbox/Errors
mkdir -p Pi_Inbox/Output

echo "✅ Directories created"
echo ""

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages

echo "✅ Dependencies installed"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  No .env file found"
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "❗ IMPORTANT: Edit .env and add your OpenAI API key!"
    echo "   Get your key from: https://platform.openai.com/api-keys"
    echo ""
else
    echo "✅ .env file exists"
    echo ""
fi

echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Make sure your OPENAI_API_KEY is set in .env"
echo "2. Run: python main_runner.py"
echo "3. Drop HTML files into: Pi_Inbox/Research_Queue/"
echo ""