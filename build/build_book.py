"""Build the public reading PDF and EPUB 3 from the authoritative Markdown."""

from __future__ import annotations

import html
import re
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "manuscript" / "zh-CN"
PDF_OUT = ROOT / "editions" / "pdf" / "queyanlun-v0.8.0-zh-reading.pdf"
EPUB_OUT = ROOT / "editions" / "epub" / "queyanlun-v0.8.0-zh.epub"
FONT_REGULAR = Path(r"C:\Windows\Fonts\STKAITI.TTF")
FONT_BOLD = Path(r"C:\Windows\Fonts\simkai.ttf")

BOOK_TITLE = "缺演论"
BOOK_SUBTITLE = "缺口、创造与文明演化"
AUTHOR = "朱泫榛"
VERSION = "0.8.0"
LICENSE = "CC BY-NC-ND 4.0"

FILES = [
    "00-prologue.md",
    "01-two-worlds.md",
    "02-gap-not-void.md",
    "03-asymmetric-expansion.md",
    "04-dual-structure-law.md",
    "05-asymmetric-expansion-law.md",
    "06-gap-response-law.md",
    "07-generational-transition-law.md",
    "08-gap-and-room-law.md",
    "09-gap-sensitivity.md",
    "10-from-sensor-to-builder.md",
    "11-paradox-of-fulfillment.md",
    "12-civilization-as-gap-history.md",
    "13-religion-science-art.md",
    "14-when-machines-fill-gaps.md",
    "15-epilogue.md",
]


def inline_markup(text: str, *, epub: bool = False) -> str:
    value = html.escape(text.strip(), quote=False)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", value)
    value = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2">\1</a>',
        value,
    )
    if epub:
        value = re.sub(r"\[\^([^\]]+)\]", r'<sup><a href="#fn-\1">\1</a></sup>', value)
    else:
        value = re.sub(r"\[\^([^\]]+)\]", r"<super>[\1]</super>", value)
    return value


