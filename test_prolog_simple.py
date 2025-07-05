#!/usr/bin/env python3
"""
Simple Prolog test to isolate the issue
"""

import sys
import os
from pyswip import Prolog

def get_project_root():
    """Get the absolute path to the project root directory."""
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(current_file)
    return project_root

PROJECT_ROOT = get_project_root()
PROLOG_FILE_PATH = os.path.join(PROJECT_ROOT, "src", "schemes", "outputs", "pm-kisan", "REFERENCE_prolog_system.pl")

def test_prolog_loading():
    """Test basic Prolog loading"""
    print("Testing Prolog loading...")
    
    try:
        prolog = Prolog()
        print("✅ Prolog instance created")
        
        # Try to load the file
        print(f"Loading file: {PROLOG_FILE_PATH}")
        prolog.consult(PROLOG_FILE_PATH)
        print("✅ Prolog file loaded successfully")
        
        # Test a simple query
        print("Testing simple query...")
        result = list(prolog.query("person('test')"))
        print(f"✅ Simple query result: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_prolog_loading()
    if success:
        print("✅ Prolog test passed")
    else:
        print("❌ Prolog test failed") 