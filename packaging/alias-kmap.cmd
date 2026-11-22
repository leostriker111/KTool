@echo off
rem Alias historico: 'kmap' hace exactamente lo mismo que 'ktool'.
rem El instalador copia este archivo como kmap.cmd junto a ktool.exe.
"%~dp0ktool.exe" %*
