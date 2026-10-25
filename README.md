# TechStore U4 - Núcleo de Lógica de Negocio y API REST

**Unidad 4: Componentes de Lógica de Negocio**  
**Facultad de Ingeniería Mecánica y Eléctrica (FIME) · UANL**

---

## 1. Descripción del Proyecto

TechStore U4 implementa el núcleo de lógica de negocio (Domain-Driven Design - DDD) para la gestión del ciclo de vida de pedidos de una tienda de tecnología. El sistema opera completamente con objetos en memoria cargados a partir de archivos CSV, modelando entidades ricas, objetos de valor (Value Objects), un Aggregate Root (`Order`), el patrón **Specification** para reglas de descuento compuestas, una máquina de estados con **Domain Events** y una API REST desacoplada construida con **FastAPI**.

---

## 2. Estructura del Proyecto

```text
techstore-u4/
│
├── datos/                      # Archivos de datos del paquete alumno
│   ├── clientes.csv            # 12 clientes (es_vip, activo)
│   ├── productos.csv           # 12 productos con precios en MXN
│   ├── pedidos.csv             # 16 pedidos iniciales (todos en DRAFT)
│   ├── detalle_pedidos.csv     # 21 líneas de artículos por pedido
│   └── escenarios.csv          # 15 escenarios de evaluación (E01–E15)
│
├── app/                        # Capa de dominio y exposición REST
│   ├── __init__.py
│   ├── domain.py               # Value Objects, Entidades, Aggregate Root y Eventos
│   ├── specifications.py       # Patrón Specification (&, |, ~) y reglas de descuento
│   └── api.py                  # Endpoints FastAPI y mapeo de excepciones de dominio
│
├── tests/                      # Suite de pruebas automatizadas
│   ├── __init__.py
│   ├── test_domain.py          # Pruebas unitarias de dominio y specifications
│   └── test_api.py             # Pruebas de integración de la API REST
│
├── cargar_csv.py               # Cargador de fixtures a objetos del dominio
├── ejecutar_escenarios.py      # Script de ejecución y bitácora de escenarios E01–E15
├── .gitignore                  # Exclusión de .venv, __pycache__ y temporales
└── README.md                   # Documentación técnica completa
```

---

## 3. Requisitos y Preparación del Entorno

### Requisitos
- Python 3.11 o superior (compatible con Python 3.12 y 3.15).

### Pasos de Instalación

