"""
PDF report generation using fpdf2.

Generates a multi-page A4 PDF with title page, overview rankings,
overview charts, and per-suburb detailed sections with embedded chart images.
"""
from pathlib import Path

from fpdf import FPDF

from models.run_result import RunResult, SuburbReport

# Color constants (RGB tuples)
COLOR_PRIMARY = (46, 134, 171)
COLOR_DARK = (33, 37, 41)
COLOR_GRAY = (108, 117, 125)
COLOR_LIGHT_BG = (248, 249, 250)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (24, 165, 88)
COLOR_RED = (220, 53, 69)

# Page dimensions (A4 in mm)
PAGE_WIDTH = 210
MARGIN = 15
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN


class PropertyReportPDF(FPDF):
    """Custom FPDF subclass for property research reports."""

    def __init__(self, run_id: str):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.run_id = run_id
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self._is_title_page = True

    def header(self):
        """Page header with run ID."""
        if self._is_title_page:
            return
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(*COLOR_GRAY)
        self.cell(CONTENT_WIDTH / 2, 8, f'Australian Property Research | {self.run_id}', align='L')
        self.cell(CONTENT_WIDTH / 2, 8, f'Page {self.page_no()}', align='R', new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*COLOR_GRAY)
        self.line(MARGIN, self.get_y(), PAGE_WIDTH - MARGIN, self.get_y())
        self.ln(4)

    def footer(self):
        """Page footer with disclaimer."""
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(*COLOR_GRAY)
        self.cell(0, 8, 'For informational purposes only. Not financial advice.', align='C')


def _fmt_currency(value) -> str:
    """Format a numeric value as currency string."""
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.0f}"
    except (ValueError, TypeError):
        return "N/A"


def _fmt_pct(value) -> str:
    """Format a numeric value as percentage string."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return "N/A"


def _fmt_num(value, decimals: int = 1) -> str:
    """Format a numeric value."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def _safe_str(value) -> str:
    """Safely convert a value to a string."""
    if value is None:
        return "N/A"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(str(item) for item in value) if value else "N/A"
    return str(value)


def _add_title_page(pdf: PropertyReportPDF, run_result: RunResult):
    """Generate the title/cover page."""
    pdf._is_title_page = True
    pdf.add_page()

    # Centered title block
    pdf.ln(60)
    pdf.set_font('Helvetica', 'B', 28)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(CONTENT_WIDTH, 15, 'Australian Property Research', align='C', new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_font('Helvetica', '', 14)
    pdf.set_text_color(*COLOR_GRAY)
    pdf.cell(CONTENT_WIDTH, 10, 'AI-Powered Investment Analysis Report', align='C', new_x="LMARGIN", new_y="NEXT")

    pdf.ln(20)

    # Run details box
    pdf.set_fill_color(*COLOR_LIGHT_BG)
    box_x = MARGIN + 30
    box_w = CONTENT_WIDTH - 60
    pdf.set_x(box_x)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(*COLOR_DARK)

    details = [
        ('Run ID', run_result.run_id),
        ('Date', run_result.timestamp.strftime('%Y-%m-%d %H:%M:%S')),
        ('Provider', run_result.user_input.get_provider_display()),
        ('Regions', ', '.join(run_result.user_input.regions)),
        ('Dwelling Type', run_result.user_input.dwelling_type.title()),
        ('Max Price', _fmt_currency(run_result.user_input.max_median_price)),
        ('Suburbs Analyzed', str(len(run_result.suburbs))),
    ]

    for label, value in details:
        pdf.set_x(box_x)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(35, 8, f'{label}:', align='L')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(box_w - 35, 8, value, align='L', new_x="LMARGIN", new_y="NEXT")

    pdf._is_title_page = False


def _add_section_heading(pdf: PropertyReportPDF, text: str):
    """Add a styled section heading."""
    pdf.ln(3)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(CONTENT_WIDTH, 10, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*COLOR_PRIMARY)
    pdf.line(MARGIN, pdf.get_y(), MARGIN + CONTENT_WIDTH, pdf.get_y())
    pdf.ln(4)
    pdf.set_text_color(*COLOR_DARK)


def _add_sub_heading(pdf: PropertyReportPDF, text: str):
    """Add a sub-section heading."""
    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(*COLOR_DARK)
    pdf.cell(CONTENT_WIDTH, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _add_key_value_pair(pdf: PropertyReportPDF, key: str, value: str, col_width: float = 55):
    """Add a label-value pair on one line."""
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*COLOR_GRAY)
    pdf.cell(col_width, 6, f'{key}:', align='L')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*COLOR_DARK)
    pdf.cell(CONTENT_WIDTH - col_width, 6, value, align='L', new_x="LMARGIN", new_y="NEXT")


