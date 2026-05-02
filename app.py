import streamlit as st
from supabase import create_client, Client
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Terminal de Gestión Patrimonial", page_icon="💼", layout="wide")

# --- CONEXIÓN SEGURA ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        st.error("Error: Credenciales no encontradas en Secrets.")
        st.stop()

supabase = init_connection()

# --- NORMALIZACIÓN DE DATOS (Protocolo de Integridad) ---
@st.cache_data(ttl=300)
def get_technical_data(symbol):
    # Descarga limpia sin MultiIndex
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    
    if df.empty:
        return None
    
    # 1. Aplanamiento de MultiIndex (Fix para yfinance 0.2+)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    
    # 2. Estandarización de nombres a minúsculas
    df.columns = [str(col).lower() for col in df.columns]
    
    # 3. Limpieza de valores nulos para cálculos precisos
    df = df.dropna()

    # 4. Cálculo de Indicadores (MACD y Stoch RSI)
    # Se añade 'append=True' para integrar los resultados al dataframe original
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.stochrsi(length=14, k=3, d=3, append=True)
    
    # Limpiamos nulos generados por las medias móviles al inicio
    return df.dropna()

@st.cache_data(ttl=3600)
def get_fx_rate():
    try:
        data = yf.download("USDMXN=X", period="1d", interval="1m", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        return float(data['Close'].iloc[-1])
    except:
        return 18.50

# --- INTERFAZ DE ACCESO Y REGISTRO ---
def auth_ui():
    st.sidebar.title("🔐 Acceso Institucional")
    # Selector de modo para permitir nuevos usuarios
    auth_mode = st.sidebar.radio("Acción", ["Iniciar Sesión", "Registrarse"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Contraseña", type="password")

    if st.sidebar.button("Confirmar"):
        if auth_mode == "Iniciar Sesión":
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun()
            except:
                st.sidebar.error("Credenciales incorrectas.")
        else:
            try:
                # El registro envía un correo de confirmación por defecto
                supabase.auth.sign_up({"email": email, "password": password})
                st.sidebar.success("Registro enviado. Confirma tu correo.")
            except Exception as e:
                st.sidebar.error(f"Fallo en registro: {e}")

if "user" not in st.session_state:
    auth_ui()
    st.stop()

# --- SIDEBAR OPERATIVO ---
with st.sidebar:
    st.title("🛠️ Operativa")
    current_fx = get_fx_rate()
    st.metric("FX USD/MXN", f"${current_fx:,.4f}")
    
    comision_pct = st.number_input("Comisión Broker (%)", value=0.10, step=0.01) / 100
    
    st.divider()
    with st.form("registro_form", clear_on_submit=True):
        st.write("📥 **Registro de Capa**")
        t_input = st.text_input("Ticker").upper()
        q_input = st.number_input("Cantidad", min_value=1)
        p_input = st.number_input("Precio MXN", min_value=0.01)
        
        if st.form_submit_button("Ejecutar"):
            # Cálculo Neto tras comisiones e IVA
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
                st.error(f"Error DB: {e}")

    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state.user
        st.rerun()

# --- DASHBOARD ---
st.header("💼 Terminal de Gestión Patrimonial")

# Métricas (Placeholder para agregación real)
m1, m2, m3 = st.columns(3)
m1.container(border=True).metric("VALOR PORTAFOLIO", "$53,979.65")
m2.container(border=True).metric("P&L REALIZADO", "$0.00")
m3.container(border=True).metric("PLUSVALÍA NETA", "$4,209.91", "+7.8%")

st.divider()

# ANÁLISIS TÉCNICO
st.subheader("📈 Gráfico Institucional")
selected_ticker = st.selectbox("Activo:", ["SOXX", "SOXL", "EEM", "NVDA", "AAPL"])

df = get_technical_data(selected_ticker)

if df is not None:
    # Definición de Subplots
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25]
    )

    # 1. Velas
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name="Precio"
    ), row=1, col=1)

    # 2. MACD (Búsqueda segura de columnas)
    m_cols = [c for c in df.columns if 'macd' in c and 'h' not in c and 's' not in c]
    s_cols = [c for c in df.columns if 'macds' in c]
    h_cols = [c for c in df.columns if 'macdh' in c]

    if m_cols and s_cols and h_cols:
        fig.add_trace(go.Scatter(x=df.index, y=df[m_cols[0]], name="MACD", line=dict(color='#2962FF')), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[s_cols[0]], name="Signal", line=dict(color='#FF6D00')), row=2, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df[h_cols[0]], name="Hist"), row=2, col=1)

    # 3. Stoch RSI
    k_cols = [c for c in df.columns if 'stochrsik' in c]
    d_cols = [c for c in df.columns if 'stochrsid' in c]

    if k_cols and d_cols:
        fig.add_trace(go.Scatter(x=df.index, y=df[k_cols[0]], name="%K", line=dict(color='#00E676')), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[d_cols[0]], name="%D", line=dict(color='#FF5252', dash='dot')), row=3, col=1)

    # Layout Investing Style
    fig.update_layout(
        height=800, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=60, t=10, b=10)
    )
    fig.update_yaxes(side="right", fixedrange=False)
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
    
    # Formula de Costo Neto (Neto de Comisiones y IVA)
    st.latex(r"Costo_{Neto} = (Q \times P) + (Q \times P \times \%Com \times 1.16)")
else:
    st.error("No se encontraron datos para el ticker.")