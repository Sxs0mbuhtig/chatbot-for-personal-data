import logging
import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from worker import init_llm, process_document, process_prompt # Functions imported directly

# Initialize Flask app and CORS
app = Flask(__name__)
# ... other setup ...

# Define the route for processing messages
@app.route('/process-message', methods=['POST'])
def process_message_route():
    user_message = request.json['userMessage']
    print('user_message', user_message)

    # FIX: Changed 'worker_ibm.process_prompt' to 'process_prompt'
    bot_response = process_prompt(user_message)

    # ... rest of the function ...

# Define the route for processing documents
@app.route('/process-document', methods=['POST'])
def process_document_route():
    # ... file checking and saving logic ...

    file = request.files['file']
    file_path = file.filename
    file.save(file_path)

    # FIX: Changed 'worker_ibm.process_document' to 'process_document'
    process_document(file_path)

    # Return a success message as JSON
    return jsonify({
        "botResponse": "Thank you for providing your PDF document. I have analyzed it, so now you can ask me any "
                       "questions regarding it!"
    }), 200

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, port=8000, host='0.0.0.0')
