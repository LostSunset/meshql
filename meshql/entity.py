from enum import Enum
import cadquery as cq
from cadquery.cq import CQObject
from dataclasses import dataclass
from typing import Iterable, Literal, Optional, OrderedDict, Sequence, Union, cast
from meshql.utils.cq import CQLinq, CQType, CQ_TYPE_STR_MAPPING, CQType2D
from meshql.utils.types import OrderedSet


ENTITY_DIM_MAPPING: dict[CQType, int] = {
    "vertex": 0,
    "edge": 1,
    "face": 2,
    "solid": 3,
}


@dataclass
class Entity:
    type: CQType
    "dimension type of the entity."

    tag: int = -1
    "tag of the entity."

    name: Optional[str] = None
    "name of the entity."

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, Entity):
            return self.type == __value.type and self.tag == __value.tag
        return False

    @property
    def dim(self):
        if self.type not in ENTITY_DIM_MAPPING:
            raise ValueError(
                f"Entity type {self.type} not supported, only {ENTITY_DIM_MAPPING.keys()}"
            )

        return ENTITY_DIM_MAPPING[self.type]

    def __hash__(self) -> int:
        return hash((self.type, self.tag))


class CQEntityContext:
    "Maps OCC objects to gmsh entity tags"

    def __init__(self, workplane: cq.Workplane, level: Union[CQType, CQType2D] = "edge") -> None:
        self.dimension = 3 if len(workplane.solids().vals()) else 2

        self.entity_registries: dict[CQType, OrderedDict[CQObject, Entity]] = {
            "compound": OrderedDict[CQObject, Entity](),
            "solid": OrderedDict[CQObject, Entity](),
            "shell": OrderedDict[CQObject, Entity](),
            "face": OrderedDict[CQObject, Entity](),
            "wire": OrderedDict[CQObject, Entity](),
            "edge": OrderedDict[CQObject, Entity](),
            "vertex": OrderedDict[CQObject, Entity](),
        }

        if self.dimension == 3:
            self._init_3d_objs(workplane, level)
        else:
            self._init_2d_objs(workplane, cast(CQType2D, level))

    def add(self, obj: CQObject):
        entity_type = CQ_TYPE_STR_MAPPING[type(obj)]
        registry = self.entity_registries[entity_type]
        if obj not in registry:
            tag = len(registry) + 1
            registry[obj] = Entity(entity_type, tag)

    def select(self, obj: CQObject):
        entity_type = CQ_TYPE_STR_MAPPING[type(obj)]
        registry = self.entity_registries[entity_type]
        return registry[obj]

    def select_many(
        self,
        target: Union[cq.Workplane, Iterable[CQObject]],
        type: Optional[CQType] = None,
    ):
        entities = OrderedSet[Entity]()
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_objs = objs if type is None else CQLinq.select(objs, type)
        for obj in selected_objs:
            try:
                selected_entity = self.select(obj)
                entities.add(selected_entity)
            except:
                ...

        return entities

    def select_batch(
        self,
        target: Union[cq.Workplane, Iterable[CQObject]],
        parent_type: CQType,
        child_type: CQType,
    ):
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_batches = CQLinq.select_batch(objs, parent_type, child_type)
        for selected_batch in selected_batches:
            yield self.select_many(selected_batch)

    def _init_3d_objs(
        self, target: Union[cq.Workplane, Sequence[CQObject]], level: CQType
    ):
        objs = CQLinq.select(target, "solid")
        for compound in cast(Sequence[Union[cq.Solid, cq.Compound]], objs):
            if level != "compound":
                for solid in compound.Solids():
                    if level != "solid":
                        for shell in solid.Shells():
                            if level != "shell":
                                self._init_2d_objs(shell.Faces(), level)
                            self.add(shell)
                    self.add(solid)
            if isinstance(compound, cq.Compound):
                self.add(compound)

    def _init_2d_objs(
        self, target: Union[cq.Workplane, Sequence[CQObject]], level: CQType2D
    ):
        objs = CQLinq.select(target, "face")
        for face in cast(Sequence[cq.Face], objs):
            if level != "face":
                for wire in [face.outerWire(), *face.innerWires()]:
                    if level != "wire":
                        for edge in wire.Edges():
                            if level != "edge":
                                for vertex in edge.Vertices():
                                    self.add(vertex)
                            self.add(edge)
                    self.add(wire)
            self.add(face)
