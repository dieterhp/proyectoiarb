import os, csv, json, time, re  # importa modulos estandar para archivos, csv, json, tiempo y regex
import requests  # importa cliente HTTP para llamar a Document Intelligence, Language y Speech
from flask import Flask, request, jsonify, render_template  # importa lo necesario de Flask
from openai import OpenAI  # importa el cliente compatible con la API v1 de Azure OpenAI

app = Flask(__name__)  # crea la aplicacion web
KEY = os.environ["AI_KEY"]  # lee la clave del recurso de IA desde variable de entorno
OPENAI_BASE = os.environ["OPENAI_BASE"]  # lee la URL base de Foundry (termina en /openai/v1/)
MODEL = os.environ.get("MODEL", "gpt-4.1-mini-1")  # lee el nombre del despliegue del modelo
COG = os.environ["COG_ENDPOINT"].rstrip("/")  # lee el endpoint cognitiveservices del mismo recurso
SPEECH_REGION = os.environ.get("SPEECH_REGION", "westus3")  # lee la region del servicio de voz
client = OpenAI(base_url=OPENAI_BASE, api_key=KEY)  # crea el cliente del modelo con la clave
D = os.path.join(os.path.dirname(__file__), "data")  # ruta de la carpeta de datos

def leer(nombre):  # funcion que carga un csv como lista de diccionarios
    with open(os.path.join(D, nombre), encoding="utf-8") as f:  # abre el archivo
        return list(csv.DictReader(f))  # devuelve las filas

CATALOGO = {r["sku"]: r["nombre"] for r in leer("catalogo_unificado.csv")}  # mapa sku -> nombre
INVENTARIO = "\n".join(f'{CATALOGO[r["sku"]]} | {r["sucursal"]} | {r["existencia"]} piezas' for r in leer("inventario_unificado.csv"))  # texto de existencias
PRECIOS = "\n".join(f'{r["nombre"]} | ${r["precio_lista_mxn"]} MXN' for r in leer("catalogo_unificado.csv"))  # texto de precios
QUEJAS = leer("quejas.csv")  # carga las quejas
QUEJAS_TXT = "\n".join(f'{q["id"]} | {q["fecha"]} | {q["cliente"]} | {q["sucursal"]} | {q["mensaje"]}' for q in QUEJAS)  # texto de quejas
POLITICA = open(os.path.join(D, "politicas", "politica_devoluciones_vigente.md"), encoding="utf-8").read()  # politica vigente

SISTEMA = f"""Eres el asistente de IA de Distribuidora Rio Claro. Responde en espanol, breve y claro.
Reglas: usa SOLO la informacion de abajo; si no esta, di que no lo sabes y sugiere hablar con una persona.
Trata igual a clientes de todas las sucursales. No reveles nominas ni costos internos.
Al final de cada respuesta escribe 'Fuente:' con el documento usado (inventario_unificado.csv, catalogo_unificado.csv, quejas.csv o politica_devoluciones_vigente.md).
Si la respuesta no usa ningun documento (saludos, preguntas generales), no escribas 'Fuente:'.
Eres una IA; las decisiones de dinero las aprueba una persona.
## INVENTARIO (producto | sucursal | existencia)
{INVENTARIO}
## PRECIOS DE LISTA
{PRECIOS}
## QUEJAS REGISTRADAS
{QUEJAS_TXT}
## POLITICA DE DEVOLUCIONES VIGENTE
{POLITICA}"""  # instruccion de sistema con todo el contexto

@app.route("/")  # ruta de la pagina principal
def index():  # funcion de la pagina principal
    return render_template("index.html")  # devuelve la plantilla

@app.route("/api/chat", methods=["POST"])  # ruta del chat
def chat():  # funcion del chat
    historial = request.json.get("mensajes", [])[-10:]  # toma los ultimos 10 mensajes
    r = client.chat.completions.create(model=MODEL, max_tokens=500, messages=[{"role": "system", "content": SISTEMA}] + historial)  # llama al modelo
    return jsonify({"respuesta": r.choices[0].message.content})  # devuelve la respuesta

@app.route("/api/speech-token")  # ruta que entrega token temporal de voz
def speech_token():  # funcion del token
    r = requests.post(f"https://{SPEECH_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken", headers={"Ocp-Apim-Subscription-Key": KEY}, timeout=15)  # pide el token
    return jsonify({"token": r.text, "region": SPEECH_REGION})  # devuelve token y region

FACT_FILE = "/tmp/facturas.json"  # archivo donde se guardan las facturas procesadas
def cargar():  # funcion que lee las facturas guardadas
    return json.load(open(FACT_FILE)) if os.path.exists(FACT_FILE) else []  # lee o devuelve lista vacia
def guardar(l):  # funcion que escribe las facturas
    json.dump(l, open(FACT_FILE, "w"))  # escribe el json

def norm(s):  # funcion que normaliza texto para comparar
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())  # deja solo letras y numeros en minuscula

