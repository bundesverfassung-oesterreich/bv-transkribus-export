import csv
import logging
from pathlib import Path
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests

from farbkeil_checker import check_image, template_path

BASELINE_CSV_PATH = Path("image_check_results_baseline.csv")
BASE_URL = "https://viewer.acdh.oeaw.ac.at/viewer/sourcefile"
OUTPUT_DIR = Path("images")
CSV_PATH = Path("image_check_results.csv")
# Set to True to download images again even if they already exist.
OVERWRITE_IMAGES = False
IDS = [
    "bv_doc_id__76",
    "bv_doc_id__109",
    "bv_doc_id__110",
    "bv_doc_id__112",
    "bv_doc_id__113",
    "bv_doc_id__118",
    "bv_doc_id__119",
    "bv_doc_id__120",
    "bv_doc_id__121",
    "bv_doc_id__123",
    "bv_doc_id__124",
    "bv_doc_id__126",
    "bv_doc_id__127",
    "bv_doc_id__130",
    "bv_doc_id__134",
    "bv_doc_id__137",
]


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def get_first_image_url(mets_xml: bytes) -> str:
    """Extract the first image URL from <mets:fileGrp USE="DEFAULT">."""
    root = ET.fromstring(mets_xml)

    mets_ns = "http://www.loc.gov/METS/"
    xlink_ns = "http://www.w3.org/1999/xlink"

    file_grp = root.find(
        f'.//{{{mets_ns}}}fileGrp[@USE="DEFAULT"]'
    )

    if file_grp is None:
        raise ValueError(
            'Could not find <mets:fileGrp USE="DEFAULT">'
        )

    file_elem = file_grp.find(
        f"{{{mets_ns}}}file"
    )

    if file_elem is None:
        raise ValueError(
            "DEFAULT fileGrp contains no files"
        )

    flocat = file_elem.find(
        f"{{{mets_ns}}}FLocat"
    )

    if flocat is None:
        raise ValueError(
            "First file contains no FLocat"
        )

    image_url = flocat.get(
        f"{{{xlink_ns}}}href"
    )

    if not image_url:
        raise ValueError(
            "FLocat has no xlink:href"
        )

    return image_url


def fetch_and_check(
    doc_id: str,
    session: requests.Session,
) -> tuple:
    """Fetch METS, download the first image, and run check_image."""

    logging.info(
        "Fetching METS for %s",
        doc_id,
    )

    response = session.get(
        BASE_URL,
        params={"id": doc_id},
        timeout=30,
    )
    response.raise_for_status()

    image_url = get_first_image_url(
        response.content
    )

    # Handle relative image URLs.
    image_url = urljoin(
        response.url,
        image_url,
    )

    logging.info(
        "Image URL for %s: %s",
        doc_id,
        image_url,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = OUTPUT_DIR / f"{doc_id}.jpg"

    # Reuse an existing image unless overwriting is enabled.
    if output_path.exists() and not OVERWRITE_IMAGES:
        logging.info(
            "Image already exists, skipping download: %s",
            output_path,
        )

    else:
        logging.info(
            "Downloading image for %s",
            doc_id,
        )

        image_response = session.get(
            image_url,
            timeout=60,
        )
        image_response.raise_for_status()

        output_path.write_bytes(
            image_response.content
        )

        logging.info(
            "Saved %s",
            output_path,
        )

    # check_image returns two values.
    is_there, value = check_image(
        output_path,
        template_path,
    )

    logging.info(
        "check_image(%s) returned: %r",
        doc_id,
        (is_there, value),
    )

    return is_there, value


def process_ids(ids: list[str]) -> None:
    """Process all IDs and save check_image results to CSV."""

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(METS image downloader)"
            ),
        }
    )

    with CSV_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.writer(csv_file)

        writer.writerow(
            [
                "id",
                "first_val",
                "second_val",
            ]
        )

        for doc_id in ids:
            try:
                is_there, value = fetch_and_check(
                    doc_id,
                    session,
                )

                writer.writerow(
                    [
                        doc_id,
                        is_there,
                        value,
                    ]
                )

                # Make sure the result is written immediately.
                csv_file.flush()

            except requests.RequestException as exc:
                logging.error(
                    "Error fetching image for %s: %s",
                    doc_id,
                    exc,
                )

            except (
                ET.ParseError,
                ValueError,
            ) as exc:
                logging.error(
                    "Error parsing METS for %s: %s",
                    doc_id,
                    exc,
                )

            except Exception:
                # A failure for one ID must not stop the batch.
                logging.exception(
                    "Unexpected error processing %s",
                    doc_id,
                )

def compare_with_baseline(
    results_path: Path,
    baseline_path: Path,
) -> None:
    """Compare first_val in the results CSV with the baseline CSV."""

    # Read baseline: id -> first_val
    baseline = {}

    with baseline_path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            baseline[row["id"]] = row["first_val"]

    # Read current results and compare.
    with results_path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            doc_id = row["id"]
            current_value = row["first_val"]

            if doc_id not in baseline:
                logging.warning(
                    "%s: not found in baseline",
                    doc_id,
                )
                continue

            baseline_value = baseline[doc_id]

            if current_value == baseline_value:
                logging.info(
                    "%s: MATCH (%s)",
                    doc_id,
                    current_value,
                )
            else:
                logging.warning(
                    "%s: DIFFERENCE - baseline=%s, current=%s",
                    doc_id,
                    baseline_value,
                    current_value,
                )

if __name__ == "__main__":
    process_ids(IDS)
    compare_with_baseline(
        Path("image_check_results.csv"),
        BASELINE_CSV_PATH,
    )