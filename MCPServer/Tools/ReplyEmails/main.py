### ESTA FUNCIÓN ES PRÁCTICAMENTE IGUAL QUE LA DE ENVIAR EMAILS 
### SOLO QUE CAMBIA LA ESTRUCTURA DEL E-MAIL QUE HAY QUE ENVIAR

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

def get_message_headers_RFC(
    service: Resource,
    thread_id: str
):
    """Extrae las cabeceras RFC 2822 de un mensaje de Gmail para estructurar una respuesta.

    Analiza el último mensaje de un hilo específico para recuperar los identificadores 
    y metadatos necesarios que permiten mantener la continuidad de la conversación.

    Args:
        service (Resource): El objeto de servicio autenticado de la API de Gmail.
        thread_id (str): El identificador único del hilo de correo.

    Returns:
        dict: Un diccionario con las siguientes claves:
            - message_id: El ID del mensaje original (cabecera Message-ID).
            - to: La dirección de correo del primer destinatario distinto al propietario de la cuenta de Gmail.
            - subject: El asunto original del hilo ."""
    
    gmail_owner = service.users().getProfile(userId="me").execute().get("emailAddress")

    messages = service.users().threads().get(userId="me", id=thread_id).execute()["messages"]
    payload = messages[-1].get("payload", [])
    headers = payload.get("headers", [])

    message_id = next(
        (header["value"] for header in headers if header["name"].lower() == "Message-ID".lower()), None
    )

    for message in messages:
        hheaders = message.get("payload", []).get("headers", [])
        to = next(
            (hheader["value"] for hheader in hheaders if (hheader["name"].lower() == "From".lower()) and (gmail_owner not in hheader["value"])), None
        )
        if to:
            break

    subject = next(
        (header["value"] for header in headers if header["name"].lower() == "Subject".lower()), None
    )

    return {
        "message_id": message_id,
        "to": to,
        "subject": subject
    }


def reply_email(
    service: Resource, 
    to: str, 
    subject: str, 
    body: str,
    thread_id: str,
    message_id: str,
    attachment_path: list[str] | None = None,
) -> str:
    """Envía una respuesta a un hilo de correo existente en Gmail con soporte para adjuntos y reintentos automáticos.

    Configura automáticamente las cabeceras RFC 2822 (In-Reply-To y References), formatea el asunto con "Re:" y gestiona fallos de red temporales (SSLEOFError).

    Args:
        service (Resource): El objeto de servicio autenticado de la API de Gmail.
        to (str): Dirección de correo electrónico del destinatario.
        subject (str): El asunto del correo (se antepone 'Re:' automáticamente si corresponde).
        body (str): El contenido textual del mensaje de respuesta.
        thread_id (str): El ID del hilo de Gmail al que se vincula la respuesta. Por defecto es None.
        message_id (str): El ID del mensaje original para encadenar las cabeceras RFC. Por defecto es None.
        attachment_path (list[str] | None, optional): Lista con los nombres de los archivos a adjuntar. Por defecto es None.

    Returns:
        str: Un mensaje de texto indicando el éxito del envío o describiendo el error detallado tras agotar los intentos."""
    
    message = MIMEMultipart()
    message["to"] = to
    # Asegurar que si es una respuesta, el asunto comience con "Re: " (si no lo tiene ya)
    if message_id and not subject.lower().startswith("re:"):
        message["subject"] = f"Re: {subject}"
    else:
        message["subject"] = subject

    # Hay que añadir cabeceras RFC 2822 para responder al hilo (así viene en la documentación)
    if message_id:
        message["In-Reply-To"] = message_id
        message["References"] = message_id

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
                logger.error(f"El archivo {attachment} no ha sido encontrado", exc_info=True)
                raise FileNotFoundError(f"El archivo {attachment} no ha sido encontrado")
                    
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    api_body = {"raw": raw_message}
    # Esto también hay que añadirlo para que Gmail sepa a qué hilo está respondiendo
    api_body["threadId"] = thread_id

    max_retries = 3
    for i in range(max_retries):
        try:
            sent_message = service.users().messages().send(
                userId="me",
                body=api_body
            ).execute()
            
            logger.debug(f"Mensaje enviado con éxito en el intento {i+1}:\n{sent_message}")
            return "Mensaje enviado con éxito"
            
        except SSLEOFError:
            logger.debug(f"Ha fallado en el intento {i+1} por SSLEOFError")
            if i < max_retries - 1:
                sleep(1)
            else:
                logger.error("No se puedo enviar el correo tras agotar todos los intentos")
                raise ConnectionError("No se pudo enviar el correo tras 3 intentos debido a fallos de red SSL")