#  download tesseract-ocr-w64-setup-5.5.0.20241111.exe (64 bit)
#  from - https://github.com/UB-Mannheim/tesseract/wiki
import pytesseract
from pytesseract import Output
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from typing import Tuple
import random
import cv2
from .preprocess import preprocess_bank_slip

def get_random_rgb_tuple() -> Tuple[int, int, int]:
    return (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255)
    )

def ocr_pytesseract(img):

    img = preprocess_bank_slip(img)
    text = pytesseract.image_to_string(img, lang='tha+eng')
    d = pytesseract.image_to_data(img, lang='tha+eng', output_type=Output.DICT)

    n_boxes = len(d['level'])
    box_image = img.copy()
    box_image = cv2.cvtColor(box_image, cv2.COLOR_GRAY2BGR)
    for i in range(n_boxes):
        (x, y, w, h) = (d['left'][i], d['top'][i], d['width'][i], d['height'][i])
        # convert to rgb
        box = cv2.rectangle(box_image, (x, y), (x + w, y + h), get_random_rgb_tuple(), 2)

    return text, box