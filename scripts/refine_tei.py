import os
import glob
import shutil
import lxml.etree as ET
import jinja2
import csv
import json
from acdh_tei_pyutils.tei import TeiReader

TEI_DIR = "./editions"
TMP_DIR = "./alltei"
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


def get_new_xml_data(doc, file_name):
    # # get body & filename
    body_node = doc.any_xpath(".//tei:body")[0]
    body = ET.tostring(body_node).decode("utf-8")
    body = body.replace('xmlns="http://www.tei-c.org/ns/1.0"', "")
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
    }
    xml_data = template.render(context)
    return xml_data


def process_all_files():
    files = glob.glob(f"{TMP_DIR}/*.xml")
    malformed_xml_docs = []
    for xml_file in files:
        doc = get_xml_doc(xml_file)
        if isinstance(doc, dict):
            malformed_xml_docs.append(doc)
        else:
            _, file_name = os.path.split(xml_file)
            xml_data = get_new_xml_data(doc, file_name)
            doc = TeiReader(xml_data)
            doc.tree_to_file(os.path.join(TEI_DIR, file_name))
    return malformed_xml_docs


# # clear directory for new export
shutil.rmtree(TEI_DIR, ignore_errors=True)
os.makedirs(TEI_DIR, exist_ok=True)

# # load / process all unprocessed files
malformed_xml_docs = process_all_files()
log_nonvalid_files(malformed_xml_docs)
