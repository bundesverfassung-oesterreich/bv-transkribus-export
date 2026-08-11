import cv2
import os


img_path = "./farbkeil_checker_resources/testimage/"
template_path = "./farbkeil_checker_resources/template_2.jpg"

SIFT_THRESHOLD = 20
COLOR_THRESHOLD = 0.4
SIFT_WEIGHT = 0.8
COLOR_WEIGHT = 0.2
DECISION_THRESHOLD = 0.9


def check_image(image_path, template_path):
    # Bilder laden
    img = cv2.imread(image_path)
    template = cv2.imread(template_path)

    # Graumodus für SIFT
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(
        template,
        cv2.COLOR_BGR2GRAY,
    )

    # SIFT-Detektor initialisieren
    sift = cv2.SIFT_create()

    # Keypoints und Descriptors finden
    kp1, des1 = sift.detectAndCompute(
        template_gray,
        None,
    )
    kp2, des2 = sift.detectAndCompute(
        img_gray,
        None,
    )

    # FLANN-Matcher
    FLANN_INDEX_KDTREE = 1

    index_params = dict(
        algorithm=FLANN_INDEX_KDTREE,
        trees=5,
    )

    search_params = dict(
        checks=50,
    )

    flann = cv2.FlannBasedMatcher(
        index_params,
        search_params,
    )

    # Punkte vergleichen
    matches = flann.knnMatch(
        des1,
        des2,
        k=2,
    )

    # Lowe's Ratio Test
    good_matches = []

    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)

    sift_matches = len(good_matches)

    # ---------------------------------------------------------
    # Farbvergleich
    # ---------------------------------------------------------

    img_hsv = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2HSV,
    )

    template_hsv = cv2.cvtColor(
        template,
        cv2.COLOR_BGR2HSV,
    )

    color_matches = 0

    for match in good_matches:
        template_point = kp1[match.queryIdx].pt
        image_point = kp2[match.trainIdx].pt

        tx, ty = map(int, template_point)
        ix, iy = map(int, image_point)

        if (
            not (
                0 <= tx < template_hsv.shape[1]
                and 0 <= ty < template_hsv.shape[0]
            )
            or not (
                0 <= ix < img_hsv.shape[1]
                and 0 <= iy < img_hsv.shape[0]
            )
        ):
            continue

        template_color = template_hsv[ty, tx]
        image_color = img_hsv[iy, ix]

        color_distance = cv2.norm(
            template_color.astype(float),
            image_color.astype(float),
            cv2.NORM_L2,
        )

        if color_distance < 40:
            color_matches += 1

    # Farbwert zwischen 0 und 1
    if sift_matches > 0:
        color_value = color_matches / sift_matches
    else:
        color_value = 0.0

    # ---------------------------------------------------------
    # Kombinierter Entscheidungswert
    # ---------------------------------------------------------

    # SIFT-Wert auf 0..1 normalisieren.
    sift_value = min(
        sift_matches / SIFT_THRESHOLD,
        1.0,
    )

    # Beide Werte berücksichtigen.
    decision_value = (
        SIFT_WEIGHT * sift_value
        + COLOR_WEIGHT * color_value
    )

    # Finale Entscheidung
    is_there = (
        sift_matches >= 140
        and (
            decision_value >= 0.87
            or (
                sift_matches >= 165
                and color_value >= 0.25
            )
        )
    )

    return (
        sift_matches,
        color_value,
        is_there,
        decision_value,
    )
