from PyQt6.QtWidgets import QVBoxLayout, QWidget, QSizePolicy
from matplotlib import rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


rcParams["font.sans-serif"] = [
    "PingFang SC",
    "Hiragino Sans GB",
    "Heiti SC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
rcParams["axes.unicode_minus"] = False


class ChartWidget(QWidget):
    """支持深浅主题的 Matplotlib 图表组件"""

    DARK = {
        "panel": "#121c2d",
        "text": "#dbeafe",
        "muted": "#94a3b8",
        "grid": "#26364f",
        "colors": ["#60a5fa", "#34d399", "#fbbf24", "#f87171", "#a78bfa", "#22d3ee", "#fb7185", "#c084fc"],
    }
    LIGHT = {
        "panel": "#ffffff",
        "text": "#1e293b",
        "muted": "#64748b",
        "grid": "#e2e8f0",
        "colors": ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#db2777", "#9333ea"],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = True
        self.palette = self.DARK.copy()
        self._last_chart = None
        self.figure = Figure(figsize=(5, 3), dpi=110, facecolor=self.palette["panel"])
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.palette = (self.DARK if is_dark else self.LIGHT).copy()
        if self._last_chart:
            # Matplotlib drawings are not affected by Qt stylesheet changes.
            # Redraw the last chart with the new palette when the app theme flips.
            kind, args, kwargs = self._last_chart
            self._draw(kind, *args, remember=False, **kwargs)
        else:
            self.figure.set_facecolor(self.palette["panel"])
            self.canvas.draw()

    def _new_axes(self):
        self.figure.clear()
        self.figure.set_facecolor(self.palette["panel"])
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(self.palette["panel"])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(colors=self.palette["muted"], labelsize=8)
        ax.title.set_color(self.palette["text"])
        ax.xaxis.label.set_color(self.palette["muted"])
        ax.yaxis.label.set_color(self.palette["muted"])
        return ax

    def _empty(self, ax, title: str):
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=14, color=self.palette["muted"])
        if title:
            ax.set_title(title, fontsize=11, pad=12, color=self.palette["text"], weight="bold")

    def draw_pie_chart(self, data: dict, title: str = ""):
        self._draw("pie", data, title, remember=True)

    def draw_line_chart(self, x_data: list, y_data: list, title: str = "", xlabel: str = "", ylabel: str = ""):
        self._draw("line", x_data, y_data, title, xlabel, ylabel, remember=True)

    def draw_bar_chart(self, categories: list, values: list, title: str = "", color: str = ""):
        self._draw("bar", categories, values, title, color, remember=True)

    def _draw(self, kind: str, *args, remember: bool):
        if remember:
            # Store the latest draw request so set_theme() can replay it without
            # each business module having to remember chart-specific state.
            self._last_chart = (kind, args, {})
        if kind == "pie":
            self._draw_pie(*args)
        elif kind == "line":
            self._draw_line(*args)
        elif kind == "bar":
            self._draw_bar(*args)

    def _draw_pie(self, data: dict, title: str = ""):
        ax = self._new_axes()
        ax.set_aspect("equal")
        labels = list(data.keys())
        values = list(data.values())
        if not values:
            self._empty(ax, title)
        else:
            wedges, texts, autotexts = ax.pie(
                values,
                labels=labels,
                autopct="%1.0f%%",
                startangle=90,
                counterclock=False,
                colors=self.palette["colors"][: len(labels)],
                pctdistance=0.78,
                labeldistance=1.08,
                wedgeprops={"width": 0.42, "edgecolor": self.palette["panel"], "linewidth": 2},
                textprops={"fontsize": 8, "color": self.palette["muted"]},
            )
            for text in texts:
                text.set_color(self.palette["muted"])
            for text in autotexts:
                text.set_color("#f8fafc" if self.is_dark else "#ffffff")
                text.set_fontsize(8)
                text.set_weight("bold")
            ax.text(0, 0, f"¥{sum(values):.0f}", ha="center", va="center", fontsize=16, color=self.palette["text"], weight="bold")
            if title:
                ax.set_title(title, fontsize=11, pad=12, color=self.palette["text"], weight="bold")
        self.figure.subplots_adjust(left=0.06, right=0.94, top=0.86, bottom=0.08)
        self.canvas.draw()

    def _draw_line(self, x_data: list, y_data: list, title: str = "", xlabel: str = "", ylabel: str = ""):
        ax = self._new_axes()
        line_color = self.palette["colors"][0]
        if not x_data or not y_data:
            self._empty(ax, title)
        else:
            x_values = list(range(len(x_data)))
            ax.plot(x_values, y_data, color=line_color, linewidth=2.4, marker="o", markersize=5)
            ax.fill_between(x_values, y_data, min(y_data), color=line_color, alpha=0.12)
            ax.set_xticks(x_values)
            ax.set_xticklabels(x_data)
            ax.grid(True, axis="y", color=self.palette["grid"], linestyle="-", linewidth=0.8, alpha=0.9)
            ax.tick_params(axis="x", rotation=25)
            if title:
                ax.set_title(title, fontsize=11, pad=12, color=self.palette["text"], weight="bold")
            if xlabel:
                ax.set_xlabel(xlabel, fontsize=9)
            if ylabel:
                ax.set_ylabel(ylabel, fontsize=9)
        self.figure.tight_layout(pad=1.2)
        self.canvas.draw()

    def _draw_bar(self, categories: list, values: list, title: str = "", color: str = ""):
        ax = self._new_axes()
        bar_color = color or self.palette["colors"][1]
        if not categories or not values:
            self._empty(ax, title)
        else:
            bars = ax.bar(categories, values, color=bar_color, alpha=0.86, width=0.58)
            ax.grid(True, axis="y", color=self.palette["grid"], linestyle="-", linewidth=0.8, alpha=0.9)
            ax.tick_params(axis="x", rotation=20)
            top = max(values) if values else 0
            ax.set_ylim(0, top * 1.18 if top else 1)
            for bar, value in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(top * 0.03, 0.5),
                    f"{value:.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=self.palette["text"],
                    weight="bold",
                )
            if title:
                ax.set_title(title, fontsize=11, pad=12, color=self.palette["text"], weight="bold")
        self.figure.tight_layout(pad=1.2)
        self.canvas.draw()
