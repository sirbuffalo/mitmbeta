from datetime import datetime, timezone
from os import getenv, makedirs
from pathlib import Path
import re
import shutil
from secrets import token_urlsafe
import subprocess
import sys
import tempfile
import tomllib
from urllib.parse import urlencode
from email.message import EmailMessage
import smtplib

import requests
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.secret_key = getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL', 'sqlite:///app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'
GOOGLE_SCOPES = 'openid email profile'
VIDEO_STYLING_DIR = Path(__file__).parent / 'video_styling'
VIDEO_FILES_DIR = Path(__file__).parent / 'video_files'
BASE_VIDEO_DIR = Path(__file__).parent / 'instance' / 'base_videos'
MERGED_VIDEO_DIR = Path(__file__).parent / 'instance' / 'merged_videos'
HLS_VIDEO_DIR = Path(__file__).parent / 'instance' / 'hls_videos'
VIDEO_FILE_EXTENSIONS = ('.mp4', '.webm', '.ogg', '.mov')
VIDEO_CHUNK_SIZE = 1024 * 1024
VIDEO_MIME_TYPES = {
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.ogg': 'video/ogg',
    '.mov': 'video/quicktime',
    '.m3u8': 'application/vnd.apple.mpegurl',
    '.ts': 'video/mp2t',
}
FFMPEG_FALLBACK_PATHS = (
    '/opt/homebrew/bin/ffmpeg',
    '/usr/local/bin/ffmpeg',
    '/opt/local/bin/ffmpeg',
    '/Applications/Note Block Studio.app/Contents/Resources/ffmpeg',
)
VIDEO_QUALITIES = {
    '1080p': {
        'label': '1080p',
        'width': 1920,
        'height': 1080,
        'standard_bitrate': '8M',
        'high_fps_bitrate': '12M',
    },
    '720p': {
        'label': '720p',
        'width': 1280,
        'height': 720,
        'standard_bitrate': '5M',
        'high_fps_bitrate': '7500k',
    },
    '480p': {
        'label': '480p',
        'width': 854,
        'height': 480,
        'standard_bitrate': '2500k',
        'high_fps_bitrate': '4M',
    },
    '360p': {
        'label': '360p',
        'width': 640,
        'height': 360,
        'standard_bitrate': '1M',
        'high_fps_bitrate': '1500k',
    },
}
VIDEO_AUDIO_BITRATE = '384k'
VIDEO_OUTPUT_FPS = 30
HARDWARE_ENCODER = None

COURSES = {

    'home':{
        'question' : '',
       'courses' :    [],
        'links' :   []
    },

    'Algebra and Calculus A':
    
    {

        "question" : "How can we find the minimum of a function?",

    'nodes' : [
   {"id":"Minimization"},
   {"id":"Differentiation"},
   {"id":"Solving\nFor 0s"},
   {"id":"Solving\nLinear\nEquations"},
   {"id":"Solving\nQuadratic\nEquations"},
   {"id":"Power\nRule"},
   {"id":"Product\nRule"},
   {"id":"Quotient\nRule"},
   {"id":"Chain\nRule"}
   ],


    'edges' : [
   ["Minimization", "Differentiation"],
   ["Minimization", "Solving\nFor 0s"],
   ["Product\nRule", "Power\nRule"],
   ["Quotient\nRule", "Product\nRule"],
   ["Chain\nRule", "Product\nRule"],
   ["Differentiation", "Chain\nRule"],
   ["Differentiation", "Power\nRule"],
   ["Differentiation", "Quotient\nRule"],
   ["Differentiation", "Product\nRule"],
   ["Solving\nFor 0s", "Solving\nLinear\nEquations"],
   ["Solving\nQuadratic\nEquations", "Solving\nLinear\nEquations"],
   ["Solving\nFor 0s", "Solving\nQuadratic\nEquations"]
    ]
    },

    'Combinatorics': 
    {

    "question": "Suppose we have 13 people in a line randomly jump either left or right. What is the probability that the teams will differ by at least 2 people?",


  "nodes": [
    {"id": "Basic\nArithmetic"},
    {"id": "Factorials"},
    {"id": "Permutations"},
    {"id": "Combinations"},
    {"id": "Choose"},
    {"id": "Overcounting"},
    {"id": "Complementary\nCounting"},
    {"id": "Probability"},
   {"id":"Jumping\nProblem"}
  ],

  "edges": [
    ["Factorials", "Basic\nArithmetic"],

    ["Permutations", "Factorials"],
    ["Combinations", "Factorials"],

    ["Choose", "Combinations"],

    ["Probability", "Basic\nArithmetic"],

    ["Overcounting", "Permutations"],
    ["Overcounting", "Combinations"],

    ["Complementary\nCounting", "Probability"],
   ["Jumping\nProblem", "Complementary\nCounting"],
   ["Jumping\nProblem", "Choose"]
  ]
}

}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    picture = db.Column(db.String(1024), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class VideoProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.String(255), nullable=False)
    seconds = db.Column(db.Float, nullable=False, default=0)
    duration = db.Column(db.Float, nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint('user_id', 'video_id', name='unique_user_video_progress'),
    )


