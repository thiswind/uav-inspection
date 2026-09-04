from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PAGE_SIZE = (1240, 1754)
MARGIN = 72
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
CLASS_NAMES = {
    "Crack": "裂缝",
    "Seepage": "渗水",
    "TileSpalling": "面砖脱落/外墙破损",
    "Hollowing": "空鼓风险",
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold and FONT_BOLD.exists() else FONT_REGULAR
    if not path.exists():
        path = Path(r"C:\Windows\Fonts\simhei.ttf")
    return ImageFont.truetype(str(path), size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in str(text):
        candidate = f"{current}{char}"
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _paragraph(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    width: int,
    spacing: int = 10,
) -> int:
    x, y = xy
    line_height = font.size + spacing
    for line in _wrap(draw, text, font, width):
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _normalized_center(detection: dict[str, Any], image_size: dict[str, Any]) -> tuple[float, float]:
    bbox = detection.get("bbox") or [0, 0, 0, 0]
    if len(bbox) != 4:
        return 0.5, 0.5
    x1, y1, x2, y2 = (float(value) for value in bbox)
    normalized = max(x1, y1, x2, y2) <= 1.5
    width = 1.0 if normalized else max(1.0, float(image_size.get("width") or 1))
    height = 1.0 if normalized else max(1.0, float(image_size.get("height") or 1))
    return max(0.0, min(1.0, (x1 + x2) / 2 / width)), max(0.0, min(1.0, (y1 + y2) / 2 / height))


def build_wall_assessment(logs: list[dict[str, Any]]) -> dict[str, Any]:
    stats = {name: 0 for name in CLASS_NAMES}
    confidence_sum = 0.0
    detection_count = 0
    zone_counts: dict[str, int] = {}
    gps_points: list[dict[str, Any]] = []
    rows = ["上部", "中部", "下部"]
    columns = ["左侧", "中央", "右侧"]

    for log in logs:
        telemetry = log.get("telemetry") or {}
        latitude = float(telemetry.get("latitude") or 0)
        longitude = float(telemetry.get("longitude") or 0)
        if latitude and longitude:
            gps_points.append({
                "time": float(log.get("time") or 0),
                "latitude": latitude,
                "longitude": longitude,
                "rel_alt": float(telemetry.get("relAlt") or telemetry.get("rel_alt") or 0),
                "abs_alt": float(telemetry.get("absAlt") or telemetry.get("abs_alt") or 0),
            })
        image_size = log.get("image_size") or {}
        for detection in log.get("detections") or []:
            name = str(detection.get("name") or "")
            if name in stats:
                stats[name] += 1
            confidence_sum += float(detection.get("conf") or 0)
            detection_count += 1
            center_x, center_y = _normalized_center(detection, image_size)
            zone = f"{rows[min(2, int(center_y * 3))]}{columns[min(2, int(center_x * 3))]}"
            zone_counts[zone] = zone_counts.get(zone, 0) + 1

    average_confidence = confidence_sum / detection_count if detection_count else 0.0
    score = min(100, round(
        stats["Crack"] * 2.5
        + stats["Seepage"] * 2.0
        + stats["TileSpalling"] * 5.0
        + average_confidence * 10,
    ))
    if not detection_count:
        level, title = "低风险", "暂未发现明显缺陷"
        summary = "当前任务尚无有效检测日志。建议完成整段视频检测，并确认字幕定位数据已加载。"
        actions = ["继续完成全立面视频巡检", "保持相同航线和焦距便于复核", "发现异常后补拍近景"]
    elif score >= 60 or stats["TileSpalling"] >= 5:
        level, title = "高风险", "存在重点外墙缺陷"
        summary = (
            f"检测日志共记录 {detection_count} 条缺陷，其中面砖脱落/外墙破损 {stats['TileSpalling']} 条、"
            f"裂缝 {stats['Crack']} 条、渗水 {stats['Seepage']} 条。建议优先安排现场复核和安全隔离。"
        )
        actions = ["立即复核脱落区域并设置地面警戒", "对裂缝端部和渗水边界补拍近景", "形成维修工单并安排同角度复检"]
    elif score >= 25:
        level, title = "中风险", "建议安排专项复核"
        summary = (
            f"检测日志共记录 {detection_count} 条缺陷，存在局部裂缝、渗水或外墙破损。"
            "应结合 GPS 位置、飞行高度和现场构件确认实际影响范围。"
        )
        actions = ["7 日内安排人工近距离复核", "记录缺陷长度、面积和相邻构件状态", "纳入下一轮无人机重点点位"]
    else:
        level, title = "低风险", "以观察维护为主"
        summary = f"检测日志共记录 {detection_count} 条低权重缺陷，可作为基线持续观察变化。"
        actions = ["保存日志图片作为缺陷基线", "下一周期复拍相同 GPS 点位", "范围或置信度上升时转入专项复核"]

    sorted_zones = [
        {"name": name, "count": count}
        for name, count in sorted(zone_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    location_summary = "未加载有效 GPS 字幕数据"
    if gps_points:
        first = gps_points[0]
        location_summary = (
            f"日志包含 {len(gps_points)} 个 GPS 点，首个点位 "
            f"{first['latitude']:.6f}, {first['longitude']:.6f}。"
        )
    return {
        "log_count": len(logs),
        "detection_count": detection_count,
        "stats": stats,
        "average_confidence": average_confidence,
        "score": score,
        "level": level,
        "title": title,
        "summary": summary,
        "actions": actions,
        "zones": sorted_zones,
        "gps_points": gps_points,
        "location_summary": location_summary,
    }


def _new_page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    page = Image.new("RGB", PAGE_SIZE, "white")
    return page, ImageDraw.Draw(page)


def generate_wall_report_pdf(
    output_path: Path,
    task: dict[str, Any],
    logs: list[dict[str, Any]],
    assessment: dict[str, Any],
    log_directory: Path,
) -> None:
    pages: list[Image.Image] = []
    page, draw = _new_page()
    pages.append(page)
    draw.rounded_rectangle((MARGIN, MARGIN, PAGE_SIZE[0] - MARGIN, 330), radius=24, fill="#0f766e")
    draw.text((MARGIN + 36, MARGIN + 36), "建筑外墙巡检报告", font=_font(52, True), fill="white")
    draw.text((MARGIN + 36, MARGIN + 112), str(task.get("task_name") or "未命名任务"), font=_font(28, True), fill="#d9fffa")
    draw.text((MARGIN + 36, MARGIN + 166), f"视频：{task.get('name') or '--'}", font=_font(22), fill="white")
    draw.text((MARGIN + 36, MARGIN + 208), f"检测日志：{assessment['log_count']} 张", font=_font(22), fill="white")

    y = 382
    draw.text((MARGIN, y), "缺陷情况评估", font=_font(34, True), fill="#0f172a")
    y += 58
    risk_colors = {"高风险": "#be123c", "中风险": "#b45309", "低风险": "#047857"}
    draw.rounded_rectangle((MARGIN, y, PAGE_SIZE[0] - MARGIN, y + 235), radius=18, fill="#f8fafc", outline="#cbd5e1", width=2)
    draw.text((MARGIN + 28, y + 24), f"{assessment['level']}  ·  {assessment['title']}", font=_font(31, True), fill=risk_colors.get(assessment["level"], "#0f766e"))
    draw.text((PAGE_SIZE[0] - MARGIN - 150, y + 22), str(assessment["score"]), font=_font(58, True), fill="#0f172a")
    _paragraph(draw, (MARGIN + 28, y + 88), assessment["summary"], _font(23), "#334155", PAGE_SIZE[0] - 2 * MARGIN - 56, 9)
    y += 280

    stats = assessment["stats"]
    cards = [
        ("裂缝", stats["Crack"], "#fee2e2", "#b91c1c"),
        ("渗水", stats["Seepage"], "#ccfbf1", "#0f766e"),
        ("面砖脱落/破损", stats["TileSpalling"], "#fef3c7", "#b45309"),
        ("平均置信度", f"{assessment['average_confidence'] * 100:.0f}%", "#e0f2fe", "#0369a1"),
    ]
    card_width = (PAGE_SIZE[0] - 2 * MARGIN - 36) // 4
    for index, (label, value, background, foreground) in enumerate(cards):
        x = MARGIN + index * (card_width + 12)
        draw.rounded_rectangle((x, y, x + card_width, y + 145), radius=16, fill=background)
        draw.text((x + 18, y + 18), label, font=_font(18, True), fill=foreground)
        draw.text((x + 18, y + 60), str(value), font=_font(44, True), fill="#0f172a")
    y += 195

    draw.text((MARGIN, y), "缺陷方位", font=_font(34, True), fill="#0f172a")
    y += 54
    y = _paragraph(draw, (MARGIN, y), assessment["location_summary"], _font(23), "#334155", PAGE_SIZE[0] - 2 * MARGIN)
    if assessment["zones"]:
        zone_text = "立面热点：" + "；".join(f"{item['name']} {item['count']} 条" for item in assessment["zones"][:5])
        y = _paragraph(draw, (MARGIN, y + 12), zone_text, _font(22), "#475569", PAGE_SIZE[0] - 2 * MARGIN)
    y += 25
    draw.text((MARGIN, y), "处置建议", font=_font(30, True), fill="#0f172a")
    y += 48
    for index, action in enumerate(assessment["actions"], start=1):
        y = _paragraph(draw, (MARGIN + 10, y), f"{index}. {action}", _font(22), "#334155", PAGE_SIZE[0] - 2 * MARGIN - 10)
        y += 8

    selected_logs = [log for log in logs if log.get("image_file")]
    if len(selected_logs) > 12:
        step = (len(selected_logs) - 1) / 11
        selected_logs = [selected_logs[round(index * step)] for index in range(12)]

    for page_index in range(0, len(selected_logs), 2):
        log_page, log_draw = _new_page()
        pages.append(log_page)
        log_draw.text((MARGIN, MARGIN), "检测日志图片", font=_font(38, True), fill="#0f172a")
        current_y = MARGIN + 68
        for log in selected_logs[page_index:page_index + 2]:
            image_path = log_directory / str(log.get("image_file"))
            if not image_path.exists():
                continue
            with Image.open(image_path) as source:
                snapshot = source.convert("RGB")
                snapshot.thumbnail((PAGE_SIZE[0] - 2 * MARGIN, 570), Image.Resampling.LANCZOS)
                x = (PAGE_SIZE[0] - snapshot.width) // 2
                log_page.paste(snapshot, (x, current_y))
                current_y += snapshot.height + 18
            telemetry = log.get("telemetry") or {}
            gps = "未定位"
            if telemetry.get("latitude") and telemetry.get("longitude"):
                gps = f"{float(telemetry['latitude']):.6f}, {float(telemetry['longitude']):.6f}"
            classes = Counter(str(item.get("name") or "") for item in log.get("detections") or [])
            class_text = "，".join(f"{CLASS_NAMES.get(name, name)} {count}" for name, count in classes.items()) or "无缺陷"
            log_draw.text((MARGIN, current_y), f"视频时间：{float(log.get('time') or 0):.1f}s    GPS：{gps}", font=_font(20, True), fill="#0f172a")
            current_y += 34
            current_y = _paragraph(log_draw, (MARGIN, current_y), f"检测结果：{class_text}", _font(20), "#475569", PAGE_SIZE[0] - 2 * MARGIN)
            current_y += 28

    total_pages = len(pages)
    for index, report_page in enumerate(pages, start=1):
        footer_draw = ImageDraw.Draw(report_page)
        footer_text = f"第 {index} / {total_pages} 页"
        footer_font = _font(16)
        footer_width = footer_draw.textbbox((0, 0), footer_text, font=footer_font)[2]
        footer_draw.text((PAGE_SIZE[0] - MARGIN - footer_width, PAGE_SIZE[1] - 48), footer_text, font=footer_font, fill="#94a3b8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(output_path, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
