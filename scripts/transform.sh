xsl_path="./page2tei/page2tei-0.xsl"

# Space-separated list of IDs to patch before transformation (format: collection-docid)
# e.g. PATCH_IDS="196428-10582280 196428-1529214"
PATCH_IDS="196429-10582300 196429-10582299 196428-10582280 196428-14147345"

pwd
ls ./
if [ ! -f  $xsl_path ]; then echo "xsl script $xsl_path not found!" & exit 1; fi
for file in ./mets/*/*_mets.xml
  do
  new=$(echo "$file" | sed "s@_mets.xml@_tei.xml@g")
  echo "transforming $file to $new"

  # Check if this file is in the patch list
  collection=$(echo "$file" | sed 's@\./mets/\([^/]*\)/.*@\1@')
  docid=$(echo "$file" | sed 's@.*/\([^_]*\)_mets.xml@\1@')
  key="${collection}-${docid}"

  needs_patch=false
  for pid in $PATCH_IDS; do
    if [ "$pid" = "$key" ]; then needs_patch=true; break; fi
  done

  if $needs_patch; then
    echo "  (patching missing @custom attributes for $key)"
    tmpdir=$(mktemp -d)
    src=$(python ./scripts/patch_page_xml.py "$file" "$tmpdir")
    java -jar ./saxon/saxon9he.jar -xsl:$xsl_path -s:$src -o:$new combine='true()'
    rm -rf "$tmpdir"
  else
    java -jar ./saxon/saxon9he.jar -xsl:$xsl_path -s:$file -o:$new combine='true()'
  fi
  done
echo "done with xslt"
echo "refining created tei"
python ./scripts/refine_tei.py