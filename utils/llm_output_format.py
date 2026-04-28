import os
import sys

def replace_latex_delimiters(content: str) -> str:
    """
    将字符串中的 LaTeX 数学定界符替换为纯文本标记：
    \( 和 \) → $
    \[ 和 \] → $$
    """
    # 注意：字符串中的反斜杠需要转义，因此用 "\\(" 表示 \(
    content = content.replace("\\(", "$")
    content = content.replace("\\)", "$")
    content = content.replace("\\[", "$$")
    content = content.replace("\\]", "$$")
    return content

def process_file(file_path: str) -> None:
    """处理单个文件：读取、替换、若变化则写回。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()
    except UnicodeDecodeError:
        # 无法用 UTF-8 解码，可能不是文本文件，跳过
        return
    except Exception as e:
        print(f"读取文件失败 {file_path}: {e}")
        return

    modified = replace_latex_delimiters(original)
    if modified != original:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified)
            print(f"已修改: {file_path}")
        except Exception as e:
            print(f"写入文件失败 {file_path}: {e}")

def main(root_dir: str) -> None:
    """遍历 root_dir 下所有文件，逐一处理。"""
    if not os.path.isdir(root_dir):
        print(f"错误: {root_dir} 不是有效的目录")
        return

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            process_file(file_path)

if __name__ == "__main__":
    # 从命令行参数获取起始目录，默认为当前目录
    path = input("PATH: ")
    main(path)