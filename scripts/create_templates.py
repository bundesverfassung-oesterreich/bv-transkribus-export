import glob
import jinja2
import pandas as pd
import os
from acdh_tei_pyutils.tei import TeiReader
from dateutil.parser import parse, ParserError
from datetime import date
import tqdm
import lxml.etree as ET


templateLoader = jinja2.FileSystemLoader(searchpath="./scripts/templates")
templateEnv = jinja2.Environment(loader=templateLoader)
template = templateEnv.get_template('tei_template.xml')

df = pd.read_csv('gesamtliste_enriched.csv')
files = glob.glob('./alltei/*.xml')

file_mapper = {}
header = ['file', 'exception']
failed = []
for x in files:
    _, tail = os.path.split(x)
    try:
        doc = TeiReader(x)
    except Exception as e:
        failed.append([tail, e])
        continue
    title = doc.any_xpath('.//tei:title[@type="main"]/text()')[0]
    file_mapper[title] = x

mets = glob.glob('./mets/*/*mets.xml')
mets_mapper = {}
for x in mets:
    col_id, doc_id = x.replace('_mets.xml', '').replace("./mets/", "").split('/')
    mets_mapper[doc_id] = col_id

no_match = []
for gr, df in tqdm.tqdm(df.groupby('folder')):
    try:
        doc_id = file_mapper[gr]
    except KeyError:
        no_match.append(gr)
        continue
    proper_col_id = doc_id.replace('./alltei/', '').replace('_tei.xml', '')
    try:
        col_id = mets_mapper[proper_col_id]
    except KeyError:
        col_id = '00000'
    file_name = f"./data/editions/{gr}.xml"
    doc = TeiReader(doc_id)
    with open(file_name.lower(), 'w') as f:
        row = df.iloc[0]
        item = {}
        item['doc_id'] = proper_col_id
        item['col_id'] = col_id
        item['settlement'] = "München"
        item['repositor'] = "Bayerisches Hauptstaatsarchiv"
        item['id'] = gr.lower()
        item['file_name'] = f"{gr}.xml".lower()
        item['title'] = f"{row['weranwen']}, {row['Ort']} am {row['Datum']}"
        qka = row['Quellenkritische Anmerkungen']
        item["terms"] = []
        try:
            for x in qka.split(';')[1:]:
                item["terms"].append(x.strip())
        except:
            pass
        try:
            item["language"] = qka.split(';')[0].strip()
        except AttributeError:
            item["language"] = "noch nicht bestimmt"
        if item["language"].startswith("deu"):
            item["lang_code"] = "deu"
        elif item["language"].startswith("lat"):
            item["lang_code"] = "lat"
        elif item["language"].startswith("franz"):
            item["lang_code"] = "fra"
        elif item["language"].startswith("ital"):
            item["lang_code"] = "ita"
        else:
            item["lang_code"] = "und"
        try:
            item['sender'] = row['weranwen'].split(' an ')[0]
        except:
            item['sender'] = row['weranwen']
        try:
            if item["sender"].startswith("Eleonora"):
                item["sender_id"] = "emt_person_id__9"
            elif item["sender"].startswith("Philipp Wilhelm von Pfalz-Neuburg"):
                item["sender_id"] = "emt_person_id__50"
            elif item["sender"].startswith("Johann Wilhelm von Pfalz"):
                item["sender_id"] = "emt_person_id__18"
        except:
            pass
        try:
            item['receiver'] = row['weranwen'].split(' an ')[-1]
        except:
            item['receiver'] = row['weranwen']
        try:
            if item["receiver"].startswith("Eleonora"):
                item["receiver_id"] = "emt_person_id__9"
            elif item["receiver"].startswith("Philipp Wilhelm von Pfalz-Neuburg"):
                item["receiver_id"] = "emt_person_id__50"
            elif item["receiver"].startswith("Johann Wilhelm von Pfalz"):
                item["receiver_id"] = "emt_person_id__18"
        except:
            pass
        try:
            row['Ort'].strip()
            item["sender_place"] = row['Ort'].strip()
            if item["sender_place"].startswith('Wien'):
                item["sender_id_place"] = "emt_place_id__63"
            elif item["sender_place"].startswith('Düsseldorf'):
                item["sender_id_place"] = "emt_place_id__13"
            elif item["sender_place"].startswith('Laxenburg'):
                item["sender_id_place"] = "emt_place_id__31"
            elif item["sender_place"].startswith('Linz'):
                item["sender_id_place"] = "emt_place_id__32"
            elif item["sender_place"].startswith('Neuburg'):
                item["sender_id_place"] = "emt_place_id__39"
            elif item["sender_place"].startswith('Bensberg'):
                item["sender_id_place"] = "emt_place_id__7"
        except:
            pass
        try:
            item["bemerkung"] = row["Bemerkung"].strip()
        except:
            pass
        item['place'] = row['Ort']
        item['writte_date'] = row['Datum']
        item['current_date'] = f"{date.today()}"
        facsimile = doc.any_xpath('.//tei:facsimile')[0]
        item["facsimile"] = ET.tostring(facsimile, encoding='utf-8', pretty_print=True).decode('utf-8').replace(' xmlns="http://www.tei-c.org/ns/1.0"', '')
        body = doc.any_xpath('.//tei:body')[0]
        body_string = ET.tostring(body, encoding='utf-8', pretty_print=True).decode('utf-8')
        body_string = body_string.replace(' xmlns="http://www.tei-c.org/ns/1.0"', '')
        body_string = body_string.replace('reason=""', '')
        body_string = body_string.replace('type=""', '')
        body_string = body_string.replace('<blackening>', '<seg type="blackening">')
        body_string = body_string.replace('</blackening>', '</seg>')
        body_string = body_string.replace('<comment>', '<seg type="comment">')
        body_string = body_string.replace('</comment>', '</seg>')
        body_string = body_string.replace('<blackening/>', '')
        body_string = body_string.replace('<comment/>', '')
        item["body_string"] = body_string
        try:
            item['parsed_date'] = parse(item['writte_date'])
        except (ParserError, TypeError):
            item['parsed_date'] = None
        item['pages'] = []
        f.write(template.render(**item))
