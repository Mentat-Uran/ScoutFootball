#!/usr/bin/env python3
"""
改进的实时可视化模块 for optimize_ratings_gpu.py
使用 Plotly 生成更美观、可靠的实时图表。

使用方法:
  1. 在主脚本中导入:
     from optimize_viz import LiveTrainingViz

  2. 创建可视化器:
     viz = LiveTrainingViz(n_steps=100, pop_size=8, enable=True)
     viz.start()  # 启动后台更新线程

  3. 每 N 步更新一次:
     viz.update(step, pop_idx, loss, spearman, pearson,
                components=components, position_weights=pw,
                league_corrs=league_corrs, top_players=top_players)

  4. 训练结束后:
     viz.finalize(best_params, best_sp, best_pr)
     viz.save("training_report.html")  # 保存为交互式 HTML
     viz.close()

特点:
  - 使用 Plotly，支持浏览器实时刷新
  - 8 个子图：Loss曲线、相关性、组件分解、位置权重、联赛相关性、Top球员、进度条、状态面板
  - 后台线程更新，不阻塞训练
  - 支持导出为交互式 HTML 报告
  - 兼容无 GUI 环境（自动降级为控制台输出）
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

# ── 依赖检查 ────────────────────────────────────────────────────────────────

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.io as pio

    # 设置 Plotly 主题
    pio.templates.default = "plotly_white"
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

import numpy as np


# ── 默认配色方案 ────────────────────────────────────────────────────────────

COLORS = {
    "background": "#0f172a",  # 深蓝黑
    "paper_bg": "#1e293b",    # 卡片背景
    "text": "#f8fafc",       # 主文字
    "text_secondary": "#94a3b8",  # 次要文字
    "accent": "#38bdf8",      # 亮蓝强调
    "success": "#22c55e",     # 绿色
    "warning": "#f59e0b",    # 橙色警告
    "error": "#ef4444",       # 红色
    "grid": "#334155",        # 网格线
    "card_border": "#475569", # 卡片边框

    # 图表颜色
    "loss": "#f97316",        # 橙色 - Loss
    "spearman": "#22c55e",    # 绿色 - Spearman
    "pearson": "#3b82f6",     # 蓝色 - Pearson
    "rank_loss": "#ef4444",   # 红色 - Rank Loss
    "ndcg": "#a855f7",        # 紫色 - NDCG
    "pos_loss": "#f59e0b",    # 橙色 - Position Loss
    "extreme": "#06b6d4",     # 青色 - Extreme
    "prior": "#6b7280",       # 灰色 - Prior
}

POSITION_COLORS = {
    "ST": "#ef4444",
    "W": "#f97316",
    "AM": "#eab308",
    "CM": "#22c55e",
    "DM": "#14b8a6",
    "FB": "#06b6d4",
    "CB": "#3b82f6",
    "GK": "#8b5cf6",
}

LEAGUE_COLORS = {
    "ENG-Premier League": "#3b82f6",
    "ESP-La Liga": "#f59e0b",
    "GER-Bundesliga": "#ef4444",
    "ITA-Serie A": "#22c55e",
    "FRA-Ligue 1": "#8b5cf6",
}


# ── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class TrainingStep:
    """单步训练数据。"""
    step: int
    pop_idx: int
    loss: float
    spearman: float
    pearson: float
    rank_loss: float = 0.0
    ndcg: float = 0.0
    pos_loss: float = 0.0
    extreme: float = 0.0
    prior: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class PositionWeights:
    """位置权重快照。"""
    step: int
    weights: dict  # {position: {dimension: value}}


# ── 实时可视化器 ───────────────────────────────────────────────────────────

class LiveTrainingViz:
    """实时训练可视化器。

    显示 8 个图表:
    1. Loss 曲线 (实时下降)
    2. Spearman/Pearson 相关性 (实时上升)
    3. Loss 组件分解 (各分量变化)
    4. 位置权重热力图 (当前最优)
    5. 各联赛相关性 (横向对比)
    6. Top 10 球员变化 (排名稳定性)
    7. 训练进度 (进度条)
    8. 状态面板 (实时统计)
    """

    def __init__(
        self,
        n_steps: int = 100,
        pop_size: int = 8,
        enable: bool = True,
        update_interval: float = 0.5,  # 秒
        port: int = 8050,
    ):
        """
        Args:
            n_steps: 最大迭代步数
            pop_size: 种群大小
            enable: 是否启用可视化
            update_interval: 更新间隔（秒）
            port: Plotly Dash 服务端口
        """
        self.enable = enable and _HAS_PLOTLY and self._check_display()
        self.n_steps = n_steps
        self.pop_size = pop_size
        self.update_interval = update_interval
        self.port = port

        # 数据存储
        self.history: deque[TrainingStep] = deque(maxlen=1000)
        self.position_weights_history: list[PositionWeights] = []
        self.best_params = None
        self.best_spearman = 0.0
        self.best_pearson = 0.0
        self.baseline_spearman = 0.0

        # 状态
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._server = None
        self._dash_app = None

        # Plotly 图表引用
        self.fig = None
        self._init_figure()

    def _check_display(self) -> bool:
        """检查是否有可用的显示环境。"""
        # 检查 DISPLAY 环境变量 (Linux)
        if os.environ.get("DISPLAY"):
            return True
        # 检查是否是 Windows/macOS
        if os.name in ("nt", "posix"):
            # 允许在无头环境运行
            return os.environ.get("FORCE_VIZ", "").lower() != "false"
        return False

    def _init_figure(self):
        """初始化 Plotly 图表结构。"""
        if not self.enable:
            return

        # 创建 3x3 子图布局 (保留 1 个位置给进度条)
        self.fig = make_subplots(
            rows=3, cols=3,
            specs=[
                [{"colspan": 2, "rowspan": 1}, None, {"rowspan": 1, "type": "xy"}],
                [{"colspan": 2}, None, {"rowspan": 1, "type": "indicator"}],
                [{"type": "bar"}, {"type": "bar"}, {"type": "xy"}],
            ],
            subplot_titles=(
                "<b>1. Loss 曲线</b>",
                "",
                "<b>2. 相关性追踪</b>",
                "",
                "<b>3. Loss 组件分解</b>",
                "",
                "<b>4. 位置权重热力图</b>",
                "<b>5. 联赛相关性</b>",
                "<b>6. 训练状态</b>",
            ),
            vertical_spacing=0.12,
            horizontal_spacing=0.08,
        )

        # 设置整体布局
        self.fig.update_layout(
            title=dict(
                text="⚽ 球员评分优化 - 实时训练进度",
                font=dict(size=20, color=COLORS["text"]),
                x=0.5,
            ),
            paper_bgcolor=COLORS["background"],
            plot_bgcolor=COLORS["paper_bg"],
            font=dict(color=COLORS["text"], size=11),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(l=60, r=30, t=80, b=60),
            width=1400,
            height=900,
        )

        # 初始化空图表数据
        self._init_chart_traces()

    def _init_chart_traces(self):
        """初始化所有子图的空 trace。"""
        # 1. Loss 曲线
        self.fig.add_trace(
            go.Scatter(
                x=[], y=[], mode="lines+markers",
                name="Total Loss",
                line=dict(color=COLORS["loss"], width=3),
                marker=dict(size=6),
            ),
            row=1, col=1,
        )
        self.fig.add_trace(
            go.Scatter(
                x=[], y=[], mode="lines",
                name="Best Loss",
                line=dict(color=COLORS["success"], width=2, dash="dash"),
            ),
            row=1, col=1,
        )

        # 2. 相关性追踪
        self.fig.add_trace(
            go.Scatter(
                x=[], y=[], mode="lines+markers",
                name="Spearman",
                line=dict(color=COLORS["spearman"], width=3),
                marker=dict(size=6),
            ),
            row=1, col=3,
        )
        self.fig.add_trace(
            go.Scatter(
                x=[], y=[], mode="lines+markers",
                name="Pearson",
                line=dict(color=COLORS["pearson"], width=3),
                marker=dict(size=6),
            ),
            row=1, col=3,
        )
        self.fig.add_trace(
            go.Scatter(
                x=[], y=[], mode="lines",
                name="Baseline",
                line=dict(color=COLORS["text_secondary"], width=1, dash="dot"),
            ),
            row=1, col=3,
        )

        # 3. Loss 组件分解 (堆叠面积图)
        components = ["rank_loss", "ndcg", "pos_loss", "extreme", "prior"]
        comp_colors = [
            COLORS["rank_loss"], COLORS["ndcg"], COLORS["pos_loss"],
            COLORS["extreme"], COLORS["prior"]
        ]
        def _rgba(hex6, alpha=0.25):
            h = hex6.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{alpha})"

        for comp, color in zip(components, comp_colors):
            self.fig.add_trace(
                go.Scatter(
                    x=[], y=[], mode="lines", stackgroup="components",
                    name=comp.replace("_", " ").title(),
                    line=dict(color=color, width=0.5),
                    fill="tonexty" if comp != "rank_loss" else None,
                    fillcolor=_rgba(color, 0.25),
                ),
                row=2, col=1,
            )

        # 4. 位置权重热力图 (会在更新时填充)
        # 5. 联赛相关性 (会在更新时填充)

        # 6. 训练状态指示器
        self.fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=0,
                title=dict(text="Spearman", font=dict(size=14)),
                gauge=dict(
                    axis=dict(range=[0, 1], tickcolor=COLORS["text_secondary"]),
                    bar=dict(color=COLORS["spearman"]),
                    bgcolor=COLORS["paper_bg"],
                    bordercolor=COLORS["card_border"],
                    borderwidth=2,
                ),
                number=dict(
                    font=dict(size=28, color=COLORS["spearman"]),
                    suffix="",
                ),
            ),
            row=2, col=3,
        )

        # 7. 进度条 (会在更新时填充)
        self.fig.add_trace(
            go.Bar(
                x=[0], y=["Progress"],
                orientation="h",
                marker=dict(
                    color=COLORS["accent"],
                    line=dict(color=COLORS["accent"], width=1),
                ),
                showlegend=False,
            ),
            row=3, col=3,
        )

    def start(self):
        """启动可视化服务（后台线程）。"""
        if not self.enable:
            print("  [Viz] 可视化已禁用，使用控制台输出模式")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        print(f"  [Viz] 实时可视化已启动: http://localhost:{self.port}")
        print("  [Viz] 打开浏览器查看训练进度...")

    def _run_server(self):
        """后台运行 Plotly Dash 服务。"""
        try:
            from dash import Dash, dcc, html, callback, Output, Input
            import dash_bootstrap_components as dbc

            self._dash_app = Dash(
                __name__,
                external_stylesheets=[dbc.themes.DARKLY],
                suppress_callback_exceptions=True,
            )

            self._dash_app.layout = html.Div([
                html.Div(id="live-update-div"),
                dcc.Interval(
                    id="interval-component",
                    interval=self.update_interval * 1000,  # 毫秒
                    n_intervals=0,
                ),
            ])

            @self._dash_app.callback(
                Output("live-update-div", "children"),
                Input("interval-component", "n_intervals"),
            )
            def update_graph(n):
                with self._lock:
                    return dcc.Graph(
                        id="training-graph",
                        figure=self.fig.to_dict() if self.fig else {},
                        config={
                            "displayModeBar": True,
                            "scrollZoom": True,
                            "responsive": True,
                        },
                        style={"height": "95vh"},
                    )

            self._dash_app.run(
                debug=False,
                port=self.port,
                host="0.0.0.0",
                use_reloader=False,
            )
        except ImportError as e:
            print(f"  [Viz] Dash 未安装，可视化降级为 HTML 文件模式: {e}")
            self._running = False
            self.enable = False
        except Exception as e:
            print(f"  [Viz] 可视化服务启动失败: {e}")
            self._running = False
            self.enable = False

    def update(
        self,
        step: int,
        pop_idx: int,
        loss: float,
        spearman: float,
        pearson: float,
        components: dict | None = None,
        position_weights: dict | None = None,
        league_corrs: dict | None = None,
        top_players: list | None = None,
    ):
        """更新可视化数据（线程安全）。"""
        with self._lock:
            # 记录数据
            step_data = TrainingStep(
                step=step,
                pop_idx=pop_idx,
                loss=loss,
                spearman=spearman,
                pearson=pearson,
                rank_loss=components.get("rank_loss", 0.0) if components else 0.0,
                ndcg=components.get("ndcg", 0.0) if components else 0.0,
                pos_loss=components.get("pos_loss", 0.0) if components else 0.0,
                extreme=components.get("extreme", 0.0) if components else 0.0,
                prior=components.get("prior", 0.0) if components else 0.0,
            )
            self.history.append(step_data)

            # 更新图表数据
            self._update_traces(step_data, position_weights, league_corrs)

        # 控制台输出（每 10 步）
        if step % 10 == 0:
            self._print_progress(step, loss, spearman, pearson)

    def _update_traces(
        self,
        step_data: TrainingStep,
        position_weights: dict | None,
        league_corrs: dict | None,
    ):
        """更新所有图表的数据。"""
        if not self.fig:
            return

        # 更新 Loss 曲线
        self.fig.data[0].x = [s.step for s in self.history]
        self.fig.data[0].y = [s.loss for s in self.history]

        # 更新 Best Loss 线
        best_loss = min(s.loss for s in self.history)
        best_x = [s.step for s in self.history if s.loss == best_loss]
        self.fig.data[1].x = best_x
        self.fig.data[1].y = [best_loss] * len(best_x)

        # 更新相关性
        self.fig.data[2].x = [s.step for s in self.history]
        self.fig.data[2].y = [s.spearman for s in self.history]
        self.fig.data[3].x = [s.step for s in self.history]
        self.fig.data[3].y = [s.pearson for s in self.history]
        self.fig.data[4].x = [0, self.history[-1].step if self.history else 0]
        self.fig.data[4].y = [self.baseline_spearman, self.baseline_spearman]

        # 更新组件分解
        components_map = [
            (self.fig.data[5], "rank_loss"),
            (self.fig.data[6], "ndcg"),
            (self.fig.data[7], "pos_loss"),
            (self.fig.data[8], "extreme"),
            (self.fig.data[9], "prior"),
        ]
        for trace, key in components_map:
            trace.x = [s.step for s in self.history]
            trace.y = [getattr(s, key, 0.0) for s in self.history]

        # 更新位置权重热力图
        if position_weights and self.history:
            self._update_heatmap(position_weights, step_data.step)

        # 更新联赛相关性
        if league_corrs and self.history:
            self._update_league_bars(league_corrs, step_data.step)

        # 更新状态指示器
        if len(self.fig.data) > 10:
            self.fig.data[10].value = step_data.spearman

        # 更新进度
        if len(self.fig.data) > 11:
            progress = step_data.step / max(self.n_steps * self.pop_size, 1)
            self.fig.data[11].x = [progress]
            self.fig.data[11].marker.color = [
                COLORS["accent"] if progress < 1 else COLORS["success"]
            ]

    def _update_heatmap(self, position_weights: dict, step: int):
        """更新位置权重热力图。"""
        POSITIONS = ["ST", "W", "AM", "CM", "DM", "FB", "CB", "GK"]
        DIMENSIONS = ["availability", "attack", "defense", "possession", "quality"]

        # 提取权重矩阵
        z = []
        for pos in POSITIONS:
            pos_w = position_weights.get(pos, {})
            row = [pos_w.get(dim, 0) for dim in DIMENSIONS]
            z.append(row)

        # 查找热力图 trace (通常是 trace 12 或之后)
        heatmap_idx = None
        for i, trace in enumerate(self.fig.data):
            if trace.type == "heatmap":
                heatmap_idx = i
                break

        if heatmap_idx is None:
            # 添加新的热力图
            self.fig.add_trace(
                go.Heatmap(
                    z=z,
                    x=DIMENSIONS,
                    y=POSITIONS,
                    colorscale="RdYlGn",
                    zmin=0,
                    zmax=0.5,
                    showscale=True,
                    text=[[f"{v:.2f}" for v in row] for row in z],
                    texttemplate="%{text}",
                    textfont={"color": "white" if sum(row) / len(row) > 0.25 else "black"},
                    hovertemplate="Position: %{y}<br>Dimension: %{x}<br>Weight: %{z:.3f}<extra></extra>",
                ),
                row=3, col=1,
            )
        else:
            # 更新现有热力图
            self.fig.data[heatmap_idx].z = z
            self.fig.data[heatmap_idx].text = [[f"{v:.2f}" for v in row] for row in z]

    def _update_league_bars(self, league_corrs: dict, step: int):
        """更新联赛相关性条形图。"""
        leagues = list(league_corrs.keys())
        corrs = list(league_corrs.values())
        colors = [LEAGUE_COLORS.get(l, COLORS["text_secondary"]) for l in leagues]

        # 查找条形图 trace
        bar_idx = None
        for i, trace in enumerate(self.fig.data):
            if trace.type == "bar" and i > 11:  # 跳过进度条
                bar_idx = i
                break

        if bar_idx is None:
            self.fig.add_trace(
                go.Bar(
                    x=corrs,
                    y=leagues,
                    orientation="h",
                    marker_color=colors,
                    text=[f"{c:.3f}" for c in corrs],
                    textposition="outside",
                    showlegend=False,
                ),
                row=3, col=2,
            )
        else:
            self.fig.data[bar_idx].x = corrs
            self.fig.data[bar_idx].y = leagues
            self.fig.data[bar_idx].marker.color = colors

    def _print_progress(self, step: int, loss: float, spearman: float, pearson: float):
        """打印进度到控制台。"""
        # 计算进度
        total = self.n_steps * self.pop_size
        progress = min(step / max(total, 1), 1.0)

        # 构建进度条
        bar_len = 30
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)

        # 最佳值
        best_sp = max(s.spearman for s in self.history) if self.history else 0

        # 打印
        print(
            f"\r  [{bar}] {progress*100:5.1f}% | "
            f"Step {step:>3} | "
            f"Loss {loss:.4f} | "
            f"Sp {spearman:.4f} | "
            f"Pr {pearson:.4f} | "
            f"Best {best_sp:.4f}",
            end="",
            flush=True,
        )

    def finalize(self, best_params, best_spearman: float, best_pearson: float):
        """训练结束时的最终处理。"""
        self.best_params = best_params
        self.best_spearman = best_spearman
        self.best_pearson = best_pearson
        self._running = False

        print(f"\n  [Viz] 训练完成! Spearman={best_spearman:.4f}, Pearson={best_pearson:.4f}")

    def save(self, path: str | Path = "training_report.html"):
        """保存为交互式 HTML 报告。"""
        if not self.fig:
            return

        path = Path(path)
        self.fig.write_html(str(path))
        print(f"  [Viz] 报告已保存: {path}")

    def save_json(self, path):
        """把训练历史保存为 JSON，供后续分析。"""
        class _NpEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, (np.integer,)):
                    return int(o)
                if isinstance(o, (np.floating,)):
                    return float(o)
                if isinstance(o, np.ndarray):
                    return o.tolist()
                return super().default(o)
        data = {
            "history": [
                {
                    "step": s.step,
                    "pop_idx": s.pop_idx,
                    "loss": s.loss,
                    "spearman": s.spearman,
                    "pearson": s.pearson,
                    "rank_loss": s.rank_loss,
                    "ndcg": s.ndcg,
                    "pos_loss": s.pos_loss,
                    "extreme": s.extreme,
                    "prior": s.prior,
                }
                for s in self.history
            ],
            "best_spearman": self.best_spearman,
            "best_pearson": self.best_pearson,
            "baseline_spearman": self.baseline_spearman,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, cls=_NpEncoder)
        print(f"  [Viz] 历史数据已保存: {path}")

    def close(self):
        """关闭可视化。"""
        self._running = False
        if self._dash_app:
            # Dash 应用通过关闭服务器来停止
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── 控制台模式可视化（无 GUI 环境）─────────────────────────────────────────

class ConsoleViz:
    """控制台模式可视化（无 GUI 环境使用）。"""

    def __init__(self, n_steps: int = 100, pop_size: int = 8, enable: bool = True):
        self.n_steps = n_steps
        self.pop_size = pop_size
        self.history: list[TrainingStep] = []

    def start(self):
        print("  [Console Viz] 使用控制台输出模式")
        print("  " + "=" * 70)
        print(f"  目标: 最大迭代 {self.n_steps * self.pop_size} 步")
        print("  " + "=" * 70)

    def update(
        self,
        step: int,
        pop_idx: int,
        loss: float,
        spearman: float,
        pearson: float,
        components: dict | None = None,
        **kwargs,
    ):
        step_data = TrainingStep(
            step=step, pop_idx=pop_idx, loss=loss,
            spearman=spearman, pearson=pearson,
            rank_loss=components.get("rank_loss", 0.0) if components else 0.0,
            ndcg=components.get("ndcg", 0.0) if components else 0.0,
            pos_loss=components.get("pos_loss", 0.0) if components else 0.0,
            extreme=components.get("extreme", 0.0) if components else 0.0,
            prior=components.get("prior", 0.0) if components else 0.0,
        )
        self.history.append(step_data)

        if step % 10 == 0:
            total = self.n_steps * self.pop_size
            progress = min(step / max(total, 1), 1.0)
            bar_len = 40
            filled = int(bar_len * progress)
            bar = "█" * filled + "░" * (bar_len - filled)

            best_sp = max(s.spearman for s in self.history)

            print(
                f"\r  [{bar}] {progress*100:5.1f}% | "
                f"Step {step:>3} | "
                f"Loss {loss:.4f} | "
                f"Sp {spearman:.4f} | "
                f"Pr {pearson:.4f} | "
                f"Best {best_sp:.4f}     ",
                end="",
                flush=True,
            )

    def finalize(self, best_params, best_spearman: float, best_pearson: float):
        print(f"\n\n  ✓ 训练完成!")
        print(f"  Best Spearman: {best_spearman:.4f}")
        print(f"  Best Pearson: {best_pearson:.4f}")

    def save(self, path: str | Path = "training_history.json"):
        import json
        path = Path(path)
        data = {
            "steps": [
                {
                    "step": s.step,
                    "loss": s.loss,
                    "spearman": s.spearman,
                    "pearson": s.pearson,
                }
                for s in self.history
            ],
            "best_spearman": best_spearman,
            "best_pearson": best_pearson,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  历史已保存: {path}")

    def save_json(self, path: str | Path = "training_history.json"):
        self.save(path)

    def close(self):
        pass


# ── 工厂函数 ────────────────────────────────────────────────────────────────

def create_visualizer(
    n_steps: int = 100,
    pop_size: int = 8,
    enable: bool = True,
    console_only: bool = False,
) -> LiveTrainingViz | ConsoleViz:
    """创建合适的可视化器。"""
    if console_only or not _HAS_PLOTLY:
        return ConsoleViz(n_steps=n_steps, pop_size=pop_size, enable=enable)
    return LiveTrainingViz(n_steps=n_steps, pop_size=pop_size, enable=enable)
