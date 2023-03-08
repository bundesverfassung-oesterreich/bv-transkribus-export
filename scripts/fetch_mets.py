import os
from transkribus_utils.transkribus_utils import ACDHTranskribusUtils
from refine_tei import load_metadata_from_dump

user = os.environ.get("TR_USER")
pw = os.environ.get("TR_PW")
BASE_ROW_DUMP_URL = "https://raw.githubusercontent.com/bundesverfassung-oesterreich/bv-entities/main/json_dumps/document.json"

transkribus_client = ACDHTranskribusUtils(
    user=user, password=pw, transkribus_base_url="https://transkribus.eu/TrpServer/rest"
)
for collection_id in load_metadata_from_dump():
    transkribus_client.collection_to_mets(collection_id, file_path="./mets")
