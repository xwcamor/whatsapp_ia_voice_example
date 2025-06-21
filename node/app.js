// app.js - WhatsApp + Baileys + GTTS avanzado

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { makeWASocket, useMultiFileAuthState, DisconnectReason } from "@whiskeysockets/baileys";
import qrcode from "qrcode-terminal";
import { default as GTTS } from "gtts";

// === RUTAS ===
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// === ESTADOS POR USUARIO ===
const estadosTransformar = new Map(); // { jid: true }
const idiomasUsuario = new Map();     // { jid: "es" }

const startSock = async () => {
  const { state, saveCreds } = await useMultiFileAuthState("auth");
  const sock = makeWASocket({ auth: state });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) qrcode.generate(qr, { small: true });
    if (connection === "open") console.log("✅ Conectado a WhatsApp");
    if (connection === "close") {
      const shouldReconnect = (lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut);
      console.log("⚠️ Desconectado. ¿Reconectar?", shouldReconnect);
      if (shouldReconnect) startSock();
    }
  });

  sock.ev.on("messages.upsert", async ({ messages }) => {
    const msg = messages[0];
    if (!msg.message || msg.key.fromMe) return;

    const from = msg.key.remoteJid;
    const texto = msg.message.conversation || msg.message?.extendedTextMessage?.text || "";

    // Paso 1: Comando inicial
    if (texto.trim().toLowerCase() === "/transformar") {
      estadosTransformar.set(from, "esperando_idioma");
      await sock.sendMessage(from, {
        text: "🌐 Escribe el idioma en el que deseas el audio:\n\n- es (Español)\n- en (Inglés)\n- fr (Francés)\n- pt (Portugués)\n- it (Italiano)\n- de (Alemán)\n\nEjemplo: `es`"
      });
      return;
    }

    // Paso 2: Espera idioma
    if (estadosTransformar.get(from) === "esperando_idioma") {
      const idioma = texto.trim().toLowerCase();
      if (!["es", "en", "fr", "pt", "it", "de"].includes(idioma)) {
        await sock.sendMessage(from, { text: "❌ Idioma no válido. Usa: es, en, fr, pt, it o de." });
        return;
      }
      idiomasUsuario.set(from, idioma);
      estadosTransformar.set(from, "esperando_texto");
      await sock.sendMessage(from, { text: "✍️ Ahora escribe el texto que deseas convertir en audio." });
      return;
    }

    // Paso 3: Convertir texto a audio
    if (estadosTransformar.get(from) === "esperando_texto") {
      const textoParaAudio = texto.trim();
      const idioma = idiomasUsuario.get(from) || "es";
      const rutaAudio = path.join(__dirname, `audio_${Date.now()}.mp3`);

      try {
        const gtts = new GTTS(textoParaAudio, idioma);
        await new Promise((res, rej) => gtts.save(rutaAudio, err => err ? rej(err) : res()));

        const audio = fs.readFileSync(rutaAudio);
        await sock.sendMessage(from, {
          audio: audio,
          mimetype: 'audio/mpeg',
          ptt: true
        });
      } catch (err) {
        console.error("❌ Error al generar audio:", err.message);
        await sock.sendMessage(from, { text: "❌ Ocurrió un error al generar el audio." });
      } finally {
        if (fs.existsSync(rutaAudio)) fs.unlinkSync(rutaAudio);
        estadosTransformar.delete(from);
        idiomasUsuario.delete(from);
      }
      return;
    }
  });
};

startSock();
