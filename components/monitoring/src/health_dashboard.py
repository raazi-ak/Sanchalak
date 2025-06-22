#!/usr/bin/env python3
"""
Health Monitoring Dashboard for Sanchalak
Provides both regular user and admin interfaces for system monitoring
"""

import os
import json
import subprocess
import asyncio
import aiohttp
import requests
import docker
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import threading
import time

app = Flask(__name__)
app.secret_key = os.environ.get('DASHBOARD_SECRET_KEY', 'your-secret-key-change-in-production')

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Docker client
docker_client = docker.from_env()

# Service configurations
SERVICES = {
    'telegram-bot': {'port': 8080, 'health_endpoint': '/health', 'internal_port': 8080},
    'orchestrator': {'port': 8000, 'health_endpoint': '/health', 'internal_port': 8000},
    'efr-db': {'port': 8001, 'health_endpoint': '/health', 'internal_port': 8000},
    'form-filler': {'port': 8002, 'health_endpoint': '/health', 'internal_port': 8000},
    'status-tracker': {'port': 8003, 'health_endpoint': '/health', 'internal_port': 8000},
    'monitoring': {'port': 8084, 'health_endpoint': '/health', 'internal_port': 8080},
    'nginx': {'port': 80, 'health_endpoint': '/health', 'internal_port': 80}
}

# Admin credentials (in production, use environment variables)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_USERNAME:
        return User(user_id)
    return None

