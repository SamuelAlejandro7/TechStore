from decimal import Decimal
from typing import Optional
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field

from cargar_csv import load_fixture
from app.domain import (
    Customer,
    Order,
    OrderItem,
    Money,
    InvalidOrderTransition,
    InvalidOrderData,
    OrderItemLimitExceeded,
)
from app.specifications import evaluate_discount, calculate_discount_rate


app = FastAPI(
    title="TechStore U4 API",
    description="API REST para la administración y ciclo de vida de pedidos TechStore.",
    version="1.0.0",
)

# Repositorio en memoria inicializado a partir de los CSV
orders: dict[str, Order] = load_fixture()


def get_order_or_404(order_id: str) -> Order:
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} no encontrado")
    return order


# Modelos Pydantic para los requests y responses
class ShipRequest(BaseModel):
    tracking_number: str = Field(..., description="Número de guía de envío")


class CancelRequest(BaseModel):
    reason: str = Field(..., description="Motivo de cancelación")


class AddItemRequest(BaseModel):
    sku: str = Field(..., description="Código de producto (SKU)")
    quantity: int = Field(..., gt=0, description="Cantidad a agregar (debe ser mayor a 0)")
    unit_price: Decimal = Field(..., gt=0, description="Precio unitario en MXN")


@app.get("/orders", summary="Listar todos los pedidos")
def list_orders():
    """Retorna un listado resumido de todos los pedidos cargados."""
    return [
        {
            "id": order.id,
            "cliente_id": order.customer.id,
            "status": order.status.value,
            "units": order.units,
            "total_mxn": float(order.total.amount),
            "descuento": evaluate_discount(order),
        }
        for order in orders.values()
    ]


@app.get("/orders/{order_id}", summary="Obtener detalles de un pedido")
def get_order(order_id: str):
    """Obtiene los detalles completos de un pedido por su ID."""
    order = get_order_or_404(order_id)
    discount_pct = evaluate_discount(order)
    rate = calculate_discount_rate(order)
    total_amount = order.total.amount
    discount_amount = total_amount * rate
    final_amount = total_amount - discount_amount

    return {
        "id": order.id,
        "customer": {
            "id": order.customer.id,
            "is_vip": order.customer.is_vip,
            "active": order.customer.active,
        },
        "status": order.status.value,
        "has_promotion": order.has_promotion,
        "units": order.units,
        "total": float(total_amount),
        "discount_percentage": discount_pct,
        "discount_amount": float(discount_amount),
        "final_amount": float(final_amount),
        "items": [
            {
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price.amount),
                "subtotal": float(item.subtotal.amount),
            }
            for item in order.items
        ],
        "events": [
            {
                "name": event.name,
                "order_id": event.order_id,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in order.events
        ],
        "tracking_number": order.tracking_number,
        "cancellation_reason": order.cancellation_reason,
    }


@app.post("/orders/{order_id}/confirm", summary="Confirmar un pedido")
def confirm_order(order_id: str):
    """Pasa un pedido de DRAFT a CONFIRMED. Requiere artículos y cliente activo."""
    order = get_order_or_404(order_id)
    try:
        order.confirm()
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidOrderData as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "id": order.id,
        "status": order.status.value,
        "events": [e.name for e in order.events],
    }


@app.post("/orders/{order_id}/ship", summary="Enviar un pedido")
def ship_order(order_id: str, payload: ShipRequest):
    """Pasa un pedido de CONFIRMED a SHIPPED. Requiere número de guía no vacío."""
    order = get_order_or_404(order_id)
    try:
        order.ship(payload.tracking_number)
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidOrderData as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "id": order.id,
        "status": order.status.value,
        "tracking_number": order.tracking_number,
        "events": [e.name for e in order.events],
    }


@app.post("/orders/{order_id}/cancel", summary="Cancelar un pedido")
def cancel_order(order_id: str, payload: CancelRequest):
    """Pasa un pedido de CONFIRMED a CANCELLED. Requiere un motivo no vacío."""
    order = get_order_or_404(order_id)
    try:
        order.cancel(payload.reason)
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidOrderData as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "id": order.id,
        "status": order.status.value,
        "cancellation_reason": order.cancellation_reason,
        "events": [e.name for e in order.events],
    }


@app.post("/orders/{order_id}/deliver", summary="Entregar un pedido")
def deliver_order(order_id: str):
    """Pasa un pedido de SHIPPED a DELIVERED."""
    order = get_order_or_404(order_id)
    try:
        order.deliver()
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {
        "id": order.id,
        "status": order.status.value,
        "events": [e.name for e in order.events],
    }


@app.post("/orders/{order_id}/return", summary="Devolver un pedido")
def return_order(order_id: str):
    """Pasa un pedido de SHIPPED a RETURNED."""
    order = get_order_or_404(order_id)
    try:
        order.return_order()
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {
        "id": order.id,
        "status": order.status.value,
        "events": [e.name for e in order.events],
    }


@app.post("/orders/{order_id}/items", summary="Agregar un artículo al pedido")
def add_item_to_order(order_id: str, item_req: AddItemRequest):
    """Agrega un artículo a un pedido en estado DRAFT, respetando el límite de 20 unidades."""
    order = get_order_or_404(order_id)
    try:
        item = OrderItem(
            sku=item_req.sku,
            quantity=item_req.quantity,
            unit_price=Money(item_req.unit_price, "MXN"),
        )
        order.add_item(item)
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (InvalidOrderData, OrderItemLimitExceeded) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "id": order.id,
        "units": order.units,
        "total": float(order.total.amount),
        "items_count": len(order.items),
    }


@app.post("/reset", summary="Reiniciar fixtures en memoria")
def reset_fixtures():
    """Recarga los pedidos originales desde los archivos CSV."""
    global orders
    orders = load_fixture()
    return {"message": "Fixtures reiniciados correctamente", "total_orders": len(orders)}
