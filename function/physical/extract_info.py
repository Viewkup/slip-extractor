import cv2
import numpy as np
from PIL import Image
import pillow_heif
import sys
import imutils
import re

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

def bkk_extracted(lines):
    def clean_text(text):
        return text.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1').replace(',', '').replace('฿', '').strip()

    # Regex patterns
    date_pattern = r"\b\d{2}/\d{2}/\d{2}\b" 
    time_pattern = r"\b\d{2}:\d{2}\b" 
    withdrawal_pattern = r"\bWITHDRAWAL\b"
    amount_pattern = r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})\b" 
    avail_bal_label_pattern = r"AVAIL\s+BAL"
    
    extracted = {
        "date": None,
        "time": None,
        "transaction_type": None,
        "withdrawal_amount": None,
        "available_balance": None
    }

    for i, raw_line in enumerate(lines):
        line = clean_text(raw_line.upper())

        # Extract date
        if not extracted["date"]:
            match = re.search(date_pattern, line)
            if match:
                extracted["date"] = match.group()

        # Extract time
        if not extracted["time"]:
            match = re.search(time_pattern, line)
            if match:
                extracted["time"] = match.group()

        # Extract transaction type
        if not extracted["transaction_type"]:
            if re.search(withdrawal_pattern, line):
                extracted["transaction_type"] = "WITHDRAWAL"

        # Extract withdrawal amount (the line usually contains the word WITHDRAWAL)
        if extracted["transaction_type"] == "WITHDRAWAL" and not extracted["withdrawal_amount"]:
            if "WITHDRAWAL" in line and i+1 < len(lines):
                # Check current or next line for amount
                current_line_match = re.search(amount_pattern, line)
                next_line_match = re.search(amount_pattern, clean_text(lines[i+1].upper()))
                if current_line_match:
                    extracted["withdrawal_amount"] = current_line_match.group()
                elif next_line_match:
                    extracted["withdrawal_amount"] = next_line_match.group()

        # Extract available balance
        if re.search(avail_bal_label_pattern, line):
            match = re.search(amount_pattern, line)
            if match:
                extracted["available_balance"] = match.group()
            elif i + 1 < len(lines):
                # Try next line if not found on current
                next_match = re.search(amount_pattern, clean_text(lines[i + 1].upper()))
                if next_match:
                    extracted["available_balance"] = next_match.group()

    return extracted

def kplus_extracted(lines):

    extracted_data = {
        "date": None,
        "time": None,
        "transaction_type": None,
        "from_account": None,
        "withdrawal_amount": None,
        "fee_amount": None,
        "account_balance": None
    }

    date_pattern = r"DATE\s*(\d{2}[/°oOo']?\d{2}[/°oOo']?\d{2})"
    time_pattern = r"TIME\s*(\d{2}:\d{2})"  
    withdrawal_pattern = r"(WITHDRAWAL)"
    from_account_pattern = r"FROM\s*ACCOUNT\s*([A-Z0-9]+)"
    amount_pattern = r"AMOUNT\s*([\d,]+\.\d{2})"
    fee_amount_pattern = r"FEE\s*AMOUNT\s*([\d,]+\.\d{2})"
    ac_balance_pattern = r"AC\s*BALANCE\s*([\d,]+\.\d{2})"

    for i, line in enumerate(lines):
        line_clean = line.replace('°', '0').replace('o', '0').replace('O', '0').strip()

        # extrcact DATE
        date_match = re.search(date_pattern, line_clean, re.IGNORECASE)
        if date_match and extracted_data["date"] is None:
            extracted_data["date"] = date_match.group(1).replace("'", "/")

        # extract TIME
        time_match = re.search(time_pattern, line_clean, re.IGNORECASE)
        if time_match and extracted_data["time"] is None:
            extracted_data["time"] = time_match.group(1) + ":00"

        # extract type of transaction (WITHDRAWAL)
        withdrawal_match = re.search(withdrawal_pattern, line_clean, re.IGNORECASE)
        if withdrawal_match and extracted_data["transaction_type"] is None:
            extracted_data["transaction_type"] = withdrawal_match.group(1).upper()

        # extract FROM ACCOUNT
        from_account_match = re.search(from_account_pattern, line_clean, re.IGNORECASE)
        if from_account_match and extracted_data["from_account"] is None:
            extracted_data["from_account"] = from_account_match.group(1)

        # extract AMOUNT (Withdrawal Amount)
        amount_match = re.search(amount_pattern, line_clean, re.IGNORECASE)
        if amount_match and extracted_data["withdrawal_amount"] is None:
            extracted_data["withdrawal_amount"] = amount_match.group(1)

        # extract FEE AMOUNT
        fee_amount_match = re.search(fee_amount_pattern, line_clean, re.IGNORECASE)
        if fee_amount_match and extracted_data["fee_amount"] is None:
            extracted_data["fee_amount"] = fee_amount_match.group(1)

        # extract A/C BALANCE
        ac_balance_match = re.search(ac_balance_pattern, line_clean, re.IGNORECASE)
        if ac_balance_match and extracted_data["account_balance"] is None:
            extracted_data["account_balance"] = ac_balance_match.group(1)

    return extracted_data

def krungthai_extracted(lines):

    extracted_data = {
        "date": None,
        "time": None,
        "transaction_type": None,
        "deposit_amount": None,
        "ac_name": None
    }

    date_pattern = r"DATE\s*([\d]{2}/[\d]{2}/[\d]{2})"
    time_pattern = r"TIME\s*([\d]{2}:[\d]{2})"
    deposit_pattern = r"(AUTO\s*DEP)"
    amount_pattern = r"จำนวนเงิน\s*([\d,]+\.\d{2})\s*BAHT"
    ac_name_pattern = r"To A/C Name\s*:\s*(.+)"

    for line in lines:
        line_clean = line.strip()

        # extract DATE
        date_match = re.search(date_pattern, line_clean, re.IGNORECASE)
        if date_match and extracted_data["date"] is None:
            extracted_data["date"] = date_match.group(1)

        # extract TIME
        time_match = re.search(time_pattern, line_clean, re.IGNORECASE)
        if time_match and extracted_data["time"] is None:
            extracted_data["time"] = time_match.group(1) + ":00"

        # extract type of transaction (AUTO DEP)
        deposit_match = re.search(deposit_pattern, line_clean, re.IGNORECASE)
        if deposit_match and extracted_data["transaction_type"] is None:
            extracted_data["transaction_type"] = deposit_match.group(1)

        # extract deposit amount
        amount_match = re.search(amount_pattern, line_clean, re.IGNORECASE)
        if amount_match and extracted_data["deposit_amount"] is None:
            extracted_data["deposit_amount"] = amount_match.group(1)

        # extract A/C Name
        ac_name_match = re.search(ac_name_pattern, line_clean)
        if ac_name_match and extracted_data["ac_name"] is None:
            extracted_data["ac_name"] = ac_name_match.group(1).strip()


    return extracted_data