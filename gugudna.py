def print_gugudan(dan):
    """
    입력받은 단의 구구단을 출력하는 함수
    Args:
        dan (int): 출력할 구구단의 단수
    """
    print(f"\n=== {dan}단 ===")
    for i in range(1, 10):
        print(f"{dan} x {i} = {dan * i}")

def main():
    try:
        # 사용자로부터 단수 입력 받기
        dan = int(input("출력할 구구단의 단수를 입력하세요 (2-9): "))
        
        # 입력값 검증
        if 2 <= dan <= 9:
            print_gugudan(dan)
        else:
            print("2부터 9까지의 숫자만 입력해주세요.")
            
    except ValueError:
        print("올바른 숫자를 입력해주세요.")

if __name__ == "__main__":
    main()