makedirs(app.instance_path, exist_ok=True)
BASE_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
MERGED_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
HLS_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
with app.app_context():
    db.create_all()


def get_current_user():
    session_user = session.get('user')
    if not session_user:
        return None

    return User.query.get(session_user.get('id'))


def valid_video_id(video_id):
    return not ('/' in video_id or '\\' in video_id or video_id in {'', '.', '..'})


def find_video_file(video_id):
    return next(
        (
            VIDEO_FILES_DIR / f'{video_id}{extension}'
            for extension in VIDEO_FILE_EXTENSIONS
            if (VIDEO_FILES_DIR / f'{video_id}{extension}').is_file()
        ),
        None,
    )


def load_video_styling(video_id):
    styling_path = (VIDEO_STYLING_DIR / f'{video_id}.toml').resolve()
    if styling_path.parent != VIDEO_STYLING_DIR.resolve() or not styling_path.is_file():
        return None

    with styling_path.open('rb') as file:
        return tomllib.load(file)


def get_ffmpeg_path():
    configured_ffmpeg = getenv('FFMPEG_BIN')
    if configured_ffmpeg and Path(configured_ffmpeg).is_file():
        return configured_ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass

    path_ffmpeg = shutil.which('ffmpeg')
    if path_ffmpeg:
        return path_ffmpeg

    return next((path for path in FFMPEG_FALLBACK_PATHS if Path(path).is_file()), None)


