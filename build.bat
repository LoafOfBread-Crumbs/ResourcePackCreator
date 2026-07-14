@echo off
echo ========================================
echo  Building Resource Pack Creator (.exe)
echo ========================================
echo.

:: Install / update build dependencies
pip install -r requirements-build.txt

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
