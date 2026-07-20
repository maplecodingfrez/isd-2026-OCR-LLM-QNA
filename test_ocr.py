import pytesseract
import cv2

img = cv2.imread(r"outputs\pages\dsba_curriculum_subset_page_002.jpg")
text = pytesseract.image_to_string(img, lang="tha+eng", config="--oem 3 --psm 6")
print(text[:1500])