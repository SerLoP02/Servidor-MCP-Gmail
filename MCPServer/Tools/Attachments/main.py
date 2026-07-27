from gmail_config import init_gmail_service, logger
import base64
import os
from googleapiclient.discovery import Resource

def download_attachments(
    service: Resource,
    msg_id: str,
    target_dir: str
) -> None:
    """Esta función simplemente descarga todos los archivos adjuntos de un mensaje de Gmail
    
    Args:
        service: Objeto de servicio autenticado de la API de Gmail.
        msg_id: ID del mensaje que contiene los adjuntos.
        target_dir: Ruta relativa del directorio donde se descargarán los archivos adjuntos. Si no existe, se creará."""

    if not os.path.exists(target_dir):
        os.mkdir(target_dir)
    
    message = service.users().messages().get(userId="me", id=msg_id).execute()
    has_attachments = False

    for part in message["payload"].get("parts", []):
        if part["filename"]:
            att_id = part["body"]["attachmentId"]
            att = service.users().messages().attachments().get(userId="me", messageId=msg_id, id=att_id).execute()
            data = att["data"]
            file_data = base64.urlsafe_b64decode(data.encode("utf-8"))
            file_path = os.path.join(target_dir, part["filename"])
            with open(file_path, "wb") as f:
                f.write(file_data)
            has_attachments = True

    if not has_attachments:
        logger.error(f"El mensaje con ID '{msg_id}' no contiene archivos adjuntos", exc_info=True)
        raise ValueError(f"El mensaje con ID '{msg_id}' no contiene archivos adjuntos")
    return None