1. **Crear y activar el entorno virtual:**
   ```powershell
   # En Windows PowerShell:
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
   *(Si usas uv: `uv venv .venv` y `.venv\Scripts\activate`)*

2. **Instalar dependencias necesarias:**
   ```powershell
   pip install fastapi uvicorn pytest httpx
   ```

---

## 4. Ejecución del Proyecto

### Carga de datos de prueba
Verifica que los 16 pedidos se importan correctamente en memoria:
```powershell
python cargar_csv.py
```

### Ejecutar la suite de pruebas automatizadas (41 pruebas)
```powershell
pytest -v
```

### Ejecutar la bitácora de los 15 escenarios (E01 a E15)
```powershell
python ejecutar_escenarios.py
```

### Iniciar el servidor API REST con recarga automática
```powershell
uvicorn app.api:app --reload
```
Una vez levantado:
- **Documentación Swagger interactiva:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Documentación ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Especificación OpenAPI (JSON):** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## 5. Reglas de Negocio Implementadas

### 5.1 Value Objects
- **`Money`**: Inmutable (`frozen=True`). Almacena `amount` como `Decimal` y `currency` como `"MXN"`. Rechaza cantidades negativas o valores no finitos (`NaN`, `Infinity`). El método `add()` valida coincidencia de divisas y retorna una nueva instancia.
- **`OrderItem`**: Inmutable. Representa una línea de producto con su SKU, cantidad positiva mayor a cero y precio unitario (`Money`). Calcula su `subtotal` como propiedad derivada (`unit_price * quantity`).

### 5.2 Aggregate Root (`Order`)
- **Control de capacidad:** Máximo 20 unidades en total por pedido (suma de `quantity` de cada ítem, no conteo de filas). Se valida preventivamente antes de incorporar el artículo.
- **Inmutabilidad en modificaciones:** Solo se permite añadir artículos si el pedido está en estado `DRAFT`.
- **Validación de moneda:** Solo se aceptan artículos cotizados en `MXN`.

### 5.3 Reglas de Descuento (Patrón Specification)
Se implementaron las especificaciones base con sobrecarga de operadores bitwise:
- `&` para conjunción (`AndSpec`)
- `|` para disyunción (`OrSpec`)
- `~` para negación (`NotSpec`)

Reglas de negocio:
1. **Regla de 10%:**
   - Cliente VIP (`VIPCustomerSpec`)
   - Total mayor estricto a 500 MXN (`MinimumAmountSpec(500)`)
   - Al menos 4 unidades (`MinimumUnitsSpec(4)`)
   - Sin promoción activa (`~ActivePromotionSpec`)
2. **Regla de 5%:**
   - Total mayor estricto a 5000 MXN (`MinimumAmountSpec(5000)`)
   - Sin promoción activa (`~ActivePromotionSpec`)
3. **Prioridad:** Si un pedido cumple ambas condiciones, se aplica prioritariamente el 10%.

### 5.4 Máquina de Estados y Domain Events
Transiciones válidas:
```text
DRAFT --confirm--> CONFIRMED --ship--> SHIPPED --deliver--> DELIVERED
                         |                    |
                       cancel               return
                         |                    |
                     CANCELLED             RETURNED
```

- `confirm()`: Requiere estado `DRAFT`, que el pedido contenga al menos un artículo y que el cliente esté activo (`customer.active == True`). Emite `OrderConfirmed`.
- `ship(tracking_number)`: Requiere estado `CONFIRMED` y número de guía no vacío. Emite `OrderShipped`.
- `cancel(reason)`: Solo es válido desde estado `CONFIRMED` y exige un motivo no vacío. Emite `OrderCancelled`.
- `deliver()`: Solo es válido desde estado `SHIPPED`. Emite `OrderDelivered`.
- `return_order()`: Solo es válido desde estado `SHIPPED`. Emite `OrderReturned`.

*Principio de integridad de eventos:* Los eventos de dominio solo se instancian y encolan tras completarse una transición válida. En caso de excepción, el estado no muta y ningún evento es registrado.

---

## 6. Catálogo de Endpoints REST

| Método | Endpoint | Descripción | Códigos HTTP |
| :--- | :--- | :--- | :--- |
| `GET` | `/orders` | Lista todos los pedidos en memoria con totales y estado | `200 OK` |
| `GET` | `/orders/{id}` | Consulta el detalle completo de un pedido, ítems, descuento y eventos | `200 OK`, `404 Not Found` |
| `POST` | `/orders/{id}/confirm` | Confirma un pedido en `DRAFT` | `200 OK`, `404`, `409 Conflict`, `422 Unprocessable` |
| `POST` | `/orders/{id}/ship` | Registra el envío con guía `{ "tracking_number": "..." }` | `200 OK`, `404`, `409 Conflict`, `422 Unprocessable` |
| `POST` | `/orders/{id}/cancel` | Cancela pedido confirmado `{ "reason": "..." }` | `200 OK`, `404`, `409 Conflict`, `422 Unprocessable` |
| `POST` | `/orders/{id}/deliver` | Registra entrega de un pedido enviado | `200 OK`, `404`, `409 Conflict` |
| `POST` | `/orders/{id}/return` | Registra devolución de un pedido enviado | `200 OK`, `404`, `409 Conflict` |
| `POST` | `/orders/{id}/items` | Agrega un producto a un pedido en `DRAFT` | `200 OK`, `404`, `409 Conflict`, `422 Unprocessable` |
| `POST` | `/reset` | Restaura los datos en memoria al estado inicial de los CSV | `200 OK` |
