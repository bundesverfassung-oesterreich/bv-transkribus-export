import glob
import shutil
import os
from tqdm import tqdm

TRANS_OUT_METS_GLOB = './mets/*/*_mets.xml'
ALL_METS_DIR = './metsout'
files = sorted(glob.glob(TRANS_OUT_METS_GLOB))
os.makedirs(ALL_METS_DIR, exist_ok=True)
print(f"copy files from {TRANS_OUT_METS_GLOB} into {ALL_METS_DIR}")
for x in tqdm(files, total=len(files)):
    _, tail = os.path.split(x)
    dst = os.path.join(ALL_METS_DIR, tail)
    shutil.copyfile(x, dst)
print("done")