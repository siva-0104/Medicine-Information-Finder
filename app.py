from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import pandas as pd
import google.generativeai as genai
import time
import cv2
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Replace with your actual path
from translate import Translator

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

app.config['UPLOAD_FOLDER'] = 'uploads/'

merged_df = pd.read_csv('data/preprocessed_data.csv')

# YOUR_API_KEY = "AIzaSyCPCrpxgM-cBdYd-Y-GOgWlr8PSV4Ft_k8"  # Ensure to set this environment variable securely
# genai.configure(api_key=YOUR_API_KEY)
# generation_config = {"temperature": 0.9, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
# model = genai.GenerativeModel("gemini-pro", generation_config=generation_config)

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Placeholder function to get product info from a CSV file
def get_product_info(product_name, target_language='en'):
    product_info = {}
    product_row = None
    product_words = product_name.strip().split()
    translator = Translator(to_lang=target_language)

    # Searching for product in the dataset
    for word in product_words:
        df_filtered = merged_df[merged_df['name'].str.strip().str.lower().str.contains(word.lower())]
        if not df_filtered.empty:
            product_row = df_filtered.iloc[0]
            break

    if product_row is None:
        # If not found in the dataset, use Gemini to get details
        return get_product_info_from_gemini(product_name, target_language)

    product_info['name'] = translator.translate(product_row['name'])
    product_info['price'] = str(product_row['price'])
    product_info['Is_discontinued'] = translator.translate("The product is discontinued, better not to use it.") if product_row['Is_discontinued'] == 1 else translator.translate("The product is not discontinued.")
    product_info['manufacturer_name'] = translator.translate(product_row['manufacturer_name'])
    product_info['pack_size'] = translator.translate(product_row['pack_size_label'])
    product_info['short_composition'] = translator.translate(product_row['short_composition'])
    product_info['substitutes'] = translator.translate(product_row['substitutes'])
    product_info['side_effects'] = translator.translate(product_row['side_effects'])
    product_info['uses'] = translator.translate(product_row['uses'])

    return product_info

# Placeholder function to get product info from Gemini
def initialize_gemini():
    # Example initialization, adjust as per actual API requirements.
    genai.configure(api_key="AIzaSyCPCrpxgM-cBdYd-Y-GOgWlr8PSV4Ft_k8")
    generation_config = {"temperature": 0.9, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
    model = genai.GenerativeModel("gemini-pro", generation_config=generation_config)
    return model

def get_product_info_from_gemini(product_name, target_language='en'):
    model = initialize_gemini()
    max_retries = 3
    retry_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            response = model.generate_content([f"Provide details for {product_name}, including the name, manufacturer, pack size, substitutes, uses, and side effects."])
            generated_text = response.text

            # Process the response to extract the required information
            product_info = {}
            product_info['name'] = product_name

            # Extract the manufacturer
            manufacturer_start = generated_text.find("Manufacturer:")
            manufacturer_end = generated_text.find("\n", manufacturer_start)
            if manufacturer_start != -1 and manufacturer_end != -1:
                product_info['manufacturer_name'] = generated_text[manufacturer_start+14:manufacturer_end].strip()
            else:
                product_info['manufacturer_name'] = None

            # Extract the pack size
            pack_size_start = generated_text.find("Pack size:")
            pack_size_end = generated_text.find("\n", pack_size_start)
            if pack_size_start != -1 and pack_size_end != -1:
                product_info['pack_size'] = generated_text[pack_size_start+10:pack_size_end].strip()
            else:
                product_info['pack_size'] = None

            # Extract the substitutes
            substitutes_start = generated_text.find("Substitutes:")
            substitutes_end = generated_text.find("\n", substitutes_start)
            if substitutes_start != -1 and substitutes_end != -1:
                product_info['substitutes'] = generated_text[substitutes_start+12:substitutes_end].strip()
            else:
                product_info['substitutes'] = None

            # Extract the uses
            uses_start = generated_text.find("Uses:")
            uses_end = generated_text.find("Side Effects:")
            if uses_start != -1 and uses_end != -1:
                product_info['uses'] = generated_text[uses_start+6:uses_end].strip()

            # Extract the side effects
            side_effects_start = generated_text.find("Side Effects:")
            if side_effects_start != -1:
                side_effects_end = generated_text.find(".", side_effects_start)
                if side_effects_end != -1:
                    product_info['side_effects'] = generated_text[side_effects_start+13:side_effects_end+1].strip()
                else:
                    product_info['side_effects'] = generated_text[side_effects_start+13:].strip()

            if target_language != 'en':
                translator = Translator(to_lang=target_language)
                product_info['manufacturer_name'] = translator.translate(product_info['manufacturer_name'])
                product_info['pack_size'] = translator.translate(product_info['pack_size'])
                product_info['substitutes'] = translator.translate(product_info['substitutes'])
                product_info['uses'] = translator.translate(product_info['uses'])
                product_info['side_effects'] = translator.translate(product_info['side_effects'])

            return product_info

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    print("Failed to get response from Gemini API after multiple attempts.")
    return None


# Placeholder function to get product info from an image
def recognize_text_from_image(image_path, target_language='en'):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray)
    if target_language != 'en':
        translator = Translator(to_lang=target_language)
        text = translator.translate(text)
    return text.strip()

def get_product_info_from_image(image_path, target_language='en'):
    product_name = recognize_text_from_image(image_path, target_language)
    product_name=product_name.lstrip("/.?,")
    if not product_name:
        return None
    else:
        print(product_name)
        return get_product_info(product_name, target_language)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_medicine_details', methods=['POST'])
def get_medicine_details():
    medicine_name = request.form.get('medicineName')
    medicine_image = request.files.get('medicineImage')
    target_language = request.form.get('targetLanguage', 'en')

    if medicine_name:
        store = get_product_info(medicine_name, target_language)
    elif medicine_image:
        filename = secure_filename(medicine_image.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        medicine_image.save(filepath)
        store = get_product_info_from_image(filepath, target_language)
    else:
        return jsonify({'error': 'No input provided'}), 400

    if store:
        return jsonify(store)
    else:
        return jsonify({'error': 'Product not found'}), 404

