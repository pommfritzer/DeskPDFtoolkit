STYLE = """
* { font-family: 'Segoe UI'; font-size: 13px; color: #23342f; }
QMainWindow, QWidget#root { background: #f6f7f3; }
QFrame#sidebar { background: #edf0e9; border-right: 1px solid #dfe4db; }
QLabel#brand { font-size: 23px; font-weight: 700; letter-spacing: -1px; }
QLabel#eyebrow { color: #6c7d70; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
QLabel#headline { font-size: 34px; font-weight: 600; letter-spacing: -1px; }
QLabel#section { font-size: 17px; font-weight: 600; }
QLabel#muted { color: #748077; }
QLabel#status { color: #456451; padding: 10px 0; }
QPushButton { border: 1px solid #d9dfd5; background: #fff; border-radius: 7px; padding: 10px 14px; text-align: left; }
QPushButton:hover { background: #edf3e9; border-color: #a1b59e; }
QPushButton:focus, QLineEdit:focus, QPlainTextEdit:focus { border: 2px solid #58804e; }
QPushButton:disabled { color: #929b91; background: #e9ece5; }
QPushButton#primary { background: #264f3b; color: #fff; border: 0; font-weight: 600; padding: 13px 18px; }
QPushButton#primary:hover { background: #35654d; }
QPushButton#primary:disabled { background: #a6b6a7; }
QPushButton#nav { background: transparent; border: 0; padding: 12px; }
QPushButton#nav:checked { background: #dce5d6; font-weight: 600; }
QPushButton#card { background: #fff; border: 1px solid #dfe4da; border-radius: 10px; padding: 18px; text-align: left; font-size: 15px; }
QPushButton#card:hover { background: #eef4e9; border-color: #91aa85; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #fff; border: 1px solid #d9dfd5; border-radius: 6px; padding: 9px; selection-background-color: #d4e5c9; }
QScrollArea { border: 0; background: transparent; }
QWidget#catalog { background: #f6f7f3; }
QListWidget { background: #fff; border: 1px solid #dfe4da; border-radius: 7px; padding: 5px; }
QListWidget::item { padding: 10px; border-radius: 4px; }
QListWidget::item:selected { background: #e0eada; color: #23342f; }
QFrame#preview { background: #e8ece4; border: 1px solid #dce2d6; border-radius: 10px; }
QProgressBar { border: 0; background: #e0e6da; border-radius: 3px; max-height: 5px; }
QProgressBar::chunk { background: #527345; }
QToolTip { background: #23342f; color: #fff; padding: 8px; border: none; }
"""
