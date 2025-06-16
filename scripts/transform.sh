xsl_path="./page2tei/page2tei-0.xsl"
if [ ! -f  $xsl_path ]; then echo "xsl script $xsl_path not found!" & exit 1; fi
for file in ./mets/*/*_mets.xml
  do
  new=$(echo "$file" | sed "s@_mets.xml@_tei.xml@g")
  echo "transforming $file to $new"
  java -jar ./saxon/saxon9he.jar -xsl:$xsl_path -s:$file -o:$new combine='true()'
  done
echo "done with xslt"
echo "refining created tei"
python ./scripts/refine_tei.py