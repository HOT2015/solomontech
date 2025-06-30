from datetime import datetime

# 현재 시간
current_time = datetime.now()
print(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

# 마감 시간
deadline = datetime.fromisoformat("2025-06-30T20:22:00")
print(f"마감 시간: {deadline.strftime('%Y-%m-%d %H:%M:%S')}")

# 비교
is_passed = current_time > deadline
print(f"현재 시간이 마감 시간보다 늦은가? {is_passed}")

# 시간 차이
time_diff = current_time - deadline
print(f"시간 차이: {time_diff}") 