import copy
import csv
import datetime
import json
import os
import re

import jinja2
import lxml.etree as ET
import requests
from acdh_tei_pyutils.tei import TeiReader


TEI_DIR = "./editions_source"
TMP_DIR = "./mets/"
MALFORMED_FILES_LOGPATH = "./logs/malformed_files.csv"
TEMPLATE_PATH = "./scripts/templates"
doc_base_row_dump_url = "https://raw.githubusercontent.com/bundesverfassung-oesterreich/bv-entities/main/json_dumps/document.json"
project_base_row_dump_url = "https://raw.githubusercontent.com/bundesverfassung-oesterreich/bv-entities/main/json_dumps/project_data.json"
doc_local_baserow_dump = TMP_DIR + "document.json"
project_local_baserow_dump = TMP_DIR + "project_data.json"
PROJECT_MD = {}
malformed_xml_docs = []

tei_ns = "http://www.tei-c.org/ns/1.0"
xml_ns = "http://www.w3.org/XML/1998/namespace"
nsmap = {"tei": tei_ns}
IIIF_REQUEST_TIMEOUT = 30
REQUESTS_SESSION = requests.Session()


templateLoader = jinja2.FileSystemLoader(searchpath=TEMPLATE_PATH)
templateEnv = jinja2.Environment(
    loader=templateLoader, trim_blocks=True, lstrip_blocks=True
)
template = templateEnv.get_template("tei_template.j2")


def tei_qname(local_name):
    return f"{{{tei_ns}}}{local_name}"


