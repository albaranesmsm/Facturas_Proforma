# 🧾 Generador de Factura Proforma en Streamlit

Esta aplicación permite generar facturas proforma en PDF a partir de un formulario.

## 🚀 Funcionalidades

- Formulario dinámico con validación de OA/SGR.

- Selección de solicitante (BO/Taller, Almacén Central, Proveedor).

- Destinos de mercancía (Andorra, Canarias, Ceuta, Melilla).

- Añadir referencias dinámicamente con validación contra catálogo.

- Generación de PDF en horizontal con imágenes y tabla de artículos.

## 📂 Archivos necesarios

- **Catálogo** (`data/catalogo.xlsx`): columnas `Referencia`, `Descripcion`, `PrecioUD`.

- **Almacenes** (`data/almacenes.xlsx`): columnas `Almacen`, `Descripcion`.

- **Destinatarios** (`data/destinatarios.xlsx`) (opcional).

- **Imágenes** en la carpeta `images/` (`logo.png`, `footer.png`).

## ▶️ Ejecución en local

```bash

pip install -r requirements.txt

streamlit run app.py
 