print(f"No matches: {len(no_match)}")

print("now fixing facs-filenames and pb-attributes")

editions = "./data/editions/"
df = pd.read_csv('gesamtliste_enriched.csv')
no_match = []
page_count_issue = []
for g, ndf in df.groupby('folder'):
    xml_doc = f"{editions}{g.lower()}.xml"
    pages = []
    try:
        doc = TeiReader(f"{xml_doc}")
    except OSError:
        no_match.append(xml_doc)
        continue
    for i, row in ndf.iterrows():
        page = {
            "file__name": row['Dateiname'],
            "fol_1": row['Foliierung'],
            "fol_2": row['Zweitfoliierung']
        }
        pages.append(page)
    for i, pb in enumerate(doc.any_xpath('.//tei:pb')):
        try:
            matching_page = pages[i]
        except IndexError:
            issue = {
                "doc": xml_doc,
                "page_nr": i
            }
            continue
        if isinstance(pages[i]['fol_1'], str):
            pb.attrib["n"] = pages[i]['fol_1']
        if isinstance(pages[i]['fol_2'], str):
            pb.attrib["ed"] = pages[i]['fol_2']
        pb.attrib["{http://www.w3.org/XML/1998/namespace}id"] = pages[i]['file__name']
    for i, graphic in enumerate(doc.any_xpath('.//tei:surface/tei:graphic[1]')):
        try:
            matching_page = pages[i]
        except IndexError:
            issue = {
                "doc": xml_doc,
                "page_nr": i
            }
            continue
        graphic.attrib["url"] = pages[i]['file__name']
    doc.tree_to_file(xml_doc)