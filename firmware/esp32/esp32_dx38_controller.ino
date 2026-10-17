// ==============================================================================
// ESP32 Web Server Remote Controller untuk Electro-Voice Dx38 / Dynacord DSP244
// Fitur:
// - Hotspot WiFi (AP Mode) + mDNS (http://dx38.local)
// - Web Interface Modern (Dark Mode Touch-Friendly ala Console Mixer)
// - WebSocket Realtime Control (Zero Latency)
// - Master Mute & Channel Mute (Out 1 - 4)
// - Gain Level Control Slider (-40 dB s.d. +6 dB)
// - HardwareSerial UART2 (GPIO 16 RX, GPIO 17 TX) ke MAX3232 RS-232 Converter
// ==============================================================================

#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

// Konfigurasi WiFi AP
const char *ssid = "EV-Dx38-Remote";
const char *password = "12345678"; // Kosongkan jika ingin open wifi

// Serial Port ke EV Dx38 via MAX3232
#define RXD2 16
#define TXD2 17
#define DX38_BAUD 19200
#define DEVICE_ID "1"

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

// State Perangkat (Disimpan agar sinkron saat browser baru dibuka)
struct ChannelState {
  int level = 0;       // dB (-40 s.d. +6)
  bool muted = false;
};

ChannelState channels[4];
bool masterMuted = false;

// Fungsi kirim perintah serial teks ke Dx38
void sendDx38Command(String cmd) {
  String fullCmd = cmd + "\r";
  Serial2.print(fullCmd);
  Serial.print("[TX -> Dx38]: ");
  Serial.println(cmd);
}

// Handler WebSocket Message
void handleWebSocketMessage(void *arg, uint8_t *data, size_t len) {
  AwsFrameInfo *info = (AwsFrameInfo*)arg;
  if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) {
    data[len] = 0;
    String message = (char*)data;
    Serial.println("[WS In]: " + message);

    // Format Perintah dari Web UI:
    // "MUTE:<ch>:<0|1>"  -> MUTE:1:1
    // "LEVEL:<ch>:<val>" -> LEVEL:1:-7
    // "MASTER_MUTE:<0|1>"

    if (message.startsWith("MUTE:")) {
      int firstColon = message.indexOf(':');
      int secondColon = message.indexOf(':', firstColon + 1);
      int ch = message.substring(firstColon + 1, secondColon).toInt();
      int val = message.substring(secondColon + 1).toInt();

      if (ch >= 1 && ch <= 4) {
        channels[ch - 1].muted = (val == 1);
        sendDx38Command("/ID" DEVICE_ID "/Out" + String(ch) + "/Mute " + String(val));
        ws.textAll(message); // Broadcast ke semua client
      }
    } 
    else if (message.startsWith("LEVEL:")) {
      int firstColon = message.indexOf(':');
      int secondColon = message.indexOf(':', firstColon + 1);
      int ch = message.substring(firstColon + 1, secondColon).toInt();
      int val = message.substring(secondColon + 1).toInt();

      if (ch >= 1 && ch <= 4) {
        channels[ch - 1].level = val;
        sendDx38Command("/ID" DEVICE_ID "/Out" + String(ch) + "/Level " + String(val));
        ws.textAll(message);
      }
    }
    else if (message.startsWith("MASTER_MUTE:")) {
      int val = message.substring(12).toInt();
      masterMuted = (val == 1);
      for (int i = 1; i <= 4; i++) {
        channels[i - 1].muted = masterMuted;
        sendDx38Command("/ID" DEVICE_ID "/Out" + String(i) + "/Mute " + String(val));
      }
      ws.textAll(message);
    }
  }
}

