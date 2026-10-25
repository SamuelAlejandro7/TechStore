"""Ejecución de los 15 escenarios E01-E15 de TechStore U4.
Genera la bitácora requerida para el reporte.
"""
from decimal import Decimal
from cargar_csv import load_fixture
from app.domain import (
    OrderItem,
    Money,
    DomainException,
    InvalidOrderData,
    InvalidOrderTransition,
    OrderItemLimitExceeded,
)
from app.specifications import evaluate_discount


def run_scenarios():
    bitacora = []

    # E01: O001 evaluar_descuento -> 10%
    orders = load_fixture()
    o = orders["O001"]
    desc = evaluate_discount(o)
    bitacora.append({
        "caso": "E01",
        "pedido": "O001",
        "estado_inicial": o.status.value,
        "operacion": "evaluar_descuento",
        "resultado_real": f"Descuento {desc}",
        "evento": "Ninguno (solo lectura)",
        "estado_final": o.status.value,
        "explicacion": "Cumple regla 10%: Cliente VIP, total $2,100.00 > $500.00, 4 unidades >= 4 y sin promoción activa."
    })

    # E02: O002 evaluar_descuento -> 0%
    orders = load_fixture()
    o = orders["O002"]
    desc = evaluate_discount(o)
    bitacora.append({
        "caso": "E02",
        "pedido": "O002",
        "estado_inicial": o.status.value,
        "operacion": "evaluar_descuento",
        "resultado_real": f"Descuento {desc}",
        "evento": "Ninguno (solo lectura)",
        "estado_final": o.status.value,
        "explicacion": "No VIP (no aplica regla 10%) y total $1,050.00 <= $5,000.00 (no aplica regla 5%). Descuento 0%."
    })

    # E03: O003 confirmar -> rechazo (Cliente inactivo)
    orders = load_fixture()
    o = orders["O003"]
    try:
        o.confirm()
        res = "Éxito inesperado"
        ev = [e.name for e in o.events]
    except DomainException as exc:
        res = f"Rechazado ({type(exc).__name__}: {exc})"
        ev = [e.name for e in o.events] or "Sin eventos"
    bitacora.append({
        "caso": "E03",
        "pedido": "O003",
        "estado_inicial": "DRAFT",
        "operacion": "confirm()",
        "resultado_real": res,
        "evento": str(ev),
        "estado_final": o.status.value,
        "explicacion": "El cliente C003 está inactivo (activo=0); la regla exige artículos y cliente activo."
    })

    # E04: O005 evaluar_descuento -> 0% (Promoción activa bloquea)
    orders = load_fixture()
    o = orders["O005"]
    desc = evaluate_discount(o)
    bitacora.append({
        "caso": "E04",
        "pedido": "O005",
        "estado_inicial": o.status.value,
        "operacion": "evaluar_descuento",
        "resultado_real": f"Descuento {desc}",
        "evento": "Ninguno (solo lectura)",
        "estado_final": o.status.value,
        "explicacion": "Tiene promoción activa (tiene_promocion=1); ~ActivePromotionSpec evalúa False y bloquea descuentos."
    })

    # E05: O006 evaluar_descuento -> 5%
    orders = load_fixture()
    o = orders["O006"]
    desc = evaluate_discount(o)
    bitacora.append({
        "caso": "E05",
        "pedido": "O006",
        "estado_inicial": o.status.value,
        "operacion": "evaluar_descuento",
        "resultado_real": f"Descuento {desc}",
        "evento": "Ninguno (solo lectura)",
        "estado_final": o.status.value,
        "explicacion": "Cliente no VIP, pero total $18,000.00 > $5,000.00 y sin promoción; cumple regla de 5%."
    })

    # E06: O007 confirmar -> rechazo (Sin artículos)
    orders = load_fixture()
    o = orders["O007"]
    try:
        o.confirm()
        res = "Éxito inesperado"
        ev = [e.name for e in o.events]
    except DomainException as exc:
        res = f"Rechazado ({type(exc).__name__}: {exc})"
        ev = [e.name for e in o.events] or "Sin eventos"
    bitacora.append({
        "caso": "E06",
        "pedido": "O007",
        "estado_inicial": "DRAFT",
        "operacion": "confirm()",
        "resultado_real": res,
        "evento": str(ev),
        "estado_final": o.status.value,
        "explicacion": "El pedido no tiene artículos cargados (items vacío); confirm() rechaza pedidos vacíos."
    })

    # E07: O008 confirmar -> éxito (20 unidades permitidas)
    orders = load_fixture()
    o = orders["O008"]
    try:
        o.confirm()
        res = f"Confirmado con éxito ({o.status.value})"
        ev = [e.name for e in o.events]
    except DomainException as exc:
        res = f"Rechazado: {exc}"
        ev = [e.name for e in o.events]
    bitacora.append({
        "caso": "E07",
        "pedido": "O008",
        "estado_inicial": "DRAFT",
        "operacion": "confirm()",
        "resultado_real": res,
        "evento": str(ev),
        "estado_final": o.status.value,
        "explicacion": "El pedido contiene exactamente 20 unidades, que es el límite máximo permitido; cliente C008 activo."
    })

    # E08: O009 agregar SKU003 x2 -> rechazo (21 unidades excede límite)
    orders = load_fixture()
    o = orders["O009"]
    initial_units = o.units
    try:
        o.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00"))))
        res = "Éxito inesperado"
    except DomainException as exc:
        res = f"Rechazado ({type(exc).__name__}: {exc})"
    bitacora.append({
        "caso": "E08",
        "pedido": "O009",
        "estado_inicial": f"DRAFT ({initial_units} unidades)",
        "operacion": "add_item(SKU003, cant=2)",
        "resultado_real": res,
        "evento": "Sin eventos",
        "estado_final": f"DRAFT ({o.units} unidades)",
        "explicacion": "El pedido tenía 19 unidades; agregar 2 sumaría 21 unidades, superando el límite estricto de 20."
    })

    # E09: O010 evaluar_descuento -> 0% (Total exactamente 500)
    orders = load_fixture()
    o = orders["O010"]
    desc = evaluate_discount(o)
    bitacora.append({
        "caso": "E09",
        "pedido": "O010",
        "estado_inicial": o.status.value,
        "operacion": "evaluar_descuento",
        "resultado_real": f"Descuento {desc}",
        "evento": "Ninguno (solo lectura)",
        "estado_final": o.status.value,
        "explicacion": "Total es $500.00 exactos. La especificación exige monto estrictamente mayor a $500.00 (> 500), por lo que no califica."
    })

    # E10: O011 evaluar_descuento -> 0% (Solo 3 unidades)
    orders = load_fixture()
    o = orders["O011"]
    desc = evaluate_discount(o)
    bitacora.append({
        "caso": "E10",
        "pedido": "O011",
        "estado_inicial": o.status.value,
        "operacion": "evaluar_descuento",
        "resultado_real": f"Descuento {desc}",
        "evento": "Ninguno (solo lectura)",
        "estado_final": o.status.value,
        "explicacion": "Cliente VIP y total $1,500.00 > $500.00, pero solo tiene 3 unidades. La regla 10% exige mínimo 4 unidades."
    })

    # E11: O012 confirmar y enviar sin guía -> rechazo envío
    orders = load_fixture()
    o = orders["O012"]
    o.confirm()
    try:
        o.ship("")
        res = "Envío exitoso inesperado"
    except DomainException as exc:
        res = f"Rechazado en ship ({type(exc).__name__}: {exc})"
    ev = [e.name for e in o.events]
    bitacora.append({
        "caso": "E11",
        "pedido": "O012",
        "estado_inicial": "DRAFT",
        "operacion": "confirm() seguido de ship('')",
        "resultado_real": res,
        "evento": str(ev),
        "estado_final": o.status.value,
        "explicacion": "confirm() tuvo éxito (emitió OrderConfirmed), pero ship('') fue rechazado por no proporcionar número de guía; permanece en CONFIRMED."
    })

    # E12: O013 confirmar dos veces -> rechazo segunda
    orders = load_fixture()
    o = orders["O013"]
    o.confirm()
    try:
        o.confirm()
        res = "Segunda confirmación exitosa inesperada"
    except DomainException as exc:
        res = f"Segunda rechazada ({type(exc).__name__}: {exc})"
    ev = [e.name for e in o.events]
    bitacora.append({
        "caso": "E12",
        "pedido": "O013",
        "estado_inicial": "DRAFT",
        "operacion": "confirm() x2",
        "resultado_real": res,
        "evento": str(ev),
        "estado_final": o.status.value,
        "explicacion": "La primera llamada pasa a CONFIRMED y genera OrderConfirmed. La segunda falla con InvalidOrderTransition y no duplica el evento."
    })

    # E13: O014 confirmar, enviar y cancelar -> rechazo cancelación
    orders = load_fixture()
    o = orders["O014"]
    o.confirm()
    o.ship("TRACK-12345")
    try:
        o.cancel("Cliente solicitó cancelación")
        res = "Cancelación exitosa inesperada"
    except DomainException as exc:
        res = f"Cancelación rechazada ({type(exc).__name__}: {exc})"
    ev = [e.name for e in o.events]
    bitacora.append({
        "caso": "E13",
        "pedido": "O014",
        "estado_inicial": "DRAFT",
        "operacion": "confirm() -> ship() -> cancel()",
        "resultado_real": res,
        "evento": str(ev),
        "estado_final": o.status.value,
        "explicacion": "Solo se puede cancelar un pedido en estado CONFIRMED. En estado SHIPPED la cancelación es inválida; permanece en SHIPPED."
    })

    # E14: O015 confirmar, enviar y devolver -> éxito
    orders = load_fixture()
    o = orders["O015"]
    o.confirm()
    o.ship("TRACK-GUIA-99")
    o.return_order()
    ev = [e.name for e in o.events]
    bitacora.append({
        "caso": "E14",
        "pedido": "O015",
        "estado_inicial": "DRAFT",
        "operacion": "confirm() -> ship() -> return_order()",
        "resultado_real": f"Devuelto con éxito ({o.status.value})",
        "evento": str(ev),
        "estado_final": o.status.value,
        "explicacion": "Flujo válido de devolución: DRAFT -> CONFIRMED -> SHIPPED -> RETURNED. Genera OrderConfirmed, OrderShipped, OrderReturned."
    })

    # E15: O016 confirmar, enviar y entregar -> éxito
    orders = load_fixture()
    o = orders["O016"]
    o.confirm()
    o.ship("TRACK-GUIA-100")
    o.deliver()
    ev = [e.name for e in o.events]
    bitacora.append({
        "caso": "E15",
        "pedido": "O016",
        "estado_inicial": "DRAFT",
        "operacion": "confirm() -> ship() -> deliver()",
        "resultado_real": f"Entregado con éxito ({o.status.value})",
        "evento": str(ev),
        "estado_final": o.status.value,
        "explicacion": "Flujo estándar de entrega: DRAFT -> CONFIRMED -> SHIPPED -> DELIVERED. Genera OrderConfirmed, OrderShipped, OrderDelivered."
    })

    print("-" * 110)
    print(f"{'Caso':<6} | {'Inicial':<10} | {'Operación':<30} | {'Estado Final':<12} | {'Eventos':<35}")
    print("-" * 110)
    for b in bitacora:
        print(f"{b['caso']:<6} | {b['estado_inicial']:<10} | {b['operacion']:<30} | {b['estado_final']:<12} | {b['evento']:<35}")
    print("-" * 110)

    return bitacora


if __name__ == "__main__":
    run_scenarios()
