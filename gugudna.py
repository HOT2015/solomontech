def print_gugudan(dan):
    """
    입력받은 단의 구구단을 출력하는 함수
    Args:
        dan (int): 출력할 구구단의 단수 (1-100)
    """
    print(f"\n=== {dan}단 ===")
    for i in range(1, 10):
        print(f"{dan:3d} x {i} = {dan * i:4d}")

def main():
    try:
        # 사용자로부터 단수 입력 받기 (1-100 범위로 확장)
        dan = int(input("출력할 구구단의 단수를 입력하세요 (1-100): "))
        
        # 입력값 검증 (1-100 범위로 확장)
        if 1 <= dan <= 100:
            print_gugudan(dan)
        else:
            print("1부터 100까지의 숫자만 입력해주세요.")
            
    except ValueError:
        print("올바른 숫자를 입력해주세요.")

if __name__ == "__main__":
    main()
