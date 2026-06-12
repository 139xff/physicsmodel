"""Convert a simple standalone HTML report into a Word .docx document.

This converter is intentionally dependency-free. It handles the subset used by
the project task reports: headings, paragraphs, lists, tables, code blocks, and
plain inline text. It writes Office Open XML directly into a .docx zip archive.
"""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import html
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

BlockKind = Literal[
    "title",
    "subtitle",
    "h2",
    "h3",
    "paragraph",
    "bullet",
    "number",
    "code",
    "table",
]


@dataclass
class Block:
    kind: BlockKind
    text: str = ""
    rows: list[list[str]] = field(default_factory=list)
    header_rows: set[int] = field(default_factory=set)


class ReportHtmlParser(HTMLParser):
    """Extract block-level report content from the generated HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._ignored_depth = 0
        self._capture_kind: str | None = None
        self._capture_end_tag: str | None = None
        self._capture_attrs: dict[str, str] = {}
        self._capture_parts: list[str] = []
        self._list_stack: list[str] = []
        self._table_rows: list[list[str]] | None = None
        self._table_header_rows: set[int] = set()
        self._current_row: list[str] | None = None
        self._current_cell_parts: list[str] | None = None
        self._current_cell_is_header = False
        self._current_row_has_header = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name: value or "" for name, value in attrs}
        if tag in {"style", "script", "svg"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return

        if tag in {"ul", "ol"}:
            self._list_stack.append(tag)
            return

        if tag == "table":
            self._table_rows = []
            self._table_header_rows = set()
            return

        if self._table_rows is not None:
            if tag == "tr":
                self._current_row = []
                self._current_row_has_header = False
            elif tag in {"th", "td"}:
                self._current_cell_parts = []
                self._current_cell_is_header = tag == "th"
            elif tag == "br" and self._current_cell_parts is not None:
                self._current_cell_parts.append("\n")
            return

        if tag in {"h1", "h2", "h3", "p", "li", "pre"}:
            self._capture_kind = tag
            self._capture_end_tag = tag
            self._capture_attrs = attrs_dict
            self._capture_parts = []
        elif tag == "div":
            classes = set(attrs_dict.get("class", "").split())
            if classes.intersection({"formula", "scope-note"}) and self._capture_kind is None:
                self._capture_kind = "pre" if "formula" in classes else "p"
                self._capture_end_tag = "div"
                self._capture_attrs = attrs_dict
                self._capture_parts = []
        elif tag == "br" and self._capture_kind is not None:
            self._capture_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return

        if tag in {"ul", "ol"}:
            if self._list_stack:
                self._list_stack.pop()
            return

        if self._table_rows is not None:
            if tag in {"th", "td"} and self._current_cell_parts is not None:
                cell_text = _normalize_text("".join(self._current_cell_parts))
                if self._current_row is not None:
                    self._current_row.append(cell_text)
                    if self._current_cell_is_header:
                        self._current_row_has_header = True
                self._current_cell_parts = None
                self._current_cell_is_header = False
            elif tag == "tr" and self._current_row is not None:
                if self._current_row:
                    row_index = len(self._table_rows)
                    self._table_rows.append(self._current_row)
                    if self._current_row_has_header:
                        self._table_header_rows.add(row_index)
                self._current_row = None
                self._current_row_has_header = False
            elif tag == "table":
                if self._table_rows:
                    self.blocks.append(
                        Block(
                            kind="table",
                            rows=self._table_rows,
                            header_rows=set(self._table_header_rows),
                        )
                    )
                self._table_rows = None
                self._table_header_rows = set()
            return

        if tag != self._capture_end_tag:
            return

        raw_text = "".join(self._capture_parts)
        captured_kind = self._capture_kind
        text = raw_text.rstrip("\n") if captured_kind == "pre" else _normalize_text(raw_text)
        if text:
            if captured_kind == "h1":
                kind: BlockKind = "title"
            elif captured_kind == "h2":
                kind = "h2"
            elif captured_kind == "h3":
                kind = "h3"
            elif captured_kind == "li":
                kind = "number" if self._list_stack and self._list_stack[-1] == "ol" else "bullet"
            elif captured_kind == "pre":
                kind = "code"
            elif "subtitle" in self._capture_attrs.get("class", ""):
                kind = "subtitle"
            else:
                kind = "paragraph"
            self.blocks.append(Block(kind=kind, text=text))

        self._capture_kind = None
        self._capture_end_tag = None
        self._capture_attrs = {}
        self._capture_parts = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._current_cell_parts is not None:
            self._current_cell_parts.append(data)
        elif self._capture_kind is not None:
            self._capture_parts.append(data)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _xml_text(value: str, *, preserve: bool = False) -> str:
    escaped = html.escape(value, quote=False)
    if preserve or value[:1].isspace() or value[-1:].isspace():
        return f'<w:t xml:space="preserve">{escaped}</w:t>'
    return f"<w:t>{escaped}</w:t>"


def _run(text: str, *, bold: bool = False, code: bool = False, size: int | None = None) -> str:
    props: list[str] = []
    if bold:
        props.append("<w:b/>")
    if code:
        props.append('<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:eastAsia="Courier New"/>')
    else:
        props.append('<w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/>')
    if size is not None:
        props.append(f'<w:sz w:val="{size}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f"<w:r>{rpr}{_xml_text(text, preserve=code)}</w:r>"


def _paragraph(
    text: str,
    *,
    style: str | None = None,
    numbering: tuple[int, int] | None = None,
    bold: bool = False,
    code: bool = False,
    align: str | None = None,
    spacing_after: int = 160,
) -> str:
    ppr: list[str] = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if numbering:
        ilvl, num_id = numbering
        ppr.append(
            "<w:numPr>"
            f'<w:ilvl w:val="{ilvl}"/>'
            f'<w:numId w:val="{num_id}"/>'
            "</w:numPr>"
        )
    ppr.append(f'<w:spacing w:after="{spacing_after}" w:line="360" w:lineRule="auto"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>"
    return f"<w:p>{ppr_xml}{_run(text, bold=bold, code=code)}</w:p>"


def _code_block(text: str) -> str:
    paragraphs = []
    for line in text.splitlines() or [""]:
        paragraphs.append(_paragraph(line, style="CodeBlock", code=True, spacing_after=0))
    return "".join(paragraphs)


def _table(rows: list[list[str]], header_rows: set[int]) -> str:
    if not rows:
        return ""
    column_count = max(len(row) for row in rows)
    total_width = 9026
    base_width = total_width // column_count
    widths = [base_width] * column_count
    widths[-1] += total_width - sum(widths)
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    tr_xml: list[str] = []
    for row_index, row in enumerate(rows):
        is_header = row_index in header_rows
        cells: list[str] = []
        for column_index in range(column_count):
            text = row[column_index] if column_index < len(row) else ""
            shading = '<w:shd w:fill="E8EEFC" w:val="clear"/>' if is_header else ""
            tc_pr = (
                "<w:tcPr>"
                f'<w:tcW w:w="{widths[column_index]}" w:type="dxa"/>'
                f"{shading}"
                '<w:tcMar><w:top w:w="90" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
                '<w:bottom w:w="90" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>'
                "</w:tcPr>"
            )
            cells.append(
                f"<w:tc>{tc_pr}"
                f"{_paragraph(text, style='TableText', bold=is_header, spacing_after=0)}"
                "</w:tc>"
            )
        tr_xml.append(f"<w:tr>{''.join(cells)}</w:tr>")
    return (
        "<w:tbl>"
        "<w:tblPr>"
        '<w:tblStyle w:val="TableGrid"/>'
        f'<w:tblW w:w="{total_width}" w:type="dxa"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="D9DEEA"/>'
        '<w:left w:val="single" w:sz="4" w:color="D9DEEA"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="D9DEEA"/>'
        '<w:right w:val="single" w:sz="4" w:color="D9DEEA"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="D9DEEA"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="D9DEEA"/></w:tblBorders>'
        "</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"{''.join(tr_xml)}"
        "</w:tbl>"
    )


def _document_xml(blocks: list[Block]) -> str:
    body_parts: list[str] = []
    for block in blocks:
        if block.kind == "title":
            body_parts.append(_paragraph(block.text, style="Title", align="center", spacing_after=220))
        elif block.kind == "subtitle":
            body_parts.append(_paragraph(block.text, style="Subtitle", align="center", spacing_after=260))
        elif block.kind == "h2":
            body_parts.append(_paragraph(block.text, style="Heading1"))
        elif block.kind == "h3":
            body_parts.append(_paragraph(block.text, style="Heading2"))
        elif block.kind == "bullet":
            body_parts.append(_paragraph(block.text, numbering=(0, 1)))
        elif block.kind == "number":
            body_parts.append(_paragraph(block.text, numbering=(0, 2)))
        elif block.kind == "code":
            body_parts.append(_code_block(block.text))
        elif block.kind == "table":
            body_parts.append(_table(block.rows, block.header_rows))
        else:
            body_parts.append(_paragraph(block.text))

    sect_pr = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{''.join(body_parts)}{sect_pr}</w:body>"
        "</w:document>"
    )


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/>
      <w:sz w:val="22"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/>
      <w:b/>
      <w:sz w:val="34"/>
      <w:color w:val="0F172A"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/>
      <w:sz w:val="22"/>
      <w:color w:val="5D667A"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="Heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="300" w:after="180"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/>
      <w:b/>
      <w:sz w:val="28"/>
      <w:color w:val="102047"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="Heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="220" w:after="140"/><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/>
      <w:b/>
      <w:sz w:val="24"/>
      <w:color w:val="22315D"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="CodeBlock">
    <w:name w:val="Code Block"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="60" w:after="0"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:eastAsia="Courier New"/>
      <w:sz w:val="18"/>
      <w:color w:val="1E3A8A"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="TableText">
    <w:name w:val="Table Text"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr>
      <w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/>
      <w:sz w:val="19"/>
    </w:rPr>
  </w:style>
  <w:style w:type="table" w:styleId="TableGrid">
    <w:name w:val="Table Grid"/>
    <w:tblPr>
      <w:tblBorders>
        <w:top w:val="single" w:sz="4" w:color="D9DEEA"/>
        <w:left w:val="single" w:sz="4" w:color="D9DEEA"/>
        <w:bottom w:val="single" w:sz="4" w:color="D9DEEA"/>
        <w:right w:val="single" w:sz="4" w:color="D9DEEA"/>
        <w:insideH w:val="single" w:sz="4" w:color="D9DEEA"/>
        <w:insideV w:val="single" w:sz="4" w:color="D9DEEA"/>
      </w:tblBorders>
    </w:tblPr>
  </w:style>
</w:styles>
"""


