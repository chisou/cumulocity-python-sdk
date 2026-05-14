import asyncio
from typing import Self, AsyncIterator, Sequence


from pyc8y.base_util import unwrap_args, ensure_sequence
from pyc8y.model.matcher import JsonMatcher
from pyc8y.auth import BasicAuth
from pyc8y.rest import CumulocityRestClient
from pyc8y.model.model_base import CumulocityObject, json_property, time_property, datetime_property, \
    CumulocityResource, JsonObject, references_property, map_params, resolve_page_size, run_batched, ensure_ids
from pyc8y.types import UserMeta, CurrentUserMeta, UserGroupMeta, InventoryRoleMeta


class TfaSettings(JsonObject):
    """TFA settings representation within Cumulocity.

    This is a regular JSON dict which features convenience properties for
    known/default entries.
    """
    enabled = json_property[bool]('tfaEnabled')
    enforced = json_property[bool]('tfaEnforced')
    strategy = json_property[str]('strategy')
    last_request_time = time_property('lastTfaRequestTime')
    last_request_datetime = datetime_property('lastTfaRequestTime')


class UserGroup(CumulocityObject):
    """Represents a Group object ("Global Role") within Cumulocity.

    Notes:
      - Global Roles are called 'groups' in the Cumulocity Standard REST API;
        However, 'global roles' is the official concept name and therefore
        used for consistency with the Cumulocity realm.

      - Only a limited set of properties are actually updatable. Others must
        be set explicitly using the corresponding API (for example: permissions).

    See also: https://cumulocity.com/api/core/#tag/Groups
    """

    _meta = UserGroupMeta

    def __init__(
            self,
            c8y:CumulocityRestClient | None = None,
            name: str | None = None,
            description: str | None = None,
    ):
        super().__init__(c8y)
        self.name = name
        self.description = description

    name = json_property[str]("name")
    description = json_property[str]("description")
    applications = json_property("applications")
    application_ids = references_property("applications", "application")
    role_ids = references_property("roles", "role")

    @property
    def object_path(self) -> str:
        return f'/user/{self.c8y.tenant_id}/groups/{self.id}'

    async def _create(self) -> Self:
        self._assert_c8y()
        return self._build(
            json=await self.c8y.post(
                f'/user/{self.c8y.tenant_id}/groups',
                json=self.to_json(),
                accept=self._meta.object_mime_type,
            ),
            c8y=self.c8y,
        )

    async def create(self) -> Self:
        """Create the GlobalRole within the database.

        Returns:
            A fresh GlobalRole object representing what was
            created within the database (including the ID).
        """
        return await self._create()

    async def reload(self, copy: bool = False) -> Self:
        """Reload this object's data from database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The reloaded GlobalRole. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._reload(copy)


    async def update(self, copy: bool = False) -> Self:
        """Write changes to the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated GlobalRole. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    async def delete(self):
        """Delete this object within the database."""
        await self._delete()

    async def assign_roles(self, *role_ids: str):
        self._assert_c8y()
        self._assert_key()
        await UserGroups(self.c8y).assign_roles(self.id, *role_ids)

    async def unassign_roles(self, *role_ids: str):
        self._assert_c8y()
        self._assert_key()
        await UserGroups(self.c8y).unassign_roles(self.id, *role_ids)

    async def assign_users(self, *users: str):
        """Assign users to this group.

        This operation is executed immediately.

        Args:
            *users (str):  An Iterable of usernames
        """
        self._assert_c8y()
        self._assert_key()
        await UserGroups(self.c8y).assign_users(self.id, *users)

    async def unassign_users(self, *users: str):
        """Unassign users from this group.

        This operation is executed immediately.

        Args:
            *users (str):  An Iterable of usernames
        """
        self._assert_c8y()
        self._assert_key()
        await UserGroups(self.c8y).unassign_users(self.id, *users)


