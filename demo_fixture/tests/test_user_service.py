from app.services.user_service import UserService

def test_create_user():
    service = UserService()
    user = service.create_user('demo')
    assert user.name == 'demo'
