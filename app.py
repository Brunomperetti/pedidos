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

# ------------------------------------------------------------------------------
# Configuración general
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Catálogo Millex",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="collapsed",  # Arranca colapsada (el botón la abre)
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

# ---- CSS global (oculta logos + añade FAB carrito móvil) ---------------------
st.markdown("""
<style>
/* Ocultar menús / logos */
#MainMenu, footer, header {visibility: hidden;}
.viewerBadge_container__1QSob,
.viewerBadge_container__rGiy7,
a[href="https://streamlit.io"],
div[class^="viewerBadge_container"],
.stDeployButton {display: none !important;}

/* Ajuste top padding */
.block-container {padding-top: 1rem;}

/* ---- BOTÓN FLOTANTE 🛒 SOLO MOBILE ---- */
.carrito-fab {
    position: fixed;
    bottom: 16px;
    right: 16px;
    background-color: #f63366;
    color: #fff;
    padding: 14px 20px;
    font-size: 18px;
    font-weight: 700;
    border-radius: 32px;
    box-shadow: 0 4px 12px rgba(0,0,0,.35);
    z-index: 99999;
    cursor: pointer;
    transition: transform .15s ease-in-out;
}
.carrito-fab:hover {transform: scale(1.06);}
@media (min-width: 769px) {.carrito-fab {display:none;}}  /* solo celular/tablet */
</style>
""", unsafe_allow_html=True)
# ------------------------------------------------------------------------------

st.title("🐾 Catálogo de productos Millex")

# ------------------------------------------------------------------------------
# 1. Bajar Excel desde Google Sheets (cacheado)
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_excel(file_id: str) -> Path:
    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    tmp = Path(tempfile.gettempdir()) / f"{file_id}.xlsx"
    tmp.write_bytes(r.content)
    return tmp

# ------------------------------------------------------------------------------
# 2. Cargar productos + imágenes
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_products(xls_path: str) -> pd.DataFrame:
    wb = load_workbook(xls_path, data_only=True)
    ws = wb.active
    img_map = {img.anchor._from.row + 1: img._data()      # fila -> bytes
               for img in ws._images if hasattr(img, "_data")}
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

# ------------------------------------------------------------------------------
# 3. Mapeo línea → Sheet ID
# ------------------------------------------------------------------------------
FILE_IDS = {
    "Línea Perros": "1EK_NlWT-eS5_7P2kWwBHsui2tKu5t26U",
    "Línea Pájaros y Roedores": "1n10EZZvZq-3M2t3rrtmvW7gfeB40VJ7F",
    "Línea Gatos": "1vSWXZKsIOqpy2wNhWsKH3Lp77JnRNKbA",
    "Línea Bombas de Acuario": "1DiXE5InuxMjZio6HD1nkwtQZe8vaGcSh",
}

# ------------------------------------------------------------------------------
# 4. Selector de línea (visible en todas las pantallas)
# ------------------------------------------------------------------------------
linea = st.selectbox("Elegí la línea de productos:", list(FILE_IDS.keys()))

# ------------------------------------------------------------------------------
# 5. Cargar catálogo seleccionado
# ------------------------------------------------------------------------------
df = load_products(str(fetch_excel(FILE_IDS[linea])))

# Carrito en sesión
cart: dict = st.session_state.setdefault("cart", {})

# ------------------------------------------------------------------------------
# 6. Mostrar productos en grilla (2 por fila)
# ------------------------------------------------------------------------------
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
                thumb = img.resize((int(img.width*0.3), int(img.height*0.3)))
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

# ------------------------------------------------------------------------------
# 7. Sidebar = Carrito
# ------------------------------------------------------------------------------
st.sidebar.header("🛒 Carrito")
st.sidebar.markdown("---")

if cart:
    tabla, total = [], 0.0
    for cod, it in cart.items():
        sub = it["precio"] * it["qty"]
        total += sub
        tabla.append([cod, it["qty"], f"${sub:,.2f}"])
    st.sidebar.table(pd.DataFrame(tabla, columns=["Código", "Cant.", "Subtotal"]))
    st.sidebar.markdown(f"**Total: ${total:,.2f}**")

    msg = "Hola! Quiero hacer un pedido de los siguientes productos:\n"
    for cod, it in cart.items():
        msg += f"- {it['detalle']} (Código {cod}) x {it['qty']}\n"
    msg += f"\nTotal: ${total:,.2f}"
    link = f"https://wa.me/5493516434765?text={urllib.parse.quote(msg)}"

    if st.sidebar.button("📲 Confirmar pedido por WhatsApp"):
        st.sidebar.success("¡Pedido listo para enviar por WhatsApp!")
        st.sidebar.markdown(f"[Enviar ahora →]({link})", unsafe_allow_html=True)

    if st.sidebar.button("🗑️ Vaciar carrito"):
        cart.clear()
        for k in list(st.session_state.keys()):
            if "-" in k and isinstance(st.session_state[k], int):
                st.session_state[k] = 0
        st.experimental_rerun()
else:
    st.sidebar.write("Todavía no agregaste productos.")

# ------------------------------------------------------------------------------
# 8. FAB móvil con contador de ítems
# ------------------------------------------------------------------------------
qty_total = sum(it["qty"] for it in cart.values())
fab_label = f"🛒 ({qty_total})" if qty_total else "🛒 Ver carrito"

st.markdown(
    f'<div class="carrito-fab" onclick="window.dispatchEvent(new Event(\'toggleSidebar\'))">{fab_label}</div>',
    unsafe_allow_html=True
)

# JS: clic → abre o cierra sidebar
st.markdown("""
<script>
window.addEventListener("toggleSidebar", () => {
  const btn = window.parent.document.querySelector('button[aria-label^="Toggle sidebar"]')
           || window.parent.document.querySelector('button[title^="Expand sidebar"]')
           || window.parent.document.querySelector('button[title^="Collapse sidebar"]');
  if (btn) btn.click();
});
</script>
""", unsafe_allow_html=True)




