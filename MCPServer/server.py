from mcp.server.fastmcp import FastMCP

from typing import Annotated
from pydantic import Field

# Tools
from gmail_config import init_gmail_service, CREDENTIALS_PATH, ATTACHMENTS_PATH
from Tools.ReadThreads import main as read_threads
from Tools.ReadThreads.utils import get_email_threads
from Tools.SendEmails.main import send_email
from Tools.ReplyEmails import main as reply_emails
from Tools.Labels.main import get_label_ids
from Tools.Attachments.main import download_attachments

mcp = FastMCP("gmail-mcp")

service = init_gmail_service(CREDENTIALS_PATH)


### LECTURA DE EMAILS ###
#########################
@mcp.tool()
async def previsualizar_hilos(
    q: Annotated[str | None, Field(default=None, description="Consulta de búsqueda usando el formato nativo de Gmail. Por defecto es None (devuelve todo)", examples=["from:user@example.com is:unread", "<palabras clave> subject:urgente"])], 
    max_results: Annotated[int, Field(default=10, description="Número máximo de hilos de correo a recuperar. Debe estar entre 1 y 100", ge=1, le=100)]
) -> dict:
    """Busca y previsualiza hilos de correo en Gmail. Esta herramienta sirve para filtrar entre los correos e identificar los adecuados.

        Returns:
            dict: Un diccionario de lista, donde cada elemento de la lista contiene:
                - Thread_id: El ID del hilo.
                - Asunto: El asunto del hilo.
                - Participantes: Participantes del hilo.
                - Snippets: Snippets de todos los mensajes del hilo."""    

    try:
        threads = get_email_threads(service = service, q = q, max_results = max_results)
        data = read_threads.preview_threads(service, threads)
        return {"hilos": data}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def leer_hilo_completo(
    thread_id: Annotated[str, Field(description="Identificador único del hilo (obtenido previamente mediante 'previsualizar_hilos')")]
) -> dict:
    """Recupera el contenido completo de todos los mensajes (ordenados de más antigüos a más recientes) dentro de un hilo específico de Gmail.
    Usa esta herramienta cuando necesites leer el contenido entero de un hilo o algunos mensajes enteros de un hilo.

    Returns:
        dict: Diccionario con la siguiente estructura:
            - Asunto: El asunto del hilo (todos los mensajes comparten el mismo asunto).
            - Mensajes: Lista de diccionarios con los mensajes. Se incluyen el remitente, los destinatarios y el contenido del mensaje"""
    
    try:
        data = read_threads.view_full_thread(service, thread_id)
        return {"hilo": data}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def obtener_message_ids_y_adjuntos_de_hilo(
    thread_id: Annotated[str, Field(description="Identificador único del hilo (obtenido previamente mediante 'previsualizar_hilos')")]
) -> dict:
    """Esta herramienta sirve para obtener los IDs de los mensajes de un hilo, así como si dichos mensajes contienen adjuntos.
    Returns:
        dict: Diccionario con la siguiente estructura:
            - message_id: El ID del mensaje.
            - snippet: Snippet del mensaje. Útil para saber a qué mensaje se está haciendo referencia.
            - filenames: Nombre de los archivos (si los hubiera) adjuntados en el mensaje."""

    try:
        resultado = read_threads.get_messages_ids_and_atts_from_threads(service, thread_id)
        return {"resultado": resultado}
    except Exception as e:
        return {"error": str(e)}
### LECTURA DE EMAILS ###
#########################


### ENVIO DE EMAILS ###
#########################
@mcp.tool()
async def enviar_email(
    destinatario: Annotated[str, Field(description="Dirección de correo electrónico del destinatario")],
    asunto: Annotated[str, Field(description="Asunto del correo")],
    cuerpo: Annotated[str, Field(description="Contenido textual del mensaje")]
) -> dict:
    """Envía un correo electrónico a través de Gmail
        
    Returns:
        dict: Un diccionario con el status del envío"""
    
    try:
        status = send_email(
            service = service,
            to = destinatario,
            subject = asunto,
            body = cuerpo
        )
        return {"status": status}
    except Exception as e:
        return {"error": str(e)}
### ENVIO DE EMAILS ###
#########################

### RESUPUESTA A EMAILS ###
############################
@mcp.tool()
async def responder_email(
    thread_id: Annotated[str, Field(description="Identificador único del hilo (obtenido previamente mediante 'previsualizar_hilos')")],
    cuerpo: Annotated[str, Field(description="Contenido textual del mensaje")]
) -> dict:
    """Responde a un hilo de correo existente en Gmail

    Returns:
        dict: Un diccionario con el status del envío
    """

    try:
        message_details = reply_emails.get_message_headers_RFC(service, thread_id)
        status = reply_emails.reply_email(
            service = service,
            body = cuerpo,
            thread_id = thread_id,
            **message_details
        )
        return {"status": status}
    except Exception as e:
        return {"error": str(e)}
