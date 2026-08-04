import re
from gmail_config import logger
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
import base64
from bs4 import BeautifulSoup


def get_email_threads(
    service: Resource,
    q: str | None = None,
    max_results: int = 10
) -> list[dict]:
    """
    Recupera una lista de hilos de correo desde Gmail aplicando filtros de búsqueda.

    Args:
        service: Objeto de servicio autenticado de la API de Gmail (googleapiclient).
        q: String de consulta opcional usando operadores de Gmail (ej. 'from:juan@email.com').
        max_results: Cantidad máxima de hilos a recuperar (por defecto 10).

    Returns:
        list[dict]: Una lista de diccionarios con la siguiente estructura:
            - id: ID único del hilo.
            - snippet: Breve parte del mensaje.
            - historyId: El ID de la última modificación que sufrió el hilo.
    """
    
    logger.info(f"Iniciando búsqueda de hilos para el usuario (max_results={max_results}, q={q}')")
    
    threads = []
    next_page_token = None

    while True:
        try:                
            result = service.users().threads().list(
                userId = "me",
                q = q,
                maxResults = min(500, max_results - len(threads)) if max_results else 500,
                pageToken = next_page_token
            ).execute()

            threads.extend(result.get("threads", []))

            next_page_token = result.get("nextPageToken")

            if not next_page_token or (max_results and len(threads) >= max_results):
                break
        except Exception as e:
            logger.error(f"Error al listar hilos de Gmail: {str(e)}", exc_info=True)
            break

    resultado = threads[:max_results] if max_results else threads
    logger.info(f"Búsqueda finalizada. Total de hilos retornados: {len(resultado)}")
    return resultado

def get_email_header(
    target_header: str,
    headers: list
) -> str:
    """Busca en los headers del email el header específico que se desea obtener.
    
    Args:
        target_header: El header específico que se desea obtener.
        headers: Todos los headers que contiene el email."""

    header = next(
        (h["value"] for h in headers if h["name"].lower() == target_header.lower()), None
    )

    return header

def callback_process_threads(
    request_id: set,
    response: dict,
    exception: HttpError | None,
    resultados_temp: dict
) -> None:
    """Callback para procesar los lotes de hilos de la API de Gmail
    
    Args:
        request_id: ID de la solicitud
        response: Respuesta deserializada de la solicitud
        exception: Si ocurrió error o no durante el procesamiento de la solicitud
        resultados_temp: Diccionario con los resultados de interés. La clave es el ID del hilo (para poder ordenarlos) y los valores son:
            - Thread_id: El id del hilo.
            - Asunto: El asunto del hilo.
            - Participantes: Lista con los participantes del hilo.
            - Snippers: Lista con los snippets de los mensajes del hilo."""

    if exception is not None:
        logger.error(f"Error en la petición por lote para el thread_id: {request_id}: {str(exception)}", exc_info=True)
        return None

    messages = response.get("messages", [])

    # Obtenemos el asunto
    primer_msg = messages[0] if messages else {}
    headers = primer_msg.get("payload", {}).get("headers", [])
    subject = get_email_header("Subject", headers)

    participants = set()
    snippets = []

    for message in messages:
        headers = message.get("payload", {}).get("headers", [])

        # Remitente
        sender = get_email_header("From", headers)
        participants.add(sender)

        # Destinatarios
        recipients = get_email_header("To", headers)
        for recipient in recipients.split(","):
            participants.add(recipient.strip())

        # Snippets
        snippet = message.get("snippet", "")
        snippet = re.sub(r"[\u0000-\u001F\u007F-\u009F\u2000-\u200F\u2028-\u202F\u2060-\u206F\ufeff\u034f]", "", snippet)
        snippet = re.sub(r'\s+', ' ', snippet).strip()
        snippets.append(snippet)

    resultados_temp[request_id] = {
        "Thread_id": request_id,
        "Asunto": subject,
        "Participantes": list(participants),
        "Snippets": snippets
    }

    return None

def extract_body(payload: dict) -> str:
    """Función para extraer y parsear a texto el cuerpo de los mensajes.
    
    Args:
        payload: El payload del email.
    
    Returns:
        str: El cuerpo del mensaje ya parseado."""
    body = "<Cuerpo del email no disponible>"

    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "multipart/alternative":
                for subpart in part["parts"]:
                    if subpart["mimeType"] == "text/plain" and "data" in subpart["body"]:
                        body = base64.urlsafe_b64decode(subpart["body"]["data"]).decode("utf-8")
                        break
            elif part["mimeType"] == "text/plain" and "data" in part["body"]:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                break
    
    if body == "<Cuerpo del email no disponible>" and "body" in payload and "data" in payload["body"]:
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

    if "<html" in body.lower() or "<body" in body.lower() or "<div" in body.lower():
        # Parseamos el HTML
        soup = BeautifulSoup(body, "html.parser")
        body = soup.get_text(separator="\n", strip=True)

    return body

def get_message_headers(message: dict) -> dict:
    """Función para obtener headers específicos de cada mensaje del hilo.
    
    Args:
        message: Diccionario que contiene detalles del email.

    Returns:
        dict: Diccionario con las cabeceras específicas del email:
            Remitente: Quién envió el mensaje.
            Destinatarios: A quién va dirido el mensaje.
            Contenido: El cuerpo del mensaje en texto plano."""

    logger.debug(f"Extrayendo detalles del mensaje ID: {message.get("id")}")

    payload = message.get("payload", {})
    headers = payload.get("headers", [])

    # Remitente
    sender = get_email_header("From", headers)

    # Destinatarios
    recipients = get_email_header("To", headers)

    # Cuerpo del email
    body = extract_body(payload)
    # Eliminamos caracteres raros PERO CONSERVAMOS saltos de línea (\n)
    body = re.sub(r"[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\u2000-\u200F\u2028-\u202F\u2060-\u206F\ufeff\u034f]", "", body)

    # Problema: la API de Gmail imprime en cada respuesta a un email las conversaciones pasadas. Para eliminar las respuestas anteriores, tenemos que ver que 
    # El texto empiece en \n seguido de >s.
    lineas = body.split('\n')
    lineas_limpias = []
    
    for linea in lineas:
        # Si la línea NO empieza por ">", es texto original de este mensaje
        if not linea.startswith(">"):
            lineas_limpias.append(linea)

    # Volvemos a unir las líneas limpias y quitamos los saltos de línea extra del final
    body = "\n".join(lineas_limpias).strip()

    return {
        "Remitente": sender,
        "Destinatarios": recipients,
        "Contenido": body
    }

def get_attachment_names_from_message(
    message: dict
) -> list | None:
    """Esta función sirve para obtener los nombres de los adjuntos (si los hay) de un mensaje de correo.
    
    Args:
        message: El mensaje de correo electrónico.
    
    Returns:
        Optional[List]: Lista con los nombres de los adjuntos si los hubiere."""

    filenames = [part["filename"] for part in message.get("payload", {}).get("parts", []) if part["filename"]]

    return filenames if filenames else None