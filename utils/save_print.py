import sys
from contextlib import contextmanager
from typing import List

class Tee:
    """同时将输出写入原始流和缓冲区"""
    def __init__(self, original_stream, buffer: List[str]):
        self.original_stream = original_stream
        self.buffer = buffer

    def write(self, message: str) -> None:
        self.original_stream.write(message)
        self.original_stream.flush()
        self.buffer.append(message)

    def flush(self) -> None:
        self.original_stream.flush()

@contextmanager
def capture_output_to_file(file_path: str):
    """
    上下文管理器：捕获所有 stdout/stderr 输出到控制台并同时保存到指定文件。
    退出上下文时自动将缓冲区内容写入文件。
    """
    output_buffer: List[str] = []
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    sys.stdout = Tee(original_stdout, output_buffer)
    sys.stderr = Tee(original_stderr, output_buffer)

    try:
        yield  # with 块中的代码在这里执行
    finally:
        # 恢复原始输出流
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        # 将捕获的输出写入文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(''.join(output_buffer))
        except Exception as e:
            # 写入失败时打印到控制台（已恢复）
            print(f"无法保存输出到文件 {file_path}: {e}", file=sys.stderr)

# 使用示例
if __name__ == "__main__":
    # 开始捕获，输出将同时显示在控制台，并在程序结束时保存到文件
    capture_output_to_file("output.log")

    # 以下为测试输出
    print("这是一条普通输出")
    print("这是另一条输出", file=sys.stderr)
    print("程序即将退出...")