<!-- CLIENT INFORMATION -->
<div class="detail-card">
    <div class="detail-card-heading">
        <span class="heading-icon"><i class="bi bi-building"></i></span>
        <div>
            <h3>Client Information</h3>
            <p>Customer details associated with this quotation.</p>
        </div>
    </div>
    <div class="detail-info-grid">
        <div class="detail-item">
            <span>Client Name</span>
            <strong>{% if quotation.client %}{{ quotation.client.company_name }}{% elif quotation.enquiry %}{{ quotation.enquiry.client.company_name }}{% else %}{{ quotation.other_client_name or "N/A" }}{% endif %}</strong>
        </div>
        <div class="detail-item">
            <span>Contact Person</span>
            <strong>{% if quotation.client %}{{ quotation.client.contact_person_name or "N/A" }}{% elif quotation.enquiry %}{{ quotation.enquiry.client.contact_person_name or "N/A" }}{% else %}N/A{% endif %}</strong>
        </div>
        <div class="detail-item">
            <span>Email</span>
            <strong>{% if quotation.client %}{{ quotation.client.email or "N/A" }}{% elif quotation.enquiry %}{{ quotation.enquiry.client.email or "N/A" }}{% else %}N/A{% endif %}</strong>
        </div>
        <div class="detail-item">
            <span>Phone</span>
            <strong>{% if quotation.client %}{{ quotation.client.primary_phone or "N/A" }}{% elif quotation.enquiry %}{{ quotation.enquiry.client.primary_phone or "N/A" }}{% else %}N/A{% endif %}</strong>
        </div>
    </div>
</div>

