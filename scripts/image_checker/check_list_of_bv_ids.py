import csv
import logging
from pathlib import Path
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests

from farbkeil_checker import check_image, template_path


LOG_PATH = Path("image_check.log")
BASE_URL = "https://viewer.acdh.oeaw.ac.at/viewer/sourcefile"

OUTPUT_DIR = Path("images")
CSV_PATH = Path("image_check_results.csv")
BASELINE_CSV_PATH = Path("image_check_results_baseline.csv")

# Wenn False, werden bereits vorhandene Bilder wiederverwendet.
# Wenn True, werden die Bilder immer erneut heruntergeladen.
OVERWRITE_IMAGES = False

# Wenn True, wird zusätzlich die zweite Seite geprüft.
TEST_AGAINST_OTHER = True

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
    handlers=[
        logging.FileHandler(
            LOG_PATH,
            encoding="utf-8",
        ),
        logging.StreamHandler(),  # keep console output as well
    ],
)

def get_image_urls(mets_xml: bytes) -> list[str]:
    """Extract all image URLs from <mets:fileGrp USE="DEFAULT">."""

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

    image_urls = []

    for file_elem in file_grp.findall(
        f"{{{mets_ns}}}file"
    ):
        flocat = file_elem.find(
            f"{{{mets_ns}}}FLocat"
        )

        if flocat is None:
            continue

        image_url = flocat.get(
            f"{{{xlink_ns}}}href"
        )

        if image_url:
            image_urls.append(image_url)

    if not image_urls:
        raise ValueError(
            'No images found in <mets:fileGrp USE="DEFAULT">'
        )

    return image_urls


