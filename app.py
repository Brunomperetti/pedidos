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
# Configuración general
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Catálogo Millex",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Eliminar logos, botones y badge
st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.viewerBadge_container__1QSob,
.viewerBadge_container__rGiy7,
a[href="https://streamlit.io"],
div[class^="viewerBadge_container"],
.stDeployButton {display: none !important;}
.block-container {padding-top: 1rem;}
/* Botón carrito flotante */
.carrito-btn {
    position: fixed;
    top: 20px;
    right: 20px;
    background-color: #f63366;
    color: white;
    padding: 12px 18px;
    border-radius: 8px;
    font-weight: bold;
    z-index: 9999;
    cursor: pointer;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Descargar catálogo desde Google Sheets
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
# Cargar productos e imágenes
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
# Mapeo sheets
# -----------------------------------------------------------------------------
FILE_IDS = {
    "Línea Perros": "1EK_NlWT-eS5_7P2kWwBHsui2tKu5t26U",
    "Línea Pájaros y Roedores": "1n10EZZvZq-3M2t3rrtmvW7gfeB40VJ7F",
    "Línea Gatos": "1vSWXZKsIOqpy2wNhWsKH3Lp77JnRNKbA",
    "Línea Bombas de Acuario": "1DiXE5InuxMjZio6HD1nkwtQZe8vaGcSh",
}

# -----------------------------------------------------------------------------
# Interfaz principal
# -----------------------------------------------------------------------------
st.title("🐾 Catálogo Millex")

linea = st.selectbox("Elegí la línea de productos:", list(FILE_IDS.keys()))
xls_path = fetch_excel(FILE_IDS[linea])
df = load_products(str(xls_path))

# Estado carrito
cart: dict = st.session_state.setdefault("cart", {})

# -----------------------------------------------------------------------------
# Mostrar productos
# -----------------------------------------------------------------------------
for i in range(0, len(df), 2):
    cols = st.columns(2)
    for j in range(2):
        if i + j >= len(df):
            continue
        prod = df.iloc[i + j]
        with cols[j]:
            if prod.img_bytes:
                img = Image.open(io.BytesIO(prod.img_bytes))
                thumb = img.resize((int(img.width * 0.3), int(img.height * 0.3)))
                st.image(thumb)
            else:
                st.write("Sin imagen")

            st.markdown(f"**{prod.detalle}**")
            st.text(f"Código: {prod.codigo}")
            st.text(f"Precio: ${prod.precio:,.2f}")

            qty_key = f"{linea}-{prod.codigo}"
            qty = st.number_input("Cantidad", min_value=0, step=1, key=qty_key)

            if qty:
                cart[prod.codigo] = {"detalle": prod.detalle, "precio": prod.precio, "qty": qty}
            elif prod.codigo in cart:
                cart.pop(prod.codigo)

# -----------------------------------------------------------------------------
# Botón flotante para mostrar carrito
# -----------------------------------------------------------------------------
st.markdown('<div class="carrito-btn" onclick="window.dispatchEvent(new Event(\'abrirCarrito\'))">🛒 Ver carrito</div>', unsafe_allow_html=True)

# Script para activar modal en cliente
st.markdown("""
<script>
window.addEventListener("abrirCarrito", function() {
    const boton = window.parent.document.querySelector('button[kind="primary"][data-testid^="baseButton"]');
    if (boton) boton.click();
});
</script>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Carrito en modal
# -----------------------------------------------------------------------------
with st.expander("🛒 Carrito de compras", expanded=False):
    if cart:
        tabla, total = [], 0.0
        for codigo, item in cart.items():
            subtotal = item["precio"] * item["qty"]
            total += subtotal
            tabla.append([codigo, item["qty"], f"${subtotal:,.2f}"])
        st.table(pd.DataFrame(tabla, columns=["Código", "Cant.", "Subtotal"]))
        st.markdown(f"**Total: ${total:,.2f}**")

        mensaje = "Hola! Quiero hacer un pedido de los siguientes productos:\n"
        for codigo, item in cart.items():
            mensaje += f"- {item['detalle']} (Código {codigo}) x {item['qty']}\n"
        mensaje += f"\nTotal: ${total:,.2f}"
        link = f"https://wa.me/5493516434765?text={urllib.parse.quote(mensaje)}"

        if st.button("📲 Confirmar pedido por WhatsApp"):
            st.success("¡Pedido listo para enviar por WhatsApp!")
            st.markdown(f"[Enviar ahora →]({link})", unsafe_allow_html=True)

        if st.button("🗑️ Vaciar carrito"):
            cart.clear()
            for k in list(st.session_state.keys()):
                if "-" in k and isinstance(st.session_state[k], int):
                    st.session_state[k] = 0
            st.experimental_rerun()
    else:
        st.write("Todavía no agregaste productos.")





