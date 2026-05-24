from __future__ import annotations
from typing import List
"""Excel文档渲染器"""
import logging
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.chart import BarChart, LineChart, PieChart, Reference

logger = logging.getLogger(__name__)


def render_xlsx(content: dict, output_path: Path):
    """将文档JSON渲染为Excel文件"""
    wb = Workbook()
    # 删除默认的Sheet
    default_sheet = wb.active

    sheets = content.get("sheets", [])
    if not sheets:
        # 如果没有sheets，尝试从sections构建简单表格
        sections = content.get("sections", [])
        sheets = [_sections_to_sheet(sections)]

    for idx, sheet_data in enumerate(sheets):
        if idx == 0:
            ws = default_sheet
            ws.title = sheet_data.get("name", "Sheet1")
        else:
            ws = wb.create_sheet(title=sheet_data.get("name", f"Sheet{idx+1}"))

        _render_sheet(ws, sheet_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    logger.info(f"Excel文档已生成: {output_path}")


def _render_sheet(ws, sheet_data: dict):
    """渲染单个Sheet"""
    headers = sheet_data.get("headers", [])
    rows = sheet_data.get("rows", [])
    column_widths = sheet_data.get("column_widths", [])
    chart_config = sheet_data.get("chart")

    # 样式
    header_font = Font(name='微软雅黑', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # 写表头
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # 写数据
    for row_idx, row_data in enumerate(rows, 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(vertical='center')

    # 设置列宽
    for col_idx, width in enumerate(column_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

    # 自动调整列宽（如果没有指定）
    if not column_widths:
        for col_idx, header in enumerate(headers, 1):
            max_len = len(str(header))
            for row_data in rows:
                if col_idx - 1 < len(row_data):
                    max_len = max(max_len, len(str(row_data[col_idx - 1])))
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 4, 50)

    # 渲染图表
    if chart_config:
        _render_chart(ws, chart_config, len(headers), len(rows))


def _render_chart(ws, chart_config: dict, num_cols: int, num_rows: int):
    """在Sheet中渲染图表"""
    chart_type = chart_config.get("type", "bar")
    title = chart_config.get("title", "")
    
    if chart_type == "bar":
        chart = BarChart()
    elif chart_type == "line":
        chart = LineChart()
    elif chart_type == "pie":
        chart = PieChart()
    else:
        chart = BarChart()

    chart.title = title
    chart.style = 10

    # 数据范围：假设第一列是标签，其余是数据
    data = Reference(ws, min_col=2, min_row=1, max_col=num_cols, max_row=num_rows + 1)
    cats = Reference(ws, min_col=1, min_row=2, max_row=num_rows + 1)

    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)

    ws.add_chart(chart, f"A{num_rows + 4}")


def _sections_to_sheet(sections: List[dict]) -> dict:
    """将简单sections转换为sheet格式（用于从分析结果生成Excel）"""
    # 提取所有表格
    headers = []
    rows = []
    for section in sections:
        if section.get("type") == "table":
            headers = section.get("headers", [])
            rows = section.get("rows", [])
            break

    return {
        "name": "数据",
        "headers": headers,
        "rows": rows,
    }
