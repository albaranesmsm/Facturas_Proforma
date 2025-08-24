import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import os
# ==========================
# FUNCIONES DE APOYO
# ==========================
def load_excel(path):
   """Carga un Excel si existe, si no devuelve DataFrame vacío."""
   if not os.path.exists(path):
       st.error(f"No se encuentra el archivo requerido: {path}")
       return pd.DataFrame()
   try:
       df = pd.read_excel(path)
       # Normalizar nombres de columnas
       df.columns = df.columns.str.strip().str.title()
       return df
   except Exception as e:
       st.error(f"Error al leer {path}: {e}")
       return pd.DataFrame()

def generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, referencias):
   """Genera el PDF de la factura proforma con logo y footer."""
   buffer = BytesIO()
   doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
   elementos = []
   styles = getSampleStyleSheet()
   styleN = styles["Normal"]
   # === LOGO ARRIBA ===
   logo_path = "image/logo.png"
   if os.path.exists(logo_path):
       elementos.append(Image(logo_path, width=120, height=60))
       elementos.append(Spacer(1, 20))
   else:
       elementos.append(Paragraph("⚠️ LOGO NO DISPONIBLE", styleN))
       elementos.append(Spacer(1, 20))
   # === CABECERA ===
   elementos.append(Paragraph("<b>FACTURA PROFORMA</b>", styleN))
   elementos.append(Spacer(1, 12))
   elementos.append(Paragraph(f"Solicitante: {solicitante}", styleN))
   if almacen_desc:
       elementos.append(Paragraph(f"Almacén: {almacen_desc}", styleN))
   if proveedor:
       elementos.append(Paragraph(f"Proveedor: {proveedor}", styleN))
   elementos.append(Paragraph(f"Número OA/SGR: {oa_sgr}", styleN))
   elementos.append(Spacer(1, 12))
   # === DESTINO ===
   if destino_row is not None:
       dest = (
           f"<b>DESTINO:</b><br/>"
           f"{destino_row.get('Nombre', '')}<br/>"
           f"{destino_row.get('Direccion', '')}<br/>"
           f"{destino_row.get('Cp', '')} {destino_row.get('Ciudad', '')} ({destino_row.get('Pais', '')})<br/>"
           f"CIF: {destino_row.get('Cif', '')}"
       )
       elementos.append(Paragraph(dest, styleN))
       elementos.append(Spacer(1, 12))
   # === TABLA DE REFERENCIAS ===
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
           ("ALIGN", (1,1), (-1,-1), "CENTER"),
       ]))
       elementos.append(tabla)
       elementos.append(Spacer(1, 24))
   # === FOOTER DEBAJO DE LA TABLA ===
   footer_path = "image/footer.png"
   if os.path.exists(footer_path):
       elementos.append(Spacer(1, 30))
       elementos.append(Image(footer_path, width=180, height=60))
   else:
       elementos.append(Paragraph("⚠️ FOOTER NO DISPONIBLE", styleN))
   # === GENERAR PDF ===
   doc.build(elementos)
   pdf = buffer.getvalue()
   buffer.close()
   return pdf

# ==========================
# CARGA DE DATOS
# ==========================
catalogo = load_excel("data/catalogo.xlsx")
destinos = load_excel("data/destinos.xlsx")
almacenes = load_excel("data/almacenes.xlsx")
# ==========================
# INTERFAZ STREAMLIT
# ==========================
st.title("📄 Generador de Factura Proforma")
with st.form("form_factura"):
   st.subheader("1) Solicitante")
   solicitante = st.selectbox("Seleccione el solicitante", ["BO/Taller", "Almacén Central", "Proveedor"])
   almacen_desc = ""
   proveedor = ""
   if solicitante == "BO/Taller":
       cod_alm = st.text_input("Código de Almacén Solicitante")
       if cod_alm and not almacenes.empty:
           if "Codigo" in almacenes.columns:
               fila = almacenes[almacenes["Codigo"].astype(str).str.upper() == cod_alm.upper()]
               if not fila.empty:
                   almacen_desc = fila.iloc[0]["Descripcion"]
                   st.success(f"Descripción: {almacen_desc}")
               else:
                   st.error("Código de almacén no encontrado")
           else:
               st.error("El archivo de almacenes no tiene columna 'Codigo'")
   elif solicitante == "Proveedor":
       proveedor = st.text_input("Nombre del proveedor")
   st.subheader("2) OA / Traspaso SGR")
   oa_sgr = st.text_input("Número OA/SGR (obligatorio)")
   if oa_sgr and not (oa_sgr.startswith("OA") or oa_sgr.startswith("SGR")):
       st.error("El número debe comenzar por 'OA' o 'SGR'")
   st.subheader("3) Destino de la mercancía")
   destino = None
   destino_row = None
   if not destinos.empty and "Nombre" in destinos.columns:
       destino = st.selectbox("Seleccione destino", destinos["Nombre"].dropna().tolist())
       destino_row = destinos[destinos["Nombre"] == destino].iloc[0].to_dict() if destino else None
   else:
       st.error("No se pudo cargar el listado de destinos")
   st.subheader("4) Referencias")
   if "referencias" not in st.session_state:
       st.session_state["referencias"] = []
   col1, col2 = st.columns([2, 1])
   with col1:
       nueva_ref = st.text_input("Referencia", key="nueva_ref")
   with col2:
       nueva_cant = st.number_input("Cantidad", min_value=1, value=1, key="nueva_cant")
   add_ref = st.form_submit_button("➕ Añadir referencia")
   if add_ref and nueva_ref:
       if not catalogo.empty and "Referencia" in catalogo.columns:
           fila = catalogo[catalogo["Referencia"].astype(str) == str(nueva_ref)]
           if not fila.empty:
               descripcion = fila.iloc[0].get("Descripcion", "SIN DESCRIPCIÓN")
               precio = float(fila.iloc[0].get("PrecioUd", 0))
               importe = precio * nueva_cant
               st.session_state["referencias"].append({
                   "Referencia": nueva_ref,
                   "Cantidad": nueva_cant,
                   "Descripcion": descripcion,
                   "PrecioUD": precio,
                   "Importe": importe
               })
           else:
               st.error("Referencia no encontrada en el catálogo")
       else:
           st.error("No se pudo cargar el catálogo correctamente")
   if st.session_state["referencias"]:
       st.write("### Referencias añadidas")
       df_refs = pd.DataFrame(st.session_state["referencias"])
       st.table(df_refs)
   generar = st.form_submit_button("📄 Generar Factura Proforma")
# ==========================
# GENERAR PDF
# ==========================
if generar:
   if not oa_sgr:
       st.error("Debes introducir un número OA/SGR válido")
   elif destino_row is not None and st.session_state["referencias"]:
       pdf = generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, st.session_state["referencias"])
       st.download_button(
           "⬇️ Descargar PDF",
           data=pdf,
           file_name=f"FacturaProforma_{oa_sgr}.pdf",
           mime="application/pdf"
       )
   else:
       st.error("Faltan datos para generar la factura")
