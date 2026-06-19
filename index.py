"""Scallion 剧本描述语言 —— 解析示例"""

from scallion import Scallion

# 读取示例剧本
with open("article.txt", "r", encoding="utf-8") as f:
    source = f.read()

print("=" * 50)
print("源码:")
print("=" * 50)
print(source)
print()

print("=" * 50)
print("AST (抽象语法树):")
print("=" * 50)
print(Scallion.dump(source))
print()

# 也可以通过脚本对象访问 AST 节点
script = Scallion.parse(source)
print("=" * 50)
print("结构化摘要:")
print("=" * 50)
print(f"角色数: {len(script.enters)}")
for e in script.enters:
    print(f"  - {e.name} (心情: {e.emotion})")
print(f"语句数: {len(script.statements)}")
for s in script.statements:
    print(f"  - {type(s).__name__}")
