import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import os
# ==========================
# FUNCIONES AUXILIARES
# ==========================
def load_excel(path):
   """Carga un Excel desde /data, limpia nombres de columnas y valores string."""
   if not os.path.exists(path):
       st.error(f"No se encuentra el archivo requerido: {path}")
       return pd.DataFrame()
   try:
       df = pd.read_excel(path)
   except Exception as e:
       st.error(f"No se pudo leer '{path}': {e}")
       return pd.DataFrame()
   df.columns = df.columns.map(lambda x: str(x).strip())
   for col in df.select_dtypes(include="object").columns:
       df[col] = df[col].astype(str).str.strip()
   return df
def norm_series(s):
   return s.astype(str).str.strip().str.upper()
def norm_value(v):
   return str(v).strip().upper()
def pick_first_col(df, candidates):
   for c in candidates:
       if c in df.columns:
           return c
   return None
# ==========================
# CARGA DE ARCHIVOS FIJOS
# ==========================
catalogo = load_excel("data/catalogo.xlsx")
almacenes = load_excel("data/almacenes.xlsx")
destinos = load_excel("data/destinos.xlsx")
# Detectar columnas relevantes
col_ref = pick_first_col(catalogo, ["Referencia", "REF", "Articulo", "Artículo"])
col_desc = pick_first_col(catalogo, ["Descripcion", "Descripción", "Desc"])
col_price = pick_first_col(catalogo, ["PrecioUD", "Precio", "PVP"])
col_alm_codigo = pick_first_col(almacenes, ["Codigo", "Código", "Cod"])
col_alm_desc = pick_first_col(almacenes, ["Descripcion", "Descripción", "Desc"])
# Normalizar
if not catalogo.empty and col_ref:
   catalogo["__REF_NORM__"] = norm_series(catalogo[col_ref])
   if col_price:
       catalogo[col_price] = pd.to_numeric(catalogo[col_price], errors="coerce").fillna(0.0)
if not almacenes.empty and col_alm_codigo:
   almacenes["__COD_NORM__"] = norm_series(almacenes[col_alm_codigo])
# ==========================
# GENERAR PDF
# ==========================
def generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, referencias):
   buffer = BytesIO()
   doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
   elementos = []
   styles = getSampleStyleSheet()
   styleN = styles["Normal"]
   elementos.append(Paragraph("<b>Factura Proforma</b>", styleN))
   elementos.append(Spacer(1, 12))
   elementos.append(Paragraph(f"Solicitante: {solicitante}", styleN))
   if almacen_desc:
       elementos.append(Paragraph(f"Almacén: {almacen_desc}", styleN))
   if proveedor:
       elementos.append(Paragraph(f"Proveedor: {proveedor}", styleN))
   elementos.append(Paragraph(f"Número OA/SGR: {oa_sgr}", styleN))
   elementos.append(Spacer(1, 12))
   if destino_row:
       dest = (
           f"Destino: {destino_row.get('Nombre', '')}, "
           f"{destino_row.get('Direccion', '')}, "
           f"{destino_row.get('Ciudad', '')} ({destino_row.get('Pais', '')})"
       )
       elementos.append(Paragraph(dest, styleN))
   elementos.append(Spacer(1, 12))
   if referencias:
       data = [["Referencia", "Cantidad", "Descripción", "Precio/UD", "Importe"]]
       for ref in referencias:
           data.append([
               ref["Referencia"],
               ref["Cantidad"],
               ref["Descripcion"],
               f"{ref['PrecioUD']:.2f}",
               f"{ref['Importe']:.2f}",
           ])
       tabla = Table(data, repeatRows=1)
       tabla.setStyle(TableStyle([
           ("BACKGROUND", (0,0), (-1,0), colors.grey),
           ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
           ("GRID", (0,0), (-1,-1), 1, colors.black),
       ]))
       elementos.append(tabla)
   doc.build(elementos)
   pdf = buffer.getvalue()
   buffer.close()
   return pdf
# ==========================
# INTERFAZ
# ==========================
st.title("📄 Generador de Factura Proforma")
if "referencias" not in st.session_state:
   st.session_state["referencias"] = []
# Solicitante
solicitante = st.selectbox("Solicitante", ["BO/Taller", "Almacén Central", "Proveedor"])
almacen_desc = ""
proveedor = ""
if solicitante == "BO/Taller":
   cod_alm = st.text_input("Código de Almacén")
   if cod_alm and not almacenes.empty and col_alm_codigo:
       cod_norm = norm_value(cod_alm)
       match = almacenes[almacenes["__COD_NORM__"] == cod_norm]
       if not match.empty:
           almacen_desc = str(match.iloc[0][col_alm_desc]) if col_alm_desc else ""
           st.success(f"Almacén: {almacen_desc}")
       else:
           st.error(f"Código '{cod_alm}' no encontrado en almacenes.xlsx")
elif solicitante == "Proveedor":
   proveedor = st.text_input("Nombre del proveedor")
# OA/SGR
oa_sgr = st.text_input("Número OA/SGR")
if oa_sgr and not (oa_sgr.startswith("OA") or oa_sgr.startswith("SGR")):
   st.warning("El número debe comenzar por 'OA' o 'SGR'.")
# Destino
destinos_list = destinos["Nombre"].tolist() if "Nombre" in destinos.columns else []
destino = st.selectbox("Destino", destinos_list)
destino_row = destinos.loc[destinos["Nombre"] == destino].iloc[0].to_dict() if destino else None
# Referencias
st.subheader("Referencias")
ref = st.text_input("Referencia")
cant = st.number_input("Cantidad", min_value=1, value=1)
if st.button("➕ Añadir referencia"):
   if not col_ref:
       st.error("El catálogo no tiene columna de referencia.")
   else:
       ref_norm = norm_value(ref)
       fila = catalogo[catalogo["__REF_NORM__"] == ref_norm]
       if fila.empty:
           st.error(f"La referencia '{ref}' no existe en el catálogo.")
       else:
           descripcion = str(fila.iloc[0][col_desc]) if col_desc else ""
           precio = float(fila.iloc[0][col_price]) if col_price else 0.0
           importe = precio * cant
           st.session_state["referencias"].append({
               "Referencia": ref,
               "Cantidad": int(cant),
               "Descripcion": descripcion,
               "PrecioUD": precio,
               "Importe": importe
           })
           st.success(f"Referencia {ref} añadida.")
if st.session_state["referencias"]:
   st.write(pd.DataFrame(st.session_state["referencias"]))
# Generar PDF
if st.button("📄 Generar PDF"):
   if not oa_sgr:
       st.error("Introduce un número OA/SGR válido.")
   elif not (oa_sgr.startswith("OA") or oa_sgr.startswith("SGR")):
       st.error("El número OA/SGR debe empezar por 'OA' o 'SGR'.")
   elif solicitante == "BO/Taller" and not almacen_desc:
       st.error("Código de almacén no válido.")
   elif solicitante == "Proveedor" and not proveedor:
       st.error("Introduce el nombre del proveedor.")
   elif not destino_row:
       st.error("Selecciona un destino válido.")
   elif not st.session_state["referencias"]:
       st.error("Añade al menos una referencia.")
   else:
       pdf_bytes = generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, st.session_state["referencias"])
       st.download_button("⬇️ Descargar PDF", pdf_bytes, file_name=f"FacturaProforma_{oa_sgr}.pdf", mime="application/pdf")
