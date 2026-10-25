import pytest
from decimal import Decimal
from cargar_csv import load_fixture
from app.domain import (
    Money,
    Customer,
    OrderItem,
    Order,
    OrderStatus,
    DomainEvent,
    InvalidOrderData,
    InvalidOrderTransition,
    OrderItemLimitExceeded,
)
from app.specifications import (
    MinimumAmountSpec,
    VIPCustomerSpec,
    MinimumUnitsSpec,
    ActivePromotionSpec,
    ten_percent_rule,
    five_percent_rule,
    evaluate_discount,
)


# ==========================================
# Pruebas de Value Objects: Money y OrderItem
# ==========================================

def test_money_valido():
    m = Money(Decimal("100.50"), "MXN")
    assert m.amount == Decimal("100.50")
    assert m.currency == "MXN"


def test_money_negativo():
    with pytest.raises(InvalidOrderData, match="Monto inválido"):
        Money(Decimal("-1.00"))


def test_money_no_finito():
    with pytest.raises(InvalidOrderData, match="Monto inválido"):
        Money(Decimal("NaN"))


def test_money_add_misma_moneda():
    m1 = Money(Decimal("150.00"), "MXN")
    m2 = Money(Decimal("50.50"), "MXN")
    res = m1.add(m2)
    assert res.amount == Decimal("200.50")
    assert res.currency == "MXN"


def test_money_add_distinta_moneda():
    m1 = Money(Decimal("100.00"), "MXN")
    m2 = Money(Decimal("100.00"), "USD")
    with pytest.raises(InvalidOrderData, match="Monedas distintas"):
        m1.add(m2)


def test_order_item_valido():
    price = Money(Decimal("250.00"))
    item = OrderItem("SKU123", 3, price)
    assert item.sku == "SKU123"
    assert item.quantity == 3
    assert item.subtotal.amount == Decimal("750.00")


def test_order_item_sku_vacio():
    with pytest.raises(InvalidOrderData, match="Artículo inválido"):
        OrderItem("   ", 2, Money(Decimal("100.00")))


def test_order_item_cantidad_cero_o_negativa():
    with pytest.raises(InvalidOrderData, match="Artículo inválido"):
        OrderItem("SKU1", 0, Money(Decimal("100.00")))
    with pytest.raises(InvalidOrderData, match="Artículo inválido"):
        OrderItem("SKU1", -5, Money(Decimal("100.00")))


# ==========================================
# Pruebas de Entity / Aggregate Root: Order
# ==========================================

def test_pedido_o001_inicia_draft():
    orders = load_fixture()
    o = orders["O001"]
    assert o.status == OrderStatus.DRAFT
    assert o.units == 4
    assert o.total.amount == Decimal("2100.00")


def test_limite_maximo_20_unidades():
    orders = load_fixture()
    o = orders["O008"]
    assert o.units == 20
    # No permite agregar ni una sola unidad más
    with pytest.raises(OrderItemLimitExceeded, match="Máximo 20 unidades"):
        o.add_item(OrderItem("SKU001", 1, Money(Decimal("600.00"))))


def test_superar_limite_21_unidades():
    orders = load_fixture()
    o = orders["O009"]
    assert o.units == 19
    # Agregar 2 llevaría a 21 unidades
    with pytest.raises(OrderItemLimitExceeded, match="Máximo 20 unidades"):
        o.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00"))))
    # Las unidades no se alteraron
    assert o.units == 19


def test_agregar_item_solo_en_draft():
    orders = load_fixture()
    o = orders["O001"]
    o.confirm()
    with pytest.raises(InvalidOrderTransition, match="Solo DRAFT admite artículos"):
        o.add_item(OrderItem("SKU001", 1, Money(Decimal("600.00"))))


def test_confirmar_cliente_inactivo_falla():
    orders = load_fixture()
    o = orders["O003"]
    assert not o.customer.active
    with pytest.raises(InvalidOrderData, match="Requiere artículos y cliente activo"):
        o.confirm()
    assert o.status == OrderStatus.DRAFT
    assert len(o.events) == 0


