import os
import datetime
import glob
import shutil
import re
import lxml.etree as ET
import lxml.builder as builder
import jinja2
import csv
import json
from acdh_tei_pyutils.tei import TeiReader


TEI_DIR = "./editions_source"
TMP_DIR = "./mets/"
MALFORMED_FILES_LOGPATH = "./logs/malformed_files.csv"
TEMPLATE_PATH = "./scripts/templates"
doc_base_row_dump_url = "https://raw.githubusercontent.com/bundesverfassung-oesterreich/bv-entities/main/json_dumps/document.json"
project_base_row_dump_url = "https://raw.githubusercontent.com/bundesverfassung-oesterreich/bv-entities/main/json_dumps/project_data.json"
doc_local_baserow_dump = TMP_DIR + "document.json"
project_local_baserow_dump = TMP_DIR + "project_data.json"
project_doc_types_dump = TMP_DIR + "doc_types.json"
project_manifestation_types_dump = TMP_DIR + "manifestation_types.json"
project_data_sets_dump = TMP_DIR + "bv_data_sets.json"
PROJECT_MD = {}


# # load template
templateLoader = jinja2.FileSystemLoader(searchpath=TEMPLATE_PATH)
templateEnv = jinja2.Environment(
    loader=templateLoader, trim_blocks=True, lstrip_blocks=True
)
template = templateEnv.get_template("tei_template.j2")
file_rename_errors = 0
nsmap = {
    "mets" : "http://www.loc.gov/METS/",
    "xml" : "http://www.tei-c.org/ns/1.0"
}
# # xml factory

NewElement = builder.ElementMaker()

# logfile for defective docs
malformed_xml_docs = []

# # def funcs
def remove_prefix(string, prefix):
    if string.startswith(prefix):
        string = string[len(prefix):]
    return string


def get_img_names_from_goobi_mets(bv_doc_id):
    request_target_url = f"https://viewer.acdh.oeaw.ac.at/viewer/sourcefile?id={bv_doc_id}"
    mets_doc = TeiReader(request_target_url)
    # thats a real good solution :)
    flocats = mets_doc.any_xpath("//*[local-name()='FLocat']")
    image_names = []
    for flocat in flocats:
        img_url = flocat.attrib['{http://www.w3.org/1999/xlink}href']
        try:
            img_name = re.match(r".*?(IMG_[0-9]+(?:_\d+)?)\.[a-zA-Z]+[^/]*$", img_url).group(1)
            # well i could have used the correct xpath but no (elements are doubled, there is default & representation)
            if img_name not in image_names:
                image_names.append(img_name)
        except AttributeError as attrib_except:
            print(f"can´t get img name from link '{img_url}' for document '{bv_doc_id}' that just was requested via GET '{request_target_url}'.")
            raise attrib_except
    sort_key = lambda imgname: int(imgname.removeprefix("IMG_"))
    # let's at least assume that the images are named correctly …
    image_names.sort(key=sort_key)
    return image_names


def replace_transkribus_images_with_goobi(graphic_elements, bv_doc_id):
    image_names = get_img_names_from_goobi_mets(bv_doc_id)
    # might need to delete one of the image_names due to remove_useless_elements 
    # removing the calibration page via remove_calibration_page
    if len(image_names) > len(graphic_elements):
        image_names.pop(0)
    tupled_list = list(map((lambda x,y: (x,y)), image_names, graphic_elements))
    for image_name, graphic_element in tupled_list:
        graphic_element.attrib["url"] = f"https://viewer.acdh.oeaw.ac.at/viewer/api/v1/records/{bv_doc_id}/files/images/{image_name}/full/full/0/default.jpg"


class PersonMetaData:
    def __init__(self, name, role, arche_role):
        self.name = name
        self.role = role
        self.arche_role = arche_role


