from gmail_config import init_gmail_service, logger
from googleapiclient.discovery import Resource
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64
import os
from time import sleep
from ssl import SSLEOFError

def send_email(
    service: Resource, 
    to: str, 
    subject: str, 
    body: str,
    attachment_path: str | None = None
) -> str:
    
    message = MIMEMultipart()
    message["to"] = to
    message["subject"] = subject
    message.attach(MIMEText(body))

    if attachment_path:
        for attachment in attachment_path:
            try: 
                filename = os.path.basename(attachment)
                with open(attachment, "rb") as file:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(file.read())
                    encoders.encode_base64(part)                    
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={filename}"
                    )
                    message.attach(part)
            except FileNotFoundError:
                logger.warning(f"Archivo {filename} no encontrado")
                continue
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    max_retries = 3
    for i in range(max_retries):
        try:
            sent_message = service.users().messages().send(
                userId="me",
                body={"raw": raw_message}
            ).execute()
            
            logger.debug(f"Mensaje enviado con éxito en el intento {i+1}:\n{sent_message}")
            return "Mensaje enviado con éxito"
            
        except SSLEOFError:
            logger.debug(f"Ha fallado en el intento {i+1} por SSLEOFError")
            sleep(1)
            
        except Exception as e:
            logger.error(f"Error inesperado al enviar el correo: {e}")
            return f"Ha habido un problema al enviar el correo: {str(e)}"
            
    logger.error("No se pudo enviar el correo tras agotar todos los intentos por fallos de red.")
    return "No se pudo enviar el correo después de 3 intentos debido a fallos de red."