def parse_blocks(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks = []
    paragraph = []

    def flush():
        if paragraph:
            blocks.append(("p", " ".join(x.strip() for x in paragraph)))
            paragraph.clear()

    for line in lines:
        if not line.strip():
            flush()
            continue
        foot = re.match(r"^\[\^([^\]]+)\]:\s*(.*)$", line)
        if foot:
            flush()
            blocks.append(("footnote", foot.group(1), foot.group(2)))
        elif line.startswith("### "):
            flush()
            blocks.append(("h3", line[4:].strip()))
        elif line.startswith("## "):
            flush()
            blocks.append(("h2", line[3:].strip()))
        elif line.startswith("# "):
            flush()
            blocks.append(("h1", line[2:].strip()))
        elif line.startswith("> "):
            flush()
            blocks.append(("quote", line[2:].strip()))
        elif re.match(r"^[-*] ", line):
            flush()
            blocks.append(("li", re.sub(r"^[-*] ", "", line)))
        elif re.match(r"^\d+\. ", line):
            flush()
            blocks.append(("li", re.sub(r"^\d+\. ", "", line)))
        else:
            paragraph.append(line)
    flush()
    return blocks


class BookDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._bookmark_id = 0

    def beforeDocument(self):
        # multiBuild performs several layout passes. Heading bookmark IDs must
        # repeat identically on every pass or the table of contents never
        # converges.
        self._bookmark_id = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            if style_name in {"ChapterTitle", "SectionTitle"}:
                level = 0 if style_name == "ChapterTitle" else 1
                text = flowable.getPlainText()
                key = f"heading-{self._bookmark_id}"
                self._bookmark_id += 1
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
                self.notify("TOCEntry", (level, text, self.page, key))


def draw_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#9B9894"))
    canvas.setFont("KaiSC", 7.2)
    if doc.page > 3:
        canvas.drawCentredString(72.5 * mm, 9.2 * mm, str(doc.page - 3))
    canvas.restoreState()


def build_pdf():
    PDF_OUT.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("KaiSC", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("KaiSCAlt", str(FONT_BOLD)))

    page_size = (145 * mm, 210 * mm)
    doc = BookDocTemplate(
        str(PDF_OUT),
        pagesize=page_size,
        leftMargin=23 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"{BOOK_TITLE}：{BOOK_SUBTITLE}",
        author=AUTHOR,
        subject="开放哲学著作阅读版",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="book", frames=[frame], onPage=draw_page)])

    body = ParagraphStyle(
        "Body",
        fontName="KaiSC",
        fontSize=11.2,
        leading=20.5,
        alignment=TA_JUSTIFY,
        firstLineIndent=22.4,
        spaceAfter=3,
        textColor=colors.HexColor("#252321"),
        wordWrap="CJK",
    )
    chapter = ParagraphStyle(
        "ChapterTitle",
        fontName="KaiSCAlt",
        fontSize=22,
        leading=31,
        alignment=TA_CENTER,
        spaceBefore=10 * mm,
        spaceAfter=34 * mm,
        textColor=colors.HexColor("#1E1D1B"),
        wordWrap="CJK",
    )
    section = ParagraphStyle(
        "SectionTitle",
        fontName="KaiSCAlt",
        fontSize=14.2,
        leading=22,
        spaceBefore=18,
        spaceAfter=9,
        textColor=colors.HexColor("#242220"),
        wordWrap="CJK",
    )
    subsection = ParagraphStyle(
        "Subsection",
        fontName="KaiSCAlt",
        fontSize=12.2,
        leading=19,
        spaceBefore=9,
        spaceAfter=5,
        wordWrap="CJK",
    )
    quote = ParagraphStyle(
        "Quote",
        parent=body,
        fontSize=10.5,
        leading=19,
        leftIndent=10 * mm,
        rightIndent=5 * mm,
        firstLineIndent=0,
        borderColor=colors.HexColor("#B9B2AA"),
        borderWidth=0,
        borderPadding=(4, 0, 4, 8),
        textColor=colors.HexColor("#504C47"),
    )
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=7 * mm, firstLineIndent=-4 * mm)
    footnote = ParagraphStyle(
        "Footnote",
        parent=body,
        fontSize=8.4,
        leading=13.5,
        firstLineIndent=0,
        textColor=colors.HexColor("#5F5A55"),
    )

    story = []
    title_style = ParagraphStyle(
        "Title",
        fontName="KaiSCAlt",
        fontSize=34,
        leading=44,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#25211E"),
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontName="KaiSC",
        fontSize=15,
        leading=25,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#55514C"),
    )
    meta_style = ParagraphStyle(
        "Meta",
        fontName="KaiSC",
        fontSize=10,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#6F6963"),
    )
    story += [
        Spacer(1, 40 * mm),
        Paragraph(BOOK_TITLE, title_style),
        Spacer(1, 5 * mm),
        Paragraph(BOOK_SUBTITLE, subtitle_style),
        Spacer(1, 36 * mm),
        Paragraph(AUTHOR, meta_style),
        Spacer(1, 5 * mm),
        Paragraph(f"开放阅读版 · v{VERSION}<br/>{LICENSE}", meta_style),
        PageBreak(),
        Spacer(1, 23 * mm),
        Paragraph("目录", title_style),
        Spacer(1, 10 * mm),
    ]
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOC1", fontName="KaiSC", fontSize=11, leading=20, leftIndent=0, firstLineIndent=0, textColor=colors.HexColor("#292724")),
        ParagraphStyle("TOC2", fontName="KaiSC", fontSize=9.2, leading=16, leftIndent=7 * mm, firstLineIndent=0, textColor=colors.HexColor("#77716A")),
    ]
    story += [toc, PageBreak()]

    for index, filename in enumerate(FILES):
        if index:
            story.append(PageBreak())
        for block in parse_blocks(SOURCE_DIR / filename):
            kind = block[0]
            if kind == "h1":
                story.append(Paragraph(inline_markup(block[1]), chapter))
            elif kind == "h2":
                story.append(Paragraph(inline_markup(block[1]), section))
            elif kind == "h3":
                story.append(Paragraph(inline_markup(block[1]), subsection))
            elif kind == "quote":
                story.append(Paragraph(inline_markup(block[1]), quote))
            elif kind == "li":
                story.append(Paragraph("• " + inline_markup(block[1]), bullet))
            elif kind == "footnote":
                story.append(Paragraph(f"[{block[1]}] {inline_markup(block[2])}", footnote))
            else:
                story.append(Paragraph(inline_markup(block[1]), body))

    story += [
        PageBreak(),
        Spacer(1, 35 * mm),
        Paragraph("版权与版本", chapter),
        Paragraph(
            f"© 2026 {AUTHOR}。正文以 {LICENSE} 许可发布。允许署名、非商业地复制和传播未经改动的完整作品。翻译、改写、节选重组和商业使用需要另行授权。",
            body,
        ),
        Paragraph("权威版本：https://github.com/huliye24/queyanlun", body),
    ]
    doc.multiBuild(story)


def blocks_to_xhtml(blocks):
    parts = []
    footnotes = []
    list_open = False
    for block in blocks:
        kind = block[0]
        if kind != "li" and list_open:
            parts.append("</ul>")
            list_open = False
        if kind == "h1":
            parts.append(f"<h1>{inline_markup(block[1], epub=True)}</h1>")
        elif kind == "h2":
            parts.append(f"<h2>{inline_markup(block[1], epub=True)}</h2>")
        elif kind == "h3":
            parts.append(f"<h3>{inline_markup(block[1], epub=True)}</h3>")
        elif kind == "quote":
            parts.append(f"<blockquote>{inline_markup(block[1], epub=True)}</blockquote>")
        elif kind == "li":
            if not list_open:
                parts.append("<ul>")
                list_open = True
            parts.append(f"<li>{inline_markup(block[1], epub=True)}</li>")
        elif kind == "footnote":
            footnotes.append(
                f'<aside class="footnote" id="fn-{html.escape(block[1])}"><sup>{html.escape(block[1])}</sup> {inline_markup(block[2], epub=True)}</aside>'
            )
        else:
            parts.append(f"<p>{inline_markup(block[1], epub=True)}</p>")
    if list_open:
        parts.append("</ul>")
    if footnotes:
        parts.append('<section class="footnotes"><h2>本章注释</h2>')
        parts.extend(footnotes)
        parts.append("</section>")
    return "\n".join(parts)


