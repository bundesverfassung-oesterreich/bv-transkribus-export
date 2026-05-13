# bv-transkribus-export
Repository to export edition data from transkribus.
If you want to modify data manually and the desired file doesn’t exist yet in the target directory, copy the source document from the editions_source folder to the editions folder in the bv-working-data repository.

Documents in the editions_source folder get published online if there isn’t a better version in the editions folder of the bv-working-data repository.

The repository also contains a standalone image-only TEI generator for documents that should not be transcribed. If you want to skip transcription via Transkribus set a checkmark in the documents baserow entrys `skip_transcription`-field. The script then reads the metadata, fetches the Goobi manifest for the image links, and writes the resulting TEI files directly into `editions_source`. Existing files with the same `bv_id` are overwritten, and malformed or missing-manifest cases are logged in `./logs/malformed_files.csv`.