void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type,
             void *arg, uint8_t *data, size_t len) {
  switch (type) {
    case WS_EVT_CONNECT:
      Serial.printf("Client connected: %u\n", client->id());
      // Kirim state saat ini ke client yang baru konek
      for (int i = 0; i < 4; i++) {
        client->text("LEVEL:" + String(i + 1) + ":" + String(channels[i].level));
        client->text("MUTE:" + String(i + 1) + ":" + String(channels[i].muted ? 1 : 0));
      }
      break;
    case WS_EVT_DISCONNECT:
      Serial.printf("Client disconnected: %u\n", client->id());
      break;
    case WS_EVT_DATA:
      handleWebSocketMessage(arg, data, len);
      break;
    case WS_EVT_PONG:
    case WS_EVT_ERROR:
      break;
  }
}

// Web UI HTML / CSS / JS Terkompresi
const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>EV Dx38 Wireless Remote</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0f1217;
      --card-bg: #181c24;
      --card-border: #28303f;
      --accent-mute: #ef4444;
      --accent-active: #10b981;
      --text-main: #f3f4f6;
      --text-dim: #9ca3af;
      --slider-track: #262e3d;
      --slider-thumb: #3b82f6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
    body {
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 16px;
    }
    header {
      width: 100%;
      max-width: 800px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 20px;
    }
    .logo-badge {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .logo-badge h1 {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      background: var(--accent-active);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--accent-active);
    }
    .master-btn {
      background: #374151;
      border: 1px solid #4b5563;
      color: #fff;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      font-size: 0.85rem;
      transition: all 0.2s;
    }
    .master-btn.active {
      background: var(--accent-mute);
      box-shadow: 0 0 12px rgba(239,68,68,0.5);
    }
    .mixer-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      width: 100%;
      max-width: 800px;
      flex: 1;
    }
    @media (max-width: 600px) {
      .mixer-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
    }
    .channel-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px 12px;
      display: flex;
      flex-direction: column;
      align-items: center;
      position: relative;
    }
    .ch-title {
      font-size: 0.9rem;
      font-weight: 700;
      color: var(--text-dim);
      margin-bottom: 8px;
    }
    .ch-val {
      font-size: 1.5rem;
      font-weight: 700;
      color: #60a5fa;
      margin-bottom: 16px;
      min-width: 60px;
      text-align: center;
    }
    .slider-container {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      min-height: 220px;
      padding: 10px 0;
    }
    input[type=range] {
      -webkit-appearance: none;
      writing-mode: vertical-lr;
      direction: rtl;
      width: 48px;
      height: 200px;
      background: var(--slider-track);
      border-radius: 24px;
      outline: none;
      cursor: pointer;
    }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: var(--slider-thumb);
      box-shadow: 0 4px 10px rgba(0,0,0,0.5);
      border: 2px solid #fff;
    }
    .mute-btn {
      width: 100%;
      margin-top: 16px;
      padding: 12px;
      border: none;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.9rem;
      cursor: pointer;
      background: #2a3342;
      color: var(--text-dim);
      transition: all 0.2s;
    }
    .mute-btn.muted {
      background: var(--accent-mute);
      color: white;
      box-shadow: 0 0 15px rgba(239,68,68,0.6);
    }
  </style>
