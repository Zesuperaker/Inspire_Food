"""
AuthService: Business logic for user and role management

Provides methods for:
- User creation and retrieval
- Role management (create, assign)
- User status management (activate, deactivate)

All methods use Flask-Security's user_datastore for database operations.
This service layer provides a cleaner interface than calling user_datastore directly.

Design:
- All static methods (stateless)
- Returns tuples of (object, message) for success/failure cases
- Checks for duplicates before creating (email, username, role)
"""

import backend.extensions


class AuthService:
    """
    Business logic service for authentication and user management.

    Wraps Flask-Security's user_datastore to provide:
    - Consistent error handling
    - User-friendly error messages
    - Validation before database operations
    - All methods are static (no instance state)
    """

    @staticmethod
    def create_user(email, password, username, active=True):
        """
        Create a new user account.

        Validation:
        - Checks if email already exists (unique constraint)
        - Checks if username already exists (unique constraint)
        - Delegates password hashing to Flask-Security

        Args:
            email (str): User email address
            password (str): User password (Flask-Security will hash it)
            username (str): Display name/login username
            active (bool): Whether account is immediately active (default True)

        Returns:
            tuple: (user_object, message)
                   Success: (User instance, "User created successfully")
                   Failure: (None, "Error message")

        Example:
            user, msg = AuthService.create_user(
                email='alice@example.com',
                password='secure123',
                username='alice'
            )
            if user:
                print(f"Created user {user.id}")
            else:
                print(f"Error: {msg}")
        """
        # Get reference to Flask-Security's user datastore
        user_datastore = backend.extensions.user_datastore

        # Check if email already exists
        if user_datastore.find_user(email=email):
            return None, "User with this email already exists"

        # Check if username already exists
        if user_datastore.find_user(username=username):
            return None, "Username already taken"

        # Create user (Flask-Security handles password hashing)
        # Uses configured password hasher (default: pbkdf2_sha512)
        user = user_datastore.create_user(
            email=email,
            password=password,
            username=username,
            active=active
        )

        # Persist to database
        user_datastore.put(user)
        user_datastore.commit()

        return user, "User created successfully"

    @staticmethod
    def get_user_by_email(email):
        """
        Retrieve a user by email address.

        Args:
            email (str): Email to search for

        Returns:
            User: User object if found, None otherwise

        Example:
            user = AuthService.get_user_by_email('alice@example.com')
            if user:
                print(user.username)
        """
        user_datastore = backend.extensions.user_datastore
        return user_datastore.find_user(email=email)

    @staticmethod
    def get_user_by_id(user_id):
        """
        Retrieve a user by ID.

        Args:
            user_id (int): User's primary key ID

        Returns:
            User: User object if found, None otherwise

        Example:
            user = AuthService.get_user_by_id(5)
            if user:
                print(user.email)
        """
        user_datastore = backend.extensions.user_datastore
        return user_datastore.find_user(id=user_id)

    @staticmethod
    def assign_role(user, role_name):
        """
        Assign a role to a user.

        Validation:
        - Checks if role exists
        - Checks if user already has role (prevents duplicates)

        Args:
            user (User): User object to assign role to
            role_name (str): Name of role to assign (e.g., 'admin', 'user')

        Returns:
            tuple: (success: bool, message: str)

        Example:
            success, msg = AuthService.assign_role(user, 'admin')
            if success:
                print("Role assigned")
        """
        user_datastore = backend.extensions.user_datastore

        # Find the role by name
        role = user_datastore.find_role(role_name)

        # Check if role exists
        if not role:
            return False, f"Role '{role_name}' not found"

        # Check if user already has this role
        if role in user.roles:
            return False, "User already has this role"

        # Add role to user
        user_datastore.add_role_to_user(user, role)
        user_datastore.commit()

        return True, f"Role '{role_name}' assigned to user"

    @staticmethod
    def create_role(name, description=None):
        """
        Create a new authorization role.

        Roles can be assigned to users to grant permissions.
        Examples: 'admin', 'user', 'retailer', 'shopper'

        Args:
            name (str): Unique role name
            description (str): Optional description of role's purpose

        Returns:
            tuple: (role_object, message)
                   Success: (Role instance, "Role created successfully")
                   Failure: (None, "Error message")

        Example:
            role, msg = AuthService.create_role(
                name='retailer',
                description='Retailer account with inventory access'
            )
        """
        user_datastore = backend.extensions.user_datastore

        # Check if role already exists
        if user_datastore.find_role(name):
            return None, "Role already exists"

        # Create new role
        role = user_datastore.create_role(
            name=name,
            description=description
        )

        # Persist to database
        user_datastore.put(role)
        user_datastore.commit()

        return role, "Role created successfully"

    @staticmethod
    def deactivate_user(user):
        """
        Deactivate a user account.

        Deactivation:
        - Marks user.active = False
        - User cannot login while inactive
        - Does NOT delete user (preserves data history)
        - Can be reactivated later

        Args:
            user (User): User object to deactivate

        Returns:
            tuple: (success: bool, message: str)

        Example:
            success, msg = AuthService.deactivate_user(user)
        """
        user_datastore = backend.extensions.user_datastore

        user.active = False
        user_datastore.put(user)
        user_datastore.commit()

        return True, "User deactivated"

    @staticmethod
    def activate_user(user):
        """
        Reactivate a user account.

        Activation:
        - Marks user.active = True
        - User can now login again
        - Undoes a prior deactivation

        Args:
            user (User): User object to activate

        Returns:
            tuple: (success: bool, message: str)

        Example:
            success, msg = AuthService.activate_user(user)
        """
        user_datastore = backend.extensions.user_datastore

        user.active = True
        user_datastore.put(user)
        user_datastore.commit()

        return True, "User activated"