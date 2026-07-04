from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
import os


import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(filename)s:%(lineno)d - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger("GmailMCP")

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")

def create_service(
    client_secret_file: str, 
    api_name: str, 
    api_version: str, 
    scopes: list
) -> Resource | None:
    
    token_path = os.path.join(os.path.dirname(__file__), "token.json")

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
        logger.debug(f"Hay token previo")
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        logger.debug(f"Ningún token encontrado o el token ha expirado")
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.debug(f"Token expirado. Actualizando el token")
        else:
            logger.debug(f"No se ha encontrado ningún token. Creando uno nuevo")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    try:
        service = build(api_name, api_version, credentials=creds)
        logger.info(f"Conexión con la cuenta de Gmail realizada con éxito")
    except HttpError as error:
        logger.error(f"Ha ocurrido un error al conectarse a la cuenta de Gmail: {error}")
        service = None

    return service

def init_gmail_service(client_file: str) -> Resource | None:
    # Definimos los scopes aquí de forma explícita
    API_NAME = "gmail"
    API_VERSION = "v1"
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly", 
        "https://www.googleapis.com/auth/gmail.modify"
    ]
    return create_service(client_file, API_NAME, API_VERSION, SCOPES)

if __name__ == "__main__":
    
    init_gmail_service(os.path.join(os.path.dirname(__file__), "credentials.json"))
    