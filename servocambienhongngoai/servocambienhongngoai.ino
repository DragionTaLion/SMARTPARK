/*
 * ============================================================
 *  SmartPark ESP8266 – Firmware v3.1
 *  Giao tiếp 2 chiều với FastAPI Server
 * ============================================================
 *  Luồng hoạt động:
 *    1. ESP kết nối WiFi (SSID hotspot từ máy tính chạy server)
 *    2. Mỗi 1.5 giây → POST /api/hardware/status gửi:
 *         {"sensors":[IR_vao,IR_ra,S1,S2,S3], "gate_trigger": 1|2|0, "ip":"..."}
 *    3. Server phân tích ảnh (ESP32-CAM), tra DB → trả về:
 *         {"status":"ok", "open_gate": 1, "cmd": "open"}
 *    4. ESP nhận response → gọi executeOpenGate(gateId) → quay servo
 *    5. Mỗi 5 giây → GET /api/esp/heartbeat (giữ kết nối alive)
 * ============================================================
 *  CÁCH CẤU HÌNH:
 *    - ssid/password: Tên và mật khẩu WiFi (hotspot từ máy tính)
 *    - serverIP:      IP máy tính trong mạng WiFi (kiểm tra bằng ipconfig)
 *                     Thường là 192.168.137.1 nếu dùng Mobile Hotspot Windows
 *    - serverPort:    8000 (mặc định FastAPI)
 * ============================================================
 */

