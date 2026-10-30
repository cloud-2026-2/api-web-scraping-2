import requests
from bs4 import BeautifulSoup
import boto3
import uuid

def lambda_handler(event, context):
    # 1. MODIFICACIÓN: URL oficial del Instituto Geofísico del Perú (IGP)
    url = "https://ultimosismo.igp.gob.pe/productos/reportes-sismicos"

    # Realizar la solicitud HTTP a la página web
    response = requests.get(url)
    if response.status_code != 200:
        return {
            'statusCode': response.status_code,
            'body': 'Error al acceder a la página web del IGP'
        }

    # Parsear el contenido HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Encontrar la tabla en el HTML
    table = soup.find('table')
    if not table:
        return {
            'statusCode': 404,
            'body': 'No se encontró la tabla de sismos en la página web'
        }

    # Extraer y limpiar los encabezados de la tabla
    headers = [header.text.strip() for header in table.find_all('th')]

    # Extraer las filas de la tabla
    rows = []
    
    # 2. MODIFICACIÓN: Usamos un slice [:10] para procesar estrictamente las primeras 10 filas (los 10 últimos sismos)
    all_rows = table.find_all('tr')[1:]  # Omitir la fila de cabecera
    target_rows = all_rows[:10]  # Filtrar solo los 10 sismos más recientes

    for row in target_rows:
        cells = row.find_all('td')
        if len(cells) == 0:
            continue
            
        row_data = {}
        for i, cell in enumerate(cells):
            if i < len(headers):
                header_name = headers[i]
                # Si la cabecera está vacía (ej. columna "Ver reporte"), se asigna un nombre por defecto
                if not header_name:
                    header_name = f"Columna_{i}"
                row_data[header_name] = cell.text.strip()
        
        rows.append(row_data)

    # 3. CONEXIÓN A DYNAMODB: Conectamos a la tabla designada
    dynamodb = boto3.resource('dynamodb')
    # Nota: Puedes cambiar 'TablaWebScrapping' si creaste una nueva tabla específica para sismos
    dynamo_table = dynamodb.Table('TablaWebScrapping')

    # Vaciar los registros existentes antes de actualizar
    scan = dynamo_table.scan()
    with dynamo_table.batch_writer() as batch:
        for each in scan['Items']:
            batch.delete_item(
                Key={
                    'id': each['id']
                }
            )

    # Insertar los 10 nuevos sismos mapeados
    i = 1
    for row in rows:
        # Limpiar campos vacíos para evitar problemas con las políticas de DynamoDB
        item_to_insert = {k: v for k, v in row.items() if v != ""}
        
        item_to_insert['#'] = str(i) 
        item_to_insert['id'] = str(uuid.uuid4())  
        
        dynamo_table.put_item(Item=item_to_insert)
        i = i + 1

    # Retornar la respuesta exitosa en JSON con los 10 sismos
    return {
        'statusCode': 200,
        'body': rows
    }

