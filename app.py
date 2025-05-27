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
# Configuración general de la app
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Catálogo Millex",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded",   # Abre el carrito al cargar
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

# ---- Ocultar menús / logos / corona -----------------------------------------
st.markdown("""
<style>
/* Menú hamburguesa y footer */
#MainMenu, footer {visibility: hidden;}
/* Barra superior (logo GH) */
header {visibility: hidden;}
/* Barra “running” */
div[data-testid="stStatusWidget"] {visibility: hidden;}
/* Viewer badge (“Hosted with Streamlit”) — múltiples variantes */
.viewerBadge_container__1QSob,
.viewerBadge_container__rGiy7,
a[href="https://streamlit.io"],
div[class^="viewerBadge_container"],
.stDeployButton {display: none !important;}
/* Ajuste de padding */
.block-container {padding-top: 1rem;}
</style>
""", unsafe_allow_html=True)
# -----------------------------------------------------------------------------

st.title("🐾 Catálogo de productos Millex")

# -----------------------------------------------------------------------------
# 1. Descargar el Excel público desde Google Sheets y cachearlo
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_excel(file_id: str) -> Path:
    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    tmp_path = Path(tempfile.gettempdir()) / f"{file_id}.xlsx"
    tmp_path.write_bytes(r.content)
    return tmp_path

# -----------------------------------------------------------------------------
# 2. Cargar productos e imágenes
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_products(xls_path: str) -> pd.DataFrame:
    wb = load_workbook(xls_path, data_only=True)
    ws = wb.active
    img_map: dict[int, bytes] = {}
    for img in ws._images:
        row = img.anchor._from.row + 1
        if hasattr(img, "_data"):
            img_map[row] = img._data()
    rows = []
    for idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        if not row[1]:
            break
        codigo, detalle, precio = row[1], row[2], row[3]
        precio = 0 if precio is None else float(str(precio).replace("$", "").replace(",", ""))
        rows.append({"fila_excel": idx, "codigo": codigo, "detalle": detalle, "precio": precio})
    df = pd.DataFrame(rows)
    df["img_bytes"] = df["fila_excel"].map(img_map)
    return df

# -----------------------------------------------------------------------------
# 3. Mapeo líneas → Sheets
# -----------------------------------------------------------------------------
FILE_IDS = {
    "Línea Perros": "1EK_NlWT-eS5_7P2kWwBHsui2tKu5t26U",
    "Línea Pájaros y Roedores": "1n10EZZvZq-3M2t3rrtmvW7gfeB40VJ7F",
    "Línea Gatos": "1vSWXZKsIOqpy2wNhWsKH3Lp77JnRNKbA",
    "Línea Bombas de Acuario": "1DiXE5InuxMjZio6HD1nkwtQZe8vaGcSh",
}

# -----------------------------------------------------------------------------
# 4. Selector de línea (en la parte principal, apto mobile)
# -----------------------------------------------------------------------------
linea = st.selectbox("Elegí la línea de productos:", list(FILE_IDS.keys()))

xls_path = fetch_excel(FILE_IDS[linea])
df = load_products(str(xls_path))

# Estado global del carrito
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

            # Cantidad
            qty_key = f"{linea}-{prod.codigo}"
            qty = st.number_input("Cantidad", min_value=0, step=1, key=qty_key)

            # Actualizar carrito
            if qty:
                cart[prod.codigo] = {"detalle": prod.detalle, "precio": prod.precio, "qty": qty}
            elif prod.codigo in cart:
                cart.pop(prod.codigo)

# -----------------------------------------------------------------------------
# 6. Carrito en la barra lateral
# -----------------------------------------------------------------------------
st.sidebar.header("🛒 Carrito")
st.sidebar.markdown("---")

if cart:
    tabla, total = [], 0.0
    for codigo, item in cart.items():
        subtotal = item["precio"] * item["qty"]
        total += subtotal
        tabla.append([codigo, item["qty"], f"${subtotal:,.2f}"])
    st.sidebar.table(pd.DataFrame(tabla, columns=["Código", "Cant.", "Subtotal"]))
    st.sidebar.markdown(f"**Total: ${total:,.2f}**")

    # WhatsApp
    mensaje = "Hola! Quiero hacer un pedido de los siguientes productos:\n"
    for codigo, item in cart.items():
        mensaje += f"- {item['detalle']} (Código {codigo}) x {item['qty']}\n"
    mensaje += f"\nTotal: ${total:,.2f}"
    link = f"https://wa.me/5493516434765?text={urllib.parse.quote(mensaje)}"

    if st.sidebar.button("Confirmar pedido por WhatsApp"):
        st.sidebar.success("¡Pedido listo para enviar por WhatsApp!")
        st.sidebar.markdown(f"[📲 Enviar pedido →]({link})", unsafe_allow_html=True)

    if st.sidebar.button("🗑️ Vaciar carrito"):
        cart.clear()
        for k in list(st.session_state.keys()):
            if "-" in k and isinstance(st.session_state[k], int):
                st.session_state[k] = 0
        st.experimental_rerun()
else:
    st.sidebar.write("Todavía no agregaste productos.")



