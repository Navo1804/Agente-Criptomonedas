import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google import genai
import requests

import matplotlib
matplotlib.use("Agg")  # backend sin pantalla, necesario para correr en servidor
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)

# ============================================================
# CONFIGURACIÓN
# ⚠️ Las credenciales NUNCA van escritas aquí en el código.
#
# Se leen automáticamente desde un archivo llamado ".env", ubicado en esta
# misma carpeta, con este contenido (reemplaza con tus valores reales):
#
#     GEMINI_API_KEY=tu_api_key_de_gemini
#     TELEGRAM_TOKEN=tu_token_del_bot
#     TELEGRAM_CHAT_ID=tu_chat_id
#
# Ese archivo ".env" está excluido en .gitignore, así que nunca se sube a
# GitHub por accidente, sin importar cuántas veces edites o subas el código.
# ============================================================
RUTA_PROYECTO = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(RUTA_PROYECTO, ".env"))

cliente = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

CARPETA_TMP = "/tmp/reporte_cartera"
os.makedirs(CARPETA_TMP, exist_ok=True)

# Carpeta persistente para el historial (NO usar /tmp, se borra al reiniciar el servidor)
HISTORIAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial")
os.makedirs(HISTORIAL_DIR, exist_ok=True)
HISTORIAL_CSV = os.path.join(HISTORIAL_DIR, "historial_cartera.csv")

# ============================================================
# TU CARTERA
# Las claves son símbolos de Binance (par + USDT, SIN guion): "LINKUSDT", "BTCUSDT", etc.
# Puedes verificar el símbolo exacto en https://www.binance.com/es/trade/LINK_USDT
#
# "cantidad" = unidades de la criptomoneda que compraste (NO dólares).
# Si solo sabes cuánto invertiste en USD, calcula: cantidad = dolares / precio_compra
#
# Si compraste el mismo par en varios precios distintos (DCA / varias órdenes),
# agrega cada compra como un elemento de la lista. El script calcula automáticamente
# el precio promedio ponderado y la cantidad total para ese par.
# ============================================================
CARTERA = {
    "LINKUSDT": [
        {"cantidad": 50, "precio_compra": 12.30},
    ],
    "BTCUSDT": [
        {"cantidad": 0.05, "precio_compra": 60000},
    ],
    "ETHUSDT": [
        {"cantidad": 1.2, "precio_compra": 3200},
    ],
    "ROSEUSDT": [
        {"cantidad": 5143.2516, "precio_compra": 0.01043},
        {"cantidad": 2000, "precio_compra": 0.009},
    ],
    "GRTUSDT": [
        {"cantidad": 0, "precio_compra": 0},  # <-- reemplaza con tus datos reales
    ],
    "POLUSDT": [
        {"cantidad": 0, "precio_compra": 0},  # <-- reemplaza con tus datos reales
    ],
}


def consolidar_posicion(lotes):
    """
    Recibe la lista de compras (lotes) de un mismo par y devuelve una posición
    consolidada: cantidad total y precio de compra promedio PONDERADO por cuánto
    invertiste en cada lote (no un promedio simple de precios).
    """
    cantidad_total = sum(lote["cantidad"] for lote in lotes)
    invertido_total = sum(lote["cantidad"] * lote["precio_compra"] for lote in lotes)
    precio_promedio = invertido_total / cantidad_total if cantidad_total else 0

    return {
        "cantidad": cantidad_total,
        "precio_compra": precio_promedio,
        "lotes": lotes,
    }