def get_xml_doc(xml_file):
    """
    returns TeiReader, if parsing creates error -> dict
    """
    try:
        return TeiReader(xml_file)
    except Exception as exception:
        malformed_xml_docs.append({"file_name": xml_file[:200], "error": exception})
        return None


def log_nonvalid_files():
    if not malformed_xml_docs:
        if os.path.isfile(MALFORMED_FILES_LOGPATH):
            os.remove(MALFORMED_FILES_LOGPATH)
        print("no malformed files")
    else:
        print("Some or all files where malformed!".upper())
        fieldnames = ["file_name", "error"]
        log_directory, _ = os.path.split(MALFORMED_FILES_LOGPATH)
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)
        with open(MALFORMED_FILES_LOGPATH, "w") as outfile:
            dict_writer = csv.DictWriter(outfile, fieldnames)
            dict_writer.writerows(malformed_xml_docs)


def seed_div_elements(doc: TeiReader, xpath_expr, regex_test, type_val):
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
                section_div = NewElement.div("\n", type=type_val)
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


def place_the_goddam_pb_inside_of_last_p_sibling_element_if_there_is_one(doc):
    for pb in doc.any_xpath(f"//tei:div/tei:pb[preceding-sibling::*[1][local-name()='p']]"):
        p = pb.getprevious()
        next_element = pb.getnext()
        if next_element is not None and next_element.xpath("local-name()='p'"):
            if next_element.tail:
                p.tail += next_element.tail
            # this binds next_el.text to pb.tail
            if next_element.text:
                if not pb.tail:
                    pb.tail = ""
                pb.tail += next_element.text
                next_element.text = ""
            p.append(pb)
            for childelement in next_element:
                p.append(childelement)
            if (next_element.text or next_element.tail) and (next_element.text.strip() or next_element.tail.strip()):
                print(ET.tostring(next_element))
                raise ValueError
            else:
                next_element.getparent().remove(next_element)
        else:
            p.append(pb)


def expand_div_element(section_div: ET._Element, append_test):
    next_element = section_div.getnext()
    while append_test(next_element):
        section_div.append(next_element)
        next_element = section_div.getnext()


def make_all_section_divs(doc):
    article_type = "article"
    # # make artikel-divs
    article_divs = seed_div_elements(
        doc,
        #xpath_expr=r"//tei:body//tei:lb/following-sibling::text()[contains(., 'Art.') or contains(., 'Artikel')]",
        xpath_expr=r"//tei:body//tei:lb/following-sibling::text()[contains(., 'Art')]",
        regex_test=r"Art(?:ikel|\.)?(?: *[0-9]+| *[iIVvXxCcDdMmLl]+) *\.* *$",
        # regex_test=r" *Art\. *$",
        type_val=article_type,
    )
    # # move created divs to child-level of main div
    for div in article_divs:
        raise_div_element(div)

    # # place content in article divs
    for div in article_divs:
        expand_div_element(
            div,
            append_test=lambda next_element: bool(
                next_element is not None and next_element.xpath("local-name()!='div'")
            ),
        )

def substitute_useless_elements(doc: TeiReader, substitution_dict:dict):
    for substituted_element_name, substitution_element_name in substitution_dict.items():
        for substituted in doc.any_xpath(f"//tei:{substituted_element_name}"):
            substituted.tag = substituted.tag.rstrip(substituted_element_name)+substitution_element_name



def remove_useless_atributes(doc: TeiReader):
    elements = doc.any_xpath(
        ".//*[local-name()='lb' or local-name()='p' or local-name()='head']"
    )
    for element in elements:
        element.attrib.clear()


def remove_lb_preserve_text(new_text:str, prev_element, parent_element, lb):
    if prev_element is not None:
        prev_element.tail = new_text
    else:
        parent_element.text = new_text
    parent_element.remove(lb)


