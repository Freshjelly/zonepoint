#!/bin/bash

# ZonePoint Development Environment Setup Script
set -e

echo "🚀 ZonePoint Development Environment Setup"
echo "=========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data logs

# Copy environment file templates
echo "📋 Setting up environment files..."
for env_example in $(find . -name ".env.example"); do
    env_file="${env_example%.example}"
    if [ ! -f "$env_file" ]; then
        echo "  Creating $env_file"
        cp "$env_example" "$env_file"
        echo "  ⚠️  Please edit $env_file and add your API keys and configurations"
    fi
done

# Build and start the main development container
echo "🏗️  Building development environment..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

$COMPOSE_CMD build zonepoint-dev

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Quick Start Commands:"
echo "  # Start main development environment"
echo "  $COMPOSE_CMD up -d zonepoint-dev"
echo ""
echo "  # Connect to development container"
echo "  $COMPOSE_CMD exec zonepoint-dev bash"
echo ""
echo "  # Start FX Analysis AI service"
echo "  $COMPOSE_CMD --profile fx-analyseai up -d"
echo ""
echo "  # Start Discord News service"
echo "  $COMPOSE_CMD --profile fx-discord-news up -d"
echo ""
echo "  # Start YouTube Insights service (with Streamlit)"
echo "  $COMPOSE_CMD --profile fx-youtube-insights up -d"
echo ""
echo "  # Run digest (dry run mode)"
echo "  $COMPOSE_CMD --profile digest up"
echo ""
echo "  # View logs"
echo "  $COMPOSE_CMD logs -f [service-name]"
echo ""
echo "⚠️  Don't forget to:"
echo "   1. Edit .env files with your API keys"
echo "   2. Configure Discord webhooks"
echo "   3. Set up RSS feeds in config files"
echo ""
echo "🌐 Exposed Ports:"
echo "   - 8000: General web services"
echo "   - 8080: Alternative web port"  
echo "   - 8501: Streamlit (YouTube Insights)"
echo "   - 5000: Flask/FastAPI services"
echo ""