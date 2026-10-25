from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from datetime import datetime, timezone
from typing import Optional


class DomainException(Exception):
    """Excepción base del dominio."""
    pass


class InvalidOrderData(DomainException):
    """Lanzada cuando los datos de una orden o artículo no son válidos."""
    pass


class InvalidOrderTransition(DomainException):
    """Lanzada cuando se intenta una transición de estado inválida."""
    pass


class OrderItemLimitExceeded(DomainException):
    """Lanzada cuando el total de unidades excede el límite permitido (20)."""
    pass


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "MXN"

    def __post_init__(self):
        if not self.amount.is_finite() or self.amount < 0:
            raise InvalidOrderData("Monto inválido")

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvalidOrderData("Monedas distintas")
        return Money(self.amount + other.amount, self.currency)


@dataclass(frozen=True)
class Customer:
    id: str
    is_vip: bool = False
    active: bool = True


@dataclass(frozen=True)
class OrderItem:
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self):
        if not self.sku.strip() or self.quantity <= 0:
            raise InvalidOrderData("Artículo inválido")

    @property
    def subtotal(self) -> Money:
        return Money(self.unit_price.amount * self.quantity, self.unit_price.currency)


class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


@dataclass(frozen=True)
class DomainEvent:
    name: str
    order_id: str
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Order:
    customer: Customer
    id: str
    has_promotion: bool = False
    status: OrderStatus = OrderStatus.DRAFT
    items: list[OrderItem] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    tracking_number: Optional[str] = None
    cancellation_reason: Optional[str] = None

    @property
    def units(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def total(self) -> Money:
        amount = sum((x.subtotal.amount for x in self.items), Decimal("0"))
        return Money(amount)

    def add_item(self, item: OrderItem) -> None:
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo DRAFT admite artículos")
        if self.units + item.quantity > 20:
            raise OrderItemLimitExceeded("Máximo 20 unidades")
        if item.unit_price.currency != "MXN":
            raise InvalidOrderData("Solo MXN")
        self.items.append(item)

    def confirm(self) -> None:
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo DRAFT")
        if not self.items or not self.customer.active:
            raise InvalidOrderData("Requiere artículos y cliente activo")
        self.status = OrderStatus.CONFIRMED
        self.events.append(DomainEvent("OrderConfirmed", self.id))

    def ship(self, tracking_number: str) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition("Solo CONFIRMED puede enviarse")
        if not tracking_number or not tracking_number.strip():
            raise InvalidOrderData("Guía obligatoria")
        self.tracking_number = tracking_number.strip()
        self.status = OrderStatus.SHIPPED
        self.events.append(DomainEvent("OrderShipped", self.id))

    def cancel(self, reason: str) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition("Solo CONFIRMED puede cancelarse")
        if not reason or not reason.strip():
            raise InvalidOrderData("Motivo obligatorio")
        self.cancellation_reason = reason.strip()
        self.status = OrderStatus.CANCELLED
        self.events.append(DomainEvent("OrderCancelled", self.id))

    def deliver(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition("Solo SHIPPED puede entregarse")
        self.status = OrderStatus.DELIVERED
        self.events.append(DomainEvent("OrderDelivered", self.id))

    def return_order(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition("Solo SHIPPED puede devolverse")
        self.status = OrderStatus.RETURNED
        self.events.append(DomainEvent("OrderReturned", self.id))
