import streamlit as st
import pandas as pd
from openpyxl import load_workbook
from pathlib import Path
import unicodedata
import requests
import tempfile
import math

# --- Funciones base de tu código ---

def quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    ).lower()

@st.cache_data(show_spinner=False)
def fetch_excel(file_id: str) -> Path:
    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    tmp = Path(tempfile.gettempdir()) / f"{file_id}.xlsx"
    tmp.write_bytes(r.content)
    return tmp

@st.cache_data(show_spinner=False)
def load_products(xls_path: str, sheet_name: str) -> pd.DataFrame:
    wb = load_workbook(xls_path, data_only=True)
    ws = wb[sheet_name]  # Cargar la hoja específica
    rows = []
    for idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        if not row[1]:
            break
        codigo, detalle, precio = row[1], row[2], row[3]
        precio = 0 if precio is None else float(str(precio).replace("$", "").replace(",", ""))
        rows.append({"fila_excel": idx, "codigo": str(codigo), "detalle": str(detalle), "precio": precio})
    df = pd.DataFrame(rows)
    # Columnas normalizadas para búsqueda
    df["codigo_norm"]  = df["codigo"].apply(quitar_acentos)
    df["detalle_norm"] = df["detalle"].apply(quitar_acentos)
    return df

# --- Variables principales ---

FILE_IDS = {
    "Catálogo Productos": "1JG-_vjmFXnWM13Xp6PCOzjgJkxks8BEF",  # ID actualizado
}

st.set_page_config(page_title="Catálogo Millex", layout="wide")

linea = st.selectbox("Elegí la línea de productos:", ["Perros", "Gatos"])
search_term = st.text_input("🔍 Buscar (código o descripción)…").strip().lower()
search_norm = quitar_acentos(search_term)

# Determinar el nombre de la hoja a cargar
sheet_name = "Perros" if linea == "Perros" else "Gatos"

df_base = load_products(str(fetch_excel(FILE_IDS["Catálogo Productos"])), sheet_name)

if search_term:
    df = df_base[
        df_base["codigo_norm"].str.contains(search_norm, na=False)
        | df_base["detalle_norm"].str.contains(search_norm, na=False)
    ]
else:
    df = df_base.copy()

# --- Paginación simple ---

ITEMS_PER_PAGE = 20
total_pages = max(1, math.ceil(len(df) / ITEMS_PER_PAGE))
page_key = f"page_{linea}"
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

# --- Mostrar productos ---

for _, row in df_page.iterrows():
    st.write(f"**Código:** {row['codigo']}")
    st.write(f"**Detalle:** {row['detalle']}")
    st.write(f"**Precio:** ${row['precio']:,.2f}")
    st.markdown("---")






