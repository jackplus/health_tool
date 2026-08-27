"""Shared chart styling. Colors follow the categorical palette's fixed slot
order (blue=slot 1, orange=slot 2) so Apple Health and Xiaomi always keep the
same identity across every chart in the app -- color follows the source, not
its rank or position."""

SOURCE_COLORS = {
    "health_auto_export": "#2f8f6b",
    "apple_health": "#2a78d6",
    "xiaomi": "#eb6834",
}
SOURCE_LABELS = {
    "health_auto_export": "Apple Health 自动同步",
    "apple_health": "Apple Health",
    "xiaomi": "小米运动健康",
}

MUTED_INK = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color="#0b0b0b"),
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis=dict(gridcolor=GRIDLINE, linecolor=BASELINE, tickfont=dict(color=MUTED_INK)),
    yaxis=dict(gridcolor=GRIDLINE, linecolor=BASELINE, tickfont=dict(color=MUTED_INK)),
)


def apply_layout(fig):
    fig.update_layout(**PLOTLY_LAYOUT)
    return fig


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def source_color(source: str) -> str:
    return SOURCE_COLORS.get(source, MUTED_INK)
