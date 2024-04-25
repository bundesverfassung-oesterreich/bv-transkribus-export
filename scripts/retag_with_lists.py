import refine_tei

if __name__ == "__main__":
    input_dir="../bv-working-data/data/editions/*.xml"
    print(f"loading xmls from {input_dir}")
    for fp in refine_tei.glob.glob(input_dir):
        print(fp)
        doc = refine_tei.TeiReader(fp)
        for div in doc.any_xpath(".//tei:div[@type='article']"):
            refine_tei.make_items_in_article(div)
            refine_tei.make_lists(div)
            refine_tei.remove_paras_with_only_list(doc)
        doc.tree_to_file(fp)