/*
 * Code Arduino điều khiển Barrier bằng Servo Motor
 * 
 * Kết nối:
 * - Servo Signal (Cam) -> D9
 * - Servo VCC (Đỏ) -> 5V
 * - Servo GND (Nâu/Đen) -> GND
 * 
 * Lệnh từ Python:
 * - Gửi ký tự 'O' (chữ O hoa) để mở barrier
 * - Barrier sẽ tự động đóng lại sau 3 giây
 */

#include <Servo.h>

Servo myservo;  // Tạo đối tượng Servo

// Cấu hình
const int SERVO_PIN = 9;
const int CLOSED_ANGLE = 0;    // Góc đóng barrier (0 độ)
const int OPEN_ANGLE = 90;     // Góc mở barrier (90 độ)
const int OPEN_DURATION = 3000; // Thời gian mở (3 giây)

void setup() {
  // Khởi tạo Serial với baud rate 9600
  Serial.begin(9600);
  
  // Gắn Servo vào chân D9
  myservo.attach(SERVO_PIN);
  
  // Đặt barrier ở vị trí đóng ban đầu
  myservo.write(CLOSED_ANGLE);
  
  // Đợi 1 giây để Servo ổn định
  delay(1000);
  
  Serial.println("Barrier system ready!");
  Serial.println("Send 'O' to open barrier");
}

void loop() {
  // Kiểm tra có dữ liệu từ Serial không
  if (Serial.available() > 0) {
    char command = Serial.read();
    
    // Xử lý lệnh 'O' (mở barrier)
    if (command == 'O' || command == 'o') {
      Serial.println("Opening barrier...");
      
      // Mở barrier
      myservo.write(OPEN_ANGLE);
      
      // Đợi 3 giây
      delay(OPEN_DURATION);
      
      // Đóng barrier lại
      myservo.write(CLOSED_ANGLE);
      
      Serial.println("Barrier closed");
    }
    // Có thể thêm các lệnh khác ở đây nếu cần
    else {
      Serial.print("Unknown command: ");
      Serial.println(command);
    }
  }
  
  // Delay nhỏ để tránh đọc Serial quá nhanh
  delay(10);
}
