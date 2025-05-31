import re
import pandas as pd # Import pandas for DataFrame conversion

BANK_LOGO_PATH = r'bank_logos'

def get_thai_month_map():
    return {
        "ม.ค.": "01", "ก.พ.": "02", "มี.ค.": "03", "เม.ย.": "04",
        "พ.ค.": "05", "มิ.ย.": "06", "ก.ค.": "07", "ส.ค.": "08",
        "ก.ย.": "09", "ต.ค.": "10", "พ.ย.": "11", "ธ.ค.": "12",
        "ม.ค": "01", "ก.พ": "02", "มี.ค": "03", "เม.ย": "04",
        "พ.ค": "05", "มิ.ย": "06", "ก.ค": "07", "ส.ค": "08",
        "ก.ย": "09", "ต.ค": "10", "พ.ย": "11", "ธ.ค": "12",
        "มค.": "01", "กพ.": "02", "มีค.": "03", "เมย.": "04",
        "พค.": "05", "มิย.": "06", "กค.": "07", "สค.": "08",
        "กย.": "09", "ตค.": "10", "พย.": "11", "ธค.": "12",
        "มค": "01", "กพ": "02", "มีค": "03", "เมย": "04",
        "พค": "05", "มิย": "06", "กค": "07", "สค": "08",
        "กย": "09", "ตค": "10", "พย": "11", "ธค": "12",
        "ก.ุพ.": "02", "ก.ุพ": "02", "ก.พ.": "02",
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
        "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
        "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
    }

def _normalize_year(year_str):
    try:
        year = int(year_str)
        if year < 100:
            if year > 50:
                year += 2500
            else:
                year += 2000
        if year > 2500:
            year -= 543
        return year
    except ValueError:
        return None

def _clean_name(name_str):
    if name_str:
        name_str = re.sub(r"^(?:©|๐|@)\s*", "", name_str) # Remove leading symbols
        return name_str.strip()
    return None

# --- Bank-Specific Extraction Functions ---

