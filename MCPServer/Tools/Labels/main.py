from googleapiclient.discovery import Resource

def get_label_ids(
    service: Resource,
    labels: list
) -> list:
    """Esta función retorna los IDs de las etiquetas
    
    Args:
        service: Objeto de servicio autenticado de la API de Gmail (googleapiclient).
        labels: Lista con las etiquetas a las que se las quiere encontrar sus IDs.
        
    Returns:
        List: Lista con los IDs de las etiquetas."""
    all_labels = service.users().labels().list(userId="me").execute().get("labels", [])
    
    label_map = {label["name"].lower(): label["id"] for label in all_labels}
    
    label_ids = []
    missing_labels = []

    for name in labels:
        clean_name = name.lower()
        if clean_name in label_map:
            label_ids.append(label_map[clean_name])
        else:
            missing_labels.append(name)

    if missing_labels:
        raise ValueError(f"No se encontraron las siguientes etiquetas: {", ".join(missing_labels)}")

    return label_ids