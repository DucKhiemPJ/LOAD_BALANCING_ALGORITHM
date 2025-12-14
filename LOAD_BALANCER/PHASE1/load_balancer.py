import requests
import time
import random
import threading
import math
from flask import Flask, jsonify, request
 
app = Flask(__name__)
 
# --- CẤU HÌNH ---
CURRENT_ALGORITHM = 'peak_ewma'
CACHE_PROBABILITY = 0.1
TOTAL_REQUESTS = 0
RESPONSE_CACHE = {}
CACHE_HITS = 0      
 
# Định giá server ($/giờ)
SERVER_PRICES = {"Fast (8001)": 10, "Medium (8002)": 5, "Slow (8003)": 2}
 
SERVERS = [
    {"name": "Fast (8001)", "url": "http://127.0.0.1:8001", "weight": 5, "active_conns": 0, "avg_response_time": 0.1, "ewma_response_time": 0.1, "total_handled": 0, "active": True, "cpu_usage": 0, "health_status": "healthy", "last_crash_time": 0},
    {"name": "Medium (8002)", "url": "http://127.0.0.1:8002", "weight": 3, "active_conns": 0, "avg_response_time": 0.5, "ewma_response_time": 0.5, "total_handled": 0, "active": True, "cpu_usage": 0, "health_status": "healthy", "last_crash_time": 0},
    {"name": "Slow (8003)", "url": "http://127.0.0.1:8003", "weight": 1, "active_conns": 0, "avg_response_time": 1.0, "ewma_response_time": 1.0, "total_handled": 0, "active": True, "cpu_usage": 0, "health_status": "healthy", "last_crash_time": 0},
]
current_index = 0
BACKEND_RECOVERY_TIME = 10  # Thời gian chờ hồi phục sau crash
EWMA_DECAY = 0.3            # Hệ số làm mượt cho thuật toán EWMA
 
# --- HÀM HỖ TRỢ CHẠY NGẦM ---
def cpu_decay_loop():
    """Giảm CPU ảo khi server rảnh rỗi (để biểu đồ đẹp hơn)"""
    while True:
        time.sleep(1)
        for server in SERVERS:
            if server.get('health_status') == 'crashed': continue
            if server['cpu_usage'] > 0:
                decay_amount = random.randint(10, 20)
                server['cpu_usage'] = max(0, server['cpu_usage'] - decay_amount)
 
threading.Thread(target=cpu_decay_loop, daemon=True).start()
 
# --- HÀM LỌC SERVER (CIRCUIT BREAKER) ---
def get_available_servers():
    """
    Trả về danh sách server:
    1. Đang bật (active=True)
    2. KHÔNG bị crash (hoặc đã hết thời gian phạt)
    """
    candidates = []
    current_time = time.time()
    for s in SERVERS:
        if not s['active']: continue
       
        # Logic Circuit Breaker: Kiểm tra server chết
        if s.get('health_status') == 'crashed':
            time_since_crash = current_time - s.get('last_crash_time', 0)
            if time_since_crash < BACKEND_RECOVERY_TIME:
                continue # Vẫn đang trong thời gian cách ly -> Bỏ qua
       
        candidates.append(s)
    return candidates
 
def calculate_current_cost():
    return sum(SERVER_PRICES[s['name']] for s in SERVERS if s['active'])
 
# ============================================================
# --- 6 THUẬT TOÁN CÂN BẰNG TẢI ---
# ============================================================
 
# 1. Round Robin (Cũ) - Chia đều vòng tròn
def get_server_round_robin():
    global current_index
    candidates = get_available_servers()
    if not candidates: return None
    server = candidates[current_index % len(candidates)]
    current_index += 1
    return server
 
# 2. Least Connection (Cũ) - Chọn ai đang ít việc nhất
def get_server_least_connection():
    candidates = get_available_servers()
    if not candidates: return None
    return min(candidates, key=lambda s: s["active_conns"])
 
# 3. Weighted Response Time (Cũ) - Dựa trên độ trễ trung bình và trọng số
def get_server_weighted_response_time():
    candidates = get_available_servers()
    if not candidates: return None
    def calculate_score(server):
        if server["avg_response_time"] == 0: return 9999
        return server["weight"] / server["avg_response_time"]
    return max(candidates, key=calculate_score)
 
# 4. Peak EWMA (Mới) - Nhạy cảm với độ trễ tăng đột biến
def get_server_peak_ewma():
    candidates = get_available_servers()
    if not candidates: return None
    def ewma_score(s):
        # Score = (Kết nối đang xử lý + 1) * Độ trễ EWMA
        val = s.get('ewma_response_time', 0.1)
        if val == 0: val = 0.1
        return (s['active_conns'] + 1) * val
    return min(candidates, key=ewma_score)
 
# 5. Power of Two Choices (Mới) - Chọn ngẫu nhiên 2, lấy 1 tốt hơn
def get_server_p2c():
    candidates = get_available_servers()
    if not candidates: return None
    if len(candidates) < 2: return candidates[0]
   
    # Chọn ngẫu nhiên 2 ứng viên
    c1, c2 = random.sample(candidates, 2)
    # So sánh dựa trên số kết nối (tránh hiệu ứng đám đông)
    return c1 if c1['active_conns'] < c2['active_conns'] else c2
 
