from ultralytics import YOLO
import cv2
import pandas as pd
import numpy as np
import os
from PIL import Image
from pathlib import Path
# import matplotlib.pylab as plt
import matplotlib.pyplot as plt
import pillow_heif
import sys
import imutils
from operator import itemgetter
from glob import glob
from scipy.spatial import distance as dist
import pytesseract
import json
import re
from function.physical.extract_info import bkk_extracted, kplus_extracted, krungthai_extracted
from function.e_slip.ocr_tesseract import ocr_pytesseract

# Register HEIC support
pillow_heif.register_heif_opener()
def convert_heic_or_heif_to_jpeg(filepath):
    try:
        img = Image.open(filepath).convert("RGB")
        return np.array(img)  # Return image as NumPy array
    except Exception as e:
        return None 

# resize image for display
def resize(image, max_width=1280, max_height=720):
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height)
    if scale < 1.0:
        image = cv2.resize(image, (int(width * scale), int(height * scale)))
    return image

def get_4_coordinates(binary,gray_image):
    # find the largest contour in the threshold image
    cnts = cv2.findContours(binary.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    c = max(cnts, key=cv2.contourArea)
    (x, y, w, h) = cv2.boundingRect(c)

    # to demonstrate the impact of contour approximation -> loop over a number of epsilon sizes
    for eps in np.linspace(0.001, 0.05, 10):
        # approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, eps * peri, True)

        # draw the approximated contour on the image
        detected_4_coor_with_contour = gray_image.copy()
        cv2.drawContours(detected_4_coor_with_contour, [approx], -1, (0, 255, 0), 3)
        text = "eps={:.4f}, num_pts={}".format(eps, len(approx))
        cv2.putText(detected_4_coor_with_contour, text, (x, y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        
        if len(approx)==4:
            break

    if len(approx)==4:
        corners = approx.reshape(4, 2)  # reshape to (4, 2) for convenience
        for i, point in enumerate(corners):
            x, y = point

        # sort the corners for perspective transform
        # Use top-left, top-right, bottom-right, bottom-left order
        def sort_corners(pts):
            pts = pts[np.argsort(pts[:, 1])]  # sort by y (top to bottom)
            top, bottom = pts[:2], pts[2:]
            # sort top by x (left to right)
            top = top[np.argsort(top[:, 0])]
            # sort bottom by x (left to right, not reversed anymore)
            bottom = bottom[np.argsort(bottom[:, 0])]
            # order: TL, TR, BL, BR
            return np.array([top[0], top[1], bottom[0], bottom[1]])

        ordered_corners = sort_corners(corners)
    else:
        print(f"ERROR: Got {len(approx)} points — not a quadrilateral. Try adjusting epsilon.")
        sys.exit(0)
    
    return ordered_corners, detected_4_coor_with_contour

def process_physical_slip(image_path, model_path=r'models\best.pt'):

    # supported filetype
    img_ext_list = ['.jpg','.JPG','.jpeg','.JPEG','.png','.PNG','.bmp','.BMP']

    # check image type
    file_extension = os.path.splitext(image_path)[1]
    # change image type(if .heif/.heic)
    if file_extension in img_ext_list:
        # read image
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    elif (file_extension=='.HEIC'or file_extension=='.heic'or file_extension=='.HEIF'or file_extension=='.heif'):
        # convert to .JPEG
        image = convert_heic_or_heif_to_jpeg(image_path) # return as np array
        if image is None:
            print('ERROR: HEIC/HEIF file conversion failed. Please check the file.')
            sys.exit(0)
    else:
        print(f'Input {image_path} is invalid. Please try again.')
        sys.exit(0)

    # load YOLO model and get labelmap
    model = YOLO(model_path, task='detect') # task='detect' => obj detection => get bb and class
    labels = model.names # is to map between class id and classname 

    # resize for appropriate scale
    image = resize(image)

    # rescale color scale -> effect model's confidence percentage
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    # -------image preprocessing--------
    # run detection
    results = model(image)
    # get the results
    detections = results[0].boxes

    # project scope => 1 image = 1 receipt
    for i in range(0,1): # if there are several obj, get the first one
        # get bounding box coordinates
        # Ultralytics returns results in Tensor format, which have to be converted to a regular Python array
        xyxy_tensor = detections[i].xyxy.cpu() # Detections in Tensor format in CPU memory
        xyxy = xyxy_tensor.numpy().squeeze() # Convert tensors to Numpy array
        xmin, ymin, xmax, ymax = xyxy.astype(int) # Extract individual coordinates and convert to int

        # get classname
        classidx = int(detections[i].cls.item())
        classname = labels[classidx] # map to get classname of the obj

        # get confidence
        conf = detections[i].conf.item()

        # cropped 
        # roi = img[y1:y2,x1:x2]
        after_yolo = image[ymin:ymax,xmin:xmax]

    # ---perspective transformation---
    # edge detection
    gray_image = cv2.cvtColor(after_yolo, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray_image, 127, 255, cv2.THRESH_BINARY)

    # get 4 coordinates for perspective transformation
    # optimize image before go get 4 coordinates
    blurred = cv2.GaussianBlur(gray_image,(3,3),0) 
    thresh = cv2.adaptiveThreshold(blurred, 255,
                                   cv2.ADAPTIVE_THRESH_MEAN_C, 
                                   cv2.THRESH_BINARY_INV, 21, 10)
    _,binaryInv = cv2.threshold(thresh, 0, 255, cv2.THRESH_BINARY_INV)
    # get 4 coordinates
    # corners' order=TL, TR, BL, BR
    corners, detected_4_coor_with_contour = get_4_coordinates(binaryInv,gray_image) #binary
    # for i,(x,y) in enumerate(corners):
    #     print(f"Corner {i + 1}: (x={x}, y={y})")
    
    #assign corners
    topLeft = corners[0]
    topRight = corners[1]
    bottomLeft = corners[2]
    bottomRight = corners[3]
    x1, y1 = topLeft
    x2, y2 = topRight
    x3, y3 = bottomLeft
    x4, y4 = bottomRight

    # euclidean (distance between 2 points in linear)
    upperLine = dist.euclidean((x1,y1),(x2,y2))
    lowerLine = dist.euclidean((x3,y3),(x4,y4))
    leftmostLine = dist.euclidean((x1,y1),(x3,y3))
    rightmostLine = dist.euclidean((x2,y2),(x4,y4))

    width = round(max(upperLine,lowerLine))
    height = round(max(leftmostLine, rightmostLine))

    # print(f"upperline: {upperLine}")
    # print(f"lowerLine: {lowerLine}")
    # print(f"leftmostLine: {leftmostLine}")
    # print(f"rightmostLine: {rightmostLine}")
    # print(f"width: {width}")
    # print(f"height: {height}")

    # perspective transformation
    if height>=width: # normal case
        pts1 = np.float32([[x1,y1],[x2,y2],[x3,y3],[x4,y4]]) # original coordinates
        pts2 = np.float32([[0,0],[width,0],[0,height],[width,height]]) # transformed pixel
        M = cv2.getPerspectiveTransform(pts1,pts2)
        perspective_trans = cv2.warpPerspective(gray_image,M,(width,height))
    if width>height: # 180 degree case -> need rotation -> in case photo flip accidentally
        pts1 = np.float32([[x1,y1],[x2,y2],[x3,y3],[x4,y4]]) # original coordinates
        pts2 = np.float32([[0,width],[0,0],[height,width],[height,0]])
        M = cv2.getPerspectiveTransform(pts1,pts2)
        perspective_trans = cv2.warpPerspective(gray_image,M,(height,width))

    # adaptive thresholding -> for handle image with shadow
    # blur for make edges softer
    blurred = cv2.GaussianBlur(perspective_trans,(3,3),0) 
    
    thresh = cv2.adaptiveThreshold(perspective_trans, 255,
                                   cv2.ADAPTIVE_THRESH_MEAN_C, 
                                   cv2.THRESH_BINARY_INV, 21, 10)
    _,binaryInv = cv2.threshold(thresh, 0, 255, cv2.THRESH_BINARY_INV)

    # --------OCR--------
    # pytesseract
    custom_config = r'--oem 3 --psm 6'
    textPytess = pytesseract.image_to_string(binaryInv, lang='tha+eng', config=custom_config)               
    #perspective_trans
    # print("-----------PYTESSERACT------------")
    # print(textPytess)

    lines = textPytess.splitlines()

    with open("pytesseract.json", "w", encoding="utf-8") as f:
        json.dump({"lines": lines}, f, ensure_ascii=False, indent=4)

    # regex
    extracted_text = None

    if classname=='bkk':
        extracted_text = bkk_extracted(lines)

    if classname=='kplus':
        extracted_text = kplus_extracted(lines)
    
    if classname=='krungthai':
        extracted_text = krungthai_extracted(lines)

    if classname=='scb':
        extracted_text = lines


    # return json (info in image)
    return image, after_yolo, conf, classname, binary, detected_4_coor_with_contour, perspective_trans, thresh, binaryInv, extracted_text
