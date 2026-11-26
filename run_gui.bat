@echo off
cd /d "%~dp0"
py -3 tr_ngage_outfit_gui.py 2>nul || python tr_ngage_outfit_gui.py
