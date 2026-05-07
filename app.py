import streamlit as st
import pandas as pd
import re
import unicodedata
import requests
from pypdf import PdfReader
from bs4 import BeautifulSoup
from io import BytesIO

# Configuración de página
st.set_page_config(page_title="IVANDAY Judicial Pro", layout="wide")

# --- 1. RÉPLICA DE FÓRMULAS EXCEL (COLUMNAS I A O) ---

def limpiar_cadena_excel(texto):
    """Réplica de limpieza profunda: quita acentos y caracteres no alfanuméricos"""
    if not texto or pd.isna(texto): return ""
    # Equivale a la normalización de texto en tus fórmulas
    texto = ''.join(c for c in unicodedata.normalize('NFD', str(texto).upper()) if unicodedata.category(c) != 'Mn')
    # Eliminar símbolos excepto la barra de expediente
    texto = re.sub(r'[^A-Z0-9/]', ' ', texto)
    return " ".join(texto.split())

def formatear_expediente_estricto(exp):
    """Extrae num/año eliminando ceros a la izquierda (Ej: 00541/2024 -> 541/2024)"""
    match = re.search(r"(\d+)/(\d{4})", str(exp))
    if match:
        return f"{int(match.group(1))}/{match.group(2)}"
    return None

def extraer_partes_validas(nombre_completo):
    """Filtra palabras irrelevantes para el cotejo (Réplica de lógica en Col J-L)"""
    limpio = limpiar_cadena_excel(nombre_completo)
    # Lista de exclusión de palabras que no identifican a la persona
    excluir = ["VS", "SECRETO", "SUCESION", "BIENES", "CONTRA", "EL", "LA", "DE", "LOS", "DEL"]
    palabras = [p for p in limpio.split() if len(p) > 3 and p not in excluir]
    return palabras

# --- 2. MOTOR DE PROCESAMIENTO ---

def realizar_doble_cotejo_judicial(texto_fuente, df_excel):
    # Preparar base de datos del Excel (Basado en Columnas B y D del archivo)
    base_busqueda = []
    for _, row in df_excel.iterrows():
        id_search = formatear_expediente_estricto(row.iloc[1]) # Columna B
        if id_search:
            base_busqueda.append({
                "id": id_search,
                "nombre": str(row.iloc[3]), # Columna D
                "claves": extraer_partes_validas(row.iloc[3])
            })

    lineas = texto_fuente.split('\n')
    resultados = []
    ciudad_actual = "TIJUANA"
    juzgado_actual = "JUZGADO"

    for i, linea in enumerate(lineas):
        l_norm = limpiar_cadena_excel(linea)
        
        # Identificar Ciudad y Juzgado (Contexto dinámico)
        for c in ["TIJUANA", "MEXICALI", "ENSENADA", "TECATE"]:
            if c in l_norm and len(l_norm) < 20: ciudad_actual = c
        if any(x in l_norm for x in ["JUZGADO", "SALA", "FAMILIAR", "CIVIL"]):
            juzgado_actual = linea.strip()

        # Detección de expedientes en el boletín
        exps_boletin = re.findall(r"(\d{1,5}/20\d{2})", linea)
        for e_bol in exps_boletin:
            id_bol = formatear_expediente_estricto(e_bol)
            
            for item in base_busqueda:
                if id_bol == item["id"]:
                    # --- EL DOBLE COTEJO (VALIDACIÓN DE NOMBRE) ---
                    # Revisamos la línea actual y la siguiente (ventana de 2 líneas)
                    ventana = l_norm
                    if i + 1 < len(lineas): 
                        ventana += " " + limpiar_cadena_excel(lineas[i+1])
                    
                    # Si alguna de las palabras clave del nombre está en el acuerdo, es positivo
                    matches = [c for c in item["claves"] if c in ventana]
                    if matches:
                        resultados.append({
                            "CIUDAD": ciudad_actual,
                            "JUZGADO": juzgado_actual,
                            "EXP": e_bol,
                            "CLIENTE": item["nombre"],
                            "ACUERDO": linea.strip()
                        })
    return resultados

# --- 3. INTERFAZ STREAMLIT ---

st.markdown("<h1 style='text-align: center; color: #E1AD01;'>⚖️ IVANDAY JUDICIAL MASTER</h1>", unsafe_allow_html=True)

if 'db' not in st.session_state: st.session_state.db = None

with st.sidebar:
    st.header("📂 Configuración Base")
    modo_ex = st.radio("Cargar Excel:", ["Local (.xlsx)", "Google Drive"])
    if modo_ex == "Local (.xlsx)":
        f = st.file_uploader("Sube el archivo", type=["xlsx"])
        if f: st.session_state.db = pd.read_excel(f, sheet_name="Expedientes")
    else:
        url_d = st.text_input("Link del Sheet:", value="https://docs.google.com/spreadsheets/d/1ssS6Zod7sUZnJBxTyBjzD5G9Arv4UNpn/edit")
        if url_d:
            # Conversión de link para descarga directa de datos
            url_d = re.sub(r'/edit.*', '/export?format=xlsx', url_d)
            st.session_state.db = pd.read_excel(url_d, sheet_name="Expedientes")

if st.session_state.db is not None:
    st.info(f"Base de datos cargada: {len(st.session_state.db)} registros.")
    
    st.header("🔍 Fuente del Boletín")
    fuente = st.selectbox("Selecciona fuente:", ["Enlace PJBC (.htm)", "Subir PDFs"])
    
    texto_analizar = ""
    if fuente == "Enlace PJBC (.htm)":
        url_pj = st.text_input("Pega el link del boletín:")
        if url_pj:
            r = requests.get(url_pj, verify=False)
            r.encoding = r.apparent_encoding
            texto_analizar = BeautifulSoup(r.text, 'html.parser').get_text(separator='\n')
    else:
        pdfs = st.file_uploader("Cargar archivos PDF", type=["pdf"], accept_multiple_files=True)
        if pdfs:
            for p in pdfs:
                reader = PdfReader(p)
                for page in reader.pages: texto_analizar += page.extract_text() + "\n"

    if st.button("🚀 EJECUTAR DOBLE COTEJO"):
        if texto_analizar:
            final_data = realizar_doble_cotejo_judicial(texto_analizar, st.session_state.db)
            if final_data:
                df = pd.DataFrame(final_data).drop_duplicates()
                for juz in df['JUZGADO'].unique():
                    with st.expander(f"🏛️ {juz}", expanded=True):
                        for _, r in df[df['JUZGADO'] == juz].iterrows():
                            st.write(f"✅ **{r['EXP']}** | {r['CLIENTE']}")
                            st.caption(f"Acuerdo: {r['ACUERDO']}")
            else:
                st.error("No se encontraron coincidencias bajo la lógica de doble cotejo.")
streamlit
pandas
openpyxl
requests
beautifulsoup4
