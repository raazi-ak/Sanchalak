#!/usr/bin/env python3
"""
Sanchalak Docker Monitoring Service
Monitors all Sanchalak services running in Docker containers
"""

import time
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

import psutil
import requests
from loguru import logger

class SanchalakMonitor:
    def __init__(self, verbose=False, output_file=None):
        self.verbose = verbose
        self.output_file = output_file
        
        # Configure logging
        if output_file:
            logger.add(output_file, rotation="10 MB", retention="7 days")
        
        # Service endpoints for internal Docker networking
        self.services = {
            'orchestrator': 'http://orchestrator:8000/health',
            'efr-db': 'http://efr-db:8000/health', 
            'form-filler': 'http://form-filler:8000/health',
            'status-tracker': 'http://status-tracker:8000/health',
            'telegram-bot': 'http://telegram-bot:8080/health'  # Corrected endpoint
        }
        
        self.stats = {
            'start_time': datetime.now(),
            'checks_performed': 0,
            'services_healthy': 0,
            'services_unhealthy': 0,
            'total_errors': 0
        }

    def check_service_health(self, service_name, url):
        """Check health of a single service"""
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                if self.verbose:
                    logger.info(f"✅ {service_name}: Healthy")
                self.stats['services_healthy'] += 1
                return True
            else:
                logger.warning(f"⚠️  {service_name}: Unhealthy (HTTP {response.status_code})")
                self.stats['services_unhealthy'] += 1
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {service_name}: Connection failed - {str(e)}")
            self.stats['services_unhealthy'] += 1
            self.stats['total_errors'] += 1
            return False

    def get_system_stats(self):
        """Get system resource usage"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_average': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
        }

    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("🚀 Starting Sanchalak Monitoring Service")
        
        while True:
            try:
                self.stats['checks_performed'] += 1
                
                # Check all services
                healthy_services = []
                unhealthy_services = []
                
                for service_name, url in self.services.items():
                    if self.check_service_health(service_name, url):
                        healthy_services.append(service_name)
                    else:
                        unhealthy_services.append(service_name)
                
                # Get system stats
                sys_stats = self.get_system_stats()
                
                # Log summary
                if self.verbose or unhealthy_services:
                    uptime = datetime.now() - self.stats['start_time']
                    logger.info(f"📊 Check #{self.stats['checks_performed']} | "
                              f"Healthy: {len(healthy_services)} | "
                              f"Unhealthy: {len(unhealthy_services)} | "
                              f"CPU: {sys_stats['cpu_percent']:.1f}% | "
                              f"Memory: {sys_stats['memory_percent']:.1f}% | "
                              f"Uptime: {str(uptime).split('.')[0]}")
                
                if unhealthy_services:
                    logger.warning(f"🚨 Unhealthy services: {', '.join(unhealthy_services)}")
                
                # Wait before next check
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("🛑 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"💥 Monitoring error: {str(e)}")
                self.stats['total_errors'] += 1
                time.sleep(5)

    def print_final_stats(self):
        """Print final statistics"""
        uptime = datetime.now() - self.stats['start_time']
        logger.info("📈 Final Statistics:")
        logger.info(f"   • Total uptime: {str(uptime).split('.')[0]}")
        logger.info(f"   • Health checks performed: {self.stats['checks_performed']}")
        logger.info(f"   • Services healthy: {self.stats['services_healthy']}")
        logger.info(f"   • Services unhealthy: {self.stats['services_unhealthy']}")
        logger.info(f"   • Total errors: {self.stats['total_errors']}")

def main():
    parser = argparse.ArgumentParser(description='Sanchalak Docker Monitoring Service')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose logging')
    parser.add_argument('-o', '--output', type=str,
                       help='Output log file path')
    
    args = parser.parse_args()
    
    # Initialize monitor
    monitor = SanchalakMonitor(verbose=args.verbose, output_file=args.output)
    
    try:
        monitor.monitor_loop()
    finally:
        monitor.print_final_stats()

if __name__ == "__main__":
    main() 