# ============================================================
# ANÁLISIS SMC
# ============================================================
def analizar_estructura_smc(velas):
    if len(velas) < 10:
        return {"tendencia": "Indefinida", "bos": [], "choch": [], "liquidez": [], "order_blocks": []}

    bos, choch, liquidez, order_blocks = [], [], [], []
    tendencia_actual = "Alcista"
    ultimo_alto_confirmado = max(velas[0]['high'], velas[1]['high'])
    ultimo_bajo_confirmado = min(velas[0]['low'], velas[1]['low'])

    for i in range(2, len(velas) - 1):
        vela_anterior = velas[i - 1]
        vela_actual = velas[i]
        vela_siguiente = velas[i + 1]

        # 1. Evaluar quiebres contra el estado anterior, antes de actualizar extremos
        if vela_actual['close'] > ultimo_alto_confirmado:
            if tendencia_actual == "Alcista":
                bos.append({"tipo": "BOS Alcista", "precio_quiebre": ultimo_alto_confirmado, "index": i})
            elif tendencia_actual == "Bajista":
                tendencia_actual = "Alcista"
                choch.append({"tipo": "ChoCh Alcista", "precio_quiebre": ultimo_alto_confirmado, "index": i})
        elif vela_actual['close'] < ultimo_bajo_confirmado:
            if tendencia_actual == "Bajista":
                bos.append({"tipo": "BOS Bajista", "precio_quiebre": ultimo_bajo_confirmado, "index": i})
            elif tendencia_actual == "Alcista":
                tendencia_actual = "Bajista"
                choch.append({"tipo": "ChoCh Bajista", "precio_quiebre": ultimo_bajo_confirmado, "index": i})

        # 2. Pivotes estructurales y liquidez
        es_alto_estructural = vela_actual['high'] > vela_anterior['high'] and vela_actual['high'] > vela_siguiente['high']
        es_bajo_estructural = vela_actual['low'] < vela_anterior['low'] and vela_actual['low'] < vela_siguiente['low']

        if es_alto_estructural:
            if vela_actual['high'] != 0 and abs(vela_actual['high'] - ultimo_alto_confirmado) / vela_actual['high'] < 0.001:
                liquidez.append({"tipo": "Techo Falso (Liquidez por encima)", "precio": vela_actual['high'], "index": i})
            ultimo_alto_confirmado = vela_actual['high']

        if es_bajo_estructural:
            if vela_actual['low'] != 0 and abs(vela_actual['low'] - ultimo_bajo_confirmado) / vela_actual['low'] < 0.001:
                liquidez.append({"tipo": "Piso Falso (Liquidez por debajo)", "precio": vela_actual['low'], "index": i})
            ultimo_bajo_confirmado = vela_actual['low']

        # 3. Order Blocks (demanda y oferta)
        es_vela_bajista = vela_actual['close'] < vela_actual['open']
        es_vela_alcista = vela_actual['close'] > vela_actual['open']
        es_impulso_alcista = vela_siguiente['close'] > vela_siguiente['open'] and \
            (vela_siguiente['close'] - vela_siguiente['open']) > (vela_actual['open'] - vela_actual['close']) * 1.5
        es_impulso_bajista = vela_siguiente['close'] < vela_siguiente['open'] and \
            (vela_siguiente['open'] - vela_siguiente['close']) > (vela_actual['close'] - vela_actual['open']) * 1.5

        if es_vela_bajista and es_impulso_alcista:
            order_blocks.append({"tipo": "Alcista (Demand OB)", "precio_alto": vela_actual['high'], "precio_bajo": vela_actual['low'], "index": i})
        if es_vela_alcista and es_impulso_bajista:
            order_blocks.append({"tipo": "Bajista (Supply OB)", "precio_alto": vela_actual['high'], "precio_bajo": vela_actual['low'], "index": i})

    return {"tendencia": tendencia_actual, "bos": bos, "choch": choch, "liquidez": liquidez, "order_blocks": order_blocks}


def calcular_score_smc(resultado):
    score = 0
    if resultado["tendencia"] == "Alcista":
        score += 2
    score += len(resultado["bos"]) * 1
    score -= len(resultado["choch"]) * 1
    score += len(resultado["order_blocks"]) * 2
    return max(score, 0)


