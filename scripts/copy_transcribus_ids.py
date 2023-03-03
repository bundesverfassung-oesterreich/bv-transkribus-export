import copy
import sys
from acdh_tei_pyutils.tei import TeiReader


def return_col_id_from_doc(doc: TeiReader):
    try:
        return doc.tree.xpath(".//trpDocMetadata/docId/text()")[0]
    except IndexError:
        return ""


def return_doc_id_from_doc(doc):
    try:
        return doc.tree.xpath(".//trpDocMetadata/collectionList/colList/colId/text()")[0]
    except IndexError:
        return ""
    

def get_metadata_from_doc(doc):
    usefull_tags = ["url", "docId", "title", "nrOfPages", "pageId", "url", "collectionList"]
    try:
        metadata = doc.tree.xpath(".//trpDocMetadata")[0]
        subels = metadata.xpath("./*")
        for subel in subels:
            if subel.xpath("local-name()") not in usefull_tags:
                metadata.remove(subel)
        return copy.deepcopy(metadata)
    except IndexError:
        return None
    
    
def write_ids_from_doc_2_doc(source_doc_path, target_doc_path):
    target_doc = TeiReader(target_doc_path)
    source_doc = TeiReader(source_doc_path)
    # # no clue how to get nice tei here
    # col_id = return_col_id_from_doc(source_doc)
    # doc_id = return_doc_id_from_doc(source_doc)
    # # so we do it nasty for now
    meta_data = get_metadata_from_doc(source_doc)
    target_doc.any_xpath("//tei:teiHeader")[0].append(meta_data)
    target_doc.tree_to_file(target_doc_path)


def main():
    if len(sys.argv) != 3:
        print("not enough arguments, need source and target paths")
    else:
        write_ids_from_doc_2_doc(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()