def check_service_health(service_name, config):
    """Check individual service health"""
    try:
        # Check if container is running
        container = docker_client.containers.get(f'sanchalak-{service_name}')
        if container.status != 'running':
            return {
                'status': 'down',
                'message': f'Container {service_name} is not running',
                'timestamp': datetime.now().isoformat()
            }
        
        # Check health endpoint if available
        if config.get('health_endpoint'):
            try:
                # Use Docker service name for internal communication
                internal_port = config.get('internal_port', config['port'])
                health_url = f'http://{service_name}:{internal_port}{config["health_endpoint"]}'
                response = requests.get(health_url, timeout=5)
                
                if response.status_code == 200:
                    try:
                        # Parse JSON response to check actual health status
                        health_data = response.json()
                        service_status = health_data.get('status', 'unknown').lower()
                        
                        if service_status in ['healthy', 'ok', 'up']:
                            return {
                                'status': 'healthy',
                                'message': f'Service is healthy: {health_data.get("service", service_name)}',
                                'timestamp': datetime.now().isoformat()
                            }
                        else:
                            return {
                                'status': 'warning',
                                'message': f'Service reports status: {service_status}',
                                'timestamp': datetime.now().isoformat()
                            }
                    except (ValueError, KeyError) as e:
                        # If JSON parsing fails, fall back to status code check
                        return {
                            'status': 'healthy',
                            'message': 'Service responded but JSON parsing failed',
                            'timestamp': datetime.now().isoformat()
                        }
                else:
                    return {
                        'status': 'warning',
                        'message': f'Health endpoint returned {response.status_code}',
                        'timestamp': datetime.now().isoformat()
                    }
            except requests.RequestException as e:
                return {
                    'status': 'warning',
                    'message': f'Health endpoint not accessible: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }
        
        return {
            'status': 'healthy',
            'message': 'Container is running',
            'timestamp': datetime.now().isoformat()
        }
        
    except docker.errors.NotFound:
        return {
            'status': 'down',
            'message': f'Container {service_name} not found',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }

def get_overall_system_health():
    """Get overall system health status (abstracted for regular users)"""
    health_statuses = {}
    total_services = len(SERVICES)
    healthy_services = 0
    warning_services = 0
    down_services = 0
    
    for service_name, config in SERVICES.items():
        status = check_service_health(service_name, config)
        health_statuses[service_name] = status
        
        if status['status'] == 'healthy':
            healthy_services += 1
        elif status['status'] == 'warning':
            warning_services += 1
        else:
            down_services += 1
    
    # Determine overall status
    if down_services == 0 and warning_services == 0:
        overall_status = 'operational'
        message = 'All systems are running normally'
    elif down_services == 0:
        overall_status = 'degraded'
        message = f'{warning_services} services experiencing issues'
    else:
        overall_status = 'critical'
        message = f'{down_services} services are down'
    
    return {
        'status': overall_status,
        'message': message,
        'summary': {
            'total': total_services,
            'healthy': healthy_services,
            'warning': warning_services,
            'down': down_services
        },
        'timestamp': datetime.now().isoformat()
    }

@app.route('/')
def index():
    """Main dashboard page"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('public_dashboard'))

@app.route('/public')
def public_dashboard():
    """Public dashboard for regular users"""
    system_health = get_overall_system_health()
    return render_template('public_dashboard.html', health=system_health)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            user = User(username)
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('public_dashboard'))

@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard with detailed service information"""
    health_statuses = {}
    for service_name, config in SERVICES.items():
        health_statuses[service_name] = check_service_health(service_name, config)
    
    return render_template('admin_dashboard.html', services=health_statuses)

@app.route('/health')
def health():
    """Health check endpoint for the monitoring service itself"""
    return jsonify({
        'status': 'healthy',
        'service': 'monitoring',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/health')
def api_health():
    """API endpoint for health checks"""
    if current_user.is_authenticated:
        # Admin mode - return detailed health
        health_statuses = {}
        for service_name, config in SERVICES.items():
            health_statuses[service_name] = check_service_health(service_name, config)
        return jsonify(health_statuses)
    else:
        # Public mode - return abstracted health
        return jsonify(get_overall_system_health())

@app.route('/api/shell', methods=['POST'])
@login_required
def execute_shell():
    """Execute shell command (admin only)"""
    command = request.json.get('command')
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    
    try:
        # For Docker commands, use the Docker Python client
        if command.startswith('docker '):
            if 'ps' in command:
                containers = []
                for container in docker_client.containers.list(all=True):
                    containers.append({
                        'id': container.id[:12],
                        'name': container.name,
                        'status': container.status,
                        'image': container.image.tags[0] if container.image.tags else container.image.id
                    })
                return jsonify({
                    'stdout': json.dumps(containers, indent=2),
                    'stderr': '',
                    'returncode': 0
                })
            elif 'stats' in command:
                stats = []
                for container in docker_client.containers.list():
                    try:
                        container_stats = container.stats(stream=False)
                        stats.append({
                            'name': container.name,
                            'cpu': container_stats['cpu_stats']['cpu_usage']['total_usage'],
                            'memory': container_stats['memory_stats']['usage'],
                            'network': container_stats['networks']
                        })
                    except:
                        pass
                return jsonify({
                    'stdout': json.dumps(stats, indent=2),
                    'stderr': '',
                    'returncode': 0
                })
            elif 'system df' in command:
                system_info = docker_client.df()
                return jsonify({
                    'stdout': json.dumps(system_info, indent=2),
                    'stderr': '',
                    'returncode': 0
                })
            elif 'logs' in command:
                # Extract container name from command
                parts = command.split()
                container_name = None
                for i, part in enumerate(parts):
                    if part == 'logs' and i + 1 < len(parts):
                        container_name = parts[i + 1]
                        break
                
                if container_name:
                    try:
                        container = docker_client.containers.get(container_name)
                        logs = container.logs(tail=50, timestamps=True).decode('utf-8')
                        return jsonify({
                            'stdout': logs,
                            'stderr': '',
                            'returncode': 0
                        })
                    except:
                        return jsonify({
                            'stdout': '',
                            'stderr': f'Container {container_name} not found',
                            'returncode': 1
                        })
                else:
                    return jsonify({
                        'stdout': '',
                        'stderr': 'Please specify container name',
                        'returncode': 1
                    })
            else:
                return jsonify({
                    'stdout': '',
                    'stderr': 'Docker command not supported. Use: docker ps, docker stats, docker system df, docker logs <container>',
                    'returncode': 1
                })
        else:
            # For non-Docker commands, use subprocess
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return jsonify({
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            })
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Command timed out'}), 408
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/docker/containers')
@login_required
def get_containers():
    """Get Docker container information"""
    try:
        containers = []
        for container in docker_client.containers.list(all=True):
            containers.append({
                'id': container.id,
                'name': container.name,
                'status': container.status,
                'image': container.image.tags[0] if container.image.tags else container.image.id,
                'created': container.attrs['Created'],
                'ports': container.attrs['NetworkSettings']['Ports']
            })
        return jsonify(containers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/docker/container/<container_id>/logs')
@login_required
def get_container_logs(container_id):
    """Get container logs"""
    try:
        container = docker_client.containers.get(container_id)
        logs = container.logs(tail=100, timestamps=True).decode('utf-8')
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False) 