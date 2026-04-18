#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <Servo.h>

// ================= CẤU HÌNH WIFI =================
const char* ssid = "Ho Sy Can";
const char* password = "phongtro284";

// ================= CẤU HÌNH SERVER =================
// Địa chỉ IP máy tính đã chạy api_server.py
const char* serverUrl = "http://192.168.50.38:8000/api/trigger?gate=in";

// ================= CẤU HÌNH CHÂN (PINS) =================
const int trigPin = D1;  // GPIO 5
const int echoPin = D2;  // GPIO 4
const int servoPin = D3; // GPIO 0

Servo barrierServo;
bool isCarDetected = false;

void setup() {
  Serial.begin(115200);
  
  // Setup Pins
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  
  // Setup Servo
  barrierServo.attach(servoPin);
  barrierServo.write(0); // Đóng lúc khởi động
  
  // Kết nối WiFi
  Serial.println();
  Serial.print("Dang ket noi WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("WiFi da ket noi!");
  Serial.print("Dia chi IP: ");
  Serial.println(WiFi.localIP());
}

long getDistance() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  long duration = pulseIn(echoPin, HIGH);
  return duration * 0.034 / 2;
}

void openBarrier() {
  Serial.println(">>> DANG MO BARRIER...");
  barrierServo.write(90); // Xoay 90 do de mo
  delay(5000);            // Cho 5 giay cho xe qua
  barrierServo.write(0);  // Dong lai
  Serial.println(">>> DA DONG BARRIER.");
}

void loop() {
  long distance = getDistance();
  
  // Neu khoang cach < 15cm va chua ghi nhan xe nay
  if (distance > 0 && distance < 15 && !isCarDetected) {
    Serial.print("Phat hien xe! Khoang cach: ");
    Serial.println(distance);
    
    isCarDetected = true; // Đánh dấu là đã bắt đầu xử lý xe này
    
    // Gui lenh len Server thong qua WiFi
    if (WiFi.status() == WL_CONNECTED) {
      WiFiClient client;
      HTTPClient http;
      
      Serial.println("Gui yeu cau den Server...");
      http.begin(client, serverUrl);
      
      int httpCode = http.POST(""); // Gui yeu cau POST trong
      
      if (httpCode > 0) {
        String payload = http.getString();
        Serial.println("Server tra loi: " + payload);
        
        // Kiem tra neu Server cho phep mo (Resident + Con cho)
        if (payload.indexOf("\"action\":\"open\"") != -1) {
          openBarrier();
        } else {
          Serial.println("Server TU CHOI mo (Xe la hoac het cho)");
        }
      } else {
        Serial.print("Loi ket noi Server: ");
        Serial.println(http.errorToString(httpCode).c_str());
      }
      http.end();
    }
  }
  
  // Neu xe da di xa (> 20cm), reset trang thai de don xe tiep theo
  if (distance > 20) {
    isCarDetected = false;
  }
  
  delay(100);
}