<!-- SHIPMENT INFORMATION -->
<div class="detail-card">
    <div class="detail-card-heading">
        <span class="heading-icon"><i class="bi bi-truck"></i></span>
        <div>
            <h3>Shipment Information</h3>
            <p>Origin, destination and shipment routing details.</p>
        </div>
    </div>
    <div class="detail-info-grid">
        <div class="detail-item">
            <span>Origin</span>
            <strong>{{ quotation.origin or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Destination</span>
            <strong>{{ quotation.destination or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Origin Port (POL)</span>
            <strong>{{ quotation.origin_port or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Destination Port (POD)</span>
            <strong>{{ quotation.destination_port or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Mode of Shipment</span>
            <strong>{{ quotation.mode_of_shipment or "N/A" }}</strong>
        </div>
    </div>
</div>

<!-- CARGO DETAILS -->
<div class="detail-card">
    <div class="detail-card-heading">
        <span class="heading-icon"><i class="bi bi-box-seam"></i></span>
        <div>
            <h3>Cargo Details</h3>
            <p>Shipment cargo and carrier information.</p>
        </div>
    </div>
    <div class="detail-info-grid">
        <div class="detail-item">
            <span>Cargo Description</span>
            <strong>{{ quotation.cargo_description or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Cargo Weight / Volume</span>
            <strong>{{ quotation.cargo_weight_volume or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Shipping Line / Airline</span>
            <strong>{{ quotation.shipping_line_airline or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>No. of Containers</span>
            <strong>{{ quotation.no_of_containers or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Container Type</span>
            <strong>{{ quotation.container_type_quota or "N/A" }}</strong>
        </div>
    </div>
</div>

<!-- SCHEDULE & TRANSIT DETAILS -->
<div class="detail-card">
    <div class="detail-card-heading">
        <span class="heading-icon"><i class="bi bi-calendar-event"></i></span>
        <div>
            <h3>Schedule & Transit Details</h3>
            <p>Departure schedule, transit and shipment timing information.</p>
        </div>
    </div>
    <div class="detail-info-grid">
        <div class="detail-item">
            <span>Estimated Time of Departure (ETD)</span>
            <strong>{{ quotation.etd.strftime("%d %b %Y %H:%M") if quotation.etd else "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Documentation Cutoff</span>
            <strong>{{ quotation.cutoff_date_documentation.strftime("%d %b %Y %H:%M") if quotation.cutoff_date_documentation else "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Cargo Cutoff</span>
            <strong>{{ quotation.cutoff_date_cargo.strftime("%d %b %Y %H:%M") if quotation.cutoff_date_cargo else "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Free Time (Days)</span>
            <strong>{{ quotation.free_time_days or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Transit Time (Days)</span>
            <strong>{{ quotation.transit_time_days or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Incoterms</span>
            <strong>{{ quotation.incoterms or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>HS Code</span>
            <strong>{{ quotation.hs_code or "N/A" }}</strong>
        </div>
    </div>
</div>

<!-- COST BREAKDOWN -->
<div class="detail-card">
    <div class="detail-card-heading">
        <span class="heading-icon"><i class="bi bi-cash-stack"></i></span>
        <div>
            <h3>Cost Breakdown</h3>
            <p>Complete freight charges and quotation pricing.</p>
        </div>
    </div>
    <div class="detail-info-grid">
        <div class="detail-item">
            <span>Ocean / Air Freight</span>
            <strong>{{ quotation.currency }} {{ "{:,.2f}".format(quotation.ocean_air_freight or 0) }}</strong>
        </div>
        <div class="detail-item">
            <span>Origin Charges</span>
            <strong>{{ quotation.currency }} {{ "{:,.2f}".format(quotation.origin_charges or 0) }}</strong>
        </div>
        <div class="detail-item">
            <span>Destination Charges</span>
            <strong>{{ quotation.currency }} {{ "{:,.2f}".format(quotation.destination_charges or 0) }}</strong>
        </div>
        <div class="detail-item">
            <span>Insurance Charges</span>
            <strong>{{ quotation.currency }} {{ "{:,.2f}".format(quotation.insurance_charges or 0) }}</strong>
        </div>
        <div class="detail-item">
            <span>Other Surcharges</span>
            <strong>{{ quotation.currency }} {{ "{:,.2f}".format(quotation.other_surcharges or 0) }}</strong>
        </div>
        <div class="detail-item quotation-amount-box full-width">
            <span>Grand Total</span>
            <strong class="grand-total-amount">{{ quotation.currency }} {{ "{:,.2f}".format(quotation.quotation_amount or 0) }}</strong>
        </div>
    </div>
</div>

<!-- PAYMENT & REMARKS -->
<div class="detail-card">
    <div class="detail-card-heading">
        <span class="heading-icon"><i class="bi bi-chat-left-text"></i></span>
        <div>
            <h3>Payment & Remarks</h3>
            <p>Payment conditions and additional quotation notes.</p>
        </div>
    </div>
    <div class="detail-info-grid">
        <div class="detail-item">
            <span>Payment Terms</span>
            <strong>{{ quotation.payment_terms or "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Quotation Status</span>
            <strong>{{ quotation.status|replace("_"," ")|title }}</strong>
        </div>
        <div class="detail-item full-width">
            <span>Remarks</span>
            <strong class="remarks-text">{{ quotation.remarks_terms or "No remarks provided." }}</strong>
        </div>
    </div>
</div>

<!-- DECISION & AUDIT INFORMATION -->
<div class="detail-card">
    <div class="detail-card-heading">
        <span class="heading-icon"><i class="bi bi-shield-check"></i></span>
        <div>
            <h3>Decision & Audit Information</h3>
            <p>Approval history and audit trail for this quotation.</p>
        </div>
    </div>
    <div class="detail-info-grid">
        <div class="detail-item">
            <span>Created By</span>
            <strong>{{ quotation.created_by.full_name if quotation.created_by else "System" }}</strong>
        </div>
        <div class="detail-item">
            <span>Created Date</span>
            <strong>{{ quotation.created_at.strftime("%d %b %Y %H:%M") if quotation.created_at else "N/A" }}</strong>
        </div>
        <div class="detail-item">
            <span>Approved By</span>
            <strong>{% if quotation.approved_by %}{{ quotation.approved_by.full_name }}{% else %}N/A{% endif %}</strong>
        </div>
        <div class="detail-item">
            <span>Approved Date</span>
            <strong>{% if quotation.approved_at %}{{ quotation.approved_at.strftime("%d %b %Y %H:%M") }}{% else %}N/A{% endif %}</strong>
        </div>
        {% if quotation.status == "rejected" %}
        <div class="detail-item full-width">
            <span>Rejection Reason</span>
            <strong class="rejection-reason-text">{{ quotation.rejection_reason or "No reason recorded." }}</strong>
        </div>
        {% endif %}
    </div>
</div>

{% block extra_css %}
<style>
/* ==================== CLEAN, MODERN ENTERPRISE CSS SYSTEM ==================== */

:root {
    --primary-color: #2563eb;
    --primary-light: #eff6ff;
    --text-main: #1e293b;
    --text-muted: #64748b;
    --border-color: #e2e8f0;
    --border-hover: #cbd5e1;
    --bg-card: #ffffff;
    --bg-page: #f8fafc;
    --bg-hover: #f1f5f9;
    --success-bg: #ecfdf5;
    --success-text: #166534;
    --danger-bg: #fef2f2;
    --danger-text: #b91c1c;
    --radius-lg: 12px;
    --radius-md: 8px;
    --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
    --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.05);
    --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Base Wrapper & Card Styles */
.detail-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: var(--shadow-sm);
    transition: var(--transition);
}

.detail-card + .detail-card {
    margin-top: 0; /* Handled by standard margin-bottom */
}

.detail-card:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-md);
}

/* Card Heading Layout */
.detail-card-heading {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 16px;
}

.heading-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    background: var(--primary-light);
    color: var(--primary-color);
    border-radius: var(--radius-md);
    flex-shrink: 0;
    transition: var(--transition);
}

.detail-card:hover .heading-icon {
    transform: scale(1.05);
}

.heading-icon i {
    font-size: 18px;
}

.detail-card-heading h3 {
    margin: 0 0 2px 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-main);
    letter-spacing: -0.01em;
}

.detail-card-heading p {
    margin: 0;
    font-size: 13px;
    color: var(--text-muted);
}

/* Grid System Layout */
.detail-info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    align-items: stretch;
}

/* Detail Items */
.detail-item {
    background: var(--bg-page);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 72px;
    transition: var(--transition);
}

.detail-item:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
}

.detail-item span {
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--text-muted);
    margin-bottom: 4px;
}

.detail-item strong {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-main);
    line-height: 1.5;
    overflow-wrap: anywhere;
    word-break: break-word;
    display: block;
}

/* Utility / Full Width Spans */
.detail-item.full-width {
    grid-column: 1 / -1;
}

/* Special Styling for Grand Total & Rejections */
.quotation-amount-box {
    position: relative;
    overflow: hidden;
    background: var(--success-bg) !important;
    border-color: #a7f3d0 !important;
}

.quotation-amount-box::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, transparent, rgba(255, 255, 255, 0.3));
    pointer-events: none;
}

.grand-total-amount {
    color: var(--success-text) !important;
    font-size: 18px !important;
}

.remarks-text {
    font-weight: 600;
    line-height: 1.6;
}

.rejection-reason-text {
    font-weight: 600;
    color: var(--danger-text);
    background: var(--danger-bg);
    padding: 10px;
    border-radius: var(--radius-md);
    border: 1px solid #fecaca;
    display: block;
}

/* Responsive Media Queries */
@media (max-width: 900px) {
    .detail-card-heading {
        align-items: center;
    }
    
    .heading-icon {
        width: 36px;
        height: 36px;
    }
}

@media (max-width: 640px) {
    .detail-card {
        padding: 16px;
    }

    .detail-info-grid {
        grid-template-columns: 1fr;
    }

    .detail-item {
        min-height: auto;
    }

    .detail-item.full-width {
        grid-column: auto;
    }

    .grand-total-amount {
        font-size: 18px !important;
    }
}
</style>
{% endblock %}