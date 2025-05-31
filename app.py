from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
import os
from PIL import Image
import pillow_heif
import io
import pandas as pd
from function.e_slip import extract_info
from function.physical import physical_slip
from function.e_slip.bank_annotation import annotation_bank
from datetime import datetime

app = Flask(__name__)

# Define specific upload folders
UPLOAD_E_SLIP_FOLDER = os.path.abspath('uploads/e-slips')
UPLOAD_PHYSICAL_FOLDER = os.path.abspath('uploads/physicals')
MODEL_PATH = os.path.abspath('models/best.pt')
BANK_CLASS_MAPPING = {
            'bangkok bank': 'bangkok',
            'bangkok': 'bangkok',
            'bkk': 'bangkok',
            'bbl': 'bangkok',
            'kasikornbank': 'kbank',
            'kbank': 'kbank',
            'k-bank': 'kbank',
            'kasikorn': 'kbank',
            'kplus': 'kbank',
            'k+': 'kbank',
            'scb': 'scb',
            'siam commercial bank': 'scb',
            'siam commercial': 'scb',
            'siam': 'scb',
            'krungthai': 'krungthai',
            'krungthai bank': 'krungthai',
            'ktb': 'krungthai',
            'krung thai': 'krungthai',
            'krungthai_bank': 'krungthai'
        }

EXTRACT_ALL_DATA_PATH = os.path.abspath('app_extraction_csv')

# Keep a general UPLOAD_FOLDER reference for simplicity in some existing functions if needed,
# or refactor them later. For now, previews might use this if not distinguished by type.
app.config['UPLOAD_E_SLIP_FOLDER'] = UPLOAD_E_SLIP_FOLDER
app.config['UPLOAD_PHYSICAL_FOLDER'] = UPLOAD_PHYSICAL_FOLDER

# Ensure upload sub-folders exist
if not os.path.exists(UPLOAD_E_SLIP_FOLDER):
    os.makedirs(UPLOAD_E_SLIP_FOLDER)
if not os.path.exists(UPLOAD_PHYSICAL_FOLDER):
    os.makedirs(UPLOAD_PHYSICAL_FOLDER)

# Re-added convert_heic_to_jpeg function
def convert_heic_to_jpeg(heic_path):
    try:
        pillow_heif.register_heif_opener()
        heif_file = pillow_heif.read_heif(heic_path)
        image = Image.frombytes(
            heif_file.mode, 
            heif_file.size, 
            heif_file.data,
            "raw",
        )
        output = io.BytesIO()
        image.save(output, format='JPEG')
        output.seek(0)
        return output
    except Exception as e:
        print(f"Error converting HEIC image: {e}")
        return None

