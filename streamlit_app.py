# streamlit_app.py
from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

# --- ReportLab (vector PDF) ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from reportlab.lib.utils import ImageReader


APP_DIR = Path(__file__).resolve().parent
HEADER_PATH = APP_DIR / "assets" / "header.png"
FOOTER_PATH = APP_DIR / "assets" / "footer.png"
DISCLAIMER_PATH = APP_DIR / "assets" / "disclaimer.txt"
VERSION_PATH = APP_DIR / "assets" / "version.txt"

# page + margins
PAGE_W, PAGE_H = letter  # points
MARGIN = 0.125 * inch    # 1/8 inch = 9 pt

# --- Absolute positions (points) for footer elements ---
# Tune these once and they will not auto-shift.
VER_FONT_SIZE = 6
PAGE_FONT_SIZE = 6
DISC_FONT_SIZE = 6
# Right-aligned X for version/page (drawRightString uses this as right edge)
FOOTER_RIGHT_X = PAGE_W - 0.625 * inch  # ~0.625" from right edge
# Y positions from bottom edge of the page (absolute), not from margins/footer height
VER_Y_ABS = 0.45 * inch   # version line (moved up by 0.10")
PAGE_Y_ABS = 0.32 * inch  # page number line (moved up by 0.10")
# Disclaimer absolute baseline (top-left of the paragraph box)
DISC_X_ABS = 0.125 * inch
DISC_Y_ABS = 0.90 * inch  # moved up by additional 0.10"

DISC_WIDTH = PAGE_W - 2 * 0.125 * inch

# --- Editable table column widths (points) ---
# Adjust these to tune layout; ensure each list sums <= doc.width
CI_COL_WIDTHS = [117, 180, 117, 180]   # [label_L, value_L, label_R, value_R]
PI_COL_WIDTHS = [117, 180, 117, 180]
TP_COL_WIDTHS = [174, 120, 60, 80, 80, 80]  # [Property, Test Method, Unit, Lower, Upper, Result]

# Keys whose values should be rendered as dates (YYYY-MM-DD)
DATE_KEYS = {
    "orderDate", "shippedDate", "manufacturingDate", "expirationDate", "testDate", "printDate"
}

# --- Column width fitter ---
def _fit_col_widths(widths: List[float], max_width: float) -> List[float]:
    """Scale widths proportionally if their sum exceeds max_width; otherwise return as-is."""
    try:
        total = float(sum(widths))
    except Exception:
        return widths
    if total <= 0:
        return widths
    if total <= max_width:
        return widths
    scale = max_width / total
    return [w * scale for w in widths]


# ------------------------ Data helpers ------------------------ #
def parse_uploaded_file(file) -> Dict[str, str]:
    """Parse a CSV/XLSX with two columns: field,value -> dict."""
    data: Dict[str, str] = {}
    if file is None:
        return data
    try:
        name = file.name.lower()
        if name.endswith(".csv"):
            df = pd.read_csv(file, header=None)
        elif name.endswith((".xls", ".xlsx")):
            df = pd.read_excel(file, header=None)
        else:
            st.error("Unsupported file type. Please upload CSV or Excel.")
            return data
        for _, row in df.iterrows():
            if len(row) < 1:
                continue
            field = row.iloc[0]
            if isinstance(field, str) and field.strip().lower() == "field":
                continue
            if pd.isna(field):
                continue
            value = row.iloc[1] if len(row) > 1 else ""
            if pd.isna(value):
                continue
            if isinstance(value, pd.Timestamp):
                value = value.strftime("%Y-%m-%d")
            data[str(field).strip()] = str(value).strip()
    except Exception as exc:
        st.error(f"Failed to parse uploaded file: {exc}")
    return data


def assemble_test_data(form_values: Dict[str, str]) -> List[Dict[str, str]]:
    tests: List[Dict[str, str]] = []
    for idx in range(1, 9):
        entry = {
            "property": form_values.get(f"property{idx}", "").strip(),
            "test_method": form_values.get(f"testMethod{idx}", "").strip(),
            "unit": form_values.get(f"unit{idx}", "").strip(),
            "lower_limit": form_values.get(f"lowerLimit{idx}", "").strip(),
            "upper_limit": form_values.get(f"upperLimit{idx}", "").strip(),
            "result": form_values.get(f"result{idx}", "").strip(),
        }
        if any(entry.values()):
            tests.append(entry)
    return tests


