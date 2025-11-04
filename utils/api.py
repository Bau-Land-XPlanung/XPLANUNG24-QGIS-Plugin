import requests

BASE_URL1 = "http://localhost:3004/dev/rest/public/qgis"
BASE_URL = "https://6tkb6m5vzc.execute-api.eu-central-1.amazonaws.com/dev/rest/public/qgis"

class ApiError(Exception):
    pass


def _get_headers(cognito_session):
    if not cognito_session:
        raise ApiError("Keine gültige Authentifizierung vorhanden.")
    id_token = cognito_session.ensure_valid_token()
    if not id_token:
        raise ApiError("Kein gültiges ID-Token verfügbar.")
    return {"Authorization": f"Bearer {id_token}"}


def APIGetOrderDetails(cognito_session, order_id: str) -> dict:
    """Holt die Details zu einem Auftrag."""
    url = f"{BASE_URL}/orders/{order_id}"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise ApiError(f"Fehler beim Laden der Orderdetails: {r.text}")
    return r.json().get("data", {})


def APIGetOrderTasks(cognito_session, order_id: str) -> dict:
    """Holt alle Aufgaben für einen Auftrag."""
    url = f"{BASE_URL}/orders/{order_id}/tasks"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise ApiError(f"Fehler beim Laden der Aufgaben: {r.text}")
    return r.json().get("data", [])

def APIGetOrderDocuments(cognito_session, order_id, review_id) -> list:
    """Holt alle Dokumente für einen Auftrag und Review."""
    url = f"{BASE_URL}/orders/{order_id}/documents/{review_id}"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise ApiError(f"Fehler beim Laden der Dokumente: {r.text}")
    return r.json().get("data", [])

def APIGetDownloadByPath(cognito_session, fileName: str, order_id: str, review_id: str) -> str:
    """Holt DownloadUrl fuer einen S3 Path"""
    url = f"{BASE_URL}/orders/{order_id}/documents/{review_id}/download?fileName={fileName}"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        raise ApiError(f"Fehler {r.status_code} beim Laden des Download-Links: {r.text}")
    return r.json().get("data", "")

def APILoadPlans(cognito_session) -> str:
    """Holt alle Pläne"""
    url = f"{BASE_URL}/plans"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        raise ApiError(f"Fehler {r.status_code} beim Laden der Plaene: {r.text}")
    return r.json().get("data", [])

def APIGetDownloadPlan(cognito_session, plan_id: str) -> str:
    """Holt DownloadUrl fuer einen Plan"""
    url = f"{BASE_URL}/plans/{plan_id}"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=39)
    if r.status_code != 200:
        raise ApiError(f"Fehler {r.status_code} beim Laden des Download-Links: {r.text}")
    return r.json().get("data", "")

def APIUploadPlan(cognito_session, s3_key, plan_id):
    """Registriert einen neuen Plan in der API nach dem Upload zu S3"""
    url = f"{BASE_URL}/plan"

    headers = _get_headers(cognito_session)
    headers["Content-Type"] = "application/json"
    
    payload = {
        'fileName': s3_key.split('/')[-1],
        'id': plan_id
    }
    
    r = requests.post(url, json=payload, headers=headers, timeout=60)

    if r.status_code == 409:
        plan = r.json().get("data", [])
        return plan.get("id")
    
    if r.status_code not in [200, 201, 202]:
        return False

    return True

def APILoadOrders(cognito_session) -> str:
    """Holt alle Aufträge"""
    url = f"{BASE_URL}/orders"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        raise ApiError(f"Fehler {r.status_code} beim Laden der Auftraege: {r.text}")
    return r.json().get("data", [])

def APIGetOrderAllMessaging(cognito_session, order_id: str) -> list:
    """Holt alle Nachrichten (alle Links) zu einem Auftrag."""
    url = f"{BASE_URL}/messaging/{order_id}"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        raise ApiError(f"Fehler beim Laden aller Nachrichten: {r.text}")
    return r.json().get("data", [])


def APIGetOrderLinkedMessaging(cognito_session, order_id: str, link_id: str, link_type: str) -> list:
    """Holt Nachrichten für einen bestimmten Link eines Auftrags."""
    url = f"{BASE_URL}/messaging/{order_id}/related/{link_id}/type/{link_type}"
    headers = _get_headers(cognito_session)
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        raise ApiError(f"Fehler beim Laden verknüpfter Nachrichten: {r.text}")
    return r.json().get("data", [])


def APIPostOrderLinkedMessaging(cognito_session, message_data: dict, company_id: str) -> dict:
    """Speichert eine neue Nachricht für einen Auftrag."""
    order_id = message_data.get("ordersId")
    if not order_id:
        raise ApiError("ordersId fehlt in den Nachrichtendaten.")

    url = f"{BASE_URL}/messaging"
    headers = _get_headers(cognito_session)
    headers["Content-Type"] = "application/json"

    payload = {
        "ordersId": order_id,
        "linkId": message_data.get("linkId"),
        "linkType": message_data.get("linkType"),
        "createdByCompany": company_id,
        "message": message_data.get("message"),
    }

    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code != 201:
        raise ApiError(f"Fehler beim Speichern der Nachricht: {r.text}")
    return r.json().get("data", {})

def APIGetUploadUrl(cognito_session) -> dict:
    """Holt eine presigned URL zum Upload eines Plans"""
    url = f"{BASE_URL}/plan-upload-url"
    headers = _get_headers(cognito_session)
    
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        raise ApiError(f"Fehler {r.status_code} beim Holen der Upload-URL: {r.text}")
    
    return r.json().get("data", {})