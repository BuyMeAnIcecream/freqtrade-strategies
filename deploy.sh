#!/bin/bash

# 🚀 SmoothOperator Optimized Final - Deployment Script
# This script automates the deployment process

set -e  # Exit on any error

echo "🚀 Starting SmoothOperator Optimized Final Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please don't run this script as root"
    exit 1
fi

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not found. Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        print_success "Docker installed. Please log out and back in, then run this script again."
        exit 0
    fi
    print_success "Docker is installed"
}

# Check if Docker Compose is installed
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_warning "Docker Compose not found. Installing..."
        sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        print_success "Docker Compose installed"
    else
        print_success "Docker Compose is installed"
    fi
}

# Create project structure
create_project_structure() {
    print_status "Creating project structure..."
    
    mkdir -p freqtrade-production/user_data/strategies
    mkdir -p freqtrade-production/user_data/data
    mkdir -p freqtrade-production/logs
    
    print_success "Project structure created"
}

# Copy strategy files
copy_strategy_files() {
    print_status "Copying strategy files..."
    
    # Copy the optimized strategy
    if [ -f "user_data/strategies/SmoothOperator_Optimized_Final.py" ]; then
        cp user_data/strategies/SmoothOperator_Optimized_Final.py freqtrade-production/user_data/strategies/
        print_success "Strategy file copied"
    else
        print_error "Strategy file not found. Please ensure SmoothOperator_Optimized_Final.py exists in user_data/strategies/"
        exit 1
    fi
    
    # Copy configuration
    if [ -f "config_binance_production.json" ]; then
        cp config_binance_production.json freqtrade-production/config.json
        print_success "Configuration file copied"
    else
        print_error "Configuration file not found. Please ensure config_binance_production.json exists"
        exit 1
    fi
}

# Create Docker Compose file
create_docker_compose() {
    print_status "Creating Docker Compose configuration..."
    
    cat > freqtrade-production/docker-compose.yml << 'EOF'
version: '3.8'
services:
  freqtrade:
    image: freqtrade/freqtrade:stable
    container_name: freqtrade
    restart: unless-stopped
    volumes:
      - "./user_data:/freqtrade/user_data"
      - "./config.json:/freqtrade/config.json"
      - "./logs:/freqtrade/user_data/logs"
    command: trade --config /freqtrade/config.json --strategy SmoothOperator_Optimized_Final
    ports:
      - "8080:8080"
    environment:
      - FREQTRADE_CONFIG=/freqtrade/config.json
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/v1/status"]
      interval: 30s
      timeout: 10s
      retries: 3
EOF
    
    print_success "Docker Compose file created"
}

# Create monitoring script
create_monitoring_script() {
    print_status "Creating monitoring script..."
    
    cat > freqtrade-production/monitor.sh << 'EOF'
#!/bin/bash

# Monitoring script for Freqtrade
echo "🤖 Freqtrade Status Check"
echo "=========================="

# Check if container is running
if docker ps | grep -q freqtrade; then
    echo "✅ Container is running"
    
    # Check API status
    if curl -s http://localhost:8080/api/v1/status > /dev/null; then
        echo "✅ API is responding"
        
        # Get status
        echo "📊 Current Status:"
        curl -s http://localhost:8080/api/v1/status | jq '.status' 2>/dev/null || echo "Status: Running"
    else
        echo "❌ API not responding"
    fi
    
    # Show recent logs
    echo ""
    echo "📋 Recent Logs:"
    docker logs --tail 10 freqtrade
else
    echo "❌ Container is not running"
    echo "To start: docker-compose up -d"
fi

echo ""
echo "🔗 Web Interface: http://localhost:8080"
echo "📊 API Status: http://localhost:8080/api/v1/status"
EOF
    
    chmod +x freqtrade-production/monitor.sh
    print_success "Monitoring script created"
}

# Create backup script
create_backup_script() {
    print_status "Creating backup script..."
    
    cat > freqtrade-production/backup.sh << 'EOF'
#!/bin/bash

# Backup script for Freqtrade
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "💾 Creating backup: $DATE"

# Backup configuration
cp config.json $BACKUP_DIR/config_$DATE.json

# Backup logs
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz user_data/logs/

# Backup strategy
cp user_data/strategies/SmoothOperator_Optimized_Final.py $BACKUP_DIR/strategy_$DATE.py

echo "✅ Backup completed: $BACKUP_DIR/"
EOF
    
    chmod +x freqtrade-production/backup.sh
    print_success "Backup script created"
}

# Main deployment function
main() {
    echo "🚀 SmoothOperator Optimized Final - Deployment Script"
    echo "=================================================="
    
    # Check prerequisites
    check_docker
    check_docker_compose
    
    # Create project structure
    create_project_structure
    
    # Copy files
    copy_strategy_files
    
    # Create Docker Compose
    create_docker_compose
    
    # Create utility scripts
    create_monitoring_script
    create_backup_script
    
    # Change to production directory
    cd freqtrade-production
    
    print_success "Deployment setup completed!"
    echo ""
    echo "📋 Next Steps:"
    echo "1. Edit config.json with your Binance API keys"
    echo "2. Test with dry-run: docker-compose up"
    echo "3. Start live trading: docker-compose up -d"
    echo "4. Monitor: ./monitor.sh"
    echo "5. Access web interface: http://localhost:8080"
    echo ""
    echo "⚠️  IMPORTANT:"
    echo "- Start with small amounts ($100-500)"
    echo "- Monitor performance closely"
    echo "- Keep your API keys secure"
    echo "- Enable 2FA on Binance"
    echo ""
    echo "📚 Documentation: DEPLOYMENT_GUIDE.md"
}

# Run main function
main 