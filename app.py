from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import os
from dotenv import load_dotenv
from PIL import Image
import google.generativeai as genai
from werkzeug.utils import secure_filename
import io

# Load environment variables from .env file
load_dotenv()

# Access the API key
api_key = os.getenv("GEMINI_API_KEY")
if api_key is None:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

# Configure the API with the key
genai.configure(api_key=api_key)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = os.getenv('SECRET_KEY', 'mysecret')  # For session management
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No selected files'}), 400

    prompt = request.form.get('prompt', '')
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    combined_text = ""
    for file in files:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        text = extract_text_from_image(filepath)
        combined_text += text + "\n"

    try:
        full_response = evaluate_text(prompt, combined_text)
        session['full_response'] = full_response
        return jsonify({'status': 'success'})  # Indicate success with JSON
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/result')
def result():
    full_response = session.get('full_response', 'No response available')
    session.pop('full_response', None)  # Clear the response from the session
    return render_template('result.html', response=full_response)

def extract_text_from_image(image_path):
    """Extracts text from an image file using Gemini API."""
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    response = genai.extract_text_from_image(image_bytes)

    if response is None or not hasattr(response, 'text'):
        raise ValueError("No valid response received from the model")

    return response.text

def evaluate_text(prompt, text):
    """Evaluates the extracted text using Gemini API and returns the full response."""
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
    )

    full_prompt = f"{prompt}\n{text}"
    response = model.generate_content(full_prompt)

    if response is None or not hasattr(response, 'text'):
        raise ValueError("No valid response received from the model")

    if 'Score' in response.text:
        return response.text[response.text.index('Score'):].replace('*', ' ')

if __name__ == "__main__":
    app.run(debug=True)