def download_image(
    image_url: str,
    output_path: Path,
    session: requests.Session,
) -> None:
    """Download an image unless it already exists."""

    if output_path.exists() and not OVERWRITE_IMAGES:
        logging.info(
            "Image already exists, skipping download: %s",
            output_path,
        )
        return

    logging.info(
        "Downloading image: %s",
        image_url,
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


def fetch_and_check(
    doc_id: str,
    session: requests.Session,
) -> tuple:
    """
    Fetch METS, check page 1 and optionally page 2.

    Returns:
        (
            sift_matches,
            color_value,
            is_there,
            decision_value,
            false_positive,
            second_sift_matches,
            second_color_value,
            second_is_there,
            second_decision_value,
        )
    """

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

    image_urls = get_image_urls(
        response.content
    )

    logging.info(
        "Found %d image(s) for %s",
        len(image_urls),
        doc_id,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # =========================================================
    # PAGE 1
    # =========================================================

    first_image_url = urljoin(
        response.url,
        image_urls[0],
    )

    logging.info(
        "Page 1 image URL for %s: %s",
        doc_id,
        first_image_url,
    )

    output_path = (
        OUTPUT_DIR / f"{doc_id}.jpg"
    )

    download_image(
        first_image_url,
        output_path,
        session,
    )

    (
        sift_matches,
        color_value,
        is_there,
        decision_value,
    ) = check_image(
        output_path,
        template_path,
    )

    logging.info(
        "check_image(%s page 1): "
        "sift_matches=%d, "
        "color_value=%.3f, "
        "is_there=%s, "
        "decision_value=%.3f",
        doc_id,
        sift_matches,
        color_value,
        is_there,
        decision_value,
    )

    # Ursprünglichen Wert von Seite 1 merken.
    page1_is_there = is_there

    # =========================================================
    # PAGE 2 / OTHER PAGE
    # =========================================================

    false_positive = False

    second_sift_matches = None
    second_color_value = None
    second_is_there = None
    second_decision_value = None

    if TEST_AGAINST_OTHER:

        if len(image_urls) > 1:

            second_image_url = urljoin(
                response.url,
                image_urls[1],
            )

            logging.info(
                "Page 2 image URL for %s: %s",
                doc_id,
                second_image_url,
            )

            second_output_path = (
                OUTPUT_DIR / f"{doc_id}_page2.jpg"
            )

            download_image(
                second_image_url,
                second_output_path,
                session,
            )

            (
                second_sift_matches,
                second_color_value,
                second_is_there,
                second_decision_value,
            ) = check_image(
                second_output_path,
                template_path,
            )

            logging.info(
                "check_image(%s page 2): "
                "sift_matches=%d, "
                "color_value=%.3f, "
                "is_there=%s, "
                "decision_value=%.3f",
                doc_id,
                second_sift_matches,
                second_color_value,
                second_is_there,
                second_decision_value,
            )

            # -------------------------------------------------
            # False Positive Detection
            # -------------------------------------------------

            if page1_is_there and second_is_there:
                false_positive = True

                logging.warning(
                    "%s: FALSE POSITIVE - "
                    "page 1 and page 2 both detected "
                    "a color card",
                    doc_id,
                )
                input("Press Enter to continue...")

            else:
                logging.info(
                    "%s: page comparison OK - "
                    "page1=%s, page2=%s",
                    doc_id,
                    page1_is_there,
                    second_is_there,
                )

        else:
            logging.warning(
                "%s: cannot test another page - "
                "METS contains only %d image(s)",
                doc_id,
                len(image_urls),
            )

    return (
        sift_matches,
        color_value,
        is_there,
        decision_value,
        false_positive,
        second_sift_matches,
        second_color_value,
        second_is_there,
        second_decision_value,
    )


def process_ids(ids: list[str]) -> None:
    """Process all IDs and save results to CSV."""

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
                "sift_matches",
                "color_value",
                "is_there",
                "decision_value",
                "false_positive",
                "second_sift_matches",
                "second_color_value",
                "second_is_there",
                "second_decision_value",
            ]
        )

        for doc_id in ids:
            try:

                (
                    sift_matches,
                    color_value,
                    is_there,
                    decision_value,
                    false_positive,
                    second_sift_matches,
                    second_color_value,
                    second_is_there,
                    second_decision_value,
                ) = fetch_and_check(
                    doc_id,
                    session,
                )

                writer.writerow(
                    [
                        doc_id,
                        sift_matches,
                        color_value,
                        is_there,
                        decision_value,
                        false_positive,
                        second_sift_matches,
                        second_color_value,
                        second_is_there,
                        second_decision_value,
                    ]
                )

                # Ergebnis sofort auf die Festplatte schreiben.
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
                # Ein Fehler darf den gesamten Batch nicht stoppen.
                logging.exception(
                    "Unexpected error processing %s",
                    doc_id,
                )


def compare_with_baseline(
    results_path: Path,
    baseline_path: Path,
) -> None:
    """
    Compare final is_there from the results CSV
    with first_val from the baseline CSV.
    """

    baseline = {}

    # =========================================================
    # BASELINE EINLESEN
    # =========================================================

    with baseline_path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        for row in reader:
            baseline[row["id"]] = row["first_val"]

    # =========================================================
    # AKTUELLE ERGEBNISSE EINLESEN
    # =========================================================

    with results_path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        for row in reader:

            doc_id = row["id"]

            # Das ist das finale Ergebnis.
            # Ein False Positive wurde hier bereits
            # auf False gesetzt.
            current_value = row["is_there"]

            if doc_id not in baseline:
                logging.warning(
                    "%s: not found in baseline",
                    doc_id,
                )
                continue

            baseline_value = baseline[doc_id]

            if current_value == baseline_value:

                logging.info(
                    "%s: MATCH - "
                    "baseline=%s, current=%s",
                    doc_id,
                    baseline_value,
                    current_value,
                )

            else:

                logging.warning(
                    "%s: DIFFERENCE - "
                    "baseline=%s, current=%s",
                    doc_id,
                    baseline_value,
                    current_value,
                )
                input("Press Enter to continue...")


if __name__ == "__main__":

    process_ids(IDS)

    compare_with_baseline(
        CSV_PATH,
        BASELINE_CSV_PATH,
    )