def replace_unleserlichs(doc):
    for text_node in doc.any_xpath('//tei:div[@type="main"]//text()[normalize-space()="unleserlich" or normalize-space()="Unleserlich"]'):
        gap = NewElement.gap(reason="illegible")
        parent = text_node.getparent()
        if text_node.is_text:
            if len(parent) == 0 and parent.xpath("local-name()") == "hi":
                parent.addnext(gap)
                parent.getparent().remove(parent)
            else:
                gap.tail = ""
                parent.text = ""
                parent.insert(0, gap)
        else:
            parent.tail=""
            parent.addnext(gap)


def replace_hi(doc: TeiReader):
    for hi_element in doc.any_xpath("//tei:hi"):
        # if span.xpath("@rend='strikethrough:true;'"):
        #     span.tag = "del"
        #     _ = span.attrib.pop("rend")
        # elif span.xpath("@rend='underlined:true;'"):
        #     span.tag = "ul"
        #     _ = span.attrib.pop("rend")
        # elif span.xpath("@rend='italic:true;'"):
        #     span.attrib["rend"] = "emphasis"
        # elif span.xpath("@rend='bold:true;'"):
        #     span.attrib["rend"] = "emphasis"
        # else:
        #     span.attrib["rend"] = ""
        hi_element.attrib.clear()
        hi_element.tag = "emph"

lb_encoders = ["-", "¬"]
def type_lb_elements(doc: TeiReader):
    lb_elements = doc.any_xpath("//tei:lb")
    for lb in lb_elements:
        prev_element = lb.getprevious()
        parent_element = lb.getparent()
        test_tail:str = lb.tail.strip() if lb.tail else ""
        prev_text: str = prev_element.tail.rstrip() if prev_element is not None else parent_element.text.rstrip()
        previous_text_node_implies_wordbreak = bool(prev_text) and prev_text[-1] in lb_encoders and (not prev_text[-2].isnumeric() if len(prev_text)>1 else True)
        lb_sibling_text_node_implies_no_wordbreak = bool(test_tail) and (test_tail.startswith("und") or test_tail.startswith("oder"))
        if previous_text_node_implies_wordbreak and not lb_sibling_text_node_implies_no_wordbreak:
            #seems to break in word
            pattern = r"[\¬\-](\s*)$"
            if prev_element is not None:
                textnode = prev_element.tail
                new_textnode = re.sub(pattern, "\n", textnode)
                prev_element.tail = new_textnode
            else:
                textnode = parent_element.text
                parent_element.text = re.sub(pattern, "\n", textnode)
            lb.attrib["break"] = "no"
        elif lb_sibling_text_node_implies_no_wordbreak:
            pattern = r"\¬"
            if prev_element is not None:
                prev_element.tail = re.sub(pattern, "-", prev_element.tail)
            else:
                parent_element.text = re.sub(pattern, "-", parent_element.text)
            lb.attrib["break"] = "yes"
        else:
            lb.attrib["break"] = "yes"



def remove_lb_elements(doc: TeiReader):
    lb_elements = doc.any_xpath("//tei:lb")
    for lb in lb_elements:
        prev_element = lb.getprevious()
        parent_element = lb.getparent()
        test_tail:str = lb.tail.strip() if lb.tail else ""
        lstrip_tail = lb.tail.lstrip() if lb.tail else test_tail
        prev_text: str = prev_element.tail.rstrip() if prev_element is not None else parent_element.text.rstrip()
        if prev_text:
            if prev_text.endswith("-"):
                if test_tail:
                    if test_tail[0].islower() and not test_tail.startswith("und") and not test_tail.startswith("oder"):
                        new_text = prev_text.rstrip("-") + lstrip_tail
                        remove_lb_preserve_text(new_text, prev_element, parent_element, lb)
                    else:
                        # hyphen but probably not in a word
                        new_text = prev_text + " " + lstrip_tail
                        remove_lb_preserve_text(new_text, prev_element, parent_element, lb)
                else:
                    parent_element.remove(lb)
            else:
                new_text = prev_text + " " + lstrip_tail
                remove_lb_preserve_text(new_text, prev_element, parent_element, lb)
        else:
            new_text = lb.tail
            remove_lb_preserve_text(new_text, prev_element, parent_element, lb)


