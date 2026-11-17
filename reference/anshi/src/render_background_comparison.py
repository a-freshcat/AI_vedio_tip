# -*- coding: utf-8 -*-
"""背景微调与 A/B 验收脚本：生成 T040 与 T020 宏观/战术成帧、960×540 并排对照与 1:1 局部校验。"""
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import render_frame

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "output"
BASEDIR = OUTDIR / "baseline"
WIDTH, HEIGHT = 1920, 1080


def load_frame(path):
    with Image.open(path) as image:
        assert image.size == (WIDTH, HEIGHT), f"Unexpected size for {path.name}: {image.size}"
        return image.convert("RGB")


def render_and_verify(tick, macro, baseline_path, output_path):
    """以精修背景渲染指定帧，保存 QA 缩略图并核验不透明前景与 Gemini 原图逐像素一致。"""
    event = next(ev for ev in render_frame.events if ev["tick_id"] == tick)
    fig = render_frame.plt.figure(figsize=(19.2, 10.8), dpi=100, frameon=False)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    try:
        if macro:
            render_frame._draw_macro(ax, tick, event, detail_background=True)
            foreground_zorder = 10
        else:
            render_frame.draw_tactical_map(ax, event["battle_id"], detail_background=True)
            foreground_zorder = 7

        fig.savefig(output_path, dpi=100, facecolor="#123966")
        qa_path = render_frame.QADIR / output_path.name
        Image.open(output_path).resize((960, 540), Image.Resampling.LANCZOS).save(qa_path)

        # 仅保留前景图层进行 alpha 掩膜抽取，验证背景纹理零遮挡前景
        fig.patch.set_visible(False)
        ax.patch.set_visible(False)
        for artist in ax.get_children():
            if artist.get_zorder() < foreground_zorder:
                artist.set_visible(False)
        fig.canvas.draw()
        opaque = np.asarray(fig.canvas.buffer_rgba())[..., 3] == 255
        assert opaque.any() and opaque.mean() < 0.35, f"Unexpected opaque ratio {opaque.mean():.3f}"

        old = np.asarray(load_frame(baseline_path))
        new = np.asarray(load_frame(output_path))
        found = float(np.mean(np.all(old[opaque] == new[opaque], axis=-1)))
        changed = float(np.mean(np.any(old[~opaque] != new[~opaque], axis=-1)))
        print(f"[{output_path.name}] opaque foreground match={found:.3%}, background updated={changed:.1%}")
        assert found >= 0.999, f"Foreground altered on {output_path.name}: {found:.4%}"
        assert changed >= 0.50, f"Background delta unexpectedly low on {output_path.name}: {changed:.1%}"
        return found, changed
    finally:
        render_frame.plt.close(fig)


