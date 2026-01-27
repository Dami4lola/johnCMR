"""
PDF Invoice Generation for OBATEK
Uses ReportLab to generate professional invoices
"""
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER

# Theme Configuration (Matches the blue in your target image)
THEME_COLOR = colors.HexColor('#2c5f78')  # Muted Teal/Blue
TEXT_COLOR = colors.HexColor('#333333')
ALT_ROW_COLOR = colors.HexColor('#f2f2f2')  # Light Gray for banding


def draw_header_footer(canvas, doc):
    """
    Draws the static background elements (Blue Header/Footer bars)
    that stay consistent on every page.
    """
    canvas.saveState()

    # --- Header Blue Bar ---
    header_height = 1.2 * inch
    canvas.setFillColor(THEME_COLOR)
    # Draw rectangle from (0, height - header_height) to (width, height)
    canvas.rect(0, letter[1] - header_height, letter[0], header_height, fill=1, stroke=0)

    # --- Header Text (White) ---
    canvas.setFillColor(colors.white)

    # "INVOICE" Title (Left)
    canvas.setFont("Helvetica", 32)
    canvas.drawString(0.5 * inch, letter[1] - 0.8 * inch, "INVOICE")

    # Company Info (Right)
    # Using drawRightString to align to the right margin
    canvas.setFont("Helvetica-Bold", 12)
    right_margin = letter[0] - 0.5 * inch
    top_text_y = letter[1] - 0.4 * inch

    canvas.drawRightString(right_margin, top_text_y, "OBATEK")

    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(right_margin, top_text_y - 14, "Professional Services")
    canvas.drawRightString(right_margin, top_text_y - 28, "Ottawa, Ontario")
    canvas.drawRightString(right_margin, top_text_y - 42, "contact@obatek.com")

    # --- Footer Blue Bar ---
    footer_height = 0.6 * inch
    canvas.setFillColor(THEME_COLOR)
    canvas.rect(0, 0, letter[0], footer_height, fill=1, stroke=0)

    # Footer Text
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawCentredString(letter[0] / 2, 0.25 * inch, "Thank you for your business!")

    canvas.restoreState()


def generate_invoice_pdf(invoice):
    """
    Generate a PDF invoice and return it as bytes
    """
    buffer = BytesIO()

    # Increase top margin to avoid overlapping with our custom header
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=1.5*inch,
        bottomMargin=0.75*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch
    )

    elements = []
    styles = getSampleStyleSheet()

    # --- Styles ---
    # Label style for "Invoice No:", "Date:", etc.
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=TEXT_COLOR,
        leading=14
    )

    # Value style for the actual data
    value_style = ParagraphStyle(
        'Value',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=TEXT_COLOR,
        leading=14
    )

    bill_to_header_style = ParagraphStyle(
        'BillToHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=TEXT_COLOR
    )

    bill_to_text_style = ParagraphStyle(
        'BillToText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=TEXT_COLOR,
        leading=14
    )

    # ==============================
    # 1. TOP SECTION (Invoice Meta & Bill To)
    # ==============================

    # Left Side: Invoice Details
    # Using Paragraphs inside tables ensures text wraps if needed
    inv_data = [
        [Paragraph("Invoice No.", label_style), Paragraph(str(invoice.invoice_number), value_style)],
        [Paragraph("Date of Issue", label_style), Paragraph(invoice.created_date.strftime('%B %d, %Y'), value_style)],
        [Paragraph("Due Date", label_style), Paragraph(invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'Upon Receipt', value_style)],
    ]

    t_left = Table(inv_data, colWidths=[1.2*inch, 2*inch])
    t_left.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    # Right Side: Bill To
    job = invoice.job
    client = job.client

    # Construct Bill To Address Block
    address_parts = [client.name]
    if client.address:
        address_parts.extend(client.address.split('\n'))

    # Create Paragraphs for right alignment
    bill_to_flowables = [Paragraph("<b>Bill To</b>", bill_to_header_style)]
    for part in address_parts:
        bill_to_flowables.append(Paragraph(part, bill_to_text_style))

    # Master Table to hold Left (Info) and Right (Bill To) side by side
    top_table_data = [[t_left, bill_to_flowables]]
    t_top = Table(top_table_data, colWidths=[3.75*inch, 3.75*inch])
    t_top.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))

    elements.append(t_top)
    elements.append(Spacer(1, 0.5*inch))

    # ==============================
    # 2. PRICING TABLE
    # ==============================

    # Header Row
    headers = ['Item', 'Description', 'Hours', 'Rate', 'Amount']

    # Data Rows
    data = []

    # Add the header
    data.append(headers)

    # Row 1 (The Job)
    data.append([
        "1",  # Item #
        invoice.job.description,  # Description
        "-",  # Hours (Placeholder)
        "-",  # Rate (Placeholder)
        f"${invoice.subtotal:,.2f}"  # Amount
    ])

    # Column Widths (Adjusted to look like the image)
    col_widths = [0.6*inch, 3.4*inch, 0.8*inch, 1.0*inch, 1.7*inch]

    t_pricing = Table(data, colWidths=col_widths)

    # Table Styling
    pricing_style = [
        # Header Row Styling
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, 0), TEXT_COLOR),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('LINEBELOW', (0, 0), (-1, 0), 1, TEXT_COLOR),  # Line below header
        ('LINEABOVE', (0, 0), (-1, 0), 1, TEXT_COLOR),  # Line above header

        # General Alignment
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Default left
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),  # Hours, Rate, Amount right aligned

        # Row Padding
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]

    # Zebra Striping (Alternating Colors)
    # Starts from row 1 (data), skips row 0 (header)
    for i in range(1, len(data)):
        if i % 2 == 0:
            bg_color = colors.white
        else:
            bg_color = ALT_ROW_COLOR
        pricing_style.append(('BACKGROUND', (0, i), (-1, i), bg_color))

    t_pricing.setStyle(TableStyle(pricing_style))
    elements.append(t_pricing)

    # Line below the last row
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(
        '<seq id="divider"/>',
        ParagraphStyle('Line', parent=styles['Normal'], borderWidth=0, borderPadding=0, spaceBefore=0)
    ))

    elements.append(Spacer(1, 0.2*inch))

    # ==============================
    # 3. TOTALS SECTION
    # ==============================

    # Totals align to the right, matching the "Amount" column width roughly
    totals_data = [
        ['Subtotal', f"${invoice.subtotal:,.2f}"],
        ['Discount', "$0.00"],  # Placeholder
        ['HST (13%)', f"${invoice.hst_amount:,.2f}"],
        ['Total', f"${invoice.total:,.2f}"],
    ]

    t_totals = Table(totals_data, colWidths=[1.5*inch, 1.7*inch])

    t_totals.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('TEXTCOLOR', (0, 0), (-1, -1), TEXT_COLOR),

        # Bold and Highlight the Final Total
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (1, -1), (1, -1), colors.HexColor('#d9edf7')),  # Light blue highlight for total
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
    ]))

    # Align the totals table to the far right of the page
    totals_wrapper = Table([[None, t_totals]], colWidths=[4.3*inch, 3.2*inch])
    elements.append(totals_wrapper)

    elements.append(Spacer(1, 0.5*inch))

    # ==============================
    # 4. NOTES (Optional)
    # ==============================
    if invoice.notes:
        elements.append(Paragraph("<b>Notes:</b>", styles['Normal']))
        elements.append(Paragraph(invoice.notes, styles['Normal']))

    # Build PDF with the custom header/footer callback
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    buffer.seek(0)
    return buffer.getvalue()