def remove_calibration_page(doc: TeiReader):
    removeable_pb_xpath = "//tei:pb[1][following-sibling::*[1][local-name()='pb']]"
    removeable_first_pb = doc.any_xpath(removeable_pb_xpath)
    if removeable_first_pb:
        calibration_pb = removeable_first_pb[0]
        if calibration_pb.tail is None or not calibration_pb.tail.strip():
            calibration_pb.getparent().remove(calibration_pb)
            first_surface = doc.any_xpath("//tei:surface[1]")[0]
            first_surface.getparent().remove(first_surface)


def remove_empty_paras(doc):
    for empty_p in doc.any_xpath("//tei:p[not(*) and normalize-space()='']"):
        if empty_p.tail is None or not empty_p.tail.strip():
            empty_p.getparent().remove(empty_p)


def remove_lbs_as_first_child_of_p_without_text(doc):
    for parent in doc.any_xpath(
        "//tei:*[(local-name()='p' or local-name()='ab') and ./node()[1][normalize-space(.)=''] and ./*[1][local-name()='lb']]"
    ):
        parent.text = parent[0].tail
        parent.remove(parent[0])


def remove_useless_elements(doc: TeiReader):
    remove_calibration_page(doc)
    remove_empty_paras(doc)
    remove_lbs_as_first_child_of_p_without_text(doc)


def get_faksimile_element(doc: TeiReader, bv_doc_id:str):
    graphic_elements = doc.any_xpath(".//tei:graphic")
    replace_transkribus_images_with_goobi(graphic_elements, bv_doc_id)
    #for graphic_element in graphic_elements:
    #    graphic_element.attrib["url"] = get_goobi_image_url(graphic_element, bv_doc_id)
    for zone_element in doc.any_xpath(".//tei:facsimile/tei:surface//tei:zone"):
        zone_element.getparent().remove(zone_element)
    faksimile_element = doc.any_xpath(".//tei:facsimile")[0]
    return ET.tostring(faksimile_element).decode("utf-8")

def create_main_div(doc: TeiReader):
    parent_div = doc.any_xpath("//tei:body/tei:div[1]")[0]
    parent_div.attrib["type"] = "main"

def add_break_attrib_to_pbs(doc):
    for pb in doc.any_xpath(
        "//tei:pb[not(@break)]"
    ):
        pb.attrib["break"] = "yes"

def create_new_xml_data(
    doc: TeiReader,
    doc_metadata: dict,
):
    # # get body & filename
    bv_doc_id = doc_metadata["bv_id"]
    print(f"processing {bv_doc_id}")
    body_node = doc.any_xpath(".//tei:body")[0]
    make_all_section_divs(doc)
    substitute_useless_elements(
        doc=doc,
        substitution_dict={
            "ab" : "p"
        }
    )
    remove_useless_atributes(doc)
    remove_useless_elements(doc)
    add_break_attrib_to_pbs(doc)
    create_main_div(doc)
    type_lb_elements(doc)
    replace_hi(doc)
    replace_unleserlichs(doc)
    place_the_goddam_pb_inside_of_last_p_sibling_element_if_there_is_one(doc)
    body_string = ET.tostring(body_node).decode("utf-8")
    body_string = body_string.replace('xmlns="http://www.tei-c.org/ns/1.0"', "")
    # # get faksimile
    faksimile = get_faksimile_element(doc, bv_doc_id=bv_doc_id)
    # # get metadata
    context = {
        "project_md": PROJECT_MD,
        "doc_metadata": doc_metadata,
        "body": body_string,
        "faksimile": faksimile,
        "current_date": datetime.date.today().strftime('%Y-%m-%d')
    }
    xml_data = template.render(context)
    doc = get_xml_doc(xml_data)
    if doc is not None:
        tei_file_path = os.path.join(TEI_DIR, bv_doc_id + ".xml")
        print("writing", tei_file_path)
        doc.tree_to_file(tei_file_path)

