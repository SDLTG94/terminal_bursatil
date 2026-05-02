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
        st.error("Faltan credenciales en la bóveda de seguridad (Secrets).")
        st.stop()

supabase = init_connection()

# --- FUNCIONES DE MERCADO (0.1% Style) ---
@st.cache_data(ttl=3600)
def get_fx_rate():
    try:
        ticker = yf.Ticker("USDMXN=X")
        data = ticker.history(period="1d")
        return float(data['Close'].iloc[-1]) if not data.empty else 18.50
    except:
        return 18.50

@st.cache_data(ttl=300)
def get_technical_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d")
    if df.empty:
        return None
    
    # Cálculos Técnicos Institucionales
    # MACD (12, 26, 9)
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    # Stochastic RSI (14, 3, 3)
    stoch_rsi = df.ta.stochrsi(length=14, k=3, d=3)
    
    # Concatenar resultados
    df = pd.concat([df, macd, stoch_rsi], axis=1)
    return df

# --- LÓGICA DE ACCESO ---
if "user" not in st.session_state:
    st.sidebar.title("🔐 Acceso")
    email = st.sidebar.text_input("Usuario")
    password = st.sidebar.text_input("Contraseña", type="password")
    if st.sidebar.button("Entrar"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except:
            st.sidebar.error("Error de autenticación.")
    st.stop()

# --- SIDEBAR: CONFIGURACIÓN Y OPERATIVA ---
with st.sidebar:
    st.title("🛠️ Configuración")
    current_fx = get_fx_rate()
    st.metric("Tipo de Cambio USD/MXN", f"${current_fx:,.4f}")
    
    comision_pct = st.number_input("Comisión Broker (%)", value=0.25, step=0.01) / 100
    iva_comision = 0.16
    
    st.divider()
    st.title("📥 Registro de Capas")
    with st.form("registro_form", clear_on_submit=True):
        t_input = st.text_input("Ticker").upper()
        q_input = st.number_input("Cantidad", min_value=1)
        p_input = st.number_input("Precio Compra Bruto (MXN)", min_value=0.01)
        
        if st.form_submit_button("Confirmar Compra"):
            costo_bruto = q_input * p_input
            friccion = costo_bruto * comision_pct * (1 + iva_comision)
            costo_neto = costo_bruto + friccion
            
            try:
                data = {
                    "user_id": st.session_state.user.id, "ticker": t_input, "shares": q_input,
                    "price_mxn": p_input, "fx_rate": current_fx, "total_net_cost": costo_neto
                }
                supabase.table("positions").insert(data).execute()
                st.success(f"Registrado: {t_input}")
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e}")

# --- DASHBOARD PRINCIPAL ---
st.header("💼 Terminal de Gestión Patrimonial")

# Métricas de Portafolio
m1, m2, m3 = st.columns(3)
m1.container(border=True).metric("VALOR DEL PORTAFOLIO ACTUAL", "$53,979.65")
m2.container(border=True).metric("UTILIDAD/PERDIDA REALIZADA", "$0.00")
m3.container(border=True).metric("PLUSVALIA/MINUSVALIA NETA", "$4,209.91", "+7.8%")

st.divider()

# Gráfico Técnico Avanzado
st.subheader("📈 Análisis Técnico Institucional")
selected_ticker = st.selectbox("Selecciona Activo:", ["SOXX", "SOXL", "EEM", "NVDA", "AAPL"])

df = get_technical_data(selected_ticker)

if df is not None:
    # 1. Crear Subplots: Precio/Vol, MACD, Stoch RSI
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.25, 0.25]
    )

    # PANEL 1: Velas Japonesas
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="Precio", increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
    ), row=1, col=1)

    # Volumen (Superpuesto en Panel 1)
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'], name="Volumen",
        marker_color='rgba(128, 128, 128, 0.2)', showlegend=False
    ), row=1, col=1)

    # PANEL 2: MACD
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], name="MACD", line=dict(color='#2962FF', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], name="Signal", line=dict(color='#FF6D00', width=1.5)), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['MACDh_12_26_9'], name="Hist", marker_color='rgba(120, 120, 120, 0.5)'), row=2, col=1)

    # PANEL 3: Stoch RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['STOCHRSIk_14_14_3_3'], name="%K", line=dict(color='#00E676', width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['STOCHRSId_14_14_3_3'], name="%D", line=dict(color='#FF5252', width=1.5, dash='dot')), row=3, col=1)
    # Líneas de Sobrecompra/Venta
    fig.add_hline(y=80, line_dash="dash", line_color="rgba(255,255,255,0.2)", row=3, col=1)
    fig.add_hline(y=20, line_dash="dash", line_color="rgba(255,255,255,0.2)", row=3, col=1)

    # Configuración de Layout (Investing Style)
    fig.update_layout(
        height=800,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=60, t=10, b=10) # Margen derecho para el eje
    )

    # Eje Y a la Derecha y Auto-ajuste
    fig.update_yaxes(side="right", gridcolor="rgba(128,128,128,0.1)", fixedrange=False)
    fig.update_xaxes(gridcolor="rgba(128,128,128,0.1)")

    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
    
    st.latex(r"Costo_{Neto} = (Q \times P) + (Q \times P \times \%Com \times 1.16)")
else:
    st.error("No se pudieron recuperar datos para el Ticker seleccionado.")