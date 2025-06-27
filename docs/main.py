# main.py

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt

class CalculatorUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('공학용 계산기')
        self.setGeometry(100, 100, 300, 400)
        self.setup_ui()

    def setup_ui(self):
        # 메인 위젯 설정
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QPushButton, QLineEdit
        
        # 중앙 위젯 생성
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # 결과 표시창
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setStyleSheet("""
            QLineEdit {
                font-size: 24px;
                padding: 10px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.display)
        
        # 버튼 그리드
        grid = QGridLayout()
        
        # 숫자 버튼
        numbers = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '0']
        positions = [(i, j) for i in range(3, -1, -1) for j in range(3)]
        
        for position, number in zip(positions, numbers):
            button = QPushButton(number)
            button.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    padding: 10px;
                    background-color: #ffffff;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            grid.addWidget(button, *position)
        
        # 연산자 버튼
        operators = ['+', '-', '*', '/']
        for i, operator in enumerate(operators):
            button = QPushButton(operator)
            button.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    padding: 10px;
                    background-color: #f8f9fa;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            grid.addWidget(button, i, 3)
        
        # Clear 버튼
        clear_button = QPushButton('C')
        clear_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 10px;
                background-color: #ff9999;
                border: 1px solid #cc6666;
                border-radius: 5px;
                color: white;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)
        grid.addWidget(clear_button, 4, 0)
        
        # 계산 버튼
        equals_button = QPushButton('=')
        equals_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 10px;
                background-color: #99ccff;
                border: 1px solid #6699cc;
                border-radius: 5px;
                color: white;
            }
            QPushButton:hover {
                background-color: #6699cc;
            }
        """)
        grid.addWidget(equals_button, 4, 1, 1, 2)
        
        layout.addLayout(grid)

def main():
    app = QApplication(sys.argv)
    window = CalculatorUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()