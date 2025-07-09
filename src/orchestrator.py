#!/usr/bin/env python3
"""
Orchestrator for Sanchalak Services

Runs all services on different ports:
- Schemabot (LLM Backend): Port 8000
- Streamlit (Frontend): Port 8501  
- EFR (Database): Existing port
"""

import subprocess
import time
import signal
import sys
import os
import psutil
from pathlib import Path

class ServiceOrchestrator:
    def __init__(self):
        self.processes = {}
        self.base_dir = Path(__file__).parent
        
    def kill_existing_services(self):
        """Kill any existing services running on our ports"""
        print("🧹 Cleaning up existing services...")
        
        ports_to_check = [8000, 8001, 8501]
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if process is using our ports
                try:
                    proc_connections = proc.net_connections()
                    for conn in proc_connections:
                        if conn.laddr.port in ports_to_check:
                            print(f"🛑 Killing process {proc.info['name']} (PID: {proc.info['pid']}) on port {conn.laddr.port}")
                            proc.terminate()
                            try:
                                proc.wait(timeout=3)
                            except psutil.TimeoutExpired:
                                proc.kill()
                            killed_count += 1
                            break
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                        
                # Also check for specific service processes (only Python processes)
                cmdline = proc.info.get('cmdline', [])
                if cmdline and len(cmdline) > 1:
                    # Only target Python processes that are running our services
                    if cmdline[0].endswith('python') or cmdline[0].endswith('python3'):
                        cmd_str = ' '.join(cmdline).lower()
                        if any(keyword in cmd_str for keyword in ['uvicorn', 'streamlit', 'schemabot', 'efr']):
                            if proc.info['pid'] != os.getpid():  # Don't kill ourselves
                                print(f"🛑 Killing existing service process: {proc.info['name']} (PID: {proc.info['pid']})")
                                proc.terminate()
                                try:
                                    proc.wait(timeout=3)
                                except psutil.TimeoutExpired:
                                    proc.kill()
                                killed_count += 1
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if killed_count > 0:
            print(f"✅ Killed {killed_count} existing service(s)")
            time.sleep(2)  # Give time for ports to be freed
        else:
            print("✅ No existing services found")
        
    def start_schemabot(self):
        """Start Schemabot LLM backend on port 8000"""
        print("🚀 Starting Schemabot (LLM Backend) on port 8000...")
        
        schemabot_dir = self.base_dir / "schemabot"
        cmd = [
            sys.executable, "-m", "uvicorn", 
            "api.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ]
        
        process = subprocess.Popen(
            cmd,
            cwd=schemabot_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.processes['schemabot'] = process
        print(f"✅ Schemabot started with PID: {process.pid}")
        return process
    
    def start_streamlit(self):
        """Start Streamlit frontend on port 8501"""
        print("🚀 Starting Streamlit (Frontend) on port 8501...")
        
        streamlit_dir = self.base_dir / "translation" / "streamlit_app"
        cmd = [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--server.headless", "true"
        ]
        
        process = subprocess.Popen(
            cmd,
            cwd=streamlit_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.processes['streamlit'] = process
        print(f"✅ Streamlit started with PID: {process.pid}")
        return process
    
    def start_efr(self):
        """Start EFR database service on port 8001"""
        print("🚀 Starting EFR Database on port 8001...")
        
        efr_dir = self.base_dir / "efr_database"
        cmd = [
            sys.executable, "-m", "uvicorn", "main:app",
            "--host", "0.0.0.0",
            "--port", "8001",
            "--reload"
        ]
        
        process = subprocess.Popen(
            cmd,
            cwd=efr_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.processes['efr'] = process
        print(f"✅ EFR Database started with PID: {process.pid}")
        return process
    
    def check_service_health(self, service_name, port=None):
        """Check if a service is healthy"""
        if port:
            try:
                import requests
                response = requests.get(f"http://localhost:{port}/health", timeout=5)
                return response.status_code == 200
            except:
                return False
        return self.processes.get(service_name, {}).poll() is None
    
    def wait_for_services(self, timeout=30):
        """Wait for services to be ready"""
        print("⏳ Waiting for services to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            all_ready = True
            
            # Check EFR Database
            if not self.check_service_health('efr', 8001):
                all_ready = False
                print("⏳ Waiting for EFR Database...")
            
            # Check Schemabot
            if not self.check_service_health('schemabot', 8000):
                all_ready = False
                print("⏳ Waiting for Schemabot...")
            
            # Check Streamlit (no health endpoint, just check if process is running)
            if not self.check_service_health('streamlit'):
                all_ready = False
                print("⏳ Waiting for Streamlit...")
            
            if all_ready:
                print("✅ All services are ready!")
                return True
            
            time.sleep(2)
        
        print("❌ Timeout waiting for services")
        return False
    
    def start_all(self):
        """Start all services"""
        print("🎯 Starting Sanchalak Orchestrator...")
        print("=" * 50)
        
        # First, kill any existing services
        self.kill_existing_services()
        
        try:
            # Start services
            self.start_efr()
            time.sleep(2)  # Give EFR time to start
            
            self.start_schemabot()
            time.sleep(3)  # Give Schemabot time to start
            
            self.start_streamlit()
            time.sleep(3)  # Give Streamlit time to start
            
            # Wait for services to be ready
            if self.wait_for_services():
                print("\n🎉 All services started successfully!")
                print("\n📋 Service URLs:")
                print("   • EFR Database: http://localhost:8001")
                print("   • Schemabot (LLM Backend): http://localhost:8000")
                print("   • Streamlit (Frontend): http://localhost:8501")
                print("\n📚 API Documentation:")
                print("   • Schemabot API Docs: http://localhost:8000/docs")
                print("   • Schemabot ReDoc: http://localhost:8000/redoc")
                print("\n🔄 Press Ctrl+C to stop all services")
                
                # Keep running
                try:
                    while True:
                        time.sleep(1)
                        # Check if any service died
                        for name, process in self.processes.items():
                            if process.poll() is not None:
                                print(f"❌ Service {name} died unexpectedly")
                                self.stop_all()
                                return
                except KeyboardInterrupt:
                    print("\n🛑 Stopping all services...")
                    self.stop_all()
            else:
                print("❌ Failed to start all services")
                self.stop_all()
                
        except Exception as e:
            print(f"❌ Error starting services: {e}")
            self.stop_all()
    
    def stop_all(self):
        """Stop all services"""
        print("🛑 Stopping all services...")
        
        for name, process in self.processes.items():
            if process.poll() is None:  # Process is still running
                print(f"🛑 Stopping {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                print(f"✅ {name} stopped")
        
        self.processes.clear()
        print("✅ All services stopped")

def signal_handler(signum, frame):
    """Handle Ctrl+C"""
    print("\n🛑 Received interrupt signal")
    if hasattr(signal_handler, 'orchestrator'):
        signal_handler.orchestrator.stop_all()
    sys.exit(0)

def main():
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and start orchestrator
    orchestrator = ServiceOrchestrator()
    signal_handler.orchestrator = orchestrator
    
    orchestrator.start_all()

if __name__ == "__main__":
    main() 