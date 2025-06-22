#!/usr/bin/env python3
"""
Health Check Script for Sanchalak Docker Services
Verifies that all components are operational from the host machine.
"""

import requests
import sys
import subprocess
from datetime import datetime

def check_service_health(service_name, url, timeout=5):
    """Check if a service is responding via its health endpoint"""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            print(f"✅ {service_name}: Healthy")
            return True
        else:
            print(f"❌ {service_name}: Unhealthy (Status: {response.status_code})")
            return False
    except requests.exceptions.RequestException:
        print(f"❌ {service_name}: Unreachable at {url}")
        return False

def check_mongo_health():
    """Check if the MongoDB container is healthy"""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", "sanchalak-mongo"],
            capture_output=True, text=True, check=True
        )
        status = result.stdout.strip()
        if status == "healthy":
            print("✅ Database (MongoDB): Healthy")
            return True
        else:
            print(f"❌ Database (MongoDB): Unhealthy (Status: {status})")
            return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Database (MongoDB): Container 'sanchalak-mongo' not found or docker not running.")
        return False

def main():
    print("🩺 Sanchalak Docker Health Check")
    print("=" * 40)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Correct service endpoints from docker-compose.yml for host access
    services = [
        ("Telegram Bot",   "http://localhost:8080/health"),
        ("Orchestrator",   "http://localhost:8000/health"),
        ("EFR Database",   "http://localhost:8001/health"),
        ("Form Filler",    "http://localhost:8002/health"),
        ("Status Tracker", "http://localhost:8003/health"),
        ("Monitoring",     "http://localhost:8084/health")
    ]
    
    healthy_services = 0
    total_services = len(services) + 1  # +1 for database
    
    # Check web services
    for service_name, url in services:
        if check_service_health(service_name, url):
            healthy_services += 1
    
    # Check database container
    if check_mongo_health():
        healthy_services += 1
    
    print()
    print("-" * 40)
    print(f"Health Summary: {healthy_services}/{total_services} services healthy")
    print("-" * 40)
    
    if healthy_services == total_services:
        print("🎉 All systems operational!")
        print()
        print("🚀 Ready for testing:")
        print("   1. Check container status: docker-compose ps")
        print("   2. View logs: ./scripts/shell.sh logs telegram-bot")
        print("   3. Test the bot in Telegram!")
        sys.exit(0)
    else:
        print("⚠️  Some services need attention!")
        print()
        print("🔧 Troubleshooting:")
        print("   1. Ensure Docker is running.")
        print("   2. Start all services: ./scripts/run.sh")
        print("   3. Check logs for the failing service: docker-compose logs -f <service-name>")
        sys.exit(1)

if __name__ == "__main__":
    main()