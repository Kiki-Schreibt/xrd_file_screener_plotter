@echo off
for %%i in (*.xy) do (
   more +2 "%%i">"%%i.temp"
   del "%%i"
)
ren *.temp *.