def xhtml_doc(title: str, body: str) -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN" xml:lang="zh-CN">
<head><meta charset="utf-8"/><title>{html.escape(title)}</title><link rel="stylesheet" href="styles.css"/></head>
<body>{body}</body></html>'''


def build_epub():
    EPUB_OUT.parent.mkdir(parents=True, exist_ok=True)
    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'https://github.com/huliye24/queyanlun/v0.8.0')}"
    chapters = []
    for i, filename in enumerate(FILES):
        blocks = parse_blocks(SOURCE_DIR / filename)
        title = next(b[1] for b in blocks if b[0] == "h1")
        href = f"chapter-{i:02d}.xhtml"
        chapters.append((f"ch{i:02d}", href, title, xhtml_doc(title, blocks_to_xhtml(blocks))))

    css = """
body { font-family: "STKaiti", "KaiTi", "Kaiti SC", "楷体", serif; font-size: 1em; line-height: 1.95; color: #252321; margin: 7%; }
h1 { font-weight: normal; text-align: center; font-size: 1.9em; line-height: 1.45; margin: 12vh 0 16vh; }
h2 { font-weight: normal; font-size: 1.35em; color: #242220; margin: 2.2em 0 .8em; }
h3 { font-weight: normal; font-size: 1.12em; margin: 1.7em 0 .6em; }
p { text-indent: 2em; text-align: justify; margin: .18em 0; orphans: 2; widows: 2; }
blockquote { border-left: .12em solid #b9b2aa; color: #504c47; margin: 1.4em 1.2em; padding: .35em 1.1em; }
li { margin: .35em 0; }
a { color: #4c4945; }
.title-page { text-align: center; padding-top: 20vh; }
.title-page h1 { font-size: 2.8em; margin: 0 0 .5em; }
.subtitle { color: #55514c; font-size: 1.25em; text-indent: 0; }
.meta { margin-top: 5em; color: #6f6963; }
.footnotes { border-top: 1px solid #bbb; margin-top: 2em; font-size: .82em; }
.footnote { display: block; margin: .5em 0; }
""".strip()

    title_page = xhtml_doc(
        BOOK_TITLE,
        f'<section class="title-page" epub:type="titlepage"><h1>{BOOK_TITLE}</h1><p class="subtitle">{BOOK_SUBTITLE}</p><p class="meta">{AUTHOR}<br/>开放阅读版 · v{VERSION}<br/>{LICENSE}</p></section>',
    )
    nav_items = "".join(f'<li><a href="{href}">{html.escape(title)}</a></li>' for _, href, title, _ in chapters)
    nav = xhtml_doc("目录", f'<nav epub:type="toc" id="toc"><h1>目录</h1><ol>{nav_items}</ol></nav>')
    manifest = [
        '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="styles.css" media-type="text/css"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
    ] + [f'<item id="{cid}" href="{href}" media-type="application/xhtml+xml"/>' for cid, href, _, _ in chapters]
    spine = '<itemref idref="title"/>' + "".join(f'<itemref idref="{cid}"/>' for cid, _, _, _ in chapters)
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0" xml:lang="zh-CN">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{book_id}</dc:identifier><dc:title>{BOOK_TITLE}：{BOOK_SUBTITLE}</dc:title>
<dc:creator>{AUTHOR}</dc:creator><dc:language>zh-CN</dc:language><dc:rights>{LICENSE}</dc:rights>
<meta property="dcterms:modified">2026-09-16T00:00:00Z</meta>
</metadata><manifest>{''.join(manifest)}</manifest><spine toc="ncx">{spine}</spine></package>'''
    navpoints = "".join(
        f'<navPoint id="np{i}" playOrder="{i+1}"><navLabel><text>{escape(title)}</text></navLabel><content src="{href}"/></navPoint>'
        for i, (_, href, title, _) in enumerate(chapters)
    )
    ncx = f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head><meta name="dtb:uid" content="{book_id}"/></head>
<docTitle><text>{BOOK_TITLE}</text></docTitle><navMap>{navpoints}</navMap></ncx>'''
    container = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'''

    with zipfile.ZipFile(EPUB_OUT, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/styles.css", css)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/toc.ncx", ncx)
        zf.writestr("OEBPS/title.xhtml", title_page)
        zf.writestr("OEBPS/nav.xhtml", nav)
        for _, href, _, content in chapters:
            zf.writestr(f"OEBPS/{href}", content)


if __name__ == "__main__":
    missing = [str(SOURCE_DIR / f) for f in FILES if not (SOURCE_DIR / f).exists()]
    if missing:
        raise SystemExit("Missing source files:\n" + "\n".join(missing))
    build_pdf()
    build_epub()
    print(PDF_OUT)
    print(EPUB_OUT)
