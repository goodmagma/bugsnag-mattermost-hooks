import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Bugsnag / Insight Hub Mattermost Hooks Proxy"

@app.route('/hooks/', defaults={'path': ''}, methods=['POST'])
@app.route('/hooks/<path:path>', methods=['POST'])
def handle_exception(path):
    # Get environment variable
    mattermost_url = os.getenv('MATTERMOST_URL')
    app_debug = os.getenv('APP_DEBUG', False)

    # Read body from POST
    input_data = request.get_data(as_text=True)

    # Extract the 'id' from the path info
    hook_id = path.strip('/') if path else None

    # Decode JSON
    try:
        data = json.loads(input_data)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON error: {str(e)}"}), 400

    # Check if trigger is an exception
    if 'trigger' in data and data['trigger'].get('type') == 'exception':
        project_name = data.get('project', {}).get('name', 'unknown')
        release_stage = data.get('error', {}).get('releaseStage', 'unknown')
        exception_class = data.get('error', {}).get('exceptionClass', 'unknown')
        message = data.get('error', {}).get('message', 'unknown')
        context = data.get('error', {}).get('context', 'unknown')
        request_url = data.get('error', {}).get('requestUrl', None)
        bugsnag_url = data.get('error', {}).get('url', '#')
        unhandled = data.get('error', {}).get('unhandled', False)

        # Determine the message prefix
        error_type = "unhandled exception" if unhandled else "exception"

        # Format stack trace
        stack_trace = "```\n"
        if 'stackTrace' in data['error'] and isinstance(data['error']['stackTrace'], list):
            for frame in data['error']['stackTrace']:
                file = frame.get('file', 'unknown file')
                line = frame.get('lineNumber', 'unknown line')
                method = frame.get('method', 'unknown method')
                stack_trace += f"{file}:{line} in {method}\n"

                # add code if it's present
                if 'code' in frame and isinstance(frame['code'], dict):
                    for code_line, code in frame['code'].items():
                        stack_trace += f"  {code_line}: {code}\n"
        stack_trace += "```\n"

        # Create markdown message
        markdown_message = f"""New **{error_type}** in **{release_stage}** from **{project_name}** in **{context}**:\n\n`{exception_class}: {message}`"""

        # Add request url if present
        if request_url:
            markdown_message += f"\n\n**Request URL**: {request_url}"

        markdown_message += f"\n\n**Stack trace**:\n{stack_trace}\n[View on Bugsnag]({bugsnag_url})"

        # Save message to log file
        if app_debug:
            with open("hooks.log", "a") as log_file:
                log_file.write(markdown_message + "\n\n")

        # Push message to Mattermost Webhook
        webhook_url = f"{mattermost_url}/hooks/{hook_id}"
        payload = json.dumps({"text": markdown_message})

        response = requests.post(webhook_url, headers={'Content-Type': 'application/json'}, data=payload)
        http_code = response.status_code

        # return response to caller
        return jsonify({"status": http_code, "message": response.text})

    else:
        # If not an exception, return a generic response
        return jsonify({"status": 200, "message": "Received"})

if __name__ == '__main__':
    app.run(debug=False)
