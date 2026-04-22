#!/usr/bin/env python3
"""Pre-processes a METS file and its referenced PAGE XML files.

Downloads all PAGE XML files referenced in the METS, adds custom=""
to any TextRegion element missing the attribute (which would otherwise
cause an XSLT type error in page2tei-0.xsl), saves the patched files
locally, and writes a modified METS whose hrefs point to those local files.

I HAVE NO CLUE WHY THIS IS NECESSARY, BUT IT SEEMS TO BE: Transkribus exports some PAGE XML files with TextRegion elements that lack 
the required @custom attribute, and this causes the XSLT transformation to fail.

Usage:
    python patch_page_xml.py <mets_file> <output_dir>
"""

import sys
import os
import requests
from lxml import etree

PAGEXML_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
PAGEXML_NS2 = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
METS_NS = "http://www.loc.gov/METS/"
XLINK_NS = "http://www.w3.org/1999/xlink"


def patch_page_xml(content):
    """Add custom="" to TextRegion elements missing the attribute."""
    tree = etree.fromstring(content)
    patched = 0
    for ns in [PAGEXML_NS, PAGEXML_NS2]:
        for region in tree.iter(f"{{{ns}}}TextRegion"):
            if "custom" not in region.attrib:
                region.set("custom", "")
                patched += 1
    return etree.tostring(tree, xml_declaration=True, encoding="UTF-8"), patched


def process_mets(mets_path, output_dir):
    tree = etree.parse(mets_path)
    root = tree.getroot()

    for flocat in root.findall(f".//{{{METS_NS}}}FLocat[@LOCTYPE='URL']"):
        href = flocat.get(f"{{{XLINK_NS}}}href")
        if not href:
            continue
        parent = flocat.getparent()
        if parent.get("MIMETYPE") != "application/xml":
            continue

        print(f"  fetching {href}", file=sys.stderr)
        resp = requests.get(href, timeout=60)
        resp.raise_for_status()

        patched_content, n = patch_page_xml(resp.content)
        if n:
            print(f"    -> patched {n} TextRegion(s) missing @custom", file=sys.stderr)

        local_name = f"{parent.get('ID', 'page')}.xml"
        local_path = os.path.join(output_dir, local_name)
        with open(local_path, "wb") as f:
            f.write(patched_content)

        flocat.set(f"{{{XLINK_NS}}}href", f"file://{os.path.abspath(local_path)}")

    output_mets = os.path.join(output_dir, os.path.basename(mets_path))
    tree.write(output_mets, xml_declaration=True, encoding="UTF-8")
    return output_mets


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <mets_file> <output_dir>", file=sys.stderr)
        sys.exit(1)

    mets_path = sys.argv[1]
    output_dir = sys.argv[2]
    os.makedirs(output_dir, exist_ok=True)

    print(process_mets(mets_path, output_dir))
