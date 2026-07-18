"""Premium PDF inspection report generation."""
import base64
import datetime as dt
import io

from fastapi import APIRouter, Body, Depends, Response
from fpdf import FPDF

from ..auth import get_current_user
from ..models import User

router = APIRouter(prefix="/api/v1/report", tags=["report"])

BLUE = (47, 107, 255)
DARK = (17, 21, 39)
GRAY = (110, 118, 140)
GRADE_COLORS = {"A": (16, 185, 129), "B": (132, 204, 22), "C": (245, 158, 11),
                "D": (249, 115, 22), "E": (239, 68, 68)}


@router.post("/pdf")
def inspection_pdf(report: dict = Body(...), user: User = Depends(get_current_user)):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Header band
    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 210, 34, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_xy(12, 9)
    pdf.cell(0, 8, "Suraya Car - Vehicle Inspection Report")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(12, 19)
    veh = report.get("vehicle", {}) or {}
    veh_label = " ".join(str(v) for v in [veh.get("year") or "", veh.get("make") or "", veh.get("model") or ""] if v) or "Vehicle"
    pdf.cell(0, 6, f"{veh_label}   |   Report {report.get('report_id','-')}   |   "
                   f"{dt.date.today().isoformat()}   |   Prepared for {user.email}")

    # Grade + recommendation
    grade = report.get("condition_grade", "-")
    gc = GRADE_COLORS.get(grade, GRAY)
    pdf.set_y(44)
    pdf.set_fill_color(*gc)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 26)
    pdf.cell(24, 24, grade, align="C", fill=True)
    pdf.set_text_color(*DARK)
    pdf.set_xy(42, 46)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 7, f"Condition grade {grade} - {report.get('purchase_recommendation','')}")
    pdf.set_xy(42, 54)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(150, 5, report.get("condition_summary", ""))

    pdf.set_y(76)
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Recommendation", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(0, 5, report.get("recommendation", ""))
    pdf.ln(4)

    # Damages table
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Findings ({report.get('damages_found', 0)})", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 242, 248)
    for w, h in [(34, "Part"), (26, "Severity"), (28, "Angle"), (52, "Repair"), (50, "Estimated cost")]:
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    total_min = report.get("estimated_repair_min", 0)
    total_max = report.get("estimated_repair_max", 0)
    for angle in report.get("angles", []):
        for d in angle.get("damages", []):
            pdf.cell(34, 7, str(d.get("damage_type", "")), border=1)
            pdf.cell(26, 7, str(d.get("severity", "")).upper(), border=1)
            pdf.cell(28, 7, str(angle.get("angle", "")), border=1)
            pdf.cell(52, 7, str(d.get("repair", ""))[:34], border=1)
            pdf.cell(50, 7, f"${d.get('cost_min',0):,} - ${d.get('cost_max',0):,}  ({d.get('repair_time','')})", border=1)
            pdf.ln()
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 8, "ESTIMATED TOTAL REPAIRS", border=1)
    pdf.cell(50, 8, f"${total_min:,} - ${total_max:,}", border=1)
    pdf.ln(12)

    # Explanations
    expl = [d.get("explanation") for a in report.get("angles", []) for d in a.get("damages", []) if d.get("explanation")]
    if expl:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "AI explanations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY)
        for e in expl[:10]:
            pdf.multi_cell(0, 5, "- " + e)
            pdf.ln(1)

    # Annotated images (first 2)
    imgs = [a.get("annotated_image") for a in report.get("angles", []) if a.get("annotated_image")][:2]
    if imgs:
        pdf.add_page()
        pdf.set_text_color(*DARK)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Annotated evidence", new_x="LMARGIN", new_y="NEXT")
        y = pdf.get_y() + 2
        for b64 in imgs:
            try:
                img = io.BytesIO(base64.b64decode(b64))
                pdf.image(img, x=12, y=y, w=180)
                y += 100
            except Exception:
                continue

    # Footer disclaimer
    pdf.set_y(-30)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(0, 4, report.get("disclaimer", ""))

    out = bytes(pdf.output())
    return Response(content=out, media_type="application/pdf",
                    headers={"Content-Disposition":
                             f"attachment; filename=SurayaCar_Report_{report.get('report_id','X')}.pdf"})
