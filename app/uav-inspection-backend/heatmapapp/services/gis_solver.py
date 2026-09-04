import math
from typing import Dict, Tuple


def pixel_to_wgs84(
    bbox,
    telemetry: Dict[str, float],
    img_width: int = 1920,
    img_height: int = 1080,
    hfov_deg: float = 80.0
) -> Tuple[float, float]:
    """
    Convert a pixel bbox center to WGS84 lat/lon using a collinearity model.
    Camera frame: x right, y down, z forward. World frame: NED (north, east, down).
    """
    if not telemetry:
        return 0.0, 0.0

    lat = float(telemetry.get("latitude", 0.0))
    lon = float(telemetry.get("longitude", 0.0))
    alt = float(telemetry.get("altitude", 0.0))
    pitch_deg = float(telemetry.get("pitch", -90.0))
    yaw_deg = float(telemetry.get("yaw", 0.0))
    roll_deg = float(telemetry.get("roll", 0.0))

    if alt <= 0 or img_width <= 0 or img_height <= 0:
        return lat, lon

    x_center = (bbox[0] + bbox[2]) / 2.0
    y_center = (bbox[1] + bbox[3]) / 2.0

    hfov = math.radians(hfov_deg)
    vfov = 2.0 * math.atan(math.tan(hfov / 2.0) * (img_height / img_width))
    fx = (img_width / 2.0) / math.tan(hfov / 2.0)
    fy = (img_height / 2.0) / math.tan(vfov / 2.0)

    x_cam = (x_center - img_width / 2.0) / fx
    y_cam = (y_center - img_height / 2.0) / fy
    z_cam = 1.0

    # Camera -> body (forward, right, down)
    v_body = [z_cam, x_cam, y_cam]

    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    roll = math.radians(roll_deg)

    r_roll = [
        [1.0, 0.0, 0.0],
        [0.0, math.cos(roll), -math.sin(roll)],
        [0.0, math.sin(roll), math.cos(roll)]
    ]
    r_pitch = [
        [math.cos(pitch), 0.0, math.sin(pitch)],
        [0.0, 1.0, 0.0],
        [-math.sin(pitch), 0.0, math.cos(pitch)]
    ]
    r_yaw = [
        [math.cos(yaw), -math.sin(yaw), 0.0],
        [math.sin(yaw), math.cos(yaw), 0.0],
        [0.0, 0.0, 1.0]
    ]

    def mat_mul(a, b):
        return [
            [a[0][0] * b[0][0] + a[0][1] * b[1][0] + a[0][2] * b[2][0],
             a[0][0] * b[0][1] + a[0][1] * b[1][1] + a[0][2] * b[2][1],
             a[0][0] * b[0][2] + a[0][1] * b[1][2] + a[0][2] * b[2][2]],
            [a[1][0] * b[0][0] + a[1][1] * b[1][0] + a[1][2] * b[2][0],
             a[1][0] * b[0][1] + a[1][1] * b[1][1] + a[1][2] * b[2][1],
             a[1][0] * b[0][2] + a[1][1] * b[1][2] + a[1][2] * b[2][2]],
            [a[2][0] * b[0][0] + a[2][1] * b[1][0] + a[2][2] * b[2][0],
             a[2][0] * b[0][1] + a[2][1] * b[1][1] + a[2][2] * b[2][1],
             a[2][0] * b[0][2] + a[2][1] * b[1][2] + a[2][2] * b[2][2]]
        ]

    def mat_vec_mul(m, v):
        return [
            m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2]
        ]

    r_temp = mat_mul(r_yaw, mat_mul(r_pitch, r_roll))
    v_world = mat_vec_mul(r_temp, v_body)

    # v_world[2] is down (positive)
    if v_world[2] <= 0:
        return lat, lon

    scale = alt / v_world[2]
    north = v_world[0] * scale
    east = v_world[1] * scale

    meters_per_deg_lat = 111319.9
    meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(lat))
    if meters_per_deg_lon == 0:
        meters_per_deg_lon = 1.0

    geo_lat = lat + (north / meters_per_deg_lat)
    geo_lon = lon + (east / meters_per_deg_lon)
    return geo_lat, geo_lon