"""Generate training progress PNG from training_history.json."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Set a readable font that supports Chinese characters when available
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data" / "gold" / "feature_store"

hist_path = DATA_DIR / "training_history.json"
meta_path = DATA_DIR / "optimized_params_meta.json"

with open(hist_path, encoding="utf-8") as f:
    hist = json.load(f)

meta = {}
if meta_path.exists():
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

history = hist["history"]
baseline_sp = hist.get("baseline_spearman", None)
best_sp = hist.get("best_spearman", None)
best_ps = hist.get("best_pearson", None)

# Aggregate per-step: best spearman/pearson across population up to each step
steps = sorted(set(int(h["step"]) for h in history))
step_best_sp = {}
step_best_ps = {}
for h in history:
    s = int(h["step"])
    sp = float(h["spearman"])
    ps = float(h["pearson"])
    if s not in step_best_sp or sp > step_best_sp[s]:
        step_best_sp[s] = sp
    if s not in step_best_ps or ps > step_best_ps[s]:
        step_best_ps[s] = ps

best_sp_curve = [step_best_sp[s] for s in steps]
best_ps_curve = [step_best_ps[s] for s in steps]

# Aggregate loss: best (lowest) loss per step
step_best_loss = {}
for h in history:
    s = int(h["step"])
    lv = float(h["loss"])
    if s not in step_best_loss or lv < step_best_loss[s]:
        step_best_loss[s] = lv
loss_curve = [step_best_loss[s] for s in steps]

fig, axes = plt.subplots(1, 3, figsize=(18, 5), dpi=120)

# 1. Spearman
ax = axes[0]
ax.plot(steps, best_sp_curve, color="#1f77b4", linewidth=2, label="Optimized (best per step)")
if baseline_sp is not None:
    ax.axhline(baseline_sp, color="#ff7f0e", linestyle="--", linewidth=1.5,
               label=f"Baseline v3 ({baseline_sp:.4f})")
ax.set_xlabel("Training Step")
ax.set_ylabel("Spearman (train)")
ax.set_title("Spearman Correlation vs Training Step")
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right")
if best_sp is not None:
    ax.axhline(best_sp, color="#2ca02c", linestyle=":", linewidth=1,
               label=f"Final best ({best_sp:.4f})")
    ax.legend(loc="lower right")

# 2. Pearson
ax = axes[1]
ax.plot(steps, best_ps_curve, color="#1f77b4", linewidth=2, label="Optimized (best per step)")
ax.set_xlabel("Training Step")
ax.set_ylabel("Pearson (train)")
ax.set_title("Pearson Correlation vs Training Step")
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right")

# 3. Loss
ax = axes[2]
ax.plot(steps, loss_curve, color="#d62728", linewidth=2, label="Composite Loss (best per step)")
ax.set_xlabel("Training Step")
ax.set_ylabel("Loss")
ax.set_title("Composite Loss vs Training Step")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper right")

# Summary text
lines = []
lines.append(f"Best train Spearman: {best_sp:.4f}" if best_sp is not None else "Best train Spearman: N/A")
lines.append(f"Best train Pearson: {best_ps:.4f}" if best_ps is not None else "Best train Pearson: N/A")
lines.append(f"Baseline v3 Spearman: {baseline_sp:.4f}" if baseline_sp is not None else "Baseline v3 Spearman: N/A")

# Holdout metrics from meta
holdout = None
if isinstance(meta, dict):
    hd = meta.get("holdout_test") or meta.get("metrics_holdout") or meta.get("holdout")
    if isinstance(hd, dict):
        holdout = hd
    elif isinstance(meta.get("metrics"), dict):
        m = meta["metrics"]
        hd = m.get("holdout_test") or m.get("metrics_holdout") or m.get("holdout")
        if isinstance(hd, dict):
            holdout = hd

if holdout is not None:
    ho_sp = holdout.get("spearman") or holdout.get("optimized_spearman")
    ho_ps = holdout.get("pearson") or holdout.get("optimized_pearson")
    ho_n = holdout.get("n_team_seasons") or holdout.get("n_teams")
    if ho_sp is not None:
        lines.append(f"Holdout Spearman: {float(ho_sp):.4f}")
    if ho_ps is not None:
        lines.append(f"Holdout Pearson: {float(ho_ps):.4f}")
    if ho_n is not None:
        lines.append(f"Holdout teams: {int(ho_n)}")

fig.suptitle("GPU Rating Optimizer — Training Progress", fontsize=14, fontweight="bold")

# Put summary text as footer
fig.text(0.01, 0.01, "   |   ".join(lines), fontsize=10, color="#333333")

plt.tight_layout(rect=(0, 0.04, 1, 1))
out_path = DATA_DIR / "training_progress.png"
plt.savefig(out_path, dpi=120, bbox_inches="tight", facecolor="white")
plt.close()
print(f"Saved: {out_path}")
