from gmail_config import logger
from bs4 import BeautifulSoup
import re
from functools import partial
from email.utils import parsedate_to_datetime
import base64
from googleapiclient.discovery import Resource


def get_email_threads(
    service: Resource,
    user_id: str = "me",
    q: str | None = None,
    max_results: int = 100
) -> list:
    """
    Recupera una lista de hilos de correo desde Gmail aplicando filtros de búsqueda.

    Esta función gestiona automáticamente la paginación de la API de Gmail. Si el número 
    de correos solicitados supera los límites de la API, realiza múltiples llamadas 
    internas hasta completar la lista solicitada.

    Args:
        service: Objeto de servicio autenticado de la API de Gmail (googleapiclient).
        user_id: ID del usuario (por defecto 'me' para la cuenta autenticada).
        q: String de consulta opcional usando operadores de Gmail (ej. 'from:juan@email.com').
        max_results: Cantidad máxima de hilos a recuperar.

    Returns:
        Una lista de diccionarios con el resumen básico de cada hilo encontrado.
    """
    
    logger.info(f"Iniciando búsqueda de hilos para el usuario (max_results={max_results}, q={q}')")
    
    threads = []
    next_page_token = None

    while True:
        try:
                
            result = service.users().threads().list(
                userId = user_id,
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

def procesar_respuesta_hilo(request_id, response, exception, resultados_temp):
    """Callback para procesar la respuesta en lote de la API de Gmail"""
    if exception is not None:
        logger.error(f"Error en la petición por lote para el thread_id {request_id}: {str(exception)}", exc_info=True)
        return None

    logger.debug(f"Procesando respuesta del lote para thread_id: {request_id}")
    messages = response.get("messages", [])

    # Obtenemos el asunto
    primer_msg = messages[0] if messages else {}
    headers = primer_msg.get("payload", {}).get("headers", [])
    subject = next(
        (h["value"] for h in headers if h["name"].lower() == "subject"), "Sin asunto"
    )

    participantes = set()
    snippets = []

    for msg in messages:
        headers_msg = msg.get("payload", {}).get("headers", [])

        # Remitente
        sender = next(
            (h["value"] for h in headers_msg if h["name"].lower() == "from"), "Sin remitente"
        )
        participantes.add(sender)

        # Destinatarios
        recipients = next(
            (h["value"] for h in headers_msg if h["name"].lower() == "to"), "Sin destinatarios"
        )
        for r in recipients.split(","):
            participantes.add(r.strip())

        # Snippets
        snippet = msg.get("snippet", "")
        snippet = re.sub(r'[\u200b\u200c\u200d\ufeff\u034f]', '', snippet)
        snippet = re.sub(r'\s+', ' ', snippet).strip()
        snippets.append(snippet)  

    # Guardamos los resultados en el diccionario que le hemos pasado
    resultados_temp[request_id] = {
        "Thread_id": request_id,
        "N. Mensajes": len(messages),
        "Asunto": subject,
        "Participantes": list(participantes),
        "Snippets": snippets
    }
    return None 

def preview_threads(
    service: Resource,
    threads: list,
    callback_func: callable = procesar_respuesta_hilo
) -> list:
    
    logger.info(f"Preparando previsualización en lote para {len(threads)} hilos.")

    resultados_temp = {}

    # Google nos exije que el callback tenga únicamente los argumentos (request_id, response, exception)
    # Con partial lo que hacemos es crear una nueva función donde el argumento que se le pase es el que se
    # toma por defecto
    batch_callback = partial(callback_func, resultados_temp=resultados_temp)

    batch = service.new_batch_http_request(callback=batch_callback)

    for thread_item in threads:
        peticion = service.users().threads().get(
            userId="me",
            id=thread_item["id"],
            format="full"
        )
        batch.add(peticion, request_id=thread_item["id"])

    if threads:
        logger.info("Ejecutando petición en lote (Batch Request)...")
        batch.execute()
        logger.info(f"Petición en lote completada. Respuestas procesadas exitosamente: {len(resultados_temp)}")
    else:
        logger.warning("La lista de hilos proporcionada a preview_threads está vacía.")

    # Reconstruimos la lista final manteniendo el orden original
    resultado_final = [resultados_temp[t["id"]] for t in threads if t["id"] in resultados_temp]

    return resultado_final  

def extract_body(payload: dict) -> str:
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

def get_message_details(
    message: dict
) -> dict:
    
    logger.debug(f"Extrayendo detalles del mensaje ID: {message.get("id")}")

    payload = message.get("payload", {})
    headers = payload.get("headers", [])

    # Remitente
    sender = next(
        (header["value"] for header in headers if header["name"].lower() == "from"), "Sin remitente"
    )

    # Destinatarios
    recipients = next(
        (header["value"] for header in headers if header["name"].lower() == "to"), "Sin destinatarios"
    )

    # Archivos adjuntados
    has_attachments = any(
        part.get("filename") for part in payload.get("parts", []) if part.get("filename")
    )

    # Fecha
    date = next(
        (header["value"] for header in headers if header["name"].lower() == "date"), "Sin fecha"
    )    
    date = parsedate_to_datetime(date)    
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", 
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    date = f"{dias[date.weekday()]}, {date.day} de {meses[date.month-1]} de {date.year} {date.strftime('%H:%M')}"

    # Etiquetas
    label = ", ".join(message.get("labelIds", []))

    # Cuerpo del correo
    body = extract_body(payload)   

    # Eliminamos espacios en blanco raros
    body = re.sub(r'[\u200b\u200c\u200d\ufeff\u034f\u200f\u200e]', '', body)

    return {
        "msg_id": message["id"],
        "Remitente": sender,
        "Destinatarios": recipients,
        "Fecha": date,
        "Contenido": body,
        "Tiene archivos": has_attachments,
        "Etiquetas": label
        }

def get_thread_details(
    service: Resource,
    thread_id: str
) -> dict:
    """
    Obtiene toda la información detallada de un hilo específico de correo.

    Realiza una consulta a la API de Gmail para traer el contenido completo, 
    procesando cada mensaje dentro del hilo para extraer el cuerpo del texto, 
    identificar si existen archivos adjuntos y limpiar caracteres invisibles 
    o codificaciones extrañas.

    Args:
        service: Objeto de servicio autenticado de la API de Gmail.
        thread_id: ID único del hilo a consultar (obtenido previamente).

    Returns:
        Un diccionario estructurado con los detalles del hilo: ID, asunto, 
        lista de mensajes (con remitente, destinatario, fecha y cuerpo), 
        y etiquetas aplicadas.

    Raises:
        Exception: Si la API de Google devuelve un error en la solicitud.
    """
    
    logger.info(f"Solicitando detalles completos del hilo ID: {thread_id}")
    
    try:
        thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    except Exception as e:
        logger.error(f"Error al obtener el hilo {thread_id} desde la API: {str(e)}", exc_info=True)
        raise e
        
    messages = thread.get("messages", [])
    logger.info(f"Hilo {thread_id} recuperado. Contiene {len(messages)} mensajes.")

    thread_details = {
        "Thread_id": thread_id,
        "Asunto": None,
        "Mensajes": []
    }

    first_header = messages[0].get("payload", {}).get("headers", [])
    thread_details["Asunto"] = next(
            (header["value"] for header in first_header if header["name"].lower() == "subject"), "Sin asunto"
        )

    for message in messages:
        thread_details["Mensajes"].append(get_message_details(message))

    return thread_details