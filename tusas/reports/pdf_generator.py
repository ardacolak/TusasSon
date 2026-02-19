"""
TUSAS Laminat Optimizasyonu PDF Rapor Olusturucu.

reportlab kullanarak profesyonel muhendislik raporu uretir.
"""

import io
from datetime import datetime
from typing import Dict, List, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image,
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF


# Ply acilarina gore renkler
ANGLE_COLORS = {
    0: colors.HexColor("#3B82F6"),     # Mavi
    90: colors.HexColor("#EF4444"),    # Kirmizi
    45: colors.HexColor("#10B981"),    # Yesil
    -45: colors.HexColor("#F59E0B"),   # Turuncu
}

ANGLE_LABELS = {
    0: "0\u00b0",
    90: "90\u00b0",
    45: "+45\u00b0",
    -45: "-45\u00b0",
}

# Kural aciklamalari
RULE_DESCRIPTIONS = {
    "R1": ("Simetri", "Orta duzleme gore simetrik istif"),
    "R2": ("Denge", "+45\u00b0/-45\u00b0 ply dengesi"),
    "R3": ("Yuzde Kurali", "Her aci yonunde %8-67 orani"),
    "R4": ("Dis Katmanlar", "Ilk/son 2 katman \u00b145\u00b0"),
    "R5": ("Dagilim", "Acilarin uniform dagilimi"),
    "R6": ("Gruplama", "Max 3 ardisik ayni aci"),
    "R7": ("Burkulma", "\u00b145\u00b0 dis yuzeylerde"),
    "R8": ("Yanal Egilme", "90\u00b0 dis yuzeylerde"),
}