# 6. Adaptive Resource Awareness (Mới) - Dựa trên CPU thực tế
def get_server_adaptive():
    candidates = get_available_servers()
    if not candidates: return None
    def resource_score(s):
        # Công thức: (CPU * 0.7) + (Connections * 0.3)
        cpu_score = s['cpu_usage']
        conn_score = s['active_conns'] * 5 # Quy đổi 1 conn ~ 5 điểm
        return (cpu_score * 0.7) + (conn_score * 0.3)
    return min(candidates, key=resource_score)
 
# --- ROUTER CHÍNH ---
@app.route('/')
def router():
    global TOTAL_REQUESTS, CACHE_HITS
    TOTAL_REQUESTS += 1
    request_key = "simulation_data"
   
    # --- 1. XỬ LÝ CACHE ---
    if request_key in RESPONSE_CACHE:
        if random.random() < CACHE_PROBABILITY:
            CACHE_HITS += 1
            cached_data = RESPONSE_CACHE[request_key].copy()
            cached_data["status"] = "served_from_cache_lucky"
            cached_data["cpu_usage"] = 0
            return jsonify(cached_data)
 
    # --- 2. CHỌN SERVER DỰA TRÊN THUẬT TOÁN ---
    target = None
   
    if CURRENT_ALGORITHM == 'round_robin':
        target = get_server_round_robin()
    elif CURRENT_ALGORITHM == 'least_connection':
        target = get_server_least_connection()
    elif CURRENT_ALGORITHM == 'weighted_response_time':
        target = get_server_weighted_response_time()
    elif CURRENT_ALGORITHM == 'peak_ewma':
        target = get_server_peak_ewma()
    elif CURRENT_ALGORITHM == 'p2c':
        target = get_server_p2c()
    elif CURRENT_ALGORITHM == 'adaptive':
        target = get_server_adaptive()
    else:
        # Fallback an toàn
        target = get_server_round_robin()
 
    # Nếu không tìm thấy server nào (Tất cả đều tắt hoặc crash)
    if target is None:
        return jsonify({
            "error": "System Overload! All servers are down.",
            "status": "system_failure"
        }), 503
 
    # --- 3. GỬI REQUEST ---
    target["active_conns"] += 1
    start_time = time.time()
   
    try:
        # [QUAN TRỌNG] Truyền tham số duration xuống backend và Timeout dài
        forward_params = request.args
        resp = requests.get(target["url"], params=forward_params, timeout=30)
       
        if resp.status_code == 200:
            data = resp.json()
            target["total_handled"] += 1
            target["health_status"] = "healthy" # Đánh dấu sống lại
            if "cpu_usage" in data: target["cpu_usage"] = data["cpu_usage"]
            RESPONSE_CACHE[request_key] = data
            return jsonify(data)
 
        elif resp.status_code == 503:
            # Server báo crash chủ động
            data = resp.json()
            target["health_status"] = "crashed"
            target["last_crash_time"] = time.time()
            target["cpu_usage"] = 100
            return jsonify(resp.json()), 503
           
        else:
             # Các lỗi khác (404, 500...)
            return jsonify(resp.json()), resp.status_code
 
    except Exception as e:
        # Lỗi kết nối mạng (Timeout/Refused) -> Đánh dấu CRASH ngay
        print(f"⚠️ {target['name']} died unexpectedly: {e}")
        target["health_status"] = "crashed"
        target["last_crash_time"] = time.time()
        target["cpu_usage"] = 0
        return jsonify({"error": "Connection failed"}), 502
 
    finally:
        target["active_conns"] -= 1
        latency = time.time() - start_time
       
        # Chỉ cập nhật chỉ số thống kê nếu server khỏe
        if target.get('health_status') == 'healthy':
            # Cập nhật Moving Average (cho Weighted RT)
            target["avg_response_time"] = (target["avg_response_time"] * 0.9) + (latency * 0.1)
           
            # Cập nhật Peak EWMA (cho thuật toán mới)
            if latency > target.get("ewma_response_time", 0):
                target["ewma_response_time"] = latency
            else:
                old_ewma = target.get("ewma_response_time", 0.1)
                target["ewma_response_time"] = (old_ewma * (1 - EWMA_DECAY)) + (latency * EWMA_DECAY)
 
# --- API STATS & CONFIG ---
@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        "algorithm": CURRENT_ALGORITHM,
        "cache_probability": CACHE_PROBABILITY,
        "total_requests": TOTAL_REQUESTS,
        "cache_hits": CACHE_HITS,
        "current_cost_per_hour": calculate_current_cost(),
        "servers": SERVERS
    })
 
@app.route('/config', methods=['POST'])
def update_config():
    global CURRENT_ALGORITHM, CACHE_PROBABILITY
    data = request.json
    if 'algorithm' in data: CURRENT_ALGORITHM = data['algorithm']
    if 'cache_probability' in data: CACHE_PROBABILITY = float(data['cache_probability']) / 100.0
    return jsonify({"status": "updated"})
 
@app.route('/toggle_server', methods=['POST'])
def toggle_server():
    data = request.json
    server_name = data.get('name')
    action = data.get('action')
    for s in SERVERS:
        if s['name'] == server_name:
            s['active'] = (action == 'on')
            if not s['active']:
                s['active_conns'] = 0
                s['cpu_usage'] = 0
                s['health_status'] = 'healthy'
            return jsonify({"status": "success"})
    return jsonify({"error": "not found"}), 404
 
if __name__ == "__main__":
    app.run(port=8000)