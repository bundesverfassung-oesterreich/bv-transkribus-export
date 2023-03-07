mkdir -p alltei
for file in ./mets/*/*_mets.xml
  do
  new=$(echo "$file" | sed "s@_mets.xml@_tei.xml@g")
  echo "transforming $file to $new"
  java -jar ./saxon/saxon9he.jar -xsl:./page2tei/page2tei-0.xsl -s:$file -o:$new
  #python ./scripts/copy_transcribus_ids.py $file $new
  #rm file
  done

echo "refining created tei"
python ./scripts/refine_tei.py