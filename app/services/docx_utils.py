"""
Shared XML namespace constants and helpers for DOCX ingestion and export.
"""
from lxml import etree

# Word ML namespaces
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PNS = f"{{{W}}}p"      # <w:p> paragraph tag
TBLNS = f"{{{W}}}tbl"  # <w:tbl> table tag
TNS = f"{{{W}}}t"      # <w:t> text tag
TCNS = f"{{{W}}}tc"    # <w:tc> table cell tag
TXBX_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TXBX_CONTENT = f"{{{TXBX_NS}}}txbxContent"

# Tracked-change tags (TMX-3700)
INS_NS = f"{{{W}}}ins"             # <w:ins> insertion
DEL_NS = f"{{{W}}}del"             # <w:del> deletion
DEL_TEXT_NS = f"{{{W}}}delText"    # <w:delText> deleted text content
MOVE_FROM_NS = f"{{{W}}}moveFrom"  # <w:moveFrom>
MOVE_TO_NS = f"{{{W}}}moveTo"      # <w:moveTo>
AUTHOR_ATTR = f"{{{W}}}author"
DATE_ATTR = f"{{{W}}}date"
W_ID_ATTR = f"{{{W}}}id"  # TMX-3704-pairing: w:id correlates moveFrom/moveTo across blocks

REVISION_TAGS = (INS_NS, DEL_NS, MOVE_FROM_NS, MOVE_TO_NS)


def cell_text_excluding_nested(cell) -> str:
    """Get text from a cell's direct paragraphs only, excluding nested table text."""
    parts = []
    cell_element = cell._tc
    for child in cell_element:
        if child.tag == PNS:
            # Direct paragraph — collect its <w:t> text
            for t_node in child.iter(TNS):
                if t_node.text:
                    parts.append(t_node.text)
    return "".join(parts)


def iter_xml_text_nodes(element):
    """Yield all <w:t> nodes under an XML element."""
    for t_node in element.iter(TNS):
        yield t_node


def replace_xml_text_nodes(element, new_text: str):
    """Replace all <w:t> text under an XML element with new_text, distributed across existing nodes."""
    t_nodes = list(iter_xml_text_nodes(element))
    if not t_nodes:
        return
    if len(t_nodes) == 1:
        t_nodes[0].text = new_text
        return
    # Put all text in first node, clear the rest
    t_nodes[0].text = new_text
    for t_node in t_nodes[1:]:
        t_node.text = ""
