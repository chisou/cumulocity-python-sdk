The **Cumulocity Python SDK** (`pyc8y` module) is designed to be
particularly useful for developing Cumulocity microservices. For this,
the module provides two helper classes that take care of microservice
specific authentication.

The [SimpleCumulocityApp][pyc8y.SimpleCumulocityApp] class should be
used for single tenant microservices. It automatically reads the
microservice's environment to determines the microservice access credentials.

The [MultiTenantCumulocityApp][pyc8y.MultiTenantCumulocityApp] class
should be used for multi-tenant microservices which need to handle requests
for arbitrary Cumulocity tenants. It reads the microservice's environment to
determine the necessary bootstrap credentials and provides additional
functions to dynamically obtain `CumulocityApi` instances for specific
tenants.