def _numbering_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="•"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="480" w:hanging="240"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="1">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="600" w:hanging="300"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>
"""


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def _root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def _document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>
"""


def _core_xml(title: str) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    escaped_title = html.escape(title, quote=False)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escaped_title}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>
"""


def _app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>EM Workbench</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <Company></Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0000</AppVersion>
</Properties>
"""


def convert_html_to_docx(html_path: Path, docx_path: Path) -> None:
    parser = ReportHtmlParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    if not parser.blocks:
        raise ValueError(f"No report content found in {html_path}.")

    title = next((block.text for block in parser.blocks if block.kind == "title"), html_path.stem)
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(docx_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("docProps/core.xml", _core_xml(title))
        archive.writestr("docProps/app.xml", _app_xml())
        archive.writestr("word/_rels/document.xml.rels", _document_rels_xml())
        archive.writestr("word/document.xml", _document_xml(parser.blocks))
        archive.writestr("word/styles.xml", _styles_xml())
        archive.writestr("word/numbering.xml", _numbering_xml())


def main() -> None:
    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument("html_path", type=Path)
    arg_parser.add_argument("docx_path", type=Path)
    args = arg_parser.parse_args()
    convert_html_to_docx(args.html_path, args.docx_path)
    print(f"Wrote {args.docx_path}")


if __name__ == "__main__":
    main()