def get_h264_encoder():
    global HARDWARE_ENCODER
    if HARDWARE_ENCODER is not None:
        return HARDWARE_ENCODER

    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError('ffmpeg is required to build videos.')

    result = subprocess.run(
        [
            ffmpeg_path,
            '-hide_banner',
            '-f',
            'lavfi',
            '-i',
            'testsrc2=size=128x72:rate=24:duration=0.25',
            '-c:v',
            'h264_videotoolbox',
            '-allow_sw',
            '1',
            '-f',
            'null',
            '-',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    HARDWARE_ENCODER = 'h264_videotoolbox' if result.returncode == 0 else 'libx264'
    return HARDWARE_ENCODER


def get_video_info(video_path):
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError('ffmpeg is required to build merged videos.')

    result = subprocess.run(
        [ffmpeg_path, '-i', str(video_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r'Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)', result.stderr)
    if match is None:
        raise RuntimeError(f'Could not read duration for {video_path.name}.')

    hours, minutes, seconds = match.groups()
    video_line = next((line for line in result.stderr.splitlines() if ' Video: ' in line), '')
    size_match = re.search(r'(\d{2,5})x(\d{2,5})', video_line)
    fps_match = re.search(r'(\d+(?:\.\d+)?)\s+fps', video_line)
    if size_match is None:
        raise RuntimeError(f'Could not read dimensions for {video_path.name}.')

    return {
        'duration': (int(hours) * 3600) + (int(minutes) * 60) + float(seconds),
        'width': int(size_match.group(1)),
        'height': int(size_match.group(2)),
        'fps': float(fps_match.group(1)) if fps_match else 30,
    }


def get_video_duration(video_path):
    return get_video_info(video_path)['duration']


def iter_valid_interjections(video_data, video_duration):
    interjections = video_data.get('interjections', [])
    for interjection in sorted(interjections, key=lambda item: item.get('time', 0)):
        interjection_video_id = interjection.get('video')
        if not interjection_video_id or not valid_video_id(interjection_video_id):
            continue

        try:
            interjection_time = float(interjection.get('time'))
        except (TypeError, ValueError):
            continue

        if 0 <= interjection_time <= video_duration:
            yield interjection_time, interjection_video_id


def offset_ranges(ranges, offset):
    shifted_ranges = []
    for range_data in ranges:
        shifted_range = {
            **range_data,
            'start': range_data['start'] + offset,
            'end': range_data['end'] + offset,
        }
        if shifted_range.get('skip_end') is not None:
            shifted_range['skip_end'] += offset

        shifted_ranges.append(shifted_range)

    return shifted_ranges


def build_video_plan(video_id, depth=0, stack=None):
    if stack is None:
        stack = []

    if video_id in stack:
        raise RuntimeError(f'Circular interjection reference: {" -> ".join([*stack, video_id])}')

    video_data = load_video_styling(video_id)
    video_file = find_video_file(video_id)
    if video_data is None or video_file is None:
        raise RuntimeError(f'Video {video_id} is missing its TOML or video file.')

    title = video_data.get('title', video_id)
    video_info = get_video_info(video_file)
    video_duration = video_info['duration']
    timeline_cursor = 0
    source_cursor = 0
    segments = []
    ranges = []

    def add_source_segment(start, end):
        nonlocal timeline_cursor
        segment_duration = max(end - start, 0)
        if segment_duration <= 0:
            return

        segment_start = timeline_cursor
        timeline_cursor += segment_duration
        segments.append(
            {
                'source': video_file,
                'start': start,
                'duration': segment_duration,
                'fps': video_info['fps'],
            }
        )
        ranges.append(
            {
                'start': segment_start,
                'end': timeline_cursor,
                'video_id': video_id,
                'title': title,
                'depth': depth,
                'skip_end': None,
            }
        )

    for interjection_time, interjection_video_id in iter_valid_interjections(video_data, video_duration):
        if interjection_time < source_cursor:
            continue

        add_source_segment(source_cursor, interjection_time)
        child_plan = build_video_plan(interjection_video_id, depth + 1, [*stack, video_id])
        child_start = timeline_cursor
        segments.extend(child_plan['segments'])
        ranges.extend(offset_ranges(child_plan['ranges'], child_start))
        timeline_cursor += child_plan['duration']
        source_cursor = interjection_time

    add_source_segment(source_cursor, video_duration)

    if depth > 0:
        for range_data in ranges:
            if range_data['depth'] == depth and range_data['skip_end'] is None:
                range_data['skip_end'] = timeline_cursor

    return {
        'duration': timeline_cursor,
        'segments': segments,
        'ranges': ranges,
    }


def merged_video_name(video_id, quality='1080p'):
    return f'{video_id}-{quality}.mp4'


def base_video_name(video_id, quality='1080p'):
    return f'{video_id}-{quality}.mp4'


def hls_video_dir_name(video_id):
    return video_id


def get_quality_config(quality):
    if quality not in VIDEO_QUALITIES:
        raise RuntimeError(f'Unknown video quality: {quality}')

    return VIDEO_QUALITIES[quality]


def get_quality_bitrate(quality_config, plan):
    max_fps = max((segment.get('fps', 30) for segment in plan['segments']), default=30)
    return quality_config['high_fps_bitrate'] if max_fps > 30 else quality_config['standard_bitrate']


def bitrate_to_kbits(bitrate):
    if bitrate.endswith('M'):
        return int(float(bitrate[:-1]) * 1000)

    if bitrate.endswith('k'):
        return int(float(bitrate[:-1]))

    return int(bitrate) // 1000


def get_merged_video(video_id, quality='1080p'):
    get_quality_config(quality)
    try:
        plan = build_composed_video_plan(video_id, quality)
    except RuntimeError:
        plan = build_video_plan(video_id)

    return MERGED_VIDEO_DIR / merged_video_name(video_id, quality), plan['ranges']


def get_base_video(video_id, quality='1080p'):
    get_quality_config(quality)
    return BASE_VIDEO_DIR / base_video_name(video_id, quality)


def get_hls_video(video_id, quality='1080p'):
    get_quality_config(quality)
    try:
        plan = build_composed_video_plan(video_id, quality)
    except RuntimeError:
        plan = build_video_plan(video_id)

    playlist_path = HLS_VIDEO_DIR / hls_video_dir_name(video_id) / quality / 'playlist.m3u8'
    return playlist_path, plan['ranges']


def get_hls_master_playlist(video_id):
    try:
        plan = build_composed_video_plan(video_id, '1080p')
    except RuntimeError:
        plan = build_video_plan(video_id)

    playlist_path = HLS_VIDEO_DIR / hls_video_dir_name(video_id) / 'master.m3u8'
    return playlist_path, plan['ranges']


def get_quality_sources(video_id):
    hls_dir_name = hls_video_dir_name(video_id)
    master_path = HLS_VIDEO_DIR / hls_dir_name / 'master.m3u8'
    sources = [
        {
            'quality': 'auto',
            'label': 'Auto',
            'url': url_for('hls_video_file', filename=f'{hls_dir_name}/master.m3u8'),
            'exists': master_path.is_file(),
        }
    ]
    for quality, config in VIDEO_QUALITIES.items():
        video_path = HLS_VIDEO_DIR / hls_dir_name / quality / 'playlist.m3u8'
        sources.append(
            {
                'quality': quality,
                'label': config['label'],
                'url': url_for('hls_video_file', filename=f'{hls_dir_name}/{quality}/playlist.m3u8'),
                'exists': video_path.is_file(),
            }
        )

    return sources


def write_concat_file(clip_paths, concat_path):
    with concat_path.open('w', encoding='utf-8') as file:
        for clip_path in clip_paths:
            escaped_path = str(clip_path).replace("'", "'\\''")
            file.write(f"file '{escaped_path}'\n")


def get_transcode_args(quality_config, video_bitrate, force_hls_keyframes=True):
    encoder = get_h264_encoder()
    video_filter = (
        f'scale={quality_config["width"]}:{quality_config["height"]}:'
        f'force_original_aspect_ratio=decrease,'
        f'pad={quality_config["width"]}:{quality_config["height"]}:(ow-iw)/2:(oh-ih)/2,'
        f'fps={VIDEO_OUTPUT_FPS},setpts=PTS-STARTPTS'
    )
    args = [
        '-vf',
        video_filter,
        '-c:v',
        encoder,
        *(['-allow_sw', '1'] if encoder == 'h264_videotoolbox' else ['-preset', 'veryfast']),
        '-b:v',
        video_bitrate,
        '-maxrate',
        video_bitrate,
        '-bufsize',
        f'{bitrate_to_kbits(video_bitrate) * 2}k',
        '-pix_fmt',
        'yuv420p',
    ]
    if force_hls_keyframes:
        args.extend(['-force_key_frames', 'expr:gte(t,n_forced*4)'])

    args.extend(
        [
            '-c:a',
            'aac',
            '-af',
            'aresample=async=1:first_pts=0',
            '-b:a',
            VIDEO_AUDIO_BITRATE,
        ]
    )
    return args


def build_base_video(video_id, quality='1080p'):
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError('ffmpeg is required to build base videos.')

    quality_config = get_quality_config(quality)
    source_path = find_video_file(video_id)
    if source_path is None:
        raise RuntimeError(f'Video {video_id} is missing its raw video file.')

    source_info = get_video_info(source_path)
    output_path = get_base_video(video_id, quality)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_bitrate = (
        quality_config['high_fps_bitrate']
        if source_info.get('fps', 30) > 30
        else quality_config['standard_bitrate']
    )
    with tempfile.TemporaryDirectory(dir=BASE_VIDEO_DIR) as temp_dir:
        temp_output_path = Path(temp_dir) / output_path.name
        subprocess.run(
            [
                ffmpeg_path,
                '-y',
                '-i',
                str(source_path),
                *get_transcode_args(quality_config, video_bitrate),
                '-movflags',
                '+faststart',
                str(temp_output_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        temp_output_path.replace(output_path)

    return output_path


def build_composed_video_plan(video_id, quality='1080p', depth=0, stack=None):
    if stack is None:
        stack = []

    if video_id in stack:
        raise RuntimeError(f'Circular interjection reference: {" -> ".join([*stack, video_id])}')

    video_data = load_video_styling(video_id)
    source_file = get_base_video(video_id, quality)
    if video_data is None or not source_file.is_file():
        raise RuntimeError(f'Video {video_id} is missing its TOML or {quality} base video.')

    title = video_data.get('title', video_id)
    video_info = get_video_info(source_file)
    video_duration = video_info['duration']
    timeline_cursor = 0
    source_cursor = 0
    segments = []
    ranges = []

    def add_source_segment(start, end):
        nonlocal timeline_cursor
        segment_duration = max(end - start, 0)
        if segment_duration <= 0:
            return

        segment_start = timeline_cursor
        timeline_cursor += segment_duration
        segments.append(
            {
                'source': source_file,
                'start': start,
                'duration': segment_duration,
                'fps': video_info['fps'],
            }
        )
        ranges.append(
            {
                'start': segment_start,
                'end': timeline_cursor,
                'video_id': video_id,
                'title': title,
                'depth': depth,
                'skip_end': None,
            }
        )

    for interjection_time, interjection_video_id in iter_valid_interjections(video_data, video_duration):
        if interjection_time < source_cursor:
            continue

        add_source_segment(source_cursor, interjection_time)
        child_video_path = MERGED_VIDEO_DIR / merged_video_name(interjection_video_id, quality)
        if not child_video_path.is_file():
            raise RuntimeError(f'Video {interjection_video_id} must be premade before {video_id}.')

        child_plan = build_composed_video_plan(interjection_video_id, quality, depth + 1, [*stack, video_id])
        child_info = get_video_info(child_video_path)
        child_start = timeline_cursor
        timeline_cursor += child_info['duration']
        segments.append(
            {
                'source': child_video_path,
                'start': 0,
                'duration': child_info['duration'],
                'fps': child_info['fps'],
            }
        )
        ranges.extend(offset_ranges(child_plan['ranges'], child_start))
        source_cursor = interjection_time

    add_source_segment(source_cursor, video_duration)

    if depth > 0:
        for range_data in ranges:
            if range_data['depth'] == depth and range_data['skip_end'] is None:
                range_data['skip_end'] = timeline_cursor

    return {
        'duration': timeline_cursor,
        'segments': segments,
        'ranges': ranges,
    }


def build_merged_video(video_id, quality='1080p'):
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError('ffmpeg is required to build merged videos.')

    quality_config = get_quality_config(quality)
    base_video_path = get_base_video(video_id, quality)
    if not base_video_path.is_file():
        build_base_video(video_id, quality)

    plan = build_composed_video_plan(video_id, quality)
    output_path = MERGED_VIDEO_DIR / merged_video_name(video_id, quality)

    if not get_video_dependencies(video_id):
        with tempfile.TemporaryDirectory(dir=MERGED_VIDEO_DIR) as temp_dir:
            temp_output_path = Path(temp_dir) / output_path.name
            shutil.copy2(base_video_path, temp_output_path)
            temp_output_path.replace(output_path)

        return output_path, plan['ranges']

    video_bitrate = get_quality_bitrate(quality_config, plan)
    with tempfile.TemporaryDirectory(dir=MERGED_VIDEO_DIR) as temp_dir:
        temp_path = Path(temp_dir)
        clip_paths = []
        for index, segment in enumerate(plan['segments']):
            clip_path = temp_path / f'clip-{index:04}.mp4'
            clip_encoder = get_h264_encoder()
            clip_encode_args = [
                '-vf',
                f'fps={VIDEO_OUTPUT_FPS},setpts=PTS-STARTPTS',
                '-c:v',
                clip_encoder,
                *(['-allow_sw', '1', '-b:v', '20M'] if clip_encoder == 'h264_videotoolbox' else ['-preset', 'veryfast', '-crf', '18']),
                '-pix_fmt',
                'yuv420p',
                '-c:a',
                'aac',
                '-af',
                'aresample=async=1:first_pts=0',
                '-b:a',
                VIDEO_AUDIO_BITRATE,
            ]
            subprocess.run(
                [
                    ffmpeg_path,
                    '-y',
                    '-fflags',
                    '+genpts',
                    '-i',
                    str(segment['source']),
                    '-ss',
                    f'{segment["start"]:.3f}',
                    '-t',
                    f'{segment["duration"]:.3f}',
                    '-map',
                    '0:v:0',
                    '-map',
                    '0:a?',
                    *clip_encode_args,
                    '-avoid_negative_ts',
                    'make_zero',
                    '-movflags',
                    '+faststart',
                    str(clip_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            clip_paths.append(clip_path)

        concat_path = temp_path / 'concat.txt'
        write_concat_file(clip_paths, concat_path)
        temp_output_path = temp_path / output_path.name
        concat_output_args = get_transcode_args(quality_config, video_bitrate)

        subprocess.run(
            [
                ffmpeg_path,
                '-y',
                '-fflags',
                '+genpts',
                '-f',
                'concat',
                '-safe',
                '0',
                '-i',
                str(concat_path),
                *concat_output_args,
                '-movflags',
                '+faststart',
                str(temp_output_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        temp_output_path.replace(output_path)

    return output_path, plan['ranges']


def build_hls_video(video_id, quality='1080p'):
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError('ffmpeg is required to build HLS videos.')

    source_video_path, timeline_ranges = get_merged_video(video_id, quality)
    if not source_video_path.is_file():
        source_video_path, timeline_ranges = build_merged_video(video_id, quality)

    playlist_path = HLS_VIDEO_DIR / hls_video_dir_name(video_id) / quality / 'playlist.m3u8'

    playlist_path.parent.mkdir(parents=True, exist_ok=True)
    for old_file in playlist_path.parent.glob('*'):
        if old_file.is_file():
            old_file.unlink()

    segment_pattern = playlist_path.parent / 'segment-%05d.ts'
    encode_args = [
        '-c',
        'copy',
        '-hls_flags',
        'independent_segments',
    ]

    subprocess.run(
        [
            ffmpeg_path,
            '-y',
            '-i',
            str(source_video_path),
            *encode_args,
            '-hls_time',
            '4',
            '-hls_playlist_type',
            'vod',
            '-hls_segment_filename',
            str(segment_pattern),
            str(playlist_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return playlist_path, timeline_ranges


def get_hls_stream_info(video_id, quality, plan):
    quality_config = get_quality_config(quality)
    video_bitrate = get_quality_bitrate(quality_config, plan)

    return {
        'bandwidth': (bitrate_to_kbits(video_bitrate) + bitrate_to_kbits(VIDEO_AUDIO_BITRATE)) * 1000,
        'resolution': f'{quality_config["width"]}x{quality_config["height"]}',
    }


def build_hls_master_playlist(video_id):
    master_path = HLS_VIDEO_DIR / hls_video_dir_name(video_id) / 'master.m3u8'
    for quality in VIDEO_QUALITIES:
        build_hls_video(video_id, quality)

    plan = build_composed_video_plan(video_id, '1080p')
    lines = ['#EXTM3U', '#EXT-X-VERSION:3']
    for quality in VIDEO_QUALITIES:
        stream_info = get_hls_stream_info(video_id, quality, plan)
        lines.append(
            '#EXT-X-STREAM-INF:'
            f'BANDWIDTH={stream_info["bandwidth"]},'
            f'RESOLUTION={stream_info["resolution"]}'
        )
        lines.append(f'{quality}/playlist.m3u8')

    master_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return master_path, plan['ranges']


def list_video_ids():
    return sorted(path.stem for path in VIDEO_STYLING_DIR.glob('*.toml') if valid_video_id(path.stem))


def get_video_dependencies(video_id):
    video_data = load_video_styling(video_id)
    if video_data is None:
        raise RuntimeError(f'Video {video_id} is missing its TOML file.')

    dependencies = []
    for interjection in video_data.get('interjections', []):
        interjection_video_id = interjection.get('video')
        if interjection_video_id and valid_video_id(interjection_video_id):
            dependencies.append(interjection_video_id)

    return dependencies


def build_dependency_graph(video_ids=None):
    roots = video_ids or list_video_ids()
    graph = {}

    def visit(video_id):
        if video_id in graph:
            return

        dependencies = get_video_dependencies(video_id)
        graph[video_id] = dependencies
        for dependency in dependencies:
            visit(dependency)

    for video_id in roots:
        visit(video_id)

    return graph


def get_dependency_build_order(video_ids=None):
    graph = build_dependency_graph(video_ids)
    order = []
    visiting = set()
    visited = set()

    def visit(video_id):
        if video_id in visited:
            return

        if video_id in visiting:
            raise RuntimeError(f'Circular interjection reference involving {video_id}.')

        visiting.add(video_id)
        for dependency in graph.get(video_id, []):
            visit(dependency)

        visiting.remove(video_id)
        visited.add(video_id)
        order.append(video_id)

    for video_id in graph:
        visit(video_id)

    return order


def is_video_progress_finished(progress):
    if progress is None or not progress.duration or progress.duration <= 0:
        return False

    return progress.seconds >= progress.duration - 1 or progress.seconds / progress.duration >= 0.98


def get_video_tree_layers(user=None):
    graph = build_dependency_graph()
    layer_by_video = {}
    visiting = set()
    progress_by_video = {}
    if user is not None:
        progress_by_video = {
            progress.video_id: progress
            for progress in VideoProgress.query.filter_by(user_id=user.id).all()
        }

    def get_layer(video_id):
        if video_id in layer_by_video:
            return layer_by_video[video_id]

        if video_id in visiting:
            raise RuntimeError(f'Circular interjection reference involving {video_id}.')

        visiting.add(video_id)
        dependencies = graph.get(video_id, [])
        layer = 0 if not dependencies else 1 + max(get_layer(dependency) for dependency in dependencies)
        visiting.remove(video_id)
        layer_by_video[video_id] = layer
        return layer

    for video_id in graph:
        get_layer(video_id)

    layers = []
    for layer_index in sorted(set(layer_by_video.values()), reverse=True):
        videos = []
        for video_id in sorted(video_id for video_id, layer in layer_by_video.items() if layer == layer_index):
            video_data = load_video_styling(video_id) or {}
            dependencies = graph.get(video_id, [])
            progress = progress_by_video.get(video_id)
            videos.append(
                {
                    'id': video_id,
                    'title': video_data.get('title', video_id),
                    'dependency_ids': dependencies,
                    'finished': is_video_progress_finished(progress),
                    'dependencies': [
                        {
                            'id': dependency,
                            'title': (load_video_styling(dependency) or {}).get('title', dependency),
                        }
                        for dependency in dependencies
                    ],
                }
            )

        layers.append({'index': layer_index, 'videos': videos})

    return layers


def premake_merged_videos(video_ids=None):
    build_order = get_dependency_build_order(video_ids)
    for video_id in build_order:
        for quality in VIDEO_QUALITIES:
            build_base_video(video_id, quality)

    built_videos = []
    for video_id in build_order:
        for quality in VIDEO_QUALITIES:
            output_path, _timeline_ranges = build_merged_video(video_id, quality)
            built_videos.append(output_path)

    for video_id in build_order:
        build_hls_master_playlist(video_id)

    return built_videos


def stream_file(path, start, end):
    with path.open('rb') as file:
        file.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = file.read(min(VIDEO_CHUNK_SIZE, remaining))
            if not chunk:
                break

            remaining -= len(chunk)
            yield chunk


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/about-us')
def about_us():
    return render_template('aboutus.html')


@app.get('/videos')
def videos():
    try:
        layers = get_video_tree_layers(get_current_user())
    except RuntimeError as error:
        return str(error), 500

    return render_template('videos.html', layers=layers)


@app.get('/login')
def login():
    return render_template(
        'login.html',
        user=session.get('user'),
        google_configured=bool(getenv('GOOGLE_CLIENT_ID') and getenv('GOOGLE_CLIENT_SECRET')),
    )


@app.get('/account')
def account():
    user = session.get('user')
    if user is None:
        return redirect(url_for('login'))

    return render_template('account.html', user=user)


@app.get('/video/<video_id>')
def video(video_id):
    if not valid_video_id(video_id):
        return 'Video not found', 404

    video_data = load_video_styling(video_id)
    if video_data is None:
        return 'Video not found', 404

    selected_quality = request.args.get('quality', 'auto')
    if selected_quality != 'auto' and selected_quality not in VIDEO_QUALITIES:
        selected_quality = 'auto'

    try:
        if selected_quality == 'auto':
            hls_playlist_path, timeline_ranges = get_hls_master_playlist(video_id)
        else:
            hls_playlist_path, timeline_ranges = get_hls_video(video_id, selected_quality)
    except RuntimeError as error:
        return str(error), 500

    if not hls_playlist_path.is_file():
        return 'HLS video has not been premade yet. Run: python main.py premake-videos', 500

    quality_sources = get_quality_sources(video_id)
    if not all(source['exists'] for source in quality_sources):
        return 'Not all HLS video qualities have been premade yet. Run: python main.py premake-videos', 500

    user = get_current_user()
    progress = None
    finished_video_ids = []
    if user is not None:
        progress = VideoProgress.query.filter_by(user_id=user.id, video_id=video_id).first()
        finished_video_ids = [
            saved_progress.video_id
            for saved_progress in VideoProgress.query.filter_by(user_id=user.id).all()
            if is_video_progress_finished(saved_progress)
        ]

    return render_template(
        'video.html',
        title=video_data.get('title', video_id),
        video_url=url_for(
            'hls_video_file',
            filename=(
                f'{hls_video_dir_name(video_id)}/master.m3u8'
                if selected_quality == 'auto'
                else f'{hls_video_dir_name(video_id)}/{selected_quality}/playlist.m3u8'
            ),
        ),
        interjections=timeline_ranges,
        quality_sources=quality_sources,
        finished_video_ids=finished_video_ids,
        selected_quality=selected_quality,
        saved_seconds=progress.seconds if progress else 0,
        progress_url=url_for('save_video_progress', video_id=video_id),
        video_js_version=(Path(__file__).parent / 'static' / 'video.js').stat().st_mtime_ns,
    )


@app.post('/video/<video_id>/progress')
def save_video_progress(video_id):
    if not valid_video_id(video_id) or load_video_styling(video_id) is None:
        return jsonify({'error': 'Video not found'}), 404

    user = get_current_user()
    if user is None:
        return jsonify({'saved': False}), 401

    data = request.get_json(silent=True) or {}
    try:
        seconds = max(float(data.get('seconds', 0)), 0)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid seconds'}), 400

    duration = data.get('duration')
    try:
        duration = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None

    if duration is not None and duration > 0:
        seconds = min(seconds, duration)

    progress = VideoProgress.query.filter_by(user_id=user.id, video_id=video_id).first()
    if progress is None:
        progress = VideoProgress(user_id=user.id, video_id=video_id)
        db.session.add(progress)

    if data.get('finished') is True:
        duration = duration if duration and duration > 0 else 1
        seconds = duration
    elif data.get('finished') is False:
        seconds = 0
        duration = duration if duration and duration > 0 else None

    progress.seconds = seconds
    progress.duration = duration if duration and duration > 0 else None
    db.session.commit()

    return jsonify({'saved': True, 'seconds': progress.seconds})


def serve_video_path(video_path):
    file_size = video_path.stat().st_size
    range_header = request.headers.get('Range')
    content_type = VIDEO_MIME_TYPES.get(video_path.suffix.lower(), 'application/octet-stream')

    if range_header:
        try:
            range_value = range_header.replace('bytes=', '', 1)
            start_text, end_text = range_value.split('-', 1)
            if start_text:
                start = int(start_text)
                end = int(end_text) if end_text else file_size - 1
            else:
                suffix_length = int(end_text)
                start = max(file_size - suffix_length, 0)
                end = file_size - 1
        except ValueError:
            return Response(status=416, headers={'Content-Range': f'bytes */{file_size}'})

        if start >= file_size or end >= file_size or start > end:
            return Response(status=416, headers={'Content-Range': f'bytes */{file_size}'})

        content_length = end - start + 1
        return Response(
            stream_file(video_path, start, end),
            status=206,
            mimetype=content_type,
            direct_passthrough=True,
            headers={
                'Accept-Ranges': 'bytes',
                'Content-Length': str(content_length),
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Cache-Control': 'public, max-age=3600',
            },
        )

    return Response(
        stream_file(video_path, 0, file_size - 1),
        mimetype=content_type,
        direct_passthrough=True,
        headers={
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size),
            'Cache-Control': 'public, max-age=3600',
        },
    )


@app.get('/video_files/<path:filename>')
def video_file(filename):
    if '/' in filename or '\\' in filename or filename in {'', '.', '..'}:
        return 'Video file not found', 404

    video_path = (VIDEO_FILES_DIR / filename).resolve()
    if video_path.parent != VIDEO_FILES_DIR.resolve() or not video_path.is_file():
        return 'Video file not found', 404

    return serve_video_path(video_path)


@app.get('/merged_video_files/<path:filename>')
def merged_video_file(filename):
    if '/' in filename or '\\' in filename or filename in {'', '.', '..'}:
        return 'Video file not found', 404

    video_path = (MERGED_VIDEO_DIR / filename).resolve()
    if video_path.parent != MERGED_VIDEO_DIR.resolve() or not video_path.is_file():
        return 'Video file not found', 404

    return serve_video_path(video_path)


@app.get('/hls_video_files/<path:filename>')
def hls_video_file(filename):
    if '\\' in filename or filename in {'', '.', '..'}:
        return 'Video file not found', 404

    video_path = (HLS_VIDEO_DIR / filename).resolve()
    try:
        video_path.relative_to(HLS_VIDEO_DIR.resolve())
    except ValueError:
        return 'Video file not found', 404

    if not video_path.is_file():
        return 'Video file not found', 404

    return serve_video_path(video_path)


@app.get('/login/google')
def google_login():
    client_id = getenv('GOOGLE_CLIENT_ID')
    client_secret = getenv('GOOGLE_CLIENT_SECRET')
    if not client_id or not client_secret:
        return render_template(
            'login.html',
            error='Google sign in is not configured yet.',
            google_configured=False,
            user=session.get('user'),
        ), 500

    state = token_urlsafe(32)
    session['oauth_state'] = state

    auth_params = {
        'client_id': client_id,
        'redirect_uri': url_for('google_callback', _external=True),
        'response_type': 'code',
        'scope': GOOGLE_SCOPES,
        'state': state,
        'prompt': 'select_account',
    }
    return redirect(f'{GOOGLE_AUTH_URL}?{urlencode(auth_params)}')


@app.get('/login/callback')
def google_callback():
    if request.args.get('error'):
        return render_template(
            'login.html',
            error=f'Google sign in failed: {request.args["error"]}',
            google_configured=True,
            user=session.get('user'),
        ), 400

    if request.args.get('state') != session.pop('oauth_state', None):
        return render_template(
            'login.html',
            error='Google sign in failed because the session state did not match.',
            google_configured=True,
            user=session.get('user'),
        ), 400

    code = request.args.get('code')
    if not code:
        return render_template(
            'login.html',
            error='Google did not return an authorization code.',
            google_configured=True,
            user=session.get('user'),
        ), 400

    token_response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'code': code,
            'client_id': getenv('GOOGLE_CLIENT_ID'),
            'client_secret': getenv('GOOGLE_CLIENT_SECRET'),
            'redirect_uri': url_for('google_callback', _external=True),
            'grant_type': 'authorization_code',
        },
        timeout=10,
    )

    if not token_response.ok:
        return render_template(
            'login.html',
            error='Google sign in failed while exchanging the authorization code.',
            google_configured=True,
            user=session.get('user'),
        ), 400

    access_token = token_response.json().get('access_token')
    userinfo_response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )

    if not userinfo_response.ok:
        return render_template(
            'login.html',
            error='Google sign in failed while loading your profile.',
            google_configured=True,
            user=session.get('user'),
        ), 400

    google_user = userinfo_response.json()
    user = User.query.filter_by(google_id=google_user.get('id')).first()

    if user is None:
        user = User(google_id=google_user.get('id'), email=google_user.get('email'))
        db.session.add(user)

    user.email = google_user.get('email')
    user.name = google_user.get('name')
    user.picture = google_user.get('picture')
    db.session.commit()

    session['user'] = {
        'id': user.id,
        'google_id': user.google_id,
        'email': user.email,
        'name': user.name,
        'picture': user.picture,
    }
    return redirect(url_for('account'))


@app.post('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.get('/courses/<course>')
def courses(course):


    user = session.get('user')
    if user is None:
        return redirect(url_for('login'))

    if course != 'home':
        return render_template('course1.html', user=session.get('user'), course_name = course, courses = COURSES[course])
    else:
        return render_template('courses.html', user=session.get('user'))


@app.get('/contact-us')
def contact_us():
    return render_template('contact_us.html')

@app.get('/feedback')
def do_feedback():
    rating = request.args.get('rating')
    comments = request.args.get('comments')


    # 1. Define credentials and addresses
    SMTP_SERVER = "smtp.gmail.com"  # Replace with your provider's SMTP server
    SMTP_PORT = 587
    SENDER_EMAIL = "info.project1716@gmail.com"
    SENDER_PASSWORD = "wnmbuqjxwngzrgec"  # Do not use your main login password!
    RECEIVER_EMAIL = "info.project1716@gmail.com"

    # 2. Construct the email message
    msg = EmailMessage()
    msg["Subject"] = f"Review from {session.get('user', {}).get('name', 'Unknown')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.set_content(f"Rating {rating}/5\n\nComments:\n {comments}")

    # 3. Connect to the server and send
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        import traceback
        traceback.print_exc()
    return render_template('index.html')







@app.get('/contact-us')
def contact_us():
    return render_template('contact_us.html')

@app.get('/feedback')
def do_feedback():
    rating = request.args.get('rating')
    comments = request.args.get('comments')


    # 1. Define credentials and addresses
    SMTP_SERVER = "smtp.gmail.com"  # Replace with your provider's SMTP server
    SMTP_PORT = 587
    SENDER_EMAIL = "info.project1716@gmail.com"
    SENDER_PASSWORD = "wnmbuqjxwngzrgec"  # Do not use your main login password!
    RECEIVER_EMAIL = "info.project1716@gmail.com"

    # 2. Construct the email message
    msg = EmailMessage()
    msg["Subject"] = f"Rating and Comments from"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.set_content(f"Rating: {rating}, Comments: {comments}")

    # 3. Connect to the server and send
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        import traceback
        traceback.print_exc()
    return render_template('index.html')

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'video-build-order':
        requested_video_ids = sys.argv[2:] or None
        try:
            for video_id in get_dependency_build_order(requested_video_ids):
                dependencies = get_video_dependencies(video_id)
                if dependencies:
                    print(f'{video_id}: needs {", ".join(dependencies)}')
                else:
                    print(f'{video_id}: needs nothing')
        except RuntimeError as error:
            print(error, file=sys.stderr)
            raise SystemExit(1)

        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1] == 'premake-videos':
        requested_video_ids = sys.argv[2:] or None
        try:
            for premade_video in premake_merged_videos(requested_video_ids):
                print(premade_video)
        except (RuntimeError, subprocess.CalledProcessError) as error:
            print(error, file=sys.stderr)
            raise SystemExit(1)

        raise SystemExit(0)

    app.run(debug=True, port=8000)
