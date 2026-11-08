@echo off
rem Désinstallation propre : retire l'environnement local, propose de garder ou non les données.
rem Le code rendu est celui du retrait : 0 réussi, 10 Python introuvable (retrait direct tenté), 15 installation en cours, 18 suppression impossible.
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "ICI=%~dp0"
set "CODE=0"
echo.
echo Désinstallation de CODAP C9.7 Jupe-Fond.
echo Cet outil retire l'environnement local des bibliothèques. Vos fichiers de travail ne sont pas touchés.
echo.
call "%ICI%Lancer_CodapC97JupeFond.bat" -u
set "CODE=%errorlevel%"
rem Seul le code 10 veut dire « Python introuvable » : les autres échecs (15 verrou, 18 suppression impossible) ne sont pas masqués.
if "%CODE%"=="10" call :retrait_direct
if not "%CODE%"=="0" goto :fin
echo.
set "REP="
set /p "REP=Supprimer aussi vos préférences et vos journaux ? [o/N] : "
if /i not "%REP%"=="o" goto :fin
call "%ICI%Lancer_CodapC97JupeFond.bat" -U
set "CODE=%errorlevel%"
if "%CODE%"=="10" call :donnees_a_la_main

:fin
echo.
if "%CODE%"=="0" (
    echo Pour retirer l'application elle-même, supprimez simplement son dossier.
) else (
    echo La désinstallation n'est pas terminée : code %CODE%. Lisez le message ci-dessus, puis relancez.
)
echo.
if not defined AMORCE_SANS_PAUSE pause
exit /b %CODE%

:retrait_direct
echo Python est introuvable : suppression directe du dossier .runtime.
if exist "%ICI%.runtime" rd /s /q "%ICI%.runtime"
if exist "%ICI%.runtime" (
    echo Le dossier .runtime n'a pas pu être supprimé : fermez l'application puis relancez.
    set "CODE=18"
) else (
    set "CODE=0"
)
goto :eof

:donnees_a_la_main
echo Python est introuvable : vos préférences et journaux ne sont pas retirés.
echo Pour les supprimer, effacez les dossiers %APPDATA%\CodapC97JupeFond et %LOCALAPPDATA%\CodapC97JupeFond.
goto :eof
