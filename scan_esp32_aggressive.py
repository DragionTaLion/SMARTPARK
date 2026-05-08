import socket
import concurrent.futures

def scan(ip, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        if s.connect_ex((ip, port)) == 0:
            print(f"FOUND: {ip}:{port}")
            return (ip, port)
    return None

ips = [f"192.168.137.{i}" for i in range(1, 255)]
ports = [80, 81]

print("Scanning 192.168.137.1-254 on ports 80, 81...")
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    futures = [executor.submit(scan, ip, port) for ip in ips for port in ports]
    results = [f.result() for f in futures if f.result()]

if not results:
    print("No devices found on these ports.")
else:
    print(f"Results: {results}")
