"""Exact geometry partitions retain edit locality through sequential changes."""
from dataclasses import dataclass
from collections import defaultdict
import math
from shapely.geometry.base import BaseGeometry
from shapely.geometry import mapping
from shapely.ops import unary_union
from ecotwin.errors import TwinError
from ecotwin.spatial.geometry import geometry, project

CLASS_CODES={10,20,30,40,50,60,70,80,90,95,100}

@dataclass(frozen=True)
class CoverPiece:
    geom: BaseGeometry
    class_code: int
    fraction: float = 1.0

def class_areas(pieces: list[CoverPiece]) -> dict[int,float]:
    values: dict[int,list[float]]=defaultdict(list)
    for piece in pieces:
        values[piece.class_code].append(piece.geom.area*piece.fraction)
    return {key:math.fsum(values[key]) for key in sorted(values)}

def reclassify(pieces: list[CoverPiece],edit: dict,srid: int) -> tuple[list[CoverPiece],float]:
    target=project(geometry(edit['polygon_geojson']),srid)
    source,destination=edit['from_class_code'],edit['to_class_code']
    fraction=edit['fraction']
    if source not in CLASS_CODES or destination not in CLASS_CODES or source==destination or not 0<fraction<=1:
        raise TwinError('MODEL_INPUT_UNSUPPORTED','Invalid reclassification')
    intersects=[p for p in pieces if p.geom.intersection(target).area>1e-8]
    if not intersects or any(p.class_code!=source for p in intersects):
        raise TwinError('MODEL_INPUT_UNSUPPORTED','Target must intersect classified coverage exclusively in its current source class')
    # Fractional sub-cell accounting preserves location and never rounds to whole pixels.
    output=[]
    realized=0.0
    for piece in pieces:
        inside=piece.geom.intersection(target)
        outside=piece.geom.difference(target)
        if not outside.is_empty:
            output.append(CoverPiece(outside,piece.class_code,piece.fraction))
        if inside.area > 0:
            amount=piece.fraction*fraction
            realized+=inside.area*amount
            if fraction<1:
                output.append(CoverPiece(inside,source,piece.fraction-amount))
            output.append(CoverPiece(inside,destination,amount))
    if not math.isclose(sum(class_areas(pieces).values()),sum(class_areas(output).values()),rel_tol=1e-9,abs_tol=1e-5):
        raise TwinError('SIMULATION_FAILED','Area conservation violated')
    return output,realized

def apply_edits(pieces: list[CoverPiece],edits: list[dict],srid: int):
    result=list(pieces)
    realized=[]
    for edit in edits:
        if edit['edit_type']=='LAND_COVER_RECLASSIFY':
            result,area=reclassify(result,edit,srid)
            realized.append({'edit_type':edit['edit_type'],'realized_area_m2':area})
    return result,realized
