import socket
import threading

def scan_ip(ip, port, timeout=0.5):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            print(f" [✔] FOUND: {ip}:{port}")
            return True
        except:
            return False

def scan_range(prefix, start, end, port):
    print(f"Scanning {prefix}.{start}-{end}:{port}...")
    threads = []
    for i in range(start, end + 1):
        ip = f"{prefix}.{i}"
        t = threading.Thread(target=scan_ip, args=(ip, port))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

if __name__ == "__main__":
    import sys
    prefix = "192.168.137"
    if len(sys.argv) > 1:
        prefix = sys.argv[1]
    
    print(f"--- Đang quét các thiết bị trong mạng {prefix}.x ---")
    # Quét các cổng phổ biến của ESP8266/ESP32 Cam
    for port in [80, 81]:
        scan_range(prefix, 1, 254, port)
    print("--- Hoàn tất quét mạng ---")
