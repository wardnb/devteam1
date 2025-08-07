#!/bin/bash

echo "🤖 Autonomous Development Team - Setup Script"
echo "============================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $required_version or higher is required. Found: $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"

# Check Docker
echo ""
echo "Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo "✅ Docker is installed"

# Check Docker Compose
echo "Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    if ! docker compose version &> /dev/null; then
        echo "❌ Docker Compose is not installed"
        echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
fi
echo "✅ Docker Compose is installed"

# Check Ollama
echo ""
echo "Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama is not installed"
    read -p "Would you like to install Ollama now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Installing Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh
    else
        echo "Please install Ollama manually: https://ollama.ai"
    fi
else
    echo "✅ Ollama is installed"
fi

# Create virtual environment
echo ""
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo ""
echo "Creating project directories..."
mkdir -p workspace/tests workspace/designs logs data

# Pull Ollama models
echo ""
echo "Pulling required Ollama models..."
echo "This may take a while depending on your internet connection..."

models=("llama3.1:8b" "codellama:13b")
for model in "${models[@]}"; do
    echo "Pulling $model..."
    ollama pull "$model"
done

# Check Redis
echo ""
echo "Checking Redis..."
if ! command -v redis-server &> /dev/null; then
    echo "⚠️  Redis is not installed locally"
    echo "Redis will run in Docker container"
else
    echo "✅ Redis is installed locally"
fi

# Create .env file
echo ""
echo "Creating environment configuration..."
cat > .env << EOF
# Autonomous Dev Team Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
OLLAMA_HOST=http://localhost:11434
LOG_LEVEL=INFO
EOF
echo "✅ Created .env file"

# Setup complete
echo ""
echo "============================================="
echo "✅ Setup Complete!"
echo ""
echo "To start the system:"
echo ""
echo "1. Using Docker (recommended):"
echo "   cd docker"
echo "   docker-compose up -d"
echo ""
echo "2. Using local Python:"
echo "   # Terminal 1: Start Redis"
echo "   redis-server"
echo "   "
echo "   # Terminal 2: Start Ollama"
echo "   ollama serve"
echo "   "
echo "   # Terminal 3: Start the dev team"
echo "   source venv/bin/activate"
echo "   python main.py --mode interactive"
echo ""
echo "3. Run example project:"
echo "   source venv/bin/activate"
echo "   python main.py --mode example"
echo ""
echo "Happy coding with your AI team! 🚀"