@echo off
rem Lanceur Windows. Un double-clic suffit.
rem Trouve un Python accepté en 64 bits, avec Tk (py -3.x de la plage, puis python), puis appelle outils\amorce.py.
rem Si aucun Python de la plage n'a Tk, un second passage retient un Python sans Tk : amorce.py explique alors l'absence de Tk (code 11).
rem Toute la logique (environnement local, installation, relance rapide, journal) est dans amorce.py.
rem Options de l'application : -t (essai, console gardée), -V (version), -h (aide).
rem Options du lanceur : -u (désinstaller), -i (installer sans lancer), -f (réinstaller), -o (hors ligne).
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "ICI=%~dp0"
set "PYTHONUTF8=1"
set "AMORCE_PAUSE=bat"
set "PYCMD="
for /f "tokens=1,2 delims=." %%a in ("3.11") do set "MIN_MAJ=%%a" & set "MIN_MIN=%%b"
for /f "tokens=1,2 delims=." %%a in ("3.13") do set "MAX_MAJ=%%a" & set "MAX_MIN=%%b"

rem Premier passage : un Python de la plage, 64 bits, qui charge Tk (la fenêtre en a besoin).
set "IMPORTS=import sys,struct,tkinter; tkinter.Tcl().eval('info patchlevel')"
call :chercher
rem Second passage : sans l'exigence de Tk, pour que amorce.py dise précisément ce qui manque.
if not defined PYCMD set "IMPORTS=import sys,struct"
if not defined PYCMD call :chercher
if not defined PYCMD goto :python_absent

%PYCMD% "%ICI%outils\amorce.py" %*
set "CODE=%errorlevel%"
if "%CODE%"=="0" exit /b 0
if defined AMORCE_SANS_PAUSE exit /b %CODE%
echo.
echo Le lancement de CODAP C9.7 Jupe-Fond s'est arrêté, code %CODE%.
echo Le détail est dans le journal indiqué ci-dessus, ou dans %LOCALAPPDATA%\CodapC97JupeFond\journaux.
echo.
pause
exit /b %CODE%

:chercher
where py >nul 2>nul
if not errorlevel 1 for /l %%m in (%MAX_MIN%,-1,%MIN_MIN%) do if not defined PYCMD call :essai_py %%m
if not defined PYCMD call :essai_python
goto :eof

:essai_py
call py -%MAX_MAJ%.%1 -c "%IMPORTS%; sys.exit(0 if struct.calcsize('P')==8 else 1)" >nul 2>nul
if not errorlevel 1 set "PYCMD=py -%MAX_MAJ%.%1"
goto :eof

:essai_python
python -c "%IMPORTS%; sys.exit(0 if (%MIN_MAJ%,%MIN_MIN%) <= sys.version_info[:2] <= (%MAX_MAJ%,%MAX_MIN%) and struct.calcsize('P')==8 else 1)" >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
goto :eof

:python_absent
echo.
echo CODAP C9.7 Jupe-Fond a besoin de Python 3.11 à 3.13, en 64 bits, et ne l'a pas trouvé sur ce poste.
echo.
echo   1. Téléchargez Python depuis https://www.python.org/downloads/
echo      et choisissez une version entre 3.11 et 3.13.
echo   2. Dans l'installateur, laissez cochées les options "tcl/tk and IDLE" et "py launcher".
echo      Vous n'avez pas besoin des droits d'administrateur : choisissez "Install for me only".
echo   3. Fermez cette fenêtre et relancez Lancer_CodapC97JupeFond.bat.
echo.
echo Ce lanceur n'installe jamais Python à votre place et ne modifie aucun réglage du système.
echo.
if not defined AMORCE_SANS_PAUSE pause
exit /b 10