# ============================================================
# ESTADO DE LA INVERSIÓN
# ============================================================
def estimar_dias_recuperacion(precio_actual, precio_objetivo, serie_cierres, ventana=90):
    """
    Proyecta, de forma compuesta, el retorno diario PROMEDIO de los últimos `ventana` días
    hacia adelante hasta alcanzar `precio_objetivo`.

    Es una extrapolación estadística simple (asume que la tendencia reciente se mantiene),
    NO una predicción confiable. El mercado cripto puede comportarse de forma muy distinta.
    """
    retornos = serie_cierres.pct_change().dropna().tail(ventana)
    if len(retornos) == 0:
        return None

    media_diaria = retornos.mean()
    if media_diaria <= 0:
        return None

    dias = np.log(precio_objetivo / precio_actual) / np.log(1 + media_diaria)
    return round(dias) if dias > 0 else 0


def calcular_estado_inversion(posicion, historial):
    precio_actual = historial["Close"].iloc[-1]
    precio_compra = posicion["precio_compra"]
    cantidad = posicion["cantidad"]

    invertido = cantidad * precio_compra
    valor_actual = cantidad * precio_actual
    ganancia_usd = valor_actual - invertido
    ganancia_pct = (precio_actual - precio_compra) / precio_compra * 100
    en_ganancia = ganancia_usd >= 0

    dias_recuperacion = None
    if not en_ganancia:
        dias_recuperacion = estimar_dias_recuperacion(precio_actual, precio_compra, historial["Close"])

    return {
        "precio_compra": precio_compra,
        "precio_actual": precio_actual,
        "cantidad": cantidad,
        "invertido": invertido,
        "valor_actual": valor_actual,
        "ganancia_usd": ganancia_usd,
        "ganancia_pct": ganancia_pct,
        "en_ganancia": en_ganancia,
        "dias_recuperacion": dias_recuperacion,
    }


# ============================================================
# GRÁFICOS (matplotlib -> PNG, luego insertados en el PDF)
# ============================================================
def grafico_resumen_cartera(resultados, ruta_salida):
    tickers = list(resultados.keys())
    porcentajes = [resultados[t]["estado"]["ganancia_pct"] for t in tickers]
    colores = ["#16a34a" if p >= 0 else "#dc2626" for p in porcentajes]

    fig, ax = plt.subplots(figsize=(7, 3))
    ax.bar(tickers, porcentajes, color=colores)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Rendimiento por par (%)")
    ax.set_ylabel("% Ganancia / Pérdida")
    for i, p in enumerate(porcentajes):
        ax.text(i, p, f"{p:.1f}%", ha="center", va="bottom" if p >= 0 else "top", fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=140)
    plt.close(fig)


# ============================================================
# HISTORIAL (CSV persistente, una fila por par por cada corrida)
# ============================================================
def guardar_historial(resultados, resumen_total):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    filas = []

    for ticker_symbol, datos in resultados.items():
        estado = datos["estado"]
        filas.append({
            "fecha": fecha,
            "ticker": ticker_symbol,
            "precio_actual": estado["precio_actual"],
            "invertido": estado["invertido"],
            "valor_actual": estado["valor_actual"],
            "ganancia_usd": estado["ganancia_usd"],
            "ganancia_pct": estado["ganancia_pct"],
        })

    # Fila adicional con el total combinado de la cartera
    filas.append({
        "fecha": fecha,
        "ticker": "TOTAL",
        "precio_actual": None,
        "invertido": resumen_total["invertido"],
        "valor_actual": resumen_total["valor_actual"],
        "ganancia_usd": resumen_total["ganancia_usd"],
        "ganancia_pct": resumen_total["ganancia_pct"],
    })

    df_nuevo = pd.DataFrame(filas)
    escribir_encabezado = not os.path.exists(HISTORIAL_CSV)
    df_nuevo.to_csv(HISTORIAL_CSV, mode="a", header=escribir_encabezado, index=False)


