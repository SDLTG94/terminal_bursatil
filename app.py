import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(layout="wide", page_title="Institutional Global Terminal", page_icon="🏛️")

# Estilos CSS para KPI Tiles (Fiel a tu dashboard local)
st.markdown("""
    <style>
    .kpi-card { background-color: #1e2130; padding: 20px; border-radius: 10px; border-left: 5px solid #00e1ff; text-align: center; margin-bottom: 10px; }
    .kpi-val { font-size: 26px; font-weight: bold; color: white; }
    .kpi-lbl { font-size: 13px; color: #808495; text-transform: uppercase; letter-spacing: 1px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN Y SEGURIDAD ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

def auth_ui():
    st.sidebar.title("🔐 Acceso")
    mode = st.sidebar.radio("Acción:", ["Entrar", "Registrarse"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Contraseña", type="password")
    
    if st.sidebar.button("Confirmar"):
        try:
            if mode == "Entrar":
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun() # Fix: Acceso inmediato sin doble clic
            else:
                supabase.auth.sign_up({"email": email, "password": password})
                st.sidebar.success("Registro enviado. Confirma tu correo.")
        except: st.sidebar.error("Error de credenciales.")

if "user" not in st.session_state:
    auth_ui()
    st.stop()

# --- 3. MOTORES DE CÁLCULO ---
def clean_df(df):
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(col).lower().strip() for col in df.columns]
    return df

@st.cache_data(ttl=60)
def get_fx_rate():
    try:
        data = yf.download("USDMXN=X", period="1d", interval="1m", progress=False)
        data = clean_df(data)
        return float(data['close'].iloc[-1])
    except: return 18.50

@st.cache_data(ttl=300)
def get_market_data(ticker):
    # Cargamos 5 años para permitir zoom-out real como en Investing
    df = yf.download(ticker, period="5y", interval="1d", auto_adjust=True, progress=False)
    df = clean_df(df)
    if df is not None:
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
    return df

# --- 4. CARGA DE PORTAFOLIO (Mapping a Supabase) ---
user_id = st.session_state.user.id
try:
    res = supabase.table("positions").select("*").eq("user_id", user_id).execute()
    positions_raw = res.data
except: positions_raw = []

portfolio = {}
for p in positions_raw:
    t = p["ticker"]
    if t not in portfolio:
        portfolio[t] = {"shares": 0, "total_gross_cost": 0, "total_net_cost": 0, "layers": []}
    portfolio[t]["shares"] += p["shares"]
    portfolio[t]["total_gross_cost"] += p["total_gross_cost"]
    portfolio[t]["total_net_cost"] += p["total_net_cost"]
    portfolio[t]["layers"].append({
        "qty": p["shares"], 
        "price_gross": p["total_gross_cost"] / p["shares"], 
        "date": p.get("created_at", "")[:10]
    })

# --- 5. SIDEBAR: OPERATIVA ---
with st.sidebar:
    st.title("🛠️ Configuración")
    fx_now = get_fx_rate()
    st.sidebar.metric("Tipo de Cambio USD/MXN", f"${fx_now:,.4f}")
    comm_pct = st.number_input("Comisión Broker (%)", value=0.25, step=0.01) / 100
    f_total = comm_pct * 1.16

    st.divider()
    st.subheader("📥 Registro de Capas")
    with st.form("compra_form", clear_on_submit=True):
        t_in = st.text_input("Ticker").upper()
        q_in = st.number_input("Cantidad", min_value=1)
        p_in = st.number_input("Precio Compra Bruto (MXN)", min_value=0.01)
        if st.form_submit_button("Confirmar Compra"):
            cost_neto = (q_in * p_in) * (1 + f_total)
            try:
                # Fix APIError: Usamos exactamente las columnas de tu esquema de Supabase
                supabase.table("positions").insert({
                    "user_id": user_id, 
                    "ticker": t_in, 
                    "shares": float(q_in),
                    "total_gross_cost": float(q_in * p_in), 
                    "total_net_cost": float(cost_neto)
                }).execute()
                st.rerun()
            except Exception as e:
                st.error("Error en base de datos. Revisa las columnas en Supabase.")

    if st.button("Cerrar Sesión"):
        del st.session_state.user
        st.rerun()

# --- 6. PROCESAMIENTO DE DATOS ---
active_data = {}
total_nav = 0.0
for t, info in portfolio.items():
    df = get_market_data(t)
    if df is not None:
        p_usd = float(df['close'].iloc[-1])
        v_mkt = p_usd * fx_now * info["shares"]
        total_nav += v_mkt
        active_data[t] = {"p_usd": p_usd, "v_mkt": v_mkt, "df": df, "prev_usd": float(df['close'].iloc[-2])}

# --- 7. DASHBOARD: KPI TILES ---
st.title("💼 Terminal de Gestión Patrimonial")
k1, k2, k3 = st.columns(3)
unrealized_net = sum((active_data[t]["v_mkt"]*(1-f_total)) - portfolio[t]["total_net_cost"] for t in active_data) if active_data else 0.0

with k1: st.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>VALOR DEL PORTAFOLIO ACTUAL</div><div class='kpi-val'>${total_nav:,.2f}</div></div>", unsafe_allow_html=True)
with k2: st.markdown(f"<div class='kpi-card' style='border-left-color: #00ff88;'><div class='kpi-lbl'>UTILIDAD/PERDIDA REALIZADA</div><div class='kpi-val'>$0.00</div></div>", unsafe_allow_html=True)
with k3: st.markdown(f"<div class='kpi-card' style='border-left-color: #ff9900;'><div class='kpi-lbl'>PLUSVALIA/MINUSVALIA NETA</div><div class='kpi-val'>${unrealized_net:,.2f}</div></div>", unsafe_allow_html=True)

st.divider()

# --- 8. MONITOREO DE POSICIONES (Desglose de Capas) ---
st.subheader("📊 Monitoreo de Posiciones Activas")
if not portfolio:
    st.info("Sin posiciones activas. Registra una compra en la barra lateral.")
else:
    for t, info in portfolio.items():
        if t in active_data:
            m = active_data[t]
            net_pnl = (m["v_mkt"] * (1 - f_total)) - info["total_net_cost"]
            be_usd = info["total_net_cost"] / (info["shares"] * fx_now * (1 - f_total))
            status = "🟢" if net_pnl >= 0 else "🔴"
            weight = (m["v_mkt"] / total_nav) * 100
            v_d = ((m["p_usd"] / m["prev_usd"]) - 1) * 100
            
            h_text = f"{t} | USD: ${m['p_usd']:,.2f} ({v_d:+.2f}%) | Real: {status} ${net_pnl:,.2f} | Peso: {weight:.1f}%"
            with st.expander(h_text):
                col_df, col_act = st.columns([0.7, 0.3])
                with col_df:
                    st.write("**Desglose de Capas (MXN):**")
                    st.dataframe(pd.DataFrame(info["layers"]), use_container_width=True)
                    st.write(f"**Breakeven USD Sugerido:** `${be_usd:,.2f}`")
                with col_act:
                    if st.button("🗑️ Eliminar Activo", key=f"del_{t}"):
                        supabase.table("positions").delete().eq("user_id", user_id).eq("ticker", t).execute()
                        st.rerun()

# --- 9. ANÁLISIS TÉCNICO (Plotly Eje Derecho + Auto-ajuste) ---
st.divider()
t_list = list(portfolio.keys()) if portfolio else ["SOXX"]
t_tech = st.selectbox("Selecciona para Gráfico Técnico:", options=t_list)
df_t = get_market_data(t_tech)

if df_t is not None:
    # Subplots para evitar el aplanamiento de las velas por el volumen
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25], specs=[[{"secondary_y": True}], [{}], [{}]])
    
    # 1. Velas Japonesas
    fig.add_trace(go.Candlestick(x=df_t.index, open=df_t['open'], high=df_t['high'], low=df_t['low'], close=df_t['close'], name="Precio"), row=1, col=1, secondary_y=False)
    
    # Volumen en eje secundario para no aplastar el precio
    fig.add_trace(go.Bar(x=df_t.index, y=df_t['volume'], name="Volumen", marker_color='rgba(128,128,128,0.2)'), row=1, col=1, secondary_y=True)
    
    # 2. MACD
    m_c = [c for c in df_t.columns if 'macd_12_26_9' in c]
    s_c = [c for c in df_t.columns if 'macds' in c]
    h_c = [c for c in df_t.columns if 'macdh' in c]
    if m_c:
        fig.add_trace(go.Scatter(x=df_t.index, y=df_t[m_c[0]], name="MACD", line=dict(color='#00e1ff')), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_t.index, y=df_t[s_c[0]], name="Signal", line=dict(color='#ff9900')), row=2, col=1)
        fig.add_trace(go.Bar(x=df_t.index, y=df_t[h_c[0]], name="Hist"), row=2, col=1)

    # 3. Stoch RSI
    k_c = [c for c in df_t.columns if 'stochrsik' in c]
    d_c = [c for c in df_t.columns if 'stochrsid' in c]
    if k_c:
        fig.add_trace(go.Scatter(x=df_t.index, y=df_t[k_c[0]], name="%K", line=dict(color='#00ff88')), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_t.index, y=df_t[d_c[0]], name="%D", line=dict(color='#ff4b4b', dash='dot')), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=60, t=10, b=10))
    fig.update_yaxes(side="right", fixedrange=False, gridcolor="rgba(128,128,128,0.1)")
    fig.update_yaxes(showticklabels=False, secondary_y=True, row=1, col=1) # Ocultamos ticks de volumen
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})