@echo off
title Tehsil AI Operator - MS Word Sync Add-in Setup
echo ========================================================
echo Tehsil AI Operator - MS Word Sync Add-in Setup
echo ========================================================
echo.
echo This script will install the Tehsil AI Operator add-in directly
echo into your Microsoft Word application.
echo.

:: Define the target folder where Word scans for sideloaded developer manifests
set TARGET_DIR=%APPDATA%\Microsoft\Office\WEF\Developer

echo [1/3] Creating target catalog directory...
if not exist "%TARGET_DIR%" (
    mkdir "%TARGET_DIR%"
)

echo [2/3] Copying manifest.xml to trusted catalog folder...
copy /Y "manifest.xml" "%TARGET_DIR%\tehsil_ai_operator_manifest.xml" >nul
if %errorlevel% neq 0 (
    echo [ERROR] Failed to copy manifest.xml. Make sure you are running this script in the project directory.
    pause
    exit /b %errorlevel%
)

echo [3/3] Registering catalog as trusted in Windows Registry...
:: Registers the directory as a Trusted Catalog for Office WEF (Web Extension Framework)
reg add "HKCU\Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\{50fff088-06d4-4a63-8826-5c9888e4089e}" /v "Url" /t REG_SZ /d "%TARGET_DIR%" /f >nul
reg add "HKCU\Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\{50fff088-06d4-4a63-8826-5c9888e4089e}" /v "Flags" /t REG_DWORD /d 1 /f >nul

echo.
echo ========================================================
echo Setup Completed Successfully! (सफलतापूर्वक इंस्टॉल हुआ)
echo ========================================================
echo.
echo Next Steps (आगे के चरण):
echo 1. Open Microsoft Word (MS Word खोलें).
echo 2. Go to the "Insert" (डालें/इन्सर्ट) tab -> Click "My Add-ins" (मेरे एड-इन्स).
echo 3. Go to the "Developer Add-ins" or "Shared Folder" section.
echo 4. Select "Tehsil AI Operator" and click "Add" to open the sidebar.
echo.
pause
