from mcp.server.fastmcp import FastMCP

# Tools
from gmail_config import init_gmail_service, CREDENTIALS_PATH
from Tools.ReadThreads import main as read_threads

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
            dict: Un diccionario con la estructura {"hilos": [list]}, donde cada elemento contiene:
                - Thread_id: Identificador único del hilo (necesario para obtener el detalle completo).
                - Asunto: El asunto del hilo.
                - N. mensajes: Cantidad total de mensajes en el hilo.
                - Participantes: Lista de correos electrónicos de los remitentes y destinatarios.
                - Snippets: Resúmenes de los mensajes del hilo.
    """    

    threads = read_threads.get_email_threads(service = service, q = q, max_results = max_results)
    data = read_threads.preview_threads(service, threads)
    return {"hilos": data}

@mcp.tool()
async def obtener_hilo_completo(
    thread_id: str
) -> dict:
    """
    Recupera el contenido completo y los metadatos de todos los mensajes dentro de un hilo específico de Gmail.

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
                - Etiquetas: Etiquetas de Gmail aplicadas al mensaje.
    """
    
    data = read_threads.get_thread_details(service, thread_id)
    return {"hilo": data}
### LECTURA DE EMAILS ###
#########################

def main():
    mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main()