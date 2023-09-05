# bv-transkribus-export-play
repo to export data from transkribus


## install
* run `./script.sh` to install saxon, fundament...
* create a virtual env e.g. `virtualenv env`; source it `source env/bin/activate` and run `pip install -r requirements.txt && wget https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-7J.zip/download && unzip download -d saxon && rm -rf download && git clone --depth=1 --branch skurzinz-patch-1 --single-branch https://github.com/skurzinz/page2tei.git`
