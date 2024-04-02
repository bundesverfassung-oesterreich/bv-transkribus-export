# bv-transkribus-export
Repository to export edition data from transkribus.
If you want to modify data manually and the desired file doesn’t exist yet in the target directory, copy the source document from the editions_source folder to the editions folder in the bv-working-data repository.

Documents in the editions_source folder get published online if there isn’t a better version in the editions folder of the bv-working-data repository.


## install
* run `./script.sh` to install saxon, fundament...
* create a virtual env e.g. `virtualenv env`; source it `source env/bin/activate` and run `pip install -r requirements.txt && wget https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-7J.zip/download && unzip download -d saxon && rm -rf download && git clone --depth=1 --branch skurzinz-patch-1 --single-branch https://github.com/skurzinz/page2tei.git`
