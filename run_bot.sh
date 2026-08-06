#!/bin/zsh
 
# Ve a la carpeta del proyecto (AJUSTA esta ruta a la tuya)
cd "/Users/FamiliaNavarrete/Desktop/Agente Criptomonedas"
 
# Corre el bot usando el Python del entorno virtual.
# Las credenciales se cargan solas desde el archivo .env de esta misma carpeta.
venv/bin/python3 main.py >> ejecucion.log 2>&1
 