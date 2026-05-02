import streamlit as st
from supabase import create_client, Client
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Terminal de Gestión Patrimonial", page_icon="💼", layout="wide")

# --- CONEXIÓN SEGURA A SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        st.error("Error: Faltan credenciales en Secrets.")
        st.stop()

supabase = init_connection()

# --- FUNCIONES DE MERCADO (LIMPIEZA DE DATOS NIVEL INSTITUCIONAL) ---
@st.cache_data(ttl=3600)
def get_fx_rate():
    try:
        data = yf.download("USDMXN=X", period="1d", interval="1m", progress=False)
        if not data.empty:
            # Aplanamos columnas por si yfinance devuelve MultiIndex
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return float(data['Close'].iloc[-1])
        return 18.50
    except:
        return 18.50

@st.cache_data(ttl=300)
def get_technical_data(symbol):
    # Descargamos con auto_adjust para evitar problemas de columnas de dividendos
    df = yf.download(symbol, period="1y", interval="1d", auto_adjust=True, progress=False)
    
    if df.empty:
        return None
    
    # CRUCIAL: Aplanar MultiIndex de yfinance para que pandas_ta funcione
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Aseguramos nombres de columnas en minúsculas (requisito de algunas versiones de TA)
    df.columns = [str(col).lower() for col in df.columns]
    
    # Cálculos Técnicos (MACD 12,26,9 y StochRSI 14,3,3)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.stochrsi(length=14, k=3, d=3, append=True)
    
    return df

# --- SISTEMA DE ACCESO (FIX: EVITA DOBLE CLIC) ---
def auth_ui():
    st.sidebar.title("🔐 Acceso Institucional")
    mode = st.sidebar.radio("Seleccione Acción:", ["Entrar", "Registrarse"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Contraseña", type="password")

    if st.sidebar.button("Confirmar"):
        if mode == "Entrar":
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun() # Fuerza el refresco inmediato
            except Exception:
                st.sidebar.error("Credenciales inválidas.")
        else:
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                st.sidebar.success("Registro iniciado. Revisa tu email para confirmar.")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

if "user" not in st.session_state:
    auth_ui()
    st.stop()

# --- SIDEBAR: CONFIGURACIÓN Y REGISTRO DE CAPAS ---
with st.sidebar:
    st.title("🛠️ Operativa")
    current_fx = get_fx_rate()
    st.metric("FX USD/MXN", f"${current_fx:,.4f}")
    
    comision_pct = st.number_input("Comisión Broker (%)", value=0.10, step=0.01) / 100
    
    st.divider()
    with st.form("registro_form", clear_on_submit=True):
        st.write("📥 **Nueva Capa**")
        t_input = st.text_input("Ticker").upper()
        q_input = st.number_input("Cantidad", min_value=1)
        p_input = st.number_input("Precio Bruto (MXN)", min_value=0.01)
        
        if st.form_submit_button("Confirmar Ejecución"):
            # Lógica de Costo Neto (Comisión + IVA)
            friccion = (q_input * p_input) * comision_pct * 1.16
            costo_neto = (q_input * p_input) + friccion
            
            try:
                data = {
                    "user_id": st.session_state.user.id, "ticker": t_input, "shares": q_input,
                    "price_mxn": p_input, "fx_rate": current_fx, "total_net_cost": costo_neto
                }
                supabase.table("positions").insert(data).execute()
                st.success(f"Registrado: {t_input}")
                st.balloons()
            except Exception as e:
                st.error(f"Error en DB: {e}")

    if st.button("Cerrar Sesión"):
        del st.session_state.user
        st.rerun()

# --- DASHBOARD PRINCIPAL ---
st.header("💼 Terminal de Gestión Patrimonial")

# Métricas Top
m1, m2, m3 = st.columns(3)
m1.container(border=True).metric("VALOR DEL PORTAFOLIO", "$53,979.65")
m2.container(border=True).metric("UTILIDAD REALIZADA", "$0.00")
m3.container(border=True).metric("PLUSVALIA NETA", "$4,209.91", "+7.8%")

st.divider()

# Gráfico Técnico con Eje Derecho y Auto-ajuste
st.subheader("📈 Análisis Técnico")
selected_ticker = st.selectbox("Seleccionar Activo:", ["SOXX", "SOXL", "EEM", "NVDA", "AAPL"])

df = get_technical_data(selected_ticker)

if df is not None:
    # 3 Paneles: Precio, MACD, Stoch RSI
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.25, 0.25]
    )

    # Panel 1: Velas
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name="Precio", increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
    ), row=1, col=1)

    # Panel 2: MACD (Asegurando nombres generados por pandas_ta)
    # Buscamos las columnas que empiecen con MACD
    m_col = [c for c in df.columns if 'macd_12_26_9' in c][0]
    s_col = [c for c in df.columns if 'macds_12_26_9' in c][0]
    h_col = [c for c in df.columns if 'macdh_12_26_9' in c][0]

    fig.add_trace(go.Scatter(x=df.index, y=df[m_col], name="MACD", line=dict(color='#2962FF')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df[s_col], name="Signal", line=dict(color='#FF6D00')), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df[h_col], name="Hist"), row=2, col=1)

    # Panel 3: Stoch RSI
    k_col = [c for c in df.columns if 'stochrsik' in c][0]
    d_col = [c for c in df.columns if 'stochrsid' in c][0]

    fig.add_trace(go.Scatter(x=df.index, y=df[k_col], name="%K", line=dict(color='#00E676')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df[d_col], name="%D", line=dict(color='#FF5252', dash='dot')), row=3, col=1)

    # Layout y Ejes (Investing Style)
    fig.update_layout(
        height=800, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=60, t=10, b=10)
    )
    fig.update_yaxes(side="right", fixedrange=False) # Auto-ajuste y Eje derecho
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
    
    st.latex(r"Costo_{Neto} = (Q \times P) + (Q \times P \times \%Com \times 1.16)")
else:
    st.error("Error al recuperar datos técnicos.")