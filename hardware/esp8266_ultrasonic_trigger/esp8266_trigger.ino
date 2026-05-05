/**
 * ============================================================
 *  ESP8266 — SmartPark IoT Gateway v2.1 (v4.0 compatible)
 * ============================================================
 *  Phần cứng:
 *    - NodeMCU / Wemos D1 Mini (ESP8266)
 *    - Cảm biến siêu âm HC-SR04
 *    - Servo Motor SG90 (điều khiển barrier)
 *
 *  Kết nối chân:
 *    HC-SR04  ->  ESP8266
 *    VCC      ->  5V (qua breadboard)
 *    GND      ->  GND
 *    TRIG     ->  D1 (GPIO5)
 *    ECHO     ->  D2 (GPIO4)
 *
 *    Servo    ->  ESP8266
 *    Signal   ->  D3 (GPIO0)
 *    VCC      ->  5V
 *    GND      ->  GND
 *
 *  Thư viện cần cài (Arduino Library Manager):
 *    - ESP8266WiFi       (tích hợp sẵn)
 *    - ESP8266HTTPClient (tích hợp sẵn)
 *    - ArduinoJson       (v6.x)
 *    - Servo             (tích hợp sẵn)
 *
 *  Luồng hoạt động:
 *    1. Đọc cảm biến mỗi MEASURE_INTERVAL ms (non-blocking với millis)
 *    2. Nếu distance < DETECT_THRESHOLD trong CONFIRM_DURATION ms liên tiếp → trigger
 *    3. POST /api/v1/entry-request đến FastAPI server
 *    4. Parse JSON response:
 *         action="OPEN"  → openBarrier() → servo 90° trong BARRIER_OPEN_MS → tự đóng 0°
 *         action="DENY"  → Serial log, không làm gì
 *    5. Tự đóng barrier trong loop() dùng millis() — NON-BLOCKING
 *
 *  Thay đổi v2.1:
 *    - Thêm hằng số rõ ràng: SERVO_OPEN_ANGLE, SERVO_CLOSE_ANGLE
 *    - Cải thiện Serial Debug: in đầy đủ giai đoạn OPEN → HOLD → CLOSE
 *    - In stage từ WebSocket response (stage field nếu có)
 * ============================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <WiFiClient.h>
#include <Servo.h>

// ─── CẤU HÌNH MẠNG ───────────────────────────────────────────────────────────
const char* WIFI_SSID   = "Long";
const char* WIFI_PASS   = "long12345";
const char* SERVER_IP   = "192.168.137.1";   // IP máy tính (FastAPI server)
const int   SERVER_PORT = 8000;

// ─── CHÂN PHẦN CỨNG ──────────────────────────────────────────────────────────
const int TRIG_PIN  = 5;    // D1 (GPIO5) — HC-SR04 Trigger
const int ECHO_PIN  = 4;    // D2 (GPIO4) — HC-SR04 Echo
const int SERVO_PIN = 0;    // D3 (GPIO0) — Servo Signal
const int LED_PIN   = 2;    // LED onboard (active LOW)

// ─── GÓC SERVO ────────────────────────────────────────────────────────────────
// v2.1: Định nghĩa hằng số góc rõ ràng thay vì magic numbers
const int SERVO_OPEN_ANGLE  = 90;   // Góc MỞ barrier (90 độ)
const int SERVO_CLOSE_ANGLE = 0;    // Góc ĐÓNG barrier (0 độ)

// ─── NGƯỠNG & THỜI GIAN ──────────────────────────────────────────────────────
const float DETECT_THRESHOLD = 10.0;    // cm — ngưỡng phát hiện xe
const int   CONFIRM_DURATION = 2000;    // ms — thời gian giữ để xác nhận (chống nhiễu)
const int   MEASURE_INTERVAL = 200;     // ms — chu kỳ đo cảm biến (5 Hz)
const int   COOLDOWN_MS      = 10000;   // ms — cooldown sau mỗi trigger
const int   HTTP_TIMEOUT_MS  = 20000;   // ms — timeout HTTP (đủ cho voting 7 frame ~12s)
const int   BARRIER_OPEN_MS  = 3000;    // ms — thời gian giữ barrier mở trước khi tự đóng

// ─── BIẾN TRẠNG THÁI ─────────────────────────────────────────────────────────
Servo barrierServo;

unsigned long lastMeasureTime    = 0;
unsigned long lastTriggerTime    = 0;
unsigned long detectionStartTime = 0;
unsigned long barrierOpenTime    = 0;

bool isDetecting  = false;    // Đang trong quá trình xác nhận xe
bool barrierOpen  = false;    // Trạng thái barrier hiện tại
bool isSending    = false;    // Đang gửi HTTP request (block sensor loop)

// ─── SETUP ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n\n============================================");
  Serial.println("  SmartPark ESP8266 Gateway v2.1");
  Serial.println("  Compatible with SmartPark Backend v4.0");
  Serial.println("============================================");

  // Khởi tạo chân HC-SR04
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  // LED debug (active LOW)
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);   // Tắt LED ban đầu

  // Khởi tạo Servo — đặt về vị trí đóng
  barrierServo.attach(SERVO_PIN);
  barrierServo.write(SERVO_CLOSE_ANGLE);
  Serial.printf("[SERVO] Khởi tạo: đặt về CLOSE (%d°)\n", SERVO_CLOSE_ANGLE);

  // Kết nối WiFi
  connectWiFi();
  Serial.printf("[WiFi] RSSI: %d dBm\n", WiFi.RSSI());
  Serial.printf("[CONFIG] Server: http://%s:%d\n", SERVER_IP, SERVER_PORT);
  Serial.printf("[CONFIG] Detect threshold: %.1f cm\n", DETECT_THRESHOLD);
  Serial.printf("[CONFIG] Confirm duration: %d ms\n", CONFIRM_DURATION);
  Serial.printf("[CONFIG] HTTP timeout: %d ms\n", HTTP_TIMEOUT_MS);
  Serial.printf("[CONFIG] Barrier open: %d ms\n", BARRIER_OPEN_MS);
  Serial.println("============================================\n");
}

// ─── LOOP (NON-BLOCKING) ─────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // 1. Kiểm tra kết nối WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Mất kết nối — đang thử lại...");
    connectWiFi();
    delay(1000);
    return;
  }

  // 2. Tự đóng barrier sau BARRIER_OPEN_MS — NON-BLOCKING (dùng millis)
  //    Đây là cơ chế an toàn: barrier luôn tự đóng mà không làm treo chip
  if (barrierOpen && (now - barrierOpenTime >= (unsigned long)BARRIER_OPEN_MS)) {
    barrierServo.write(SERVO_CLOSE_ANGLE);
    barrierOpen = false;
    Serial.printf(
      "[BARRIER] ⬇ AUTO-CLOSE — Barrier đóng về %d° sau %d ms\n",
      SERVO_CLOSE_ANGLE, BARRIER_OPEN_MS
    );
    digitalWrite(LED_PIN, HIGH);   // Tắt LED sau khi đóng
  }

  // 3. Bỏ qua vòng lặp nếu đang gửi HTTP hoặc trong cooldown
  if (isSending) {
    delay(50);
    return;
  }
  if (lastTriggerTime != 0 && (now - lastTriggerTime < (unsigned long)COOLDOWN_MS)) {
    unsigned long remaining = COOLDOWN_MS - (now - lastTriggerTime);
    // Chỉ in cảnh báo 1 lần mỗi giây để không spam Serial
    static unsigned long lastCooldownLog = 0;
    if (now - lastCooldownLog >= 1000) {
      Serial.printf("[COOLDOWN] Còn %lu ms\n", remaining);
      lastCooldownLog = now;
    }
    delay(50);
    return;
  }

  // 4. Đo cảm biến theo chu kỳ MEASURE_INTERVAL
  if (now - lastMeasureTime < (unsigned long)MEASURE_INTERVAL) return;
  lastMeasureTime = now;

  float distance = measureDistance();
  if (distance > 0) {
    Serial.printf("[SENSOR] HC-SR04: %.1f cm\n", distance);
  }

  // 5. Logic xác nhận 2 giây (chống nhiễu cảm biến)
  if (distance > 0 && distance < DETECT_THRESHOLD) {
    if (!isDetecting) {
      // Bắt đầu đếm thời gian xác nhận
      isDetecting = true;
      detectionStartTime = now;
      Serial.printf(
        "[DETECT] Phát hiện vật thể %.1f cm < %.1f cm — đếm xác nhận...\n",
        distance, DETECT_THRESHOLD
      );
    } else {
      // Kiểm tra đã giữ đủ CONFIRM_DURATION chưa
      unsigned long held = now - detectionStartTime;
      if (held >= (unsigned long)CONFIRM_DURATION) {
        Serial.printf(
          "\n[TRIGGER!] ✅ Xe xác nhận sau %lu ms — gửi trigger đến server!\n",
          held
        );
        sendTrigger(distance);
        lastTriggerTime = millis();
        isDetecting = false;
      }
    }
  } else {
    // Vật thể rời khỏi vùng phát hiện → reset bộ đếm
    if (isDetecting) {
      Serial.println("[DETECT] Vật thể rời đi — reset bộ đếm xác nhận");
    }
    isDetecting = false;
    detectionStartTime = 0;
  }
}

// ─── ĐO KHOẢNG CÁCH HC-SR04 ──────────────────────────────────────────────────
float measureDistance() {
  // Gửi xung Trigger 10µs
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // Đo thời gian Echo (timeout 30ms = tối đa ~5m)
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return -1;   // Timeout → không có tín hiệu
  return duration * 0.01715f;     // Chuyển sang cm (34300 cm/s / 2)
}

// ─── GỬI HTTP TRIGGER ─────────────────────────────────────────────────────────
void sendTrigger(float distance) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] Không có WiFi — bỏ qua trigger");
    return;
  }

  isSending = true;
  digitalWrite(LED_PIN, LOW);   // Bật LED báo hiệu đang xử lý

  WiFiClient client;
  HTTPClient http;

  String url = String("http://") + SERVER_IP + ":" + SERVER_PORT + "/api/v1/entry-request";
  Serial.println("[HTTP] ─────────────────────────────────────────");
  Serial.printf("[HTTP] POST %s\n", url.c_str());
  Serial.printf("[HTTP] Payload: {distance=%.1f cm, device=esp8266_gate_v2}\n", distance);
  Serial.printf("[HTTP] Timeout: %d ms (đủ cho voting 7 frame)\n", HTTP_TIMEOUT_MS);

  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(HTTP_TIMEOUT_MS);

  // Build JSON body theo EntryRequest schema
  StaticJsonDocument<256> doc;
  doc["distance"]  = distance;
  doc["device_id"] = "esp8266_gate_v2";
  doc["threshold"] = DETECT_THRESHOLD;
  String body;
  serializeJson(doc, body);

  int httpCode = http.POST(body);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("[HTTP] Response %d: %s\n", httpCode, response.c_str());

    // Parse JSON response từ backend
    StaticJsonDocument<512> resp;
    DeserializationError err = deserializeJson(resp, response);

    if (!err && httpCode == 200) {
      const char* action       = resp["action"] | "DENY";
      const char* plate        = resp["plate"]  | "N/A";
      const char* owner        = resp["owner"]  | "Xe lạ";
      const char* trang_thai   = resp["trang_thai"] | "N/A";
      float       proc_ms      = resp["processing_ms"] | 0.0f;

      Serial.println("[HTTP] ─────────────────────────────────────────");
      Serial.printf("[RESULT] Action     : %s\n", action);
      Serial.printf("[RESULT] Biển số    : %s\n", plate);
      Serial.printf("[RESULT] Chủ xe     : %s\n", owner);
      Serial.printf("[RESULT] Trạng thái : %s\n", trang_thai);
      Serial.printf("[RESULT] Thời gian AI: %.0f ms\n", proc_ms);
      Serial.println("[HTTP] ─────────────────────────────────────────");

      if (strcmp(action, "OPEN") == 0) {
        openBarrier();
      } else {
        Serial.println("[BARRIER] 🔒 DENY — Không mở cổng");
      }
    } else {
      Serial.printf("[HTTP] ❌ Parse error hoặc lỗi response: %s\n", err.c_str());
    }
  } else {
    Serial.printf("[HTTP] ❌ Kết nối thất bại: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
  isSending = false;
  // LED sẽ tắt khi barrier đóng lại (trong loop)
}

// ─── MỞ BARRIER ──────────────────────────────────────────────────────────────
void openBarrier() {
  Serial.println("[BARRIER] ─────────────────────────────────────────");
  Serial.printf("[BARRIER] ⬆ OPEN  — Servo quay %d° (mở barrier)\n", SERVO_OPEN_ANGLE);
  barrierServo.write(SERVO_OPEN_ANGLE);
  barrierOpen = true;
  barrierOpenTime = millis();
  Serial.printf("[BARRIER] ⏳ HOLD  — Giữ mở trong %d ms\n", BARRIER_OPEN_MS);
  Serial.printf("[BARRIER] ⬇ CLOSE — Sẽ tự đóng về %d° sau %d ms (non-blocking)\n",
                SERVO_CLOSE_ANGLE, BARRIER_OPEN_MS);
  Serial.println("[BARRIER] ─────────────────────────────────────────");
}

// ─── KẾT NỐI WIFI ─────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.printf("[WiFi] Đang kết nối tới '%s'", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] ✅ Kết nối thành công!\n");
    Serial.printf("[WiFi] IP local : %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[WiFi] RSSI     : %d dBm\n", WiFi.RSSI());
  } else {
    Serial.println("\n[WiFi] ❌ Thất bại sau 20 lần thử — sẽ tự thử lại...");
  }
}
