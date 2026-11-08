@echo off
rem Installation sans lancement, puis raccourci facultatif sur le Bureau (aucun réglage du système touché).
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "ICI=%~dp0"
echo.
echo Installation de CODAP C9.7 Jupe-Fond : préparation de l'environnement local, une seule fois.
echo.
call "%ICI%Lancer_CodapC97JupeFond.bat" -i
if errorlevel 1 exit /b %errorlevel%

echo.
set "REP="
set /p "REP=Créer un raccourci sur le Bureau ? [O/n] : "
if /i "%REP%"=="n" goto :fin
set "RAC_CIBLE=%ICI%Lancer_CodapC97JupeFond.bat"
set "RAC_DIR=%ICI%"
set "RAC_ICONE=%ICI%src\codap_c_97_jupe_fond\assets\icone.ico"
set "RAC_NOM=CODAP C9.7 Jupe-Fond"
powershell -NoProfile -Command "$d = $env:RAC_DOSSIER; if (-not $d) { $d = [Environment]::GetFolderPath('Desktop') }; $s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d ($env:RAC_NOM + '.lnk'))); $s.TargetPath = $env:RAC_CIBLE; $s.WorkingDirectory = $env:RAC_DIR; $s.WindowStyle = 7; if (Test-Path $env:RAC_ICONE) { $s.IconLocation = $env:RAC_ICONE }; $s.Save()"
if errorlevel 1 (echo Le raccourci n'a pas pu être créé.) else (echo Raccourci créé.)

:fin
echo.
echo Installation terminée. Lancez CODAP C9.7 Jupe-Fond avec Lancer_CodapC97JupeFond.bat ou le raccourci.
echo.
if not defined AMORCE_SANS_PAUSE pause
exit /b 0
