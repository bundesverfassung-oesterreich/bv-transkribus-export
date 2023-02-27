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
faulty_xml_docs = []

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
        faulty_xml_docs.append({"file_name": xml_file, "error": e})
        return None

def log_nonvalid_files():
    pass

def get_new_xml_data(doc, filen_ame):
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

# # clear directory for new export
shutil.rmtree(TEI_DIR, ignore_errors=True)
os.makedirs(TEI_DIR, exist_ok=True)

# # load / process all unprocessed files
files = glob.glob(f"{TMP_DIR}/*.xml")
for xml_file in files:
    doc = get_xml_doc(xml_file)
    _, file_name = os.path.split(xml_file)
    if doc is not None:
        xml_data = get_new_xml_data(doc, file_name)
        doc = TeiReader(xml_data)
        doc.tree_to_file(os.path.join(TEI_DIR, file_name))