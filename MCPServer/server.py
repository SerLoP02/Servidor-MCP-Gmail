from mcp.server.fastmcp import FastMCP

# Tools
from gmail_config import init_gmail_service, CREDENTIALS_PATH
from Tools.ReadThreads import main as read_threads
from Tools.SendEmails.main import send_email
from Tools.ReplyEmails import main as reply_emails

mcp = FastMCP("gmail-mcp")

service = init_gmail_service(CREDENTIALS_PATH)

### LECTURA DE EMAILS ###
#########################
@mcp.tool()
async def previsualizar_hilos(
    q: str | None = None, 
    max_results: int = 10
) -> dict:
    """Busca y previsualiza hilos de correo en Gmail. Ideal para buscar correos específicos antes de leer su contenido completo.

        Args:
            q: Cadena de texto para filtrar correos usando la sintaxis exacta 
                de búsqueda de Gmail. Puedes usar operadores como 'from:user@example.com', 'is:unread', 
                'subject:urgente', o palabras clave generales. Por defecto es None (devuelve todo).
            max_results: Número máximo de hilos de correo a recuperar. Por defecto es 10.
        Returns:
            dict: Un diccionario donde cada elemento contiene:
                - Thread_id: Identificador único del hilo (necesario para obtener el detalle completo).
                - Asunto: El asunto del hilo.
                - N. mensajes: Cantidad total de mensajes en el hilo.
                - Participantes: Lista de correos electrónicos de los remitentes y destinatarios.
                - Snippets: Resúmenes de los mensajes del hilo."""    

    try:
        threads = read_threads.get_email_threads(service = service, q = q, max_results = max_results)
        data = read_threads.preview_threads(service, threads)
        return {"hilos": data}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def obtener_hilo_completo(
    thread_id: str
) -> dict:
    """Recupera el contenido completo y los metadatos de todos los mensajes dentro de un hilo específico de Gmail.

    Args:
        thread_id: El identificador único del hilo (obtenido previamente mediante "previsualizar_hilos").

    Returns:
        dict: Un diccionario con la estructura detallada del hilo:
            - Thread_id: ID del hilo.
            - Asunto: Asunto del hilo.
            - Mensajes: Lista de diccionarios, donde cada mensaje contiene:
                - msg_id: ID único del mensaje.
                - Remitente: Dirección de email del autor.
                - Destinatarios: Direcciones de email de los destinatarios.
                - Fecha: Fecha de envío.
                - Contenido: Cuerpo del mensaje limpio.
                - Tiene archivos: True si el mensaje incluye adjuntos.
                - Etiquetas: Etiquetas de Gmail aplicadas al mensaje."""
    
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
    destinatario: str,
    asunto: str,
    cuerpo: str
) -> dict:
    """Envía un correo electrónico a través de Gmail.  
    
    Args:
        destinatario: Dirección de correo electrónico completa del receptor.
        asunto: El título o línea de asunto del correo.
        cuerpo: El contenido textual del mensaje.
        
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
    thread_id: str,
    cuerpo: str
) -> dict:
    """Responde a un hilo de correo existente en Gmail.

    Args:
        thread_id: El identificador único del hilo al que se desea responder (obtenido previamente mediante "previsualizar_hilos").
        cuerpo: El contenido textual del mensaje de respuesta.

    Returns:
        dict: Un diccionario con el status del envío.
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



def main():
    mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main()