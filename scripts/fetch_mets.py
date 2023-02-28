import os
from transkribus_utils.transkribus_utils import ACDHTranskribusUtils

user = os.environ.get("TR_USER")
pw = os.environ.get("TR_PW")
col_id = os.environ.get("TR_COL_ID", "188933")
os.makedirs("./mets", exist_ok=True)

transkribus_client = ACDHTranskribusUtils(
    user=user, password=pw, transkribus_base_url="https://transkribus.eu/TrpServer/rest"
)

mpr_docs = transkribus_client.collection_to_mets(col_id, file_path="./mets")
