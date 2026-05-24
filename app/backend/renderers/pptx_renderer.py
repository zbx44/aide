from __future__ import annotations
from typing import List
"""PPT文档渲染器"""
import logging
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

logger = logging.getLogger(__name__)

# 主题色
THEME_COLORS = {
    "primary": RGBColor(0x1A, 0x56, 0xDB),     # 主色蓝
    "dark": RGBColor(0x2D, 0x3A, 0x4A),         # 深色
    "light_bg": RGBColor(0xF5, 0xF7, 0xFA),     # 浅背景
    "accent": RGBColor(0xE8, 0x6C, 0x00),       # 强调色橙
    "white": RGBColor(0xFF, 0xFF, 0xFF),
    "gray": RGBColor(0x66, 0x66, 0x66),
}


def render_pptx(content: dict, output_path: Path):
    """将文档JSON渲染为PPT文件"""
    prs = Presentation()
    # 16:9比例
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    title = content.get("title", "未命名演示")
    slides = content.get("slides", [])

    if not slides:
        # 从sections构建默认幻灯片
        from core.template_engine import _sections_to_slides
        slides = _sections_to_slides(content.get("sections", []), title)

    for slide_data in slides:
        layout_type = slide_data.get("layout", "content")

        if layout_type == "title":
            _render_title_slide(prs, slide_data)
        elif layout_type == "content":
            _render_content_slide(prs, slide_data)
        elif layout_type == "chart":
            _render_chart_slide(prs, slide_data, output_path)
        else:
            _render_content_slide(prs, slide_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    logger.info(f"PPT文档已生成: {output_path}, 共{len(prs.slides)}页")


def _render_title_slide(prs: Presentation, data: dict):
    """渲染封面页"""
    slide_layout = prs.slide_layouts[5]  # 空白版式
    slide = prs.slides.add_slide(slide_layout)

    # 背景色
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = THEME_COLORS["primary"]

    # 标题
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(2))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = data.get("title", "")
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = THEME_COLORS["white"]
    p.alignment = PP_ALIGN.CENTER

    # 副标题
    subtitle = data.get("subtitle", "")
    if subtitle:
        txBox2 = slide.shapes.add_textbox(Inches(1), Inches(4.8), Inches(11), Inches(1))
        tf2 = txBox2.text_frame
        tf2.word_wrap = True
        p2 = tf2.paragraphs[0]
        p2.text = subtitle
        p2.font.size = Pt(24)
        p2.font.color.rgb = RGBColor(0xCC, 0xD5, 0xE8)
        p2.alignment = PP_ALIGN.CENTER

    # 底部装饰线
    line = slide.shapes.add_shape(
        1, Inches(3), Inches(4.5), Inches(7), Inches(0.04)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = THEME_COLORS["accent"]
    line.line.fill.background()


def _render_content_slide(prs: Presentation, data: dict):
    """渲染内容页"""
    slide_layout = prs.slide_layouts[5]  # 空白版式，完全自定义
    slide = prs.slides.add_slide(slide_layout)

    # 背景
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = THEME_COLORS["white"]

    # 左侧装饰条
    shape = slide.shapes.add_shape(
        1,  # 矩形
        Inches(0), Inches(0),
        Inches(0.25), Inches(7.5)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = THEME_COLORS["primary"]
    shape.line.fill.background()

    # 标题
    txBox = slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12), Inches(1))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = data.get("title", "")
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = THEME_COLORS["dark"]

    # 内容区
    body_items = data.get("body", [])
    if not body_items:
        # 兼容处理：如果body为空，尝试从text/content字段提取
        raw_text = data.get("text", "") or data.get("content", "")
        if raw_text:
            body_items = [{"type": "text", "content": raw_text}]

    if body_items:
        txBox2 = slide.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(12), Inches(5.5))
        tf2 = txBox2.text_frame
        tf2.word_wrap = True
        first_item = True

        for item in body_items:
            if item.get("type") == "bullet":
                for bullet_text in item.get("items", []):
                    if first_item:
                        p = tf2.paragraphs[0]
                        first_item = False
                    else:
                        p = tf2.add_paragraph()
                    p.text = f"• {bullet_text}"
                    p.font.size = Pt(18)
                    p.font.color.rgb = THEME_COLORS["dark"]
                    p.space_after = Pt(8)
                    p.level = 0
            elif item.get("type") == "text":
                text_content = item.get("content", "") or item.get("text", "")
                if text_content:
                    if first_item:
                        p = tf2.paragraphs[0]
                        first_item = False
                    else:
                        p = tf2.add_paragraph()
                    p.text = text_content
                    p.font.size = Pt(18)
                    p.font.color.rgb = THEME_COLORS["gray"]
                    p.space_after = Pt(8)
            else:
                # 兜底：直接按字符串输出
                text = str(item) if not isinstance(item, str) else item
                if text and text != "None":
                    if first_item:
                        p = tf2.paragraphs[0]
                        first_item = False
                    else:
                        p = tf2.add_paragraph()
                    p.text = text[:300]
                    p.font.size = Pt(16)
                    p.font.color.rgb = THEME_COLORS["gray"]

    # 底部装饰线
    line = slide.shapes.add_shape(
        1, Inches(0.6), Inches(7.1), Inches(12), Inches(0.03)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = THEME_COLORS["primary"]
    line.line.fill.background()


def _render_chart_slide(prs: Presentation, data: dict, doc_path: Path):
    """渲染图表页"""
    slide_layout = prs.slide_layouts[5]  # 空白版式
    slide = prs.slides.add_slide(slide_layout)

    # 添加标题
    from pptx.util import Inches, Pt
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = data.get("title", "")
    p.font.size = Pt(32)
    p.font.bold = True

    # 渲染图表为图片并嵌入
    chart_config = data.get("chart", {})
    chart_data = chart_config.get("data", {})
    chart_type = chart_config.get("chart_type", "bar")
    chart_title = chart_config.get("title", data.get("title", ""))

    try:
        from renderers.docx_renderer import _render_chart_image
        img_path = _render_chart_image(chart_data, chart_title, chart_type, doc_path)
        if img_path:
            slide.shapes.add_picture(
                str(img_path),
                Inches(1.5), Inches(1.5),
                Inches(10), Inches(5.5)
            )
    except Exception as e:
        logger.error(f"PPT图表渲染失败: {e}")
        txBox2 = slide.shapes.add_textbox(Inches(2), Inches(3), Inches(9), Inches(2))
        tf2 = txBox2.text_frame
        tf2.text = f"[图表渲染失败: {e}]"



