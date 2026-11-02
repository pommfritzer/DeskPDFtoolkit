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

STYLE += """
* { color: #e1eee7; }
QMainWindow { background: #123a31; }
QWidget#catalog { background: transparent; }
QFrame#topbar { background: rgba(9, 30, 29, 215); border-bottom: 1px solid #4c7566; border-radius: 0; }
QLabel#brand { color: #edfff4; font-size: 24px; }
QLabel#eyebrow, QLabel#muted { color: #b5c9bf; }
QLabel#status { color: #c8f2d3; }
QPushButton { background: rgba(27, 61, 51, 225); color: #e1eee7; border: 1px solid #557d6c; }
QPushButton:hover { background: #396e56; border-color: #b2dbc3; }
QPushButton#nav { color: #d5e6dc; padding: 8px; }
QPushButton#nav:checked { background: #426d57; }
QPushButton#card { background: rgba(15, 44, 39, 205); color: #ecf6ef; border: 1px solid #537968; border-radius: 18px; font-size: 14px; padding: 24px; }
QPushButton#card:hover { background: rgba(60, 107, 77, 240); border-color: #c0e2cd; }
QPushButton#primary { background: #bee2c5; color: #143a2a; }
QPushButton#primary:hover { background: #d4efda; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { color: #eaf3ec; background: #183e33; border-color: #5b7f6b; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QListWidget { background: rgba(11, 35, 32, 170); color: #e1eee7; border-color: #4a7160; }
QListWidget::item:selected { background: #3e7256; color: #fff; }
QFrame#preview { background: rgba(18, 48, 39, 200); border-color: #4a7160; }
QMenu { background: #173b30; color: #ecf4ec; border: 1px solid #648d77; }
QMenu::item { padding: 10px 20px; }
QMenu::item:selected { background: #3e7256; }
QSlider::groove:horizontal { height: 5px; background: #50725e; border-radius: 2px; }
QSlider::handle:horizontal { background: #d1ecd8; width: 16px; margin: -6px 0; border-radius: 8px; }
"""

STYLE += "QPushButton#brand { background: transparent; border: 0; padding: 0; font-size: 24px; font-weight: 700; color: #edfff4; }"

STYLE += "QDialog { background: #123a31; } QToolButton { background: #214a3b; color: #e8f3ec; border: 1px solid #658775; border-radius: 6px; padding: 8px 16px; } QToolButton:checked { background: #bee2c5; color: #143a2a; }"

STYLE += "QPushButton#passwordConfirm { border-radius: 17px; background: #bee2c5; color: #143a2a; padding: 0; text-align: center; font-size: 22px; }"

STYLE += "QSplitter::handle:vertical { background: #406f58; } QSplitter::handle:vertical:hover { background: #a2d8b4; }"
