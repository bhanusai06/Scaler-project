from fastapi import FastAPI
from existing_file import reset, ResponseModel  # Assuming the original reset handler and model are in 'existing_file'

app = FastAPI()


# Common reset endpoint aliases
@app.post('/reset', response_model=ResponseModel)
async def reset_alias():
    return await reset()

@app.post('/openenv/reset', response_model=ResponseModel)
async def openenv_reset_alias():
    return await reset()

@app.post('/env/reset', response_model=ResponseModel)
async def env_reset_alias():
    return await reset()

@app.post('/api/reset', response_model=ResponseModel)
async def api_reset_alias():
    return await reset()


# OPTIONS handlers to avoid preflight issues
@app.options('/reset')
@app.options('/openenv/reset')
@app.options('/env/reset')
@app.options('/api/reset')
async def options_handler():
    return 200