/*
 * ============================================================
 * SmartPark ESP8266 – Firmware v3.2 (Thêm Báo Cháy Khẩn Cấp)
 * Giao tiếp 2 chiều với FastAPI Server
 * ============================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ─── LCD I2C (địa chỉ 0x27) ─────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ─── Servo ───────────────────────────────────────────────────
Servo servoIn;
Servo servoOut;

// ─── CẤU HÌNH CHÂN ───────────────────────────────────────────
const int irInPin   = 3;   // RX  – Cảm biến cổng VÀO (rút khi nạp code)
const int irOutPin  = 13;  // D7  – Cảm biến cổng RA
const int irSlot1   = 0;   // D3  – Ô đỗ 1
const int irSlot2   = 2;   // D4  – Ô đỗ 2
const int irSlot3   = 16;  // D0  – Ô đỗ 3
const int buzzerPin = 15;  // D8  – Còi
const int servoInPin  = 12; // D6  – Servo cổng vào
const int servoOutPin = 14; // D5  – Servo cổng ra

// [ĐÃ COMMENT] Khai báo chân cảm biến cháy
 const int fireSensorPin = A0;  // A0 - Cảm biến báo cháy (Analog)

// ─── CẤU HÌNH WIFI & SERVER ───────────────────────────────────
const char* ssid     = "LAPTOP-71LM2GV2 7594"; 
const char* password = "12345678";                 
const char* serverIP = "192.168.137.1";            
const int   serverPort = 8000;                     

// ─── TIMING ───────────────────────────────────────────────────
const unsigned long STATUS_INTERVAL    = 1500;  // ms – Gửi cảm biến lên server
const unsigned long HEARTBEAT_INTERVAL = 5000;  // ms – Gửi heartbeat
const unsigned long GATE_OPEN_MS       = 3000;  // ms – Giữ cổng mở
const unsigned long LCD_REFRESH_MS     = 1000;  // ms – Cập nhật LCD
const unsigned long WIFI_CHECK_MS      = 15000; // ms – Kiểm tra WiFi tự động

// ─── TRẠNG THÁI ───────────────────────────────────────────────
int  availableSlots  = 3;
bool isGateActive    = false;
bool irInTriggered   = false;
bool irOutTriggered  = false;

// [ĐĐ COMMENT] Biến lưu trạng thái cháy
 bool isFireDetected  = false; 

unsigned long lastStatusTime    = 0;
unsigned long lastHeartbeatTime = 0;
unsigned long lastLcdTime       = 0;
unsigned long lastWifiCheck     = 0;

WiFiClient wifiClient;

float sinVal;
int toneVal;

// ═══════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200, SERIAL_8N1, SERIAL_TX_ONLY);
  Serial.println("\n=== SmartPark ===");

  // Khởi tạo chân
  pinMode(irInPin,   INPUT);
  pinMode(irOutPin,  INPUT);
  pinMode(irSlot1,   INPUT);
  pinMode(irSlot2,   INPUT);
  pinMode(irSlot3,   INPUT);
  pinMode(buzzerPin, OUTPUT);
  digitalWrite(buzzerPin, LOW);

  // [ĐÃ COMMENT] Khởi tạo chân cảm biến cháy
   pinMode(fireSensorPin, INPUT);

  // Servo về vị trí đóng (0°)
  servoIn.attach(servoInPin);
  servoOut.attach(servoOutPin);
  servoIn.write(0);
  servoOut.write(0);

  // LCD khởi động
  Wire.begin(4, 5); // SDA=D2(GPIO4), SCL=D1(GPIO5)
  lcd.init();
  lcd.backlight();
  lcdPrint("SmartPark ", "Dang ket noi...");

  // Kết nối WiFi
  connectWiFi();

  beep1(2);
  delay(1000);
  lcd.clear();
}

// ═══════════════════════════════════════════════════════════════
void connectWiFi() {
  Serial.printf("[WiFi] Ket noi toi: %s\n", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Ket noi OK – IP ESP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[WiFi] Server: http://%s:%d\n", serverIP, serverPort);
    lcdPrint("WiFi OK!", WiFi.localIP().toString().c_str());
  } else {
    Serial.printf("\n[WiFi] THAT BAI! Status: %d\n", WiFi.status());
    lcdPrint("WiFi THAT BAI!", String("Code:") + String(WiFi.status()));
  }
}

// ═══════════════════════════════════════════════════════════════
void loop() {
  unsigned long now = millis();

  // ── Tự động kết nối lại WiFi nếu mất ─────────────────────
  if (now - lastWifiCheck >= WIFI_CHECK_MS) {
    lastWifiCheck = now;
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WiFi] Mat ket noi, dang thu lai...");
      WiFi.reconnect();
    }
  }

  // [ĐÃ COMMENT] ── Kiểm tra cảm biến báo cháy liên tục ─────────
  
  int fireVal = analogRead(fireSensorPin);
  isFireDetected = (fireVal < 500); // Áp tụt xuống dưới 500 là có lửa
  
  // ── 1. Đọc cảm biến cổng (chỉ khi cổng không đang hoạt động) ──
  if (!isGateActive) {
    irInTriggered  = (digitalRead(irInPin)  == LOW);
    irOutTriggered = (digitalRead(irOutPin) == LOW);
  }

  // ── 2. Gửi trạng thái lên server, nhận lệnh mở cổng ────────
  if (now - lastStatusTime >= STATUS_INTERVAL) {
    lastStatusTime = now;
    sendStatusToServer();
  }

  // ── 3. Gửi heartbeat ─────────────────────────────────────────
  if (now - lastHeartbeatTime >= HEARTBEAT_INTERVAL) {
    lastHeartbeatTime = now;
    sendHeartbeat();
  }

  // ── 4. Cập nhật LCD ──────────────────────────────────────────
  if (!isGateActive && now - lastLcdTime >= LCD_REFRESH_MS) {
    lastLcdTime = now;
    updateLCD();
  }

  yield(); // Cho phép ESP8266 xử lý WiFi stack
}

// ═══════════════════════════════════════════════════════════════
// POST /api/hardware/status — Gửi cảm biến, nhận lệnh mở cổng
// ═══════════════════════════════════════════════════════════════
void sendStatusToServer() {
  if (WiFi.status() != WL_CONNECTED) return;

  // Đọc tất cả cảm biến ô đỗ
  int s1 = digitalRead(irSlot1);
  int s2 = digitalRead(irSlot2);
  int s3 = digitalRead(irSlot3);
  availableSlots = (s1 == HIGH) + (s2 == HIGH) + (s3 == HIGH);

  // Xác định trigger: cổng nào đang có xe → server chụp ảnh nhận diện
  int trigger = 0;
  if (!isGateActive) {
    if (irInTriggered)       trigger = 1;  // Cổng vào
    else if (irOutTriggered) trigger = 2;  // Cổng ra
  }

  // Build JSON body
  String body = "{";
  body += "\"sensors\":[";
  body += String(irInTriggered ? 1 : 0) + ",";
  body += String(irOutTriggered ? 1 : 0) + ",";
  body += String(s1 == LOW ? 1 : 0) + ",";
  body += String(s2 == LOW ? 1 : 0) + ",";
  body += String(s3 == LOW ? 1 : 0);
  
  // -- BUILD JSON KHI BẬT BÁO CHÁY --
  body += "],";
  body += "\"gate_trigger\":" + String(trigger) + ",";
  body += "\"fire_alarm\":" + String(isFireDetected ? 1 : 0) + ","; 
  body += "\"ip\":\"" + WiFi.localIP().toString() + "\"";
  body += "}";
  

  HTTPClient http;
  String url = "http://" + String(serverIP) + ":" + String(serverPort) + "/api/hardware/status";
  http.begin(wifiClient, url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(2500);

  int httpCode = http.POST(body);

  if (httpCode == 200) {
    String response = http.getString();

    // Parse JSON response để lấy lệnh từ server
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, response);
    if (!err) {
      int openGate    = doc["open_gate"] | 0;
      const char* cmd = doc["cmd"]       | "none";

      Serial.printf("[SERVER] open_gate=%d cmd=%s\n", openGate, cmd);

      // Nếu server ra lệnh mở hoặc đóng cổng
      if (openGate > 0 && (strcmp(cmd, "open") == 0 || strcmp(cmd, "emergency") == 0 || strcmp(cmd, "close_all") == 0)) {
        Serial.printf("[CMD] Nhan lenh tu server: gate=%d, cmd=%s\n", openGate, cmd);
        executeOpenGate(openGate);
      }
    } else {
      Serial.printf("[SERVER] Parse JSON loi: %s\n", err.c_str());
    }
  } else if (httpCode < 0) {
    Serial.printf("[SERVER] Loi ket noi (%s): %s\n", url.c_str(), http.errorToString(httpCode).c_str());
  } else {
    Serial.printf("[SERVER] HTTP %d\n", httpCode);
  }

  http.end();
}

// ═══════════════════════════════════════════════════════════════
// GET /api/esp/heartbeat — Giữ kết nối, lấy lệnh pending
// ═══════════════════════════════════════════════════════════════
void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = "http://" + String(serverIP) + ":" + String(serverPort)
               + "/api/esp/heartbeat?ip=" + WiFi.localIP().toString();
  http.begin(wifiClient, url);
  http.setTimeout(2000);
  int httpCode = http.GET();

  if (httpCode == 200) {
    String response = http.getString();
    StaticJsonDocument<128> doc;
    if (!deserializeJson(doc, response)) {
      int gate        = doc["gate"] | 0;
      const char* cmd = doc["cmd"]  | "none";
      if (gate > 0 && strcmp(cmd, "open") == 0) {
        Serial.printf("[HEARTBEAT] Nhan lenh pending: mo cong %d\n", gate);
        executeOpenGate(gate);
      }
    }
  }
  http.end();
}

// ═══════════════════════════════════════════════════════════════
// Thực thi lệnh mở cổng từ server
// ═══════════════════════════════════════════════════════════════
void executeOpenGate(int gateId) {
  if (isGateActive) {
    Serial.println("[GATE] Dang xu ly, bo qua lenh moi.");
    return;
  }
  isGateActive = true;

  if (gateId == 1) {
    // ─── Cổng VÀO ────────────────────────────────────────────
    Serial.println("[GATE] >>> MO CONG VAO <<<");
    lcdPrint(">> Xe Vao <<", "Cho trong: " + String(availableSlots > 0 ? availableSlots - 1 : 0));
    beep1(1);

    servoIn.write(180);
    delay(GATE_OPEN_MS);
    servoIn.write(0); // Đóng lại

  } else if (gateId == 2) {
    // ─── Cổng RA ─────────────────────────────────────────────
    Serial.println("[GATE] <<< MO CONG RA >>>");
    lcdPrint("<< Xe Ra >>", "Cam on!");
    beep1(1);

    servoOut.write(0);
    delay(GATE_OPEN_MS);
    servoOut.write(180);
  } 
  
  // [ĐÃ COMMENT] ─── TÌNH TRẠNG KHẨN CẤP: MỞ CẢ 2 CỔNG ──────────
  
  else if (gateId == 3) {
    Serial.println("[EMERGENCY] <<< CHAY! MO TOAN BO CONG >>>");
    lcdPrint("!! CHAY !!", "DI TAN NGAY !!!");
    beep2(5); // Hú còi 5 tiếng dài
    
    servoIn.write(180);
    servoOut.write(0);
    // Lưu ý: Trong tình huống cháy, mình KHÔNG gọi hàm đóng cổng (write 0)
    // Cổng sẽ giữ trạng thái mở toang cho đến khi bạn reset mạch.
    // Nếu bạn muốn nó đóng lại sau 1 khoảng thời gian, bạn có thể thêm delay vào đây.
  }

  else if (gateId == 4) {
    Serial.println("[SAFE] <<< HET CHAY! DONG CONG >>>");
    lcdPrint("AN TOAN", "Hoat dong bth");
    servoIn.write(0);
    servoOut.write(180);
    delay(2000);
    beep2(0);
  }
  

  isGateActive = false;
  lcd.clear();
}

// ═══════════════════════════════════════════════════════════════
// LCD: Cập nhật hiển thị trạng thái bãi xe
// ═══════════════════════════════════════════════════════════════
void updateLCD() {
  // Bỏ qua cập nhật màn hình bình thường nếu đang cháy
  if (isFireDetected) {
     return; // Giữ nguyên chữ cảnh báo cháy trên màn hình
  }

  int s1 = digitalRead(irSlot1);
  int s2 = digitalRead(irSlot2);
  int s3 = digitalRead(irSlot3);
  availableSlots = (s1 == HIGH) + (s2 == HIGH) + (s3 == HIGH);

   if (availableSlots == 0) {
    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("!!! BAI XE DAY");
    beep1(1);
    return;
  }

  // Dòng 1: số chỗ trống 
  lcd.setCursor(0, 0);
  lcd.print("Cho trong: ");
  lcd.print(availableSlots);
  lcd.print("   ");

  // Dòng 2: trạng thái từng ô đỗ (F=đầy, E=trống)
  lcd.setCursor(0, 1);
  lcd.print("1:");
  lcd.print((s1 == LOW) ? "F" : "E");
  lcd.print(" 2:");
  lcd.print((s2 == LOW) ? "F" : "E");
  lcd.print(" 3:");
  lcd.print((s3 == LOW) ? "F" : "E");
  lcd.print("      ");
}

// ═══════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════
void lcdPrint(String line1, String line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1.substring(0, 16));
  lcd.setCursor(0, 1);
  lcd.print(line2.substring(0, 16));
}

void lcdPrint(String line1, const char* line2) {
  lcdPrint(line1, String(line2));
}

void beep1(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(buzzerPin, HIGH);
    delay(100);
    digitalWrite(buzzerPin, LOW);
    delay(100);
  }
}

void beep2(int times) {
  if (times == 0) {
    noTone(buzzerPin);
    digitalWrite(buzzerPin, LOW);
    return;
  }
  for (int t = 0; t < times; t++) {
    for (int i = 0; i < 180; i++) {
        sinVal = sin(i * (3.1412 / 180));   
        toneVal = 2000 + (int)(sinVal * 1000); 
        tone(buzzerPin, toneVal);
        delay(2);
    }
  }
  noTone(buzzerPin); // Tắt âm sau khi hú xong
  digitalWrite(buzzerPin, LOW);
}
