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
import math

# ------------------------------------------------------------------------------
# Configuración general
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Catálogo Millex",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="collapsed",
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
.product-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.product-image {
    width: 100%;
    height: 180px;
    object-fit: contain;
    margin-bottom: 12px;
    border-radius: 8px;
    background: #f9f9f9;
}
.product-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 8px;
    color: #333;
    flex-grow: 1;
}
.product-code {
    font-size: 14px;
    color: #666;
    margin-bottom: 4px;
}
.product-price {
    font-size: 18px;
    font-weight: 700;
    color: #f63366;
    margin-bottom: 12px;
}
.product-qty {
    margin-top: auto;
}
.stNumberInput > div {width: 100%;}
.stNumberInput input {width: 100%;}

/* ---- PAGINACIÓN ---- */
.pagination {
    display: flex;
    justify-content: center;
    margin: 20px 0;
    gap: 8px;
}
.pagination button {
    background: #f0f2f6;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    cursor: pointer;
    transition: all 0.3s;
}
.pagination button:hover {
    background: #e0e2e6;
}
.pagination button.active {
    background: #f63366;
    color: white;
}
.pagination button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* ---- SIDEBAR ---- */
[data-testid="stSidebar"] {
    background: #f8f9fa;
    padding: 16px;
}
.sidebar-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
}
.cart-item {
    padding: 12px 0;
    border-bottom: 1px solid #e0e0e0;
}
.cart-item:last-child {
    border-bottom: none;
}
.cart-total {
    font-weight: 700;
    font-size: 18px;
    margin: 16px 0;
    color: #f63366;
}
.whatsapp-btn {
    background-color: #25D366 !important;
    color: white !important;
    width: 100%;
    margin: 8px 0;
}
.clear-btn {
    background-color: #f8f9fa !important;
    color: #f63366 !important;
    border: 1px solid #f63366 !important;
    width: 100%;
    margin: 8px 0;
}
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
# 6. Configuración de paginación
# ------------------------------------------------------------------------------
ITEMS_PER_PAGE = 45
total_pages = math.ceil(len(df) / ITEMS_PER_PAGE)
current_page = st.session_state.get(f"current_page_{linea}", 1)

# Función para cambiar de página
def change_page(page_num):
    st.session_state[f"current_page_{linea}"] = page_num

# Controles de paginación
if total_pages > 1:
    col1, col2, col3 = st.columns([1, 6, 1])
    with col1:
        if current_page > 1:
            st.button("◀ Anterior", on_click=change_page, args=(current_page-1,))
    with col2:
        st.write(f"Página {current_page} de {total_pages}")
    with col3:
        if current_page < total_pages:
            st.button("Siguiente ▶", on_click=change_page, args=(current_page+1,))

# ------------------------------------------------------------------------------
# 7. Mostrar productos en grilla (3 por fila)
# ------------------------------------------------------------------------------
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
            # Tarjeta de producto
            st.markdown(f'<div class="product-card">', unsafe_allow_html=True)
            
            # Imagen
            if prod.img_bytes:
                img = Image.open(io.BytesIO(prod.img_bytes))
                st.image(img, use_column_width=True)
            else:
                st.image("https://via.placeholder.com/200x150?text=Sin+imagen", 
                         use_column_width=True)
            
            # Detalles del producto
            st.markdown(f'<div class="product-title">{prod.detalle}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="product-code">Código: {prod.codigo}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="product-price">${prod.precio:,.2f}</div>', unsafe_allow_html=True)
            
            # Selector de cantidad
            qty_key = f"{linea}-{prod.codigo}"
            qty = st.number_input("Cantidad", min_value=0, step=1, key=qty_key, 
                                  value=cart.get(prod.codigo, {}).get("qty", 0))
            
            if qty:
                cart[prod.codigo] = {"detalle": prod.detalle, "precio": prod.precio, "qty": qty}
            elif prod.codigo in cart:
                cart.pop(prod.codigo)
            
            st.markdown(f'</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 8. Sidebar = Carrito
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-title"><h2>🛒 Carrito</h2></div>', unsafe_allow_html=True)
    st.markdown("---")
    
    if cart:
        for cod, it in cart.items():
            st.markdown(f"""
            <div class="cart-item">
                <div><strong>{it['detalle']}</strong></div>
                <div>Código: {cod}</div>
                <div>Cantidad: {it['qty']}</div>
                <div>Subtotal: ${it['precio'] * it['qty']:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        total = sum(it["precio"] * it["qty"] for it in cart.values())
        st.markdown(f'<div class="cart-total">Total: ${total:,.2f}</div>', unsafe_allow_html=True)
        
        msg = "Hola! Quiero hacer un pedido de los siguientes productos:\n"
        for cod, it in cart.items():
            msg += f"- {it['detalle']} (Código {cod}) x {it['qty']}\n"
        msg += f"\nTotal: ${total:,.2f}"
        link = f"https://wa.me/5493516434765?text={urllib.parse.quote(msg)}"
        
        if st.button("📲 Confirmar pedido por WhatsApp", key="whatsapp_btn"):
            st.success("¡Pedido listo para enviar por WhatsApp!")
            st.markdown(f"[Enviar ahora →]({link})", unsafe_allow_html=True)
        
        if st.button("🗑️ Vaciar carrito", key="clear_btn"):
            cart.clear()
            for k in list(st.session_state.keys()):
                if "-" in k and isinstance(st.session_state[k], int):
                    st.session_state[k] = 0
            st.experimental_rerun()
    else:
        st.write("Todavía no agregaste productos.")

# ------------------------------------------------------------------------------
# 9. FAB móvil con contador de ítems
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



