import streamlit as st
import pandas as pd
from openpyxl import load_workbook
from pathlib import Path
from PIL import Image
import io
import urllib.parse
import requests
import tempfile
import math

# ---------------------------------------------------------------------
# Configuración general
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Catálogo Millex",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

# ---- CSS global (oculta logos + añade FAB carrito móvil) -------------
st.markdown(
    """
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
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}
.carrito-fab:hover {transform: scale(1.06);}
@media (min-width: 769px) {.carrito-fab {display:none;}}  /* solo celular/tablet */

/* ---- ESTILOS PRODUCTOS ---- */
.product-card {
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    padding: 16px;
    height: 100%;
    transition: box-shadow 0.3s ease;
    display: flex;
    flex-direction: column;
}
.product-card:hover {box-shadow: 0 4px 12px rgba(0,0,0,0.1);}
.product-image {
    width: 100%;
    height: 180px;
    object-fit: contain;
    margin-bottom: 12px;
    border-radius: 8px;
    background: #f9f9f9;
}
.product-title {font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #333; flex-grow: 1;}
.product-code  {font-size: 14px; color: #666; margin-bottom: 4px;}
.product-price {font-size: 18px; font-weight: 700; color: #f63366; margin-bottom: 12px;}
.product-qty   {margin-top: auto;}
.stNumberInput > div, .stNumberInput input {width: 100%;}

/* ---- PAGINACIÓN ---- */
.pagination {display: flex; justify-content: center; margin: 20px 0; gap: 8px;}
.pagination button {
    background: #f0f2f6; border: none; border-radius: 6px;
    padding: 8px 12px; cursor: pointer; transition: all 0.3s;
}
.pagination button:hover      {background: #e0e2e6;}
.pagination button.active     {background: #f63366; color: white;}
.pagination button:disabled   {opacity: 0.5; cursor: not-allowed;}

/* ---- SIDEBAR ---- */
[data-testid="stSidebar"] {background: #f8f9fa; padding: 16px;}
.sidebar-title {display: flex; align-items: center; gap: 8px; margin-bottom: 16px;}
.cart-item {padding: 12px 0; border-bottom: 1px solid #e0e0e0; color: #333;} /* ← texto visibile */
.cart-item:last-child {border-bottom: none;}
.cart-total {font-weight: 700; font-size: 18px; margin: 16px 0; color: #f63366;}
.whatsapp-btn {background-color: #25D366 !important; color: white !important; width: 100%; margin: 8px 0;}
.clear-btn    {background-color: #f8f9fa !important; color: #f63366 !important; border: 1px solid #f63366 !important; width: 100%; margin: 8px 0;}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
st.title("🐾 Catálogo de productos Millex")

# ---------------------------------------------------------------------
# 1. Bajar Excel desde Google Sheets (cacheado)
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_excel(file_id: str) -> Path:
    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    tmp = Path(tempfile.gettempdir()) / f"{file_id}.xlsx"
    tmp.write_bytes(r.content)
    return tmp

# ---------------------------------------------------------------------
# 2. Cargar productos + imágenes
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_products(xls_path: str) -> pd.DataFrame:
    wb = load_workbook(xls_path, data_only=True)
    ws = wb.active
    img_map = {img.anchor._from.row + 1: img._data() for img in ws._images if hasattr(img, "_data")}
    rows = []
    for idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        if not row[1]:   # columna B vacía => fin de datos
            break
        codigo, detalle, precio = row[1], row[2], row[3]
        precio = 0 if precio is None else float(str(precio).replace("$", "").replace(",", ""))
        rows.append({"fila_excel": idx, "codigo": codigo, "detalle": detalle, "precio": precio})
    df = pd.DataFrame(rows)
    df["img_bytes"] = df["fila_excel"].map(img_map)
    return df

# ---------------------------------------------------------------------
# 3. Mapeo línea → Sheet ID
# ---------------------------------------------------------------------
FILE_IDS = {
    "Línea Perros": "1EK_NlWT-eS5_7P2kWwBHsui2tKu5t26U",
    "Línea Pájaros y Roedores": "1n10EZZvZq-3M2t3rrtmvW7gfeB40VJ7F",
    "Línea Gatos": "1vSWXZKsIOqpy2wNhWsKH3Lp77JnRNKbA",
    "Línea Bombas de Acuario": "1DiXE5InuxMjZio6HD1nkwtQZe8vaGcSh",
}

# ---------------------------------------------------------------------
# 4. Selector de línea + buscador
# ---------------------------------------------------------------------
col_linea, col_search = st.columns([1, 2])
with col_linea:
    linea = st.selectbox("Elegí la línea de productos:", list(FILE_IDS.keys()))
with col_search:
    search_term = st.text_input("🔍 Buscar (código o descripción)…").strip().lower()

# ---------------------------------------------------------------------
# 5. Cargar catálogo filtrado
# ---------------------------------------------------------------------
df_base = load_products(str(fetch_excel(FILE_IDS[linea])))

if search_term:
    df = df_base[
        df_base["codigo"].astype(str).str.contains(search_term, case=False)
        | df_base["detalle"].str.lower().str.contains(search_term)
    ]
else:
    df = df_base

# ---------------------------------------------------------------------
# 6. Paginación
# ---------------------------------------------------------------------
ITEMS_PER_PAGE = 45
total_pages = max(1, math.ceil(len(df) / ITEMS_PER_PAGE))
current_page_key = f"current_page_{linea}"
current_page = st.session_state.get(current_page_key, 1)

def change_page(page_num: int):
    st.session_state[current_page_key] = page_num

# ---------------------------------------------------------------------
# 7. Navegador de páginas (arriba)
# ---------------------------------------------------------------------
def pager(position: str):
    col1, col2, col3 = st.columns([1, 6, 1])
    with col1:
        st.button("◀", on_click=change_page, args=(current_page - 1,), disabled=current_page == 1, key=f"{position}_prev")
    with col2:
        st.write(f"Página {current_page} de {total_pages}")
    with col3:
        st.button("⬇" if position == "bottom" else "▶",
                  on_click=change_page,
                  args=(current_page + 1,),
                  disabled=current_page == total_pages,
                  key=f"{position}_next")

if total_pages > 1:
    pager("top")

# ---------------------------------------------------------------------
# 8. Mostrar productos
# ---------------------------------------------------------------------
start_idx = (current_page - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
paginated_df = df.iloc[start_idx:end_idx]

for i in range(0, len(paginated_df), 3):
    cols = st.columns(3)
    for j in range(3):
        if i + j >= len(paginated_df):
            continue
        prod = paginated_df.iloc[i + j]
        with cols[j]:
            st.markdown('<div class="product-card">', unsafe_allow_html=True)

            # Imagen
            if prod.img_bytes is not None:
                img = Image.open(io.BytesIO(prod.img_bytes))
                st.image(img, use_container_width=True)  # ← parámetro moderno
            else:
                st.image(
                    "https://via.placeholder.com/200x150?text=Sin+imagen",
                    use_container_width=True,
                )

            # Detalles
            st.markdown(f'<div class="product-title">{prod.detalle}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="product-code">Código: {prod.codigo}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="product-price">${prod.precio:,.2f}</div>', unsafe_allow_html=True)

            # Selector cantidad
            qty_key = f"{linea}-{prod.codigo}"
            qty = st.number_input(
                "Cantidad",
                min_value=0,
                step=1,
                key=qty_key,
                value=st.session_state.get("cart", {}).get(prod.codigo, {}).get("qty", 0),
            )

            cart = st.session_state.setdefault("cart", {})
            if qty:
                cart[prod.codigo] = {"detalle": prod.detalle, "precio": prod.precio, "qty": qty}
            elif prod.codigo in cart:
                cart.pop(prod.codigo)

            st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# 9. Navegador de páginas (abajo con flecha ↓)
# ---------------------------------------------------------------------
if total_pages > 1:
    pager("bottom")

# ---------------------------------------------------------------------
# 10. Sidebar = Carrito
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-title"><h2>🛒 Carrito</h2></div>', unsafe_allow_html=True)
    st.markdown("---")

    cart = st.session_state["cart"]
    if cart:
        for cod, it in cart.items():
            st.markdown(
                f"""
<div class="cart-item">
  <div><strong>{it['detalle']}</strong></div>
  <div>Código: {cod}</div>
  <div>Cantidad: {it['qty']}</div>
  <div>Subtotal: ${it['precio'] * it['qty']:,.2f}</div>
</div>
""",
                unsafe_allow_html=True,
            )

        total = sum(it["precio"] * it["qty"] for it in cart.values())
        st.markdown(f'<div class="cart-total">Total: ${total:,.2f}</div>', unsafe_allow_html=True)

        # Link a WhatsApp
        msg_lines = [f"- {it['detalle']} (Código {cod}) x {it['qty']}" for cod, it in cart.items()]
        msg = "Hola! Quiero hacer un pedido de los siguientes productos:\n" + "\n".join(msg_lines) + f"\n\nTotal: ${total:,.2f}"
        link = f"https://wa.me/5493516434765?text={urllib.parse.quote(msg)}"

        st.link_button("📲 Confirmar pedido por WhatsApp", link, use_container_width=True, key="whats_btn")
        if st.button("🗑️ Vaciar carrito", key="clear_btn"):
            st.session_state["cart"].clear()
            # resetear los number_input
            for k in list(st.session_state.keys()):
                if k.startswith(f"{linea}-"):
                    st.session_state[k] = 0
            st.experimental_rerun()
    else:
        st.write("Todavía no agregaste productos.")

# ---------------------------------------------------------------------
# 11. FAB móvil con contador
# ---------------------------------------------------------------------
qty_total = sum(it["qty"] for it in st.session_state["cart"].values())
fab_label = f"🛒 ({qty_total})" if qty_total else "🛒 Ver carrito"
st.markdown(
    f'<div class="carrito-fab" onclick="window.dispatchEvent(new Event(\'toggleSidebar\'))">{fab_label}</div>',
    unsafe_allow_html=True,
)

# ---- JS: toggle sidebar ----
st.markdown(
    """
<script>
window.addEventListener("toggleSidebar", () => {
  const btn = window.parent.document.querySelector('button[aria-label^="Toggle sidebar"]')
           || window.parent.document.querySelector('button[title^="Expand sidebar"]')
           || window.parent.document.querySelector('button[title^="Collapse sidebar"]');
  if (btn) btn.click();
});
</script>
""",
    unsafe_allow_html=True,
)