def leer_historial():
    if not os.path.exists(HISTORIAL_CSV):
        return None
    df = pd.read_csv(HISTORIAL_CSV, parse_dates=["fecha"])
    return df


def grafico_evolucion(df, ticker_symbol, ruta_salida, titulo):
    """
    Grafica la evolución del % de ganancia/pérdida de un ticker (o 'TOTAL') a lo largo
    de las corridas históricas guardadas en el CSV. Devuelve False si no hay suficiente
    historial todavía (se necesitan al menos 2 puntos para trazar una línea).
    """
    df_filtrado = df[df["ticker"] == ticker_symbol].sort_values("fecha")
    if len(df_filtrado) < 2:
        return False

    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(df_filtrado["fecha"], df_filtrado["ganancia_pct"], marker="o", color="#2563eb", linewidth=1.5)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(titulo)
    ax.set_ylabel("% Ganancia / Pérdida")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=140)
    plt.close(fig)
    return True


# ============================================================
# TELEGRAM
# ============================================================
def obtener_comparacion_anterior(df_historial):
    """
    Compara la corrida actual (última fila 'TOTAL' del CSV) contra la corrida
    inmediatamente anterior. Devuelve None si es la primera corrida registrada
    (no hay nada con qué comparar todavía).
    """
    if df_historial is None:
        return None

    df_total = df_historial[df_historial["ticker"] == "TOTAL"].sort_values("fecha")
    if len(df_total) < 2:
        return None

    actual = df_total.iloc[-1]
    anterior = df_total.iloc[-2]

    return {
        "fecha_anterior": anterior["fecha"],
        "ganancia_pct_anterior": anterior["ganancia_pct"],
        "valor_actual_anterior": anterior["valor_actual"],
        "delta_pct": actual["ganancia_pct"] - anterior["ganancia_pct"],
        "delta_valor_usd": actual["valor_actual"] - anterior["valor_actual"],
        "dias_transcurridos": (actual["fecha"] - anterior["fecha"]).days,
    }


def generar_informe_general(resultados, resumen_total, comparacion):
    """
    Pide a Gemini un informe ejecutivo de máximo ~300 palabras (pensado para
    caber en una sola carilla del PDF) que resuma el estado general de la
    cartera y lo compare contra la corrida anterior (útil si el script corre
    automáticamente, p. ej. una vez por semana vía cron).
    """
    resumen_pares = "\n".join(
        f"- {ticker}: {datos['estado']['ganancia_pct']:.2f}% "
        f"({'ganancia' if datos['estado']['en_ganancia'] else 'pérdida'}), "
        f"tendencia SMC {datos['resultado_smc']['tendencia']}, score {datos['score']}"
        for ticker, datos in resultados.items()
    )

    if comparacion:
        texto_comparacion = (
            f"Hace {comparacion['dias_transcurridos']} días la cartera estaba en "
            f"{comparacion['ganancia_pct_anterior']:.2f}% (valor ${comparacion['valor_actual_anterior']:.2f}). "
            f"Cambio desde entonces: {comparacion['delta_pct']:+.2f} puntos porcentuales, "
            f"${comparacion['delta_valor_usd']:+.2f} en valor."
        )
    else:
        texto_comparacion = "Esta es la primera corrida registrada, no hay una corrida anterior con la cual comparar."

    prompt = f"""
Eres un analista financiero. Con base en estos datos de una cartera de criptomonedas, escribe un informe
ejecutivo en español, de MÁXIMO 300 palabras (debe caber en una sola página), en prosa corrida dividida
en 3-4 párrafos cortos, sin encabezados ni listas markdown.

Resumen total: Invertido=${resumen_total['invertido']:.2f}, Valor actual=${resumen_total['valor_actual']:.2f}, P/L=${resumen_total['ganancia_usd']:.2f} ({resumen_total['ganancia_pct']:.2f}%).

Comparación con la corrida anterior: {texto_comparacion}

Detalle por par:
{resumen_pares}

El informe debe:
1. Dar un panorama general de cómo va la inversión a la fecha.
2. Comparar brevemente esta corrida contra la anterior (mejoró, empeoró o se mantuvo, y por cuánto).
3. Mencionar qué par(es) están destacando, para bien o para mal.
4. Cerrar con una postura general (mantener, revisar, vigilar de cerca), aclarando que es una referencia
   informativa basada en datos históricos y no una asesoría financiera.

Sé directo y evita relleno.
"""
    return cliente.models.generate_content(model="gemini-2.5-flash", contents=prompt).text


