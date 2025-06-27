function addTodo() {
    const todoInput = document.getElementById("todo");
    const todo = todoInput.value.trim(); // 입력 값의 앞뒤 공백 제거

    if (todo === "") {
        alert("할 일을 입력해주세요."); // 할 일이 비어있으면 경고 메시지 표시
        return; // 함수 실행 중단
    }

    const todoList = document.getElementById("todoList");
    const todoItem = document.createElement("li");
    todoItem.textContent = todo;

    // 삭제 버튼 추가 (선택 사항이지만 유용함)
    const deleteButton = document.createElement("button");
    deleteButton.textContent = "삭제";
    deleteButton.onclick = function() {
        todoList.removeChild(todoItem);
    };
    todoItem.appendChild(deleteButton);

    todoList.appendChild(todoItem);

    todoInput.value = ""; // 입력 필드 초기화
}

// "추가" 버튼과 Enter 키 이벤트 연결
document.getElementById("addBtn").onclick = addTodo;
document.getElementById("todo").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        addTodo();
    }
});

