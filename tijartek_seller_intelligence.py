import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import json

# ============================================================================
# PAGE CONFIG & STYLING
# ============================================================================

st.set_page_config(
    page_title="Tijartek Seller Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tijartek Color Palette
COLORS = {
    "background": "#F5EFEB",
    "foreground": "#2F4156",
    "accent": "#567C8D",
    "good": "#567C8D",
    "bad": "#8B4F4F",
    "border": "#7A9BAD",
    "card_bg": "#FBF9F6",
    "neutral": "#C8D9E6",
    "highlight": "#D2A185",
    "light_blue": "#CADBE7",
    "pale": "#E9F0F4",
}

# Custom CSS for Tijartek branding
st.markdown(f"""
<style>
    * {{
        color: {COLORS['foreground']};
    }}
    
    body {{
        background-color: {COLORS['background']};
    }}
    
    .stMetricValue {{
        font-size: 2.5rem;
        font-weight: 700;
    }}
    
    .stMetricLabel {{
        font-size: 0.9rem;
        font-weight: 600;
        color: {COLORS['accent']};
    }}
    
    h1, h2, h3 {{
        color: {COLORS['foreground']};
        font-weight: 700;
    }}
    
    .score-excellent {{
        color: {COLORS['good']};
    }}
    
    .score-warning {{
        color: {COLORS['highlight']};
    }}
    
    .score-critical {{
        color: {COLORS['bad']};
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATA GENERATION (Replace with Databricks queries)
# ============================================================================

@st.cache_data
def generate_sample_data():
    """
    TEMPORARY: Generate sample seller data.
    REPLACE with actual Databricks query using:
    
    from databricks import sql
    conn = sql.connect(server_hostname=HOST, http_path=HTTP_PATH, token=TOKEN)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            s.seller_id, s.seller_name,
            DATE_TRUNC('MONTH', d.full_date) as month,
            SUM(o.total_amount) as revenue,
            SUM(o.gross_profit) as gross_profit,
            SUM(o.quantity) as quantity_sold,
            COUNT(CASE WHEN o.is_returned = 1 THEN 1 END) / COUNT(*) * 100 as return_rate
        FROM fact_orders o
        JOIN dim_seller s ON o.seller_key = s.seller_key
        JOIN dim_date d ON o.date_key = d.date_key
        WHERE d.year >= 2023
        GROUP BY s.seller_id, s.seller_name, DATE_TRUNC('MONTH', d.full_date)
        ORDER BY s.seller_id, month
    ''')
    return pd.DataFrame(cursor.fetchall())
    """
    
    np.random.seed(42)
    sellers = ["Rowland Lynch", "Francis Retail", "Ahmed Electronics", "Noor Fashion", "Smart Home Egypt"]
    months = pd.date_range("2023-01-01", "2025-03-01", freq='MS')
    
    data = []
    for seller in sellers:
        base_revenue = np.random.randint(300000, 1000000)
        base_margin = np.random.uniform(0.25, 0.45)
        
        for i, month in enumerate(months):
            # Add some trend and seasonality
            trend = 1 + (i * 0.02)  # Slight growth
            seasonality = 1.2 if month.month in [3, 11, 12] else 0.95 if month.month in [2, 8] else 1.0
            
            revenue = base_revenue * trend * seasonality * np.random.uniform(0.85, 1.15)
            gross_profit = revenue * base_margin
            quantity = int(revenue / np.random.uniform(200, 500))
            return_rate = np.random.uniform(2, 8)
            
            # Add anomalies for some sellers at specific times
            if seller == "Ahmed Electronics" and month == pd.Timestamp("2024-09-01"):
                return_rate = 15  # Spike
            if seller == "Smart Home Egypt" and month >= pd.Timestamp("2025-01-01"):
                revenue *= 0.6  # Declining
                
            data.append({
                "seller_id": seller.replace(" ", "_"),
                "seller_name": seller,
                "month": month,
                "revenue": int(revenue),
                "gross_profit": int(gross_profit),
                "quantity_sold": quantity,
                "return_rate": round(return_rate, 2)
            })
    
    return pd.DataFrame(data)

# ============================================================================
# BUSINESS LOGIC
# ============================================================================

def calculate_health_score(revenue, gross_profit, quantity, return_rate):
    """Composite seller health score (0-100)"""
    profit_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
    revenue_score = min(100, (revenue / 1000000) * 100)
    volume_score = min(100, (quantity / 5000) * 100)
    quality_score = max(0, 100 - (return_rate * 5))
    
    health = (
        revenue_score * 0.3 +
        volume_score * 0.25 +
        profit_margin * 0.25 +
        quality_score * 0.2
    )
    
    return round(min(100, max(0, health)), 1)

def detect_anomalies(seller_data):
    """Detect unusual patterns in seller metrics"""
    if len(seller_data) < 2:
        return None
    
    seller_data = seller_data.sort_values("month")
    latest = seller_data.iloc[-1]
    prev = seller_data.iloc[-2]
    
    anomalies = []
    
    # Revenue drop
    revenue_change = ((latest["revenue"] - prev["revenue"]) / prev["revenue"] * 100) if prev["revenue"] > 0 else 0
    if revenue_change < -25:
        anomalies.append({
            "type": "Revenue Decline",
            "severity": "high" if revenue_change < -40 else "medium",
            "detail": f"Revenue dropped {abs(revenue_change):.1f}% vs last month"
        })
    
    # Return rate spike
    return_change = latest["return_rate"] - prev["return_rate"]
    if return_change > 3:
        anomalies.append({
            "type": "Return Rate Spike",
            "severity": "high" if return_change > 5 else "medium",
            "detail": f"Return rate increased {return_change:.1f}pp to {latest['return_rate']:.1f}%"
        })
    
    # Volume drop
    volume_change = ((latest["quantity_sold"] - prev["quantity_sold"]) / prev["quantity_sold"] * 100) if prev["quantity_sold"] > 0 else 0
    if volume_change < -20:
        anomalies.append({
            "type": "Volume Decline",
            "severity": "medium",
            "detail": f"Quantity sold dropped {abs(volume_change):.1f}%"
        })
    
    return anomalies if anomalies else None

def forecast_revenue(seller_data, months_ahead=3):
    """Simple linear forecast of revenue for next N months"""
    seller_data = seller_data.sort_values("month")
    
    if len(seller_data) < 3:
        return None
    
    x = np.arange(len(seller_data))
    y = seller_data["revenue"].values
    
    # Linear regression
    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs[0], coeffs[1]
    
    forecast = []
    last_month = seller_data.iloc[-1]["month"]
    
    for i in range(1, months_ahead + 1):
        next_month = last_month + pd.DateOffset(months=i)
        predicted_revenue = intercept + slope * (len(seller_data) + i - 1)
        forecast.append({
            "month": next_month,
            "predicted_revenue": max(0, int(predicted_revenue))
        })
    
    return pd.DataFrame(forecast)

def calculate_churn_risk(seller_data):
    """Estimate churn risk based on trend patterns"""
    if len(seller_data) < 3:
        return {"risk_level": "unknown", "risk_score": 0, "signals": []}
    
    seller_data = seller_data.sort_values("month")
    
    signals = []
    risk_score = 0
    
    # Revenue trend
    recent_6 = seller_data.tail(6) if len(seller_data) >= 6 else seller_data
    if len(recent_6) > 1:
        revenue_trend = (recent_6.iloc[-1]["revenue"] - recent_6.iloc[0]["revenue"]) / recent_6.iloc[0]["revenue"]
        if revenue_trend < -0.3:
            signals.append("Declining revenue")
            risk_score += 30
    
    # Return rate trend
    if len(recent_6) > 1:
        return_trend = recent_6.iloc[-1]["return_rate"] - recent_6.iloc[0]["return_rate"]
        if return_trend > 2:
            signals.append("Rising return rate")
            risk_score += 25
    
    # Volume trend
    if len(recent_6) > 1:
        volume_trend = (recent_6.iloc[-1]["quantity_sold"] - recent_6.iloc[0]["quantity_sold"]) / recent_6.iloc[0]["quantity_sold"]
        if volume_trend < -0.2:
            signals.append("Decreasing sales volume")
            risk_score += 20
    
    # Low profitability
    latest_margin = (seller_data.iloc[-1]["gross_profit"] / seller_data.iloc[-1]["revenue"] * 100) if seller_data.iloc[-1]["revenue"] > 0 else 0
    if latest_margin < 20:
        signals.append("Low profit margin")
        risk_score += 15
    
    risk_level = "critical" if risk_score >= 70 else "high" if risk_score >= 50 else "medium" if risk_score >= 30 else "low"
    
    return {
        "risk_level": risk_level,
        "risk_score": min(100, risk_score),
        "signals": signals
    }

def generate_ai_insight(seller_name, health_score, anomalies, churn_risk):
    """Call Claude API to generate business insight"""
    try:
        prompt = f"""You are a business intelligence analyst for Tijartek, an Egyptian e-commerce platform.

Seller: {seller_name}
Health Score: {health_score}/100
Churn Risk: {churn_risk['risk_level'].upper()} ({churn_risk['risk_score']}/100)
Risk Signals: {', '.join(churn_risk['signals']) if churn_risk['signals'] else 'None'}
Anomalies: {str(anomalies) if anomalies else 'None detected'}

Generate a SHORT, ACTIONABLE insight (2-3 sentences) that:
1. Summarizes the seller's health status
2. Highlights the biggest concern
3. Provides ONE specific recommendation

Be direct and data-driven."""

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("content") and len(data["content"]) > 0:
                return data["content"][0].get("text", "Insight generation failed.")
    except:
        pass
    
    return None

# ============================================================================
# UI COMPONENTS
# ============================================================================

st.markdown("# Tijartek Seller Intelligence")
st.markdown("AI-powered seller performance analysis & risk detection")

st.divider()

# Sidebar - Seller Selection
with st.sidebar:
    st.markdown("## Seller Selection")
    data = generate_sample_data()
    sellers = sorted(data["seller_name"].unique())
    selected_seller = st.selectbox("Choose a seller:", sellers)
    st.divider()
    st.markdown("### About This Dashboard")
    st.caption("""
    Real-time seller health monitoring with AI-powered insights:
    - **Health Score**: Composite metric from revenue, volume, margin, quality
    - **Anomaly Detection**: Flags unusual patterns vs baseline
    - **Churn Risk**: Predictive risk assessment
    - **Forecasting**: Next 3 months revenue projection
    """)

# Get selected seller data
seller_data = data[data["seller_name"] == selected_seller].sort_values("month")
latest_metrics = seller_data.iloc[-1]

# ============================================================================
# SECTION 1: HEALTH SCORE
# ============================================================================

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("### Health Score")
    
    health = calculate_health_score(
        latest_metrics["revenue"],
        latest_metrics["gross_profit"],
        latest_metrics["quantity_sold"],
        latest_metrics["return_rate"]
    )
    
    # Score card with color coding
    if health >= 75:
        score_class = "score-excellent"
        status = "Excellent"
    elif health >= 50:
        score_class = "score-warning"
        status = "Good"
    else:
        score_class = "score-critical"
        status = "Needs Attention"
    
    st.markdown(f"<div style='text-align: center; padding: 30px; border: 2px solid {COLORS['accent']}; border-radius: 8px; background: {COLORS['pale']};'><div style='font-size: 3rem; font-weight: 700; color: {COLORS['accent']}; margin-bottom: 10px;'>{health}</div><div style='font-size: 1.1rem; color: {COLORS['foreground']};'>{status}</div></div>", unsafe_allow_html=True)

with col2:
    st.markdown("### Key Metrics")
    st.metric("Revenue", f"${latest_metrics['revenue']/1e6:.2f}M")
    st.metric("Margin", f"{(latest_metrics['gross_profit']/latest_metrics['revenue']*100):.1f}%")

with col3:
    st.markdown("### Quality")
    st.metric("Return Rate", f"{latest_metrics['return_rate']:.1f}%")
    st.metric("Volume", f"{latest_metrics['quantity_sold']:,}")

st.divider()

# ============================================================================
# SECTION 2: ANOMALY DETECTION
# ============================================================================

st.markdown("### Anomaly Detection")

anomalies = detect_anomalies(seller_data)

if anomalies:
    for anomaly in anomalies:
        severity_color = COLORS['bad'] if anomaly['severity'] == 'high' else COLORS['highlight']
        st.warning(f"**{anomaly['type']}** ({anomaly['severity'].upper()}) — {anomaly['detail']}")
else:
    st.success("No anomalies detected. Seller metrics are stable.")

st.divider()

# ============================================================================
# SECTION 3: CHURN RISK
# ============================================================================

st.markdown("### Churn Risk Assessment")

churn = calculate_churn_risk(seller_data)

col1, col2 = st.columns([1, 2])

with col1:
    risk_color = {
        "critical": COLORS['bad'],
        "high": COLORS['highlight'],
        "medium": COLORS['neutral'],
        "low": COLORS['good']
    }[churn['risk_level']]
    
    st.markdown(f"""
    <div style='text-align: center; padding: 30px; border: 2px solid {risk_color}; border-radius: 8px; background: {COLORS['pale']};'>
        <div style='font-size: 2.5rem; font-weight: 700; color: {risk_color}; margin-bottom: 10px;'>{churn['risk_score']}</div>
        <div style='font-size: 1rem; color: {COLORS['foreground']};'>{churn['risk_level'].upper()}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("**Risk Signals:**")
    if churn['signals']:
        for signal in churn['signals']:
            st.caption(f"• {signal}")
    else:
        st.caption("No risk signals detected")

st.divider()

# ============================================================================
# SECTION 4: REVENUE FORECAST
# ============================================================================

st.markdown("### Revenue Forecast (Next 3 Months)")

forecast = forecast_revenue(seller_data, months_ahead=3)

if forecast is not None:
    # Chart data
    chart_data = pd.concat([
        seller_data[['month', 'revenue']].tail(6).rename(columns={'revenue': 'Actual Revenue'}),
        forecast.rename(columns={'predicted_revenue': 'Actual Revenue'}).drop(columns=['month']),
    ], ignore_index=False)
    
    forecast_display = forecast.copy()
    forecast_display['month'] = forecast_display['month'].dt.strftime('%B %Y')
    forecast_display['predicted_revenue'] = forecast_display['predicted_revenue'].apply(lambda x: f"${x/1e6:.2f}M")
    
    st.table(forecast_display)
    
    # Line chart - actual revenue
    recent_revenue = seller_data[['month', 'revenue']].tail(6).copy()
    recent_revenue.columns = ['Month', 'Revenue']
    st.line_chart(data=recent_revenue.set_index('Month'), height=300)
else:
    st.info("Insufficient data for forecast.")

st.divider()

# ============================================================================
# SECTION 5: AI INSIGHT
# ============================================================================

st.markdown("### AI Business Insight")

with st.spinner("Generating AI insight..."):
    ai_insight = generate_ai_insight(selected_seller, health, anomalies, churn)

if ai_insight:
    st.info(ai_insight)
else:
    st.markdown("""
    *AI insight generation requires Anthropic API access. 
    Add your API key via Streamlit secrets for live insights.*
    """)

st.divider()

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("""
---
**Tijartek Seller Intelligence Dashboard** | Data-driven seller performance monitoring
""")
