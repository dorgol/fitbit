@echo off
setlocal enabledelayedexpansion

:: Set output file
set OUTPUT_FILE=project_export.txt

:: Clear the output file
echo. > %OUTPUT_FILE%

:: Generate tree structure
echo ========================================= >> %OUTPUT_FILE%
echo PROJECT TREE STRUCTURE >> %OUTPUT_FILE%
echo ========================================= >> %OUTPUT_FILE%
echo. >> %OUTPUT_FILE%

:: Use tree command to show directory structure (src folder only)
if exist "src" (
    cd src
    tree /F /A >> ..\%OUTPUT_FILE%
    cd ..
) else (
    echo src directory not found! >> %OUTPUT_FILE%
)

echo. >> %OUTPUT_FILE%
echo. >> %OUTPUT_FILE%
echo ========================================= >> %OUTPUT_FILE%
echo FILE CONTENTS >> %OUTPUT_FILE%
echo ========================================= >> %OUTPUT_FILE%
echo. >> %OUTPUT_FILE%

:: Concatenate only Python project files from src directory
for /r src %%f in (*.py *.txt *.md *.json *.yml *.yaml *.cfg *.ini) do (
    if exist "%%f" (
        echo. >> %OUTPUT_FILE%
        echo ----------------------------------------- >> %OUTPUT_FILE%
        echo FILE: %%f >> %OUTPUT_FILE%
        echo ----------------------------------------- >> %OUTPUT_FILE%
        type "%%f" >> %OUTPUT_FILE%
        echo. >> %OUTPUT_FILE%
        echo. >> %OUTPUT_FILE%
    )
)

echo Export completed! Check %OUTPUT_FILE%
pause