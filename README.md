# Bot de Cartera Cripto

Este proyecto es un bot personal que revisa una cartera de criptomonedas y avisa,
por Telegram, cómo va la inversión: si está ganando o perdiendo, cuánto, y un
resumen general con gráficos en PDF.

## Qué hace el bot

- Revisa los precios de las criptomonedas configuradas.
- Calcula cuánto se invirtió, cuánto vale hoy esa inversión, y la ganancia o
  pérdida en dólares y en porcentaje.
- Si una moneda está en pérdida, calcula un tiempo aproximado de recuperación
  (es solo una estimación, no una garantía).
- Genera un pequeño análisis de tendencia para cada moneda con ayuda de
  inteligencia artificial.
- Guarda un historial de cada revisión, para poder comparar cómo va la cartera
  con el paso del tiempo.
- Envía por Telegram un mensaje corto con el resumen, más un PDF con el detalle
  completo, tablas y gráficos.

Está pensado para correr solo, de forma automática, por ejemplo una vez por
semana.

## Antes de usarlo

Se necesita:

- Python instalado.
- Un bot de Telegram (se crea gratis hablando con **@BotFather** en Telegram).
- Una clave gratuita de Gemini (inteligencia artificial de Google), disponible en
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

Los precios de las criptomonedas se obtienen directamente de Binance, así que no
hace falta cuenta ni clave para esa parte.

## Instalación

Las instrucciones cambian un poco según el sistema operativo. Elegir la sección
correspondiente.

### Windows

1. Instalar Python (si no está instalado) desde
   [python.org/downloads](https://www.python.org/downloads/). **Importante:**
   durante la instalación, marcar la casilla **"Add python.exe to PATH"** antes
   de darle a "Install Now".
2. Abrir la **Símbolo del sistema (CMD)** o **PowerShell** y ubicarse en la
   carpeta del proyecto:
   ```bat
   cd ruta\a\la\carpeta\del\proyecto
   ```
3. Crear y activar el entorno virtual:
   ```bat
   python -m venv venv
   venv\Scripts\activate
   ```
   > Si usa PowerShell y aparece un error de permisos al activar, ejecutar antes:
   > `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
4. Instalar las dependencias:
   ```bat
   python -m pip install google-genai reportlab requests matplotlib pandas numpy python-dotenv
   ```

### macOS

1. Instalar Python (si no está instalado). La forma más simple es con
   [Homebrew](https://brew.sh):
   ```bash
   brew install python
   ```
   También se puede descargar el instalador desde
   [python.org/downloads](https://www.python.org/downloads/).
2. Abrir la app **Terminal** y ubicarse en la carpeta del proyecto:
   ```bash
   cd ruta/a/la/carpeta/del/proyecto
   ```
3. Crear y activar el entorno virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Instalar las dependencias:
   ```bash
   python3 -m pip install google-genai reportlab requests matplotlib pandas numpy python-dotenv
   ```

### Linux

1. Instalar Python y las herramientas necesarias (en distribuciones basadas en
   Debian/Ubuntu):
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv
   ```
   En otras distribuciones, usar el gestor de paquetes correspondiente (`dnf`,
   `pacman`, etc.).
2. Ubicarse en la carpeta del proyecto:
   ```bash
   cd ruta/a/la/carpeta/del/proyecto
   ```
3. Crear y activar el entorno virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Instalar las dependencias:
   ```bash
   python3 -m pip install google-genai reportlab requests matplotlib pandas numpy python-dotenv
   ```

### Notas comunes a los tres sistemas

- Si `pip install ...` da el error "command not found", usar siempre
  `python3 -m pip install ...` (Windows: `python -m pip install ...`) en su
  lugar. Si ni así funciona, correr primero `python3 -m ensurepip --upgrade`
  (Windows: `python -m ensurepip --upgrade`).
- El entorno virtual queda activado solo en la ventana de terminal donde se
  ejecutó el comando `activate`. Hay que activarlo de nuevo cada vez que se
  abra una terminal nueva antes de correr el bot.
- Para salir del entorno virtual en cualquier sistema, el comando es:
  ```bash
  deactivate
  ```

## Configuración

El bot necesita tres datos para funcionar: la clave de Gemini, el token del bot
de Telegram y el ID del chat donde debe enviar los mensajes.

Estos datos van en un archivo llamado `.env`, ubicado en la misma carpeta que
`main.py`. Ese archivo nunca se sube a GitHub (ya viene excluido en
`.gitignore`), así que las credenciales quedan siempre a salvo sin tener que
acordarse de borrar nada antes de subir el código.

**Cómo crearlo:**

1. En la carpeta del proyecto hay un archivo llamado `.env.example`, que sirve
   de plantilla.
2. Se hace una copia de ese archivo y se renombra a `.env`:
   - Windows (CMD):
     ```bat
     copy .env.example .env
     ```
   - macOS / Linux:
     ```bash
     cp .env.example .env
     ```
3. Se abre `.env` con cualquier editor de texto y se reemplaza cada valor por
   el real:
   ```
   GEMINI_API_KEY=clave_real_de_gemini
   TELEGRAM_TOKEN=token_real_del_bot
   TELEGRAM_CHAT_ID=id_real_del_chat
   ```
4. Se guarda el archivo. Listo — el bot lo lee automáticamente cada vez que
   se ejecuta, sin pasos adicionales.

Para conseguir el ID del chat, se le escribe cualquier mensaje al bot y luego se
visita esta dirección en el navegador, reemplazando el token:

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

Ahí aparece un número llamado `"id"`, dentro de `"chat"` — ese es el ID que hay
que copiar.

## Cargar las monedas de la cartera

Dentro del archivo `main.py` hay una lista llamada `CARTERA`, donde se agregan
las monedas junto con la cantidad comprada y el precio de compra. Ejemplo:

```python
CARTERA = {
    "LINKUSDT": [
        {"cantidad": 50, "precio_compra": 12.30},
    ],
}
```

Si una misma moneda se compró varias veces a precios distintos, se agregan todas
las compras dentro de la misma lista, y el bot calcula el precio promedio solo.

## Cómo correrlo

Con el entorno virtual activado:

- Windows:
  ```bat
  python main.py
  ```
- macOS / Linux:
  ```bash
  python3 main.py
  ```

Al terminar, debería llegar un mensaje y un PDF al chat de Telegram configurado.
La primera vez que se corre no habrá gráfico de evolución todavía, porque recién
se está guardando el primer registro. A partir de la segunda vez ya aparece.

## Importante

- Nada de lo que genera este bot es una recomendación financiera. Los datos y
  análisis son solo una referencia informativa.
- Las claves y tokens nunca deben compartirse ni subirse a GitHub. Si alguna se
  llega a exponer por error, hay que revocarla y generar una nueva de inmediato.
