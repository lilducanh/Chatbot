import lmstudio as lms  
from lmstudio import Chat  
import mysql.connector  
import re
from datetime import datetime

# Cấu hình cơ sở dữ liệu MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'database': 'quanlynhanvien'
}

# Khởi tạo mô hình LM Studio
model = lms.llm(
    "deepseek-r1-distill-qwen-7b",
    config={
        "contextLength": 8192,
        "url": "ws://localhost:1234/llm"
    }
)

# Hàm kết nối database
def connect_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Lỗi kết nối database: {err}")
        return None

# Lấy schema từ database
def get_database_schema():
    conn = connect_db()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [table[0] for table in cursor.fetchall()]
    
    schema_info = {}
    for table in tables:
        cursor.execute(f"DESCRIBE {table}")
        schema_info[table] = [column[0] for column in cursor.fetchall()]
    
    conn.close()
    return schema_info

# Thực thi truy vấn SQL
def execute_sql(query: str) -> str:
    conn = connect_db()
    if not conn:
        return "Lỗi kết nối database."
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = [dict(zip(columns, row)) for row in results]
        return str(data)
    except mysql.connector.Error as err:
        return f"Lỗi truy vấn: {err}"
    finally:
        conn.close()
#2
# Tạo truy vấn SQL từ câu hỏi
def generate_sql_query(question: str, schema: dict) -> str:
    question_lower = question.lower()

    # Prompt với hướng dẫn rõ ràng hơn để chỉ trả về câu lệnh SQL
    prompt = f"""
    Dưới đây là danh sách bảng và cột trong cơ sở dữ liệu MySQL:
    {', '.join([f"{table}: {', '.join(columns)}" for table, columns in schema.items()])}

    Người dùng hỏi: "{question}"

    Dưới đây là các loại câu hỏi và cách bạn cần xử lý:
    - "Số lượng X": Trả về truy vấn `SELECT COUNT(*) FROM <table_name>` nếu X tương ứng với tên bảng trong schema.
    - "Danh sách X": Trả về truy vấn `SELECT * FROM <table_name>` nếu X tương ứng với tên bảng trong schema.
    - "Tuổi của <tên người>": Trả về truy vấn SQL để tính tuổi từ cột `ngaysinh` và cột `hoten` trong bảng `nhanvien`.
    - "Thông tin X": Trả về truy vấn để tìm thông tin chi tiết từ bảng `nhanvien` dựa trên tên nhân viên.
    
    **Chỉ trả về truy vấn SQL hợp lệ**, không giải thích hay văn bản thừa.
    """

    chat = Chat(prompt)
    result = model.respond(chat, config={"temperature": 0.7, "maxTokens": 200})
    
    # Trả về truy vấn SQL thuần túy mà không có giải thích
    sql_query = result.content.strip()
    
    # Lọc phần <think> hoặc văn bản không cần thiết
    sql_query = re.sub(r"<think>.*?</think>|\n|```sql|```", "", sql_query, flags=re.DOTALL).strip()

    # Kiểm tra tính hợp lệ cơ bản của câu truy vấn SQL
    match = re.search(r"^(SELECT|INSERT|UPDATE|DELETE)\s+.*FROM\s+\w+", sql_query, re.IGNORECASE)
    return match.group(0) if match else "Không thể tạo truy vấn SQL hợp lệ."

# Vòng lặp trò chuyện trên terminal
def chat_loop():
    schema = get_database_schema()
    if not schema:
        print("Không thể lấy schema database. Kiểm tra kết nối!")
        return
    
    chat = Chat("Bạn là chuyên gia truy vấn database MySQL.")
    print("Chào! Hỏi tôi về database (nhập trống để thoát):")
    print(f"Schema: {schema}")

    while True:
        user_input = input("Bạn: ")
        if not user_input:
            print("Tạm biệt!")
            break
        
        chat.add_user_message(user_input)
        
        # Tạo truy vấn SQL
        sql_query = generate_sql_query(user_input, schema)
        print("SQL Query:", sql_query)
        
        if "Không thể" in sql_query:
            print("Bot: Không thể tạo truy vấn SQL hợp lệ.")
        else:
            # Thực thi truy vấn và xử lý kết quả
            result = execute_sql(sql_query)
            if "Lỗi" in result:
                print(f"Bot: {result}")
            else:
                # Xử lý kết quả cho câu hỏi "Số lượng X"
                if "COUNT(*)" in sql_query:
                    count_match = re.search(r"{'COUNT\(\*\)': (\d+)}", result)
                    if count_match:
                        count = count_match.group(1)
                        match_keyword = re.search(r"Số lượng\s+(.+)", user_input.lower())
                        if match_keyword:
                            entity = match_keyword.group(1).strip()
                            print(f"Bot: Số lượng {entity} là {count}.")
                        else:
                            print(f"Bot: Số lượng là {count}.")
                else:
                    print(f"Bot: Danh sách: {result}")

if __name__ == '__main__':
    chat_loop()
