import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# ============================
# LOAD DATA
# ============================

CSV_FILE = "benchmark_data.csv"
df = pd.read_csv(CSV_FILE)

sns.set_theme(style="whitegrid")

# Lọc timeout để biểu đồ không bị méo
df_clean = df[df["server"] != "TIMEOUT"]

# ============================
# 1. BOX PLOT – LATENCY STABILITY
# ============================

plt.figure(figsize=(14, 6))
sns.boxplot(
    x="algorithm",
    y="latency",
    hue="workload",
    data=df_clean,
    showfliers=False
)

plt.title("Latency Stability across Load Balancing Algorithms", fontsize=14, fontweight="bold")
plt.ylabel("Latency (ms)")
plt.xlabel("Algorithm")
plt.legend(title="Workload")
plt.tight_layout()
plt.savefig("chart_latency_box.png", dpi=300)
plt.close()

print("✅ Saved: chart_latency_box.png")

# ============================
# 2. P95 LATENCY – TAIL PERFORMANCE
# ============================

p95_df = (
    df.groupby(["algorithm", "workload"])["latency"]
    .quantile(0.95)
    .reset_index(name="p95_latency")
)

plt.figure(figsize=(14, 6))
sns.barplot(
    x="p95_latency",
    y="algorithm",
    hue="workload",
    data=p95_df
)

plt.title("P95 Latency (Tail Performance)", fontsize=14, fontweight="bold")
plt.xlabel("Latency (ms)")
plt.ylabel("Algorithm")
plt.legend(title="Workload")
plt.tight_layout()
plt.savefig("chart_p95_latency.png", dpi=300)
plt.close()

print("✅ Saved: chart_p95_latency.png")

# ============================
# 3. LOAD DISTRIBUTION – BACKEND AWARENESS
# ============================

df_success = df[df["status"] == 200]

load_dist = pd.crosstab(
    [df_success["algorithm"], df_success["workload"]],
    df_success["server"]
)

plt.figure(figsize=(16, 7))
load_dist.plot(
    kind="bar",
    stacked=True,
    figsize=(16, 7),
    width=0.75
)

plt.title("Load Distribution across Backend Servers", fontsize=14, fontweight="bold")
plt.ylabel("Number of Requests")
plt.xlabel("Algorithm / Workload")
plt.xticks(rotation=45, ha="right")
plt.legend(title="Backend Server", bbox_to_anchor=(1.02, 1), loc="upper left")
plt.tight_layout()
plt.savefig("chart_load_distribution.png", dpi=300)
plt.close()

print("✅ Saved: chart_load_distribution.png")
