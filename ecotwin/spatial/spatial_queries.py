from sqlalchemy import select
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from ecotwin.db.models import City,CitySnapshot,DatasetRevision,LandcoverCell,GeoFeature
from ecotwin.models.landcover import CoverPiece
from ecotwin.spatial.geometry import project
from ecotwin.errors import TwinError

def city_by_slug(session,slug):
    row=session.scalar(select(City).where(City.slug==slug))
    if not row:
        raise TwinError('CITY_NOT_FOUND','Register the city with ecotwin city create',404)
    return row

def snapshot_inputs(session,snapshot):
    revisions=list(session.scalars(select(DatasetRevision).where(DatasetRevision.id.in_(snapshot.dataset_revision_ids))))
    if len(revisions)!=len(snapshot.dataset_revision_ids) or any(r.status!='READY' for r in revisions):
        raise TwinError('DATASET_NOT_READY','Snapshot contains missing or incomplete revisions')
    return sorted(revisions,key=lambda r:r.kind)

def load_cover(session,snapshot,city):
    revisions=snapshot_inputs(session,snapshot)
    cover=next((r for r in revisions if r.kind=='worldcover'),None)
    if not cover:
        raise TwinError('INSUFFICIENT_INPUT_DATA','WorldCover revision required')
    rows=session.scalars(select(LandcoverCell).where(LandcoverCell.revision_id==cover.id).order_by(LandcoverCell.cell_y,LandcoverCell.cell_x))
    pieces=[CoverPiece(project(to_shape(row.geom),city.analysis_srid),row.class_code) for row in rows]
    if not pieces:
        raise TwinError('INSUFFICIENT_INPUT_DATA','No classified land-cover cells')
    return pieces

def snapshot_buildings(session,snapshot):
    return [to_shape(row.geom) for row in session.scalars(select(GeoFeature).where(GeoFeature.revision_id.in_(snapshot.dataset_revision_ids),GeoFeature.category=='building'))]
