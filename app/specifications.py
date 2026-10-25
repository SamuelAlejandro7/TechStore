from decimal import Decimal
from typing import Any
from app.domain import Order


class Specification:
    """Clase base para el patrón Specification."""

    def is_satisfied_by(self, candidate: Any) -> bool:
        raise NotImplementedError

    def __and__(self, other: "Specification") -> "AndSpec":
        return AndSpec(self, other)

    def __or__(self, other: "Specification") -> "OrSpec":
        return OrSpec(self, other)

    def __invert__(self) -> "NotSpec":
        return NotSpec(self)


class AndSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)


class OrSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)


class NotSpec(Specification):
    def __init__(self, spec: Specification):
        self.spec = spec

    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self.spec.is_satisfied_by(candidate)


class MinimumAmountSpec(Specification):
    """Verifica que el total del pedido sea estrictamente mayor al monto especificado."""

    def __init__(self, amount: Decimal):
        self.amount = amount

    def is_satisfied_by(self, order: Order) -> bool:
        return order.total.amount > self.amount


class VIPCustomerSpec(Specification):
    """Verifica que el cliente sea VIP."""

    def is_satisfied_by(self, order: Order) -> bool:
        return bool(order.customer.is_vip)


class MinimumUnitsSpec(Specification):
    """Verifica que el total de unidades del pedido sea mayor o igual al mínimo."""

    def __init__(self, min_units: int = 4):
        self.min_units = min_units

    def is_satisfied_by(self, order: Order) -> bool:
        return order.units >= self.min_units


class ActivePromotionSpec(Specification):
    """Verifica si el pedido ya tiene una promoción activa."""

    def is_satisfied_by(self, order: Order) -> bool:
        return bool(order.has_promotion)


# Reglas de negocio compuestas mediante operadores lógicos
# 10%: VIP, >500 MXN, >=4 unidades, sin promoción activa
ten_percent_rule = (
    MinimumAmountSpec(Decimal("500"))
    & VIPCustomerSpec()
    & MinimumUnitsSpec(4)
    & ~ActivePromotionSpec()
)

# 5%: >5000 MXN, sin promoción activa
five_percent_rule = (
    MinimumAmountSpec(Decimal("5000"))
    & ~ActivePromotionSpec()
)

# Regla combinada que determina si aplica algún descuento
any_discount_rule = ten_percent_rule | five_percent_rule


def evaluate_discount(order: Order) -> str:
    """Evalúa el porcentaje de descuento aplicable.
    
    Si ambas condiciones se cumplen, se da prioridad al 10%.
    Retorna "10%", "5%" o "0%".
    """
    if ten_percent_rule.is_satisfied_by(order):
        return "10%"
    if five_percent_rule.is_satisfied_by(order):
        return "5%"
    return "0%"


def calculate_discount_rate(order: Order) -> Decimal:
    """Retorna la tasa numérica de descuento (Decimal)."""
    rate_map = {
        "10%": Decimal("0.10"),
        "5%": Decimal("0.05"),
        "0%": Decimal("0.00"),
    }
    return rate_map[evaluate_discount(order)]
