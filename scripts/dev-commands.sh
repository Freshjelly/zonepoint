#!/bin/bash

# ZonePoint Development Helper Commands
set -e

# Detect compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

show_help() {
    echo "🔧 ZonePoint Development Commands"
    echo "================================="
    echo ""
    echo "Basic Commands:"
    echo "  $0 start                    # Start main development environment"
    echo "  $0 stop                     # Stop all services"
    echo "  $0 restart                  # Restart main development environment"
    echo "  $0 shell                    # Connect to development container shell"
    echo "  $0 logs [service]           # View logs (optional service name)"
    echo ""
    echo "Service Commands:"
    echo "  $0 fx-ai                    # Start FX Analysis AI service"
    echo "  $0 fx-news                  # Start Discord News service" 
    echo "  $0 fx-youtube               # Start YouTube Insights service"
    echo "  $0 digest                   # Run digest (one-time)"
    echo ""
    echo "Development Commands:"
    echo "  $0 build                    # Rebuild development environment"
    echo "  $0 clean                    # Clean up containers and volumes"
    echo "  $0 status                   # Show status of all services"
}

case "$1" in
    "start")
        echo "🚀 Starting ZonePoint development environment..."
        $COMPOSE_CMD up -d zonepoint-dev
        echo "✅ Development environment started!"
        echo "   Connect with: $0 shell"
        ;;
    "stop")
        echo "🛑 Stopping all ZonePoint services..."
        $COMPOSE_CMD down
        echo "✅ All services stopped!"
        ;;
    "restart")
        echo "🔄 Restarting development environment..."
        $COMPOSE_CMD restart zonepoint-dev
        ;;
    "shell")
        echo "🐚 Connecting to development container..."
        $COMPOSE_CMD exec zonepoint-dev bash
        ;;
    "logs")
        if [ -n "$2" ]; then
            $COMPOSE_CMD logs -f "$2"
        else
            $COMPOSE_CMD logs -f
        fi
        ;;
    "fx-ai")
        echo "🤖 Starting FX Analysis AI service..."
        $COMPOSE_CMD --profile fx-analyseai up -d
        ;;
    "fx-news")
        echo "📰 Starting Discord News service..."
        $COMPOSE_CMD --profile fx-discord-news up -d
        ;;
    "fx-youtube")
        echo "📺 Starting YouTube Insights service..."
        $COMPOSE_CMD --profile fx-youtube-insights up -d
        echo "🌐 Streamlit available at: http://localhost:8501"
        ;;
    "digest")
        echo "📊 Running digest..."
        $COMPOSE_CMD --profile digest up
        ;;
    "build")
        echo "🏗️  Rebuilding development environment..."
        $COMPOSE_CMD build --no-cache zonepoint-dev
        ;;
    "clean")
        echo "🧹 Cleaning up containers and volumes..."
        $COMPOSE_CMD down -v --remove-orphans
        docker system prune -f
        ;;
    "status")
        echo "📊 ZonePoint Services Status:"
        $COMPOSE_CMD ps
        ;;
    *)
        show_help
        ;;
esac