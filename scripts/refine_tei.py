import os
import glob
import shutil
import lxml.etree as ET
import lxml.builder as builder
import jinja2
import csv
import json
from acdh_tei_pyutils.tei import TeiReader
from slugify import slugify


TEI_DIR = "./editions"
TMP_DIR = "./mets/"
MALFORMED_FILES_LOGPATH = "./logs/malformed_files.csv"

# # setup metadata from json
MD_TABLE = {}
with open("specific_meta_data.json", "r", encoding="utf-8") as json_metadata_file:
    MD_TABLE = json.load(json_metadata_file)
PROJECT_MD = {}
with open("general_meta_data.json", "r", encoding="utf-8") as json_metadata_file:
    PROJECT_MD = json.load(json_metadata_file)

# # load template
templateLoader = jinja2.FileSystemLoader(searchpath="./scripts/templates")
templateEnv = jinja2.Environment(
    loader=templateLoader, trim_blocks=True, lstrip_blocks=True
)
template = templateEnv.get_template("tei_template.j2")
file_rename_errors = 0

# # xml factory

NewElement = builder.ElementMaker()

# # def funcs

def remove_elements(root_element: TeiReader, xpath_expression: str, preserve_childnodes = True):
    elements = root_element.any_xpath(xpath_expression)
    for element in elements:
        text = element.text
        parent_element = element.getparent()
        previous_sibling = element.getprevious()
        if preserve_childnodes:
            if len(element) == 0:
                text = (text or "") + (element.tail or "")
            if text is not None and text.strip():
                if previous_sibling is not None:
                    if not previous_sibling.tail or not previous_sibling.tail.strip():
                        previous_sibling.tail = text
                    else:
                        previous_sibling.tail += text
                else:
                    if not parent_element.text or not parent_element.text.strip():
                        parent_element.text = text
                    else:
                        parent_element.text += text
            if len(element) > 0:
                for subelement in element:
                    element.addprevious(subelement)
                if element.tail is not None and element.tail.strip():
                    previous_sibling = element.getprevious()
                    if not previous_sibling.tail or not previous_sibling.tail.strip():
                        previous_sibling.tail = element.tail
                    else:
                        previous_sibling.tail += element.tail
        else:
            element_tail = element.tail
            if element_tail and element_tail.strip():
                if previous_sibling:
                    if previous_sibling.tail is not None:
                        previous_sibling.tail += element_tail
                    else:
                        previous_sibling.tail = element_tail
                else:
                    if parent_element.text is not None:
                        parent_element.text += element_tail
                    else:
                        parent_element.text = element_tail
        parent_element.remove(element)


def get_xml_doc(xml_file):
    try:
        return TeiReader(xml_file)
    except Exception as e:
        return {"file_name": xml_file, "error": e}


def log_nonvalid_files(malformed_xml_docs):
    if not malformed_xml_docs:
        if os.path.isfile(MALFORMED_FILES_LOGPATH):
            os.remove(MALFORMED_FILES_LOGPATH)
    else:
        fieldnames = ["file_name", "error"]
        log_directory, _ = os.path.split(MALFORMED_FILES_LOGPATH)
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)
        with open(MALFORMED_FILES_LOGPATH, "w") as outfile:
            dict_writer = csv.DictWriter(outfile, fieldnames)
            dict_writer.writerows(malformed_xml_docs)


def get_new_filename(doc: TeiReader):
    try:
        main_title_string = doc.any_xpath(
            "//tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title[@type='main']/text()[1]"
        )[0]
        return slugify(main_title_string) + ".xml"
    except IndexError:
        global file_rename_errors
        file_rename_errors += 1
        return f"titel_konnte_nicht_ermittelt_werden_{file_rename_errors}"

