for file in ./mets/*/*_mets.xml
  do
  new=$(echo "$file" | sed "s@_mets.xml@_tei.xml@g")
  echo "transforming $file to $new"
  java -jar ./saxon/saxon9he.jar -xsl:./page2tei/page2tei-0.xsl -s:$file -o:$new
  done
echo "done with xslt"
echo "refining created tei"
python ./scripts/refine_tei.py