# Copyright (c) 2025 Cumulocity GmbH

from __future__ import annotations

import logging
from http.client import HTTPConnection

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request

from pyc8y.app import MultiTenantCumulocityApp
from pyc8y.rest import UnauthorizedError


# A multi-tenant aware Cumulocity application can be created just like this.
# The bootstrap authentication information is read from the standard
# Cumulocity environment variables that are injected into the Docker
# container.
# The MultiTenantCumulocityApp class is not a CumulocityClient instance (in
# contrast to SimpleCumulocityApp), it acts as a factory to provide
# specific CumulocityClient instances for subscribed tenants and users.

# load environment from a .env if present
load_dotenv()

# enable full logging for requests
HTTPConnection.debuglevel = 1
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

# initialize cumulocity
c8yapp = MultiTenantCumulocityApp()
logging.info("CumulocityApp initialized.")
c8y_bootstrap = c8yapp.bootstrap_instance
logging.info(f"Bootstrap: {c8y_bootstrap.base_url}, Tenant: {c8y_bootstrap.tenant_id}, User:{c8y_bootstrap.username}")


# setup FastAPI
webapp = FastAPI()


@webapp.get("/health")
async def health():
    """Return dummy health string."""
    return {'status': 'ok'}


@webapp.get("/debug")
async def debug(request: Request):
    """Return debug information."""
    return {
        'headers': dict(request.headers),
        'cookies': dict(request.cookies),
    }


@webapp.get("/tenant")
async def tenant_info(request: Request):
    """Return subscribed tenant's ID, username and devices it has access to."""
    # The subscribed tenant's credentials (to access Cumulocity and to access
    # the microservice) are part of the inbound request's headers. This is
    # resolved automatically when using the get_tenant_instance function.
    c8y = await c8yapp.get_tenant_instance(headers=request.headers, cookies=request.cookies)
    logging.info(f"Obtained tenant instance: tenant: {c8y.tenant_id}, user: {c8y.username}")
    # If the tenant ID is known (e.g. from URL) it can be given directly
    # like this:
    # c8y = await c8yapp.get_tenant_instance(tenant_id='t12345')
    return {
        'tenant': {
            'tenant_id': c8y.tenant_id,
            'base_url': c8y.base_url,
            'username': c8y.username,
        },
        'devices': [
            {'name': d.name, 'id': d.id, 'type': d.type}
            for d in await c8y.device_inventory.get_all()
        ],
    }


@webapp.get("/user")
async def user_info(request: Request):
    """Return user's tenant, username and devices they have access to."""
    # The user's credentials (to access Cumulocity and to access the
    # microservice) are part of the inbound request's headers. This is
    # resolved automatically when using the get_user_instance function.
    # Note: the user connections are cached, hence it can be possible to
    # receive an outdated, no longer valid connection. The corresponding
    # UnauthorizedError must be caught and dealt with.
    for _ in range(2):
        c8y = await c8yapp.get_user_instance(request.headers, request.cookies)
        try:
            logging.info(f"Obtained user instance: tenant: {c8y.tenant_id}, user: {c8y.username}")
            return {
                'username': c8y.username,
                'devices': [
                    {'name': d.name, 'id': d.id, 'type': d.type}
                    for d in await c8y.device_inventory.get_all()
                ],
            }
        except UnauthorizedError:
            await c8yapp.clear_user_cache(c8y.username)
    raise RuntimeError("Unable to obtain a valid user scope connection!")


if __name__ == "__main__":
    uvicorn.run(webapp, host='0.0.0.0', port=80)
