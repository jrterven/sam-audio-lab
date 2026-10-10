import math
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Region(BaseModel):
    sign: Literal['+', '-']
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def valid(self):
        if self.end <= self.start:
            raise ValueError('La región debe tener duración positiva.')
        return self


class Recipe(BaseModel):
    media_id: str
    start: float = Field(default=0, ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    model: Literal['small', 'base', 'large'] = 'small'
    prompt: str = Field(default='', max_length=2000)
    regions: list[Region] = Field(default_factory=list, max_length=100)
    tracking_id: str | None = None
    seed: int = Field(default=42, ge=0, le=2147483647)

    @model_validator(mode='after')
    def valid(self):
        duration = self.end - self.start
        if not 0 < duration <= 30.001:
            raise ValueError('Selecciona un fragmento de hasta 30 segundos.')
        for i, r in enumerate(self.regions):
            if r.start < self.start or r.end > self.end + 1e-6:
                raise ValueError('Las regiones deben estar dentro del fragmento.')
            for q in self.regions[:i]:
                if r.sign != q.sign and max(r.start, q.start) < min(r.end, q.end):
                    raise ValueError('Las regiones positivas y negativas no pueden superponerse.')
        return self


class Point(BaseModel):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
    label: Literal[0, 1] = 1


class Annotation(BaseModel):
    frame: int = Field(ge=0)
    points: list[Point] = Field(default_factory=list)
    tracking_id: str | None = None
    detection_id: str | None = None
    candidate: int = Field(default=0, ge=0)


class VisionRequest(BaseModel):
    media_id: str
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    frame: int = Field(default=0, ge=0)
    text: str = Field(default='', max_length=500)
    annotations: list[Annotation] = Field(default_factory=list)

    @model_validator(mode='after')
    def valid(self):
        if not 0 < self.end - self.start <= 30.001:
            raise ValueError('Selecciona un fragmento de hasta 30 segundos.')
        max_frame = math.ceil((self.end-self.start)*25)
        if self.frame >= max_frame or any(a.frame >= max_frame for a in self.annotations):
            raise ValueError('Fotograma fuera del fragmento.')
        return self


class ExportRequest(BaseModel):
    run_id: str
    track: Literal['target', 'residual'] = 'target'
