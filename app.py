# catalogo_millex_app.py
import streamlit as st
import pandas as pd
from openpyxl import load_workbook
from pathlib import Path
from PIL import Image
import io
import urllib.parse
import requests
import tempfile

# catalogo_millex_app.py

import streamlit as st
import pandas as pd
from openpyxl import load_workbook
from pathlib import Path
from PIL import Image
import io
import urllib.parse
import requests
import tempfile

# ----------------------------------------------------------------------------- 
# Configuración general de la app (antes que nada) 
# ----------------------------------------------------------------------------- 

st.set_page_config(page_title="Catálogo Millex", page_icon="🐾", layout="wide", initial_sidebar_state="expanded")

# Desactivar elementos de Streamlit (menú, footer, botón desplegar, corona roja)
st.markdown("""
    <style>
    #MainMenu, footer, .stDeployButton, .viewerBadge_container__1QSob {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 1. Descargar el Excel público desde Google Sheets y cachearlo
# -----------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def fetch_excel(file_id: str) -> Path:
    """Descarga la Sheet pública como .xlsx y devuelve la ruta temporal."""
    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    tmp_path = Path(tempfile.gettempdir()) / f"{file_id}.xlsx"
    tmp_path.write_bytes(r.content)
    return tmp_path


# -----------------------------------------------------------------------------
# 2. Cargar productos e imágenes a partir de un .xlsx local
# -----------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_products(xls_path: str) -> pd.DataFrame:
    """Devuelve un DataFrame con los productos de la hoja activa.

    Asume que los datos empiezan en la fila 3 y que las imágenes están
    insertadas en la misma fila del producto."""
    wb = load_workbook(xls_path, data_only=True)
    ws = wb.active

    # Mapa: Nº de fila -> bytes de la imagen
    img_map: dict[int, bytes] = {}
    for img in ws._images:
        row = img.anchor._from.row + 1   # openpyxl usa índice base 0
        if hasattr(img, "_data"):
            img_map[row] = img._data()

    # Leer los datos a partir de la fila 3
    rows: list[dict] = []
    for idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        if not row[1]:          # Si no hay código, cortamos.
            break
        codigo, detalle, precio = row[1], row[2], row[3]
        precio = 0 if precio is None else float(str(precio).replace("$", "").replace(",", ""))
        rows.append({
            "fila_excel": idx,
            "codigo": codigo,
            "detalle": detalle,
            "precio": precio,
        })

    df = pd.DataFrame(rows)
    df["img_bytes"] = df["fila_excel"].map(img_map)
    return df


# -----------------------------------------------------------------------------
# 3. Configuración general de la app
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Catálogo Millex",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="auto",
    # Esto vacía el menú … pero igual lo ocultamos con CSS abajo
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

# ---- 3.a  Ocultar menús/footers/logo ----------------------------------------------------------------
hide_streamlit_style = """
<style>
/* Oculta el menú hamburguesa */
#MainMenu {visibility: hidden;}
/* Oculta el footer "Made with Streamlit" */
footer {visibility: hidden;}
/* Oculta la barra superior (incluye logo GH en algunos temas) */
header {visibility: hidden;}
/* Oculta la barra de estado / “running” */
div[data-testid="stStatusWidget"] {visibility: hidden;}
/* Opcional: achica padding top */
.block-container {padding-top: 1rem;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
# ------------------------------------------------------------------------------------------------------

st.title("🐾 Catálogo de productos Millex")


# Mapeo línea → ID de la Google Sheet pública
FILE_IDS = {
    "Línea Perros": "1EK_NlWT-eS5_7P2kWwBHsui2tKu5t26U",
    "Línea Pájaros y Roedores": "1n10EZZvZq-3M2t3rrtmvW7gfeB40VJ7F",
    "Línea Gatos": "1vSWXZKsIOqpy2wNhWsKH3Lp77JnRNKbA",
    "Línea Bombas de Acuario": "1DiXE5InuxMjZio6HD1nkwtQZe8vaGcSh",
}

# -----------------------------------------------------------------------------
# 4. Selector de línea y carga de datos
# -----------------------------------------------------------------------------

st.sidebar.header("Seleccioná una línea")
linea = st.sidebar.selectbox("Línea de productos:", list(FILE_IDS.keys()))

xls_path = fetch_excel(FILE_IDS[linea])
df = load_products(str(xls_path))

# Estado global del carrito (vive en la sesión)
cart: dict = st.session_state.setdefault("cart", {})

# -----------------------------------------------------------------------------
# 5. Grid de productos (2 por fila)
# -----------------------------------------------------------------------------

for i in range(0, len(df), 2):
    cols = st.columns(2)
    for j in range(2):
        if i + j >= len(df):
            continue
        prod = df.iloc[i + j]
        with cols[j]:
            # Imagen
            if prod.img_bytes:
                img = Image.open(io.BytesIO(prod.img_bytes))
                thumb = img.resize((int(img.width * 0.3), int(img.height * 0.3)))
                st.image(thumb)
            else:
                st.write("Sin imagen")

            # Detalle
            st.markdown(f"**{prod.detalle}**")
            st.text(f"Código: {prod.codigo}")
            st.text(f"Precio: ${prod.precio:,.2f}")

            # Cantidad (clave única por línea + código)
            qty_key = f"{linea}-{prod.codigo}"
            qty = st.number_input("Cantidad", min_value=0, step=1, key=qty_key)

            # Actualizar carrito
            if qty:
                cart[prod.codigo] = {
                    "detalle": prod.detalle,
                    "precio": prod.precio,
                    "qty": qty,
                }
            elif prod.codigo in cart:
                cart.pop(prod.codigo)

# -----------------------------------------------------------------------------
# 6. Carrito en la barra lateral
# -----------------------------------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.header("🛒 Carrito")

if cart:
    tabla = []
    total = 0.0
    for codigo, item in cart.items():
        subtotal = item["precio"] * item["qty"]
        total += subtotal
        tabla.append([codigo, item["qty"], f"${subtotal:,.2f}"])

    st.sidebar.table(pd.DataFrame(tabla, columns=["Código", "Cant.", "Subtotal"]))
    st.sidebar.markdown(f"**Total: ${total:,.2f}**")

    # Armado de mensaje de WhatsApp
    mensaje = "Hola! Quiero hacer un pedido de los siguientes productos:\n"
    for codigo, item in cart.items():
        mensaje += f"- {item['detalle']} (Código {codigo}) x {item['qty']}\n"
    mensaje += f"\nTotal: ${total:,.2f}"

    link = f"https://wa.me/5493516434765?text={urllib.parse.quote(mensaje)}"

    # Botón confirmar
    if st.sidebar.button("Confirmar pedido por WhatsApp"):
        st.sidebar.success("¡Pedido listo para enviar por WhatsApp!")
        st.sidebar.markdown(f"[📲 Enviar pedido →]({link})", unsafe_allow_html=True)

    # ---------- Botón vaciar carrito -------------
    if st.sidebar.button("🗑️ Vaciar carrito"):
        cart.clear()
        # Poner en cero todos los number_input que se crearon
        for k in list(st.session_state.keys()):
            if "-" in k and isinstance(st.session_state[k], int):
                st.session_state[k] = 0
        st.experimental_rerun()
    # ---------------------------------------------
else:
    st.sidebar.write("Todavía no agregaste productos.")



