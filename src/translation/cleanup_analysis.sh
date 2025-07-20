#!/bin/bash

# Sanchalak Project Cleanup Script
# This script helps clean up duplicate and outdated UI files

echo "🧹 Sanchalak Project Cleanup"
echo "=============================="

echo ""
echo "📁 Current project structure analysis:"
echo ""

# Check for duplicate directories
echo "🔍 Checking for duplicate/outdated directories..."

TRANSLATION_DIR="d:/Code_stuff/Sanchalak/translation"
SRC_DIR="d:/Code_stuff/Sanchalak/src"

# Check streamlit_old directory
if [ -d "$TRANSLATION_DIR/streamlit_old" ]; then
    echo "⚠️  Found outdated directory: translation/streamlit_old/"
    echo "   This contains older version of the UI files"
    echo "   Current integrated version is in: translation/streamlit_app/"
    echo ""
    echo "   Recommended action: Remove streamlit_old directory"
    echo "   Command: rm -rf '$TRANSLATION_DIR/streamlit_old'"
    echo ""
fi

# Check src/translation directory
if [ -d "$SRC_DIR/translation" ]; then
    echo "⚠️  Found duplicate directory: src/translation/"
    echo "   This appears to be a duplicate of the translation/ directory"
    echo "   Active development should use: translation/"
    echo ""
    echo "   Recommended action: Review and potentially remove src/translation"
    echo "   Command: rm -rf '$SRC_DIR/translation'"
    echo ""
fi

# Check for other potential duplicates
echo "🔍 Checking for other potential overlaps..."

# List all app.py files
echo ""
echo "📄 Found app.py files:"
find "d:/Code_stuff/Sanchalak" -name "app.py" -type f | while read file; do
    echo "   - $file"
done

echo ""
echo "📄 Found utils.py files:"
find "d:/Code_stuff/Sanchalak" -name "utils.py" -type f | while read file; do
    echo "   - $file"
done

echo ""
echo "🎯 Integration Status:"
echo "=============================="
echo "✅ MAIN UI (INTEGRATED):     translation/streamlit_app/"
echo "✅ API SERVICES:              translation/api/"
echo "✅ BACKEND ENTRY:             translation/main.py"
echo "✅ MODELS & SCHEMAS:          translation/models.py"
echo ""

echo "📋 Cleanup Recommendations:"
echo "=============================="
echo "1. Keep: translation/streamlit_app/ (main integrated UI)"
echo "2. Keep: translation/api/ (API services)"
echo "3. Keep: translation/main.py (FastAPI entry point)"
echo "4. Remove: translation/streamlit_old/ (outdated UI)"
echo "5. Review: src/translation/ (potential duplicate)"
echo ""

echo "🚀 Quick Start Commands:"
echo "=============================="
echo "# Start the backend API server:"
echo "cd '$TRANSLATION_DIR'"
echo "python main.py"
echo ""
echo "# Start the integrated UI (in another terminal):"
echo "cd '$TRANSLATION_DIR/streamlit_app'"
echo "streamlit run app.py"
echo ""

echo "📚 Documentation:"
echo "=============================="
echo "📖 API Integration Guide: translation/API_INTEGRATION_README.md"
echo "🔧 Health Check: Available in UI sidebar"
echo "🧪 API Testing: Available in UI expander section"
echo ""

echo "✅ Cleanup analysis complete!"
echo ""
echo "💡 Note: The main UI in translation/streamlit_app/ is fully integrated"
echo "   with the API services and includes comprehensive error handling,"
echo "   health monitoring, and testing capabilities."
