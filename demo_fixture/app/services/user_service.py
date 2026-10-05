from app.models import User

class UserService:
    def create_user(self, name: str) -> User:
        user = User(name)
        self.save(user)
        return user

    def save(self, user: User) -> None:
        print(user.name)
