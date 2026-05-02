import streamlit as st
from supabase import create_client, Client

# 1. Conexión Segura
# Streamlit leerá automáticamente los valores de tu archivo secrets.toml
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.title("🏛️ Terminal Global de Inversión")

# 2. Sistema de Registro/Login Simple
st.sidebar.title("🔐 Acceso")
email = st.sidebar.text_input("Correo electrónico")
password = st.sidebar.text_input("Contraseña", type="password")

if st.sidebar.button("Entrar / Registrarse"):
    try:
        # Intentamos hacer login
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.success(f"Bienvenido, {email}")
    except:
        # Si falla, intentamos registrarlo como nuevo usuario
        try:
            res = supabase.auth.sign_up({"email": email, "password": password})
            st.info("Revisa tu correo para confirmar tu cuenta.")
        except Exception as e:
            st.error(f"Error: {e}")

# 3. Solo mostrar el dashboard si hay un usuario logueado
if "user" in st.session_state:
    st.write(f"ID de Usuario Activo: {st.session_state.user.id}")
    # Aquí es donde pegaremos el resto de tu lógica de visualización
else:
    st.warning("Por favor, inicia sesión para ver tu portafolio.")