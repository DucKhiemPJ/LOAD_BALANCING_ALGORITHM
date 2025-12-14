import requests
import time
import random
import statistics
import pandas as pd
from concurrent.futures import ThreadPoolExecutor


LB_URL = "http://127.0.0.1:8000"
CONFIG_URL = f"{LB_URL}/config"

ALGORITHMS = [
    "round_robin",
    "least_connection",
    "weighted_response_time",
    "peak_ewma",
    "p2c",
    "adaptive"
]

REQUEST_TIMEOUT = 5
CONCURRENCY = 10

# Benchmark rigor
TOTAL_REQUESTS = 200
REPEATS = 5
WARMUP_REQUESTS = 50
COOLDOWN = 5

# Reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Workload profiles
WORKLOADS = ["constant", "burst", "heavy_tail"]

# ============================
# Helper functions
# ============================

def set_algorithm(algo):
    requests.post(CONFIG_URL, json={"algorithm": algo, "cache_probability": 0})
    time.sleep(COOLDOWN)

def send_request(req_id, workload):
    start = time.time()

    # Workload shaping
    params = {}
    if workload == "burst" and random.random() < 0.3:
        params["duration"] = random.choice([1, 2, 3])
    elif workload == "heavy_tail":
        if random.random() < 0.2:
            params["duration"] = random.choice([2, 4, 6])

    try:
        r = requests.get(LB_URL, params=params, timeout=REQUEST_TIMEOUT)
        latency = (time.time() - start) * 1000
        data = r.json()
        return {
            "latency": latency,
            "status": r.status_code,
            "server": data.get("server", "unknown"),
            "success": 1 if r.status_code == 200 else 0
        }
    except:
        return {
            "latency": REQUEST_TIMEOUT * 1000,
            "status": 504,
            "server": "timeout",
            "success": 0
        }


def warmup():
    for _ in range(WARMUP_REQUESTS):
        try:
            requests.get(LB_URL, timeout=2)
        except:
            pass

def run_single_experiment(algo, workload, run_id):
    set_algorithm(algo)
    warmup()

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [
            executor.submit(send_request, i, workload)
            for i in range(TOTAL_REQUESTS)
        ]

        results = [f.result() for f in futures]

    for r in results:
        r["algorithm"] = algo
        r["workload"] = workload
        r["run_id"] = run_id

    return results

def run_benchmark():
    all_results = []

    for algo in ALGORITHMS:
        for workload in WORKLOADS:
            for run in range(1, REPEATS + 1):
                print(f"▶ Algo={algo} | Workload={workload} | Run={run}")
                batch = run_single_experiment(algo, workload, run)
                all_results.extend(batch)

    return pd.DataFrame(all_results)

# ============================
# Statistical analysis
# ============================

def analyze(df):
    summary = (
        df.groupby(["algorithm", "workload"])
        .agg(
            avg_latency=("latency", "mean"),
            std_latency=("latency", "std"),
            p95_latency=("latency", lambda x: x.quantile(0.95)),
            success_rate=("success", "mean")
        )
        .reset_index()
    )

    summary["success_rate"] *= 100
    return summary

# ============================
# Main
# ============================

if __name__ == "__main__":
    print("=== JOURNAL-GRADE BENCHMARK STARTED ===")
    df = run_benchmark()
    summary = analyze(df)

    df.to_csv("raw_results.csv", index=False)
    summary.to_csv("summary_results.csv", index=False)

    print("\n=== SUMMARY (Mean ± Std) ===")
    print(summary)
    print("\n✅ Saved: raw_results.csv")
    print("✅ Saved: summary_results.csv")
