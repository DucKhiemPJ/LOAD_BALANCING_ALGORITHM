from flask import Flask, jsonify
import time, threading, random, math

class ServerInstance:
    def __init__(self, port, base_delay, name, A, k):
        self.app = Flask(name)
        self.port = port
        self.base_delay = base_delay
        self.name = name
        
        # CPU model parameters
        self.A = A
        self.k = k
        
        # State tracking
        self.active_requests = 0
        self.lock = threading.Lock()

        # Crash system
        self.cpu_overload_count = 0
        self.is_crashed = False
        self.crash_start_time = 0
        self.CRASH_DURATION = 10

        self.app.add_url_rule("/", "index", self.index)

    def model_cpu(self, active_reqs):
        """Non-linear real-world CPU saturation model"""
        idle_cpu = random.uniform(2, 5)  
        load_curve = self.A * (1 - math.exp(-self.k * active_reqs))
        noise = random.uniform(-3, 3)
        cpu = idle_cpu + load_curve + noise
        cpu = max(0, min(cpu, 100))
        return cpu

    def model_delay(self, base, cpu):
        cpu_factor = 1 + (cpu / 80)  # delay rises fast past 80%
        jitter = random.uniform(-0.05, 0.05)
        return max(0.01, base * cpu_factor + jitter)

    def index(self):
        # 🟥 Handle crash mode
        if self.is_crashed:
            elapsed = time.time() - self.crash_start_time
            if elapsed < self.CRASH_DURATION:
                return jsonify({
                    "server": self.name,
                    "port": self.port,
                    "status": "crashed",
                    "cpu_usage": 100,
                    "remaining": round(self.CRASH_DURATION - elapsed, 1),
                }), 503
            else:
                self.is_crashed = False
                self.cpu_overload_count = 0
                print(f"♻️ {self.name} RECOVERED")
        
        with self.lock:
            self.active_requests += 1
        
        try:
            # Compute CPU + delay
            cpu = self.model_cpu(self.active_requests)
            delay = self.model_delay(self.base_delay, cpu)
            time.sleep(delay)

            # Crash logic
            if cpu > 95:
                self.cpu_overload_count += 1
            else:
                self.cpu_overload_count = 0

            if self.cpu_overload_count >= 3:  # require 3 consecutive overloads
                self.is_crashed = True
                self.crash_start_time = time.time()
                print(f"💥 {self.name} CRASHED (CPU stayed >95%)")
                return jsonify({
                    "server": self.name,
                    "port": self.port,
                    "status": "crashed_now",
                    "cpu_usage": 100,
                    "delay": delay,
                }), 503

            return jsonify({
                "server": self.name,
                "port": self.port,
                "status": "handled",
                "delay": round(delay, 3),
                "cpu_usage": int(cpu),
                "active_requests": self.active_requests
            })
        
        finally:
            with self.lock:
                self.active_requests -= 1

    def run(self):
        print(f"🚀 {self.name} started on port {self.port}")
        self.app.run(port=self.port, debug=False, use_reloader=False, threaded=True)


# ---------------------- CLUSTER CONFIG ------------------------

def start_node(port, base_delay, name, A, k):
    node = ServerInstance(port, base_delay, name, A, k)
    node.run()

if __name__ == "__main__":
    print("\n--- BACKEND CLUSTER (REALISTIC MODE) ---")

    t1 = threading.Thread(target=start_node, args=(8001, 0.10, "Server_Fast", 70, 0.15))

    t2 = threading.Thread(target=start_node, args=(8002, 0.35, "Server_Medium", 90, 0.25))

    t3 = threading.Thread(target=start_node, args=(8003, 0.90, "Server_Slow", 120, 0.40))


    t1.start(); t2.start(); t3.start()
