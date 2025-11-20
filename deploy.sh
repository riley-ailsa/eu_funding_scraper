#!/bin/bash
set -e

echo "============================================"
echo "EU Funding Scraper - Docker Deployment"
echo "============================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  No .env file found!"
    echo ""
    echo "Please create a .env file with your configuration:"
    echo "  cp .env.example .env"
    echo "  # Edit .env with your API keys"
    echo ""
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Parse command line arguments
ACTION=${1:-up}

case $ACTION in
    up|start)
        echo ""
        echo "🚀 Starting services..."
        docker-compose up -d
        echo ""
        echo "✅ Services started!"
        echo ""
        echo "📊 View logs:"
        echo "   docker-compose logs -f scraper"
        echo ""
        echo "🛑 Stop services:"
        echo "   ./deploy.sh stop"
        ;;

    stop|down)
        echo ""
        echo "🛑 Stopping services..."
        docker-compose down
        echo ""
        echo "✅ Services stopped!"
        ;;

    restart)
        echo ""
        echo "🔄 Restarting services..."
        docker-compose restart
        echo ""
        echo "✅ Services restarted!"
        ;;

    logs)
        docker-compose logs -f scraper
        ;;

    build)
        echo ""
        echo "🔨 Building images..."
        docker-compose build
        echo ""
        echo "✅ Build complete!"
        ;;

    status)
        echo ""
        echo "📊 Service Status:"
        docker-compose ps
        echo ""
        echo "📁 Recent update reports:"
        find data -name "update_report_*.json" -type f -mtime -1 -exec ls -lh {} \; 2>/dev/null | tail -5
        ;;

    clean)
        echo ""
        echo "⚠️  This will stop services and remove volumes (including database data)!"
        read -p "Are you sure? (yes/no): " -r
        if [[ $REPLY =~ ^[Yy]es$ ]]; then
            docker-compose down -v
            echo "✅ Cleaned up!"
        else
            echo "❌ Cancelled"
        fi
        ;;

    manual)
        echo ""
        echo "🏃 Running manual scrape..."
        docker-compose run --rm scraper-manual
        ;;

    shell)
        echo ""
        echo "🐚 Starting shell in scraper container..."
        docker-compose run --rm scraper bash
        ;;

    *)
        echo ""
        echo "Usage: ./deploy.sh [command]"
        echo ""
        echo "Commands:"
        echo "  up, start     - Start all services (default)"
        echo "  stop, down    - Stop all services"
        echo "  restart       - Restart services"
        echo "  logs          - View scraper logs (live)"
        echo "  build         - Rebuild Docker images"
        echo "  status        - Show service status and recent reports"
        echo "  clean         - Stop and remove all data (destructive!)"
        echo "  manual        - Run a one-off manual scrape"
        echo "  shell         - Open bash shell in container"
        echo ""
        exit 1
        ;;
esac
