from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "architecture.png"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    fill: str,
    max_chars: int,
) -> None:
    lines: list[str] = []
    for part in text.split("\n"):
        lines.extend(wrap(part, width=max_chars) or [""])

    line_height = font.getbbox("Ag")[3] + 5
    total_height = line_height * len(lines)
    x1, y1, x2, y2 = box
    y = y1 + ((y2 - y1) - total_height) // 2

    for line in lines:
        width = draw.textlength(line, font=font)
        draw.text((x1 + ((x2 - x1) - width) / 2, y), line, font=font, fill=fill)
        y += line_height


def rounded_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    fill: str,
    outline: str,
) -> None:
    draw.rounded_rectangle(box, radius=16, fill=fill, outline=outline, width=2)
    x1, y1, x2, y2 = box
    title_font = load_font(22, bold=True)
    body_font = load_font(17)
    draw_wrapped(draw, title, (x1 + 12, y1 + 14, x2 - 12, y1 + 48), title_font, "#102033", 18)
    draw_wrapped(draw, subtitle, (x1 + 14, y1 + 56, x2 - 14, y2 - 12), body_font, "#27384f", 24)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str) -> None:
    draw.line([start, end], fill=color, width=4)
    x, y = end
    draw.polygon([(x, y), (x - 13, y - 8), (x - 13, y + 8)], fill=color)


def main() -> None:
    width, height = 1800, 1060
    image = Image.new("RGB", (width, height), "#f6f8fb")
    draw = ImageDraw.Draw(image)

    title_font = load_font(42, bold=True)
    subtitle_font = load_font(22)
    draw.text((70, 48), "W1-D3: AIOps Observability Data Layer", font=title_font, fill="#0b1f35")
    draw.text(
        (72, 105),
        "Use case: payment service anomaly detection with metric -> trace -> log investigation",
        font=subtitle_font,
        fill="#53657d",
    )

    boxes = [
        ((70, 220, 300, 360), "Service", "Payment service\nOpenTelemetry SDK", "#e7f0ff"),
        ((370, 220, 600, 360), "Collection", "OTel Collector\nDaemonSet", "#e8f7ee"),
        ((670, 220, 900, 360), "Transport", "Kafka topics\nmetrics/logs/traces", "#fff3d7"),
        ((970, 220, 1200, 360), "Processing", "Flink jobs\nparse + enrich + features", "#fdeaea"),
        ((1270, 150, 1500, 290), "Metric Store", "VictoriaMetrics\nPromQL + retention", "#eee9ff"),
        ((1270, 360, 1500, 500), "Log Store", "Loki + S3\nlabel-first search", "#e7f7fb"),
        ((1270, 570, 1500, 710), "Trace Store", "Jaeger\nsampled spans", "#f2f4f7"),
        ((970, 570, 1200, 710), "Feature Store", "Redis online\nS3 + Parquet offline", "#eaf8e7"),
        ((1570, 220, 1740, 360), "Query", "Grafana\nAlertmanager", "#fff0f5"),
        ((1570, 520, 1740, 660), "AI/RCA", "Anomaly detector\nroot cause workflow", "#eef6ff"),
    ]

    for box, title, subtitle, fill in boxes:
        rounded_box(draw, box, title, subtitle, fill, "#cbd6e2")

    line = "#34536f"
    arrow(draw, (300, 290), (370, 290), line)
    arrow(draw, (600, 290), (670, 290), line)
    arrow(draw, (900, 290), (970, 290), line)
    arrow(draw, (1200, 290), (1270, 220), line)
    arrow(draw, (1200, 300), (1270, 430), line)
    arrow(draw, (1130, 360), (1130, 570), line)
    arrow(draw, (1500, 220), (1570, 290), line)
    arrow(draw, (1500, 430), (1570, 590), line)
    arrow(draw, (1500, 640), (1570, 590), line)
    arrow(draw, (1200, 640), (1570, 590), line)

    note_font = load_font(20)
    draw.rounded_rectangle((70, 805, 1740, 955), radius=18, fill="#ffffff", outline="#d8e0eb", width=2)
    notes = [
        "Kafka absorbs incident spikes and allows replay when processing/storage is down.",
        "Flink computes rolling features for real-time anomaly detection.",
        "Metrics trigger alerts, traces locate the slow path, logs confirm the exact failure.",
        "Hot data stays queryable; cold data moves to S3/Parquet for low-cost retention.",
    ]
    y = 832
    for item in notes:
        draw.text((105, y), f"- {item}", font=note_font, fill="#25364a")
        y += 30

    image.save(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
