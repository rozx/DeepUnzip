import os
from deepunzip.classes.PasswordBook import PasswordBook


def load_all_passwords(paths: list[str]) -> PasswordBook:
    """Load all passwords from a directory 从目录加载所有密码"""
    password_book = PasswordBook()

    # load password from paths
    for path in paths:
        if os.path.isdir(path):
            # load from directory
            password_book.load_passwords(os.path.join(path, "passwords.txt"))
        else:
            parent_dir = os.path.dirname(path)
            password_book.load_passwords(os.path.join(parent_dir, "passwords.txt"))

    return password_book


def save_all_passwords(password_book: PasswordBook) -> None:
    """Save all passwords to all loaded files 将所有密码保存到所有加载的文件"""
    password_book.save_passwords()
