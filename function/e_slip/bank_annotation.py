import cv2
import numpy as np
import os 
from function.e_slip.preprocess import preprocess_bank_slip_for_template_matching

def multi_scale_template_matching(image, template, scales=[0.5, 0.75, 1.0, 1.25, 1.5]):
    best_max_val = -1
    best_max_loc = None
    best_scale = 1.0
    
    image, template = preprocess_bank_slip_for_template_matching(image, template)
    
    for scale in scales:
        # Resize template
        width = int(template.shape[1] * scale)
        height = int(template.shape[0] * scale)
        resized_template = cv2.resize(template, (width, height))
        
        # Skip if template is larger than image
        if resized_template.shape[0] > image.shape[0] or resized_template.shape[1] > image.shape[1]:
            continue
            
        # Perform template matching
        result = cv2.matchTemplate(image, resized_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        # Update best match if current match is better
        if max_val > best_max_val:
            best_max_val = max_val
            best_max_loc = max_loc
            best_scale = scale
            best_resized_template = resized_template

    box_image = image.copy()
    # convert to rgb
    box_image = cv2.cvtColor(box_image, cv2.COLOR_GRAY2BGR)
    # draw box
    cv2.rectangle(
        box_image, 
        best_max_loc, 
        (best_max_loc[0] + best_resized_template.shape[1], best_max_loc[1] + best_resized_template.shape[0]), 
        (0, 255, 0), 
        2
    )
    
    return best_scale, best_max_val, best_max_loc, box_image

def flann_matching(image, object):
    # Initiate SIFT detector
    sift = cv2.SIFT_create()
    
    # find the keypoints and descriptors with SIFT
    kp1, des1 = sift.detectAndCompute(image,None)
    kp2, des2 = sift.detectAndCompute(object,None)
    
    # FLANN parameters
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
    search_params = dict(checks=50)   # or pass empty dictionary
    
    flann = cv2.FlannBasedMatcher(index_params,search_params)
    
    matches = flann.knnMatch(des2,des1,k=2)
    
    # Need to draw only good matches, so create a mask
    matchesMask = [[0,0] for i in range(len(matches))]
    
    # ratio test as per Lowe's paper
    good_matches = []
    for i,(m,n) in enumerate(matches):
        if m.distance < 0.7*n.distance:
            matchesMask[i]=[1,0]
            good_matches.append(m)
    
    draw_params = dict(matchColor = (0,255,0),
                    singlePointColor = (255,0,0),
                    matchesMask = matchesMask,
                    flags = cv2.DrawMatchesFlags_DEFAULT)
    
    result = cv2.drawMatchesKnn(object,kp2,image,kp1,matches,None,**draw_params)

    return result, len(good_matches)

def annotation_bank(img, template_path):
    objects = os.listdir(template_path)
    best_match = (0, None)
    best_max_val = 0

    if isinstance(img, str):
        img = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
    elif isinstance(img, np.ndarray):
        img = img
    else:
        print(f"Error: Invalid image path or type: {type(img)}")
        return None

    for object in objects:

        banks = os.listdir(os.path.join(template_path, object))

        for bank in banks:
            temp = os.path.join(template_path, object, bank)
            template_img = cv2.imread(temp, cv2.IMREAD_GRAYSCALE)

            print(f'template: {bank}')

            print(f'    - Template Matching Method')
            scales = np.arange(0.1, 2.0, 0.1)
            best_scale, best_max_val, best_max_loc, box_image = multi_scale_template_matching(img, template_img, scales)
            print(f'        Best scale: {float(best_scale):.1f}')
            print(f'        Best max value: {float(best_max_val):.4f}')
            if best_max_val > 0.7:
                best_match = (best_max_val, object)
                break

            # flann matching
            print(f'    - Flann Matching Method')
            flann_result, flann_good_match = flann_matching(img, template_img)
            print(f'        flann good match: {flann_good_match}')
                
            if flann_good_match > best_match[0]:
                best_match = (flann_good_match, object)

            if best_match[0] > 50:
                break

        if best_match[0] > 50 or best_max_val > 0.7:
            break
    
    return best_match[1]
