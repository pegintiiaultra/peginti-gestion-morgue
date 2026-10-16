@echo off
rem POINT D'ENTREE UNIQUE — Windows : double-clic sur ce fichier
cd /d "%~dp0application" && call installer.bat %*
