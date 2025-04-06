from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

# Configurações
SERVICE_ACCOUNT_FILE = '/coplab-456000-ceba63e1bafc.json'
FOLDER_ID = '1wRrJ6rgKckA3zSJVqWR8doj2AkfvPq0o'

SCOPES = ['https://www.googleapis.com/auth/drive']

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=credentials)

def upload_comprovante(file_path, file_name):
    file_metadata = {
        'name': file_name,
        'parents': [FOLDER_ID]
    }

    media = MediaFileUpload(file_path, resumable=True)
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    return file.get('id')  # ID do arquivo salvo no Drive
