import streamlit as st
from supabase import create_client, Client
import yfinance as yf

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Terminal de Gestión Patrimonial", page_icon="💼", layout="wide")

# --- CONEXIÓN SEGURA ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- FUNCIONES AUTOMATIZADAS ---
@st.cache_data(ttl=3600)  # Actualiza el FX cada hora
def get_fx_rate():
    try:
        data = yf.download("USDMXN=X", period="1d", interval="1m")
        return data['Close'].iloc[-1]
    except:
        return 17.50  # Fallback en caso de error de red

# --- LÓGICA DE SESIÓN ---
if "user" not in st.session_state:
    # Simulación de Login (Cámbialo por tu lógica de Auth anterior si es necesario)
    st.sidebar.title("🔐 Acceso")
    email = st.sidebar.text_input("Correo")
    password = st.sidebar.text_input("Contraseña", type="password")
    if st.sidebar.button("Entrar"):
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.rerun()
    st.stop()

# --- SIDEBAR: CONFIGURACIÓN Y REGISTRO ---
with st.sidebar:
    st.title("🛠️ Configuración")
    
    # Automatización del FX
    current_fx = get_fx_rate()
    st.metric("Tipo de Cambio USD/MXN", f"${current_fx:,.4f}")
    
    # Configuración Global de Comisión
    comision_pct = st.number_input("Comisión Broker (%)", value=0.25, step=0.01) / 100
    iva_comision = 0.16
    
    st.divider()
    
    st.title("📥 Registro de Capas")
    with st.form("registro_form"):
        ticker_input = st.text_input("Ticker").upper()
        qty_input = st.number_input("Cantidad", min_value=1, step=1)
        price_input = st.number_input("Precio Compra Bruto (MXN)", min_value=0.01, format="%.2f")
        
        # Cálculo de fricción instantáneo
        costo_bruto = qty_input * price_input
        friccion = costo_bruto * comision_pct * (1 + iva_comision)
        costo_neto = costo_bruto + friccion
        
        submit = st.form_submit_button("Confirmar Compra")
        
        if submit and ticker_input:
            try:
                data = {
                    "user_id": st.session_state.user.id,
                    "ticker": ticker_input,
                    "shares": qty_input,
                    "price_mxn": price_input,
                    "fx_rate": current_fx,
                    "total_net_cost": costo_neto
                }
                supabase.table("positions").insert(data).execute()
                st.success(f"Ejecutado: {ticker_input}")
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e}")

# --- PANEL PRINCIPAL: DASHBOARD ---
st.header("💼 Terminal de Gestión Patrimonial")

# Métricas Top (Placeholder para lógica de agregación de Supabase)
m1, m2, m3 = st.columns(3)
with m1:
    st.container(border=True).metric("VALOR DEL PORTAFOLIO ACTUAL", "$53,979.65")
with m2:
    st.container(border=True).metric("UTILIDAD/PERDIDA REALIZADA", "$0.00")
with m3:
    st.container(border=True).metric("PLUSVALIA/MINUSVALIA NETA", "$4,209.91", "+7.8%")

st.divider()

# Monitoreo de Posiciones
st.subheader("📊 Monitoreo de Posiciones Activas")

# Ejemplo de visualización de capas (Esto se alimentará de tu Query a Supabase)
with st.expander("TBBB | USD: 36.58 (+0.22%) | Real: 🟢 -421.30 (-2.69%) | Peso: 28.4%"):
    st.write("Detalle de capas y precio promedio...")

with st.expander("SOXL | USD: 130.40 (+2.69%) | Real: 🟢 4,631.20 (13.65%) | Peso: 71.6%"):
    st.write("Detalle de capas y precio promedio...")

# Gráfico Técnico
st.divider()
selected_ticker = st.selectbox("Selecciona para Gráfico Técnico:", ["TBBB", "SOXL", "EEM", "SOXX"])
st.line_chart(yf.download(selected_ticker, period="1mo")['Close'])