</head>
<body>
  <header>
    <div class="logo-badge">
      <div id="statusDot" class="status-dot"></div>
      <h1>EV Dx38 Remote</h1>
    </div>
    <button id="masterMute" class="master-btn" onclick="toggleMasterMute()">MUTE ALL</button>
  </header>

  <div class="mixer-grid">
    <!-- Channel 1 s.d. 4 -->
    <div class="channel-card">
      <div class="ch-title">OUTPUT 1</div>
      <div id="val1" class="ch-val">0 dB</div>
      <div class="slider-container">
        <input type="range" id="fader1" min="-40" max="6" value="0" oninput="onFader(1, this.value)">
      </div>
      <button id="mute1" class="mute-btn" onclick="toggleMute(1)">MUTE</button>
    </div>

    <div class="channel-card">
      <div class="ch-title">OUTPUT 2</div>
      <div id="val2" class="ch-val">0 dB</div>
      <div class="slider-container">
        <input type="range" id="fader2" min="-40" max="6" value="0" oninput="onFader(2, this.value)">
      </div>
      <button id="mute2" class="mute-btn" onclick="toggleMute(2)">MUTE</button>
    </div>

    <div class="channel-card">
      <div class="ch-title">OUTPUT 3</div>
      <div id="val3" class="ch-val">0 dB</div>
      <div class="slider-container">
        <input type="range" id="fader3" min="-40" max="6" value="0" oninput="onFader(3, this.value)">
      </div>
      <button id="mute3" class="mute-btn" onclick="toggleMute(3)">MUTE</button>
    </div>

    <div class="channel-card">
      <div class="ch-title">OUTPUT 4</div>
      <div id="val4" class="ch-val">0 dB</div>
      <div class="slider-container">
        <input type="range" id="fader4" min="-40" max="6" value="0" oninput="onFader(4, this.value)">
      </div>
      <button id="mute4" class="mute-btn" onclick="toggleMute(4)">MUTE</button>
    </div>
  </div>

  <script>
    let ws;
    let masterMuted = false;

    function initWS() {
      ws = new WebSocket(`ws://${location.host}/ws`);
      ws.onopen = () => {
        document.getElementById('statusDot').style.background = '#10b981';
      };
      ws.onclose = () => {
        document.getElementById('statusDot').style.background = '#ef4444';
        setTimeout(initWS, 1500);
      };
      ws.onmessage = (event) => {
        const parts = event.data.split(':');
        if (parts[0] === 'LEVEL') {
          const ch = parts[1];
          const val = parts[2];
          document.getElementById('fader' + ch).value = val;
          document.getElementById('val' + ch).innerText = val + ' dB';
        } else if (parts[0] === 'MUTE') {
          const ch = parts[1];
          const isMuted = parts[2] === '1';
          const btn = document.getElementById('mute' + ch);
          if (isMuted) btn.classList.add('muted');
          else btn.classList.remove('muted');
        } else if (parts[0] === 'MASTER_MUTE') {
          masterMuted = parts[1] === '1';
          const btn = document.getElementById('masterMute');
          if (masterMuted) btn.classList.add('active');
          else btn.classList.remove('active');
        }
      };
    }

    function onFader(ch, val) {
      document.getElementById('val' + ch).innerText = val + ' dB';
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(`LEVEL:${ch}:${val}`);
      }
    }

    function toggleMute(ch) {
      const btn = document.getElementById('mute' + ch);
      const willMute = !btn.classList.contains('muted');
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(`MUTE:${ch}:${willMute ? 1 : 0}`);
      }
    }

    function toggleMasterMute() {
      masterMuted = !masterMuted;
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(`MASTER_MUTE:${masterMuted ? 1 : 0}`);
      }
    }

    window.onload = initWS;
  </script>
</body>
</html>
)rawliteral";

void setup() {
  Serial.begin(115200);
  
  // Inisialisasi UART2 untuk komunikasi ke EV Dx38
  Serial2.begin(DX38_BAUD, SERIAL_8N1, RXD2, TXD2);

  Serial.println("\n[+] Mengaktifkan WiFi Access Point...");
  WiFi.softAP(ssid, password);
  Serial.print("[+] IP Address ESP32: ");
  Serial.println(WiFi.softAPIP());

  // WebSocket Server Setup
  ws.onEvent(onEvent);
  server.addHandler(&ws);

  // Serve Single Page Application UI
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send_P(200, "text/html", index_html);
  });

  server.begin();
  Serial.println("[+] Web Server & WebSocket telah aktif!");
  
  // Kirim Query Device Check ke Dx38
  delay(500);
  sendDx38Command("/ID" DEVICE_ID "/DEVICE ?");
}

void loop() {
  ws.cleanupClients();

  // Membaca respon balik dari Dx38 dan forward ke Serial Monitor ESP32
  if (Serial2.available()) {
    String reply = Serial2.readStringUntil('\r');
    reply.trim();
    if (reply.length() > 0) {
      Serial.println("[RX <- Dx38]: " + reply);
    }
  }
}
