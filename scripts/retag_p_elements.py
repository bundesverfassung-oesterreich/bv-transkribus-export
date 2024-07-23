import refine_tei
from acdh_tei_pyutils.tei import TeiReader

def remove_all_lb_elements(doc: TeiReader):
    lb_elements = doc.any_xpath("//tei:lb")
    for lb in lb_elements:
        prev_textnode_result = lb.xpath("./preceding-sibling::node()[1][boolean(self::text())]")
        prev_textnode = prev_textnode_result[0] if prev_textnode_result else None
        lb_parent = lb.getparent()
        if prev_textnode is not None:
            spacer = ""
            if lb.tail is None:
                lb.tail = ""
            if lb.attrib["break"] == "yes":
                # between words
                spacer = " "
            new_prev_textnode = prev_textnode.rstrip() + spacer + lb.tail.lstrip()
            parent = prev_textnode.getparent()
            if prev_textnode.is_tail:
                parent.tail = new_prev_textnode
            else:
                parent.text = new_prev_textnode
            lb.tail = ""
        else:
            prev= lb.getprevious()
            if prev is not None:
                prev.tail = lb.tail
            else:
                lb_parent.text = lb.tail
        lb_parent.remove(lb)

local_name = "local-name()='pb'"
contains_hyphen = "contains(substring(normalize-space(), string-length(normalize-space()) - 1), '-')"
text_test = f"self::text()[{contains_hyphen}]"
preceding_textnode_test = f"preceding-sibling::node()[1][{text_test}]"
preceding_fw_test = f"preceding-sibling::*[local-name()='fw' and {preceding_textnode_test}]"
preceding_test = f"({preceding_textnode_test} or {preceding_fw_test})"
conditions = f"{local_name} and {preceding_test}"
pbs_xpath = f"//*[{conditions}]"

def set_pb_break_attrib(doc: TeiReader):
    pbs = doc.any_xpath(pbs_xpath)
    for pb in pbs:
        pb.attrib["break"] = "no"
        previoustext = pb.xpath("./preceding-sibling::node()[self::text() and normalize-space()!=''][1]")
        if previoustext:
            previoustextnode = previoustext[0]
            textparent = previoustextnode.getparent()
            if previoustextnode.is_tail:
                textparent.tail = textparent.tail.rstrip("\t\n ")
            else:
                textparent.text = textparent.text.rstrip("\t\n ")
    return bool(pbs)


if __name__ == "__main__":
    input_dir="../bv-working-data/data/editions/*.xml"
    print(f"loading xmls from {input_dir}")
    for fp in refine_tei.glob.glob(input_dir):
        print(fp)
        doc = refine_tei.TeiReader(fp)
        #remove_all_lb_elements(doc)
        if set_pb_break_attrib(doc):
            doc.tree_to_file(fp)