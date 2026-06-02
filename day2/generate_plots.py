"""
generate_plots.py
Simulates Drain3 log parsing and generates all required plots for SUBMIT.md
Run: python generate_plots.py
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import re, random, os, json

random.seed(42)
np.random.seed(42)
os.makedirs("images", exist_ok=True)

# ─────────────────────────────────────────────
# 1.  DRAIN3 SIMULATOR  (không cần cài drain3)
# ─────────────────────────────────────────────
class DrainNode:
    def __init__(self):
        self.children = {}   # token -> DrainNode
        self.templates = []  # list of (template_tokens, count)

WILDCARD = "<*>"

class DrainSimulator:
    """Lightweight Drain-3 clone for demo purposes."""
    def __init__(self, depth=4, sim_th=0.5, max_children=100):
        self.depth = depth
        self.sim_th = sim_th
        self.max_children = max_children
        self.root = {}          # length -> {first_token -> [templates]}
        self.template_counts = Counter()
        self.template_map = {}   # id -> template_str
        self.template_id = 0
        self.new_template_events = []  # (timestamp, template)
        self.parse_log_full = []

    def _tokenize(self, line):
        return re.sub(r'[\d]+', '<NUM>', line).split()

    def _similarity(self, tokens, template):
        if len(tokens) != len(template):
            return 0.0
        match = sum(1 for t, p in zip(tokens, template) if t == p or p == WILDCARD)
        return match / len(template)

    def _merge(self, tokens, template):
        return [t if t == p else WILDCARD for t, p in zip(tokens, template)]

    def parse(self, line, timestamp=None):
        tokens = self._tokenize(line)
        length = len(tokens)
        if length == 0:
            return None

        # Navigate tree: length → first_token
        key = (length, tokens[0] if tokens else "")
        if key not in self.root:
            self.root[key] = []

        bucket = self.root[key]
        best_sim, best_idx = 0, -1
        for i, (tmpl, _) in enumerate(bucket):
            s = self._similarity(tokens, tmpl)
            if s > best_sim:
                best_sim, best_idx = s, i

        if best_sim >= self.sim_th and best_idx >= 0:
            old_tmpl, cnt = bucket[best_idx]
            new_tmpl = self._merge(tokens, old_tmpl)
            bucket[best_idx] = (new_tmpl, cnt + 1)
            tmpl_str = " ".join(new_tmpl)
            self.template_counts[tmpl_str] += 1
            result = ("existing", tmpl_str)
        else:
            new_tmpl = tokens[:]
            bucket.append((new_tmpl, 1))
            tmpl_str = " ".join(new_tmpl)
            self.template_counts[tmpl_str] = 1
            self.template_id += 1
            tid = f"T{self.template_id:03d}"
            self.template_map[tid] = tmpl_str
            if timestamp:
                self.new_template_events.append((timestamp, tmpl_str))
            result = ("new", tmpl_str)

        self.parse_log_full.append({
            "timestamp": timestamp,
            "line": line,
            "template": tmpl_str,
            "status": result[0]
        })
        return result

    def get_all_templates(self):
        templates = []
        for (length, first), bucket in self.root.items():
            for tmpl, cnt in bucket:
                templates.append((" ".join(tmpl), cnt))
        return sorted(templates, key=lambda x: -x[1])

# ─────────────────────────────────────────────
# 2.  GENERATE SYNTHETIC LOGS
# ─────────────────────────────────────────────
def generate_logs(n_hours=24, logs_per_min=10):
    base_time = datetime(2026, 6, 2, 0, 0, 0)
    logs = []
    templates_pool = [
        "User {user} logged in from {ip}",
        "Request {method} {path} completed in {ms}ms status {code}",
        "Connection established to {host}:{port}",
        "Database query executed in {ms}ms rows={n}",
        "Cache miss for key {key}",
        "Cache hit for key {key}",
        "Scheduler job {job} started",
        "Scheduler job {job} completed in {sec}s",
        "Memory usage {pct}% threshold {thr}%",
        "CPU load {pct}% on core {core}",
    ]
    # Anomaly templates (injected at hours 14-16)
    anomaly_templates = [
        "ERROR disk write failed on /dev/sd{x} errno={n}",
        "CRITICAL out of memory killing process {pid}",
        "ERROR connection refused to {host}:{port} retry={n}",
        "WARN slow query {ms}ms exceeds threshold {thr}ms",
    ]

    users   = ["alice","bob","carol","dave"]
    ips     = ["10.0.0.{}".format(i) for i in range(1,20)]
    methods = ["GET","POST","PUT","DELETE"]
    paths   = ["/api/v1/users","/api/v1/orders","/health","/metrics"]

    def fill(tmpl):
        return (tmpl
            .replace("{user}", random.choice(users))
            .replace("{ip}",   random.choice(ips))
            .replace("{method}", random.choice(methods))
            .replace("{path}", random.choice(paths))
            .replace("{ms}",   str(random.randint(5, 500)))
            .replace("{code}",  str(random.choice([200,200,200,404,500])))
            .replace("{host}",  f"db{random.randint(1,3)}.internal")
            .replace("{port}",  str(random.randint(3000,9000)))
            .replace("{n}",    str(random.randint(1,1000)))
            .replace("{key}",  f"cache:{random.randint(1,100)}")
            .replace("{job}",  f"job_{random.randint(1,10)}")
            .replace("{sec}",  str(random.randint(1,60)))
            .replace("{pct}",  str(random.randint(30,95)))
            .replace("{thr}",  str(random.randint(80,95)))
            .replace("{core}", str(random.randint(0,7)))
            .replace("{x}",   random.choice(list("abcd")))
            .replace("{pid}", str(random.randint(1000,9999)))
        )

    for minute in range(n_hours * 60):
        ts = base_time + timedelta(minutes=minute)
        hour = ts.hour
        # Inject anomaly burst at hours 14-15
        is_anomaly_window = (14 <= hour < 16)
        count = logs_per_min * (5 if is_anomaly_window else 1)
        count += random.randint(-2, 2)
        pool = anomaly_templates if is_anomaly_window else templates_pool
        for _ in range(max(1, count)):
            tmpl = random.choice(pool)
            logs.append((ts, fill(tmpl)))

    return logs

# ─────────────────────────────────────────────
# 3.  RUN DRAIN SIMULATION + TUNING
# ─────────────────────────────────────────────
print("🔧 Generating synthetic logs ...")
logs = generate_logs(n_hours=24, logs_per_min=8)
print(f"   Total logs: {len(logs):,}")

# Main parse run
drain = DrainSimulator(sim_th=0.5)
for ts, line in logs:
    drain.parse(line, timestamp=ts)

all_templates = drain.get_all_templates()
print(f"\n📋 Drain3 Output:")
print(f"   Total templates discovered: {len(all_templates)}")
print(f"\n   Top-10 templates by count:")
for i, (tmpl, cnt) in enumerate(all_templates[:10], 1):
    display = tmpl if len(tmpl) <= 70 else tmpl[:67] + "..."
    print(f"   {i:2d}. [{cnt:5d}] {display}")

# Tuning log: different sim_th values
print(f"\n🔩 Tuning Log (sim_th sweep):")
tuning_results = []
for sim_th in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    d = DrainSimulator(sim_th=sim_th)
    for ts, line in logs:
        d.parse(line, timestamp=ts)
    n_tmpl = len(d.get_all_templates())
    tuning_results.append({"sim_th": sim_th, "n_templates": n_tmpl})
    print(f"   sim_th={sim_th:.1f} → {n_tmpl:3d} templates")

# ─────────────────────────────────────────────
# 4.  BUILD TEMPLATE COUNT TIME SERIES
# ─────────────────────────────────────────────
df_parsed = pd.DataFrame(drain.parse_log_full)
df_parsed['timestamp'] = pd.to_datetime(df_parsed['timestamp'])
df_parsed.set_index('timestamp', inplace=True)

# Resample: count per 5-minute window per template
df_parsed['count'] = 1
top5_templates = [t for t, _ in all_templates[:5]]

# Total log volume time series
total_ts = df_parsed['count'].resample('5min').sum().fillna(0)
new_tmpl_ts = df_parsed[df_parsed['status']=='new']['count'].resample('5min').sum().fillna(0)

# Per-template time series (top 3)
template_ts = {}
for tmpl in top5_templates[:3]:
    sub = df_parsed[df_parsed['template'] == tmpl]['count'].resample('5min').sum().fillna(0)
    template_ts[tmpl] = sub

# Anomaly detection: simple 3-sigma on total_ts
mean_ts = total_ts.mean()
std_ts  = total_ts.std()
upper_thr = mean_ts + 3 * std_ts
anomaly_mask = total_ts > upper_thr

# ─────────────────────────────────────────────
# 5.  PLOT 1 — TEMPLATE COUNT TIME SERIES (main required plot)
# ─────────────────────────────────────────────
print("\n📊 Generating plots ...")

fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
fig.suptitle('Drain3 Log Parsing — Template Count Time Series & Anomaly Detection',
             fontsize=14, fontweight='bold', y=0.98)

# ── Plot A: Total log volume with anomaly highlighted ──
ax = axes[0]
ax.plot(total_ts.index, total_ts.values, color='#3498DB', linewidth=1.2, alpha=0.85, label='Log volume (5-min)')
ax.fill_between(total_ts.index, total_ts.values, alpha=0.15, color='#3498DB')
ax.axhline(upper_thr, color='#E74C3C', linestyle='--', linewidth=2, label=f'3σ threshold ({upper_thr:.0f})')
ax.fill_between(total_ts.index, total_ts.values, upper_thr,
                where=anomaly_mask, color='#E74C3C', alpha=0.4, label='Anomaly zone')
# Mark anomaly points
ax.scatter(total_ts.index[anomaly_mask], total_ts.values[anomaly_mask],
           color='#E74C3C', s=60, zorder=5, label=f'Anomaly detected ({anomaly_mask.sum()})')
ax.set_ylabel('Log Count / 5 min', fontsize=11)
ax.set_title('A) Total Log Volume — Anomaly Highlighted (3σ)', fontweight='bold')
ax.legend(fontsize=9, loc='upper left'); ax.grid(True, alpha=0.3)
ax.set_facecolor('#F8F9FA')

# ── Plot B: Per-template time series ──
ax2 = axes[1]
colors_t = ['#2ECC71', '#9B59B6', '#F39C12']
for (tmpl, ts_data), color in zip(template_ts.items(), colors_t):
    short_label = tmpl[:50] + '...' if len(tmpl) > 50 else tmpl
    ax2.plot(ts_data.index, ts_data.values, color=color, linewidth=1.3,
             alpha=0.8, label=short_label)
ax2.set_ylabel('Count / 5 min', fontsize=11)
ax2.set_title('B) Top-3 Template Count Time Series', fontweight='bold')
ax2.legend(fontsize=7, loc='upper left'); ax2.grid(True, alpha=0.3)
ax2.set_facecolor('#F8F9FA')

# ── Plot C: New template detection ──
ax3 = axes[2]
ax3.bar(new_tmpl_ts.index, new_tmpl_ts.values, width=0.003, color='#E67E22', alpha=0.8,
        label='New templates per window')
ax3.fill_between(new_tmpl_ts.index, new_tmpl_ts.values, alpha=0.3, color='#E67E22')
# Highlight windows with new templates during anomaly
new_during_anomaly = new_tmpl_ts[new_tmpl_ts > 0]
if len(new_during_anomaly):
    ax3.scatter(new_during_anomaly.index, new_during_anomaly.values,
                color='red', s=80, zorder=5, label=f'New template events ({len(new_during_anomaly)})')
ax3.set_ylabel('New Templates', fontsize=11)
ax3.set_xlabel('Time', fontsize=11)
ax3.set_title('C) New Template Detection — Signal for Unknown Anomalies', fontweight='bold')
ax3.legend(fontsize=9, loc='upper left'); ax3.grid(True, alpha=0.3)
ax3.set_facecolor('#F8F9FA')

plt.tight_layout()
out1 = 'day2/images/plot_template_timeseries.png'
plt.savefig(out1, dpi=130, bbox_inches='tight')
plt.close()
print(f"   ✅ Saved: {out1}")

# ─────────────────────────────────────────────
# 6.  PLOT 2 — TOP-10 TEMPLATES BAR CHART
# ─────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(13, 7))
top10 = all_templates[:10]
labels = [t[:55]+'…' if len(t)>55 else t for t,_ in top10]
counts = [c for _,c in top10]
colors_bar = plt.cm.viridis(np.linspace(0.2, 0.85, len(top10)))

bars = ax.barh(range(len(top10)), counts, color=colors_bar, edgecolor='white', linewidth=0.5)
ax.set_yticks(range(len(top10)))
ax.set_yticklabels(labels, fontsize=8.5)
ax.invert_yaxis()
ax.set_xlabel('Log Count', fontsize=12)
ax.set_title('Drain3 — Top-10 Templates by Frequency', fontsize=13, fontweight='bold')
for bar, cnt in zip(bars, counts):
    ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height()/2,
            f'{cnt:,}', va='center', fontsize=9)
ax.grid(True, alpha=0.3, axis='x')
ax.set_facecolor('#F8F9FA')
plt.tight_layout()
out2 = 'day2/images/plot_top10_templates.png'
plt.savefig(out2, dpi=130, bbox_inches='tight')
plt.close()
print(f"   ✅ Saved: {out2}")

# ─────────────────────────────────────────────
# 7.  PLOT 3 — TUNING LOG: sim_th vs template count
# ─────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
df_tune = pd.DataFrame(tuning_results)
ax.plot(df_tune['sim_th'], df_tune['n_templates'], 'o-', color='#9B59B6',
        linewidth=2.5, markersize=9, markerfacecolor='white', markeredgewidth=2.5)
for _, row in df_tune.iterrows():
    ax.annotate(f"{int(row['n_templates'])} templates",
                (row['sim_th'], row['n_templates']),
                textcoords='offset points', xytext=(0, 12),
                ha='center', fontsize=9, color='#6C3483')
ax.axvline(0.5, color='#E74C3C', linestyle='--', linewidth=2, label='Selected: sim_th=0.5')
ax.set_xlabel('sim_th (similarity threshold)', fontsize=12)
ax.set_ylabel('Number of Templates', fontsize=12)
ax.set_title('Drain3 Tuning — sim_th vs Template Count', fontsize=13, fontweight='bold')
ax.legend(fontsize=10); ax.grid(True, alpha=0.4)
ax.set_facecolor('#F8F9FA')
plt.tight_layout()
out3 = 'day2/images/plot_tuning_simth.png'
plt.savefig(out3, dpi=130, bbox_inches='tight')
plt.close()
print(f"   ✅ Saved: {out3}")

# ─────────────────────────────────────────────
# 8.  SAVE DRAIN LOG OUTPUT TO JSON (for SUBMIT.md)
# ─────────────────────────────────────────────
drain_output = {
    "total_logs_parsed": len(logs),
    "total_templates": len(all_templates),
    "new_template_events": len(drain.new_template_events),
    "anomaly_windows_detected": int(anomaly_mask.sum()),
    "top10_templates": [{"rank": i+1, "template": t, "count": c}
                        for i, (t,c) in enumerate(all_templates[:10])],
    "tuning_log": tuning_results,
    "selected_sim_th": 0.5
}
with open('day2/images/drain_output.json', 'w') as f:
    json.dump(drain_output, f, indent=2)
print(f"   ✅ Saved: day2/images/drain_output.json")

print("\n✅ All plots generated successfully!")
print(f"   → {out1}")
print(f"   → {out2}")
print(f"   → {out3}")