@app.route('/')
def index():
    message = request.args.get('message', None)
    uploaded_filename_param = request.args.get('uploaded_filename', None)
    slip_type_param = request.args.get('slip_type', None) # For auto-preview after upload
    
    e_slip_files = []
    if os.path.exists(app.config['UPLOAD_E_SLIP_FOLDER']):
        for f_name in sorted(os.listdir(app.config['UPLOAD_E_SLIP_FOLDER'])):
            if not f_name.startswith('.'):
                e_slip_files.append(f_name)
                
    physical_slip_files = []
    if os.path.exists(app.config['UPLOAD_PHYSICAL_FOLDER']):
        for f_name in sorted(os.listdir(app.config['UPLOAD_PHYSICAL_FOLDER'])):
            if not f_name.startswith('.'):
                physical_slip_files.append(f_name)
                
    return render_template('index.html', 
                           message=message, 
                           uploaded_filename_param=uploaded_filename_param, 
                           slip_type_param=slip_type_param, # Pass to template
                           e_slip_files=e_slip_files,
                           physical_slip_files=physical_slip_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index', message='No file part'))
    file = request.files['file']
    slip_type = request.form.get('slip_type') # Get slip_type from form

    if file.filename == '':
        return redirect(url_for('index', message='No selected file'))
    if not slip_type:
        return redirect(url_for('index', message='No slip type selected'))

    if file:
        filename = file.filename
        
        target_folder = ""
        if slip_type == 'e-slip':
            target_folder = app.config['UPLOAD_E_SLIP_FOLDER']
        elif slip_type == 'physical':
            target_folder = app.config['UPLOAD_PHYSICAL_FOLDER']
        else:
            return redirect(url_for('index', message='Invalid slip type selected'))
            
        file_path = os.path.join(target_folder, filename)
        file.save(file_path)
        return redirect(url_for('index', 
                                message=f'{slip_type.capitalize()} "{filename}" uploaded successfully', 
                                uploaded_filename=filename,
                                slip_type=slip_type)) # Pass slip_type for auto-preview context

# Route to serve uploaded files for preview
@app.route('/uploads_preview/<slip_type>/<path:filename>')
def serve_upload_for_preview(slip_type, filename):
    target_folder = ""
    if slip_type == 'e-slip':
        target_folder = app.config['UPLOAD_E_SLIP_FOLDER']
    elif slip_type == 'physical':
        target_folder = app.config['UPLOAD_PHYSICAL_FOLDER']
    else:
        return "Invalid slip type", 400

    file_path_abs = os.path.join(target_folder, filename)
    
    if not os.path.abspath(file_path_abs).startswith(os.path.abspath(target_folder)):
        return "Access denied", 403
    if not os.path.exists(file_path_abs):
        return "File not found", 404

    if filename.lower().endswith('.heic'):
        converted_image = convert_heic_to_jpeg(file_path_abs)
        if converted_image:
            return send_file(converted_image, mimetype='image/jpeg', as_attachment=False, download_name=os.path.splitext(filename)[0] + '.jpg')
        else:
            return "Error converting HEIC image", 500
    
    return send_from_directory(target_folder, filename)

# E-slip processing
@app.route('/process_e_slip/<filename>')
def process_e_slip_route(filename):
    file_path = os.path.join(app.config['UPLOAD_E_SLIP_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    try:
        extracted_data_df = extract_info.process_image(file_path)
        
        # Get bank class information from annotation_bank
        detected_bank = annotation_bank(file_path, 'bank_logos')
        
        # Get raw OCR text
        from function.e_slip.ocr_tesseract import ocr_pytesseract
        raw_ocr_text, _ = ocr_pytesseract(file_path)
        
        # Normalize the detected bank name
        bank_class = BANK_CLASS_MAPPING.get(detected_bank.lower() if detected_bank else '', detected_bank)
        
        if extracted_data_df is not None and not extracted_data_df.empty:
            data_html = extracted_data_df.to_html(classes='table table-striped', index=False)
            return render_template('display_data.html', data_html=data_html, filename=filename, slip_type='e-slip', bank_class=bank_class, raw_ocr=raw_ocr_text)
        else:
            return render_template('display_data.html', error_message="No data extracted or an error occurred.", filename=filename, slip_type='e-slip', bank_class=bank_class, raw_ocr=raw_ocr_text)
    except AttributeError as e:
        error_msg = f"Error: Function not found in e-slip processing module. {str(e)}"
        print(error_msg)
        return render_template('display_data.html', error_message=error_msg, filename=filename, slip_type='e-slip', bank_class=None, raw_ocr=None)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template('display_data.html', error_message=f"Error processing e-slip: {str(e)}", filename=filename, slip_type='e-slip', bank_class=None, raw_ocr=None)

# Physical slip processing
@app.route('/process_physical_slip/<filename>')
def process_physical_slip_route(filename):
    file_path = os.path.join(app.config['UPLOAD_PHYSICAL_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    try:
        image, after_yolo, conf, classname, binary, detected_4_coor_with_contour, perspective_trans, thresh, binaryInv, extracted_text = physical_slip.process_physical_slip(file_path, MODEL_PATH)
        
        # Get raw OCR text by running OCR on the processed image
        import pytesseract
        custom_config = r'--oem 3 --psm 6'
        raw_ocr_text = pytesseract.image_to_string(binaryInv, lang='tha+eng', config=custom_config)
        
        # Normalize the classname to ensure consistent color mapping
        bank_class = BANK_CLASS_MAPPING.get(classname.lower() if classname else '', classname)
        
        # Handle the extracted text based on the bank type
        data_html = ""
        if isinstance(extracted_text, dict):
            # If extracted_text is a dictionary (structured data from bkk, kplus, krungthai)
            import pandas as pd
            df = pd.DataFrame([extracted_text])
            data_html = df.to_html(classes='table table-striped', index=False)
        elif isinstance(extracted_text, list):
            # If extracted_text is a list (lines from scb or fallback)
            for line in extracted_text:
                if line.strip():  # Only add non-empty lines
                    data_html += f"<p>{line}</p>"
        else:
            # Fallback: treat as string or other format
            data_html = f"<p>{str(extracted_text)}</p>"
            
        return render_template('display_data.html', data_html=data_html, filename=filename, slip_type='physical', bank_class=bank_class, raw_ocr=raw_ocr_text)
    except AttributeError as e:
        error_msg = f"Error: Function not found in physical slip processing module. {str(e)}"
        print(error_msg)
        return render_template('display_data.html', error_message=error_msg, filename=filename, slip_type='physical', bank_class=None, raw_ocr=None)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template('display_data.html', error_message=f"Error processing physical slip: {str(e)}", filename=filename, slip_type='physical', bank_class=None, raw_ocr=None)

@app.route('/delete/<slip_type>/<filename>', methods=['POST'])
def delete_file_route(slip_type, filename):
    target_folder = ""
    if slip_type == 'e-slip':
        target_folder = app.config['UPLOAD_E_SLIP_FOLDER']
    elif slip_type == 'physical':
        target_folder = app.config['UPLOAD_PHYSICAL_FOLDER']
    else:
        return redirect(url_for('index', message='Error: Invalid slip type for deletion.'))

    file_path = os.path.join(target_folder, filename)
    
    if not os.path.abspath(file_path).startswith(os.path.abspath(target_folder)):
        return redirect(url_for('index', message='Error: Invalid file path for deletion.'))

    try:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            os.remove(file_path)
            return redirect(url_for('index', message=f'{slip_type.capitalize()} "{filename}" deleted successfully.'))
        else:
            return redirect(url_for('index', message=f'Error: File "{filename}" not found in {slip_type}s.'))
    except Exception as e:
        print(f"Error deleting file {filename} from {slip_type}s: {e}")
        return redirect(url_for('index', message=f'Error deleting file "{filename}": {str(e)}'))

@app.route('/extract_all_data', methods=['POST'])
def extract_all_data():
    """Extract data from all uploaded files and export to CSV"""
    try:
        
        # Create results directory if it doesn't exist
        results_dir = EXTRACT_ALL_DATA_PATH
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        # Generate timestamp for unique filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize data storage
        e_slip_data = []
        physical_slip_data = []
        failed_files = []
        
        # Process E-slips
        if os.path.exists(app.config['UPLOAD_E_SLIP_FOLDER']):
            e_slip_files = [f for f in os.listdir(app.config['UPLOAD_E_SLIP_FOLDER']) 
                           if not f.startswith('.') and os.path.isfile(os.path.join(app.config['UPLOAD_E_SLIP_FOLDER'], f))]
            
            for filename in e_slip_files:
                try:
                    file_path = os.path.join(app.config['UPLOAD_E_SLIP_FOLDER'], filename)
                    extracted_data_df = extract_info.process_image(file_path)
                    
                    if extracted_data_df is not None and not extracted_data_df.empty:
                        # Add metadata
                        extracted_data_df['filename'] = filename
                        extracted_data_df['slip_type'] = 'e-slip'
                        extracted_data_df['processing_timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Get bank information
                        detected_bank = annotation_bank(file_path, 'bank_logos')
                        bank_class = BANK_CLASS_MAPPING.get(detected_bank.lower() if detected_bank else '', detected_bank)
                        extracted_data_df['detected_bank'] = bank_class
                        
                        e_slip_data.append(extracted_data_df)
                    else:
                        failed_files.append(f"e-slip: {filename} - No data extracted")
                        
                except Exception as e:
                    failed_files.append(f"e-slip: {filename} - Error: {str(e)}")
        
        # Process Physical slips
        if os.path.exists(app.config['UPLOAD_PHYSICAL_FOLDER']):
            physical_slip_files = [f for f in os.listdir(app.config['UPLOAD_PHYSICAL_FOLDER']) 
                                  if not f.startswith('.') and os.path.isfile(os.path.join(app.config['UPLOAD_PHYSICAL_FOLDER'], f))]
            
            for filename in physical_slip_files:
                try:
                    file_path = os.path.join(app.config['UPLOAD_PHYSICAL_FOLDER'], filename)
                    image, after_yolo, conf, classname, binary, detected_4_coor_with_contour, perspective_trans, thresh, binaryInv, extracted_text = physical_slip.process_physical_slip(file_path, MODEL_PATH)
                    
                    if extracted_text:
                        # Convert extracted text to DataFrame format
                        if isinstance(extracted_text, dict):
                            df = pd.DataFrame([extracted_text])
                        elif isinstance(extracted_text, list):
                            # Convert list of text lines to a single text field
                            text_content = '\n'.join([line for line in extracted_text if line.strip()])
                            df = pd.DataFrame([{'extracted_text': text_content}])
                        else:
                            df = pd.DataFrame([{'extracted_text': str(extracted_text)}])
                        
                        # Add metadata
                        df['filename'] = filename
                        df['slip_type'] = 'physical'
                        df['processing_timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df['detected_bank'] = BANK_CLASS_MAPPING.get(classname.lower() if classname else '', classname)
                        df['confidence'] = conf
                        
                        physical_slip_data.append(df)
                    else:
                        failed_files.append(f"physical: {filename} - No data extracted")
                        
                except Exception as e:
                    failed_files.append(f"physical: {filename} - Error: {str(e)}")
        
        # Save results to CSV files
        success_count = 0
        
        if e_slip_data:
            e_slip_combined = pd.concat(e_slip_data, ignore_index=True)
            e_slip_csv_path = os.path.join(results_dir, f'e_slip_extraction_{timestamp}.csv')
            e_slip_combined.to_csv(e_slip_csv_path, index=False)
            success_count += len(e_slip_data)
        
        if physical_slip_data:
            physical_slip_combined = pd.concat(physical_slip_data, ignore_index=True)
            physical_csv_path = os.path.join(results_dir, f'physical_slip_extraction_{timestamp}.csv')
            physical_slip_combined.to_csv(physical_csv_path, index=False)
            success_count += len(physical_slip_data)
        
        # Create a summary report
        summary_data = {
            'processing_timestamp': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            'total_e_slips_processed': [len(e_slip_data)],
            'total_physical_slips_processed': [len(physical_slip_data)],
            'total_files_processed': [success_count],
            'total_failed_files': [len(failed_files)],
            'failed_files_list': ['; '.join(failed_files) if failed_files else 'None']
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_csv_path = os.path.join(results_dir, f'extraction_summary_{timestamp}.csv')
        summary_df.to_csv(summary_csv_path, index=False)
        
        # Prepare success message
        message_parts = []
        if e_slip_data:
            message_parts.append(f"E-slips: {len(e_slip_data)} files processed")
        if physical_slip_data:
            message_parts.append(f"Physical slips: {len(physical_slip_data)} files processed")
        
        if success_count > 0:
            success_msg = f"Data extraction completed! {', '.join(message_parts)}. Results saved to app_extraction_csv/ folder. Click 'View Extraction Results' to see the data."
            if failed_files:
                success_msg += f" Note: {len(failed_files)} files failed to process."
        else:
            success_msg = "No data could be extracted from uploaded files. Please check your files and try again."
            
        return redirect(url_for('index', message=success_msg))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return redirect(url_for('index', message=f'Error during bulk extraction: {str(e)}'))

@app.route('/view_results')
def view_results():
    """Display all extraction results"""
    try:
        results_dir = EXTRACT_ALL_DATA_PATH
        
        if not os.path.exists(results_dir):
            return render_template('view_results.html', 
                                 message="No results directory found. Please run data extraction first.",
                                 e_slip_results=[], 
                                 physical_slip_results=[], 
                                 summary_results=[])
        
        # Get all CSV files from results directory
        e_slip_results = []
        physical_slip_results = []
        summary_results = []
        
        for filename in os.listdir(results_dir):
            if filename.endswith('.csv'):
                file_path = os.path.join(results_dir, filename)
                try:
                    # Determine file type based on filename
                    if 'e_slip_extraction' in filename:
                        df = pd.read_csv(file_path)
                        e_slip_results.append({
                            'filename': filename,
                            'data': df,
                            'record_count': len(df),
                            'file_path': file_path,
                            'creation_time': os.path.getmtime(file_path)
                        })
                    elif 'physical_slip_extraction' in filename:
                        df = pd.read_csv(file_path)
                        physical_slip_results.append({
                            'filename': filename,
                            'data': df,
                            'record_count': len(df),
                            'file_path': file_path,
                            'creation_time': os.path.getmtime(file_path)
                        })
                    elif 'extraction_summary' in filename:
                        df = pd.read_csv(file_path)
                        summary_results.append({
                            'filename': filename,
                            'data': df,
                            'file_path': file_path,
                            'creation_time': os.path.getmtime(file_path)
                        })
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
                    continue
        
        # Sort by creation time (newest first)
        e_slip_results.sort(key=lambda x: x['creation_time'], reverse=True)
        physical_slip_results.sort(key=lambda x: x['creation_time'], reverse=True)
        summary_results.sort(key=lambda x: x['creation_time'], reverse=True)
        
        # Convert timestamps to readable format
        for result_list in [e_slip_results, physical_slip_results, summary_results]:
            for result in result_list:
                result['creation_time_str'] = datetime.fromtimestamp(result['creation_time']).strftime("%Y-%m-%d %H:%M:%S")
        
        return render_template('view_results.html', 
                             e_slip_results=e_slip_results,
                             physical_slip_results=physical_slip_results,
                             summary_results=summary_results,
                             message=None)
                             
    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template('view_results.html', 
                             message=f"Error loading results: {str(e)}",
                             e_slip_results=[], 
                             physical_slip_results=[], 
                             summary_results=[])

@app.route('/download_csv/<path:filename>')
def download_csv(filename):
    """Download a specific CSV file"""
    try:
        results_dir = EXTRACT_ALL_DATA_PATH
        file_path = os.path.join(results_dir, filename)
        
        # Security check
        if not os.path.abspath(file_path).startswith(os.path.abspath(results_dir)):
            return "Access denied", 403
        
        if not os.path.exists(file_path):
            return "File not found", 404
            
        return send_from_directory(results_dir, filename, as_attachment=True)
        
    except Exception as e:
        return f"Error downloading file: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True) 