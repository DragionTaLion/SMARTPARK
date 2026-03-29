import socket
import threading

def scan_ip(ip, port, timeout=0.1):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            print(f"Found: {ip}:{port}")
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
    scan_range("172.20.10", 1, 20, 80)
    scan_range("172.20.10", 1, 20, 81)
