from mcp.server.fastmcp import FastMCP

from typing import Annotated
from pydantic import Field

# Tools
from gmail_config import init_gmail_service, CREDENTIALS_PATH
from Tools.ReadThreads import main as read_threads
from Tools.SendEmails.main import send_email
from Tools.ReplyEmails import main as reply_emails
from Tools.Labels.main import get_label_ids

mcp = FastMCP("gmail-mcp")

service = init_gmail_service(CREDENTIALS_PATH)


### LECTURA DE EMAILS ###
#########################
@mcp.tool()
async def previsualizar_hilos(
    q: Annotated[str | None, Field(default=None, description="Consulta de búsqueda usando el formato nativo de Gmail. Por defecto es None (devuelve todo)", examples=["from:user@example.com is:unread", "<palabras clave> subject:urgente"])], 
    max_results: Annotated[int, Field(default=10, description="Número máximo de hilos de correo a recuperar. Debe estar entre 1 y 100", ge=1, le=100)]
) -> dict:
    """Busca y previsualiza hilos de correo en Gmail. Ideal para buscar correos específicos antes de leer su contenido completo

        Returns:
            dict: Un diccionario donde cada elemento contiene:
                - Thread_id: Identificador único del hilo (necesario para obtener el detalle completo)
                - Asunto: El asunto del hilo
                - N. mensajes: Cantidad total de mensajes en el hilo
                - Participantes: Lista de correos electrónicos de los remitentes y destinatarios
                - Snippets: Resúmenes de los mensajes del hilo"""    

    try:
        threads = read_threads.get_email_threads(service = service, q = q, max_results = max_results)
        data = read_threads.preview_threads(service, threads)
        return {"hilos": data}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def obtener_hilo_completo(
    thread_id: Annotated[str, Field(description="Identificador único del hilo (obtenido previamente mediante 'previsualizar_hilos')")]
) -> dict:
    """Recupera el contenido completo y los metadatos de todos los mensajes dentro de un hilo específico de Gmail 

    Returns:
        dict: Un diccionario con la estructura detallada del hilo:
            - Thread_id: ID del hilo
            - Asunto: Asunto del hilo
            - Mensajes: Lista de diccionarios, donde cada mensaje contiene:
                - msg_id: ID único del mensaje
                - Remitente: Dirección de email del autor
                - Destinatarios: Direcciones de email de los destinatarios
                - Fecha: Fecha de envío
                - Contenido: Cuerpo del mensaje limpio
                - Tiene archivos: True si el mensaje incluye adjuntos
                - Etiquetas: Etiquetas de Gmail aplicadas al mensaje"""
    
    try:
        data = read_threads.get_thread_details(service, thread_id)
        return {"hilo": data}
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
    name: Annotated[str, Field(description="Nombre de la etiqueta")]
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

def main():
    mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main()