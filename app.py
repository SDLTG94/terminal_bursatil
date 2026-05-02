import streamlit as st
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Terminal Global de Inversión", page_icon="🏛️", layout="wide")

# --- CONEXIÓN SEGURA A LA NUBE ---
# El 0.1% utiliza abstracción: el código no conoce los secretos, solo los solicita.
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Error de infraestructura: No se detectaron las credenciales en Secrets.")
    st.stop()

# --- LÓGICA DE AUTENTICACIÓN (SIDEBAR) ---
def login_sidebar():
    st.sidebar.title("🔐 Acceso Institucional")
    email = st.sidebar.text_input("Correo electrónico", key="login_email")
    password = st.sidebar.text_input("Contraseña", type="password", key="login_pass")
    
    col1, col2 = st.sidebar.columns(2)
    
    if col1.button("Entrar"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.sidebar.error("Credenciales inválidas.")

    if col2.button("Registrarse"):
        try:
            # El registro requiere confirmación por correo por defecto en Supabase
            res = supabase.auth.sign_up({"email": email, "password": password})
            st.sidebar.info("Solicitud enviada. Revisa tu correo para confirmar.")
        except Exception as e:
            st.sidebar.error(f"Error en registro: {e}")

    if st.sidebar.button("Cerrar Sesión"):
        if "user" in st.session_state:
            del st.session_state.user
            st.rerun()

# --- INTERFAZ PRINCIPAL ---
st.title("🏛️ Terminal Global de Inversión")

login_sidebar()

if "user" in st.session_state:
    user_id = st.session_state.user.id
    st.success(f"Sesión activa: **{st.session_state.user.email}**")

    # --- MÓDULO DE REGISTRO DE OPERACIONES ---
    # Foco en el 0.1%: Registro de capas con fricción operativa incluida.
    with st.expander("➕ Registrar Nueva Operación (Capas de Inversión)", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ticker = st.text_input("Ticker", placeholder="ej. SOXX o NVDA").upper()
            qty = st.number_input("Cantidad de Títulos", min_value=1, step=1)
        with c2:
            price_mxn = st.number_input("Precio de Ejecución (MXN)", min_value=0.01, format="%.2f")
            fx_rate = st.number_input("Tipo de Cambio (USD/MXN)", min_value=1.0, value=18.50)
        with c3:
            # Comisión estándar de casas de bolsa en México (ej. 0.10% a 0.25%)
            comision_pct = st.number_input("Comisión Bróker (%)", value=0.10, step=0.01) / 100
            iva_comision = 0.16 # IVA sobre la comisión

        # LÓGICA DE COSTO NETO (Sin tratamiento fiscal ISR, solo fricción operativa)
        # Fuente de lógica: Instrucción de cálculo neto tras comisiones e IVA.
        costo_bruto = qty * price_mxn
        # La fricción es la comisión del bróker más su respectivo IVA
        friccion_operativa = costo_bruto * comision_pct * (1 + iva_comision)
        costo_neto = costo_bruto + friccion_operativa

        st.divider()
        st.write("### Análisis de Entrada")
        
        # Visualización matemática para transparencia de auditoría
        st.latex(r"Costo_{Neto} = (Q \times P) + (Q \times P \times \%Com \times 1.16)")
        
        st.info(f"Costo Total de Adquisición: **${costo_neto:,.2f} MXN**")

        if st.button("Confirmar y Sincronizar con Nube"):
            if ticker:
                try:
                    # Insertar en la tabla 'positions' de Supabase
                    # Nota: Asegúrate de que las columnas coincidan en tu DB
                    data = {
                        "user_id": user_id,
                        "ticker": ticker,
                        "shares": qty,
                        "price_mxn": price_mxn,
                        "fx_rate": fx_rate,
                        "total_net_cost": costo_neto
                    }
                    supabase.table("positions").insert(data).execute()
                    st.success(f"Transacción de {ticker} registrada con éxito.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error de base de datos: {e}")
            else:
                st.warning("Ingrese un Ticker válido para proceder.")

    # --- DASHBOARD DE MONITOREO ---
    st.divider()
    st.subheader("Monitoreo de Portafolio en Tiempo Real")
    
    # Estos valores se conectarán a las consultas de Supabase en la siguiente fase
    m1, m2, m3 = st.columns(3)
    m1.metric("Equity Value (MXN)", "$0.00", "0.00%")
    m2.metric("P&L Realizado (Neto)", "$0.00", "0.00%")
    m3.metric("Fricción Acumulada (Comisiones + IVA)", "$0.00")

else:
    # Pantalla para usuarios no logueados
    st.warning("Acceso restringido. Por favor, inicie sesión para visualizar sus activos.")
    
    with st.expander("Acerca de esta Terminal"):
        st.write("""
        Terminal diseñada para el análisis avanzado de portafolios bajo los estándares de la certificación AMIB.
        * **Seguridad:** Implementación de Row Level Security (RLS) en Supabase.
        * **Cálculos:** Basados en precios de mercado y costos netos de fricción.
        * **Infraestructura:** Despliegue continuo via GitHub y Streamlit Cloud.
        """)