def make_comparison_sheet(rows, sheet_path, title_text):
    """生成 960×540 左右并排对比 + 下方 1:1 原尺寸三局部对照板。"""
    margin, mid_gap = 24, 16
    panel_width, panel_height = 960, 540
    crop_h = 160
    column_x = (margin, margin + panel_width + mid_gap)
    first_row = 74
    row_height = 30 + panel_height + 16 + 24 + crop_h
    row_gap = 24
    canvas = Image.new(
        "RGB",
        (column_x[1] + panel_width + margin, first_row + len(rows) * row_height + max(0, len(rows) - 1) * row_gap + margin),
        "#17212D",
    )
    draw = ImageDraw.Draw(canvas)
    bold = ImageFont.truetype(render_frame.FONT_BOLD.get_file(), 28)
    label = ImageFont.truetype(render_frame.FONT_REG.get_file(), 20)
    detail = ImageFont.truetype(render_frame.FONT_REG.get_file(), 17)

    draw.text((column_x[0], margin), f"Gemini 原图（{title_text}）", font=bold, fill="#E6EBF1", anchor="lt")
    draw.text((column_x[1], margin), f"背景精修（{title_text}）", font=bold, fill="#FFE04D", anchor="lt")

    for index, (name, file_pair, detail_crops) in enumerate(rows):
        y = first_row + index * (row_height + row_gap)
        draw.text((column_x[0], y), name, font=label, fill="#C4D0DC", anchor="lt")
        for x, path in zip(column_x, file_pair):
            frame = load_frame(path)
            canvas.paste(frame.resize((panel_width, panel_height), Image.Resampling.LANCZOS), (x, y + 30))
            n_crops = len(detail_crops)
            crop_width = (panel_width - (n_crops - 1) * mid_gap) // n_crops
            for crop_index, (caption, box) in enumerate(detail_crops):
                crop_x = x + crop_index * (crop_width + mid_gap)
                caption_y = y + 30 + panel_height + 14
                draw.text((crop_x, caption_y), caption, font=detail, fill="#C4D0DC", anchor="lt")
                # 精确 1:1 裁切（保证像素不二次缩放失真）
                x0, y0, x1, y1 = box
                cx = (x0 + x1) // 2
                cy = (y0 + y1) // 2
                bx0 = max(0, min(WIDTH - crop_width, cx - crop_width // 2))
                by0 = max(0, min(HEIGHT - crop_h, cy - crop_h // 2))
                patch = frame.crop((bx0, by0, bx0 + crop_width, by0 + crop_h))
                canvas.paste(patch, (crop_x, caption_y + 24))
    canvas.save(sheet_path, optimize=True)
    print(f"Saved comparison sheet: {sheet_path}")


def main():
    assert BASEDIR.exists(), f"Missing baseline backups in {BASEDIR}"

    t040_macro = (BASEDIR / "frame_T040_macro.png", OUTDIR / "frame_T040_macro.png")
    t040_tac = (BASEDIR / "frame_T040.png", OUTDIR / "frame_T040.png")
    t020_macro = (BASEDIR / "frame_T020_macro.png", OUTDIR / "frame_T020_macro.png")
    t020_tac = (BASEDIR / "frame_T020.png", OUTDIR / "frame_T020.png")

    render_and_verify("T040", True, *t040_macro)
    render_and_verify("T040", False, *t040_tac)
    render_and_verify("T020", True, *t020_macro)
    render_and_verify("T020", False, *t020_tac)

    make_comparison_sheet(
        [
            (
                "宏观 · T040 收复长安",
                t040_macro,
                [
                    ("秦岭坡脊与坡麓", (90, 815, 399, 975)),
                    ("太行坡脊浅沟与平原", (770, 315, 1079, 475)),
                    ("渤海近岸浅水色阶", (1460, 270, 1769, 430)),
                ],
            ),
            (
                "战术 · T040 香积寺",
                t040_tac,
                [
                    ("沣水渐变/浅滩/水纹", (35, 240, 344, 400)),
                    ("军阵下方低对比", (640, 550, 949, 710)),
                    ("东原台地坡褶与坡脚", (1430, 770, 1739, 930)),
                ],
            ),
        ],
        OUTDIR / "T040_background_comparison.png",
        "T040 香积寺",
    )

    make_comparison_sheet(
        [
            (
                "宏观 · T020 灵宝与潼关",
                t020_macro,
                [
                    ("潼关秦岭坡麓与河谷", (380, 700, 689, 860)),
                    ("太行北北东走向坡褶", (770, 315, 1079, 475)),
                    ("渤海浅水层与水纹", (1460, 270, 1769, 430)),
                ],
            ),
            (
                "战术 · T020 灵宝西原",
                t020_tac,
                [
                    ("黄河水纹与河岸浅滩", (460, 110, 769, 270)),
                    ("狭道烟火与军阵低对比", (990, 200, 1299, 360)),
                    ("南崖岩面与坡脚阴影", (840, 490, 1149, 650)),
                ],
            ),
        ],
        OUTDIR / "T020_background_comparison.png",
        "T020 灵宝西原",
    )


if __name__ == "__main__":
    main()
