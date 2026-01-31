import backend.extensions


class AuthService:
    """Service layer for authentication business logic"""

    @staticmethod
    def create_user(email, password, username, active=True):
        """
        Create a new user

        Args:
            email (str): User email
            password (str): User password (will be hashed by Flask-Security)
            username (str): User username
            active (bool): Whether user is active

        Returns:
            tuple: (user, message) - user object or None, status message
        """
        user_datastore = backend.extensions.user_datastore
        if user_datastore.find_user(email=email):
            return None, "User with this email already exists"

        if user_datastore.find_user(username=username):
            return None, "Username already taken"

        user = user_datastore.create_user(
            email=email,
            password=password,
            username=username,
            active=active
        )
        user_datastore.put(user)
        user_datastore.commit()
        return user, "User created successfully"

    @staticmethod
    def get_user_by_email(email):
        """
        Get user by email

        Args:
            email (str): User email

        Returns:
            User: User object or None
        """
        user_datastore = backend.extensions.user_datastore
        return user_datastore.find_user(email=email)

    @staticmethod
    def get_user_by_id(user_id):
        """
        Get user by ID

        Args:
            user_id (int): User ID

        Returns:
            User: User object or None
        """
        user_datastore = backend.extensions.user_datastore
        return user_datastore.find_user(id=user_id)

    @staticmethod
    def assign_role(user, role_name):
        """
        Assign role to user

        Args:
            user (User): User object
            role_name (str): Role name to assign

        Returns:
            tuple: (success, message)
        """
        user_datastore = backend.extensions.user_datastore
        role = user_datastore.find_role(role_name)
        if not role:
            return False, f"Role '{role_name}' not found"

        if role in user.roles:
            return False, "User already has this role"

        user_datastore.add_role_to_user(user, role)
        user_datastore.commit()
        return True, f"Role '{role_name}' assigned to user"

    @staticmethod
    def create_role(name, description=None):
        """
        Create a new role

        Args:
            name (str): Role name
            description (str): Role description

        Returns:
            tuple: (role, message) - role object or None, status message
        """
        user_datastore = backend.extensions.user_datastore
        if user_datastore.find_role(name):
            return None, "Role already exists"

        role = user_datastore.create_role(
            name=name,
            description=description
        )
        user_datastore.put(role)
        user_datastore.commit()
        return role, "Role created successfully"

    @staticmethod
    def deactivate_user(user):
        """
        Deactivate a user

        Args:
            user (User): User object

        Returns:
            tuple: (success, message)
        """
        user_datastore = backend.extensions.user_datastore
        user.active = False
        user_datastore.put(user)
        user_datastore.commit()
        return True, "User deactivated"

    @staticmethod
    def activate_user(user):
        """
        Activate a user

        Args:
            user (User): User object

        Returns:
            tuple: (success, message)
        """
        user_datastore = backend.extensions.user_datastore
        user.active = True
        user_datastore.put(user)
        user_datastore.commit()
        return True, "User activated"