"""Modelos Pydantic: lo que entra por el POST y lo que devolvemos.

Pydantic valida solo: si el cuerpo no cumple, FastAPI responde 422 antes de
que corra nuestro código. Por eso las reglas viven acá y no en los endpoints.
"""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Estado = Literal["pendiente", "ejecutando", "completada", "fallida", "cancelada"]
ESTADOS: tuple[str, ...] = ("pendiente", "ejecutando", "completada", "fallida", "cancelada")


class TareaNueva(BaseModel):
    """Cuerpo del POST. Los campos dependen del `tipo` (ver el validador)."""
    tipo: Literal["descargar", "hashear", "esperar"]
    timeout: float | None = Field(default=None, gt=0, description="segundos; None = el default")
    # esperar
    segundos: float | None = Field(default=None, ge=0)
    # hashear
    texto: str | None = None
    iteraciones: int | None = Field(default=None, ge=1)
    # descargar
    urls: list[str] | None = None

    @model_validator(mode="after")
    def _exigir_campos_del_tipo(self):
        requeridos = {
            "esperar": {"segundos": self.segundos},
            "hashear": {"texto": self.texto, "iteraciones": self.iteraciones},
            "descargar": {"urls": self.urls},
        }[self.tipo]
        faltan = [k for k, v in requeridos.items() if v is None]
        if faltan:
            raise ValueError(f"la tarea '{self.tipo}' exige: {', '.join(faltan)}")
        if self.tipo == "descargar" and not self.urls:
            raise ValueError("urls no puede estar vacía")
        return self


class Tarea(TareaNueva):
    """Lo que devolvemos: lo pedido más lo que agrega el servidor."""
    id: int
    estado: Estado = "pendiente"
    resultado: object | None = None
    error: str | None = None
