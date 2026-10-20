"""Server-owned geospatial policy; no client can supply trust or a township claim."""

from math import asin, cos, radians, sin, sqrt


def distance_meters(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(lambda value: radians(float(value)), (lat1, lon1, lat2, lon2))
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    haversine = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 6371008.8 * 2 * asin(sqrt(min(1, max(0, haversine))))


class TownshipBoundaryResolver:
    """Override only with reviewed server-side boundary data; ambiguous matches return None."""

    def township_at(self, latitude, longitude) -> str | None:
        return None