def enviar_mensaje(token, chat_id, mensaje):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    respuesta = requests.post(url, data={"chat_id": chat_id, "text": mensaje})
    if respuesta.status_code == 200:
        print("✅ Mensaje enviado correctamente a Telegram")
    else:
        print("❌ Error al enviar mensaje:", respuesta.text)


def enviar_documento(token, chat_id, ruta_pdf, caption=""):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(ruta_pdf, "rb") as archivo:
        respuesta = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption[:1024]},
            files={"document": archivo},
        )
    if respuesta.status_code == 200:
        print("✅ PDF enviado correctamente a Telegram")
    else:
        print("❌ Error al enviar el PDF:", respuesta.text)


# ============================================================
# ANÁLISIS POR PAR (SMC + estado de inversión + Gemini)
# ============================================================
COLUMNAS_KLINES = [
    "open_time", "Open", "High", "Low", "Close", "Volume",
    "close_time", "quote_asset_volume", "trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]
VELAS_POR_SOLICITUD = 1000  # máximo que permite Binance por llamada


def descargar_historial(simbolo_binance, intentos=3, espera_segundos=5):
    """
    Descarga TODO el historial diario disponible en Binance para el símbolo,
    desde su fecha de listado hasta hoy. Binance limita cada solicitud a 1000
    velas, así que se pagina automáticamente hacia adelante hasta traerlas todas.
    No requiere API key (datos de mercado públicos).
    """
    url = "https://api.binance.com/api/v3/klines"

    for intento in range(1, intentos + 1):
        try:
            todas_las_velas = []
            start_time = 0  # 0 = Binance empieza desde la fecha de listado del par

            while True:
                params = {
                    "symbol": simbolo_binance,
                    "interval": "1d",
                    "limit": VELAS_POR_SOLICITUD,
                    "startTime": start_time,
                }
                respuesta = requests.get(url, params=params, timeout=15)

                if respuesta.status_code == 400:
                    # Símbolo inválido: no tiene sentido reintentar
                    print(f"❌ Símbolo inválido en Binance: {simbolo_binance} ({respuesta.text})")
                    return None

                if respuesta.status_code != 200:
                    raise requests.RequestException(f"Binance respondió {respuesta.status_code}: {respuesta.text}")

                lote = respuesta.json()
                if not lote:
                    break

                todas_las_velas.extend(lote)

                if len(lote) < VELAS_POR_SOLICITUD:
                    break  # ya llegamos a las velas más recientes, no hay más páginas

                start_time = lote[-1][6] + 1  # close_time de la última vela + 1 ms
                time.sleep(0.2)  # pausa breve para no saturar el rate limit de Binance

            if not todas_las_velas:
                return None

            df = pd.DataFrame(todas_las_velas, columns=COLUMNAS_KLINES)
            for col in ["Open", "High", "Low", "Close"]:
                df[col] = df[col].astype(float)
            df.index = pd.to_datetime(df["open_time"], unit="ms")
            df = df[~df.index.duplicated(keep="first")]
            return df[["Open", "High", "Low", "Close"]]

        except requests.RequestException as e:
            print(f"⏳ Intento {intento}/{intentos}: error con {simbolo_binance} ({e}), reintentando en {espera_segundos}s...")
            time.sleep(espera_segundos)

    return None


def analizar_par(ticker_symbol, lotes):
    posicion = consolidar_posicion(lotes)

    historial = descargar_historial(ticker_symbol)

    if historial is None or historial.empty:
        print(f"⚠️ Sin datos para {ticker_symbol}, se omite.")
        return None

    velas = [
        {"open": fila["Open"], "high": fila["High"], "low": fila["Low"], "close": fila["Close"]}
        for _, fila in historial.iterrows()
    ]

    resultado_smc = analizar_estructura_smc(velas)
    score = calcular_score_smc(resultado_smc)
    estado = calcular_estado_inversion(posicion, historial)

    if resultado_smc["order_blocks"]:
        ob = resultado_smc["order_blocks"][-1]
        zona_ob = f"{ob['precio_bajo']:.4f} - {ob['precio_alto']:.4f}"
        tipo_ob = ob["tipo"]
    else:
        zona_ob = "No encontrado"
        tipo_ob = "N/A"

    recuperacion_txt = (
        f"{estado['dias_recuperacion']} días (estimado)" if estado["dias_recuperacion"] is not None
        else ("N/A" if estado["en_ganancia"] else "Indeterminado (sin tendencia positiva reciente)")
    )

    prompt = f"""
Actúa como analista SMC para {ticker_symbol}.
Datos técnicos: Tendencia={resultado_smc['tendencia']}, BOS={len(resultado_smc['bos'])}, ChoCh={len(resultado_smc['choch'])}, OBs={len(resultado_smc['order_blocks'])}, Score={score}.
Mi posición: Invertido=${estado['invertido']:.2f}, Valor actual=${estado['valor_actual']:.2f}, P/L={estado['ganancia_pct']:.2f}% ({'ganancia' if estado['en_ganancia'] else 'pérdida'}), Recuperación estimada={recuperacion_txt}.

Responde en máximo 500 caracteres, directo, sin saludos:
1. Resumen técnico breve.
2. Estado de mi posición.
3. Si estoy perdiendo, comenta la recuperación estimada con cautela (es una proyección, no garantía).
4. Decisión sugerida: Comprar más, Vender, o Mantener/Esperar.
5. Confianza: Alta/Media/Baja.
"""
    respuesta_gemini = cliente.models.generate_content(model="gemini-2.5-flash", contents=prompt).text

    return {
        "historial": historial,
        "resultado_smc": resultado_smc,
        "score": score,
        "estado": estado,
        "posicion": posicion,
        "zona_ob": zona_ob,
        "tipo_ob": tipo_ob,
        "respuesta_gemini": respuesta_gemini,
    }


# ============================================================
# GENERACIÓN DEL PDF DETALLADO
# ============================================================
def generar_pdf_reporte(resultados, resumen_total, ruta_pdf):
    styles = getSampleStyleSheet()
    estilo_normal = styles["Normal"]
    estilo_titulo = styles["Title"]
    estilo_h2 = styles["Heading2"]
    estilo_small = ParagraphStyle("small", parent=estilo_normal, fontSize=9, leading=12)

    story = []

    # --- Portada / resumen general ---
    story.append(Paragraph("Reporte de Cartera Cripto", estilo_titulo))
    story.append(Paragraph(datetime.now().strftime("Generado el %d/%m/%Y a las %H:%M"), estilo_small))
    story.append(Spacer(1, 12))

    color_total = colors.HexColor("#16a34a") if resumen_total["ganancia_pct"] >= 0 else colors.HexColor("#dc2626")
    tabla_resumen = Table(
        [
            ["Total invertido", "Valor actual", "Ganancia / Pérdida", "% Total"],
            [
                f"${resumen_total['invertido']:.2f}",
                f"${resumen_total['valor_actual']:.2f}",
                f"${resumen_total['ganancia_usd']:.2f}",
                f"{resumen_total['ganancia_pct']:.2f}%",
            ],
        ],
        hAlign="LEFT",
        colWidths=[4 * cm, 4 * cm, 4.5 * cm, 3 * cm],
    )
    tabla_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TEXTCOLOR", (3, 1), (3, 1), color_total),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(tabla_resumen)
    story.append(Spacer(1, 16))

    # --- Gráfico comparativo de rendimiento por par (snapshot de hoy) ---
    ruta_grafico_resumen = os.path.join(CARPETA_TMP, "resumen_cartera.png")
    grafico_resumen_cartera(resultados, ruta_grafico_resumen)
    story.append(Image(ruta_grafico_resumen, width=16 * cm, height=6.8 * cm))
    story.append(Spacer(1, 10))

    # --- Gráfico de evolución histórica del % total (si ya hay corridas previas) ---
    df_historial = leer_historial()
    if df_historial is not None:
        ruta_evolucion_total = os.path.join(CARPETA_TMP, "evolucion_total.png")
        hay_evolucion = grafico_evolucion(df_historial, "TOTAL", ruta_evolucion_total,
                                           "Evolución histórica del % total de la cartera")
        if hay_evolucion:
            story.append(Image(ruta_evolucion_total, width=16 * cm, height=6.8 * cm))
        else:
            story.append(Paragraph(
                "Aún no hay suficiente historial para graficar la evolución (se necesitan al menos 2 corridas).",
                estilo_small,
            ))
    story.append(PageBreak())

    # --- Sección detallada por par ---
    for ticker_symbol, datos in resultados.items():
        estado = datos["estado"]
        smc = datos["resultado_smc"]

        story.append(Paragraph(ticker_symbol, estilo_h2))

        recuperacion_txt = (
            f"{estado['dias_recuperacion']} días (estimado)" if estado["dias_recuperacion"] is not None
            else ("N/A" if estado["en_ganancia"] else "Indeterminado")
        )

        tabla_par = Table(
            [
                ["Métrica", "Valor"],
                ["Cantidad total", f"{estado['cantidad']}"],
                ["Precio de compra promedio", f"${estado['precio_compra']:.4f}"],
                ["Precio actual", f"${estado['precio_actual']:.4f}"],
                ["Invertido", f"${estado['invertido']:.2f}"],
                ["Valor actual", f"${estado['valor_actual']:.2f}"],
                ["Ganancia / Pérdida", f"${estado['ganancia_usd']:.2f} ({estado['ganancia_pct']:.2f}%)"],
                ["Recuperación estimada", recuperacion_txt],
                ["Tendencia SMC", smc["tendencia"]],
                ["Score SMC", f"{datos['score']}"],
                ["BOS / ChoCh detectados", f"{len(smc['bos'])} / {len(smc['choch'])}"],
                ["Último Order Block", f"{datos['tipo_ob']} ({datos['zona_ob']})"],
            ],
            colWidths=[5 * cm, 10 * cm],
        )
        tabla_par.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ]))
        story.append(tabla_par)
        story.append(Spacer(1, 10))

        # --- Desglose de lotes (solo si hay más de una compra para este par) ---
        lotes = datos["posicion"]["lotes"]
        if len(lotes) > 1:
            story.append(Paragraph("Desglose de compras (lotes):", ParagraphStyle("bold_small2", parent=estilo_small, fontName="Helvetica-Bold")))
            filas_lotes = [["#", "Cantidad", "Precio de compra", "Invertido"]]
            for i, lote in enumerate(lotes, start=1):
                filas_lotes.append([
                    str(i),
                    f"{lote['cantidad']}",
                    f"${lote['precio_compra']:.4f}",
                    f"${lote['cantidad'] * lote['precio_compra']:.2f}",
                ])
            tabla_lotes = Table(filas_lotes, colWidths=[1 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm])
            tabla_lotes.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]))
            story.append(tabla_lotes)
            story.append(Spacer(1, 10))

        story.append(Paragraph("Análisis (Gemini):", ParagraphStyle("bold_small", parent=estilo_small, fontName="Helvetica-Bold")))
        story.append(Paragraph(datos["respuesta_gemini"].replace("\n", "<br/>"), estilo_small))
        story.append(PageBreak())

    # --- Informe general final (máx. 1 carilla), con comparación vs. la corrida anterior ---
    comparacion = obtener_comparacion_anterior(df_historial)
    informe_general = generar_informe_general(resultados, resumen_total, comparacion)

    story.append(Paragraph("Informe General de la Cartera", estilo_h2))
    story.append(Spacer(1, 8))

    if comparacion:
        tabla_comparacion = Table(
            [
                ["", f"Corrida anterior ({comparacion['fecha_anterior'].strftime('%d/%m/%Y')})", "Corrida actual", "Cambio"],
                [
                    "% Ganancia/Pérdida",
                    f"{comparacion['ganancia_pct_anterior']:.2f}%",
                    f"{resumen_total['ganancia_pct']:.2f}%",
                    f"{comparacion['delta_pct']:+.2f} pts",
                ],
                [
                    "Valor de cartera",
                    f"${comparacion['valor_actual_anterior']:.2f}",
                    f"${resumen_total['valor_actual']:.2f}",
                    f"${comparacion['delta_valor_usd']:+.2f}",
                ],
            ],
            colWidths=[4 * cm, 4.3 * cm, 4.3 * cm, 3.4 * cm],
        )
        tabla_comparacion.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ]))
        story.append(tabla_comparacion)
        story.append(Spacer(1, 12))
    else:
        story.append(Paragraph(
            "Esta es la primera corrida registrada; a partir de la próxima ejecución este informe incluirá "
            "la comparación semana a semana.",
            estilo_small,
        ))
        story.append(Spacer(1, 12))

    story.append(Paragraph(informe_general.replace("\n", "<br/>"), estilo_normal))

    doc = SimpleDocTemplate(ruta_pdf, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    doc.build(story)


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================
def main():
    resultados = {}
    for ticker_symbol, lotes in CARTERA.items():
        analisis = analizar_par(ticker_symbol, lotes)
        if analisis:
            resultados[ticker_symbol] = analisis

    if not resultados:
        print("❌ No se pudo analizar ningún par. Abortando.")
        return

    invertido_total = sum(r["estado"]["invertido"] for r in resultados.values())
    valor_actual_total = sum(r["estado"]["valor_actual"] for r in resultados.values())
    ganancia_usd_total = valor_actual_total - invertido_total
    ganancia_pct_total = (ganancia_usd_total / invertido_total * 100) if invertido_total else 0

    resumen_total = {
        "invertido": invertido_total,
        "valor_actual": valor_actual_total,
        "ganancia_usd": ganancia_usd_total,
        "ganancia_pct": ganancia_pct_total,
    }

    guardar_historial(resultados, resumen_total)

    ruta_pdf = os.path.join(CARPETA_TMP, "reporte_cartera.pdf")
    generar_pdf_reporte(resultados, resumen_total, ruta_pdf)

    estado_txt = "en ganancia 📈" if ganancia_pct_total >= 0 else "en pérdida 📉"
    mensaje_corto = (
        f"🤖 Análisis de cartera completado.\n"
        f"Total: {ganancia_pct_total:+.2f}% ({estado_txt})\n"
        f"Invertido: ${invertido_total:.2f} | Valor actual: ${valor_actual_total:.2f}\n"
        f"📎 Detalle completo (tablas + gráficos) en el PDF adjunto."
    )

    enviar_mensaje(TOKEN, CHAT_ID, mensaje_corto)
    enviar_documento(TOKEN, CHAT_ID, ruta_pdf, caption="Reporte detallado de cartera")


if __name__ == "__main__":
    main()