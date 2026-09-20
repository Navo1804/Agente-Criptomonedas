# Agente Criptomonedas 🤖📈

Bot personal de monitoreo de cartera cripto (estrategia DCA) que corre de forma automática, analiza tus posiciones con estructura de mercado (SMC), genera un informe en PDF y te lo envía por Telegram.

## ¿Qué hace?

1. Descarga el historial diario completo de cada par desde la API pública de Binance (sin necesidad de API key).
2. Analiza la estructura de mercado (Smart Money Concepts): tendencia, BOS/ChoCh, liquidez y Order Blocks.
3. Calcula el estado real de tu inversión por par (invertido, valor actual, ganancia/pérdida, días estimados de recuperación si estás en pérdida).
4. Genera un análisis narrativo con IA (Gemini, con respaldo automático en Groq si Gemini falla) tanto por par como un informe ejecutivo general comparado con la corrida anterior.
5. Arma un PDF con portada, tablas, gráficos y el análisis de IA.
6. Envía un resumen corto y el PDF completo a un chat de Telegram.
7. Guarda un historial persistente en CSV para poder graficar la evolución de la cartera entre corridas.

## Requisitos

- Python 3.10+
- Una cuenta de [Google AI Studio](https://aistudio.google.com/) (API key de Gemini, plan gratuito funciona)
- Una cuenta de [Groq](https://console.groq.com/) (API key gratuita, usada como respaldo si Gemini falla o se satura)
- Un bot de Telegram (token vía [@BotFather](https://t.me/BotFather)) y el ID del chat donde quieres recibir los reportes

## Instalación

```bash
# 1. Clona o copia el proyecto y entra a la carpeta
cd "Agente Criptomonedas"

# 2. Crea y activa un entorno virtual
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# 3. Instala las dependencias
python3 -m pip install --upgrade pip
python3 -m pip install python-dotenv google-genai requests numpy pandas matplotlib reportlab
```

## Configuración

Crea un archivo `.env` en la misma carpeta que `main.py` con este contenido (reemplaza con tus valores reales):

```env
GEMINI_API_KEY=tu_api_key_de_gemini
GROQ_API_KEY=tu_api_key_de_groq
TELEGRAM_TOKEN=tu_token_del_bot
TELEGRAM_CHAT_ID=tu_chat_id
```

> ⚠️ El archivo `.env` nunca debe subirse a GitHub. Ya está excluido en `.gitignore`.

### Tu cartera

Edita el diccionario `CARTERA` en `main.py` con tus pares reales (símbolo de Binance, formato `PARUSDT`) y tus compras:

```python
CARTERA = {
    "LINKUSDT": [
        {"cantidad": 4.02, "precio_compra": 12.41},
        {"cantidad": 2.48, "precio_compra": 9.24},   # DCA: puedes agregar varias compras por par
    ],
    # ...agrega tus propios pares aquí
}
```

Si compraste el mismo par varias veces, agrega cada compra como un elemento separado de la lista — el script calcula automáticamente el precio promedio ponderado.

## Uso manual

```bash
source venv/bin/activate
python3 main.py
```

Al terminar, recibirás un mensaje resumen y el PDF completo en tu chat de Telegram, y quedará una copia del historial en `historial/historial_cartera.csv`.

## Automatización

### macOS (launchd)

El proyecto incluye `com.familianavarrete.agentecriptomonedas.plist` + `run_bot.sh`, configurado para correr automáticamente los sábados a las 11:00 AM.

```bash
launchctl unload ~/Library/LaunchAgents/com.familianavarrete.agentecriptomonedas.plist
cp com.familianavarrete.agentecriptomonedas.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.familianavarrete.agentecriptomonedas.plist
```

> ⚠️ El proyecto debe vivir **fuera** de una carpeta sincronizada con iCloud Drive (por ejemplo, directamente en el home del usuario) — iCloud interfiere con los permisos de launchd en macOS Catalina y versiones posteriores.

### Windows

Equivalente en desarrollo (`run_bot.bat` + Programador de tareas de Windows). Se actualizará esta sección cuando esté listo.

## Límites a tener en cuenta

- **Gemini (plan gratuito):** 20 peticiones/día para `gemini-2.5-flash`. Cada corrida hace ~9 llamadas (una por par + el informe ejecutivo), así que 2-3 corridas seguidas en el mismo día agotan la cuota. Se reinicia cada 24 h.
- **Respaldo con Groq:** si Gemini falla (cuota agotada, error 503 por alta demanda, etc.), el bot reintenta automáticamente con Groq (`openai/gpt-oss-120b`) antes de rendirse. Si ambos fallan, el reporte se genera igual con un texto de aviso en vez del análisis de IA — el bot nunca se cae por esto.

## Estructura del proyecto

```
Agente Criptomonedas/
├── main.py
├── .env                          # credenciales (no se sube a git)
├── run_bot.sh                    # wrapper para launchd (macOS)
├── run_bot.bat                   # wrapper para Windows (en desarrollo)
├── com.familianavarrete.agentecriptomonedas.plist
└── historial/
    └── historial_cartera.csv     # historial persistente entre corridas
```

## Aviso

Este bot es una herramienta de seguimiento personal. El análisis técnico (SMC) y el análisis generado por IA son referencias informativas basadas en datos históricos, **no constituyen asesoría financiera**.