def _add_overview_section(pdf: PropertyReportPDF, run_result: RunResult):
    """Add overview with ranking table."""
    pdf.add_page()
    _add_section_heading(pdf, 'Suburb Rankings Overview')

    suburbs = run_result.get_top_suburbs()
    if not suburbs:
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(CONTENT_WIDTH, 8, 'No suburbs to display.', new_x="LMARGIN", new_y="NEXT")
        return

    # Table header
    col_widths = [10, 40, 12, 30, 25, 22, 18, 23]
    headers = ['#', 'Suburb', 'State', 'Median Price', '5yr Growth', 'Growth', 'Risk', 'Composite']

    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(*COLOR_PRIMARY)
    pdf.set_text_color(*COLOR_WHITE)
    for i, (header, width) in enumerate(zip(headers, col_widths)):
        pdf.cell(width, 7, header, border=1, fill=True, align='C')
    pdf.ln()

    # Table rows
    pdf.set_text_color(*COLOR_DARK)
    for idx, report in enumerate(suburbs):
        m = report.metrics
        gp = m.growth_projections

        if idx % 2 == 1:
            pdf.set_fill_color(*COLOR_LIGHT_BG)
        else:
            pdf.set_fill_color(*COLOR_WHITE)

        pdf.set_font('Helvetica', '', 8)
        row_data = [
            str(report.rank or idx + 1),
            m.identification.name,
            m.identification.state,
            _fmt_currency(m.market_current.median_price),
            _fmt_pct(gp.projected_growth_pct.get(5, 0)),
            _fmt_num(gp.growth_score),
            _fmt_num(gp.risk_score),
            _fmt_num(gp.composite_score),
        ]

        for value, width in zip(row_data, col_widths):
            pdf.cell(width, 6, value, border=1, fill=True, align='C')
        pdf.ln()


def _embed_chart(pdf: PropertyReportPDF, chart_path: Path, caption: str = ""):
    """Embed a chart image with optional caption. Skip if file missing."""
    if not chart_path.exists():
        return

    # Check if enough space for chart (roughly 80mm + caption)
    if pdf.get_y() > 200:
        pdf.add_page()

    try:
        pdf.image(str(chart_path), x=MARGIN, w=CONTENT_WIDTH)
    except Exception:
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(*COLOR_GRAY)
        pdf.cell(CONTENT_WIDTH, 6, f'[Chart could not be embedded: {chart_path.name}]',
                 new_x="LMARGIN", new_y="NEXT")
        return

    if caption:
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(*COLOR_GRAY)
        pdf.cell(CONTENT_WIDTH, 5, caption, align='C', new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*COLOR_DARK)
    pdf.ln(3)


def _add_overview_charts(pdf: PropertyReportPDF, output_dir: Path):
    """Embed overview chart images."""
    charts_dir = output_dir / "charts"
    if not charts_dir.exists():
        return

    overview_charts = sorted(charts_dir.glob("overview_*.png"))
    if not overview_charts:
        return

    _add_section_heading(pdf, 'Comparison Charts')

    for chart_path in overview_charts:
        caption = chart_path.stem.replace("overview_", "").replace("_", " ").title()
        _embed_chart(pdf, chart_path, caption)


