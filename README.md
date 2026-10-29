# bv-transkribus-export
Repository to export edition data from transkribus.
If you want to modify data manually and the desired file doesn’t exist yet in the target directory, copy the source document from the editions_source folder to the editions folder in the bv-working-data repository.

Documents in the editions_source folder get published online if there isn’t a better version in the editions folder of the bv-working-data repository.

The repository also contains a standalone image-only TEI generator for documents that should not be transcribed. If you want to skip transcription via Transkribus set a checkmark in the documents baserow entrys `skip_transcription`-field. The script then reads the metadata, fetches the Goobi manifest for the image links, and writes the resulting TEI files directly into `editions_source`. Existing files with the same `bv_id` are overwritten, and malformed or missing-manifest cases are logged in `./logs/malformed_files.csv`.

## Image-only IIIF export fields

Every page of an image-only document is represented by a complete, dereferenceable IIIF link:

```xml
<surface xml:id="facs_1" ulx="0" uly="0" lrx="2645" lry="4250">
  <graphic url="https://viewer.acdh.oeaw.ac.at/viewer/api/v1/records/bv_doc_id__100/files/images/IMG_0086.tif/info.json"
           width="2645px" height="4250px"/>
</surface>
```

- `@url`: full IIIF Image API endpoint (`.../info.json`) — openable as-is, no URL heuristics needed
- `@width`, `@height`: image dimensions from that `info.json`
- `surface/@lrx`, `surface/@lry`: the same dimensions as plain numbers, matching the convention used for transcribed documents

`@url` intentionally does **not** point to a rendered JPEG (`.../full/full/0/default.jpg`): that is a derivative, not an identity.

### Where the link comes from

The exporter reads the document manifest (`.../records/{bv_id}/manifest`), which lists every page's IIIF image service, so one request covers the whole document. If the manifest is unavailable, each page is probed directly (`{id}.tif/info.json`, then `{id}/info.json`).

If IIIF resolution fails for a page, the exporter falls back to the bare image id (`.../images/{image_name}`) and omits `@width`/`@height`/`@lrx`/`@lry`. A document is never skipped because of unavailable IIIF metadata.
