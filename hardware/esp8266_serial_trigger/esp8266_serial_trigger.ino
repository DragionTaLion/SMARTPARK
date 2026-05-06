/**
 * ============================================================
 *  ESP8266 — USB Serial Ultrasonic Trigger
 * ============================================================
 *  Chức năng:
 *    Đo khoảng cách HC-SR04, khi phát hiện xe (< 50cm)
 *    → gửi "TRIGGER\n" qua USB Serial về PC.
 *
 *  Kết nối chân:
 *    HC-SR04  →  ESP8266 (NodeMCU)
 *    VCC      →  3.3V
 *    GND      →  GND
 *    TRIG     →  D5 (GPIO14)
 *    ECHO     →  D6 (GPIO12)
 *
 *  Board: NodeMCU 1.0 (ESP-12E Module)
 *  Baud:  115200
 * ============================================================
 */

// ─── CẤU HÌNH ───────────────────────────────────────────────────────────────
const int   TRIG_PIN          = 14;    // D5
const int   ECHO_PIN          = 12;    // D6
const float DETECT_THRESHOLD  = 50.0; // cm — phát hiện xe khi < 50cm
const int   MEASURE_INTERVAL  = 200;  // ms — đo 5 lần/giây
const int   COOLDOWN_SECONDS  = 8;    // giây — cooldown sau mỗi trigger

unsigned long lastTriggerTime = 0;
unsigned long lastMeasureTime = 0;

void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  Serial.println("ESP8266 Ultrasonic Serial Trigger v1.0");
  Serial.println("READY");
}

void loop() {
  // Xử lý lệnh từ PC (ví dụ: "PING" để kiểm tra kết nối)
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "PING") Serial.println("PONG");
    if (cmd == "STATUS") {
      Serial.printf("STATUS:threshold=%.0fcm,cooldown=%ds\n",
                    DETECT_THRESHOLD, COOLDOWN_SECONDS);
    }
  }

  unsigned long now = millis();
  if (now - lastMeasureTime < MEASURE_INTERVAL) return;
  lastMeasureTime = now;

  float distance = measureDistance();

  // Phát hiện xe
  if (distance > 0 && distance < DETECT_THRESHOLD) {
    unsigned long elapsed = (now - lastTriggerTime) / 1000;
    if (lastTriggerTime == 0 || elapsed >= COOLDOWN_SECONDS) {
      // Gửi TRIGGER kèm khoảng cách để server có thể log
      Serial.printf("TRIGGER:%.1f\n", distance);
      lastTriggerTime = now;
    }
  }
}

// ─── ĐO KHOẢNG CÁCH HC-SR04 ─────────────────────────────────────────────────
float measureDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // timeout 30ms (~5m)
  if (duration == 0) return -1;
  return duration * 0.01715f;
}