# ------------------------ PDF generation ------------------------ #
class NumberedCanvas(canvas.Canvas):
    """Canvas that writes 'Page X of Y' and a version string during save()."""
    def __init__(self, *args, version_text: str = "1.0", footer_h: float = 0.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._version_text = version_text
        self._footer_h = footer_h

    def showPage(self):
        # Do NOT call super().showPage() here; we only store the state.
        # The actual page emission happens once in save().
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer_numbers(total_pages)
            super().showPage()
        super().save()

    def _draw_footer_numbers(self, total_pages: int) -> None:
        page_num = self.getPageNumber()
        page_text = f"Page {page_num} of {total_pages}"
        right_x = FOOTER_RIGHT_X
        # Version line
        self.setFont("Helvetica", VER_FONT_SIZE)
        self.setFillColor(colors.grey)
        self.drawRightString(right_x, VER_Y_ABS, f"{self._version_text}")
        # Page line
        self.setFont("Helvetica", PAGE_FONT_SIZE)
        self.drawRightString(right_x, PAGE_Y_ABS, page_text)


def _safe_read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return default.strip()



def _image_reader_or_none(path: Path) -> ImageReader | None:
    try:
        if path.is_file():
            return ImageReader(str(path))
    except Exception:
        pass
    return None

# --- Formatting helpers ---
from datetime import datetime

def _normalize_date_str(s: str) -> str:
    """Return YYYY-MM-DD if s parses as a date; else the original string."""
    if not s:
        return s
    try:
        # Pandas-style parsing for robustness
        dt = pd.to_datetime(s, errors="coerce")
        if pd.isna(dt):
            return s
        # If Timestamp, get date component
        if hasattr(dt, "to_pydatetime"):
            dt = dt.to_pydatetime()
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d")
        return str(dt)[:10]
    except Exception:
        return s

def _sci_if_needed(val: str) -> str:
    """If numeric and |value| >= 1000, return in scientific notation like 1.5E+06."""
    if val is None:
        return ""
    s = str(val).strip()
    if not s:
        return s
    try:
        # remove commas for parsing
        f = float(s.replace(",", ""))
        if abs(f) >= 1000:
            return f"{f:.1E}"
        return s
    except Exception:
        return s


def generate_coa_pdf_vector(
    info: Dict[str, str],
    tests: List[Dict[str, str]],
) -> bytes:
    """Vector PDF via ReportLab with header/footer, margins, and auto page numbers."""

    # Load assets
    header_ir = _image_reader_or_none(HEADER_PATH)
    footer_ir = _image_reader_or_none(FOOTER_PATH)
    disclaimer_text = _safe_read_text(
        DISCLAIMER_PATH,
        default="DISCLAIMER: Materials, products, and services are provided under our standard terms and conditions.",
    )
    version_text = _safe_read_text(VERSION_PATH, default="1.0")

    # Pre-measure scaled header/footer height to set frame margins
    def scaled_h(img_ir: ImageReader | None, max_width: float) -> float:
        if not img_ir:
            return 0.0
        iw, ih = img_ir.getSize()
        scale = min(max_width / float(iw), 1.0)
        return ih * scale

    content_width = PAGE_W - 2 * MARGIN
    header_h = scaled_h(header_ir, content_width)
    footer_h = scaled_h(footer_ir, content_width)

    # Reserve space for header and footer within 1/8" margins
    top_margin = MARGIN + (header_h + (6 if header_h else 0))
    bottom_margin = MARGIN + (footer_h + 36)  # +36pt for disclaimer & page/version text

    buffer = io.BytesIO()

    # Build doc with a single main frame inside margins
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )

    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="normal",
        showBoundary=0,
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=18,
        alignment=1,  # center
        spaceAfter=8,
    )
    style_bar = ParagraphStyle(
        "Bar",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.black,
        leading=12,
        spaceBefore=6,
        spaceAfter=4,
    )
    style_cell = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
    )
    style_cell_bold = ParagraphStyle(
        "CellBold",
        parent=style_cell,
        fontName="Helvetica-Bold",
    )
    style_small = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=colors.grey,
    )

    # Section header (gray bar) helper using a one-cell table
    def section_bar(label: str):
        tbl = Table([[Paragraph(label, style_bar)]], colWidths=[doc.width])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e6e6e6")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        return tbl

    story: List = []

    # -------- CUSTOMER INFORMATION (two-column 4-col table) --------
    story.append(section_bar("CUSTOMER INFORMATION"))

    customer_info_rows: List[Tuple[str, str, str, str]] = [
        ("Customer Name", info.get("customerName", ""), "Account Number", info.get("accountNumber", "")),
        ("Customer PO Number", info.get("poNumber", ""), "Supplier Quote Number", info.get("quoteNumber", "")),
        ("Order Date", info.get("orderDate", ""), "Quantity Shipped", info.get("quantityShipped", "")),
        ("Shipped Date", info.get("shippedDate", ""), "Shipped To Location", info.get("shippedLocation", "")),
    ]
    ci_cells = []
    for l1, v1, l2, v2 in customer_info_rows:
        # Normalize date values where applicable
        kv1 = _normalize_date_str(v1) if "order" in l1.lower() or "shipped" in l1.lower() else v1
        kv2 = _normalize_date_str(v2) if ("quote" in l2.lower()) is False and ("shipped" in l2.lower()) else v2
        ci_cells.append([
            Paragraph(l1, style_cell_bold),
            Paragraph(kv1, style_cell),
            Paragraph(l2, style_cell_bold),
            Paragraph(kv2, style_cell),
        ])
    ci_tbl = Table(ci_cells, colWidths=_fit_col_widths(CI_COL_WIDTHS, doc.width))
    ci_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(ci_tbl)
    story.append(Spacer(1, 6))

    # -------- PRODUCT INFORMATION --------
    story.append(section_bar("PRODUCT INFORMATION"))

    product_info_rows = [
        ("Item Name", info.get("itemName", ""), "Item SKU", info.get("itemSKU", "")),
        ("Lot Number", info.get("lotNumber", ""), "Manufacturing Location", info.get("manufacturingLocation", "")),
        ("Manufacturing Date", info.get("manufacturingDate", ""), "Test Date", info.get("testDate", "")),
        ("Expiration Date", info.get("expirationDate", ""), "Certificate Print Date", info.get("printDate", "")),
    ]
    pi_cells = []
    for l1, v1, l2, v2 in product_info_rows:
        # Normalize date values by label
        is_date1 = any(k in l1.lower() for k in ("manufacturing date", "expiration", "test date", "print date"))
        is_date2 = any(k in l2.lower() for k in ("manufacturing date", "expiration", "test date", "print date"))
        kv1 = _normalize_date_str(v1) if is_date1 else v1
        kv2 = _normalize_date_str(v2) if is_date2 else v2
        pi_cells.append([
            Paragraph(l1, style_cell_bold),
            Paragraph(kv1, style_cell),
            Paragraph(l2, style_cell_bold),
            Paragraph(kv2, style_cell),
        ])
    pi_tbl = Table(pi_cells, colWidths=_fit_col_widths(PI_COL_WIDTHS, doc.width))
    pi_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(pi_tbl)
    story.append(Spacer(1, 6))

    # -------- TESTED PROPERTIES --------
    story.append(section_bar("TESTED PROPERTIES"))

    # header + rows
    tp_data: List[List] = [[
        Paragraph("PROPERTY", style_cell_bold),
        Paragraph("TEST METHOD", style_cell_bold),
        Paragraph("UNIT", style_cell_bold),
        Paragraph("LOWER LIMIT", style_cell_bold),
        Paragraph("UPPER LIMIT", style_cell_bold),
        Paragraph("RESULT", style_cell_bold),
    ]]
    for t in tests:
        tp_data.append([
            Paragraph(t.get("property", ""), style_cell),
            Paragraph(t.get("test_method", ""), style_cell),
            Paragraph(t.get("unit", ""), style_cell),
            Paragraph(_sci_if_needed(t.get("lower_limit", "")), style_cell),
            Paragraph(_sci_if_needed(t.get("upper_limit", "")), style_cell),
            Paragraph(_sci_if_needed(t.get("result", "")), style_cell),
        ])

    tp_tbl = Table(tp_data, colWidths=_fit_col_widths(TP_COL_WIDTHS, doc.width), repeatRows=1)
    tp_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(tp_tbl)
    story.append(Spacer(1, 6))

    # --- Page decoration (header/footer drawing, page/version) --- #
    def on_page(c: canvas.Canvas, doc_obj: BaseDocTemplate):
        # Header image (top inside margins)
        if header_ir:
            iw, ih = header_ir.getSize()
            scale = min(content_width / float(iw), 1.0)
            new_w, new_h = iw * scale, ih * scale
            c.drawImage(
                header_ir,
                MARGIN, PAGE_H - MARGIN - new_h,
                width=new_w, height=new_h,
                preserveAspectRatio=True, mask="auto"
            )

        # Footer image (bottom inside margins)
        if footer_ir:
            iw, ih = footer_ir.getSize()
            scale = min(content_width / float(iw), 1.0)
            new_w, new_h = iw * scale, ih * scale
            c.drawImage(
                footer_ir,
                MARGIN, MARGIN,
                width=new_w, height=new_h,
                preserveAspectRatio=True, mask="auto"
            )

        # Disclaimer block at absolute position
        disc_style = ParagraphStyle(
            "Disc",
            parent=style_small,
            fontName="Helvetica",
            fontSize=DISC_FONT_SIZE,
            leading=8,
            textColor=colors.grey,
            alignment=4,  # TA_JUSTIFY
        )
        disc_src = (disclaimer_text or "").strip()
        disc_para = Paragraph(disc_src, disc_style)
        w, h = disc_para.wrapOn(c, DISC_WIDTH, 300)
        disc_para.drawOn(c, DISC_X_ABS, DISC_Y_ABS)

    template = PageTemplate(id="main", frames=[frame], onPage=on_page)
    doc.addPageTemplates([template])

    # Build with custom canvas to fill total pages, passing version and footer_h
    def _canvas_maker(*args, **kwargs):
        return NumberedCanvas(*args, version_text=version_text, footer_h=footer_h, **kwargs)
    doc.build(story, canvasmaker=_canvas_maker)

    # Replace the "__" placeholder with real total page counts:
    # The NumberedCanvas saves pages with our on_page calls already executed.
    # For simplicity, re-open buffer to do nothing; page 'of Y' gets drawn by the
    # second pass in NumberedCanvas.save() where we could draw totals. Here we
    # kept a placeholder; for a single-pass 'Page X of Y', we accept "Page X of __".
    #
    # If you want strict 'Page X of Y', uncomment a more advanced PageCount
    # routine. For most COAs (single page), this reads "Page 1 of __" which is
    # acceptable. To force single page, ensure content fits within one page.

    buffer.seek(0)
    return buffer.getvalue()


