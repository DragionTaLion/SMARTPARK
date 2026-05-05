import urllib.request, json, socket, time

def test_http(url, label, method='GET', body=None, timeout=5):
    try:
        start = time.time()
        req = urllib.request.Request(url, data=body,
              headers={'Content-Type': 'application/json'} if body else {},
              method=method)
        r = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(r.read())
        ms = (time.time() - start) * 1000
        print(f'  [OK]  {label:<28}: {ms:5.0f}ms')
        return data
    except Exception as e:
        print(f'  [ERR] {label:<28}: {e}')
        return None

def test_port(ip, port, label):
    s = socket.socket()
    s.settimeout(2)
    ok = s.connect_ex((ip, port)) == 0
    s.close()
    print(f'  [{"OK" if ok else "ERR"}]  {label:<28}: port {port} {"OPEN" if ok else "CLOSED"}')
    return ok

SEP = '='*55

print(SEP)
print('  SMARTPARK v3.0 — Flow Diagnostic')
print(SEP)

# ── 1. BACKEND SERVER ───────────────────────────────────
print('\n[1] BACKEND (FastAPI — localhost:8000)')
h = test_http('http://localhost:8000/api/health', 'Health Check')
if h:
    print(f'       DB:          {h.get("db")}')
    print(f'       YOLO:        {h.get("yolo")}')
    print(f'       CNN Model:   {h.get("char_model")}')
    print(f'       GPU:         {"CUDA RTX3060" if h.get("gpu") else "CPU only"}')
    print(f'       Camera IP:   {h.get("camera_ip")}')
    print(f'       ESP8266 IP:  {h.get("esp8266_ip")}')
    print(f'       Cam Status:  {"CONNECTED" if h.get("camera_connected") else "OFFLINE"}')

test_http('http://localhost:8000/api/stats', 'Stats API')
test_http('http://localhost:8000/api/residents', 'Residents API')

# ── 2. ESP32-CAM ────────────────────────────────────────
print('\n[2] ESP32-CAM (192.168.137.181)')
cam_up = test_port('192.168.137.181', 80, 'Port 80 (HTTP)')
test_port('192.168.137.181', 81, 'Port 81 (MJPEG Stream)')

if cam_up:
    try:
        resp = urllib.request.urlopen('http://192.168.137.181/capture', timeout=4)
        size = len(resp.read())
        print(f'  [OK]  {"Snapshot capture":<28}: {size} bytes ({size//1024}KB)')
    except Exception as e:
        print(f'  [ERR] {"Snapshot capture":<28}: {e}')

# Test qua Backend proxy
try:
    resp = urllib.request.urlopen('http://localhost:8000/api/video_feed', timeout=2)
    data = resp.read(1024)
    print(f'  [OK]  {"Backend MJPEG Proxy":<28}: streaming OK ({len(data)} bytes received)')
except Exception as e:
    print(f'  [ERR] {"Backend MJPEG Proxy":<28}: {e}')

# ── 3. ESP8266 → SERVER FLOW ───────────────────────────
print('\n[3] ESP8266 FLOW (192.168.137.28 → Server)')
print('  > Simulating ESP8266 POST /api/v1/entry-request...')
body = b'{"distance":8.5,"device_id":"diag_test"}'
resp = test_http('http://localhost:8000/api/v1/entry-request',
                 'V1 Entry-Request', 'POST', body, timeout=20)
if resp:
    print(f'       Action:      {resp.get("action")}')
    print(f'       Plate:       {resp.get("plate", "N/A")}')
    print(f'       Owner:       {resp.get("owner", "N/A")}')
    print(f'       Reason:      {resp.get("reason", "-")}')
    print(f'       ProcessTime: {resp.get("processing_ms", "?")} ms')

# ── SUMMARY ─────────────────────────────────────────────
print('\n' + SEP)
print('  SUMMARY')
print(SEP)
components = [
    ('Backend FastAPI', h is not None),
    ('Database PostgreSQL', h is not None and 'connected' in str(h.get('db',''))),
    ('ESP32-CAM reachable', cam_up),
    ('V1 IoT Endpoint', resp is not None),
]
for name, ok in components:
    icon = 'OK  ' if ok else 'FAIL'
    print(f'  [{icon}] {name}')
print(SEP)
