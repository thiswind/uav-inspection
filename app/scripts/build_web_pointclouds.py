from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / 'webodm_downloads' / 'test_20260715'
OUTPUT_ROOT = PROJECT_ROOT / 'measurement_data' / 'pointcloud_web'
DOCKER_IMAGE = 'opendronemap/nodeodm:stable'
TASK_KEYS = [
    'task_01_xinxixueyuan_1',
    'task_02_xinxixueyuan_2',
    'task_03_meiguiyuan_2',
    'task_04_meiguiyuan_1',
    'task_05_meiguiyuan_3',
]


def docker_pdal(*args: str, capture: bool = False) -> str:
    command = [
        'docker', 'run', '--rm',
        '-v', f'{PROJECT_ROOT}:/workspace',
        '--entrypoint', 'pdal', DOCKER_IMAGE,
        *args,
    ]
    result = subprocess.run(command, check=True, text=True, capture_output=capture)
    return result.stdout if capture else ''


def docker_path(path: Path) -> str:
    return f"/workspace/{path.relative_to(PROJECT_ROOT).as_posix()}"


def ply_vertex_count(path: Path) -> int:
    with path.open('rb') as stream:
        while True:
            line = stream.readline().decode('ascii').strip()
            if line.startswith('element vertex '):
                return int(line.rsplit(' ', 1)[-1])
            if line == 'end_header' or not line:
                break
    raise RuntimeError(f'PLY header does not contain a vertex count: {path}')


def build_task(task_key: str, target_points: int, force: bool) -> None:
    source = SOURCE_ROOT / task_key / 'pointcloud.laz'
    output_dir = OUTPUT_ROOT / task_key
    output = output_dir / 'scene.ply'
    metadata_path = output_dir / 'scene.json'
    pipeline_path = output_dir / 'pipeline.json'
    if output.exists() and metadata_path.exists() and not force:
        print(f'{task_key}: already generated')
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    info = json.loads(docker_pdal('info', docker_path(source), '--summary', capture=True))['summary']
    bounds = info['bounds']
    source_points = int(info['num_points'])
    step = max(1, math.ceil(source_points / target_points))
    origin = {
        'x': (float(bounds['minx']) + float(bounds['maxx'])) / 2,
        'y': (float(bounds['miny']) + float(bounds['maxy'])) / 2,
        'z': (float(bounds['minz']) + float(bounds['maxz'])) / 2,
    }
    matrix = (
        f"1 0 0 {-origin['x']:.9f} "
        f"0 1 0 {-origin['y']:.9f} "
        f"0 0 1 {-origin['z']:.9f} 0 0 0 1"
    )
    pipeline = [
        {'type': 'readers.las', 'filename': docker_path(source)},
        {'type': 'filters.decimation', 'step': step},
        {'type': 'filters.transformation', 'matrix': matrix},
        {
            'type': 'filters.assign',
            'value': ['Red = Red * 257', 'Green = Green * 257', 'Blue = Blue * 257'],
        },
        {
            'type': 'writers.ply',
            'filename': docker_path(output),
            'storage_mode': 'little endian',
            'dims': 'X,Y,Z,Red,Green,Blue',
        },
    ]
    pipeline_path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{task_key}: {source_points:,} source points, decimation step {step}')
    docker_pdal('pipeline', docker_path(pipeline_path))

    display_points = ply_vertex_count(output)
    local_bounds = {
        'minx': float(bounds['minx']) - origin['x'],
        'maxx': float(bounds['maxx']) - origin['x'],
        'miny': float(bounds['miny']) - origin['y'],
        'maxy': float(bounds['maxy']) - origin['y'],
        'minz': float(bounds['minz']) - origin['z'],
        'maxz': float(bounds['maxz']) - origin['z'],
    }
    metadata = {
        'task_key': task_key,
        'source_file': source.relative_to(PROJECT_ROOT).as_posix(),
        'source_points': source_points,
        'display_points': display_points,
        'decimation_step': step,
        'epsg': 32648,
        'origin': origin,
        'source_bounds': bounds,
        'local_bounds': local_bounds,
        'dimensions': ['X', 'Y', 'Z', 'Red', 'Green', 'Blue'],
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{task_key}: wrote {display_points:,} display points to {output}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Build browser-ready point clouds without changing WebODM task data.')
    parser.add_argument('--target-points', type=int, default=450_000)
    parser.add_argument('--task', choices=TASK_KEYS, action='append')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    for task_key in args.task or TASK_KEYS:
        build_task(task_key, args.target_points, args.force)


if __name__ == '__main__':
    main()
