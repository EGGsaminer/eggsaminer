"""CSV and PDF export from analysis results."""
import io, csv, statistics
from typing import List, Any
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart


def _rows(results: List[Any]) -> List[dict]:
    return [r.__dict__ if hasattr(r, "__dict__") else dict(r) for r in results]


def generate_csv(results: List[Any]) -> bytes:
    rows = _rows(results)
    if not rows: return b"No results"
    fields = ["id","session_name","haugh_unit","yolk_index","albumen_index",
              "yolk_alb_ratio","yolk_circularity","thick_thin_ratio",
              "roche_yolk_color","grade","freshness","freshness_days",
              "H_alb_mm","yolk_H_mm","yolk_D_mm","alb_spread_mm",
              "egg_weight_g","ppm_top","ppm_side","created_at"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
    return buf.getvalue().encode()


def generate_pdf(results: List[Any]) -> bytes:
    rows = _rows(results)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    S = getSampleStyleSheet()
    title_s = ParagraphStyle("T", parent=S["Title"], fontSize=20,
                              textColor=colors.HexColor("#0f172a"), spaceAfter=3*mm)
    sub_s   = ParagraphStyle("S", parent=S["Normal"], fontSize=9,
                              textColor=colors.HexColor("#64748b"), spaceAfter=8*mm)
    head_s  = ParagraphStyle("H", parent=S["Heading2"], fontSize=12,
                              textColor=colors.HexColor("#1d4ed8"),
                              spaceBefore=5*mm, spaceAfter=3*mm)
    story = []
    story.append(Paragraph("🥚 Egg Quality Analyzer Pro", title_s))
    story.append(Paragraph(
        f"Report generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · "
        f"{len(rows)} egg(s) analysed", sub_s))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 4*mm))

    # Summary stats
    hus = [r.get("haugh_unit") for r in rows if r.get("haugh_unit") is not None]
    def _stat(lst):
        if not lst: return "—", "—"
        m = round(sum(lst)/len(lst), 2)
        s = round(statistics.stdev(lst), 2) if len(lst)>1 else 0.0
        return m, s
    hm,hs = _stat(hus)
    yis=[r.get("yolk_index") for r in rows if r.get("yolk_index")]
    aim=[r.get("albumen_index") for r in rows if r.get("albumen_index")]
    ym,ys = _stat(yis); am,as_ = _stat(aim)

    story.append(Paragraph("Summary Statistics", head_s))
    sdata = [["Metric","Mean","Std Dev"],
             ["Haugh Unit (HU)", str(hm), str(hs)],
             ["Yolk Index (YI)",  str(ym), str(ys)],
             ["Albumen Index (AI)", str(am), str(as_)]]
    st = Table(sdata, colWidths=[70*mm,45*mm,45*mm])
    st.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0f172a")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f8fafc"),colors.white]),
        ("GRID",(0,0),(-1,-1),.5,colors.HexColor("#e2e8f0")),
        ("ALIGN",(1,0),(-1,-1),"CENTER"),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    story.append(st); story.append(Spacer(1,5*mm))

    # HU chart
    if hus:
        story.append(Paragraph("Haugh Unit Distribution", head_s))
        d = Drawing(160*mm, 55*mm)
        bc = VerticalBarChart()
        bc.x,bc.y,bc.width,bc.height = 10*mm,5*mm,140*mm,45*mm
        bc.data=[hus]; bc.bars[0].fillColor=colors.HexColor("#1d4ed8")
        bc.valueAxis.valueMin=max(0,min(hus)-5)
        bc.valueAxis.valueMax=max(hus)+5
        bc.valueAxis.valueStep=10
        labels=[r.get("session_name","")[:8] for r in rows if r.get("haugh_unit")]
        bc.categoryAxis.categoryNames=labels
        bc.categoryAxis.labels.fontSize=7
        d.add(bc); story.append(d); story.append(Spacer(1,4*mm))

    # Results table
    story.append(Paragraph("Detailed Results", head_s))
    gc = {"AA":"#16a34a","A":"#1d4ed8","B":"#d97706"}
    tdata=[["#","Session","HU","YI","AI","Y/A","Circ","Grade","Freshness"]]
    for i,r in enumerate(rows,1):
        tdata.append([str(i), r.get("session_name","")[:15],
                      str(r.get("haugh_unit","—")), str(r.get("yolk_index","—")),
                      str(r.get("albumen_index","—")), str(r.get("yolk_alb_ratio","—")),
                      str(r.get("yolk_circularity","—")), r.get("grade","—"),
                      r.get("freshness","—")])
    cw=[8*mm,38*mm,16*mm,18*mm,18*mm,16*mm,14*mm,15*mm,28*mm]
    rt = Table(tdata, colWidths=cw, repeatRows=1)
    cmds=[("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0f172a")),
          ("TEXTCOLOR",(0,0),(-1,0),colors.white),
          ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
          ("FONTSIZE",(0,0),(-1,-1),7.5),
          ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f8fafc"),colors.white]),
          ("GRID",(0,0),(-1,-1),.5,colors.HexColor("#e2e8f0")),
          ("ALIGN",(2,0),(-1,-1),"CENTER"),
          ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]
    for i,r in enumerate(rows,1):
        g=r.get("grade","")
        if g in gc:
            cmds.append(("TEXTCOLOR",(7,i),(7,i),colors.HexColor(gc[g])))
            cmds.append(("FONTNAME",(7,i),(7,i),"Helvetica-Bold"))
    rt.setStyle(TableStyle(cmds))
    story.append(rt)
    doc.build(story)
    return buf.getvalue()
