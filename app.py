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
   """Carga un Excel y limpia espacios en columnas."""
   if not os.path.exists(path):
       st.error(f"No se encuentra el archivo requerido: {path}")
       return pd.DataFrame()
   df = pd.read_excel(path)
   df.columns = df.columns.str.strip()
   return df
def generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, referencias):
   """Genera PDF de factura proforma."""
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
   elementos.append(Paragraph("<b>Material gratuito sin valor comercial</b>", styleN))
   elementos.append(Spacer(1, 12))
   elementos.append(Paragraph("Servicio POSTVENTA<br/>C/TITAN 15<br/>28045 - MADRID (ESPAÑA) CIF A28078202", styleN))
   elementos.append(Spacer(1, 12))
   # Destino
   if destino_row is not None:
       dest_text = f"""
<b>DESTINATARIO:</b><br/>
       {destino_row['Nombre']}<br/>
       {destino_row['Direccion']}<br/>
       {destino_row['CP']} {destino_row['Ciudad']} ({destino_row['Pais']})<br/>
       CIF: {destino_row['CIF']}
       """
   else:
       dest_text = "<b>DESTINATARIO:</b> No encontrado"
   elementos.append(Paragraph(dest_text, styleN))
   elementos.append(Spacer(1, 12))
   elementos.append(Paragraph(f"<b>NÚMERO DE FACTURA PROFORMA:</b> {oa_sgr}", styleN))
   elementos.append(Spacer(1, 12))
   # Tabla referencias
   if referencias:
       data = [["Referencia","Cantidad","Descripción","Precio/UD","Importe"]]
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
           ("BACKGROUND",(0,0),(-1,0),colors.grey),
           ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),
           ("ALIGN",(0,0),(-1,-1),"CENTER"),
           ("GRID",(0,0),(-1,-1),1,colors.black)
       ]))
       elementos.append(t)
   elementos.append(Spacer(1, 24))
   # Pie de página
   try:
       pie = Image("images/pie.png", width=200, height=50)
       elementos.append(pie)
   except:
       elementos.append(Paragraph("PIE NO DISPONIBLE", styleN))
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
# INICIALIZACIÓN DE STREAMLIT
# ==========================
st.title("📄 Generador de Factura Proforma")
if "referencias" not in st.session_state:
   st.session_state["referencias"] = []
# ==========================
# FORMULARIO PRINCIPAL
# ==========================
with st.form("form_factura", clear_on_submit=False):
   st.subheader("1) Solicitante")
   solicitante = st.selectbox("Seleccione el solicitante", ["BO/Taller", "Almacén Central", "Proveedor"])
   almacen_desc = ""
   proveedor = ""
   if solicitante == "BO/Taller":
       cod_alm = st.text_input("Código de Almacén Solicitante")
       if cod_alm:
           if "Codigo" not in almacenes.columns:
               st.error("La columna 'Codigo' no existe en almacenes.xlsx")
           else:
               fila_alm = almacenes[almacenes["Codigo"] == cod_alm]
               if not fila_alm.empty:
                   almacen_desc = fila_alm.iloc[0]["Descripcion"]
                   st.success(f"Descripción: {almacen_desc}")
               else:
                   st.error("Código de almacén no encontrado")
   elif solicitante == "Proveedor":
       proveedor = st.text_input("Nombre del proveedor")
   st.subheader("2) OA / Traspaso SGR")
   oa_sgr = st.text_input("Número OA/SGR (obligatorio)")
   if oa_sgr and not (oa_sgr.startswith("OA") or oa_sgr.startswith("SGR")):
       st.error("El número debe comenzar por 'OA' o 'SGR'")
   st.subheader("3) Destino")
   destino = st.selectbox("Seleccione destino", destinos["Nombre"].tolist())
   destino_row = destinos[destinos["Nombre"] == destino].iloc[0] if destino else None
   st.subheader("4) Referencias")
   col1, col2 = st.columns([2,1])
   with col1:
       nueva_ref = st.text_input("Referencia", key="ref_input")
   with col2:
       nueva_cant = st.number_input("Cantidad", min_value=1, value=1, key="cant_input")
   # Botones del formulario
   add_ref = st.form_submit_button("➕ Añadir referencia")
   generar_pdf_btn = st.form_submit_button("📄 Generar Factura Proforma")
# ==========================
# GESTIÓN DE REFERENCIAS
# ==========================
if add_ref:
   if not nueva_ref:
       st.error("Debes introducir una referencia")
   else:
       fila_ref = catalogo[catalogo["Referencia"] == nueva_ref]
       if not fila_ref.empty:
           descripcion = fila_ref.iloc[0]["Descripcion"]
           precio = fila_ref.iloc[0]["PrecioUD"]
           importe = precio * nueva_cant
           # Evitar duplicados
           st.session_state["referencias"].append({
               "Referencia": nueva_ref,
               "Cantidad": nueva_cant,
               "Descripcion": descripcion,
               "PrecioUD": precio,
               "Importe": importe
           })
       else:
           st.error("Referencia no encontrada en el catálogo")
# Mostrar referencias añadidas
if st.session_state["referencias"]:
   st.write("### Referencias añadidas")
   df_refs = pd.DataFrame(st.session_state["referencias"])
   st.table(df_refs)
   # Permitir eliminar referencias
   eliminar_idx = st.multiselect("Selecciona referencias para eliminar (opcional)", df_refs.index.tolist())
   if eliminar_idx:
       st.session_state["referencias"] = [r for i,r in enumerate(st.session_state["referencias"]) if i not in eliminar_idx]
       st.experimental_rerun()
# ==========================
# GENERAR PDF
# ==========================
if generar_pdf_btn:
   if not oa_sgr:
       st.error("Debes introducir un número OA/SGR válido")
   elif destino_row is None:
       st.error("Debes seleccionar un destino")
   elif not st.session_state["referencias"]:
       st.error("Debes añadir al menos una referencia")
   else:
       pdf_bytes = generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, st.session_state["referencias"])
       st.download_button(
           "⬇️ Descargar PDF",
           data=pdf_bytes,
           file_name=f"FacturaProforma_{oa_sgr}.pdf",
           mime="application/pdf"
       )
