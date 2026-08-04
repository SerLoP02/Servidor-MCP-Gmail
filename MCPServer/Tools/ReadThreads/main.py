from gmail_config import logger
from googleapiclient.discovery import Resource
from functools import partial

from Tools.ReadThreads import utils


## PRUEBAS
from gmail_config import init_gmail_service, CREDENTIALS_PATH

def preview_threads(
    service: Resource,
    threads: list,
    callback_func: callable,
    chunk_size: int = 10
) -> list[dict]:
    """Esta función previsualiza un hilo. Útil para no tener que ver todo el contenido de un hilo (que puede ser grande)
    
    Args:
        service: Objeto de servicio autenticado de la API de Gmail (googleapiclient).
        threads: Los hilos que se van a previsualizar (resultado de la función get_email_threads de Tools/ReadThreads/main.py).
        callback_func: El callback que se ejecutará en el procesamiento de cada hilo.
        chunk_size: Cuántos hilos se procesarán a la vez.
        
    Returns:
        List[Dict]: Lista de diccionarios con la siguiente estructura:
            - Thread_id: El ID del hilo.
            - Asunto: El asunto del hilo.
            - Participantes: Participantes del hilo.
            - Snippets: Snippets de todos los mensajes del hilo."""

    resultados_temp = {}

    # Google nos exije que el callback tenga únicamente los argumentos (request_id, response, exception).
    # Con partial lo que hacemos es crear una nueva función donde el argumento que se le pase es el que se toma por defecto
    batch_callback = partial(callback_func, resultados_temp=resultados_temp)

    # Procesamos los lotes por sublotes (chunks) para no saturar la API de peticiones
    for i in range(0, len(threads), chunk_size):
        chunk = threads[i : i + chunk_size]
        batch = service.new_batch_http_request(callback=batch_callback)

        # Aquí es donde usamos los chunks para no saturar la API de peticiones
        for thread in chunk:
            request = service.users().threads().get(
                userId = "me",
                id = thread["id"],
                format = "full"
            )
            batch.add(request, request_id=thread["id"])

        batch.execute()

    final_results =  [resultados_temp[thread["id"]] for thread in threads if thread["id"] in resultados_temp]

    return final_results

def view_full_thread(
    service: Resource,
    thread_id: str
) -> dict:
    """Esta función lee todos los mensajes (mensajes completos, no snippets) que se han enviado en un hilo.
    
    Args:
        service: Objeto de servicio autenticado de la API de Gmail (googleapiclient).
        thread_id: El ID del hilo.
        
    Returns:
        dict: Diccionario con la siguiente estructura:
            - Asunto: El asunto del hilo (todos los mensajes comparten el mismo asunto).
            - Mensajes: Lista de diccionarios con los mensajes. Se incluyen el remitente, los destinatarios y el contenido del mensaje"""

    logger.info(f"Viendo los mensajes enteros del hilo ID: {thread_id}")

    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    messages = thread.get("messages", [])

    thread_details = {
        "Asunto": None,
        "Mensajes": []
    }

    first_message_headers = messages[0].get("payload", {}).get("headers", [])
    thread_details["Asunto"] = utils.get_email_header("Subject", first_message_headers)

    for message in messages:
        thread_details["Mensajes"].append(utils.get_message_headers(message))
        
    return thread_details

def get_messages_ids_and_atts_from_threads(
    service: Resource,
    thread_id: str
) -> list[dict]:
    """Esta función permite obtener los IDs de los mensajes de un hilo, así como si dichos mensajes contienen adjuntos.
    
    Args:
        service: Objeto de servicio autenticado de la API de Gmail (googleapiclient).
        thread_id: El ID del hilo que se quiere estudiar.
        
    Returns:
        List[Dict]: Una lista de diccionarios con la siguiente estructura:
            - message_id: El ID del mensaje.
            - snippet: Snippet del mensaje. Útil para saber a qué mensaje se está haciendo referencia.
            - filenames: Nombre de los archivos (si los hubiere) adjuntados en el mensaje."""

    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    messages = thread.get("messages")

    thread_details = []

    for message in messages:
        thread_details_dict = dict(
            message_id = message.get("id"),
            snippet = message.get("snippet"),
            filenames = utils.get_attachment_names_from_message(message)
        )
        thread_details.append(thread_details_dict)

    return thread_details
    

if __name__ == "__main__":

    import json
    service = init_gmail_service(CREDENTIALS_PATH)
    threads = utils.get_email_threads(service, q="in:starred", max_results=50)
    thread_id = threads[1]["id"]
    print(get_messages_ids_from_threads(service, thread_id))