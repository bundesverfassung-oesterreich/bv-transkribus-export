EDITIONSPATH="./editions"
METSPATH="./mets"
if [ -d "$EDITIONSPATH" ]; then rm -r "$EDITIONSPATH"; fi
if [ -d "$METSPATH" ]; then rm -r "$METSPATH"; fi
mkdir -p "$METSPATH"
mkdir -p "$EDITIONSPATH"
apt-get update && apt-get install openjdk-11-jre-headless -y --no-install-recommend
pip install -r requirements.txt
wget https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-7J.zip/download && unzip -o download -d saxon && rm -rf download
git clone --depth=1 --branch skurzinz-patch-1 --single-branch https://github.com/skurzinz/page2tei.git