class UserGroups(CumulocityResource):
    """Provides access to the (User) Groups API.

    Notes:
      - User groups are called _Global Roles_  in the Cumulocity UI; However,
        'group' is the technical name and therefore used for consistency with
        the REST API.

    See also: https://cumulocity.com/api/core/#tag/Groups
    """
    _meta = UserGroupMeta
    _object_type = UserGroup

    @property
    def resource_path(self) -> str:
        return f"user/{self.c8y.tenant_id}/groups"

    def build_object_path(self, object_id: str) -> str:
        return f"user/{self.c8y.tenant_id}/groups/{object_id}"

    async def get(self, group_id: int | str):
        """Retrieve a specific group.

        Args:
            group_id (int|str): The ID of the user group.

        Returns:
            A UserGroup instance
        """
        return await self._get((str(group_id)))

    async def get_by_name(self, name: str):
        """Retrieve a specific group by name.

        Args:
            name (str): The name of the user group.

        Returns:
            A UserGroup instance
        """
        return UserGroup._build(
            await self.c8y.get(
                f"/user/{self.c8y.tenant_id}/groupByName/{name}",
                accept=self._meta.object_mime_type,
            ),
            c8y=self.c8y,
        )

    async def resolve_group_ids(self, *names: str) -> list[int]:
        """Resolve group names to their numeric IDs.

        Args:
            *names (str): Names of user groups to resolve.

        Returns:
            List of numeric group IDs
        """
        return [g.id for g in await asyncio.gather(*[self.get_by_name(n) for n in names])]

    def select(
            self,
            expression: str | None = None,
            *,
            username: str | None = None,
            limit: int | None = 5,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> AsyncIterator[UserGroup]:
        """Iterate over user groups.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            username (str): Retrieve groups assigned to a specified user
                If omitted, all available groups are returned
            include (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The inclusion is applied first.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            exclude (str | JsonMatcher): Matcher/expression to filter the query
                results (on client side). The exclusion is applied second.
                Creates a PyDF (Python Display Filter) matcher by default for strings.
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int): Pull a specific page; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.
            workers (int):  Number of pages to fetch in parallel; defaults to sequential

        Return:
            Generator of GlobalRole instances

        See also:
            https://github.com/bytebutcher/pydfql/blob/main/docs/USER_GUIDE.md#4-query-language
        """
        page_size = resolve_page_size(page_size, limit, include, exclude)
        async def fetch_page(page: int, **_) -> list:
            """Custom page fetcher for get by username."""
            result = await self.c8y.get(
                f'/user/{self.c8y.tenant_id}/users/{username}/groups',
                params=(('pageSize', page_size), ('currentPage', page)),
            )
            return [ref['group'] for ref in result['references']]

        return super()._iterate(
            expression=expression,
            fetch_page=fetch_page if username else None,
            page_number=page_number,
            limit=limit,
            include=include,
            exclude=exclude,
            as_values=as_values,
            workers=workers,
        )

    async def get_all(
            self,
            expression: str | None = None,
            *,
            username: str | None = None,
            limit: int | None = 5,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> list[UserGroup]:
        """Query the database for user groups and return the results as a list.

        This function is a greedy version of the `select` function. All
        available results are read immediately and returned as a list.

        See `select` for a documentation of arguments.

        Returns:
            List of UserGroup objects
        """
        return [x async for x in self.select(
            expression=expression,
            username=username,
            limit=limit,
            include=include,
            exclude=exclude,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
        )]

    async def get_count(self, expression: str | None = None, *, username: str | None = None) -> int:
        """Calculate the number of user groups in the database.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            username (str): Count groups assigned to a specific user;
                if omitted, the total number of groups is returned.

        Returns:
            Number of user groups
        """
        if expression:
            result = await self.c8y.get(
                f"{self.resource_path}?{expression}&pageSize=1&withTotalPages=true"
            )
            return result['statistics']['totalPages']
        if username:
            path = f'/user/{self.c8y.tenant_id}/users/{username}/groups'
        else:
            path = f'/user/{self.c8y.tenant_id}/groups'
        result = await self.c8y.get(path, params=(('pageSize', '1'), ('withTotalPages', 'true')))
        return result['statistics']['totalPages']

    async def create(self, *groups: UserGroup, workers: int | None = None) -> None:
        """Create user groups within the database.

        Args:
            *groups (UserGroup): Collection of UserGroup instances
            workers (int): Number of parallel requests
        """
        await self._create(*groups, workers=workers)

    async def update(self, *groups: UserGroup, workers: int | None = None) -> None:
        """Update user groups within the database.

        Args:
            *groups (UserGroup): Collection of UserGroup instances
            workers (int): Number of parallel requests
        """
        await self._update(*groups, workers=workers)

    async def delete(self, *groups: str | int | UserGroup, workers: int | None = None) -> None:
        """Delete user groups from the database.

        Args:
            *groups (str | int | UserGroup): Group objects or IDs to delete
            workers (int): Number of parallel requests
        """
        await self._delete(*groups, workers=workers)

    async def assign_users(self, group_id: int | str, *usernames: str, workers: int | None = None):
        """Assign users to a global role.

        Args:
            group_id (int|str):  Technical ID of the user group
            *usernames (str):  Iterable of usernames to assign
            workers (int):  Number of parallel requests; defaults to sequential
        """
        path = f"{self.build_object_path(str(group_id))}/users"
        await run_batched(
            list(usernames), workers,
            lambda u: self.c8y.post(path, json={'user': {'self': f'/user/{self.c8y.tenant_id}/users/{u}'}}, accept=None),
        )

    async def unassign_users(self, group_id: int | str, *usernames: str, workers: int | None = None):
        """Unassign users from a user group.

        Args:
            group_id (int|str):  Technical ID of the user group
            *usernames (str):  Iterable of usernames to unassign
            workers (int):  Number of parallel requests; defaults to sequential
        """
        base_path = self.build_object_path(str(group_id)) + '/users/'
        await run_batched(list(usernames), workers, lambda u: self.c8y.delete(base_path + u))

    async def assign_roles(self, group_id: int | str, *role_ids: str, workers: int | None = None):
        """Add roles to a user group.

        Args:
            group_id (int|str):  Technical ID of the global role
            *role_ids (str):  Iterable of role ID to assign
            workers (int):  Number of parallel requests; defaults to sequential
        """
        path = f"{self.build_object_path(str(group_id))}/roles"
        await run_batched(
            unwrap_args(role_ids),
            workers,
            lambda r: self.c8y.post(path, json={'role': {'self': f'user/roles/{r}'}}, accept=None)
        )

    async def unassign_roles(self, group_id: int | str, *role_ids: str, workers: int | None = None):
        """Remove roles from a user group.

        Args:
            group_id (int|str):  Technical ID of the global role
            *role_ids (str):  Iterable of role ID to assign
            workers (int):  Number of parallel requests; defaults to sequential
        """
        path = f"{self.build_object_path(str(group_id))}/roles"
        await run_batched(
            unwrap_args(role_ids),
            workers,
            lambda r: self.c8y.delete(f"{path}/{r}")
        )


class BaseUser(CumulocityObject):
    """Represents a User object within Cumulocity."""

    _meta = UserMeta

    def __init__(
            self,
            c8y: CumulocityRestClient | None = None,
            username: str | None = None,
            email: str | None = None,
            enabled: bool = True,
            display_name: str | None = None,
            password: str | None = None,
            first_name: str | None = None,
            last_name: str | None = None,
            phone: str | None = None,
            tfa_enabled: bool = False,
            require_password_reset: bool = False,
    ):
        super().__init__(c8y)
        if username is not None:
            self._staged_json["userName"] = username
        self.enabled = enabled
        self.email = email
        self.display_name = display_name
        self.password = password
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.tfa_enabled = tfa_enabled
        if not password:
            self.send_password_reset_email = True
            # self.should_reset_password = True

    username = json_property[str]("userName", read_only=True)
    password_strength = json_property("passwordStrength", read_only=True)

    owner = json_property[str]("owner", read_only=True)
    delegated_by = json_property("delegatedBy", read_only=True)

    email = json_property[str]("email")
    enabled = json_property[bool]("enabled")
    display_name = json_property[str]('displayName')
    password = json_property[str]('password')
    first_name = json_property[str]('firstName')
    last_name = json_property[str]('lastName')
    phone = json_property[str]('phone')
    tfa_enabled = json_property[bool]('twoFactorAuthenticationEnabled')
    last_password_change = time_property('lastPasswordChange')
    last_password_change_datetime = datetime_property('lastPasswordChange')
    require_password_reset = json_property[bool]('shouldResetPassword')
    should_reset_password = json_property[bool]('shouldResetPassword')
    send_password_reset_email = json_property[bool]('sendPasswordResetEmail')

    async def reload(self, copy: bool = False) -> Self:
        """Reload the User from the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The reloaded User. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._reload(copy)

    async def update(self, copy: bool = False) -> Self:
        """Update the User within the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated User. By default this is `self`; if `copy=True`,
            a fresh instance.
        """
        return await self._update(copy)

    def _assert_key(self):
        # override as users use their username as key
        if not self.username:
            raise ValueError("Username must be provided.")


class Permission(JsonObject):
    """Represents a permission within an inventory role.

    See also: https://cumulocity.com/api/core/#tag/Inventory-Roles
    """

    class Level:
        ANY = "*"
        READ = "READ"
        WRITE = "ADMIN"

    class Scope:
        ANY = "*"
        ALARM = "ALARM"
        AUDIT = "AUDIT"
        EVENT = "EVENT"
        MEASUREMENT = "MEASUREMENT"
        MANAGED_OBJECT = "MANAGED_OBJECT"
        OPERATION = "OPERATION"

    permission = json_property[str]("permission")
    scope = json_property[str]("scope")
    type = json_property[str]("type")

    def __init__(self, data: dict | None = None, *, level: str = Level.ANY, scope: str = Scope.ANY, type: str = "*"):
        if data is not None:
            super().__init__(data)
        else:
            super().__init__()
            self.level = level
            self.scope = scope
            self.type = type

    @classmethod
    def from_json(cls, data: dict) -> Self:
        return cls(data)

    @property
    def id(self) -> int | None:
        return self.get("id", None)


class ReadPermission(Permission):
    """Represents a read-only permission within an inventory role."""

    def __init__(self, scope: str = Permission.Scope.ANY, type: str = "*"):
        super().__init__(level=Permission.Level.READ, scope=scope, type=type)


class WritePermission(Permission):
    """Represents a write permission within an inventory role."""

    def __init__(self, scope: str = Permission.Scope.ANY, type: str = "*"):
        super().__init__(level=Permission.Level.WRITE, scope=scope, type=type)


class AnyPermission(Permission):
    """Represents a read/write permission within an inventory role."""

    def __init__(self, scope: str = Permission.Scope.ANY, type: str = "*"):
        super().__init__(level=Permission.Level.ANY, scope=scope, type=type)


class InventoryRole(CumulocityObject):
    """Represents an inventory role within Cumulocity.

    Inventory roles define a set of permissions scoped to specific managed
    objects (e.g. device groups).

    See also: https://cumulocity.com/api/core/#tag/Inventory-Roles
    """

    _meta = InventoryRoleMeta

    name = json_property[str]("name")
    description = json_property[str]("description")

    @property
    def permissions(self) -> list[Permission]:
        return [Permission.from_json(p) for p in self._json.get("permissions", [])]

    @permissions.setter
    def permissions(self, value: list[Permission]):
        self.set("permissions", list(value))

    async def create(self) -> Self:
        """Create this inventory role within the database.

        Returns:
            A fresh InventoryRole representing the created object.
        """
        return await self._create()

    async def update(self, copy: bool = False) -> Self:
        """Write changes to the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The updated InventoryRole. By default this is `self`; if
            `copy=True`, a fresh instance.
        """
        return await self._update(copy)

    async def reload(self, copy: bool = False) -> Self:
        """Reload this inventory role from the database.

        Args:
            copy (bool): If True, return a fresh instance with the server's
                state and leave self unchanged; default False (mutate self).

        Returns:
            The reloaded InventoryRole. By default this is `self`; if
            `copy=True`, a fresh instance.
        """
        return await self._reload(copy)

    async def delete(self) -> None:
        """Remove this inventory role from the database."""
        await self._delete()


class InventoryRoleAssignment(CumulocityObject):
    """Represents a user's inventory role assignment for a managed object.

    See also: https://cumulocity.com/api/core/#tag/Inventory-Roles
    """

    _meta = None

    managed_object_id = json_property[str]("managedObject.id")

    @property
    def roles(self) -> list[InventoryRole]:
        return [InventoryRole.from_json(r) for r in self._json.get("roles", [])]


class InventoryRoles(CumulocityResource[InventoryRole]):
    """Provides access to the Inventory Roles API.

    See also: https://cumulocity.com/api/core/#tag/Inventory-Roles
    """

    _meta = InventoryRoleMeta
    _object_type = InventoryRole

    async def get(self, role_id: int | str) -> InventoryRole:
        """Retrieve a specific inventory role.

        Args:
            role_id (int|str): ID of the inventory role

        Returns:
            An InventoryRole instance
        """
        return await self._get(str(role_id))

    def select(
        self,
        expression: str | None = None,
        *,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
    ) -> AsyncIterator[InventoryRole]:
        """Iterate over all defined inventory roles.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int): Pull a specific page only
            as_values: Extract values at JSON paths instead of parsing objects
            workers (int): Number of parallel page requests

        Returns:
            AsyncIterator of InventoryRole instances
        """
        page_size = resolve_page_size(page_size, limit)
        return self._iterate(
            expression=expression,
            params=map_params(page_size=page_size) if not expression else (),
            page_number=page_number,
            limit=limit,
            as_values=as_values,
            workers=workers,
        )

    async def get_all(
        self,
        expression: str | None = None,
        *,
        limit: int | None = 5,
        page_size: int | None = None,
        page_number: int | None = None,
        as_values: str | tuple | Sequence[str | tuple] | None = None,
        workers: int | None = None,
    ) -> list[InventoryRole]:
        """Query the database for inventory roles and return the results as a list.

        See `select` for a documentation of arguments.

        Returns:
            List of InventoryRole instances
        """
        return [x async for x in self.select(
            expression=expression,
            limit=limit,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
        )]

    async def create(self, *roles: InventoryRole, workers: int | None = None) -> None:
        """Create inventory roles within the database.

        Args:
            *roles (InventoryRole): Collection of InventoryRole instances
            workers (int): Number of parallel requests
        """
        await self._create(*roles, workers=workers)

    async def update(self, *roles: InventoryRole, workers: int | None = None) -> None:
        """Update inventory roles within the database.

        Args:
            *roles (InventoryRole): Collection of InventoryRole instances
            workers (int): Number of parallel requests
        """
        await self._update(*roles, workers=workers)

    async def delete(self, *roles: str | int | InventoryRole, workers: int | None = None) -> None:
        """Delete inventory roles from the database.

        Args:
            *roles (str|int|InventoryRole): Role objects or IDs to delete
            workers (int): Number of parallel requests
        """
        await self._delete(*roles, workers=workers)

    async def get_assignments(self, username: str) -> list[InventoryRoleAssignment]:
        """Retrieve all inventory role assignments for a user.

        Args:
            username (str): Username of the Cumulocity user

        Returns:
            List of InventoryRoleAssignment instances
        """
        result = await self.c8y.get(f"/user/{self.c8y.tenant_id}/users/{username}/roles/inventory")
        return [
            InventoryRoleAssignment.from_json(j, c8y=self.c8y)
            for j in result["inventoryAssignments"]
        ]

    async def assign(
        self,
        username: str,
        managed_object_id: str | int,
        *roles: InventoryRole | int | str,
    ) -> InventoryRoleAssignment:
        """Assign inventory roles for a managed object to a user.

        Args:
            username (str): Username of the Cumulocity user
            managed_object_id (str|int): ID of the managed object (e.g. device group)
            *roles (InventoryRole|int|str): Role objects or IDs to assign

        Returns:
            The created InventoryRoleAssignment
        """
        role_ids = [r.id if isinstance(r, InventoryRole) else r for r in roles]
        payload = {
            "managedObject": {"id": str(managed_object_id)},
            "roles": [{"id": rid} for rid in role_ids],
        }
        result = await self.c8y.post(
            f"/user/{self.c8y.tenant_id}/users/{username}/roles/inventory",
            json=payload,
        )
        return InventoryRoleAssignment.from_json(result, c8y=self.c8y)

    async def unassign(self, username: str, *assignment_ids: str | int) -> None:
        """Remove inventory role assignments from a user.

        Args:
            username (str): Username of the Cumulocity user
            *assignment_ids (str|int): IDs of existing inventory role assignments
        """
        base_path = f"/user/{self.c8y.tenant_id}/users/{username}/roles/inventory"
        await run_batched(
            assignment_ids,
            None,
            lambda aid: self.c8y.delete(f"{base_path}/{aid}"),
        )


class User(BaseUser):
    """Represents a User object within Cumulocity."""

    @property
    def object_path(self) -> str:
        return f'/user/{self.c8y.tenant_id}/users/{self.username}'

    async def _create(self) -> Self:
        self._assert_c8y()
        return self._build(
            json=await self.c8y.post(
                f'/user/{self.c8y.tenant_id}/users',
                json=self.to_json(),
                accept=self._meta.object_mime_type,
            ),
            c8y=self.c8y,
        )

    async def create(self) -> Self:
        """Create the User within the database.

        Returns:
            A fresh User object representing what was
            created within the database (including the ID).
        """
        return await self._create()

    async def set_owner(self, user_id: str) -> None:
        """Set the owner for this user.

        Args:
            user_id (str): ID of the owner to set; use None to remove.
        """
        self._assert_c8y()
        self._assert_key()
        await Users(self.c8y).set_owner(self.username, user_id)

    async def set_delegate(self, user_id: str) -> None:
        """Set the delegate for this user.

        Args:
            user_id (str): ID of the delegate to set; use None to remove.
        """
        self._assert_c8y()
        self._assert_key()
        await Users(self.c8y).set_delegate(self.username, user_id)

    async def assign_global_role(self, group_id: int | str) -> None:
        """Assign a global role (user group) to this user.

        Args:
            group_id (int|str): ID of an existing user group
        """
        self._assert_c8y()
        self._assert_key()
        await UserGroups(self.c8y).assign_users(group_id, self.username)

    async def unassign_global_role(self, group_id: int | str) -> None:
        """Unassign a global role (user group) from this user.

        Args:
            group_id (int|str): ID of an assigned user group
        """
        self._assert_c8y()
        self._assert_key()
        await UserGroups(self.c8y).unassign_users(group_id, self.username)

    async def retrieve_global_roles(self) -> list[UserGroup]:
        """Retrieve the user's assigned global roles.

        Returns:
            List of assigned UserGroup instances.
        """
        self._assert_c8y()
        self._assert_key()
        return await UserGroups(self.c8y).get_all(username=self.username)

    async def retrieve_inventory_role_assignments(self) -> list[InventoryRoleAssignment]:
        """Retrieve the user's inventory role assignments.

        Returns:
            List of InventoryRoleAssignment instances.
        """
        self._assert_c8y()
        self._assert_key()
        return await InventoryRoles(self.c8y).get_assignments(self.username)

    async def assign_inventory_roles(
        self,
        managed_object_id: str | int,
        *roles: InventoryRole | int | str,
    ) -> InventoryRoleAssignment:
        """Assign inventory roles for a managed object to this user.

        Args:
            managed_object_id (str|int): ID of the managed object (e.g. device group)
            *roles (InventoryRole|int|str): Role objects or IDs to assign

        Returns:
            The created InventoryRoleAssignment
        """
        self._assert_c8y()
        self._assert_key()
        return await InventoryRoles(self.c8y).assign(self.username, managed_object_id, *roles)

    async def unassign_inventory_roles(self, *assignment_ids: str | int) -> None:
        """Unassign inventory role assignments from this user.

        Args:
            *assignment_ids (str|int): IDs of existing inventory role assignments
        """
        self._assert_c8y()
        self._assert_key()
        await InventoryRoles(self.c8y).unassign(self.username, *assignment_ids)

    async def delete(self) -> None:
        """Delete this user from the database."""
        await self._delete()


class CurrentUser(BaseUser):
    """Represents a "current" User object within Cumulocity.

    See also https://cumulocity.com/api/core/#tag/Current-User
    """
    _meta = CurrentUserMeta

    @property
    def object_path(self) -> str:
        return '/user/currentUser'

    async def update_password(self, current_password: str, new_password: str):
        """Update the current user's password.

        Args:
            current_password(str): the current password
            new_password (str): the new password to set
        """
        self._assert_c8y()
        await Users(self.c8y).set_current_password(current_password, new_password)


class Users(CumulocityResource):
    """Provides access to the User API.

    See also: https://cumulocity.com/api/core/#tag/Users
    """

    _meta = UserMeta
    _object_type = User

    def build_object_path(self, object_id: str) -> str:
        return f"user/{self.c8y.tenant_id}/users/{object_id}"

    async def get(self, username: str):
        """Retrieve a specific user.

        Args:
            username (str): The ID of the user (usually the mail address)

        Returns:
            A User instance
        """
        return await self._get(username)

    async def get_current(self) -> CurrentUser:
        """Retrieve current user.

        Returns:
            CurrentUser instance
        """
        return CurrentUser.from_json(
            await self.c8y.get(
                "/user/currentUser",
                accept=CurrentUserMeta.object_mime_type,
            ),
            c8y=self.c8y,
        )

    async def logout_all(self):
        """Terminate all user's sessions."""
        await self.c8y.post(f'/user/logout/{self.c8y.tenant_id}/allUsers', json={})

    def select(
            self,
            expression: str | None = None,
            *,
            username: str | None = None,
            groups: int | UserGroup | Sequence[int | UserGroup] | None = None,
            owner: str | None = None,
            only_devices: bool | None = None,
            with_subusers_count: bool | None = None,
            limit: int | None = 5,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> AsyncIterator[User]:
        """Iterate over users.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            username (str): Filter by username or username prefix
            groups (int|str|UserGroup|Sequence): Filter by group membership; accepts
                group IDs (int or str) or UserGroup instances;
                use UserGroups.resolve_group_id to resolve a group name to an ID first
            owner (str): Filter by owner username
            only_devices (bool): Only return device users (prefixed with `device_`)
            with_subusers_count (bool): Include `subusersCount` field in results
            limit (int | None):  Maximum number of results. Default is 5 to support
                quick Jupyter-style exploration; pass `None` to fetch all matching.
            include (str | JsonMatcher): Client-side inclusion filter
            exclude (str | JsonMatcher): Client-side exclusion filter
            page_size (int | None):  Number of records read per request. If None
                (default), inferred from `limit` and whether client-side filters are
                set.
            page_number (int): Pull a specific page only
            as_values: Extract values at JSON paths instead of parsing objects
            workers (int): Number of parallel page requests

        Note:
            The get_all function supports group names for the groups parameter.

        Returns:
            AsyncIterator of User instances
        """
        # for some reason, the groups param accepts multiple group ID, comma separated
        groups_param = ','.join(str(g) for g in ensure_ids(ensure_sequence(groups))) if groups is not None else None

        page_size = resolve_page_size(page_size, limit, include, exclude)
        params = (
            map_params(
                username=username,
                groups=groups_param,
                owner=owner,
                only_devices=only_devices,
                with_subusers_count=with_subusers_count,
                page_size=page_size,
            )
            if not expression
            else ()
        )

        async def fetch_page(page: int, **_) -> list:
            if expression:
                result = await self.c8y.get(
                    f'/user/{self.c8y.tenant_id}/users?{expression}&currentPage={page}',
                )
            else:
                result = await self.c8y.get(
                    f'/user/{self.c8y.tenant_id}/users',
                    params=(*params, ('currentPage', page)),
                )
            return result['users']

        return super()._iterate(
            expression=expression,
            fetch_page=fetch_page,
            page_number=page_number,
            limit=limit,
            include=include,
            exclude=exclude,
            as_values=as_values,
            workers=workers,
        )

    async def get_all(
            self,
            expression: str | None = None,
            *,
            username: str | None = None,
            groups: str | int | UserGroup | Sequence[str | int | UserGroup] | None = None,
            owner: str | None = None,
            only_devices: bool | None = None,
            with_subusers_count: bool | None = None,
            limit: int | None = 5,
            include: str | JsonMatcher | None = None,
            exclude: str | JsonMatcher | None = None,
            page_size: int | None = None,
            page_number: int | None = None,
            as_values: str | tuple | Sequence[str | tuple] | None = None,
            workers: int | None = None,
    ) -> list[User]:
        """Query the database for users and return the results as a list.

        This function is a greedy version of the `select` function. All
        available results are read immediately and returned as a list.

        See `select` for a documentation of arguments.

        Returns:
            List of User instances
        """

        async def resolve_group_id(obj) -> int:
            if isinstance(obj, int):
                return obj
            if isinstance(obj, UserGroup):
                obj._assert_key()
                return obj.id
            try:
                return int(obj)
            except ValueError:
                return (await UserGroups(self.c8y).get_by_name(obj)).id

        group_ids = (
            await asyncio.gather(*[resolve_group_id(g) for g in ensure_sequence(groups)])
            if groups is not None else None
        )
        return [x async for x in self.select(
            expression=expression,
            username=username,
            groups=group_ids,
            owner=owner,
            only_devices=only_devices,
            with_subusers_count=with_subusers_count,
            limit=limit,
            include=include,
            exclude=exclude,
            page_size=page_size,
            page_number=page_number,
            as_values=as_values,
            workers=workers,
        )]

    async def get_count(
            self,
            expression: str | None = None,
            *,
            username: str | None = None,
            groups: str | int | UserGroup | Sequence[str | int | UserGroup] | None = None,
            owner: str | None = None,
            only_devices: bool | None = None,
    ) -> int:
        """Calculate the number of users in the database.

        Args:
            expression (str): Arbitrary filter expression which will be passed
                to Cumulocity without change; all other filters are ignored
                if this is provided
            username (str): Filter by username or username prefix
            groups (int|str|UserGroup|Sequence): Filter by group membership
            owner (str): Filter by owner username
            only_devices (bool): Only count device users (prefixed with `device_`)

        Returns:
            Number of users
        """
        path = f'/user/{self.c8y.tenant_id}/users'
        if expression:
            result = await self.c8y.get(f"{path}?{expression}&pageSize=1&withTotalPages=true")
            return result['statistics']['totalPages']
        groups_param = ','.join(str(g) for g in ensure_ids(ensure_sequence(groups))) if groups is not None else None
        params = map_params(
            username=username,
            groups=groups_param,
            owner=owner,
            only_devices=only_devices,
            page_size=1,
        )
        result = await self.c8y.get(path, (*params, ('withTotalPages', 'true')))
        return result['statistics']['totalPages']

    async def create(self, *users: User, workers: int | None = None) -> None:
        """Create users within the database.

        Args:
            *users (User): Collection of User instances
            workers (int): Number of parallel requests
        """
        path = f"user/{self.c8y.tenant_id}/users"
        await run_batched(
            unwrap_args(users),
            workers,
            lambda u: self.c8y.post(path, json=u.to_json(), accept=None),
        )

    async def update(self, *users: User, workers: int | None = None) -> None:
        """Update users within the database.

        Args:
            *users (User): Collection of User instances
            workers (int): Number of parallel requests
        """
        await run_batched(
            unwrap_args(users),
            workers,
            lambda u: self.c8y.put(self.build_object_path(u.username), json=u.to_json(only_updated=True), accept=None),
        )

    async def delete(self, *users: str | User, workers: int | None = None) -> None:
        """Delete users from the database.

        Args:
            *users (str | User): User objects or usernames to delete
            workers (int): Number of parallel requests
        """
        usernames = [u.username if isinstance(u, User) else u for u in unwrap_args(users)]
        await run_batched(
            usernames,
            workers,
            lambda u: self.c8y.delete(self.build_object_path(u)),
        )

    async def set_current_password(self, current_password: str, new_password: str):
        """Set the password of the current user.

        Note: This automatically updates the connection with the new auth information.

        Args:
            current_password (str): The current password
            new_password (str): The new password to set
        """
        request_json = {
            'currentUserPassword': current_password,
            'newPassword': new_password,
        }
        await self.c8y.put('/user/currentUser/password', json=request_json, accept=None)
        if isinstance(self.c8y.auth, BasicAuth):
            await self.c8y.close()
            self.c8y.auth = BasicAuth(self.c8y.auth.username, new_password)
            self.c8y._session = None

    async def set_owner(self, user_id: str, owner_id: str | None):
        """Set the owner of a given user.

        Args:
            user_id (str): The user to set an owner for
            owner_id (str):  The ID of the owner user; Can be None to
                unassign/remove the current owner
        """
        resource = f"{self.build_object_path(user_id)}/owner"
        if not owner_id:
            await self.c8y.delete(resource)
        else:
            await self.c8y.put(resource, json={'owner': owner_id}, accept=None)

    async def set_delegate(self, user_id: str, delegate_id: str | None):
        """Set the delegate of a given user.

        Args:
            user_id (str): The user to set a delegate for
            delegate_id (str):  The ID of the delegate user; Can be None to
                unassign/remove the current delegate
        """
        resource = f"{self.build_object_path(user_id)}/delegatedby"
        if not delegate_id:
            await self.c8y.delete(resource)
        else:
            await self.c8y.put(resource, json={'delegatedBy': delegate_id}, accept=None)

    async def get_tfa_settings(self, user_id: str) -> TfaSettings:
        """Read the TFA settings of a given user.

        Args:
            user_id (str): The user to query the settings for

        Returns:
            A TfaSettings object
        """
        return TfaSettings(await self.c8y.get(self.build_object_path(user_id) + '/tfa'))

    async def revoke_totp_secret(self, user_id: str):
        """Revoke the currently set TFA/TOTP secret for a user.

        Args:
            user_id (str): The user to revoke the totp secret for
        """
        await self.c8y.delete(f"{self.build_object_path(user_id)}/totpSecret/revoke")