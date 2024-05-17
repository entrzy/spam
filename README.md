@app.route('/normal', methods=['POST'])
def normal():
    try:
        # Attempt to parse JSON from the request
        data = request.get_json()

        # Assuming that any syntactically correct JSON is acceptable
        if data is not None:
            # Generate a UUID for tracing, inserted into the original request if needed
            request_id = str(uuid.uuid4())  # Example usage, if you need to use it within the response or for logging
            # Provide a static response as requested
            return jsonify({
                "responseBody": {
                    "chubTransId": "107078096-29090",
                    "acknowledgementId": 3012585945546302260,
                    "errorDescription": "",
                    "errorCode": 0,
                    "status": "ACCEPT"
                }
            }), 200
        else:
            # Handle cases where the JSON is null or not parseable
            return jsonify({"responseBody": {
                "errorDescription": "Invalid JSON format",
                "errorCode": 400,
                "status": "REJECT"
            }}), 400
    except Exception as e:
        # Catch any other exceptions and respond with a server error status
        return jsonify({"responseBody": {
            "errorDescription": str(e),
            "errorCode": 500,
            "status": "REJECT"
        }}), 500
