import os
import glob
import shutil
import re
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


def seed_div_elements(doc: TeiReader, xpath_expr, regex_test, ana_val):
    reverse_ordered_div_elements = []
    section_head_strs = doc.any_xpath(xpath_expr)
    section_head_strs.reverse()
    for head_str in section_head_strs:
        head_str: ET._ElementUnicodeResult
        if re.match(regex_test, head_str.strip()):
            head_element = head_str.getparent()
            if head_str.is_tail:
                head_element.tag = "head"
                head_element.text = head_str
                head_element.tail = "\n"
                section_div = NewElement.div("\n", ana=ana_val)
                section_div.tail = "\n"
                head_element.addprevious(section_div)
                section_div.append(head_element)
                reverse_ordered_div_elements.append(section_div)
    return reverse_ordered_div_elements


def raise_div_element(section_div: ET._Element):
    parent_element = section_div.getparent()
    while parent_element.xpath("local-name()") != "div":
        if section_div.getprevious() is not None:
            parent_split_element = NewElement.stuff("\n")
            parent_split_element.tag = parent_element.tag
            siblings = section_div.xpath("following-sibling::*")
            for element in siblings:
                parent_split_element.append(element)
            parent_element.addnext(parent_split_element)
            parent_element.addnext(section_div)
        else:
            if parent_element.text and parent_element.text.strip():
                parent_split_element = NewElement.randomTagShouldntExist("\n")
                parent_split_element.tag = parent_element.tag
                parent_split_element.text = parent_element.text
                parent_element.text = ""
                parent_element.addprevious(parent_split_element)
            parent_element.addprevious(section_div)
        parent_element = section_div.getparent()


def expand_div_element(section_div: ET._Element, append_test):
    next_element = section_div.getnext()
    while append_test(next_element):
        section_div.append(next_element)
        next_element = section_div.getnext()


def make_all_section_divs(doc):
    section_ana = "section"
    subsection_ana = "sub_section"
    article_ana = "article"
    # # make artikel-divs
    article_divs = seed_div_elements(
        doc,
        xpath_expr=r"//tei:body//tei:lb/following-sibling::text()[contains(., 'Art.')]",
        regex_test=r"^Art\.? .{0,10}$",
        ana_val=article_ana,
    )
    for div in article_divs:
        raise_div_element(div)

    # # make section-divs
    section_divs = seed_div_elements(
        doc,
        xpath_expr=r"//tei:body//tei:lb/following-sibling::text()[contains(., 'nitt') or contains(., 'estimmung')]",
        regex_test="^[A-Za-zäöü]{3,}ter Ab.{1,4}nitt[. ]*$|[aA]llgemeine [bB]estimmungen.{,4}$",
        ana_val=section_ana,
    )
    for div in section_divs:
        raise_div_element(div)

    # # make subsection-divssubsection
    subsection_divs = seed_div_elements(
        doc,
        xpath_expr=r"//tei:body//tei:lb[count(following-sibling::*)<2]/following-sibling::text()[contains(.,'on de')]",
        regex_test=r"^[A-Z]{1}[).]* [vV]on de.{5,30}$",
        ana_val=subsection_ana,
    )
    for div in subsection_divs:
        raise_div_element(div)

    # # place content in section_divs
    for div in section_divs:
        expand_div_element(
            div,
            append_test=lambda next_element: bool(
                next_element is not None
                and next_element.xpath(f"not(@ana='{section_ana}')")
            ),
        )

    # # place content in sub_section_divs
    for div in subsection_divs:
        expand_div_element(
            div,
            append_test=lambda next_element: bool(
                next_element is not None
                and next_element.xpath(f"not(@ana='{subsection_ana}')")
            ),
        )

    # # place content in article divs
    for div in article_divs:
        expand_div_element(
            div,
            append_test=lambda next_element: bool(
                next_element is not None and next_element.xpath("local-name()!='div'")
            ),
        )


def remove_useless_atributes(doc: TeiReader):
    elements = doc.any_xpath(".//*[local-name()='lb' or local-name()='p']")
    for element in elements:
        element.attrib.clear()


def remove_useless_lbs(doc: TeiReader):
    for p in doc.any_xpath(
        "//tei:p[./node()[1][normalize-space(.)=''] and ./*[1][local-name()='lb']]"
    ):
        p.text = p[0].tail
        p.remove(p[0])


def get_faksimile(doc: TeiReader, image_urls: list):
    for graphic_element in doc.any_xpath(".//tei:graphic"):
        graphic_element.attrib["url"] = image_urls.pop()
    for zone_element in doc.any_xpath(
        ".//tei:facsimile/tei:surface//tei:zone[not(@subtype='paragraph')]"
    ):
        zone_element.getparent().remove(zone_element)
    faksimile_element = doc.any_xpath(".//tei:facsimile")[0]
    return ET.tostring(faksimile_element).decode("utf-8")


def get_new_xml_data(doc: TeiReader, file_name: str, image_urls: list):
    # # get body & filename
    body_node = doc.any_xpath(".//tei:body")[0]
    make_all_section_divs(doc)
    remove_useless_atributes(doc)
    remove_useless_lbs(doc)
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
        "faksimile": faksimile,
    }
    xml_data = template.render(context)
    return xml_data


def find_image_urls(xml_file_path: str):
    _, filename = os.path.split(xml_file_path)
    doc_nmbr = filename.split("_")[0]
    mets_file_str = f"./mets/188933/{doc_nmbr}_mets.xml"
    # image_name_file_str = f"./mets/188933/{doc_nmbr}_image_name.xml"
    doc = TeiReader(mets_file_str)
    return doc.tree.xpath(
        "//ns3:fileGrp[@ID='IMG']/ns3:file/ns3:FLocat/@ns2:href",
        namespaces={
            "ns3": "http://www.loc.gov/METS/",
            "ns2": "http://www.w3.org/1999/xlink",
        },
    )


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

if __name__ == "__main__":
    # # load / process all unprocessed files
    malformed_xml_docs = []
    for collection_id in ["188933"]:
        malformed_xml_docs += process_all_files(collection_id)
    log_nonvalid_files(malformed_xml_docs)
    if file_rename_errors != 0:
        print(
            f"\n{file_rename_errors} file(s) couldn’t be renamed since title wasn’t found in xml\n"
        )
