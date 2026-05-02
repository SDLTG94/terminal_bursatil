import streamlit as st
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Terminal Bursátil", page_icon="🏛️", layout="wide")

# --- CONEXIÓN SEGURA (CAPA DE ABSTRACCIÓN) ---
# El código no conoce los valores reales, solo las etiquetas de la bóveda
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Error de configuración en los Secretos de la plataforma.")
    st.stop()

# --- LÓGICA DE AUTENTICACIÓN ---
def login_sidebar():
    st.sidebar.title("🔐 Acceso Institucional")
    email = st.sidebar.text_input("Correo electrónico")
    password = st.sidebar.text_input("Contraseña", type="password")
    
    col1, col2 = st.sidebar.columns(2)
    
    if col1.button("Entrar"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.sidebar.error("Credenciales inválidas")

    if col2.button("Registrarse"):
        try:
            res = supabase.auth.sign_up({"email": email, "password": password})
            st.sidebar.info("Revisa tu correo para confirmar la cuenta.")
        except Exception as e:
            st.sidebar.error(f"Error en registro: {e}")

    if st.sidebar.button("Cerrar Sesión"):
        if "user" in st.session_state:
            del st.session_state.user
            st.rerun()

# --- INTERFAZ PRINCIPAL ---
st.title("🏛️ Terminal Global de Inversión")

# Ejecutamos el menú de acceso
login_sidebar()

if "user" in st.session_state:
    # --- ÁREA EXCLUSIVA PARA USUARIOS AUTENTICADOS ---
    user_email = st.session_state.user.email
    st.success(f"Sesión activa: **{user_email}**")
    
    # Placeholder para las métricas de portafolio
    st.subheader("Monitoreo de Portafolio (Neto de Comisiones y IVA)")
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Equity Value", "$0.00", "0.00%")
    col_b.metric("Realized P&L", "$0.00", "0.00%")
    col_c.metric("Buying Power", "$0.00")

    st.divider()
    
    # Aquí integrarás la lógica de carga de datos desde Supabase
    st.info("La terminal está conectada a la nube. Lista para procesar órdenes y capas de inversión.")

else:
    # --- PANTALLA DE ESPERA ---
    st.warning("Por favor, utiliza el panel lateral para iniciar sesión y visualizar tu portafolio.")
    
    with st.expander("Información del Sistema"):
        st.write("""
        Esta terminal utiliza una arquitectura desacoplada:
        * **Backend:** Supabase (PostgreSQL) con cifrado AES-256.
        * **Frontend:** Streamlit Cloud.
        * **Seguridad:** Row Level Security (RLS) activo para privacidad total entre usuarios.
        """)