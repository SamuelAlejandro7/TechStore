import pytest
from fastapi.testclient import TestClient
from app.api import app, reset_fixtures


@pytest.fixture(autouse=True)
def setup_teardown_fixtures():
    """Reinicia el estado en memoria antes de cada prueba de la API."""
    reset_fixtures()
    yield
    reset_fixtures()


client = TestClient(app)


def test_api_list_orders():
    response = client.get("/orders")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 16
    assert data[0]["id"] == "O001"
    assert data[0]["status"] == "DRAFT"


def test_api_get_order_detail():
    response = client.get("/orders/O001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "O001"
    assert data["status"] == "DRAFT"
    assert data["units"] == 4
    assert data["total"] == 2100.0
    assert data["discount_percentage"] == "10%"
    assert data["customer"]["id"] == "C001"
    assert data["customer"]["is_vip"] is True


def test_api_order_not_found_404():
    response = client.get("/orders/NO_EXISTE")
    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"].lower()


def test_api_confirm_order_not_found_404():
    response = client.post("/orders/NO_EXISTE/confirm")
    assert response.status_code == 404


def test_api_confirm_order_empty_items_422():
    # O007 no tiene artículos
    response = client.post("/orders/O007/confirm")
    assert response.status_code == 422
    assert "Requiere artículos" in response.json()["detail"]


def test_api_confirm_inactive_customer_422():
    # O003 tiene cliente inactivo C003
    response = client.post("/orders/O003/confirm")
    assert response.status_code == 422
    assert "cliente activo" in response.json()["detail"]


def test_api_confirm_success_200():
    response = client.post("/orders/O001/confirm")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "O001"
    assert data["status"] == "CONFIRMED"
    assert "OrderConfirmed" in data["events"]


def test_api_confirm_double_transition_conflict_409():
    # Primera confirmación exitosa
    r1 = client.post("/orders/O013/confirm")
    assert r1.status_code == 200

    # Segunda confirmación produce conflicto 409
    r2 = client.post("/orders/O013/confirm")
    assert r2.status_code == 409
    assert "Solo DRAFT" in r2.json()["detail"]


def test_api_ship_missing_tracking_number_422():
    # Confirmamos primero
    client.post("/orders/O012/confirm")
    # Intentamos enviar con guía vacía
    response = client.post("/orders/O012/ship", json={"tracking_number": "   "})
    assert response.status_code == 422
    assert "Guía obligatoria" in response.json()["detail"]


def test_api_ship_success_200():
    client.post("/orders/O012/confirm")
    response = client.post("/orders/O012/ship", json={"tracking_number": "TRACK-XYZ-123"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SHIPPED"
    assert data["tracking_number"] == "TRACK-XYZ-123"
    assert "OrderShipped" in data["events"]


def test_api_cancel_from_shipped_conflict_409():
    client.post("/orders/O014/confirm")
    client.post("/orders/O014/ship", json={"tracking_number": "TRACK-XYZ-123"})
    # Cancelar desde SHIPPED debe fallar
    response = client.post("/orders/O014/cancel", json={"reason": "Ya no lo quiero"})
    assert response.status_code == 409
    assert "Solo CONFIRMED puede cancelarse" in response.json()["detail"]


def test_api_cancel_from_confirmed_success_200():
    client.post("/orders/O002/confirm")
    response = client.post("/orders/O002/cancel", json={"reason": "Error en dirección"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELLED"
    assert data["cancellation_reason"] == "Error en dirección"
    assert "OrderCancelled" in data["events"]


def test_api_add_item_limit_exceeded_422():
    # O009 tiene 19 unidades, agregar 2 excede 20
    response = client.post(
        "/orders/O009/items",
        json={"sku": "SKU003", "quantity": 2, "unit_price": 120.00},
    )
    assert response.status_code == 422
    assert "Máximo 20 unidades" in response.json()["detail"]


def test_api_add_item_success_200():
    # O002 tiene 2 unidades, agregar 3 da 5
    response = client.post(
        "/orders/O002/items",
        json={"sku": "SKU003", "quantity": 3, "unit_price": 120.00},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["units"] == 5
    assert data["total"] == 1050.0 + (3 * 120.0)
