import requests
import time
import random
import math
import sys
import threading

LB_URL = "http://127.0.0.1:8000"

def send_request(request_id, duration=None):
    try:
        start = time.time()
        
        # Nếu có duration (giây), gửi kèm param để Backend biết mà "ngủ"
        params = {}
        if duration:
            params['duration'] = duration
            
        # Timeout phải dài hơn duration để không bị ngắt giữa chừng
        resp = requests.get(LB_URL, params=params, timeout=30) 
        elapsed = time.time() - start
        
        data = resp.json()
        server_name = data.get("server", "Unknown")
        status = data.get("status", "Unknown")
        conn_type = data.get("connection_type", "short")
        
        # In kết quả
        if "served_from_cache" in status:
            print(f"\033[92m[Req #{request_id}] ✅ CACHE HIT ({elapsed:.3f}s)\033[0m")
        else:
            if conn_type == "long-lived":
                print(f"\033[93m[Req #{request_id}] 🕒 LONG REQ ({duration}s) -> {server_name}\033[0m")
            else:
                print(f"[Req #{request_id}] ➡️ {server_name} ({elapsed:.3f}s)")
            
    except requests.exceptions.RequestException as e:
        print(f"\033[91m[Req #{request_id}] ❌ FAILED ({str(e)[:50]})\033[0m")

def run_steady_mode(rps):
    print(f"\n--- CHẾ ĐỘ STEADY: {rps} Requests/Giây ---")
    print("Nhấn Ctrl+C để dừng...")
    counter = 0
    delay = 1.0 / rps
    try:
        while True:
            counter += 1
            threading.Thread(target=send_request, args=(counter,)).start()
            time.sleep(delay)
    except KeyboardInterrupt:
        print("\nĐã dừng test.")

def run_spike_mode():
    print(f"\n--- CHẾ ĐỘ SPIKE (ĐỘT BIẾN) ---")
    counter = 0
    try:
        while True:
            print("\n🔵 Normal traffic...")
            for _ in range(5):
                counter += 1
                threading.Thread(target=send_request, args=(counter,)).start()
                time.sleep(0.5)

            print("\n🔴 SPIKE!!! (20 reqs fast)")
            for _ in range(20): 
                counter += 1
                threading.Thread(target=send_request, args=(counter,)).start()
                time.sleep(0.05) 
            time.sleep(2) 
    except KeyboardInterrupt:
        print("\nĐã dừng test.")

def run_wave_mode():
    print(f"\n--- CHẾ ĐỘ SINE WAVE (HÌNH SIN) ---")
    counter = 0
    t = 0
    try:
        while True:
            traffic_intensity = 11 + 9 * math.sin(t) 
            current_rps = int(traffic_intensity)
            delay = 1.0 / max(1, current_rps)
            
            counter += 1
            threading.Thread(target=send_request, args=(counter,)).start()
            
            bar = "█" * current_rps
            sys.stdout.write(f"\rTraffic Level: {bar} ({current_rps} req/s)   ")
            sys.stdout.flush()

            time.sleep(delay)
            t += 0.1 
    except KeyboardInterrupt:
        print("\nĐã dừng test.")

# [CẬP NHẬT] Chế độ Mixed tự động lặp (Auto Loop)
def run_mixed_mode():
    print(f"\n--- CHẾ ĐỘ MIXED (Test Least Connection - Auto Loop) ---")
    print("Mô tả: Gửi 4 request dài (5s) -> Đợi -> Gửi 10 request ngắn -> Đợi 6s -> Lặp lại.")
    print("Nhấn Ctrl+C để dừng.")
    
    counter = 0
    try:
        while True:
            print(f"\n🔄 --- BẮT ĐẦU CHU KỲ MỚI ---")
            
            # 1. Gửi 4 request dài (chiếm dụng kết nối)
            # Mục tiêu: Làm bận 2 server (mỗi server 2 conn), chừa 1 server rảnh (0 conn)
            print("🚀 Đang gửi 4 request chiếm dụng 5 giây...")
            for _ in range(4):
                counter += 1
                threading.Thread(target=send_request, args=(counter, 5)).start()
                time.sleep(0.1)
            
            time.sleep(1) # Đợi chút cho active_conns trên LB cập nhật
            
            # 2. Gửi request ngắn
            # Least Connection sẽ đẩy hết vào server rảnh (Active=0)
            print("🚀 Đang gửi 10 request ngắn liên tiếp...")
            for _ in range(10):
                counter += 1
                threading.Thread(target=send_request, args=(counter,)).start()
                time.sleep(0.2)
            
            print("⏳ Đang chờ server giải phóng kết nối (6s)...")
            # Ngủ 6s (lớn hơn thời gian giữ kết nối 5s) để đảm bảo mọi server về trạng thái rảnh
            # trước khi bắt đầu chu kỳ mới, giúp test chính xác hơn.
            time.sleep(6) 
            
    except KeyboardInterrupt:
        print("\nĐã dừng test.")

if __name__ == "__main__":
    print("==========================================")
    print("   CÔNG CỤ GIẢ LẬP TRAFFIC (LOAD TEST)    ")
    print("==========================================")
    print("1. Ổn định (Steady Load)")
    print("2. Đột biến (Spike/Burst Load)")
    print("3. Hình Sin (Wave/Oscillating Load)")
    print("4. Hỗn hợp (Mixed - Auto Loop)")
    print("==========================================")
    
    choice = input("Chọn chế độ (1-4): ")
    
    if choice == '1':
        rps = float(input("Nhập số request/giây (VD: 5): "))
        run_steady_mode(rps)
    elif choice == '2':
        run_spike_mode()
    elif choice == '3':
        run_wave_mode()
    elif choice == '4':
        run_mixed_mode()
    else:
        print("Lựa chọn không hợp lệ!")