@app.route("/api/factura", methods=["POST"])  # ruta que procesa una factura
def factura():  # funcion de facturas
    datos = request.files["archivo"].read()  # lee el archivo subido
    url = f"{COG}/documentintelligence/documentModels/prebuilt-invoice:analyze?api-version=2024-11-30"  # URL del modelo de facturas
    r = requests.post(url, headers={"Ocp-Apim-Subscription-Key": KEY, "Content-Type": "application/octet-stream"}, data=datos, timeout=60)  # envia el archivo
    if r.status_code != 202:  # si no fue aceptado
        return jsonify({"error": r.text}), 500  # devuelve el error
    op = r.headers["Operation-Location"]  # URL para consultar el resultado
    for _ in range(30):  # espera hasta 30 intentos
        time.sleep(2)  # pausa 2 segundos
        res = requests.get(op, headers={"Ocp-Apim-Subscription-Key": KEY}, timeout=30).json()  # consulta el estado
        if res.get("status") in ("succeeded", "failed"):  # si termino
            break  # sale del ciclo
    docs = res.get("analyzeResult", {}).get("documents", [])  # lista de documentos detectados
    campos = docs[0]["fields"] if docs else {}  # campos del primer documento
    def val(n):  # funcion que obtiene texto y confianza de un campo
        c = campos.get(n, {})  # busca el campo
        return (c.get("valueString") or c.get("content"), c.get("confidence", 0))  # devuelve valor y confianza
    prov, cp = val("VendorName")  # proveedor
    folio, cf = val("InvoiceId")  # folio
    fecha, cd = val("InvoiceDate")  # fecha
    tc = campos.get("InvoiceTotal", {})  # campo del total
    total = (tc.get("valueCurrency") or {}).get("amount")  # monto del total
    ct = tc.get("confidence", 0)  # confianza del total
    UMBRAL = float(os.environ.get("UMBRAL", "0.7"))  # lee el umbral de confianza desde una variable de entorno
    confianza = min(cp, cf, ct) if docs else 0  # confianza minima solo de proveedor, folio y total
    estado, motivo = "Pendiente de aprobacion", ""  # estado inicial
    if not docs or total is None or not folio or confianza < UMBRAL:  # si faltan datos o hay poca confianza
        estado, motivo = "REVISION HUMANA", "Confianza baja o datos faltantes: no se inventa el total."  # marca revision
    previas = cargar()  # lee facturas anteriores
    if any(norm(p["proveedor"]) == norm(prov) and norm(p["folio"]) == norm(folio) and p["total"] == total for p in previas if prov and folio):  # compara proveedor, folio y total
        estado, motivo = "DUPLICADA", "Mismo proveedor, folio y total que una factura ya registrada."  # marca duplicada
    reg = {"archivo": request.files["archivo"].filename, "proveedor": prov, "folio": folio, "fecha": fecha, "total": total, "confianza": round(confianza, 2), "confianzas": {"proveedor": round(cp, 2), "folio": round(cf, 2), "fecha": round(cd, 2), "total": round(ct, 2)}, "estado": estado, "motivo": motivo}  # arma el registro
    if estado != "DUPLICADA":  # las duplicadas no se guardan
        previas.append(reg)  # agrega a la lista
        guardar(previas)  # guarda la lista
    return jsonify(reg)  # devuelve el resultado

@app.route("/api/facturas")  # ruta que lista facturas
def lista_facturas():  # funcion de listado
    return jsonify(cargar())  # devuelve la lista

@app.route("/api/aprobar", methods=["POST"])  # ruta de aprobacion humana
def aprobar():  # funcion de aprobacion
    folio = request.json["folio"]  # folio a aprobar
    l = cargar()  # lee facturas
    for f in l:  # recorre
        if f["folio"] == folio:  # si coincide
            f["estado"] = "APROBADA por " + request.json.get("persona", "revisor")  # registra quien aprobo
    guardar(l)  # guarda cambios
    return jsonify(l)  # devuelve lista

@app.route("/api/quejas")  # ruta de quejas con sentimiento
def quejas():  # funcion de quejas
    docs = [{"id": q["id"], "language": "es", "text": q["mensaje"]} for q in QUEJAS]  # arma documentos para Language
    r = requests.post(f"{COG}/language/:analyze-text?api-version=2023-04-01", headers={"Ocp-Apim-Subscription-Key": KEY}, json={"kind": "SentimentAnalysis", "analysisInput": {"documents": docs}}, timeout=60)  # llama al servicio
    if r.status_code != 200:  # si el servicio no respondio con exito
        return jsonify({"error": r.status_code, "detalle": r.text}), 500  # devuelve el codigo y el texto del error
    sent = {d["id"]: d["sentiment"] for d in r.json().get("results", {}).get("documents", [])}  # mapa id -> sentimiento
    salida = [{**q, "sentimiento": sent.get(q["id"], "n/d")} for q in QUEJAS]  # une quejas con sentimiento
    return jsonify(salida)  # devuelve resultado
