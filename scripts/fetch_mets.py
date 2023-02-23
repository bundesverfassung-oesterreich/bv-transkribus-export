import os
import pandas as pd
from tqdm import tqdm
from transkribus_utils.transkribus_utils import ACDHTranskribusUtils

user = os.environ.get('TR_USER')
pw = os.environ.get('TR_PW')
os.makedirs('./mets', exist_ok=True)

transkribus_client = ACDHTranskribusUtils(
    user=user,
    password=pw,
    transkribus_base_url="https://transkribus.eu/TrpServer/rest"
)

mpr_docs = transkribus_client.collection_to_mets("188933", file_path='./mets')