def _extract_bangkok_info(ocr_text: str, thai_month_map: dict) -> dict:
    res = {
        'transaction_date': None, 'transaction_time': None, 'amount': None,
        'from_account_name': None, 'to_account_name': None, 'to_bank': None, 'ref_number': None
    }
    
    # Date and Time
    match_dt_a = re.search(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4})[,\s]+(\d{2}:\d{2})", ocr_text, re.IGNORECASE)
    if match_dt_a:
        date_str_capture, time_str_capture = match_dt_a.groups()
        try:
            parts = date_str_capture.split()
            day_val = int(parts[0])
            month_abbr = parts[1][:3].capitalize()
            year_val = _normalize_year(parts[2])
            month_num_str = thai_month_map.get(month_abbr)
            if year_val and month_num_str:
                res['transaction_date'] = f"{year_val}-{month_num_str}-{day_val:02d}"
                res['transaction_time'] = time_str_capture
        except Exception:
            pass # Date/time parsing failed

    # Amount
    amount_match = re.search(r"Amount\s+([“\-”,\d]+\.\d{2})\s*(?:tHe|THB|tie|tne)", ocr_text)
    if amount_match:
        try:
            res['amount'] = float(amount_match.group(1).replace(",", "").replace("“", "").replace("”", ""))
        except ValueError:
            pass

    # Reference Number
    ref_match_main = re.search(r"Transaction reference\s*([A-Z0-9]{10,})", ocr_text)
    if ref_match_main:
        res['ref_number'] = ref_match_main.group(1).strip()
    else:
        ref_match_bank = re.search(r"Bank reference no\.\s*(\d+)", ocr_text)
        if ref_match_bank:
            res['ref_number'] = ref_match_bank.group(1).strip()

    # From Account Name
    from_match = re.search(r"(?:From\s+)?©\s*(.*?)(?:\n|\s{2,}|Bangkok Bank)", ocr_text)
    if from_match:
        res['from_account_name'] = _clean_name(from_match.group(1))

    # To Account Name and To Bank
    to_block_match = re.search(r"(?:@|To)\s*(.*?)(?:\n\s*\S{3,}-\S{1,}-\S{3,}|\n\s*Biller ID|\n\s*Bank reference no|PromptPay|Kasikornbank|Siam Commercial Bank|Kiatnakin Phatra Bank|ttb|\d{3,}-\d{1,}-\d{3,})", ocr_text, re.DOTALL)
    if to_block_match:
        block_content = to_block_match.group(1).strip()
        to_account_name_candidate = block_content.split('\n')[0].strip()
        if not ("THB" in to_account_name_candidate or "successful" in to_account_name_candidate or "Scan to verify" in to_account_name_candidate):
            res['to_account_name'] = _clean_name(to_account_name_candidate)

        bank_keywords_map = {
            "Kasikornbank": "Kasikornbank", "Siam Commercial Bank": "SCB", 
            "Kiatnakin Phatra Bank": "Kiatnakin Phatra Bank", "PromptPay": "PromptPay", 
            "ttb": "ttb", "LINE MAN (QR by ttb)": "ttb"
        }
        for kw, bank_name in bank_keywords_map.items():
            # Check in the block itself or in the vicinity of the original text after the block
            if kw.lower() in block_content.lower() or \
               (res['to_account_name'] and kw.lower() in res['to_account_name'].lower()):
                res['to_bank'] = bank_name
                if kw == "LINE MAN (QR by ttb)": # Special case for LINE MAN
                    lm_match = re.search(r"น\s*(LINE MAN.*?)(?:\nBiller|\(QR by ttb\))", ocr_text)
                    if lm_match: res['to_account_name'] = _clean_name(lm_match.group(1).strip())
                break
    if not res['to_account_name']:
        line_man_match = re.search(r"น\s*(LINE MAN.*?)(?:\nBiller|\(QR by ttb\))", ocr_text)
        if line_man_match:
            res['to_account_name'] = _clean_name(line_man_match.group(1).strip())
            if "ttb" in res['to_account_name'] or "ttb" in ocr_text: res['to_bank'] = "ttb"
            
    return res

