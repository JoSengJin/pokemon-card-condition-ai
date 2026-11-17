"""Offline synthetic-only display. No file paths, collection or label imports."""
import base64
import html
import json
from pathlib import Path
from .observation_assets import verify_assets


def render_page(packet, assets):
    verified = verify_assets(packet, assets)
    profile = packet["profile"]
    if (profile["renderer_version"] != "synthetic-observation-v1" or
            profile["resize"] not in (None, "none") or profile["interpolation"] is not None):
        raise ValueError("unsupported synthetic renderer profile")
    articles = []
    for entry in packet["entries"]:
        images = []
        for asset in entry["assets"]:
            width, height = profile["image_css"] or asset["size"]
            images.append(f'<img id="{entry["entry_id"]}-{asset["kind"]}" data-ref="{asset["ref"]}" '
                          f'width="{width}" height="{height}" alt="{asset["kind"]}">')
        articles.append(f'<article data-entry="{entry["entry_id"]}"><h2>{entry["entry_id"]}</h2>' + ''.join(images) + '</article>')
    public_packet = json.dumps(packet, ensure_ascii=False, allow_nan=False).replace('<', r'\u003c')
    public_assets = json.dumps({ref: base64.b64encode(raw).decode('ascii') for ref, raw in verified.items()})
    script = Path(__file__).with_name('observation_display.js').read_text()
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>합성 구역 판정 시험</title><style>body{font:16px/1.6 sans-serif;padding:20px}article{overflow:auto;margin:20px 0}'
            'img{display:block;margin:8px 0}pre{white-space:pre-wrap}textarea{display:block}</style>'
            '<h1>합성 시험 전용 · 실제 수집 미승인</h1><pre>' + html.escape(packet['instructions']) + '</pre>'
            '<p id="status">이미지 검증 전 · 판정 입력 잠김</p><main id="review">' + ''.join(articles) + '</main>'
            '<div id="response-controls"></div>'
            '<script id="packet" type="application/json">' + public_packet + '</script>'
            '<script id="assets" type="application/json">' + public_assets + '</script>'
            '<script id="display-code">' + script + '</script><script>initialize();</script></html>')