### RESUPUESTA A EMAILS ###
############################


### MANEJO DE ETIQUETAS ###
############################
@mcp.tool()
async def crear_etiqeta(
    name: Annotated[str, Field(description="Nombre exacto de la etiqueta")]
) -> dict:
    """Crea una etiqueta de Gmail

    Returns:
        dict: Un diccionario con el status del envío"""

    try:
        body = {
            "name": name
        }
        service.users().labels().create(userId="me", body=body).execute()
        return {"status": "Se ha creado exitosamente la etiqueta"}
    except Exception as e:
        return {"error": f"Se ha producido el siguiente error al crear la etiqueta {name}: {str(e)}"}  

@mcp.tool()
async def eliminar_etiqueta(
    name: Annotated[str, Field(description="Nombre de la etiqueta. El nombre no distingue entre minúsculas y mayúsculas")]
) -> dict:
    """Elimina una etiqueta de Gmail
    
    Returns:
        dict: Un diccionario con el status del envío"""

    try:
        label_id = get_label_ids(service, [name])
        service.users().labels().delete(userId="me", id=label_id)
        return {"status": "Se ha eliminado exitosamente la etiqueta"}
    except Exception as e:
        return {"error": f"Se ha producido el siguiente error al eliminar la etiqueta {name}: {str(e)}"}

@mcp.tool()
async def asignar_etiquetas_a_hilo(
    thread_id: Annotated[str, Field(description="Identificador único del hilo (obtenido previamente mediante 'previsualizar_hilos')")],
    labels: Annotated[list[str], Field(description="Lista con los nombres de las etiquetas (tanto las por-defecto como las propias del usuario). Los nombres no distinguen entre minúsculas y mayúsculas", examples=[["trash"], ["spam", "starred", "<etiqueta_usuario>"]])]
) -> dict:
    """Añade una o varias etiquetas a un hilo de conversación de Gmail específico

    Returns:
        dict: Un diccionario con el status del proceso"""

    try:
        label_ids = get_label_ids(service, labels)
        body = {
            "addLabelIds": label_ids
        }
        service.users().threads().modify(userId="me", id = thread_id, body = body).execute()
        return {"status": "Se ha movido exitosamente el hilo a la etiqueta"}
    except Exception as e:
        return {"error": f"Se ha producido el siguiente error: {str(e)}"}

@mcp.tool()
async def quitar_etiquetas_a_hilo(
    thread_id: Annotated[str, Field(description="Identificador único del hilo (obtenido previamente mediante 'previsualizar_hilos')")],
        labels: Annotated[list[str], Field(description="Lista con los nombres de las etiquetas (tanto las por-defecto como las propias del usuario). Los nombres no distinguen entre minúsculas y mayúsculas", examples=[["unread"], ["spam", "<etiqueda_usuario>"]])]
) -> dict:
    """Quita una o varias etiquetas a un hilo de conversación de Gmail específico

    Returns:
        dict: Un diccionario con el status del proceso"""

    try:
        label_ids = get_label_ids(service, labels)
        body = {
            "removeLabelIds": label_ids
        }
        service.users().threads().modify(userId="me", id = thread_id, body = body).execute()
        return {"status": f"Se eliminado exitosamente el hilo de la etiqueta"}
    except Exception as e:
        return {"error": f"Se ha producido el siguiente error: {str(e)}"}
### MANEJO DE ETIQUETAS ###
############################


### DESCARGA DE ADJUNTOS ###
############################
@mcp.tool()
async def descargar_adjuntos(
    msg_id: Annotated[str, Field(description="ID del mensaje que contiene los archivos adjuntos (obtenido previamente mediante 'obtener_message_ids_y_adjuntos_de_hilo')")]
) -> dict:
    """Descarga todos los archivos adjuntos de un mensaje específico de Gmail

    Returns:
        dict: Un diccionario con el status del proceso"""

    try:
        download_attachments(service, msg_id, ATTACHMENTS_PATH)
        return {"status": "Archivos descargados exitosamente"}
    except Exception as e:
        return {"error": f"Se ha producido el siguiente error al descargar los archivos adjuntos: {str(e)}"}
### DESCARGA DE ADJUNTOS ###
############################


def main():
    mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main()