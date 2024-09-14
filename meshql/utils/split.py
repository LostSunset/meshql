from typing import Sequence
import cadquery as cq
import numpy as np
import cadquery as cq
from typing import Literal, Sequence, Union, cast
from meshql.utils.cq import CQUtils
from meshql.utils.cq_cache import CQCache
from meshql.utils.cq_linq import CQLinq
from meshql.utils.types import (
    Axis,
    OrderedSet,
    VectorSequence,
    to_vec,
)

SplitAt = Literal["end", "per"]
SnapType = Union[bool, Literal["closest"], float]
MultiFaceAxis = Union[Axis, Literal["avg", "face1", "face2"]]

class SplitUtils:
    @staticmethod
    def split_workplane(workplane: cq.Workplane, splits: Sequence[cq.Face]):
        # shape_combo = [*workplane.vals(), *splits]
        # cache_exists = CQCache.get_cache_exists(shape_combo)
        # cache_file_name = CQCache.get_file_name(shape_combo)
        # if cache_exists:
        #     print("Split cache exists, loading ...")
        #     shape = CQCache.import_brep(cache_file_name)
        # else:
        #     for split in splits:      
        #         workplane = workplane.split(split)
        #     shape = CQUtils.fuse_shapes(workplane.vals())
        #     CQCache.export_brep(shape, cache_file_name)
        for split in splits:      
            workplane = workplane.split(split)
        shape = CQUtils.fuse_shapes(workplane.vals())


        return cq.Workplane(shape)

    @staticmethod
    def make_split_face_from_edges(edge1: cq.Edge, edge2: cq.Edge, is_line_end: bool = True):
        if (edge2.endPoint().Center() - edge1.endPoint().Center()).Length < (
            edge2.startPoint().Center() - edge1.endPoint().Center()
        ).Length:
            near_pnt1, near_pnt2 = edge2.endPoint(), edge2.startPoint()
        else:
            near_pnt1, near_pnt2 = edge2.startPoint(), edge2.endPoint()

        split_edges = [
            edge1,
            cq.Edge.makeLine(edge1.endPoint(), near_pnt1),
            cq.Edge.makeLine(near_pnt1, near_pnt2) if is_line_end else edge2,
            cq.Edge.makeLine(near_pnt2, edge1.startPoint()),
        ]
        try:
            return cq.Face.makeFromWires(cq.Wire.assembleEdges(split_edges))
        except:
            return cq.Face.makeNSidedSurface(split_edges, [])

    @staticmethod
    def make_plane_split_face(
        workplane: cq.Workplane,
        base_pnt: VectorSequence = (0, 0, 0),
        angle: VectorSequence = (0, 0, 1),
        sizing: Literal["maxDim", "infinite"] = "maxDim",
    ):
        maxDim = workplane.findSolid().BoundingBox().DiagonalLength * CQUtils.max_dim_multiplier
        base_pnt_vec = to_vec(base_pnt)
        angle_vec = to_vec(np.radians(list(angle)))
        if sizing == "maxDim":
            return cq.Face.makePlane(maxDim, maxDim, base_pnt_vec, angle_vec)
        else:
            return cq.Face.makePlane(None, None, base_pnt_vec, angle_vec)

    @staticmethod
    def make_edge_split_face(
        workplane: cq.Workplane,
        edge: cq.Edge,
        axis: Axis = "Z",
        dir: Literal["away", "towards", "both"] = "both",
        snap: SnapType = False,
        snap_edges=OrderedSet[cq.Edge](),
    ):
        maxDim = workplane.findSolid().BoundingBox().DiagonalLength * CQUtils.max_dim_multiplier
        normal_vector = CQUtils.normalize(to_vec(axis))
        towards_edge = edge.translate(normal_vector * maxDim)
        away_edge = edge.translate(-normal_vector * maxDim)
        if dir == "both":
            towards_split_face = SplitUtils.make_split_face_from_edges(edge, towards_edge)
            away_split_face = SplitUtils.make_split_face_from_edges(edge, away_edge)
            split_face = towards_split_face.fuse(away_split_face)
        elif dir in ("towards", "away"):
            split_face = SplitUtils.make_split_face_from_edges(
                edge, towards_edge if dir == "towards" else away_edge
            )

        if snap != False:
            snap_tolerance = snap if isinstance(snap, float) else None
            intersected_edges = workplane.intersect(cq.Workplane(split_face)).edges().vals()
            if len(intersected_edges) > 0:
                closest_intersection_edge = CQLinq.find_nearest(intersected_edges, edge)
                assert closest_intersection_edge, "No close intersecting edge found"
                snap_edge = cast(
                    cq.Edge,
                    CQLinq.find_nearest(
                        workplane,
                        closest_intersection_edge,
                        snap_tolerance,
                        excluded=[edge],
                    ),
                )
                if snap_edge and snap_edge not in snap_edges:
                    snap_edges.add(snap_edge)
                    split_face = SplitUtils.make_split_face_from_edges(
                        edge, snap_edge, is_line_end=False
                    )
                    return split_face

        return split_face