def find_article_titles(doc: TeiReader):
    article_titles = doc.any_xpath("//tei:lb/following-sibling::text()[contains(., 'Art.')]")
    article_titles.reverse()
    for arttitle in article_titles:
        # # regext test necessary
        arttitle: ET._ElementUnicodeResult
        parent = arttitle.getparent()
        if arttitle.is_tail:
            parent.tag = "head"
            parent.text = arttitle
            parent.tail = "\n"
            div = NewElement.div("\n", ana="article")
            div.tail = "\n"
            parent.addprevious(div)
            div.append(parent)
            p_element = NewElement.p("\n")
            div.append(p_element)
            next_element = div.getnext()
            while (next_element is not None and next_element.xpath("local-name()!='p' and local-name()!='div'")):
                new_next_element = next_element.getnext()
                p_element.append(next_element)
                next_element = new_next_element

def remove_useless_atributes(doc: TeiReader):
    elements = doc.any_xpath(
        ".//*[local-name()='lb' or local-name()='p']"
    )
    for element in elements:
        element.attrib.clear()

def get_faksimile(doc: TeiReader, image_urls: list):
    for graphic_element in doc.any_xpath(".//tei:graphic"):
        graphic_element.attrib["url"] = image_urls.pop()
    for zone_element in doc.any_xpath(".//tei:facsimile/tei:surface//tei:zone[not(@subtype='paragraph')]"):
        zone_element.getparent().remove(zone_element)
    faksimile_element = doc.any_xpath(".//tei:facsimile")[0]
    return ET.tostring(faksimile_element).decode("utf-8")
    

def get_new_xml_data(doc: TeiReader, file_name: str, image_urls: list):
    # # get body & filename
    body_node = doc.any_xpath(".//tei:body")[0]
    remove_useless_atributes(doc)
    find_article_titles(doc)
    body = ET.tostring(body_node).decode("utf-8")
    body = body.replace('xmlns="http://www.tei-c.org/ns/1.0"', "")
    # # get faksimile
    faksimile = get_faksimile(doc, image_urls)
    # # get metadata
    try:
        item_md = MD_TABLE[file_name.replace(".xml", "")]
    except KeyError:
        item_md = MD_TABLE["dummy"]
    context = {
        "project_md": PROJECT_MD,
        "item_md": item_md,
        "file_name": file_name,
        "body": body,
        "faksimile": faksimile
    }
    xml_data = template.render(context)
    return xml_data


def find_image_urls(xml_file_path: str):
    _, filename = os.path.split(xml_file_path)
    doc_nmbr = filename.split("_")[0]
    mets_file_str = f"./mets/188933/{doc_nmbr}_mets.xml"
    #image_name_file_str = f"./mets/188933/{doc_nmbr}_image_name.xml"
    doc = TeiReader(mets_file_str)
    return doc.tree.xpath("//ns3:fileGrp[@ID='IMG']/ns3:file/ns3:FLocat/@ns2:href", namespaces={"ns3":"http://www.loc.gov/METS/", "ns2":"http://www.w3.org/1999/xlink"})


def process_all_files(collection_id):
    source_files = glob.glob(f"{TMP_DIR}/{collection_id}/*_tei.xml")
    malformed_xml_docs = []
    for xml_file in source_files:
        image_urls = find_image_urls(xml_file)
        doc = get_xml_doc(xml_file)
        if isinstance(doc, dict):
            malformed_xml_docs.append(doc)
        else:
            # _, old_file_name = os.path.split(xml_file)
            new_file_name = get_new_filename(doc)
            print(f"\t{new_file_name}")
            xml_data = get_new_xml_data(doc, new_file_name, image_urls)
            doc = TeiReader(xml_data)
            doc.tree_to_file(os.path.join(TEI_DIR, new_file_name))
    return malformed_xml_docs


# # clear directory for new export
shutil.rmtree(TEI_DIR, ignore_errors=True)
os.makedirs(TEI_DIR, exist_ok=True)

# # load / process all unprocessed files
malformed_xml_docs = []
for collection_id in ["188933"]:
    malformed_xml_docs += process_all_files(collection_id)
log_nonvalid_files(malformed_xml_docs)
if file_rename_errors != 0:
    print(
        f"\n{file_rename_errors} file(s) couldn’t be renamed since title wasn’t found in xml\n"
    )
