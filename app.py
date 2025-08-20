import streamlit as st
import pandas as pd
from openpyxl import load_workbook
from pathlib import Path
import unicodedata
import requests
import tempfile
import math
from io import BytesIO

# --- Funciones base de tu código ---

def quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    ).lower()

@st.cache_data(show_spinner=False)
def fetch_excel_from_drive(file_id: str) -> Path:
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    tmp = Path(tempfile.gettempdir()) / f"{file_id}.xlsx"
    tmp.write_bytes(r.content)
    return tmp

@st.cache_data(show_spinner=False)
def load_products_from_sheet(xls_path: str, sheet_name: str) -> pd.DataFrame:
    wb = load_workbook(xls_path, data_only=True)
    ws = wb[sheet_name]  # Cargar la hoja específica
    
    # Leer las filas a partir de la fila 3 (suponiendo que las primeras filas son encabezados)
    rows = []
    images = {}  # Diccionario para almacenar las imágenes

    for idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        if not row[0]:  # Si no hay SKU, se detiene
            break
        # Extraer solo las columnas necesarias (SKU, Imagen, Descripción, etc.)
        sku, imagen, descripcion, tamaño, precio_usd, unidades_por_caja, *resto = row[:7]

        # Buscar imágenes embebidas en la hoja
        for img in ws._images:
            if img.anchor._from.col == 1 and img.anchor._from.row == idx - 1:  # Relacionar con la fila
                img_bytes = img._data()
                images[sku] = img_bytes  # Almacenar la imagen en un diccionario con SKU como clave
        
        # Filtramos solo las columnas necesarias
        rows.append([sku, imagen, descripcion, tamaño, precio_usd, unidades_por_caja])

    # Crear DataFrame con las columnas especificadas
    df = pd.DataFrame(rows, columns=[
        "SKU", "Imagen", "Descripcion", "Tamaño del producto", "Precio USD", "Unidades por caja"
    ])
    
    # Limpiar las filas con datos incompletos si es necesario
    df = df.dropna(subset=["SKU", "Descripcion", "Precio USD", "Unidades por caja"])  # Eliminar filas con datos faltantes en columnas críticas
    
    # Normalizar los datos
    df["descripcion_norm"] = df["Descripcion"].apply(quitar_acentos)
    
    # Limpiar precios (eliminando signos de dólar y comas)
    df["Precio USD"] = df["Precio USD"].apply(lambda x: float(str(x).replace("$", "").replace(",", "")) if isinstance(x, str) else x)
    
    return df, images

# --- Variables principales ---

st.set_page_config(page_title="Catálogo Millex", layout="wide")

# ID del archivo de Google Sheets
FILE_ID = "1JG-_vjmFXnWM13Xp6PCOzjgJkxks8BEF"  # Reemplazar con el ID de tu archivo

# Cargar el archivo Excel desde Google Drive
xls_path = fetch_excel_from_drive(FILE_ID)

# Cargar las hojas disponibles en el archivo Excel
wb = load_workbook(xls_path, data_only=True)
sheet_names = wb.sheetnames  # Obtener los nombres de las hojas

# Selección de la hoja a cargar (Perros, Gatos, etc.)
sheet_name = st.selectbox("Selecciona la línea de productos:", sheet_names)

# Cargar los productos desde la hoja seleccionada
df_base, images = load_products_from_sheet(str(xls_path), sheet_name)

if df_base.empty:
    st.stop()  # Detener la ejecución si no se encuentran datos válidos

# Búsqueda en productos
search_term = st.text_input("🔍 Buscar (SKU o descripción)…").strip().lower()
search_norm = quitar_acentos(search_term)

if search_term:
    df = df_base[
        df_base["descripcion_norm"].str.contains(search_norm, na=False)
        | df_base["SKU"].str.contains(search_norm, na=False)
    ]
else:
    df = df_base.copy()

# --- Carrito de compras --- 

if "cart" not in st.session_state:
    st.session_state["cart"] = []

# Función para agregar al carrito
def add_to_cart(sku, nombre, precio, cantidad=1):
    st.session_state["cart"].append({"SKU": sku, "Nombre": nombre, "Precio": precio, "Cantidad": cantidad})

# Mostrar carrito y total
def show_cart():
    if st.session_state["cart"]:
        st.write("### Carrito de compras")
        cart_df = pd.DataFrame(st.session_state["cart"])
        st.write(cart_df)
        total = sum(item["Precio"] * item["Cantidad"] for item in st.session_state["cart"])
        st.write(f"**Total: ${total:,.2f}**")
    else:
        st.write("### El carrito está vacío.")

# --- Paginación simple ---

ITEMS_PER_PAGE = 20
total_pages = max(1, math.ceil(len(df) / ITEMS_PER_PAGE))
page_key = f"page_{sheet_name}"
if page_key not in st.session_state:
    st.session_state[page_key] = 1

def prev_page():
    if st.session_state[page_key] > 1:
        st.session_state[page_key] -= 1

def next_page():
    if st.session_state[page_key] < total_pages:
        st.session_state[page_key] += 1

# Mostrar paginación
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    st.button("◀ Anterior", on_click=prev_page, disabled=st.session_state[page_key] == 1)
with col2:
    st.markdown(f"**Página {st.session_state[page_key]} de {total_pages}**")
with col3:
    st.button("Siguiente ▶", on_click=next_page, disabled=st.session_state[page_key] == total_pages)

start_idx = (st.session_state[page_key] - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
df_page = df.iloc[start_idx:end_idx]

# --- Mostrar productos con imagen y carrito ---

for _, row in df_page.iterrows():
    st.write(f"**SKU:** {row['SKU']}")
    st.write(f"**Descripción:** {row['Descripcion']}")
    st.write(f"**Tamaño del producto:** {row['Tamaño del producto']}")
    st.write(f"**Precio unitario (USD):** ${row['Precio USD']:,.2f}")
    st.write(f"**Unidades por caja:** {row['Unidades por caja']}")
    
    # Mostrar imagen (si existe en el diccionario de imágenes)
    if row['SKU'] in images:
        img_bytes = images[row['SKU']]
        st.image(img_bytes, caption=row['Descripcion'], width=150)  # Ajustar tamaño de imagen a 150px de ancho
    
    # Campo para ingresar cantidad de cajas
    cantidad = st.number_input(f"Cantidad de {row['SKU']}", min_value=1, max_value=100, value=1, step=1, key=row['SKU'])
    
    # Calcular el precio total basado en la cantidad de cajas y el precio por unidad
    total_price = row["Precio USD"] * row["Unidades por caja"] * cantidad
    st.write(f"**Precio Total (USD):** ${total_price:,.2f}")
    
    # Botón para agregar al carrito
    if st.button(f"Agregar {row['SKU']} al carrito", key=f"add_{row['SKU']}"):
        add_to_cart(row['SKU'], row['Descripcion'], total_price, cantidad)
    
    st.markdown("---")

# Mostrar el carrito
show_cart()




