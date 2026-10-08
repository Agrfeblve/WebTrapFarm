from flask import Flask, request, jsonify, send_from_directory, render_template_string
from pathlib import Path

app = Flask(__name__)
ROOT = Path("sites")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(ROOT / "static", filename)

questions_data = [
    {
        'id': 'q1',
        'type': 'checkbox',
        'text': 'Would you like to receive updates about future events or rewards?',
        'options': ['Yes, notify me via email', 'Yes, notify me via SMS', 'No, thank you']
    },
    {
        'id': 'q2',
        'type': 'radio',
        'text': 'Do you agree to the terms and confirm that your information is accurate?',
        'options': ['Yes, I agree', 'No']
    }
]

@app.route('/questionnaire', methods=['GET', 'POST'])
def questionnaire_page():
    if request.method == 'POST':
        print("Received questionnaire data:")
        for key in request.form:
            print(f"{key}: {request.form.getlist(key)}")

        return jsonify({
            'success': True,
            'message': 'Questionnaire submitted successfully, lucky draw unlocked!'
        })

    return render_template(
        'questionnaire.html',
        title='Product Satisfaction Survey',
        questions=questions_data
    )

@app.route("/1/<path:filename>")
def popup_instant(filename):
    file_path = ROOT / "popup-instant" / filename
    html = file_path.read_text(encoding="utf-8")
    return render_template_string(html)

@app.route("/2/<path:filename>")
def popup_later(filename):
    file_path = ROOT / "popup-later" / filename
    html = file_path.read_text(encoding="utf-8")
    return render_template_string(html)

@app.route("/iframe/<iframe_name>")
def serve_iframe(iframe_name):
    file_path = ROOT / "popup-later" / "iframe" / f"{iframe_name}.html"

    if not file_path.exists():
        abort(404)

    html = file_path.read_text(encoding="utf-8")
    return render_template_string(html)

@app.route("/6/<path:filename>")
def ad(filename):
    file_path = ROOT / "ad" / filename
    html = file_path.read_text(encoding="utf-8")
    return render_template_string(html)

@app.route("/3/<path:filename>")
def form_back(filename):
    file_path = ROOT / "form-back" / filename
    html = file_path.read_text(encoding="utf-8")
    return render_template_string(html)

@app.route("/4/<path:filename>")
def form_front(filename):
    file_path = ROOT / "form-front" / filename
    html = file_path.read_text(encoding="utf-8")
    return render_template_string(html)

@app.route("/5/<path:filename>")
def default(filename):
    file_path = ROOT / "default" / filename
    html = file_path.read_text(encoding="utf-8")
    return render_template_string(html)

@app.route("/")
def index():
    return "OK"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8012, debug=True)
