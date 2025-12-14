import requests
import time
import random
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from concurrent.futures import ThreadPoolExecutor

# ============================
# --- CẤU HÌNH CHUNG ---
# ============================

LB_URL = "http://127.0.0.1:8000"
CONFIG_URL = f"{LB_URL}/config"

ALGORITHMS = [
    'round_robin',
    'least_connection',
    'weighted_response_time',
    'peak_ewma',
    'p2c',
    'adaptive'
]

WORKLOADS = ['constant', 'burst', 'heavy_tail']

TOTAL_REQUESTS_PER_ALGO = 200   # 200 request / thuật toán / workload
CONCURRENCY = 10
COOLDOWN_TIME = 5
REQUEST_TIMEOUT = 5

REPEATS = 4                     # Repeat 4 lần để tính std
WARMUP_REQUESTS = 50

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ============================
# --- HELPER FUNCTIONS ---
# ============================

def set_load_balancer_config(algo):
    requests.post(CONFIG_URL, json={
        "algorithm": algo,
        "cache_probability": 0
    })
    print(f"\n🔄 Switched to algorithm: {algo.upper()}")
    time.sleep(COOLDOWN_TIME)


def warmup():
    for _ in range(WARMUP_REQUESTS):
        try:
            requests.get(LB_URL, timeout=2)
        except:
            pass


def send_single_request(workload):
    start_time = time.time()
    params = {}

    # --- Workload shaping (client-side) ---
    if workload == "burst":
        if random.random() < 0.3:
            params["duration"] = random.choice([1, 2, 3])

    elif workload == "heavy_tail":
        if random.random() < 0.2:
            params["duration"] = random.choice([2, 4, 6])

    try:
        resp = requests.get(LB_URL, params=params, timeout=REQUEST_TIMEOUT)
        latency = (time.time() - start_time) * 1000

        data = resp.json()
        server_name = data.get('server', 'Unknown')
        status = resp.status_code

        if status == 503:
            server_name = "CRASHED"

        return {
            "latency": latency,
            "server": server_name,
            "status": status,
            "success": 1 if status == 200 else 0
        }

    except:
        return {
            "latency": REQUEST_TIMEOUT * 1000,
            "server": "TIMEOUT",
            "status": 504,
            "success": 0
        }

# ============================
# --- BENCHMARK CORE ---
# ============================

def run_benchmark():
    all_results = []

    print("🚀 BENCHMARK STARTED")
    print(f"Algorithms: {len(ALGORITHMS)} | Workloads: {WORKLOADS}")
    print(f"Requests: {TOTAL_REQUESTS_PER_ALGO} | Concurrency: {CONCURRENCY}")
    print(f"Repeats: {REPEATS}")

    try:
        requests.get(LB_URL)
    except:
        print("❌ Cannot connect to Load Balancer.")
        return None

    for algo in ALGORITHMS:
        set_load_balancer_config(algo)
        warmup()

        for workload in WORKLOADS:
            for run in range(1, REPEATS + 1):
                print(f"▶ Algo={algo} | Workload={workload} | Run={run}")

                with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
                    futures = [
                        executor.submit(send_single_request, workload)
                        for _ in range(TOTAL_REQUESTS_PER_ALGO)
                    ]
                    results = [f.result() for f in futures]

                for r in results:
                    r.update({
                        "algorithm": algo,
                        "workload": workload,
                        "run": run
                    })

                all_results.extend(results)

    return pd.DataFrame(all_results)

# ============================
# --- VISUALIZATION ---
# ============================

def visualize_results(df):
    print("\n🎨 Generating charts...")
    sns.set_theme(style="whitegrid")

    df_clean = df[df['server'] != 'TIMEOUT']

    # --- Box Plot ---
    plt.figure(figsize=(12, 6))
    sns.boxplot(
        x="algorithm",
        y="latency",
        hue="workload",
        data=df_clean,
        showfliers=False
    )
    plt.title("Latency Stability (Box Plot)")
    plt.ylabel("Latency (ms)")
    plt.xlabel("Algorithm")
    plt.tight_layout()
    plt.savefig("chart_1_latency_box.png", dpi=300)
    plt.close()

    # --- P95 Latency ---
    p95_data = (
        df.groupby(["algorithm", "workload"])["latency"]
        .quantile(0.95)
        .reset_index()
    )

    plt.figure(figsize=(12, 6))
    sns.barplot(
        x="latency",
        y="algorithm",
        hue="workload",
        data=p95_data
    )
    plt.title("P95 Latency (Tail Latency)")
    plt.xlabel("Latency (ms)")
    plt.ylabel("Algorithm")
    plt.tight_layout()
    plt.savefig("chart_2_p95_latency.png", dpi=300)
    plt.close()

    # --- Load Distribution ---
    df_success = df[df['status'] == 200]
    ct = pd.crosstab(
        [df_success['algorithm'], df_success['workload']],
        df_success['server']
    )

    ct.plot(kind='bar', stacked=True, figsize=(14, 6))
    plt.title("Load Distribution Across Backends")
    plt.ylabel("Number of Requests")
    plt.xlabel("Algorithm / Workload")
    plt.tight_layout()
    plt.savefig("chart_3_load_distribution.png", dpi=300)
    plt.close()

# ============================
# --- MAIN ---
# ============================

if __name__ == "__main__":
    df = run_benchmark()

    if df is not None:
        visualize_results(df)

        df.to_csv("benchmark_data.csv", index=False)
        print("✅ Saved: benchmark_data.csv")
