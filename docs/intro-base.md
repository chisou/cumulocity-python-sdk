The SDK module provides a convenience wrapper around the standard Cumulocity
REST API (see also the [OpenAPI documentation](https://cumulocity.com/api/core/)).

The [CumulocityRestClient][pyc8y.CumulocityRestClient] class provides the
fundamental wrapping around authentication and basic `get`, `post`, 
`put`, `delete` commands. The [CumulocityClient][pyc8y.CumulocityClient]
class is your entrypoint into higher level funct    ions, grouped by
contexts like `inventory`, `users`, and `measurements`. Each of these
contexts is documented in detail within the
`main-api-classes` section.

The [DeviceRegistryClient][pyc8y.DeviceRegistryClient] class
provides an additional entry point for devices, wrapping the entire
bootstrap mechanism. See also the [Device integration
documentation](https://cumulocity.com/guides/device-sdk/rest/#device-integration)
at Cumulocity.
