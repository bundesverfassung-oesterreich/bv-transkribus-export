#!/bin/bash
EDITIONSPATH="./editions_source"
METSPATH="./mets"
LOGPATH="./logs/malformed_files.csv"
if [ -d "$EDITIONSPATH" ]; then rm -r "$EDITIONSPATH"; fi
if [ -d "$METSPATH" ]; then rm -r "$METSPATH"; fi
if [ -f "$LOGPATH" ]; then rm -r "$LOGPATH"; fi
mkdir -p "$METSPATH"
mkdir -p "$EDITIONSPATH"