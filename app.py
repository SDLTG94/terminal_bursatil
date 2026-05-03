import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client, Client
import streamlit.components.v1 as components
import json

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(layout="wide", page_title="Institutional Global Terminal", page_icon="🏛️")

st.markdown("""
    <style>
    .kpi-card { background-color: #1e2130; padding: 20px; border-radius: 10px; border-left: 5px solid #00e1ff; text-align: center; margin-bottom: 10px; }
    .kpi-val { font-size: 26px; font-weight: bold; color: white; }
    .kpi-lbl { font-size: 13px; color: #808495; text-transform: uppercase; letter-spacing: 1px; }
    .floating-agent { position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: transparent; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# --- 3. GESTIÓN DE SESIÓN ---
if "user" not in st.session_state:
    st.sidebar.title("🔐 Acceso")
    auth_mode = st.sidebar.radio("Acción:", ["Entrar", "Registrarse"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Contraseña", type="password")
    if st.sidebar.button("Confirmar Acceso"):
        try:
            if auth_mode == "Entrar":
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state.user = res.user
                    st.rerun()
            else:
                supabase.auth.sign_up({"email": email, "password": password})
                st.sidebar.success("Registro enviado. Confirma tu correo.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
    st.stop()

# --- 4. MOTORES DE CÁLCULO ---
def clean_df(df):
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
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
    df = yf.download(ticker, period="5y", interval="1d", auto_adjust=True, progress=False)
    df = clean_df(df)
    if df is not None:
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
        df.columns = [c.lower() for c in df.columns]
    return df

# --- 5. CARGA DE DATOS (VERSION 4.1) ---
user_id = st.session_state.user.id
try:
    res_pos = supabase.table("positions").select("*").eq("user_id", user_id).execute()
    positions_raw = res_pos.data
    res_trades = supabase.table("trades").select("amount").eq("user_id", user_id).execute()
    realized_sum = sum(item["amount"] for item in res_trades.data)
except: 
    positions_raw = []
    realized_sum = 0.0

portfolio = {}
for p in positions_raw:
    t = p["ticker"]
    if t not in portfolio:
        portfolio[t] = {"shares": 0, "total_gross_cost": 0, "total_net_cost": 0, "layers": [], "ids": []}
    portfolio[t]["shares"] += p["shares"]
    portfolio[t]["total_gross_cost"] += p["total_gross_cost"]
    portfolio[t]["total_net_cost"] += p["total_net_cost"]
    portfolio[t]["ids"].append(p["id"])
    portfolio[t]["layers"].append({"qty": p["shares"], "p_gross": p["total_gross_cost"]/p["shares"], "date": p.get("created_at", "")[:10]})

# --- 6. SIDEBAR: OPERATIVA ---
with st.sidebar:
    st.title("🛠️ Configuración")
    fx_now = get_fx_rate()
    st.metric("FX USD/MXN", f"${fx_now:,.4f}")
    comm_pct = st.number_input("Comisión Broker (%)", value=0.25, step=0.01) / 100
    f_total = comm_pct * 1.16
    st.divider()
    with st.form("form_compra", clear_on_submit=True):
        t_final = st.text_input("Ticker").upper().strip()
        q_in = st.number_input("Cantidad", min_value=1)
        p_in = st.number_input("Precio Bruto (MXN)", min_value=0.01)
        if st.form_submit_button("Confirmar Compra"):
            if t_final:
                c_neto = float((q_in * p_in) * (1 + f_total))
                supabase.table("positions").insert({"user_id": user_id, "ticker": t_final, "shares": float(q_in), "total_gross_cost": float(q_in*p_in), "total_net_cost": c_neto}).execute()
                st.rerun()
    if st.button("Cerrar Sesión"):
        del st.session_state.user
        st.rerun()

# --- 7. PROCESAMIENTO DE MERCADO ---
active_data = {}
total_nav = 0.0
for t, info in portfolio.items():
    df = get_market_data(t)
    if df is not None:
        p_usd = float(df['close'].iloc[-1])
        v_mkt = p_usd * fx_now * info["shares"]
        total_nav += v_mkt
        active_data[t] = {"p_usd": p_usd, "v_mkt": v_mkt, "df": df, "prev_usd": float(df['close'].iloc[-2])}

# --- 8. DASHBOARD KPI (VERSION 4.1) ---
st.title("💼 Terminal de Gestión Patrimonial")
k1, k2, k3 = st.columns(3)
unrealized_net = sum((active_data[t]["v_mkt"]*(1-f_total)) - portfolio[t]["total_net_cost"] for t in active_data) if active_data else 0.0
with k1: st.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>VALOR PORTAFOLIO</div><div class='kpi-val'>${total_nav:,.2f}</div></div>", unsafe_allow_html=True)
with k2: st.markdown(f"<div class='kpi-card' style='border-left-color: #00ff88;'><div class='kpi-lbl'>UTILIDAD REALIZADA</div><div class='kpi-val'>${realized_sum:,.2f}</div></div>", unsafe_allow_html=True)
with k3: st.markdown(f"<div class='kpi-card' style='border-left-color: #ff9900;'><div class='kpi-lbl'>PLUSVALIA NETA</div><div class='kpi-val'>${unrealized_net:,.2f}</div></div>", unsafe_allow_html=True)

# --- 9. MONITOREO Y VENTAS ---
st.subheader("📊 Monitoreo de Posiciones Activas")
if portfolio:
    for t, info in portfolio.items():
        if t in active_data:
            m = active_data[t]
            net_pnl = (m["v_mkt"] * (1 - f_total)) - info["total_net_cost"]
            pnl_pct = (net_pnl / info["total_net_cost"]) * 100 if info["total_net_cost"] > 0 else 0
            h_text = f"{t} | USD: ${m['p_usd']:,.2f} | Real: ${net_pnl:,.2f} ({pnl_pct:+.2f}%)"
            with st.expander(h_text):
                st.write(f"Breakeven USD: ${info['total_net_cost']/(info['shares']*fx_now*(1-f_total)):,.2f}")

# --- 10. GRÁFICO TÉCNICO (VERSION 4.1) ---
st.divider()
t_tech = st.selectbox("Selecciona para Gráfico Técnico:", options=list(portfolio.keys()) if portfolio else ["SOXX"])
df_t = get_market_data(t_tech)
if df_t is not None:
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.15, 0.22, 0.23])
    fig.add_trace(go.Candlestick(x=df_t.index, open=df_t['open'], high=df_t['high'], low=df_t['low'], close=df_t['close'], name="Precio"), row=1, col=1)
    k_list = [c for c in df_t.columns if 'stochrsi' in c.lower() and 'k' in c.lower()]
    if k_list:
        fig.add_trace(go.Scatter(x=df_t.index, y=df_t[k_list[0]], name="%K", line=dict(color='#00ff88')), row=4, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color="white", row=4, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="white", row=4, col=1)
    fig.update_layout(height=800, template="plotly_dark", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 10.5 BLOQUE ESTRATÉGICO: RESUMEN PARA TOBIAS ---
resumen_dict = {}
if portfolio:
    for ticker, info in portfolio.items():
        if ticker in active_data:
            m = active_data[ticker]
            pnl_neto = ((m["v_mkt"] * (1 - f_total)) - info["total_net_cost"])
            pnl_pct = (pnl_neto / info["total_net_cost"]) * 100 if info["total_net_cost"] > 0 else 0
            resumen_dict[ticker] = {
                "títulos": int(info['shares']),
                "costo_promedio_mxn": round(info['total_net_cost']/info['shares'], 2),
                "rendimiento_neto_pct": f"{pnl_pct:+.2f}%",
                "precio_actual_usd": round(m['p_usd'], 2)
            }
    contexto_tobias = json.dumps(resumen_dict)
else:
    contexto_tobias = "Cartera vacía."

# --- 11. AGENTE FLOTANTE TOBIAS (DYNAMIC VARIABLES) ---
safe_context = contexto_tobias.replace('"', '\\"')
tobias_html = f"""
<div class="floating-agent">
    <elevenlabs-convai 
        agent-id="agent_4901kqp1gs5bfqstk9zw2p61rpe8"
        dynamic-variables='{{"portfolio_context": "{safe_context}"}}'>
    </elevenlabs-convai>
    <script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async type="text/javascript"></script>
</div>
"""
components.html(tobias_html, height=500)