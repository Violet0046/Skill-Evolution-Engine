# Patch 格式规则

## Patch 语法

### 基本结构

```
*** Begin Patch
*** Update File: <文件路径>
@@ <锚点行>
 <不变的上下文行>
-<要删除的行>
+<要添加的行>
 <不变的上下文行>
*** End Patch
```

### 锚点行（@@）

- `@@` 后面跟一行**已存在的文本**
- 系统会从文件中定位这行文本
- 在找到锚点行的位置开始应用修改
- 不是 unified-diff 的 `@@ -n,m +n,m @@` 格式

### 行前缀

| 前缀 | 含义 |
|------|------|
| `-` | 删除此行 |
| `+` | 添加此行 |
| ` `（空格） | 保持此行不变（上下文） |

### 多个段落

可以在一个 `*** Update File` 块中有多个 `@@` 段落：

```
*** Begin Patch
*** Update File: SKILL.md
@@ ## 第一节
 ## 第一节
+新增内容
@@ ## 第二节
 ## 第二节
-删除内容
*** End Patch
```

## 其他操作

### 添加文件

```
*** Begin Patch
*** Add File: <文件路径>
+<新行1>
+<新行2>
*** End Patch
```

### 删除文件

```
*** Begin Patch
*** Delete File: <文件路径>
*** End Patch
```

## 应用 Patch 的步骤

1. 读取原始文件内容
2. 解析 Patch 格式
3. 对每个 `@@` 段落：
   a. 在文件中定位锚点行
   b. 从锚点行位置开始应用修改
4. 保存修改后的文件

## 示例

### 修复脚本路径

```
*** Begin Patch
*** Update File: SKILL.md
@@ ## 执行步骤
 ## 执行步骤
+
+1.5 **检查路径**: 使用绝对路径而非相对路径
*** End Patch
```

### 添加错误处理

```
*** Begin Patch
*** Update File: SKILL.md
@@ ## 错误处理
 ## 错误处理
+
+如果遇到 429 或 5xx 错误，等待 2 秒后重试，最多 3 次。
*** End Patch
```

### 修改参数

```
*** Begin Patch
*** Update File: SKILL.md
@@ curl -X POST
-curl -X POST -H "Content-Type: text/plain"
+curl -X POST -H "Content-Type: application/json"
*** End Patch
```

## 注意事项

1. 锚点行必须**精确匹配**（包括空格和大小写）
2. 上下文行帮助定位，但只有标记了 `-` 或 `+` 的行会被修改
3. 如果锚点行在文件中不存在，Patch 应用失败
4. 建议使用足够独特的行作为锚点，避免歧义
