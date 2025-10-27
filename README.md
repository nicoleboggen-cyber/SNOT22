# SNOT-22 + EVA (VAS) App (Streamlit)

Formulario para registrar RUT, SNOT-22 (0-5 cada item) y EVA (0-10) por visita; guarda en Google Sheets o CSV/XLSX local. Incluye anonimizacion opcional (hash SHA-256 con SALT).

## Despliegue rapido (Streamlit Community Cloud)
1) Crea un repo en GitHub y sube todo este directorio.
2) En Streamlit Cloud, crea una app apuntando a app.py (branch main).
3) En Secrets, pega y completa algo como:

[general]
SALT = "cambia_esto_por_un_salt_largo_y_unico"
STORE_PLAINTEXT_RUT = "false"

[gcp_service_account]
type = "service_account"
project_id = "TU_PROYECTO"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "tu-servicio@tu-proyecto.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"

[google]
GOOGLE_SHEET_ID = "ID_DE_TU_HOJA"
GOOGLE_SHEET_WORKSHEET = "Respuestas"

4) En Google Sheets: crea una hoja vacia, copia su ID (entre /d/ y /edit) y compartela con el client_email del service account (permiso Editor).
5) Lanza la app. Si no configuras Sheets, guardara en data/data.csv y data/data.xlsx.
6) (Opcional) Ajusta el consentimiento en la app segun tu CEI.

## Estructura de columnas
- timestamp (UTC ISO 8601)
- patient_id (SHA-256 de RUT normalizado + SALT)
- rut_plain (solo si STORE_PLAINTEXT_RUT="true")
- visit_date (YYYY-MM-DD)
- vas_0_10
- snot22_q1 ... snot22_q22
- snot22_total
- notes

## Ejecucion local
pip install -r requirements.txt
streamlit run app.py

Los datos se guardaran en data/ si no hay Google Sheets configurado.
