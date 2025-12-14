import requests
import time
import random
import math
import sys
import threading

LB_URL = "http://127.0.0.1:8000"

def send_request(request_id):
    try:
        start = time.time()
        # Timeout cực ngắn để không block luồng gửi nếu server chậm
        resp = requests.get(LB_URL, timeout=3) 
        elapsed = time.time() - start
        
        data = resp.json()
        server_name = data.get("server", "Unknown")
        status = data.get("status", "Unknown")
        
        # In kết quả gọn gàng
        # Cache hit thì in màu xanh lá, Miss thì in màu thường
        if "served_from_cache" in data.get("status", ""):
            print(f"\033[92m[Req #{request_id}] ✅ CACHE HIT ({elapsed:.3f}s)\033[0m")
        else:
            print(f"[Req #{request_id}] ➡️ {server_name} ({elapsed:.3f}s)")
            
    except requests.exceptions.RequestException:
        print(f"\033[91m[Req #{request_id}] ❌ FAILED (Load Balancer Timeout/Down)\033[0m")

def run_steady_mode(rps):
    print(f"\n--- CHẾ ĐỘ STEADY: {rps} Requests/Giây ---")
    print("Nhấn Ctrl+C để dừng...")
    counter = 0
    delay = 1.0 / rps
    try:
        while True:
            counter += 1
            # Tạo luồng mới cho mỗi request để không bị block
            threading.Thread(target=send_request, args=(counter,)).start()
            time.sleep(delay)
    except KeyboardInterrupt:
        print("\nĐã dừng test.")

def run_spike_mode():
    print(f"\n--- CHẾ ĐỘ SPIKE (ĐỘT BIẾN) ---")
    print("Mô phỏng: Yên bình -> BÙM (Traffic tăng vọt) -> Yên bình")
    print("Nhấn Ctrl+C để dừng...")
    counter = 0
    try:
        while True:
            # 1. Giai đoạn yên bình (Normal traffic)
            print("\n🔵 Giai đoạn bình thường (Normal)...")
            for _ in range(10):
                counter += 1
                threading.Thread(target=send_request, args=(counter,)).start()
                time.sleep(0.5) # 2 req/s

            # 2. Giai đoạn Bùng nổ (Spike traffic)
            print("\n🔴 PHÁT HIỆN TRAFFIC SPIKE!!! (DDoS mô phỏng)...")
            for _ in range(1000): # Bắn 1000 req cực nhanh
                counter += 1
                threading.Thread(target=send_request, args=(counter,)).start()
                time.sleep(0.05) # 20 req/s

            print("\n🟢 Hạ nhiệt...")
            time.sleep(2) # Nghỉ ngơi

    except KeyboardInterrupt:
        print("\nĐã dừng test.")

def run_wave_mode():
    print(f"\n--- CHẾ ĐỘ SINE WAVE (HÌNH SIN) ---")
    print("Mô phỏng: Traffic tăng dần lên đỉnh rồi giảm dần xuống đáy...")
    counter = 0
    t = 0
    try:
        while True:
            # Công thức hình sin để tạo dao động traffic
            # Traffic sẽ dao động từ 2 req/s đến 20 req/s
            traffic_intensity = 11 + 9 * math.sin(t) 
            
            # Delay tỷ lệ nghịch với độ mạnh traffic (càng mạnh delay càng thấp)
            current_rps = int(traffic_intensity)
            delay = 1.0 / max(1, current_rps)
            
            counter += 1
            threading.Thread(target=send_request, args=(counter,)).start()
            
            # Hiển thị mức độ traffic hiện tại bằng thanh ngang
            bar = "█" * current_rps
            sys.stdout.write(f"\rTraffic Level: {bar} ({current_rps} req/s)   ")
            sys.stdout.flush()

            time.sleep(delay)
            t += 0.1 # Tăng biến thời gian
            
    except KeyboardInterrupt:
        print("\nĐã dừng test.")

if __name__ == "__main__":
    print("==========================================")
    print("   CÔNG CỤ GIẢ LẬP TRAFFIC (LOAD TEST)    ")
    print("==========================================")
    print("1. Ổn định (Steady Load)")
    print("2. Đột biến (Spike/Burst Load)")
    print("3. Hình Sin (Wave/Oscillating Load)")
    print("==========================================")
    
    choice = input("Chọn chế độ (1/2/3): ")
    
    if choice == '1':
        rps = float(input("Nhập số request/giây (VD: 5): "))
        run_steady_mode(rps)
    elif choice == '2':
        run_spike_mode()
    elif choice == '3':
        run_wave_mode()
    else:
        print("Lựa chọn không hợp lệ!")