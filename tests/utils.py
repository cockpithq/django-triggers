from django.db.transaction import get_connection


def run_on_commit():
    connection = get_connection()
    for on_commit_func in connection.run_on_commit:
        on_commit_func[1]()