def _extract_kbank_info(ocr_text: str, thai_month_map: dict) -> dict:
    res = {
        'transaction_date': None, 'transaction_time': None, 'amount': None,
        'from_account_name': None, 'to_account_name': None, 'to_bank': None, 'ref_number': None
    }
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

    # Date and Time
    match_dt_b = re.search(r"(\d{1,2})\s*([ก-ฮ]+\.(?:[คมย]|พฤศจิกายน|มิถุนายน)\.|[ก-ฮ]\.[ก-ฮุ]\.|[ก-ฮ]{2,3}(?:\.|\s))\s*(\d{2,4})\s+(\d{2}:\d{2})\s*(?:น\.|u\.)", ocr_text)
    if match_dt_b:
        day_str, thai_month_input, year_str, time_val = match_dt_b.groups()
        try:
            day_val = int(day_str)
            # Normalize month input (e.g., "มีค." to "มี.ค.", "ก.ุพ." to "ก.ุพ.")
            month_key_to_lookup = thai_month_input.strip()
            if not month_key_to_lookup.endswith('.') and len(month_key_to_lookup) > 1 and month_key_to_lookup not in thai_month_map :
                if len(month_key_to_lookup) == 3 and month_key_to_lookup[1] != '.': # e.g. มีค
                     month_key_to_lookup = f"{month_key_to_lookup[0]}.{month_key_to_lookup[1]}."
                elif not month_key_to_lookup.endswith('.'):
                     month_key_to_lookup += "."


            month_num_str = thai_month_map.get(month_key_to_lookup)
            if not month_num_str and '.' in month_key_to_lookup: # try without last dot if common like ก.พ
                 month_num_str = thai_month_map.get(month_key_to_lookup[:-1])


            year_val = _normalize_year(year_str)
            if year_val and month_num_str:
                res['transaction_date'] = f"{year_val}-{month_num_str}-{day_val:02d}"
                res['transaction_time'] = time_val
        except Exception:
            pass

    # Amount
    amount_match = re.search(r"จํานวน(?:เงิน)?:\s*([,\d]+\.\d{2})\s*บาท", ocr_text)
    if not amount_match: #KBank sometimes has "จํานวน:" then amount on next line or after spaces
        amount_match = re.search(r"จํานวน:\s*\n*\s*([,\d]+\.\d{2})\s*บาท", ocr_text, re.MULTILINE)
    if amount_match:
        try:
            res['amount'] = float(amount_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Reference Number
    ref_match = re.search(r"เลขที่รายการ:\s*([A-Z0-9]+)", ocr_text)
    if ref_match:
        res['ref_number'] = ref_match.group(1).strip()

    # From Account Name
    # Find line with "ธ.กสิกรไทย" or KBank account pattern, name is usually line above
    from_account_idx = -1
    for i, line in enumerate(lines):
        if ("ธ.กสิกรไทย" in line or re.search(r"XXX-X-X\d{3,6}-X", line)) and i > 0:
            name_candidate = lines[i-1]
            if not any(kw in name_candidate for kw in ["โอนเจินสําเร็จ", "จ่ายบิล", "ชําระเงิน", "K PLUS", "บาท"]) and \
               not re.match(r"\d{1,2}\s*[ก-ฮ]+\.", name_candidate) and len(name_candidate) > 2 and "รายการ:" not in name_candidate:
                res['from_account_name'] = _clean_name(name_candidate)
                # Check for two-line name (e.g., title on one line, name on next)
                if i > 1 and any(title in lines[i-2] for title in ["น.ส.", "นาย", "นาง", "บจก.", "หจก."]) and len(name_candidate.split()) <= 2 : # Allow for first name + last initial
                    res['from_account_name'] = _clean_name(lines[i-2] + " " + name_candidate)
                break
    
    # To Account Name and To Bank
    # This is complex for KBank due to variations (transfer, bill payment, QR)
    # Strategy: Look for sections after the 'from' account details
    
    to_section_found = False
    if res['from_account_name']:
        try:
            from_name_end_idx = ocr_text.lower().rfind(res['from_account_name'].lower()[-10:]) # Find last part of from_name
            if from_name_end_idx != -1:
                 from_name_end_idx += 10 # approx end
            else: # if from_name was not found or too short, search after first account number
                first_acc_num_match = re.search(r"XXX-X-X\d{3,6}-X", ocr_text)
                if first_acc_num_match:
                    from_name_end_idx = first_acc_num_match.end()
                else: # Fallback to after date/time if everything else fails
                    dt_match_end = re.search(r"(\d{2}:\d{2})\s*(?:น\.|u\.)", ocr_text)
                    from_name_end_idx = dt_match_end.end() if dt_match_end else 50 # Arbitrary start if no markers

            search_text_for_to = ocr_text[from_name_end_idx:]
            
            # Pattern 1: Direct Transfer (Name \n Bank/PromptPay)
            # (Name line) \n (Bank line OR PromptPay line OR another name line for billers)
            # Avoid capturing "เลขที่รายการ" or amount lines as name
            # ([^\n]+?) -> Non-greedy name capture
            # (?:XXX-X-X\d{3,6}-X|รหัสพร้อมเพย์|Pay|ธ\.[ก-ฮฯ]+|Shop|Wallet|บจก\.|หจก\.|[A-Z\s]{5,}) -> Bank indicator
            to_transfer_match = re.search(
                r"([^\n]+?)\n\s*(?:(XXX-X-X\d{3,6}-X)|(ธ\.[ก-ฮฯ\s]+(?:ไทย|พาณิชย์|กรุงศรี)?)|รหัสพร้อมเพย์|Prompt\s*Pay|Payee ID|([A-Z\s]{5,}[Ss]hop)|[A-Z\s]+Wallet|บจก\.|หจก\.)",
                search_text_for_to, re.IGNORECASE
            )
            if to_transfer_match:
                cand_to_name = to_transfer_match.group(1).strip()
                if not any(kw in cand_to_name for kw in ["เลขที่รายการ", "จํานวน", "ค่าธรรมเนียม", "บาท", "สแกนตรวจสอบสลิป"]) and len(cand_to_name) > 2:
                    res['to_account_name'] = _clean_name(cand_to_name)
                    to_section_found = True
                    
                    bank_line_indicators = [
                        (to_transfer_match.group(3), None), # ธ. Bank Name
                        ("รหัสพร้อมเพย์" if "รหัสพร้อมเพย์" in to_transfer_match.group(0) else None, "PromptPay"),
                        ("PromptPay" if "PromptPay" in to_transfer_match.group(0).lower() else None, "PromptPay"),
                        ("Payee ID" if "Payee ID" in to_transfer_match.group(0) else None, "PromptPay"), # Often for PromptPay
                        (to_transfer_match.group(4), to_transfer_match.group(4)), # Shop name
                        ("Wallet" if "Wallet" in to_transfer_match.group(0) else None, "Wallet")
                    ]
                    for indicator, bank_val in bank_line_indicators:
                        if indicator:
                            res['to_bank'] = bank_val if bank_val else indicator.strip()
                            break
                    if "กสิกรไทย" in (res['to_bank'] or ""): res['to_bank'] = "Kasikornbank"
                    elif "ไทยพาณิชย์" in (res['to_bank'] or ""): res['to_bank'] = "SCB"
            
            # Pattern 2: Bill Payment / QR Payment (often 1-2 lines for recipient name, then "เลขที่รายการ" or "N hin" or Ref No.)
            if not to_section_found:
                 # Look for name(s) before "เลขที่รายการ" or specific biller identifiers
                 # Try to capture 1 or 2 lines as recipient name
                biller_match = re.search(
                    r"([^\n]+)\s*(?:\n\s*([^\n]+))?\s*\n+(?:เลขที่รายการ|N\s+hin|Ref No\.|รหัสอ้างอิง|20\d{10,})", # 20... is QR payment ref
                    search_text_for_to, re.MULTILINE
                )
                if biller_match:
                    b_line1 = biller_match.group(1).strip()
                    b_line2 = biller_match.group(2).strip() if biller_match.group(2) else ""

                    if not any(kw in b_line1 for kw in ["เลขที่รายการ", "จํานวน", "ค่าธรรมเนียม", "บาท", "สแกนตรวจสอบสลิป", "XXX-X-X"]) and len(b_line1) > 2:
                        potential_name = b_line1
                        if b_line2 and not any(kw in b_line2 for kw in ["เลขที่รายการ", "จํานวน", "ค่าธรรมเนียม", "บาท", "สแกนตรวจสอบสลิป", "XXX-X-X"]) \
                           and not re.match(r"\d{10,}", b_line2) and not "Pay" in b_line2 and not "ธ." in b_line2 : # Avoid ref numbers and bank lines
                            potential_name += " " + b_line2
                        
                        res['to_account_name'] = _clean_name(potential_name.strip())
                        to_section_found = True
                        
                        # Infer bank for known KBank billers
                        if res['to_account_name']:
                            if "Shopee" in res['to_account_name']: res['to_bank'] = "ShopeePay"
                            elif "TrueMoney" in res['to_account_name']: res['to_bank'] = "TrueMoney Wallet"
                            elif "LINE MAN" in res['to_account_name']: res['to_bank'] = "LINE MAN" # Or ttb if specified
                            elif any(shop_kw in res['to_account_name'] for shop_kw in ["Shop", "ร้าน", "บจก.", "หจก.", "Co., Ltd."]):
                                res['to_bank'] = "Biller" # Generic biller/shop
        except Exception:
            pass # KBank 'to' parsing is tricky

    return res

def _extract_scb_info(ocr_text: str, thai_month_map: dict) -> dict:
    res = {
        'transaction_date': None, 'transaction_time': None, 'amount': None,
        'from_account_name': None, 'to_account_name': None, 'to_bank': None, 'ref_number': None
    }

    # Date and Time
    match_dt_c = re.search(r"(\d{1,2}\s+(?:[ก-ฮ]+\.(?:[คมย]|พฤศจิกายน|มิถุนายน)\.|[ก-ฮ]{2,3}(?:\.|\s))\s+\d{4})\s+-\s+(\d{2}:\d{2})", ocr_text)
    if not match_dt_c: # Alternative format like "01 เม.ย. 2568 - 21:45" but also handles "04 wig. 2568 - 13:19"
        match_dt_c = re.search(r"(\d{1,2}\s+[A-Za-zก-ฮ]+\.?\s+\d{4})\s+-\s+(\d{2}:\d{2})", ocr_text)

    if match_dt_c:
        date_str_capture, time_str_capture = match_dt_c.groups()
        try:
            parts = date_str_capture.split()
            day_val = int(parts[0])
            month_input = parts[1].replace(".","") # Remove dots for lookup e.g. "เม.ย" -> "เมย"
            
            month_num_str = None
            for k,v in thai_month_map.items(): # Match abbreviation like "wig." for "พ.ค." or similar
                if month_input.lower().startswith(k.replace(".","").lower()[:2]): # Match first 2 chars of abbreviation
                    month_num_str = v
                    break
            if not month_num_str: month_num_str = thai_month_map.get(parts[1]) # Try direct match with dot
            if not month_num_str: month_num_str = thai_month_map.get(parts[1] + ".") # Try with added dot

            year_val = _normalize_year(parts[2])
            if year_val and month_num_str:
                res['transaction_date'] = f"{year_val}-{month_num_str}-{day_val:02d}"
                res['transaction_time'] = time_str_capture
        except Exception:
            pass

    # Amount
    amount_match = re.search(r"จํานวนเงิน\s*([,\d]+\.\d{2})", ocr_text)
    if not amount_match: # SCB card slips sometimes have "จํานวนเงิ่น"
        amount_match = re.search(r"จํานวนเงิ่น\s*([,\d]+\.\d{2})", ocr_text)
    if amount_match:
        try:
            res['amount'] = float(amount_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Reference Number
    ref_match = re.search(r"รหัสอ้างอิง:\s*([A-Za-z0-9]+)", ocr_text)
    if ref_match:
        res['ref_number'] = ref_match.group(1).strip()

    # From Account Name
    from_match = re.search(r"จาก\s*(?:©|@)\s*(.*?)(?:\n|XXX-XXX\d{3}-\d|\d{4}\s*\d{2}xx\s*xxxx\s*\d{4}|รหัสอ้างอิง)", ocr_text)
    if from_match:
        name_candidate = from_match.group(1).strip()
        if "PLANET SCB" in name_candidate: res['from_account_name'] = "PLANET SCB"
        else: res['from_account_name'] = _clean_name(name_candidate)


    # To Account Name and To Bank
    to_match = re.search(r"ไปยัง\s*(?:@|0|©)?\s*(.*?)(?:\n|x-\d{4}|X{3}-\d{3}|Biller ID|\d{4}\s*\d{2}xx|Comp code|บัญชีรับชําระ|เลขที่เครื่องชําระเงิน|รหัสร้านค้า|\d{3,}-\d{1,}-\d{3,})", ocr_text)
    if to_match:
        to_name_candidate = to_match.group(1).strip()
        res['to_account_name'] = _clean_name(to_name_candidate)

        if "พร้อมเพย์" in to_name_candidate or "พร้อมแพย์" in to_name_candidate:
            res['to_bank'] = "PromptPay"
            info_prov_match = re.search(r"ข้อมูลเพิ่มเติมจากผู้ให้บริการ\s*\n\s*(.*?)(?:\s*\(.*?\))?\s*\n", ocr_text)
            if info_prov_match:
                actual_name = info_prov_match.group(1).strip()
                if len(actual_name) > 3 and "ผู้รับเงินสามารถสแกน" not in actual_name:
                    res['to_account_name'] = _clean_name(actual_name)
        elif "TRUE MONEY" in to_name_candidate.upper():
            res['to_bank'] = "TrueMoney"
            res['to_account_name'] = "TRUE MONEY CO.,LTD." # Standardize
        elif "PLANET SCB" in to_name_candidate:
            res['to_bank'] = "SCB Planet"
            # Extract name from "ข้อมูลเพิ่มเติมจากผู้ให้บริการ" if available for Planet SCB
            planet_info_match = re.search(r"ข้อมูลเพิ่มเติมจากผู้ให้บริการ\s*\n\s*([A-Z\s]+)\s*\n", ocr_text)
            if planet_info_match:
                res['to_account_name'] = _clean_name(planet_info_match.group(1).strip())
            else:
                res['to_account_name'] = "PLANET SCB" # Default if no specific name found
        elif any(b_kw in to_name_candidate for b_kw in ["เอไอเอส", "AIS", "การประปา", "การไฟฟ้า", "Biller ID", "Comp code"]):
            res['to_bank'] = "Biller"
        elif "SCB" in ocr_text.split(to_name_candidate)[-1] if to_name_candidate in ocr_text else False: # Check if SCB appears after the name
            res['to_bank'] = "SCB"
        # If "ไปยัง" points to a person and no bank keyword, it's often SCB to SCB, but can be other banks too.
        # Try to find bank hints in the text around the 'to_account_name'
        if not res['to_bank'] and res['to_account_name']:
            context_after_to_name = ""
            try:
                idx = ocr_text.lower().find(res['to_account_name'].lower())
                if idx != -1:
                    context_after_to_name = ocr_text[idx + len(res['to_account_name']):idx + len(res['to_account_name']) + 70] # Check next 70 chars
            except: pass
            
            if "กสิกรไทย" in context_after_to_name or "Kasikorn" in context_after_to_name: res['to_bank'] = "Kasikornbank"
            elif "กรุงไทย" in context_after_to_name or "Krungthai" in context_after_to_name: res['to_bank'] = "Krungthai"
            elif "Bangkok Bank" in context_after_to_name: res['to_bank'] = "Bangkok Bank"
            # SCB to SCB is often implicit, leave as None if no other bank is found

    return res

def _extract_krungthai_info(ocr_text: str, thai_month_map: dict) -> dict:
    res = {
        'transaction_date': None, 'transaction_time': None, 'amount': None,
        'from_account_name': None, 'to_account_name': None, 'to_bank': None, 'ref_number': None
    }
    
    # Date and Time
    # Example: "01 เม.ย. 2568 - 18:41" or "01 w.A. 2565 - 23:53" (w.A. for พ.ค.)
    match_dt_c = re.search(r"(\d{1,2}\s+(?:[ก-ฮA-Za-z]+\.(?:[คมยสตน]|[คมยสตน]\.)?)\s+\d{4})\s+-\s+(\d{2}:\d{2})", ocr_text)
    if match_dt_c:
        date_str_capture, time_str_capture = match_dt_c.groups()
        try:
            parts = date_str_capture.split()
            day_val = int(parts[0])
            month_input_raw = parts[1]
            
            month_num_str = None
            # Try matching parts of the month input, e.g. "w.A." could be พ.ค.
            cleaned_month_input = month_input_raw.replace(".","").lower()
            for k_map, v_map in thai_month_map.items():
                cleaned_k_map = k_map.replace(".","").lower()
                if cleaned_month_input.startswith(cleaned_k_map[:2]) and len(cleaned_k_map) >1 : # Match first 2 chars
                     month_num_str = v_map
                     break
            if not month_num_str: month_num_str = thai_month_map.get(month_input_raw) # Direct match
            if not month_num_str and not month_input_raw.endswith('.'): month_num_str = thai_month_map.get(month_input_raw + ".") # Try with dot


            year_val = _normalize_year(parts[2])
            if year_val and month_num_str:
                res['transaction_date'] = f"{year_val}-{month_num_str}-{day_val:02d}"
                res['transaction_time'] = time_str_capture
        except Exception:
            pass

    # Amount
    amount_match = re.search(r"จํานวนเงิน\s*([,\d]+\.\d{2})\s*บาท", ocr_text)
    if amount_match:
        try:
            res['amount'] = float(amount_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Reference Number
    ref_match = re.search(r"รหัสอ(?:ฮ|า)้างอิง\s*([A-Za-z0-9\s]+)", ocr_text) # Allow for OCR error "อฮ้างอิง"
    if ref_match:
        res['ref_number'] = ref_match.group(1).strip().split('\n')[0] # Take first line if multi-line

    # From Account Name
    from_match = re.search(r"^(?:©|๐|iG)?\s*(น\.ส\.|นาย|นาง|นส\.)\s*(.*?)\n\s*กรุงไทย", ocr_text, re.MULTILINE | re.IGNORECASE)
    if not from_match: # Simpler from pattern if the above is too specific
        from_match = re.search(r"^(?:©|๐|iG)?\s*([^\n]+?)\n\s*กรุงไทย", ocr_text, re.MULTILINE | re.IGNORECASE)

    if from_match:
        name_parts = [p for p in from_match.groups() if p]
        name_candidate = " ".join(name_parts).strip()
        if "Krungthai" not in name_candidate and "รหัสอ้างอิง" not in name_candidate and "G-Wallet" not in name_candidate and len(name_candidate) > 3:
             res['from_account_name'] = _clean_name(name_candidate)


    # To Account Name and To Bank
    # Krungthai format: "โปยัง\nNAME\nBANK" or "le)\nNAME\nBANK" or "๒ BILLER_NAME \n (ID)"
    to_block_match = re.search(r"(?:โปยัง|le\)|Vv|๑|๒)\s*\n?\s*(.*?)(?:\n\s*([ก-ฮA-Za-z\s\.]*(?:Bank|ไทย|เพย์|Pay|Wallet|shop|G-Wallet|ออมสิน))|\n\s*\(?\d{5,}\)?|\n\s*จํานวนเงิน|\n\s*รหัสอ้างอิง\s*1|\n\s*หมายเลขอ้างอิง\s*1)", ocr_text, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    
    if to_block_match:
        to_name_candidate_full = to_block_match.group(1).strip()
        # Take the first line of the candidate block as name, avoid account numbers or IDs
        to_name_first_line = to_name_candidate_full.split('\n')[0].strip()

        if not any(kw in to_name_first_line for kw in ["จํานวนเงิน","ค่าธรรมเนียม","วันที่ทํา","รหัสอ้างอิง", "XXX-X-XX", "G-Wallet"]) and \
           not re.match(r"^\(G-WALLET\)", to_name_first_line, re.IGNORECASE) and len(to_name_first_line) > 2 :
            res['to_account_name'] = _clean_name(to_name_first_line)
        
        # Explicit bank line
        if to_block_match.group(2):
            to_bank_line = to_block_match.group(2).strip()
            if "กสิกรไทย" in to_bank_line: res['to_bank'] = "Kasikornbank"
            elif "พร้อมเพย์" in to_bank_line or "PromptPay" in to_bank_line: res['to_bank'] = "PromptPay"
            elif "ออมสิน" in to_bank_line: res['to_bank'] = "GSB"
            elif "G-Wallet" in to_bank_line.upper(): res['to_bank'] = "G-Wallet" # Also check if G-Wallet is in name
            elif "SHOPEEPAY" in to_bank_line.upper(): res['to_bank'] = "ShopeePay"
            elif "MPAY" in to_bank_line.upper(): res['to_bank'] = "MPAY"
            elif "K+ SHOP" in to_bank_line.upper(): res['to_bank'] = "K+ shop"
            elif "ร้านถุงเงิน" in to_bank_line: res['to_bank'] = "ร้านถุงเงิน"
            else: res['to_bank'] = to_bank_line # Store as is
        
        # Infer from name if bank not found in explicit line
        if not res['to_bank'] and res['to_account_name']:
            if "SHOPEEPAY" in res['to_account_name'].upper(): res['to_bank'] = "ShopeePay"
            elif "MPAY" in res['to_account_name'].upper(): res['to_bank'] = "MPAY"
            elif "K+ SHOP" in res['to_account_name'].upper(): res['to_bank'] = "K+ shop"
            elif "ร้านถุงเงิน" in res['to_account_name']: res['to_bank'] = "ร้านถุงเงิน"
            elif "G-Wallet" in to_name_candidate_full.upper() or "(G-WALLET)" in to_name_candidate_full.upper(): # Check full block for G-Wallet
                res['to_bank'] = "G-Wallet"
                if not res['to_account_name'] or "G-Wallet" in res['to_account_name'] : # If name is just G-Wallet, try to find actual name
                    actual_name_gwallet = re.search(r"([^\n(]+)\s*\(G-WALLET\)", to_name_candidate_full, re.IGNORECASE)
                    if actual_name_gwallet:
                        res['to_account_name'] = _clean_name(actual_name_gwallet.group(1))


    return res

# --- Main Processing Function ---
from .ocr_tesseract import ocr_pytesseract
from .bank_annotation import annotation_bank

def process_image(file_path: str):
    """Orchestrates OCR, bank identification, and information extraction."""
    try:
        ocr_text, _ = ocr_pytesseract(file_path) # We only need the text
        if not ocr_text:
            print(f"OCR failed to extract text from {file_path}")
            return None

        bank_name = annotation_bank(file_path, BANK_LOGO_PATH) 
        if not bank_name:
            print(f"Bank identification failed for {file_path}")
            # Fallback: try to infer from OCR text if no logo match
            if "kasikorn" in ocr_text.lower() or "kbank" in ocr_text.lower(): bank_name = "kbank"
            elif "siam commercial bank" in ocr_text.lower() or "scb" in ocr_text.lower(): bank_name = "scb"
            elif "bangkok bank" in ocr_text.lower() : bank_name = "bangkok"
            elif "krungthai" in ocr_text.lower() or "ktb" in ocr_text.lower(): bank_name = "krungthai"
            # Add more fallbacks if needed
            else:
                print("Could not determine bank from OCR text either.")
                return None 
        
        print(f"Identified bank: {bank_name} for file: {file_path}")

        thai_months = get_thai_month_map()
        extracted_info = None

        # Map bank_name (from annotation_bank) to function calls
        # The names returned by annotation_bank might need to be normalized here
        # For example, if annotation_bank returns "Kasikornbank", map it to "kbank"
        normalized_bank_name = bank_name.lower()

        if "bangkok" in normalized_bank_name: # Assuming annotation_bank might return "Bangkok Bank Logo" or similar
            extracted_info = _extract_bangkok_info(ocr_text, thai_months)
        elif "kbank" in normalized_bank_name or "kasikorn" in normalized_bank_name:
            extracted_info = _extract_kbank_info(ocr_text, thai_months)
        elif "scb" in normalized_bank_name or "siam commercial" in normalized_bank_name:
            extracted_info = _extract_scb_info(ocr_text, thai_months)
        elif "krungthai" in normalized_bank_name or "ktb" in normalized_bank_name:
            extracted_info = _extract_krungthai_info(ocr_text, thai_months)
        # Add other banks as needed
        else:
            print(f"No specific extraction logic for bank: {bank_name}")
            return None

        if extracted_info:
            extracted_info['from_bank'] = normalized_bank_name
            # Convert the dictionary to a Pandas DataFrame before returning
            # This makes it consistent with app.py's expectation
            df = pd.DataFrame([extracted_info]) # Create DataFrame from a single dictionary
            return df
        else:
            print(f"Extraction failed for bank {bank_name} on file {file_path}")
            return None

    except Exception as e:
        print(f"Error in process_image for {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return None