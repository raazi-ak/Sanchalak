@echo off
REM Sanchalak Project Cleanup Analysis Script
REM This script helps analyze duplicate and outdated UI files

echo 🧹 Sanchalak Project Cleanup
echo ==============================
echo.

echo 📁 Current project structure analysis:
echo.

REM Check for duplicate directories
echo 🔍 Checking for duplicate/outdated directories...

set TRANSLATION_DIR=d:\Code_stuff\Sanchalak\translation
set SRC_DIR=d:\Code_stuff\Sanchalak\src

REM Check streamlit_old directory
if exist "%TRANSLATION_DIR%\streamlit_old" (
    echo ⚠️  Found outdated directory: translation\streamlit_old\
    echo    This contains older version of the UI files
    echo    Current integrated version is in: translation\streamlit_app\
    echo.
    echo    Recommended action: Remove streamlit_old directory
    echo    Command: rmdir /s /q "%TRANSLATION_DIR%\streamlit_old"
    echo.
)

REM Check src/translation directory
if exist "%SRC_DIR%\translation" (
    echo ⚠️  Found duplicate directory: src\translation\
    echo    This appears to be a duplicate of the translation\ directory
    echo    Active development should use: translation\
    echo.
    echo    Recommended action: Review and potentially remove src\translation
    echo    Command: rmdir /s /q "%SRC_DIR%\translation"
    echo.
)

echo 🔍 Checking for other potential overlaps...

REM List all app.py files
echo.
echo 📄 Found app.py files:
for /r "d:\Code_stuff\Sanchalak" %%f in (app.py) do echo    - %%f

echo.
echo 📄 Found utils.py files:
for /r "d:\Code_stuff\Sanchalak" %%f in (utils.py) do echo    - %%f

echo.
echo 🎯 Integration Status:
echo ==============================
echo ✅ MAIN UI (INTEGRATED):     translation\streamlit_app\
echo ✅ API SERVICES:              translation\api\
echo ✅ BACKEND ENTRY:             translation\main.py
echo ✅ MODELS ^& SCHEMAS:          translation\models.py
echo.

echo 📋 Cleanup Recommendations:
echo ==============================
echo 1. Keep: translation\streamlit_app\ (main integrated UI)
echo 2. Keep: translation\api\ (API services)
echo 3. Keep: translation\main.py (FastAPI entry point)
echo 4. Remove: translation\streamlit_old\ (outdated UI)
echo 5. Review: src\translation\ (potential duplicate)
echo.

echo 🚀 Quick Start Commands:
echo ==============================
echo # Start the backend API server:
echo cd "%TRANSLATION_DIR%"
echo python main.py
echo.
echo # Start the integrated UI (in another terminal):
echo cd "%TRANSLATION_DIR%\streamlit_app"
echo streamlit run app.py
echo.

echo 📚 Documentation:
echo ==============================
echo 📖 API Integration Guide: translation\API_INTEGRATION_README.md
echo 🔧 Health Check: Available in UI sidebar
echo 🧪 API Testing: Available in UI expander section
echo.

echo ✅ Cleanup analysis complete!
echo.
echo 💡 Note: The main UI in translation\streamlit_app\ is fully integrated
echo    with the API services and includes comprehensive error handling,
echo    health monitoring, and testing capabilities.

pause
