mkdir -p alltei
for file in ./metsout/*.xml
  do 
  new=$(echo "$file" | sed "s@_mets.xml@_tei.xml@g")
  new=$(echo "$new" | sed "s@metsout@alltei@g")
  echo "$file $new"
  java -jar ./saxon/saxon9he.jar -xsl:./page2tei/page2tei-0.xsl -s:$file -o:$new
done