def _create_styles():
    """Ozel PDF stilleri olustur."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "TitleCover",
        parent=styles["Title"],
        fontSize=28,
        leading=34,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.HexColor("#1E3A5F"),
    ))

    styles.add(ParagraphStyle(
        "SubtitleCover",
        parent=styles["Normal"],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=10,
        textColor=colors.HexColor("#4A5568"),
    ))

    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#1E3A5F"),
        borderWidth=0,
        borderColor=colors.HexColor("#3B82F6"),
        borderPadding=4,
    ))

    styles.add(ParagraphStyle(
        "BodyTurkish",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        "SmallNote",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#6B7280"),
    ))

    return styles


def _build_cover_page(elements, styles, project_name, engineer_name, revision):
    """Kapak sayfasi olustur."""
    elements.append(Spacer(1, 60 * mm))

    # Baslik
    elements.append(Paragraph(project_name, styles["TitleCover"]))
    elements.append(Spacer(1, 10 * mm))

    # Alt baslik
    elements.append(Paragraph("Kompozit Laminat Istif Optimizasyonu Raporu", styles["SubtitleCover"]))
    elements.append(Spacer(1, 5 * mm))

    # Cizgi
    elements.append(HRFlowable(width="80%", thickness=2, color=colors.HexColor("#3B82F6")))
    elements.append(Spacer(1, 20 * mm))

    # Bilgi tablosu
    now = datetime.now()
    info_data = [
        ["Tarih:", now.strftime("%d.%m.%Y %H:%M")],
        ["Muhendis:", engineer_name or "-"],
        ["Revizyon:", revision],
        ["Yazilim:", "TUSAS Laminat Optimizatoru v1.0"],
    ]

    info_table = Table(info_data, colWidths=[40 * mm, 80 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1F2937")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
    ]))
    elements.append(info_table)

    elements.append(PageBreak())


def _build_params_section(elements, styles, optimization_params):
    """Optimizasyon parametreleri bolumu."""
    elements.append(Paragraph("1. Optimizasyon Parametreleri", styles["SectionHeader"]))

    params = optimization_params or {}
    rule_weights = params.get("rule_weights", {})

    # Genel parametreler
    general_data = [
        ["Parametre", "Deger"],
        ["Bolge Sayisi", str(params.get("zone_count", "-"))],
        ["Populasyon Buyuklugu", str(params.get("population_size", "-"))],
        ["Jenerasyon Sayisi", str(params.get("generations", "-"))],
        ["Toplam Sure", f"{params.get('duration_seconds', '-')} sn"],
    ]

    gen_table = Table(general_data, colWidths=[60 * mm, 50 * mm])
    gen_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(gen_table)
    elements.append(Spacer(1, 8 * mm))

    # Kural agirliklari tablosu
    if rule_weights:
        elements.append(Paragraph("Kural Agirliklari", styles["BodyTurkish"]))

        weight_data = [["Kural", "Aciklama", "Agirlik"]]
        for rule_key in ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]:
            desc = RULE_DESCRIPTIONS.get(rule_key, (rule_key, ""))[0]
            weight = rule_weights.get(rule_key, "-")
            weight_data.append([rule_key, desc, str(weight)])

        w_table = Table(weight_data, colWidths=[20 * mm, 50 * mm, 25 * mm])
        w_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(w_table)

    elements.append(Spacer(1, 10 * mm))


def _build_zone_summary(elements, styles, zones):
    """Bolge ozeti tablosu."""
    elements.append(Paragraph("2. Bolge Ozeti", styles["SectionHeader"]))

    header = ["Bolge", "Ply Sayisi", "Fitness", "0\u00b0", "90\u00b0", "+45\u00b0", "-45\u00b0", "Root"]
    summary_data = [header]

    for zone in zones:
        if zone is None:
            continue
        ply_counts = zone.get("ply_counts", {})
        is_root = "Evet" if zone.get("is_root", False) else ""
        fitness = zone.get("fitness", 0)
        fitness_str = f"{fitness:.1f}" if isinstance(fitness, (int, float)) else str(fitness)

        row = [
            f"Zone {zone.get('index', '?')}",
            str(zone.get("ply_count", "-")),
            fitness_str,
            str(ply_counts.get("0", ply_counts.get(0, "-"))),
            str(ply_counts.get("90", ply_counts.get(90, "-"))),
            str(ply_counts.get("45", ply_counts.get(45, "-"))),
            str(ply_counts.get("-45", ply_counts.get(-45, "-"))),
            is_root,
        ]
        summary_data.append(row)

    col_widths = [25 * mm, 22 * mm, 20 * mm, 15 * mm, 15 * mm, 15 * mm, 15 * mm, 15 * mm]
    s_table = Table(summary_data, colWidths=col_widths)
    s_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(s_table)
    elements.append(Spacer(1, 10 * mm))


def _draw_ply_diagram(sequence, width=160 * mm, height=40 * mm):
    """Istif sirasi icin 2D renkli ply diagram ciz."""
    d = Drawing(width, height)
    n = len(sequence)
    if n == 0:
        return d

    ply_width = min(float(width - 10 * mm) / n, 8 * mm)
    ply_height = float(height - 12 * mm)
    x_start = 5 * mm

    for i, angle in enumerate(sequence):
        color = ANGLE_COLORS.get(angle, colors.gray)
        x = x_start + i * ply_width
        rect = Rect(x, 8 * mm, ply_width - 0.5, ply_height)
        rect.fillColor = color
        rect.strokeColor = colors.HexColor("#9CA3AF")
        rect.strokeWidth = 0.3
        d.add(rect)

    # Lejand
    legend_x = 5 * mm
    for angle, color in ANGLE_COLORS.items():
        rect = Rect(legend_x, 0, 8, 5)
        rect.fillColor = color
        rect.strokeColor = None
        d.add(rect)
        label = ANGLE_LABELS.get(angle, str(angle))
        s = String(legend_x + 10, 0.5, label, fontSize=6, fillColor=colors.black)
        d.add(s)
        legend_x += 25 * mm

    return d


def _build_zone_details(elements, styles, zones):
    """Her bolge icin detayli kural skorlari ve istif sirasi."""
    elements.append(Paragraph("3. Bolge Detaylari", styles["SectionHeader"]))

    for zone in zones:
        if zone is None:
            continue

        zone_idx = zone.get("index", "?")
        fitness = zone.get("fitness", 0)
        fitness_str = f"{fitness:.1f}" if isinstance(fitness, (int, float)) else str(fitness)
        is_root = " (Root)" if zone.get("is_root", False) else ""

        elements.append(Paragraph(
            f"Zone {zone_idx}{is_root} - Fitness: {fitness_str}/100",
            styles["BodyTurkish"]
        ))

        # Kural skorlari tablosu
        penalties = zone.get("penalties", {})
        if penalties:
            rule_data = [["Kural", "Aciklama", "Agirlik", "Skor", "Ceza", "Neden"]]
            for rule_key in ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]:
                rule_info = penalties.get(rule_key, {})
                desc_name = RULE_DESCRIPTIONS.get(rule_key, (rule_key, ""))[0]
                weight = rule_info.get("weight", "-")
                score = rule_info.get("score", "-")
                penalty = rule_info.get("penalty", "-")
                reason = rule_info.get("reason", "")

                # Skor formatla
                weight_str = f"{weight:.1f}" if isinstance(weight, (int, float)) else str(weight)
                score_str = f"{score:.1f}" if isinstance(score, (int, float)) else str(score)
                penalty_str = f"{penalty:.1f}" if isinstance(penalty, (int, float)) else str(penalty)

                # Neden cok uzunsa kisalt
                if len(reason) > 35:
                    reason = reason[:32] + "..."

                rule_data.append([rule_key, desc_name, weight_str, score_str, penalty_str, reason])

            r_table = Table(rule_data, colWidths=[14 * mm, 28 * mm, 18 * mm, 16 * mm, 16 * mm, 55 * mm])
            r_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (5, 0), (5, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4F6")]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(r_table)

        # Istif sirasi diagrami
        sequence = zone.get("sequence", [])
        if sequence:
            elements.append(Spacer(1, 3 * mm))
            elements.append(Paragraph("Istif Sirasi:", styles["SmallNote"]))

            # Sequence text
            seq_text = " ".join([f"{ANGLE_LABELS.get(a, str(a))}" for a in sequence])
            if len(seq_text) > 200:
                seq_text = seq_text[:197] + "..."
            elements.append(Paragraph(f"<font size='7'>{seq_text}</font>", styles["SmallNote"]))

            # Renkli diagram
            diagram = _draw_ply_diagram(sequence)
            elements.append(diagram)

        elements.append(Spacer(1, 8 * mm))


def _build_warnings(elements, styles, zones):
    """Uyarilar ve oneriler bolumu."""
    warnings = []

    for zone in zones:
        if zone is None:
            continue
        zone_idx = zone.get("index", "?")
        fitness = zone.get("fitness", 0)
        penalties = zone.get("penalties", {})

        if isinstance(fitness, (int, float)) and fitness < 80:
            warnings.append(f"Zone {zone_idx}: Dusuk fitness skoru ({fitness:.1f}/100)")

        for rule_key in ["R1", "R6"]:
            rule_info = penalties.get(rule_key, {})
            penalty = rule_info.get("penalty", 0)
            if isinstance(penalty, (int, float)) and penalty > 5:
                desc = RULE_DESCRIPTIONS.get(rule_key, (rule_key, ""))[0]
                warnings.append(f"Zone {zone_idx}: Yuksek {rule_key} ({desc}) cezasi: {penalty:.1f}")

    if warnings:
        elements.append(Paragraph("4. Uyarilar ve Oneriler", styles["SectionHeader"]))
        for w in warnings:
            elements.append(Paragraph(f"\u2022 {w}", styles["BodyTurkish"]))
        elements.append(Spacer(1, 10 * mm))


def _footer(canvas, doc):
    """Sayfa alt bilgisi."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#9CA3AF"))
    page_num = canvas.getPageNumber()
    canvas.drawCentredString(
        A4[0] / 2, 12 * mm,
        f"TUSAS Laminat Optimizatoru - Sayfa {page_num}"
    )
    canvas.drawRightString(
        A4[0] - 15 * mm, 12 * mm,
        datetime.now().strftime("%d.%m.%Y")
    )
    canvas.restoreState()


def generate_optimization_report(
    zones: List[Dict],
    optimization_params: Optional[Dict] = None,
    engineer_name: str = "",
    project_name: str = "TUSAS Laminat Optimizasyonu",
    revision: str = "Rev. 1",
) -> bytes:
    """PDF rapor olustur ve bytes olarak dondur.

    Args:
        zones: Zone sonuclari listesi
        optimization_params: Optimizasyon parametreleri
        engineer_name: Muhendis adi
        project_name: Proje adi
        revision: Revizyon numarasi

    Returns:
        PDF icerik bytes
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=project_name,
        author=engineer_name or "TUSAS",
    )

    styles = _create_styles()
    elements = []

    # 1. Kapak sayfasi
    _build_cover_page(elements, styles, project_name, engineer_name, revision)

    # 2. Optimizasyon parametreleri
    _build_params_section(elements, styles, optimization_params)

    # 3. Bolge ozeti
    _build_zone_summary(elements, styles, zones)

    # 4. Bolge detaylari
    _build_zone_details(elements, styles, zones)

    # 5. Uyarilar
    _build_warnings(elements, styles, zones)

    # Footer ile build et
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
