import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh
import json
import os

# --- 1. CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(layout="wide", page_title="Institutional Global Terminal", page_icon="🏛️")
st_autorefresh(interval=60 * 1000, key="market_update")

# Estilos CSS para KPI Tiles con la nueva nomenclatura
st.markdown("""
    <style>
    .kpi-card { background-color: #1e2130; padding: 20px; border-radius: 10px; border-left: 5px solid #00e1ff; text-align: center; margin-bottom: 10px; }
    .kpi-val { font-size: 26px; font-weight: bold; color: white; }
    .kpi-lbl { font-size: 13px; color: #808495; text-transform: uppercase; letter-spacing: 1px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GESTIÓN DE DATOS Y PERSISTENCIA ---
DB_FILE = "portfolio.json"
IVA = 0.16

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"positions": {}, "realized_pnl": []}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

def clean_data(df):
    if df is not None and not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(col).strip() for col in df.columns]
    return df

db = load_db()

# --- 3. MOTORES DE CÁLCULO ---
@st.cache_data(ttl=60)
def get_fx_rate():
    try:
        data = yf.download("USDMXN=X", period="1d", interval="1m", auto_adjust=True)
        data = clean_data(data)
        val = data['Close'].iloc[-1]
        return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)
    except: return 18.50 

@st.cache_data(ttl=60)
def get_live_market(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", auto_adjust=True)
        return clean_data(df)
    except: return None

# --- 4. BARRA LATERAL: CONFIGURACIÓN Y REGISTRO ---
st.sidebar.title("🛠️ Configuración")
fx_now = get_fx_rate()
st.sidebar.metric("Tipo de Cambio USD/MXN", f"${fx_now:,.4f}")

comm_input = st.sidebar.number_input("Comisión Broker (%)", min_value=0.0, value=0.25, step=0.01)
f_current = (comm_input / 100) * (1 + IVA)

st.sidebar.divider()
st.sidebar.subheader("📥 Registro de Capas")
with st.sidebar.form("form_compra", clear_on_submit=True):
    t_in = st.text_input("Ticker").upper()
    q_in = st.number_input("Cantidad", min_value=1, step=1)
    p_in = st.number_input("Precio Compra Bruto (MXN)", min_value=0.01)
    if st.form_submit_button("Confirmar Compra"):
        if t_in:
            if t_in not in db["positions"]:
                db["positions"][t_in] = {"shares": 0, "total_gross_cost": 0, "total_net_cost": 0, "layers": []}
            p = db["positions"][t_in]
            p["shares"] += q_in
            p["total_gross_cost"] += (q_in * p_in)
            p["total_net_cost"] += (q_in * p_in) * (1 + f_current)
            p["layers"].append({"qty": q_in, "p_gross": p_in, "fx": fx_now, "date": str(pd.Timestamp.now().date())})
            save_db(db); st.rerun()

# --- 5. LÓGICA DE MONITOREO ---
active_data = {}
total_nav = 0.0

if db["positions"]:
    for t, info in db["positions"].items():
        df_live = get_live_market(t)
        if df_live is not None:
            p_usd = float(df_live['Close'].iloc[-1].iloc[0]) if isinstance(df_live['Close'].iloc[-1], pd.Series) else float(df_live['Close'].iloc[-1])
            prev_usd = float(df_live['Close'].iloc[-2].iloc[0]) if isinstance(df_live['Close'].iloc[-2], pd.Series) else float(df_live['Close'].iloc[-2])
            theo_mxn = p_usd * fx_now
            v_mkt = theo_mxn * info["shares"]
            total_nav += v_mkt
            active_data[t] = {"p_usd": p_usd, "prev_usd": prev_usd, "theo_mxn": theo_mxn, "v_mkt": v_mkt, "df": df_live}

# --- 6. HEADER: KPI TILES (Nombres Actualizados) ---
st.title("💼 Terminal de Gestión Patrimonial")
k1, k2, k3 = st.columns(3)
realized_sum = sum(i["amount"] for i in db["realized_pnl"])
unrealized_net = sum((active_data[t]["v_mkt"]*(1-f_current)) - db["positions"][t]["total_net_cost"] for t in active_data) if active_data else 0.0

with k1: st.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>VALOR DEL PORTAFOLIO ACTUAL</div><div class='kpi-val'>${total_nav:,.2f}</div></div>", unsafe_allow_html=True)
with k2: st.markdown(f"<div class='kpi-card' style='border-left-color: #00ff88;'><div class='kpi-lbl'>UTILIDAD/PERDIDA REALIZADA</div><div class='kpi-val'>${realized_sum:,.2f}</div></div>", unsafe_allow_html=True)
with k3: st.markdown(f"<div class='kpi-card' style='border-left-color: #ff9900;'><div class='kpi-lbl'>PLUSVALIA/MINUSVALIA NETA</div><div class='kpi-val'>${unrealized_net:,.2f}</div></div>", unsafe_allow_html=True)

st.divider()

# --- 7. MONITOREO DINÁMICO ---
st.subheader("📊 Monitoreo de Posiciones Activas")
if not db["positions"]:
    st.info("Sin posiciones activas. Registra una compra en la barra lateral.")
else:
    for t, info in db["positions"].items():
        if t in active_data:
            m = active_data[t]
            weight = (m["v_mkt"] / total_nav) * 100
            be_usd = info["total_net_cost"] / (info["shares"] * fx_now * (1 - f_current))
            net_pnl = (m["v_mkt"] * (1 - f_current)) - info["total_net_cost"]
            net_pct = (net_pnl / info["total_net_cost"]) * 100
            
            v_d = ((m["p_usd"] / m["prev_usd"]) - 1) * 100
            status = "🟢" if net_pnl >= 0 else "🔴"
            h_text = f"{t} | USD: ${m['p_usd']:,.2f} ({v_d:+.2f}%) | Real: {status} ${net_pnl:,.2f} ({net_pct:.2f}%) | Peso: {weight:.1f}%"
            
            with st.expander(h_text):
                c_data, c_act = st.columns([0.7, 0.3])
                with c_data:
                    st.write("**Desglose de Capas (MXN):**")
                    st.dataframe(pd.DataFrame(info["layers"]), use_container_width=True)
                    st.write(f"**Breakeven USD Sugerido:** `${be_usd:,.2f}`")
                
                with c_act:
                    st.write("**Acciones:**")
                    if st.button("🗑️ Eliminar Activo", key=f"del_{t}"):
                        del db["positions"][t]; save_db(db); st.rerun()
                    
                    with st.expander("📤 Registrar Venta"):
                        with st.form(f"sell_{t}"):
                            q_s = st.number_input("Títulos", 1, info["shares"])
                            p_s = st.number_input("Precio Venta Bruto (MXN)")
                            if st.form_submit_button("Ejecutar Venta"):
                                rev_n = (q_s * p_s) * (1 - f_current)
                                cost_n = q_s * (info["total_net_cost"] / info["shares"])
                                db["realized_pnl"].append({"ticker": t, "amount": round(rev_n - cost_n, 2), "date": str(pd.Timestamp.now().date())})
                                avg_g = info["total_gross_cost"] / info["shares"]
                                avg_n = info["total_net_cost"] / info["shares"]
                                info["shares"] -= q_s
                                info["total_gross_cost"] -= (q_s * avg_g)
                                info["total_net_cost"] -= (q_s * avg_n)
                                if info["shares"] <= 0: del db["positions"][t]
                                save_db(db); st.rerun()

    # --- 8. ANÁLISIS TÉCNICO ---
    st.divider()
    t_tech = st.selectbox("Selecciona para Gráfico Técnico:", options=list(db["positions"].keys()))
    df_t = active_data[t_tech]["df"]
    
    if df_t is not None:
        df_t.ta.macd(fast=12, slow=26, signal=9, append=True)
        df_t.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
        
        m_l, m_s, m_h = "MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9"
        s_k, s_d = "STOCHRSIk_14_14_3_3", "STOCHRSId_14_14_3_3"

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.5, 0.25, 0.25])
        fig.add_trace(go.Candlestick(x=df_t.index, open=df_t['Open'], high=df_t['High'], low=df_t['Low'], close=df_t['Close'], name="Velas"), row=1, col=1)
        
        if m_l in df_t.columns:
            fig.add_trace(go.Scatter(x=df_t.index, y=df_t[m_l], name="MACD", line=dict(color='#00e1ff', width=1.5)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_t.index, y=df_t[m_s], name="Signal", line=dict(color='#ff9900', width=1.5)), row=2, col=1)
            h_colors = ['#00ff88' if v >= 0 else '#ff4b4b' for v in df_t[m_h]]
            fig.add_trace(go.Bar(x=df_t.index, y=df_t[m_h], name="Hist", marker_color=h_colors, opacity=0.4), row=2, col=1)

        if s_k in df_t.columns:
            fig.add_trace(go.Scatter(x=df_t.index, y=df_t[s_k], name="Stoch K", line=dict(color='#00ff88', width=1.5)), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_t.index, y=df_t[s_d], name="Stoch D", line=dict(color='#ff4b4b', width=1.5, dash='dot')), row=3, col=1)
            fig.add_hline(y=80, line_dash="dash", line_color="gray", opacity=0.5, row=3, col=1)
            fig.add_hline(y=20, line_dash="dash", line_color="gray", opacity=0.5, row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", showlegend=False, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)