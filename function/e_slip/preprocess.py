import cv2
import numpy as np
import math

def resize_image(image, width):
    height = int(image.shape[0] * (width / image.shape[1]))
    return cv2.resize(image, (width, height))

def cut_image(image):
    h, w = image.shape
    return image[0:math.ceil(h/1.5), 0:w]

def preprocess_bank_slip(img):
    if isinstance(img, str):
        image = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
    elif isinstance(img, np.ndarray):
        image = img
    else:
        print(f"Error: Invalid image path or type: {type(img)}")
        return None

    if image is None:
        print(f"Error: Could not load image at {img}")
        return None

    thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    return thresh

def preprocess_bank_slip_for_template_matching(image, template):
    # resize image width
    image = resize_image(image, 1000)
    # cut half of image
    image = cut_image(image)
    
    # resize object width
    template = resize_image(template, 240)

    # gaussian blur image
    image = cv2.GaussianBlur(image, (3, 3), 0)
    template = cv2.GaussianBlur(template, (3, 3), 0)
    
    image = preprocess_bank_slip(image)
    template = preprocess_bank_slip(template)

    return image, template
