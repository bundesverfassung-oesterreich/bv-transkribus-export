from acdh_tei_pyutils.tei import TeiReader
import lxml.builder as E
import glob
elementMaker = E.ElementMaker(namespace="http://www.tei-c.org/ns/1.0", nsmap={"tei": "http://www.tei-c.org/ns/1.0"})
inputpath = "./editions_source/*.xml"

def make_catalogue(inputpath):
    catalogue = {}
    for file in glob.glob(inputpath):
        tr = TeiReader(file)
        # get date of creation from teiHeader/fileDesc/publicationStmt
        date = tr.any_xpath('.//tei:msDesc/tei:history/tei:origin/@notBefore-iso')[0].strip()
        dataset = tr.any_xpath('.//tei:idno[@type="bv_data_set"]/text()')[0].strip()
        if not date or not dataset:
            print("dataset: ", dataset)
            print("date: ", date)
            raise ValueError(f"Skipping {file} because date or dataset is missing")
        if not dataset in catalogue:
            catalogue[dataset] = []
        else:
            catalogue[dataset].append((date, file))
    return catalogue

def get_number_from_filename(filename):
    # get number from filename
    number = filename.split("__")[-1].split(".")[0]
    # pad with leading zeros to 4 digits
    number = "-"+number.zfill(4)
    return number

def sort_and_update_catalogue(catalogue):
    for dataset in catalogue:
        print(f"Dataset: {dataset} with {len(catalogue[dataset])} files")
        dataset = sorted(catalogue[dataset], key=lambda x: x[0]+get_number_from_filename(x[1]))
        current_index = 0
        for date, filepath in dataset:
            current_index += 100
            xmldoc = TeiReader(filepath)
            ordernumber = str(current_index).zfill(4)
            series_stmt = elementMaker.seriesStmt(
                "\n",
                elementMaker.title(xmldoc.any_xpath("//tei:idno[@type='bv_data_set']/text()")[0].strip()),
                "\n",
                elementMaker.biblScope(ordernumber,unit="part"),
                "\n"
            )
            series_stmt.tail ="\n"
            publicationStmt = xmldoc.any_xpath("//tei:fileDesc/tei:publicationStmt")[0]
            publicationStmt.addnext(series_stmt)
            xmldoc.tree_to_file(filepath)

catalogue = make_catalogue(inputpath)
sort_and_update_catalogue(catalogue)