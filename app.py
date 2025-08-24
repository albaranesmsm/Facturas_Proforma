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
   """Carga un Excel si existe y limpia espacios en columnas y valores."""
   if not os.path.exists(path):
       st.error(f"No se encuentra el archivo requerido: {path}")
       return pd.DataFrame()
   df = pd.read_excel(path)
   df.columns = df.columns.str.strip()
   for col in df.select_dtypes(include="object").columns:
       df[col] = df[col].astype(str).str.strip()
   return df
def generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, referencias):
   """Genera el PDF de la factura proforma."""
   buffer = BytesIO()
   doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
   elementos = []
   styles = getSampleStyleSheet()
   styleN = styles["Normal"]
   # Logo superior
   try:
       logo = Image("images/logo.png", width=120, height=50)
       elementos.append(logo)
   except:
       elementos.append(Paragraph("LOGO NO DISPONIBLE", styleN))
   elementos.append(Spacer(1, 12))
   elementos.append(Paragraph("<b>Material gratuito sin valor comercial (Valor a precio estadístico)</b>", styleN))
   elementos.append(Spacer(1, 12))
   elementos.append(Paragraph("Servicio POSTVENTA<br/>C/TITAN 15<br/>28045 - MADRID (ESPAÑA) CIF A28078202", styleN))
   elementos.append(Spacer(1, 12))
   # Destino
   if destino_row is not None:
       dest_text = f"""
<b>DESTINATARIO:</b><br/>
       {destino_row.get('Nombre','')}<br/>
       {destino_row.get('Direccion','')}<br/>
       {destino_row.get('CP','')} {destino_row.get('Ciudad','')} ({destino_row.get('Pais','')})<br/>
       CIF: {destino_row.get('CIF','')}
       """
   else:
       dest_text = "<b>DESTINATARIO:</b> No encontrado"
   elementos.append(Paragraph(dest_text, styleN))
   elementos.append(Spacer(1, 12))
   elementos.append(Paragraph(f"<b>NÚMERO DE FACTURA PROFORMA:</b> {oa_sgr}", styleN))
   elementos.append(Spacer(1, 12))
   # Tabla de referencias
   if referencias:
       data = [["Referencia", "Cantidad", "Descripción", "Precio/UD", "Importe"]]
       for ref in referencias:
           data.append([
               ref["Referencia"],
               ref["Cantidad"],
               ref["Descripcion"],
               f"{ref['PrecioUD']:.2f}",
               f"{ref['Importe']:.2f}"
           ])
       t = Table(data, repeatRows=1)
       t.setStyle(TableStyle([
           ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
           ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
           ("ALIGN", (0, 0), (-1, -1), "CENTER"),
           ("GRID", (0, 0), (-1, -1), 1, colors.black),
       ]))
       elementos.append(t)
   elementos.append(Spacer(1, 24))
   # Pie de página
   try:
       pie = Image("images/pie.png", width=200, height=50)
       elementos.append(pie)
   except:
       elementos.append(Paragraph("PIE NO DISPONIBLE", styleN))
   # Construcción del PDF
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
# Debug opcional para comprobar columnas cargadas
# st.write("Columnas catálogo:", catalogo.columns.tolist())
# st.write("Columnas destinos:", destinos.columns.tolist())
# st.write("Columnas almacenes:", almacenes.columns.tolist())
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
       cod_alm = st.text_input("Código de Almacén Solicitante").strip()
       if cod_alm:
           if "Codigo" in almacenes.columns:
               fila = almacenes[almacenes["Codigo"].str.upper() == cod_alm.upper()]
               if not fila.empty:
                   almacen_desc = fila.iloc[0]["Descripcion"]
                   st.success(f"Descripción: {almacen_desc}")
               else:
                   st.error(f"Código de almacén '{cod_alm}' no encontrado en el fichero")
           else:
               st.error("El archivo de almacenes no contiene la columna 'Codigo'")
   elif solicitante == "Proveedor":
       proveedor = st.text_input("Nombre del proveedor")
   st.subheader("2) OA / Traspaso SGR")
   oa_sgr = st.text_input("Número OA/SGR (obligatorio)").strip()
   if oa_sgr and not (oa_sgr.startswith("OA") or oa_sgr.startswith("SGR")):
       st.error("El número debe comenzar por 'OA' o 'SGR'")
   st.subheader("3) Destino de la mercancía")
   destino = st.selectbox("Seleccione destino", destinos["Nombre"].tolist() if "Nombre" in destinos.columns else [])
   destino_row = destinos[destinos["Nombre"] == destino].iloc[0] if destino else None
   st.subheader("4) Referencias")
   if "referencias" not in st.session_state:
       st.session_state["referencias"] = []
   col1, col2 = st.columns([2, 1])
   with col1:
       nueva_ref = st.text_input("Referencia", key="nueva_ref").strip()
   with col2:
       nueva_cant = st.number_input("Cantidad", min_value=1, value=1, key="nueva_cant")
   # Botón para añadir referencias
   add_ref = st.form_submit_button("➕ Añadir referencia")
   if add_ref and nueva_ref:
       if "Referencia" in catalogo.columns:
           fila = catalogo[catalogo["Referencia"].str.upper() == nueva_ref.upper()]
           if not fila.empty:
               descripcion = fila.iloc[0]["Descripcion"]
               precio = float(fila.iloc[0]["PrecioUD"])
               importe = precio * nueva_cant
               st.session_state["referencias"].append({
                   "Referencia": nueva_ref,
                   "Cantidad": nueva_cant,
                   "Descripcion": descripcion,
                   "PrecioUD": precio,
                   "Importe": importe
               })
               st.success(f"Referencia {nueva_ref} añadida correctamente")
           else:
               st.error(f"Referencia '{nueva_ref}' no encontrada en el catálogo")
       else:
           st.error("El archivo de catálogo no contiene la columna 'Referencia'")
   if st.session_state["referencias"]:
       st.write("### Referencias añadidas")
       df_refs = pd.DataFrame(st.session_state["referencias"])
       st.table(df_refs)
   # Botón final de generación
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
