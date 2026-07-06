@echo off
echo ========================================
echo  Building Resource Pack Creator (.exe)
echo ========================================
echo.

:: Install dependencies
pip install pyinstaller tkinterdnd2

:: Build the exe
pyinstaller ResourcePackCreator.spec --clean

echo.
echo ========================================
if exist "dist\ResourcePackCreator.exe" (
    echo  BUILD SUCCESSFUL!
    echo  Output: dist\ResourcePackCreator.exe
) else (
    echo  BUILD FAILED — check errors above
)
echo ========================================
pause
