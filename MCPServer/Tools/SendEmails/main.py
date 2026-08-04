from gmail_config import logger
from googleapiclient.discovery import Resource
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64
import os
from time import sleep
from ssl import SSLEOFError
from email_validator import validate_email, EmailNotValidError

def send_email(
    service: Resource, 
    to: str, 
    subject: str, 
    body: str,
    attachment_path: str | None = None
) -> str:

    tto = []
    # Validamos que los emails sean válidos y existan (nos aseguramos que la LLM introduzca bien los correos electrónicos)
    for recipient in to.split(","):
        try:
            recipient = recipient.strip()
            valid = validate_email(recipient, check_deliverability=True)
            to = valid.normalized
            tto.append(to)
        except EmailNotValidError as e:
            logger.error(f"Se ha producido un error al enviar el correo a {recipient}: {str(e)}", exc_info=True)
            raise ValueError(f"{recipient} no es un email válido: {str(e)}")
    to = ",".join(tto)
    
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