def return_image_urls(mets_doc):
    """
    returns image links from mets file in doc order
    """
    return mets_doc.tree.xpath(
        "//ns3:fileGrp[@ID='IMG']/ns3:file/ns3:FLocat/@ns2:href",
        namespaces={
            "ns3": "http://www.loc.gov/METS/",
            "ns2": "http://www.w3.org/1999/xlink",
        },
    )


def return_transkribus_doc_id(xml_file_path):
    _, filename = os.path.split(xml_file_path)
    return filename.split("_")[0]


def return_mets_doc(transkribus_doc_id: str, transkribus_collection_id: str):
    mets_file_str = f"./mets/{transkribus_collection_id}/{transkribus_doc_id}_mets.xml"
    return get_xml_doc(mets_file_str)


def return_col_id_from_mets_doc(doc: TeiReader):
    try:
        return doc.tree.xpath(".//trpDocMetadata/docId/text()")[0]
    except IndexError:
        return ""


def fetch_metadata_dump(url, local_filepath):
    import requests
    print(f"downloading from {url}")
    results = requests.get(url)
    json_result = results.json()
    with open(local_filepath, "w") as outfile:
        json.dump(json_result, outfile)
    return json_result


class BaseRowTypeResolver:
    def __init__(self):
        self.doc_types_url = "https://raw.githubusercontent.com/bundesverfassung-oesterreich/bv-entities/main/json_dumps/type_of_document.json"
        self.manifestation_types_url = "https://raw.githubusercontent.com/bundesverfassung-oesterreich/bv-entities/main/json_dumps/type_of_manifestation.json"
        self.bv_data_sets_url = "https://raw.githubusercontent.com/bundesverfassung-oesterreich/bv-entities/main/json_dumps/data_set.json"
        self.doc_types_path = project_doc_types_dump
        self.manifestation_types_path = project_manifestation_types_dump
        self.data_sets_path = project_data_sets_dump
        self.doc_types_by_row = fetch_metadata_dump(
            url=self.doc_types_url,
            local_filepath=self.doc_types_path
        )
        self.manifestation_types_by_row = fetch_metadata_dump(
            url=self.manifestation_types_url,
            local_filepath=self.manifestation_types_path
        )
        self.bv_data_sets_by_row = fetch_metadata_dump(
            url=self.bv_data_sets_url,
            local_filepath=self.data_sets_path
        )
        self.doctype_by_id = None
        self.manitype_by_id = None
        self.datasets_by_id = None
    

    def get_doctype_from_id(self, d_id:str):
        if self.doctype_by_id is None:
            self.doctype_by_id = dict(
                [
                    (item["bv_id"], item) for rownmbr, item in self.doc_types_by_row.items()
                ]
            )
        return self.doctype_by_id[d_id]
    

    def get_manifestationtype_from_id(self, m_id:str):
        if self.manitype_by_id is None:
            self.manitype_by_id = dict(
                [
                    (item["bv_id"], item) for rownmbr, item in self.manifestation_types_by_row.items()
                ]
            )
        return self.manitype_by_id[m_id]
    

    def get_dataset_from_id(self, d_id:str):
        if self.datasets_by_id is None:
            self.datasets_by_id = dict(
                [
                    (item["bv_id"], item) for rownmbr, item in self.manifestation_types_by_row.items()
                ]
            )
        return self.datasets_by_id[d_id]

    
    def get_dataset_from_row(self, row_number:str):
        return self.bv_data_sets_by_row[row_number]

    def get_manifestationtype_from_row(self, row_number:str):
        return self.manifestation_types_by_row[row_number]


    def get_doctype_from_row(self, row_number:str):
        return self.doc_types_by_row[row_number]
    

