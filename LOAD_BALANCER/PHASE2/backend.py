from flask import Flask, jsonify, request
import time, threading, random, math

class ServerInstance:
    def __init__(self, port, name, profile):
        self.app = Flask(name)
        self.port = port
        self.name = name

        # === HOMOGENEOUS HARDWARE MODEL ===
        self.BASE_DELAY = 0.3
        self.A = 90
        self.k = 0.22

        # === NETWORK INSTABILITY PROFILE ===
        self.profile = profile
        self.jitter_prob = profile["jitter_prob"]
        self.spike_prob = profile["spike_prob"]
        self.micro_freeze_prob = profile["micro_freeze_prob"]

        # Spike durations
        self.SPIKE_DELAY = profile["spike_delay"]
        self.MICRO_FREEZE_DELAY = profile["micro_freeze_delay"]

        # Runtime state
        self.active_requests = 0
        self.lock = threading.Lock()

        # Crash system
        self.cpu_overload_count = 0
        self.is_crashed = False
        self.crash_start_time = 0
        self.CRASH_DURATION = 8

        self.app.add_url_rule("/", "index", self.index)

    # ==== MODELS ====

    def model_cpu(self, active):
        idle = random.uniform(3, 6)
        load_curve = self.A * (1 - math.exp(-self.k * active))
        noise = random.uniform(-2, 2)
        return max(0, min(100, idle + load_curve + noise))

    def model_delay(self, cpu):
        cpu_factor = 1 + (cpu / 85)
        jitter = random.uniform(-0.03, 0.03)
        return max(0.01, self.BASE_DELAY * cpu_factor + jitter)

    # ==== ROUTE ====

    def index(self):
        # Circuit breaker
        if self.is_crashed:
            if time.time() - self.crash_start_time < self.CRASH_DURATION:
                return jsonify({"server": self.name, "status": "crashed"}), 503
            else:
                self.is_crashed = False
                self.cpu_overload_count = 0
                print(f"♻️ {self.name} RECOVERED")

        with self.lock:
            self.active_requests += 1

        try:
            cpu = self.model_cpu(self.active_requests)
            delay = self.model_delay(cpu)

            # ===== FAILURE INJECTION ENGINE =====
            note = "normal"
            r = random.random()

            if r < self.spike_prob:
                delay = self.SPIKE_DELAY
                note = "spike"
                print(f"⚡ {self.name} latency spike")

            elif r < (self.spike_prob + self.micro_freeze_prob):
                delay = self.MICRO_FREEZE_DELAY
                note = "micro_freeze"

            elif r < (self.spike_prob + self.micro_freeze_prob + self.jitter_prob):
                delay += random.uniform(0.2, 0.5)
                note = "jitter"

            time.sleep(delay)

            # Crash logic
            if cpu > 97:
                self.cpu_overload_count += 1
            else:
                self.cpu_overload_count = 0

            if self.cpu_overload_count >= 4:
                self.is_crashed = True
                self.crash_start_time = time.time()
                print(f"💥 {self.name} CRASHED")
                return jsonify({"status": "crashed_now"}), 503

            return jsonify({
                "server": self.name,
                "status": "handled",
                "delay": round(delay, 3),
                "cpu_usage": int(cpu),
                "note": note
            })

        finally:
            with self.lock:
                self.active_requests -= 1

    def run(self):
        import logging
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        print(f"🚀 {self.name} started on :{self.port}")
        self.app.run(port=self.port, debug=False, threaded=True, use_reloader=False)


# ==== START CLUSTER ====

def start_node(port, name, profile):
    node = ServerInstance(port, name, profile)
    node.run()


if __name__ == "__main__":
    print("\n--- BACKEND CLUSTER ---")

    PROFILES = [
        {
            "name": "Server_A",
            "port": 8001,
            "jitter_prob": 0.15,
            "spike_prob": 0.15,
            "micro_freeze_prob": 0.05,
            "spike_delay": 2.5,
            "micro_freeze_delay": 1.2
        },
        {
            "name": "Server_B",
            "port": 8002,
            "jitter_prob": 0.25,
            "spike_prob": 0.05,
            "micro_freeze_prob": 0.15,
            "spike_delay": 2.0,
            "micro_freeze_delay": 1.5
        },
        {
            "name": "Server_C",
            "port": 8003,
            "jitter_prob": 0.10,
            "spike_prob": 0.10,
            "micro_freeze_prob": 0.20,
            "spike_delay": 3.0,
            "micro_freeze_delay": 1.0
        }
    ]

    threads = []
    for p in PROFILES:
        t = threading.Thread(
            target=start_node, 
            args=(p["port"], p["name"], p)
        )
        t.start()
        threads.append(t)