def test_confirmar_pedido_vacio_falla():
    orders = load_fixture()
    o = orders["O007"]
    assert len(o.items) == 0
    with pytest.raises(InvalidOrderData, match="Requiere artículos y cliente activo"):
        o.confirm()
    assert o.status == OrderStatus.DRAFT
    assert len(o.events) == 0


def test_confirmacion_exitosa_y_doble_confirmacion():
    orders = load_fixture()
    o = orders["O013"]
    assert o.status == OrderStatus.DRAFT
    o.confirm()
    assert o.status == OrderStatus.CONFIRMED
    assert len(o.events) == 1
    assert o.events[0].name == "OrderConfirmed"
    assert o.events[0].order_id == "O013"

    # Segunda confirmación prohibida
    with pytest.raises(InvalidOrderTransition, match="Solo DRAFT"):
        o.confirm()
    # No se agrega un segundo evento y el estado permanece en CONFIRMED
    assert o.status == OrderStatus.CONFIRMED
    assert len(o.events) == 1


def test_envio_sin_guia_falla():
    orders = load_fixture()
    o = orders["O012"]
    o.confirm()
    with pytest.raises(InvalidOrderData, match="Guía obligatoria"):
        o.ship("")
    assert o.status == OrderStatus.CONFIRMED
    assert len(o.events) == 1  # Solo el de confirmación


def test_cancelacion_desde_shipped_falla():
    orders = load_fixture()
    o = orders["O014"]
    o.confirm()
    o.ship("GUIA-123")
    assert o.status == OrderStatus.SHIPPED
    with pytest.raises(InvalidOrderTransition, match="Solo CONFIRMED puede cancelarse"):
        o.cancel("Motivo cualquiera")
    assert o.status == OrderStatus.SHIPPED
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped"]


def test_cancelacion_valida_desde_confirmed():
    orders = load_fixture()
    o = orders["O002"]
    o.confirm()
    o.cancel("Cliente solicitó cancelación antes del envío")
    assert o.status == OrderStatus.CANCELLED
    assert o.cancellation_reason == "Cliente solicitó cancelación antes del envío"
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderCancelled"]


def test_flujo_completo_entrega():
    orders = load_fixture()
    o = orders["O016"]
    o.confirm()
    o.ship("TRACK-GUIA-100")
    o.deliver()
    assert o.status == OrderStatus.DELIVERED
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped", "OrderDelivered"]


def test_flujo_completo_devolucion():
    orders = load_fixture()
    o = orders["O015"]
    o.confirm()
    o.ship("TRACK-GUIA-99")
    o.return_order()
    assert o.status == OrderStatus.RETURNED
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped", "OrderReturned"]


# ==========================================
# Pruebas de Specifications
# ==========================================

def test_descuento_vip_10_porciento():
    orders = load_fixture()
    assert evaluate_discount(orders["O001"]) == "10%"


def test_no_vip_total_menor_5000_cero_descuento():
    orders = load_fixture()
    assert evaluate_discount(orders["O002"]) == "0%"


def test_promocion_activa_bloquea_descuento():
    orders = load_fixture()
    assert evaluate_discount(orders["O005"]) == "0%"


def test_descuento_5_porciento_monto_mayor_5000():
    orders = load_fixture()
    assert evaluate_discount(orders["O006"]) == "5%"


def test_umbral_estricto_500_cero_descuento():
    orders = load_fixture()
    assert evaluate_discount(orders["O010"]) == "0%"


def test_unidades_insuficientes_cero_descuento():
    orders = load_fixture()
    assert evaluate_discount(orders["O011"]) == "0%"


def test_composicion_operadores_specification():
    spec1 = MinimumAmountSpec(Decimal("500"))
    spec2 = VIPCustomerSpec()
    and_spec = spec1 & spec2
    or_spec = spec1 | spec2
    not_spec = ~spec1

    orders = load_fixture()
    o001 = orders["O001"]  # VIP, total 2100 > 500
    assert and_spec.is_satisfied_by(o001) is True
    assert or_spec.is_satisfied_by(o001) is True
    assert not_spec.is_satisfied_by(o001) is False