# ------------------------ Streamlit UI ------------------------ #
def main():
    st.set_page_config(page_title="COA Generator", layout="wide")
    st.title("Certificate of Analysis (COA) Generator")

    # Compact UI CSS
    st.markdown(
        """
        <style>
        /* Reduce vertical gaps around text inputs and labels */
        div[data-baseweb="input"] { margin-bottom: 2px; }
        label { margin-bottom: 2px !important; }
        /* Compact the block container padding */
        .block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; }
        /* Compact expander content spacing */
        [data-testid="stExpander"] details { padding-top: 0.25rem; padding-bottom: 0.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Upload")
        up = st.file_uploader("CSV/XLSX (two columns: field, value)", type=["csv", "xls", "xlsx"])
        parsed = parse_uploaded_file(up)
        if parsed:
            st.success("Parsed uploaded data.")
        if st.checkbox("Show parsed values"):
            st.write(parsed or {})

    # -------- Forms arranged to mirror PDF --------
    vals: Dict[str, str] = {}

    st.markdown("### CUSTOMER INFORMATION")
    c1, c2 = st.columns(2)
    with c1:
        vals["customerName"] = st.text_input("Customer Name", parsed.get("customerName", ""))
        vals["poNumber"] = st.text_input("Customer PO Number", parsed.get("poNumber", ""))
        vals["orderDate"] = st.text_input("Order Date", parsed.get("orderDate", ""))
        vals["shippedDate"] = st.text_input("Shipped Date", parsed.get("shippedDate", ""))
    with c2:
        vals["accountNumber"] = st.text_input("Account Number", parsed.get("accountNumber", ""))
        vals["quoteNumber"] = st.text_input("Supplier Quote Number", parsed.get("quoteNumber", ""))
        vals["quantityShipped"] = st.text_input("Quantity Shipped", parsed.get("quantityShipped", ""))
        vals["shippedLocation"] = st.text_input("Shipped To Location", parsed.get("shippedLocation", ""))

    st.markdown("---")
    st.markdown("### PRODUCT INFORMATION")
    p1, p2 = st.columns(2)
    with p1:
        vals["itemName"] = st.text_input("Item Name", parsed.get("itemName", ""))
        vals["lotNumber"] = st.text_input("Lot Number", parsed.get("lotNumber", ""))
        vals["manufacturingDate"] = st.text_input("Manufacturing Date", parsed.get("manufacturingDate", ""))
        vals["expirationDate"] = st.text_input("Expiration Date", parsed.get("expirationDate", ""))
    with p2:
        vals["itemSKU"] = st.text_input("Item SKU", parsed.get("itemSKU", ""))
        vals["manufacturingLocation"] = st.text_input("Manufacturing Location", parsed.get("manufacturingLocation", ""))
        vals["testDate"] = st.text_input("Test Date", parsed.get("testDate", ""))
        vals["printDate"] = st.text_input("Certificate Print Date", parsed.get("printDate", ""))

    st.markdown("---")
    st.markdown("### TESTED PROPERTIES")
    with st.expander("Edit Properties", expanded=True):
        for i in range(1, 9):
            st.markdown(f"**Row {i}**")
            r1, r2, r3 = st.columns([2, 2, 1])
            vals[f"property{i}"] = r1.text_input("Property", parsed.get(f"property{i}", ""), key=f"prop{i}")
            vals[f"testMethod{i}"] = r2.text_input("Test Method", parsed.get(f"testMethod{i}", ""), key=f"tm{i}")
            vals[f"unit{i}"] = r3.text_input("Unit", parsed.get(f"unit{i}", ""), key=f"unit{i}")
            r4, r5, r6 = st.columns([1, 1, 1])
            vals[f"lowerLimit{i}"] = r4.text_input("Lower Limit", parsed.get(f"lowerLimit{i}", ""), key=f"ll{i}")
            vals[f"upperLimit{i}"] = r5.text_input("Upper Limit", parsed.get(f"upperLimit{i}", ""), key=f"ul{i}")
            vals[f"result{i}"] = r6.text_input("Result", parsed.get(f"result{i}", ""), key=f"res{i}")
            st.markdown('<hr style="margin:6px 0; border:0; border-top:1px solid #eee;" />', unsafe_allow_html=True)



    # After Tested Properties expander/divider, add single sidebar Generate & Download button
    # Build current tests and filename from inputs
    tests = assemble_test_data(vals)
    sku = vals.get("itemSKU", "").strip() or "ITEMSKU"
    lot = vals.get("lotNumber", "").strip() or "LOTNUMBER"
    po = vals.get("poNumber", "").strip() or "CUSTOMERPO"
    filename = f"{sku}_{lot}_{po}.pdf"

    # One-click: Generate & Download in the sidebar
    def _build_pdf_bytes() -> bytes:
        return generate_coa_pdf_vector(vals, tests)

    with st.sidebar:
        st.download_button(
            label="Generate & Download PDF",
            data=_build_pdf_bytes(),
            file_name=filename,
            mime="application/pdf",
            key="download_generate_single",
        )


if __name__ == "__main__":
    main()
