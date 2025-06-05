import os

def print_directory_tree(start_path, indent=""):
    """
    打印目录树结构
    :param start_path: 起始目录路径
    :param indent: 缩进，用于递归时控制层级
    """
    try:
        entries = os.listdir(start_path)  # 列出当前目录下的所有文件和子目录
        for entry in entries:
            entry_path = os.path.join(start_path, entry)
            if os.path.isdir(entry_path):
                # 如果是目录，打印目录名并递归
                print(f"{indent}📁 {entry}")
                print_directory_tree(entry_path, indent + "    ")
            else:
                # 如果是文件，打印文件名
                print(f"{indent}📄 {entry}")
    except PermissionError:
        print(f"{indent}⛔ [权限不足] 无法访问 {start_path}")

if __name__ == "__main__":
    # 起始目录，可以修改为你想打印的目录路径
    start_directory = "提交内容说明/2312966_林晖鹏+2212574_文雅竹+2313725_张耕嘉+第二次作业/源码"
    print(f"目录树 ({os.path.abspath(start_directory)}):")
    print_directory_tree(start_directory)