baserow_type_resolver = BaseRowTypeResolver()

def load_metadata_from_dump():
    json_data = None
    if not os.path.exists(doc_local_baserow_dump):
        _ = fetch_metadata_dump(
            url=doc_base_row_dump_url, local_filepath=doc_local_baserow_dump
        )
        json_data = fetch_metadata_dump(
            url=doc_base_row_dump_url, local_filepath=doc_local_baserow_dump
        )
    else:
        with open(doc_local_baserow_dump, "r") as infile:
            json_data = json.load(infile)
    meta_data_objs_by_transkribus_id = {}
    for row in json_data.values():
        mets_dict = row
        transkribus_col_id = mets_dict["transkribus_col_id"]
        transkribus_doc_id = mets_dict["transkribus_doc_id"]
        if transkribus_col_id and transkribus_col_id.strip():
            if transkribus_col_id not in meta_data_objs_by_transkribus_id:
                meta_data_objs_by_transkribus_id[transkribus_col_id] = {}
            meta_data_objs_by_transkribus_id[transkribus_col_id][transkribus_doc_id] = mets_dict
    return meta_data_objs_by_transkribus_id


def resolve_types(doc_metadata):
    manifestation_types = []
    for entry in doc_metadata["type_of_manifestation"]:
        manifestation_types.append(
            baserow_type_resolver.get_manifestationtype_from_row(str(entry["id"]))["name"]
        )
    doc_types = []
    for entry in doc_metadata["type_of_document"]:
        doc_types.append(
            baserow_type_resolver.get_doctype_from_row(str(entry["id"]))["name"]
        )
    doc_metadata["type_of_document"] = " ".join(doc_types)
    doc_metadata["type_of_manifestation"] = " ".join(manifestation_types)
    return doc_metadata


def process_all_files():
    # # load metadata from baserow
    metadata = load_metadata_from_dump()
    for transkribus_collection_id, collection_metadata in metadata.items():
        # # load sourcefiles from fetch / transform job
        source_files = glob.glob(f"{TMP_DIR}/{transkribus_collection_id}/*_tei.xml")
        for xml_file_path in source_files:
            # # parsing doc to mem
            doc = get_xml_doc(xml_file_path)
            if doc is not None:
                # # important stuff happens here
                # # organize data yet missing in the final doc
                transkribus_doc_id = return_transkribus_doc_id(xml_file_path)
                if transkribus_doc_id not in collection_metadata:
                    print(
                        f"No metadata found for transkribus-doc-id '{transkribus_doc_id}'."
                    )
                else:
                    doc_metadata = resolve_types(collection_metadata[transkribus_doc_id])
                    print(f"loading {transkribus_doc_id}")
                    mets_doc = return_mets_doc(
                        transkribus_doc_id, transkribus_collection_id
                    )
                    if mets_doc is not None:
                        #image_urls = return_image_urls(mets_doc)
                        # # change the doc / write data to it
                        create_new_xml_data(doc, doc_metadata)


if __name__ == "__main__":
    # # the following is needed, cause you never know if this stuff ist there.
    if os.path.isfile(project_local_baserow_dump):
        with open(
            project_local_baserow_dump, "r", encoding="utf-8"
        ) as json_metadata_file:
            PROJECT_MD = json.load(json_metadata_file)["1"]
    else:
        PROJECT_MD = fetch_metadata_dump(
            url=project_base_row_dump_url, local_filepath=project_local_baserow_dump
        )["1"]
    # # clear directory for new export
    shutil.rmtree(TEI_DIR, ignore_errors=True)
    os.makedirs(TEI_DIR, exist_ok=True)
    # # load / process all unprocessed files
    process_all_files()
    log_nonvalid_files()
    if file_rename_errors != 0:
        print(
            f"\n{file_rename_errors} file(s) couldn’t be renamed since title wasn’t found in xml\n"
        )
