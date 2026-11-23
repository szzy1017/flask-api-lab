import colorsys
import re

import requests
from flask import Flask, Response, jsonify, request

app = Flask(__name__)


def hex_to_rgb(hex_color):
    """Convert a six-digit HEX color to an RGB tuple in the 0-255 range."""
    value = hex_color.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("HEX color must be 6 characters")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """Convert RGB channel values in the 0-1 range to a HEX string."""
    channels = (max(0, min(255, round(value * 255))) for value in (r, g, b))
    return "{:02X}{:02X}{:02X}".format(*channels)


def get_colormind_palette():
    """Fetch an AI-generated color palette from the Colormind API."""
    try:
        response = requests.post(
            "http://colormind.io/api/", json={"model": "default"}, timeout=5
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        if not isinstance(result, list) or not result:
            return None
        if any(
            not isinstance(color, list)
            or len(color) != 3
            or any(not isinstance(channel, (int, float)) or not 0 <= channel <= 255 for channel in color)
            for color in result
        ):
            return None
        return ["#" + "".join(f"{round(channel):02X}" for channel in color) for color in result]
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return None


def generate_palette_by_mode(hex_color, mode):
    """Generate a palette according to the selected mode."""
    if mode == "ai":
        ai_palette = get_colormind_palette()
        if ai_palette:
            return ai_palette
        mode = "analogous"

    r, g, b = hex_to_rgb(hex_color)
    h, lightness, saturation = colorsys.rgb_to_hls(
        r / 255.0, g / 255.0, b / 255.0
    )

    hue_offsets = [0, 0.5] if mode == "complementary" else [-0.16, -0.08, 0, 0.08, 0.16]
    palette = []
    for offset in hue_offsets:
        new_hue = (h + offset) % 1.0
        nr, ng, nb = colorsys.hls_to_rgb(new_hue, lightness, saturation)
        palette.append(f"#{rgb_to_hex(nr, ng, nb)}")
    return palette


@app.route("/", methods=["GET"])
def home():
    return """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Palette Generator API Playground</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #f8fafc; color: #1e293b; }
        h1 { color: #0f172a; }
        .control-panel { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
        input, select, button { padding: 10px; font-size: 16px; border: 1px solid #cbd5e1; border-radius: 6px; }
        input[type="color"] { width: 52px; height: 44px; padding: 4px; cursor: pointer; }
        button { background: #2563eb; color: white; border: none; cursor: pointer; }
        button:hover { background: #1d4ed8; }
        button:disabled { opacity: .65; cursor: wait; }
        .preview-box { margin-top: 20px; }
        iframe { border: none; width: 100%; height: 140px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); background: white; }
        pre { background: #0f172a; color: #38bdf8; padding: 15px; border-radius: 8px; overflow-x: auto; min-height: 48px; }
        .error { color: #b91c1c; }
        @media (max-width: 520px) { body { margin: 24px auto; } .control-panel > * { flex: 1 1 auto; } }
    </style>
</head>
<body>
    <h1>🎨 Palette Generator Playground</h1>
    <p>直接測試調色盤 API，並預覽生成的 SVG 色卡。</p>

    <div class="control-panel">
        <label for="colorPicker">主色</label>
        <input type="color" id="colorPicker" value="#3498db" aria-label="選擇主色">
        <label for="modeSelect">配色模式</label>
        <select id="modeSelect">
            <option value="analogous">類似色 (Analogous)</option>
            <option value="complementary">互補色 (Complementary)</option>
            <option value="ai">AI 配色 (Colormind)</option>
        </select>
        <button id="generateButton" type="button">生成調色盤</button>
    </div>

    <div class="preview-box">
        <h2>SVG 卡片預覽</h2>
        <iframe id="svgFrame" title="調色盤 SVG 預覽" src="/api/palette/preview.svg?colors=3498db,2ecc71,f1c40f,e67e22,e74c3c"></iframe>
    </div>

    <div class="preview-box">
        <h2>API JSON 回傳結果</h2>
        <pre id="jsonResult" aria-live="polite">正在載入調色盤…</pre>
    </div>

    <script>
        const colorPicker = document.getElementById('colorPicker');
        const modeSelect = document.getElementById('modeSelect');
        const generateButton = document.getElementById('generateButton');
        const jsonResult = document.getElementById('jsonResult');
        const svgFrame = document.getElementById('svgFrame');

        async function fetchPalette() {
            generateButton.disabled = true;
            jsonResult.classList.remove('error');
            jsonResult.textContent = '正在產生調色盤…';
            try {
                const params = new URLSearchParams({
                    hex: colorPicker.value.slice(1),
                    mode: modeSelect.value
                });
                const response = await fetch(`/api/palette/generate?${params}`);
                const data = await response.json();
                jsonResult.textContent = JSON.stringify(data, null, 2);
                if (!response.ok) {
                    jsonResult.classList.add('error');
                    return;
                }
                if (data.palette) {
                    const colors = data.palette.map(color => color.replace('#', '')).join(',');
                    svgFrame.src = `/api/palette/preview.svg?colors=${encodeURIComponent(colors)}`;
                }
            } catch (error) {
                jsonResult.classList.add('error');
                jsonResult.textContent = `無法連線至 API：${error.message}`;
            } finally {
                generateButton.disabled = false;
            }
        }

        generateButton.addEventListener('click', fetchPalette);
        fetchPalette();
    </script>
</body>
</html>"""


@app.route("/api/palette/generate", methods=["GET"])
def generate_palette():
    hex_color = request.args.get("hex", "3498db")
    mode = request.args.get("mode", "analogous").lower()
    normalized_hex = hex_color.lstrip("#")

    if not re.fullmatch(r"[0-9a-fA-F]{6}", normalized_hex):
        return jsonify(
            {"error": "Invalid HEX color. Please provide a valid 6-character HEX string."}
        ), 400

    palette = generate_palette_by_mode(normalized_hex, mode)
    return jsonify(
        {
            "hex": f"#{normalized_hex.upper()}",
            "mode": mode,
            "palette": palette,
            "message": "Palette generated successfully",
        }
    )


@app.route("/api/palette/preview.svg", methods=["GET"])
def preview_svg():
    colors_param = request.args.get(
        "colors", "3498DB,2ECC71,F1C40F,E67E22,E74C3C"
    )
    raw_colors = colors_param.split(",")
    if not 1 <= len(raw_colors) <= 12:
        return jsonify({"error": "Provide between 1 and 12 HEX colors."}), 400

    colors = []
    for raw_color in raw_colors:
        color = raw_color.strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            return jsonify({"error": "Each color must be a valid 6-character HEX string."}), 400
        colors.append(f"#{color.upper()}")

    rect_width = 80
    height = 120
    width = rect_width * len(colors)
    svg_rects = "".join(
        f'<rect x="{i * rect_width}" y="0" width="{rect_width}" height="{height}" fill="{color}" />'
        f'<text x="{i * rect_width + 6}" y="{height - 15}" fill="#ffffff" '
        f'font-family="sans-serif" font-size="11" font-weight="bold">{color}</text>'
        for i, color in enumerate(colors)
    )
    svg_content = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">{svg_rects}</svg>'
    )
    return Response(svg_content, mimetype="image/svg+xml")


if __name__ == "__main__":
    app.run(debug=True)
