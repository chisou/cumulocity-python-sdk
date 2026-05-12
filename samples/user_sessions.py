# Copyright (c) 2025 Cumulocity GmbH

"""
This sample code demonstrates how to obtain Cumulocity user sessions (sessions
that are run within the context of a named user).

When writing a microservice for Cumulocity you always have two options to
get access to Cumulocity:

  a) Use a technical user' context. This is injected into the microservice
     via environment variables that pyc8y automatically deals with.

  b) Use the context of whatever user accesses the microservice. The
     credentials for this context must be extracted from the inbound request.

The SimpleCumulocityApp and MultiTenantCumulocityApp classes can be used to
get a user specific CumulocityClient instance using the get_user_instance
function as illustrated below. This function will automatically extract the
authorization information within the inbound request's headers and build a
CumulocityClient instance based on that.
"""

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request

from pyc8y.app import SimpleCumulocityApp

load_dotenv()
app = FastAPI()
c8y = SimpleCumulocityApp()


@app.get("/info")
async def info(request: Request):
    """Return user's username and devices they have access to."""
    # The user's credentials (to access Cumulocity and to access the
    # microservice) are part of the inbound request's headers. This is
    # resolved automatically when using the get_user_instance function.
    user_c8y = await c8y.get_user_instance(request.headers)
    return {
        'username': user_c8y.username,
        'devices': [
            {'name': d.name, 'id': d.id, 'type': d.type}
            for d in await user_c8y.device_inventory.get_all()
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app)
