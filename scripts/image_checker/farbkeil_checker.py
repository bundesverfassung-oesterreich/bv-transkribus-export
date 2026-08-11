import cv2
import os

img_path = './farbkeil_checker_resources/testimage/'
template_path = './farbkeil_checker_resources/farbkeil_template.jpg'


def check_image(image_path, template_path):
    # Bilder im Graumodus laden
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)

    # SIFT-Detektor initialisieren
    sift = cv2.SIFT_create()

    # Erkennungspunkte (Keypoints) und Beschreibungen (Descriptors) finden
    kp1, des1 = sift.detectAndCompute(template, None)
    kp2, des2 = sift.detectAndCompute(img, None)

    # FLANN-Matcher für schnellen Punkte-Abgleich einrichten
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    # Punkte vergleichen
    matches = flann.knnMatch(des1, des2, k=2)

    # Nur gute Treffer behalten (Lowe's Ratio Test)
    good_matches = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)

    print(f"Anzahl guter Übereinstimmungen: {len(good_matches)}")

    # Schwellenwert festlegen (z. B. reichen oft 10-15 exakte Punkt-Treffer)
    if len(good_matches) >= 10:
        return True, len(good_matches)
    else:
        return False, len(good_matches)
for image in os.listdir(img_path):
    print(f"Überprüfe Bild: {image}")
    if image.endswith(('.jpg', '.jpeg', '.png')):
        check_image(os.path.join(img_path, image), template_path)
    else:
        print(f"Datei {image} wird übersprungen.")