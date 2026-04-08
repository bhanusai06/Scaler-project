# Your existing content here

# New POST route aliases with OPTIONS handlers for trailing-slash variants
@app.route('/reset/', methods=['POST', 'OPTIONS'])
def reset():
    # Your logic here
    pass

@app.route('/openenv/reset/', methods=['POST', 'OPTIONS'])
def openenv_reset():
    # Your logic here
    pass

@app.route('/env/reset/', methods=['POST', 'OPTIONS'])
def env_reset():
    # Your logic here
    pass

@app.route('/api/reset/', methods=['POST', 'OPTIONS'])
def api_reset():
    # Your logic here
    pass
