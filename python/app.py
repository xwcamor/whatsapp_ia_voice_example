from flask import Flask, request, jsonify
from flask_cors import CORS
import pytesseract
from PIL import Image
import mysql.connector
import os
import uuid
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1234",
    "database": "examen"
}

@app.route("/ocr", methods=["POST"])
def ocr():
    if "file" not in request.files:
        return jsonify({"error": "Archivo no encontrado"}), 400

    file = request.files["file"]
    filename = f"temp_{uuid.uuid4().hex}.png"
    file.save(filename)

    text = pytesseract.image_to_string(Image.open(filename), lang="spa")
    os.remove(filename)

    # Guardar texto OCR en archivo para depuración con ruta absoluta
    debug_path = os.path.join(os.getcwd(), "debug_ocr.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(text)

    print("🧾 Texto extraído por OCR:")
    print(text)
    print("✅ debug_ocr.txt guardado en:", debug_path)

    if not text.strip():
        return jsonify({"error": "No se pudo leer el texto con OCR"}), 400

    cliente = None
    totales_detectados = []
    tipo = "Soles"

    # Buscar línea de cliente
    for line in text.splitlines():
        line_lower = line.lower()

        if not cliente:
            if "cliente" in line_lower:
                cliente = line.split(":")[-1].strip()
            elif line.isupper() and len(line.split()) >= 2:
                cliente = line.strip()

    # Buscar montos como 1,200.00, S/ 40.00, 40,00, etc.
    matches = re.findall(r"(S\/\s*)?((?:\d{1,3}[.,]?)+(?:\d{2}))", text)
    totales_detectados = [m[1].replace(",", ".") for m in matches]
    print("🧪 Candidatos a monto detectados:", totales_detectados)

    # Convertir y filtrar valores válidos mayores a 1.00
    valores = [float(m.replace(",", ".")) for m in totales_detectados if float(m.replace(",", ".")) >= 1.00]
    total = valores[-1] if valores else None

    return jsonify({
        "cliente": cliente,
        "total": total,
        "tipo": tipo,
        "posibles_totales": totales_detectados
    })

@app.route("/guardar", methods=["POST"])
def guardar():
    data = request.get_json()
    cliente = data.get("cliente")
    total = data.get("total")
    tipo = data.get("tipo")

    if not cliente or not total:
        return jsonify({"error": "Datos incompletos"}), 400

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO facturas (cliente, total, tipo, fecha) VALUES (%s, %s, %s, NOW())", (cliente, total, tipo))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"mensaje": "Guardado exitosamente"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/responder', methods=['POST'])
def responder():
    data = request.get_json()
    mensaje = data.get('mensaje', '').strip().lower()
    remitente = data.get('remitente', '')

    print(f"📩 Mensaje recibido desde {remitente}: {mensaje}")

    if mensaje in ['hola', 'buenos días', 'buenas']:
        respuesta = "👋 ¡Hola! ¿En qué puedo ayudarte?"
    elif mensaje == 'gracias':
        respuesta = "🙏 ¡De nada!"
    else:
        respuesta = "🤖 Soy un bot. Usa los comandos: #codigo, /escanear o escribe 'hola'."

    return jsonify({"respuesta": respuesta})

if __name__ == "__main__":
    app.run(port=5000)