def sanitize_log_field(value):
    """Make a log value safe for the CSV and the way the workflow parses it."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    # the workflow reads the csv with `cut -d','`, so commas must not sneak in
    text = text.replace(",", ";")
    return re.sub(r"\s+", " ", text).strip()


def record_malformed(file_name, error):
    malformed_xml_docs.append(
        {
            "file_name": sanitize_log_field(file_name),
            "error": sanitize_log_field(error),
        }
    )


def get_xml_doc(xml_file):
    try:
        return TeiReader(xml_file)
    except Exception as exception:
        record_malformed(xml_file[:200], exception)
        return None


def log_nonvalid_files():
    if not malformed_xml_docs:
        print("no malformed files")
        return

    print("Some or all files where malformed!".upper())
    fieldnames = ["file_name", "error"]
    log_directory, _ = os.path.split(MALFORMED_FILES_LOGPATH)
    if log_directory and not os.path.exists(log_directory):
        os.makedirs(log_directory)
    log_exists = os.path.isfile(MALFORMED_FILES_LOGPATH) and os.path.getsize(
        MALFORMED_FILES_LOGPATH
    ) > 0
    with open(MALFORMED_FILES_LOGPATH, "a", newline="", encoding="utf-8") as outfile:
        dict_writer = csv.DictWriter(outfile, fieldnames)
        if not log_exists:
            dict_writer.writeheader()
        dict_writer.writerows(malformed_xml_docs)


def fetch_metadata_dump(url, local_filepath):
    print(f"downloading from {url}")
    results = REQUESTS_SESSION.get(url, timeout=IIIF_REQUEST_TIMEOUT)
    results.raise_for_status()
    json_result = results.json()
    log_directory, _ = os.path.split(local_filepath)
    if log_directory and not os.path.exists(log_directory):
        os.makedirs(log_directory)
    with open(local_filepath, "w", encoding="utf-8") as outfile:
        json.dump(json_result, outfile)
    return json_result


def load_project_metadata():
    if os.path.isfile(project_local_baserow_dump):
        with open(project_local_baserow_dump, "r", encoding="utf-8") as json_metadata_file:
            return json.load(json_metadata_file)["1"]
    return fetch_metadata_dump(
        url=project_base_row_dump_url, local_filepath=project_local_baserow_dump
    )["1"]


def load_document_metadata():
    if os.path.isfile(doc_local_baserow_dump):
        with open(doc_local_baserow_dump, "r", encoding="utf-8") as infile:
            return json.load(infile)
    return fetch_metadata_dump(url=doc_base_row_dump_url, local_filepath=doc_local_baserow_dump)


def normalize_doc_metadata(doc_metadata):
    normalized = copy.deepcopy(doc_metadata)
    normalized.setdefault("has_author", [])
    normalized.setdefault("has_digitizing_agent", [])
    normalized.setdefault("data_set", [])
    normalized.setdefault("type_of_document", [])
    normalized.setdefault("type_of_manifestation", [])

    normalized["type_of_document"] = " ".join(
        entry.get("value", "").strip()
        for entry in doc_metadata.get("type_of_document", [])
        if entry.get("value")
    )
    normalized["type_of_manifestation"] = " ".join(
        entry.get("value", "").strip()
        for entry in doc_metadata.get("type_of_manifestation", [])
        if entry.get("value")
    )
    return normalized


def get_goobi_imageName_from_url(image_url):
    return image_url.split("/")[-1].split(".")[0]


def build_goobi_iiif_base_url(bv_doc_id, image_name):
    return f"https://viewer.acdh.oeaw.ac.at/viewer/api/v1/records/{bv_doc_id}/files/images/{image_name}"


def build_manifest_url(bv_doc_id):
    return f"https://viewer.acdh.oeaw.ac.at/viewer/api/v1/records/{bv_doc_id}/manifest"


def fetch_iiif_info(info_url):
    response = REQUESTS_SESSION.get(info_url, timeout=IIIF_REQUEST_TIMEOUT)
    response.raise_for_status()
    iiif_info = response.json()
    return {
        "info_url": info_url,
        "width": int(iiif_info["width"]),
        "height": int(iiif_info["height"]),
    }


def get_image_name_from_service_id(service_id):
    image_name = service_id.rstrip("/").split("/")[-1]
    for suffix in (".tif", ".tiff", ".jp2", ".jpg", ".jpeg", ".png"):
        if image_name.lower().endswith(suffix):
            return image_name[: -len(suffix)]
    return image_name


def fetch_iiif_manifest_page_map(bv_doc_id):
    manifest_url = build_manifest_url(bv_doc_id)
    response = REQUESTS_SESSION.get(manifest_url, timeout=IIIF_REQUEST_TIMEOUT)
    response.raise_for_status()
    manifest = response.json()

    sequences = manifest.get("sequences", [])
    if not sequences:
        raise ValueError(f"manifest has no sequences: {manifest_url}")

    canvases = sequences[0].get("canvases", [])
    if not canvases:
        raise ValueError(f"manifest has no canvases: {manifest_url}")

    page_map = {}
    for canvas in canvases:
        images = canvas.get("images", [])
        if not images:
            continue

        resource = images[0].get("resource", {})
        service = resource.get("service", {})
        service_id = service.get("@id")
        if not service_id:
            continue

        width = resource.get("width") or canvas.get("width")
        height = resource.get("height") or canvas.get("height")
        if width is None or height is None:
            continue

        image_name = get_image_name_from_service_id(service_id)
        page_map[image_name] = {
            "info_url": f"{service_id.rstrip('/')}/info.json",
            "width": int(width),
            "height": int(height),
        }

    if not page_map:
        raise ValueError(f"manifest did not expose page image services: {manifest_url}")

    return page_map


def build_info_url_for_image(bv_doc_id, image_name, use_tif_suffix):
    iiif_image_id = build_goobi_iiif_base_url(
        bv_doc_id=bv_doc_id,
        image_name=image_name,
    )
    if use_tif_suffix:
        return f"{iiif_image_id}.tif/info.json"
    return f"{iiif_image_id}/info.json"


def resolve_iiif_page_metadata(bv_doc_id, image_name):
    """Return the first reachable IIIF info.json for a page (manifest uses the .tif id)."""
    failed_candidates = []
    for use_tif_suffix in (True, False):
        info_url = build_info_url_for_image(
            bv_doc_id=bv_doc_id,
            image_name=image_name,
            use_tif_suffix=use_tif_suffix,
        )
        try:
            return fetch_iiif_info(info_url)
        except Exception as exception:
            failed_candidates.append(f"{info_url}: {exception}")

    raise ValueError(
        f"no working IIIF info endpoint for {bv_doc_id}/{image_name}; "
        f"checked: {' | '.join(failed_candidates)}"
    )


def build_fallback_page(bv_doc_id, image_name, page_index):
    """Last resort: the bare image id, as written before IIIF metadata was resolved."""
    return {
        "info_url": build_goobi_iiif_base_url(
            bv_doc_id=bv_doc_id,
            image_name=image_name,
        ),
        "width": None,
        "height": None,
        "image_name": image_name,
        "page_index": page_index,
    }


def resolve_iiif_metadata_for_doc(bv_doc_id, image_names):
    if not image_names:
        return []

    manifest_map = {}
    try:
        manifest_map = fetch_iiif_manifest_page_map(bv_doc_id)
        print(f"iiif strategy for {bv_doc_id}: document manifest")
    except Exception as exception:
        print(f"manifest unavailable for {bv_doc_id}, fallback to page checks: {exception}")

    pages = []
    for page_index, image_name in enumerate(image_names, start=1):
        page_metadata = manifest_map.get(image_name)
        if page_metadata is None:
            try:
                page_metadata = resolve_iiif_page_metadata(
                    bv_doc_id=bv_doc_id,
                    image_name=image_name,
                )
            except Exception as exception:
                print(f"{bv_doc_id}/{image_name}: no IIIF info.json, using bare id: {exception}")
                page_metadata = build_fallback_page(bv_doc_id, image_name, page_index)
        else:
            page_metadata = dict(page_metadata)

        page_metadata["image_name"] = image_name
        page_metadata["page_index"] = page_index
        pages.append(page_metadata)

    if manifest_map and len(manifest_map) < len(image_names):
        print(
            f"{bv_doc_id}: manifest matched {len(manifest_map)}/{len(image_names)} pages"
        )

    return pages


def get_img_names_from_goobi_mets(bv_doc_id):
    request_target_url = (
        f"https://viewer.acdh.oeaw.ac.at/viewer/sourcefile?id={bv_doc_id}"
    )
    mets_doc = TeiReader(request_target_url)
    ns = mets_doc.nsmap
    ns["mets"] = "http://www.loc.gov/METS/"
    ns["xlink"] = "http://www.w3.org/1999/xlink"
    image_links = mets_doc.tree.xpath(
        "//mets:fileGrp[@USE='DEFAULT']//mets:FLocat[@LOCTYPE='URL']/@xlink:href",
        namespaces=ns,
    )
    if not image_links:
        raise ValueError(
            f"No image links found for document {bv_doc_id} at {request_target_url}"
        )
    image_names = [get_goobi_imageName_from_url(img_link) for img_link in image_links]
    image_names.sort(key=lambda image_name: int(image_name.removeprefix("IMG_")))
    return image_names


def build_facsimile(iiif_pages):
    facsimile = ET.Element(tei_qname("facsimile"), nsmap={None: tei_ns})
    for index, page_data in enumerate(iiif_pages, start=1):
        surface = ET.SubElement(facsimile, tei_qname("surface"))
        surface.set(f"{{{xml_ns}}}id", f"facs_{index}")

        graphic = ET.SubElement(surface, tei_qname("graphic"))
        graphic.set("url", page_data["info_url"])
        if page_data["width"] is not None and page_data["height"] is not None:
            surface.set("ulx", "0")
            surface.set("uly", "0")
            surface.set("lrx", str(page_data["width"]))
            surface.set("lry", str(page_data["height"]))
            graphic.set("width", f"{page_data['width']}px")
            graphic.set("height", f"{page_data['height']}px")

    return ET.tostring(facsimile, encoding="unicode")


def build_body(iiif_pages):
    body = ET.Element(tei_qname("body"), nsmap={None: tei_ns})
    div = ET.SubElement(body, tei_qname("div"))
    div.set("type", "main")
    for index, _page_data in enumerate(iiif_pages, start=1):
        pb = ET.SubElement(div, tei_qname("pb"))
        pb.set("facs", f"#facs_{index}")
        pb.set("n", str(index))
        pb.set(f"{{{xml_ns}}}id", f"img_{index:04d}")
        pb.set("break", "yes")
    body_string = ET.tostring(body, encoding="unicode")
    return body_string.replace('xmlns="http://www.tei-c.org/ns/1.0"', "")


def create_new_xml_data(doc_metadata, iiif_pages):
    bv_doc_id = doc_metadata["bv_id"]
    print(f"processing {bv_doc_id}")
    context = {
        "project_md": PROJECT_MD,
        "doc_metadata": normalize_doc_metadata(doc_metadata),
        "body": build_body(iiif_pages),
        "faksimile": build_facsimile(iiif_pages),
        "current_date": datetime.date.today().strftime("%Y-%m-%d"),
    }
    xml_data = template.render(context)
    doc = get_xml_doc(xml_data)
    if doc is not None:
        tei_file_path = os.path.join(TEI_DIR, bv_doc_id + ".xml")
        print("writing", tei_file_path)
        doc.tree_to_file(tei_file_path)


def process_all_files():
    metadata = load_document_metadata()
    eligible_docs = 0
    processed_docs = 0
    failed_docs = 0
    for row in metadata.values():
        if not row.get("skip_transcription"):
            continue
        eligible_docs += 1
        bv_doc_id = row.get("bv_id")
        if not bv_doc_id:
            record_malformed(str(row.get("id", "unknown")), "missing bv_id")
            failed_docs += 1
            continue
        try:
            image_names = get_img_names_from_goobi_mets(bv_doc_id)
        except Exception as exception:
            record_malformed(bv_doc_id, exception)
            failed_docs += 1
            continue
        if not image_names:
            record_malformed(bv_doc_id, "no images found")
            failed_docs += 1
            continue
        try:
            iiif_pages = resolve_iiif_metadata_for_doc(bv_doc_id, image_names)
        except Exception as exception:
            # Never drop a document because IIIF metadata was unavailable.
            print(f"{bv_doc_id}: IIIF resolution failed, using bare image ids: {exception}")
            iiif_pages = [
                build_fallback_page(bv_doc_id, image_name, index)
                for index, image_name in enumerate(image_names, start=1)
            ]

        create_new_xml_data(row, iiif_pages)
        processed_docs += 1
    if eligible_docs == 0:
        print("no image-only documents found")
    elif processed_docs == 0:
        print(
            f"found {eligible_docs} image-only document(s), but none could be generated; "
            f"{failed_docs} failed (see {MALFORMED_FILES_LOGPATH})"
        )
    else:
        print(
            f"generated {processed_docs} image-only TEI file(s) from {eligible_docs} eligible "
            f"document(s); {failed_docs} failed"
        )


if __name__ == "__main__":
    PROJECT_MD = load_project_metadata()
    os.makedirs(TEI_DIR, exist_ok=True)
    process_all_files()
    log_nonvalid_files()