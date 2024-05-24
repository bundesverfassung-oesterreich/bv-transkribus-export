import refine_tei
from acdh_tei_pyutils.tei import TeiReader

def delete_lbs(doc: TeiReader):
    for lb in doc.any_xpath("//tei:lb"):
        parent = lb.getparent()
        parent.remove(lb)


if __name__ == "__main__":
    input_dir="../bv-working-data/data/editions/*.xml"
    print(f"loading xmls from {input_dir}")
    for fp in refine_tei.glob.glob(input_dir):
        print(fp)
        doc = refine_tei.TeiReader(fp)
        delete_lbs(doc)
        # for article_div in doc.any_xpath(".//tei:div[@type='article']"):
        #     refine_tei.make_jur_sections_in_article(article_div)
        doc.tree_to_file(fp)