def _add_suburb_section(pdf: PropertyReportPDF, report: SuburbReport, output_dir: Path):
    """Add a complete suburb section starting on a new page."""
    pdf.add_page()
    m = report.metrics
    gp = m.growth_projections

    # Suburb header
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(*COLOR_PRIMARY)
    rank_text = f"#{report.rank} " if report.rank else ""
    pdf.cell(CONTENT_WIDTH, 12, f'{rank_text}{m.get_display_name()}', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Investment summary metrics
    _add_sub_heading(pdf, 'Investment Summary')
    _add_key_value_pair(pdf, 'Median Price', _fmt_currency(m.market_current.median_price))
    _add_key_value_pair(pdf, '5-Year Growth', _fmt_pct(gp.projected_growth_pct.get(5, 0)))
    _add_key_value_pair(pdf, 'Growth Score', _fmt_num(gp.growth_score))
    _add_key_value_pair(pdf, 'Risk Score', _fmt_num(gp.risk_score))
    _add_key_value_pair(pdf, 'Composite Score', _fmt_num(gp.composite_score))
    if m.market_current.rental_yield_current:
        _add_key_value_pair(pdf, 'Rental Yield', _fmt_pct(m.market_current.rental_yield_current))
    pdf.ln(2)

    # Growth projections table
    _add_sub_heading(pdf, 'Growth Projections')
    proj_col_widths = [25, 25, 35, 35, 35]
    proj_headers = ['Horizon', 'Growth %', 'Est. Price', 'CI Low', 'CI High']

    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(*COLOR_PRIMARY)
    pdf.set_text_color(*COLOR_WHITE)
    for header, width in zip(proj_headers, proj_col_widths):
        pdf.cell(width, 7, header, border=1, fill=True, align='C')
    pdf.ln()

    pdf.set_text_color(*COLOR_DARK)
    median_price = m.market_current.median_price or 0
    ci = gp.confidence_intervals or {}

    for idx, year in enumerate([1, 2, 3, 5, 10, 25]):
        if idx % 2 == 1:
            pdf.set_fill_color(*COLOR_LIGHT_BG)
        else:
            pdf.set_fill_color(*COLOR_WHITE)

        growth = gp.projected_growth_pct.get(year, 0)
        est_price = median_price * (1 + growth / 100) if median_price else 0
        interval = ci.get(year)
        ci_low = _fmt_pct(interval[0]) if interval and len(interval) == 2 else "N/A"
        ci_high = _fmt_pct(interval[1]) if interval and len(interval) == 2 else "N/A"

        pdf.set_font('Helvetica', '', 8)
        row_data = [
            f'{year} Year{"s" if year > 1 else ""}',
            _fmt_pct(growth),
            _fmt_currency(est_price),
            ci_low,
            ci_high,
        ]
        for value, width in zip(row_data, proj_col_widths):
            pdf.cell(width, 6, value, border=1, fill=True, align='C')
        pdf.ln()

    pdf.ln(2)

    # Key growth drivers
    if gp.key_drivers:
        _add_sub_heading(pdf, 'Key Growth Drivers')
        pdf.set_font('Helvetica', '', 9)
        for driver in gp.key_drivers[:8]:
            driver_text = str(driver)[:120]
            pdf.cell(5, 5, '', align='L')
            pdf.cell(CONTENT_WIDTH - 5, 5, f'- {driver_text}', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # Current market metrics
    _add_sub_heading(pdf, 'Current Market Metrics')
    mc = m.market_current
    if mc.average_price:
        _add_key_value_pair(pdf, 'Average Price', _fmt_currency(mc.average_price))
    if mc.days_on_market_current:
        _add_key_value_pair(pdf, 'Days on Market', _fmt_num(mc.days_on_market_current, 0))
    if mc.auction_clearance_current:
        _add_key_value_pair(pdf, 'Auction Clearance', _fmt_pct(mc.auction_clearance_current))
    if mc.turnover_rate_current:
        _add_key_value_pair(pdf, 'Turnover Rate', _fmt_pct(mc.turnover_rate_current))
    pdf.ln(2)

    # Physical configuration
    pc = m.physical_config
    if any([pc.typical_bedrooms, pc.typical_bathrooms, pc.land_size_median_sqm]):
        _add_sub_heading(pdf, 'Property Configuration')
        if pc.typical_bedrooms:
            _add_key_value_pair(pdf, 'Bedrooms', str(pc.typical_bedrooms))
        if pc.typical_bathrooms:
            _add_key_value_pair(pdf, 'Bathrooms', str(pc.typical_bathrooms))
        if pc.typical_car_spaces:
            _add_key_value_pair(pdf, 'Car Spaces', str(pc.typical_car_spaces))
        if pc.land_size_median_sqm:
            _add_key_value_pair(pdf, 'Land Size', f'{pc.land_size_median_sqm:.0f} sqm')
        if pc.floor_size_median_sqm:
            _add_key_value_pair(pdf, 'Floor Size', f'{pc.floor_size_median_sqm:.0f} sqm')
        pdf.ln(2)

    # Infrastructure summary
    inf = m.infrastructure
    has_infra = any([inf.current_transport, inf.future_transport, inf.planned_infrastructure])
    if has_infra:
        _add_sub_heading(pdf, 'Infrastructure & Amenities')
        if inf.current_transport:
            _add_key_value_pair(pdf, 'Current Transport', _safe_str(inf.current_transport)[:150], col_width=40)
        if inf.future_transport:
            _add_key_value_pair(pdf, 'Future Transport', _safe_str(inf.future_transport)[:150], col_width=40)
        if inf.planned_infrastructure:
            _add_key_value_pair(pdf, 'Planned Projects', _safe_str(inf.planned_infrastructure)[:150], col_width=40)
        if inf.schools_summary:
            _add_key_value_pair(pdf, 'Schools', _safe_str(inf.schools_summary)[:150], col_width=40)
        if inf.shopping_access:
            _add_key_value_pair(pdf, 'Shopping', _safe_str(inf.shopping_access)[:150], col_width=40)
        pdf.ln(2)

    # Risk analysis
    if gp.risk_analysis:
        _add_sub_heading(pdf, 'Risk Analysis')
        pdf.set_font('Helvetica', '', 9)
        risk_text = str(gp.risk_analysis)[:500]
        pdf.multi_cell(CONTENT_WIDTH, 5, risk_text)
        pdf.ln(2)

    # Embed suburb charts
    charts_dir = output_dir / "charts"
    slug = m.get_slug()

    chart_files = [
        (f"growth_projection_{slug}.png", "Growth Projection"),
        (f"price_history_{slug}.png", "Price History"),
        (f"dom_history_{slug}.png", "Days on Market History"),
    ]

    for filename, caption in chart_files:
        chart_path = charts_dir / filename
        _embed_chart(pdf, chart_path, caption)


def generate_pdf(run_result: RunResult, output_dir: Path, pdf_path: Path):
    """
    Generate the complete PDF report.

    Args:
        run_result: Complete RunResult
        output_dir: Directory containing chart images
        pdf_path: Where to write the PDF
    """
    pdf = PropertyReportPDF(run_id=run_result.run_id)

    # Title page
    _add_title_page(pdf, run_result)

    # Overview rankings
    _add_overview_section(pdf, run_result)

    # Overview charts
    _add_overview_charts(pdf, output_dir)

    # Individual suburb reports
    for report in run_result.get_top_suburbs():
        _add_suburb_section(pdf, report, output_dir)

    # Write PDF
    pdf.output(str(pdf_path))
